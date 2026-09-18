"""The exported flow must still match what the harness expects to find."""

import json
from pathlib import Path

import pytest

from routereval.cases import Branch
from routereval.detect import IGNORED_NODES, NODE_LABELS

FLOW = Path(__file__).resolve().parents[1] / "flow/agentflow-v2-tutor.json"


@pytest.fixture(scope="module")
def flow():
    return json.loads(FLOW.read_text(encoding="utf-8"))


def test_the_export_is_present_and_parses(flow):
    assert flow["nodes"] and flow["edges"]


def test_every_node_is_either_a_known_branch_or_infrastructure(flow):
    # If someone renames a branch in Flowise and re-exports, detection silently
    # stops working. This is the test that catches it.
    for node in flow["nodes"]:
        label = (node.get("data", {}).get("label") or "").lower().replace(" ", "")
        assert label in NODE_LABELS or label in IGNORED_NODES, label


def test_the_three_specialist_branches_are_present(flow):
    labels = {
        NODE_LABELS.get((n.get("data", {}).get("label") or "").lower().replace(" ", ""))
        for n in flow["nodes"]
    }
    assert {Branch.CONCEPTUAL, Branch.PRACTICAL, Branch.ADMIN} <= labels


def test_there_is_a_router_node(flow):
    names = {n.get("data", {}).get("name") for n in flow["nodes"]}
    assert "conditionAgentAgentflow" in names


def test_the_flow_has_no_out_of_scope_branch(flow):
    # Worth asserting rather than assuming: the out-of-scope test cases exist
    # precisely because this deployment cannot answer them, and the README says
    # so. If a branch is ever added, this test fails and the claim gets updated.
    labels = {(n.get("data", {}).get("label") or "").lower() for n in flow["nodes"]}
    assert not any("scope" in label for label in labels)
