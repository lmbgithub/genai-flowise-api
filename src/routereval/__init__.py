"""Does the intelligent router actually route? — an evaluation harness.

Standard library only. `requests` is not needed for one POST, and writing the
retry, timeout and error handling out is the point: the harness has to survive a
502 in the middle of a run, and the notebook this replaces did not.
"""

from routereval.baseline import route as keyword_route
from routereval.cases import CASES, Branch, Case
from routereval.client import (
    Answer,
    AuthError,
    FlowiseClient,
    FlowiseError,
    ScriptedClient,
)
from routereval.detect import Detection, detect
from routereval.evaluate import (
    Report,
    Result,
    compare,
    evaluate_client,
    evaluate_function,
)

__all__ = [
    "CASES",
    "Answer",
    "AuthError",
    "Branch",
    "Case",
    "Detection",
    "FlowiseClient",
    "FlowiseError",
    "Report",
    "Result",
    "ScriptedClient",
    "compare",
    "detect",
    "evaluate_client",
    "evaluate_function",
    "keyword_route",
]
