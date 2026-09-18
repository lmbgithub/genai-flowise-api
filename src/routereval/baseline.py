"""A keyword router, in twenty lines, to price the LLM one.

This exists because "the intelligent router sends each question to the right
specialist" is not a finding until something cheap has been tried. If a regex
scores the same, the model is buying latency and per-call cost and nothing else;
if the regex collapses on the adversarial cases and the model does not, that gap
is the actual result.
"""

from __future__ import annotations

import re

from routereval.cases import Branch

# Ordered: the first pattern that matches wins, so the more specific
# vocabularies are listed before the general ones.
RULES: tuple[tuple[Branch, re.Pattern[str]], ...] = (
    (
        Branch.ADMIN,
        re.compile(
            r"\b(deadline|due|submit|submission|grade|grades|mark|marks|enrol|deliver)\b",
            re.I,
        ),
    ),
    (
        Branch.PRACTICAL,
        re.compile(
            r"\b(compute|calculate|solve|differentiate|integrate|evaluate)\b", re.I
        ),
    ),
    (
        Branch.CONCEPTUAL,
        re.compile(
            r"\b(what is|explain|define|definition|difference between|why does)\b", re.I
        ),
    ),
)


def route(question: str) -> Branch:
    """Classify by keyword, defaulting to the conceptual branch.

    The default matters and is worth arguing about. There is no "unsure" option
    here — the baseline must answer, exactly as the deployed flow must — so the
    fallback is the branch that does least damage when wrong: a conceptual
    answer to a practical question is unhelpful, while a practical answer to an
    admin question invents a deadline.
    """
    for branch, pattern in RULES:
        if pattern.search(question):
            return branch
    return Branch.CONCEPTUAL
