"""Scoring, and every way an accuracy number can flatter a router."""

import math

from routereval.cases import Branch, Case
from routereval.client import Answer, ScriptedClient
from routereval.evaluate import (
    Report,
    Result,
    compare,
    evaluate_client,
    evaluate_function,
)

CASES = (
    Case("easy one", Branch.CONCEPTUAL, "plain"),
    Case("hard one", Branch.PRACTICAL, "tricky", adversarial=True),
)


def tagged(mapping):
    return ScriptedClient(
        answers={q: Answer(text=f"x [branch: {b.value}]") for q, b in mapping.items()}
    )


def test_a_perfect_router_scores_one():
    report = evaluate_client(
        tagged({"easy one": Branch.CONCEPTUAL, "hard one": Branch.PRACTICAL}), CASES
    )
    assert report.accuracy == 1.0


def test_easy_and_adversarial_are_reported_separately():
    # An aggregate hides exactly the half that distinguishes routers.
    report = evaluate_client(
        tagged({"easy one": Branch.CONCEPTUAL, "hard one": Branch.CONCEPTUAL}), CASES
    )
    assert report.easy.accuracy == 1.0
    assert report.adversarial.accuracy == 0.0


def test_an_undetectable_route_counts_as_a_failure_not_a_skip():
    # Skipping them would inflate accuracy by dropping the runs that went wrong.
    client = ScriptedClient(default=Answer(text="no tag here"))
    report = evaluate_client(client, CASES)
    assert report.accuracy == 0.0
    assert report.undetectable == 2


def test_undetectable_routes_are_called_out_in_the_summary():
    report = evaluate_client(ScriptedClient(default=Answer(text="x")), CASES)
    assert "no branch trace or tag" in report.summary()


def test_a_failed_call_does_not_end_the_run():
    # The notebook this replaces let one 502 abort the whole evaluation.
    client = ScriptedClient(
        answers={
            q: Answer(text=f"x [branch: {b.value}]")
            for q, b in {
                "easy one": Branch.CONCEPTUAL,
                "hard one": Branch.PRACTICAL,
            }.items()
        },
        fail_times=1,
    )
    report = evaluate_client(client, CASES)
    assert report.total == 2
    assert report.errors == 1
    assert report.correct == 1


def test_an_error_is_not_undetectable():
    client = ScriptedClient(default=Answer(text="x [branch: conceptual]"), fail_times=1)
    report = evaluate_client(client, CASES)
    assert report.errors == 1
    assert report.undetectable == 0


def test_accuracy_of_an_empty_report_is_undefined_not_zero():
    assert math.isnan(Report("empty", ()).accuracy)


def test_the_confusion_matrix_records_what_it_was_routed_to():
    report = evaluate_client(
        tagged({"easy one": Branch.ADMIN, "hard one": Branch.PRACTICAL}), CASES
    )
    assert report.confusion()[(Branch.CONCEPTUAL, Branch.ADMIN)] == 1


def test_failures_list_only_the_wrong_ones():
    report = evaluate_client(
        tagged({"easy one": Branch.CONCEPTUAL, "hard one": Branch.ADMIN}), CASES
    )
    assert [r.case.question for r in report.failures()] == ["hard one"]


def test_evaluate_function_scores_a_local_router():
    report = evaluate_function(
        lambda q: Branch.CONCEPTUAL, CASES, name="always conceptual"
    )
    assert report.correct == 1


def test_compare_of_nothing():
    assert compare([]) == "no reports"


def test_compare_states_the_gap_over_the_baseline():
    baseline = evaluate_function(
        lambda q: Branch.CONCEPTUAL, CASES, name="keyword baseline"
    )
    better = evaluate_client(
        tagged({"easy one": Branch.CONCEPTUAL, "hard one": Branch.PRACTICAL}),
        CASES,
        name="flow",
    )
    text = compare([baseline, better])
    assert "beats the keyword baseline" in text
    assert "not a measurement" in text  # the n caveat travels with the claim


def test_compare_says_so_when_the_baseline_is_not_beaten():
    baseline = evaluate_function(
        lambda q: q and Branch.CONCEPTUAL, CASES, name="keyword baseline"
    )
    worse = evaluate_client(ScriptedClient(default=Answer(text="x")), CASES, name="flow")
    assert "not beaten" in compare([baseline, worse])


def test_a_result_with_no_detection_is_never_correct():
    assert not Result(CASES[0], None).correct
