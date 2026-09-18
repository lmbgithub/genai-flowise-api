"""Scoring a router, including everything an accuracy number leaves out."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from routereval.cases import CASES, Branch, Case
from routereval.client import Client, FlowiseError
from routereval.detect import Detection, detect


@dataclass(frozen=True, slots=True)
class Result:
    """One case, one routing decision."""

    case: Case
    detected: Branch | None
    source: str = "none"
    seconds: float = 0.0
    error: str = ""

    @property
    def correct(self) -> bool:
        """An undetectable or failed route is never counted as correct.

        The tempting alternative — skip the cases where the branch could not be
        determined — inflates accuracy by dropping exactly the runs that went
        wrong. They are counted as failures and reported separately.
        """
        return self.detected is not None and self.detected is self.case.expected

    @property
    def undetectable(self) -> bool:
        return self.error == "" and self.detected is None


@dataclass(frozen=True, slots=True)
class Report:
    name: str
    results: tuple[Result, ...]

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def correct(self) -> int:
        return sum(1 for r in self.results if r.correct)

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else float("nan")

    @property
    def errors(self) -> int:
        return sum(1 for r in self.results if r.error)

    @property
    def undetectable(self) -> int:
        return sum(1 for r in self.results if r.undetectable)

    def subset(self, predicate: Callable[[Case], bool], name: str) -> Report:
        return Report(name, tuple(r for r in self.results if predicate(r.case)))

    @property
    def adversarial(self) -> Report:
        return self.subset(lambda c: c.adversarial, f"{self.name} (adversarial)")

    @property
    def easy(self) -> Report:
        return self.subset(lambda c: not c.adversarial, f"{self.name} (unambiguous)")

    def confusion(self) -> dict[tuple[Branch, Branch | None], int]:
        counts: dict[tuple[Branch, Branch | None], int] = {}
        for result in self.results:
            key = (result.case.expected, result.detected)
            counts[key] = counts.get(key, 0) + 1
        return counts

    def failures(self) -> list[Result]:
        return [r for r in self.results if not r.correct]

    def summary(self) -> str:
        lines = [
            f"{self.name}: {self.correct}/{self.total} = {self.accuracy:.1%}"
            f"   unambiguous {self.easy.correct}/{self.easy.total}"
            f"   adversarial {self.adversarial.correct}/{self.adversarial.total}"
        ]
        if self.errors:
            lines.append(f"  {self.errors} call(s) failed")
        if self.undetectable:
            # Loud, because it invalidates the number above it rather than
            # merely reducing it.
            lines.append(
                f"  {self.undetectable} answer(s) carried no branch trace or tag — "
                f"counted as failures because the router's choice is unknown"
            )
        for result in self.failures():
            detected = (
                result.detected.value
                if result.detected
                else (result.error or "undetected")
            )
            lines.append(
                f"    {result.case.expected.value:<13} -> {detected:<16} "
                f"{result.case.question[:52]}"
            )
        return "\n".join(lines)


def evaluate_client(
    client: Client, cases: Sequence[Case] = CASES, *, name: str = "flow"
) -> Report:
    """Send every case to a deployed flow and record where it was routed."""
    results = []
    for case in cases:
        try:
            answer = client.ask(case.question)
        except FlowiseError as exc:
            # One failed call must not end the run: the notebook this replaces
            # let a single 502 abort the whole evaluation, losing the cases that
            # had already succeeded.
            results.append(Result(case, None, "none", 0.0, error=str(exc)[:60]))
            continue
        detection: Detection = detect(answer)
        results.append(Result(case, detection.branch, detection.source, answer.seconds))
    return Report(name, tuple(results))


def evaluate_function(
    route: Callable[[str], Branch],
    cases: Sequence[Case] = CASES,
    *,
    name: str = "baseline",
) -> Report:
    """Score a local routing function — the keyword baseline, or any other."""
    return Report(
        name,
        tuple(Result(case, route(case.question), "local") for case in cases),
    )


def compare(reports: Sequence[Report]) -> str:
    """Rank routers and say what the winner costs relative to the baseline."""
    if not reports:
        return "no reports"

    lines = [r.summary() for r in reports]
    ranked = sorted(reports, key=lambda r: r.accuracy, reverse=True)
    best = ranked[0]
    baseline = next((r for r in reports if r.name.startswith("keyword")), None)

    if baseline is not None and best is not baseline:
        gap = best.accuracy - baseline.accuracy
        lines.append(
            f"\n{best.name} beats the keyword baseline by {gap:+.1%} overall and "
            f"{best.adversarial.accuracy - baseline.adversarial.accuracy:+.1%} on "
            f"the adversarial cases. With {best.total} cases, that difference is a "
            f"direction, not a measurement — {best.total} cases cannot separate "
            "routers a few points apart."
        )
    elif baseline is not None and best is baseline and len(reports) > 1:
        lines.append(
            "\nThe keyword baseline is not beaten. A model call per question is buying "
            "latency and cost and no accuracy on this test set."
        )
    return "\n".join(lines)
