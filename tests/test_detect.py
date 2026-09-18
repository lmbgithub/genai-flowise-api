"""Which branch answered — and refusing to guess when that is unknowable."""

import pytest

from routereval.cases import Branch
from routereval.client import Answer
from routereval.detect import branch_from_tag, branch_from_trace, detect, strip_tag


def test_a_tag_is_read():
    detection = detect(Answer(text="an answer [branch: practical]"))
    assert detection.branch is Branch.PRACTICAL
    assert detection.source == "tag"


@pytest.mark.parametrize(
    "text", ["[branch:admin]", "[ branch : ADMIN ]", "[Branch: Admin]"]
)
def test_tag_syntax_is_forgiving(text):
    assert branch_from_tag(text) is Branch.ADMIN


def test_a_tag_naming_an_unknown_branch_is_not_a_guess():
    # A flow bug. Reporting it as undetectable surfaces it; mapping it to a
    # nearby branch would hide it inside the accuracy figure.
    assert branch_from_tag("[branch: wizard]") is None


def test_no_tag_is_none():
    assert branch_from_tag("just an answer") is None


def test_the_trace_wins_over_a_tag():
    # The trace is what the flow did; the tag is what a prompt was asked to say.
    answer = Answer(
        text="an answer [branch: conceptual]",
        raw={"agentFlowExecutedData": [{"nodeLabel": "Practical"}]},
    )
    assert detect(answer).branch is Branch.PRACTICAL
    assert detect(answer).source == "trace"


def test_infrastructure_nodes_are_not_branches():
    # The condition agent is in every trace; counting it would score every run
    # identically and hide the routing entirely.
    trace = [{"nodeLabel": "Start"}, {"nodeLabel": "Condition Agent"}]
    assert branch_from_trace(trace) is None


def test_the_last_specialist_wins():
    # A flow can route, backtrack and route again; the answer the user sees
    # comes from the branch that ran last.
    trace = [{"nodeLabel": "Conceptual"}, {"nodeLabel": "Practical"}]
    assert branch_from_trace(trace) is Branch.PRACTICAL


@pytest.mark.parametrize("key", ["nodeLabel", "agentName", "nodeName", "name", "label"])
def test_node_names_are_read_from_any_of_the_known_keys(key):
    assert branch_from_trace([{key: "Admin"}]) is Branch.ADMIN


def test_nested_node_data_is_read():
    assert branch_from_trace([{"data": {"label": "Admin"}}]) is Branch.ADMIN


def test_both_trace_field_names_are_accepted():
    # Flowise has moved this field between versions.
    for key in ("agentFlowExecutedData", "agentReasoning"):
        answer = Answer(text="x", raw={key: [{"nodeLabel": "Admin"}]})
        assert detect(answer).branch is Branch.ADMIN


def test_a_trace_that_is_not_a_list_is_ignored():
    assert detect(Answer(text="x", raw={"agentReasoning": "oops"})).branch is None


def test_neither_trace_nor_tag_is_none_not_a_guess():
    # The decision the repository turns on: an evaluation that cannot see the
    # route must say so rather than infer one from the answer's wording.
    detection = detect(Answer(text="The Pythagorean theorem states that..."))
    assert detection.branch is None
    assert detection.source == "none"
    assert not detection.certain


def test_the_tag_is_not_shown_to_a_reader():
    assert strip_tag("an answer [branch: admin]") == "an answer"
