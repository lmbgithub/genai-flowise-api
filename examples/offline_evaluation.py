"""Run the full evaluation with no endpoint, no credential and no network.

Three scripted flows stand in for a deployment:

* `tagged`     — every branch ends its answer with `[branch: ...]`
* `traced`     — the deployment returns an execution trace
* `untagged`   — the deployment returns text and nothing else

The third is the point. Its answers are *identical in content* to the first
flow's, and the harness scores it 0 — because there is no way to know which
branch produced them. An evaluator that guessed from the wording would report a
number, and the number would be measuring the guess.

    python examples/offline_evaluation.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from routereval import baseline
from routereval.cases import CASES, Branch
from routereval.client import Answer, ScriptedClient
from routereval.evaluate import compare, evaluate_client, evaluate_function

# A scripted flow that routes perfectly except on the adversarial cases, where
# it makes the mistakes a real router makes: it follows the surface verb.
SURFACE_VERB = {
    "What is a derivative, and what is the derivative of x^3?": Branch.CONCEPTUAL,
    "Explain how to compute a standard deviation.": Branch.PRACTICAL,
    "What is the grading formula for the final mark?": Branch.PRACTICAL,
}


def chosen(question: str, expected: Branch) -> Branch:
    return SURFACE_VERB.get(question, expected)


def tagged_client() -> ScriptedClient:
    return ScriptedClient(
        answers={
            case.question: Answer(
                text="...an answer... [branch: "
                f"{chosen(case.question, case.expected).value}]"
            )
            for case in CASES
        }
    )


def traced_client() -> ScriptedClient:
    return ScriptedClient(
        answers={
            case.question: Answer(
                text="...an answer...",
                raw={
                    "text": "...an answer...",
                    "agentFlowExecutedData": [
                        {"nodeLabel": "Condition Agent"},
                        {"nodeLabel": chosen(case.question, case.expected).value.title()},
                    ],
                },
            )
            for case in CASES
        }
    )


def untagged_client() -> ScriptedClient:
    return ScriptedClient(
        answers={case.question: Answer(text="...an answer...") for case in CASES}
    )


def main() -> None:
    reports = [
        evaluate_function(baseline.route, name="keyword baseline"),
        evaluate_client(tagged_client(), name="flow (tagged answers)"),
        evaluate_client(traced_client(), name="flow (execution trace)"),
        evaluate_client(untagged_client(), name="flow (no trace, no tag)"),
    ]
    print(compare(reports))
    print(
        "\nThe last two flows route identically. The only difference is whether the\n"
        "deployment reports which branch ran — and without that the evaluation is\n"
        "not a weaker measurement, it is no measurement."
    )


if __name__ == "__main__":
    main()
