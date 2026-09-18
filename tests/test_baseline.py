"""The cheap router, and where it breaks — which is the point of having it."""

import pytest

from routereval.baseline import route
from routereval.cases import ADVERSARIAL, Branch
from routereval.evaluate import evaluate_function


@pytest.mark.parametrize(
    "question,expected",
    [
        ("What is the Pythagorean theorem?", Branch.CONCEPTUAL),
        ("Compute the hypotenuse if the legs are 6 and 8.", Branch.PRACTICAL),
        ("When is the final assignment due?", Branch.ADMIN),
        ("Where can I see my grades?", Branch.ADMIN),
    ],
)
def test_the_unambiguous_cases_are_easy(question, expected):
    assert route(question) is expected


def test_admin_vocabulary_wins_over_subject_vocabulary():
    # Ordering matters: "deadline for the Bayes exercise" is an admin question.
    assert route("Why does the deadline for the Bayes exercise matter?") is Branch.ADMIN


def test_the_fallback_is_the_least_damaging_branch():
    # No keyword matches. A practical answer to an admin question invents a
    # deadline; a conceptual answer to a practical one is merely unhelpful.
    assert route("mmm hmm") is Branch.CONCEPTUAL


def test_it_cannot_express_out_of_scope():
    # Not a bug in the baseline — a property of any router with no reject
    # option, including the deployed flow.
    assert route("What is the weather in Madrid tomorrow?") is not Branch.OUT_OF_SCOPE


def test_it_is_fooled_by_the_surface_verb():
    assert route("Explain how to compute a standard deviation.") is Branch.PRACTICAL


def test_it_scores_well_on_easy_cases_and_badly_on_adversarial_ones():
    # This is the number the deployed router has to beat to justify its cost.
    report = evaluate_function(route, name="keyword baseline")
    assert report.easy.accuracy >= 0.8
    assert report.adversarial.accuracy < report.easy.accuracy


def test_routing_is_case_insensitive():
    assert route("COMPUTE THE HYPOTENUSE") is route("compute the hypotenuse")


def test_every_adversarial_case_still_gets_an_answer():
    assert all(isinstance(route(c.question), Branch) for c in ADVERSARIAL)
