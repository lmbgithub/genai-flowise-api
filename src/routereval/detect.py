"""Working out which branch actually answered.

This is the decision the whole repository turns on. The prediction endpoint
returns a block of text. The text does not say which specialist produced it, and
the specialists are all instructed to sound like helpful tutors — so reading the
answer and deciding which branch it "sounds like" is the evaluator grading its
own guess.

Two sources are used, in order:

1. the flow's execution trace, when the deployment returns one — authoritative;
2. an explicit tag the branch prompt emits, e.g. `[branch: practical]`.

When neither is present the result is `None`, not a guess. An evaluation that
cannot tell which branch ran must say so, because the alternative is an accuracy
figure measuring a heuristic that was never validated.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from routereval.cases import Branch
from routereval.client import Answer

#: A branch prompt ending with this tag makes detection exact with no trace.
TAG = re.compile(r"\[\s*branch\s*:\s*([a-z-]+)\s*\]", re.I)

#: Flowise node labels in the exported flow, mapped to branches.
NODE_LABELS: dict[str, Branch] = {
    "conceptual": Branch.CONCEPTUAL,
    "conceptualtutor": Branch.CONCEPTUAL,
    "practical": Branch.PRACTICAL,
    "practicaltutor": Branch.PRACTICAL,
    "admin": Branch.ADMIN,
    "adminfaq": Branch.ADMIN,
    "outofscope": Branch.OUT_OF_SCOPE,
    "out-of-scope": Branch.OUT_OF_SCOPE,
}

#: Nodes that are infrastructure, not specialists. The condition agent appears
#: in every trace; counting it as the answering branch would score every run
#: identically.
IGNORED_NODES = frozenset(
    {"start", "startagentflow", "conditionagent", "conditionagentflow"}
)


class UndetectableBranch(RuntimeError):
    """Neither a trace nor a tag was available."""


@dataclass(frozen=True, slots=True)
class Detection:
    branch: Branch | None
    source: str  # "trace", "tag", or "none"

    @property
    def certain(self) -> bool:
        return self.branch is not None


def detect(answer: Answer) -> Detection:
    from_trace = branch_from_trace(answer.trace)
    if from_trace is not None:
        return Detection(from_trace, "trace")

    from_tag = branch_from_tag(answer.text)
    if from_tag is not None:
        return Detection(from_tag, "tag")

    return Detection(None, "none")


def branch_from_trace(trace: Sequence[dict[str, Any]]) -> Branch | None:
    """The last specialist node that produced output.

    The last, not the first: a flow can route, backtrack and route again, and
    the branch that produced the answer the user sees is the one that ran last.
    """
    found: Branch | None = None
    for entry in trace:
        name = _node_name(entry)
        if not name or name in IGNORED_NODES:
            continue
        branch = NODE_LABELS.get(name)
        if branch is not None:
            found = branch
    return found


def branch_from_tag(text: str) -> Branch | None:
    match = TAG.search(text or "")
    if not match:
        return None
    try:
        return Branch(match.group(1).lower())
    except ValueError:
        # A tag naming a branch that does not exist is a flow bug worth
        # surfacing as "undetectable" rather than silently ignoring.
        return None


def _node_name(entry: dict[str, Any]) -> str:
    for key in ("nodeLabel", "agentName", "nodeName", "name", "label"):
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().lower().replace(" ", "")
    data = entry.get("data")
    if isinstance(data, dict):
        return _node_name(data)
    return ""


def strip_tag(text: str) -> str:
    """Remove the branch tag so it is not shown to a reader as part of the answer."""
    return TAG.sub("", text).strip()
