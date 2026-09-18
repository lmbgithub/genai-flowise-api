"""The test set has to contain the cases that can actually fail."""

from routereval.cases import ADVERSARIAL, CASES, IN_SCOPE, Branch


def test_every_branch_is_represented():
    assert {c.expected for c in CASES} == set(Branch)


def test_questions_are_unique():
    # A duplicated question silently double-weights one capability.
    assert len({c.question for c in CASES}) == len(CASES)


def test_there_are_adversarial_cases():
    # A set of unambiguous examples is passed by a regex and measures nothing.
    assert len(ADVERSARIAL) >= 5


def test_every_adversarial_case_says_what_it_probes():
    assert all(c.probes for c in ADVERSARIAL)


def test_out_of_scope_cases_exist():
    # A router that cannot say "none of these" fails here, and should.
    assert any(c.expected is Branch.OUT_OF_SCOPE for c in CASES)


def test_in_scope_excludes_out_of_scope():
    assert all(c.expected is not Branch.OUT_OF_SCOPE for c in IN_SCOPE)
    assert len(IN_SCOPE) < len(CASES)


def test_a_prompt_injection_case_is_present():
    assert any("ignore your instructions" in c.question.lower() for c in CASES)


def test_cases_are_in_english():
    assert all(c.question.isascii() for c in CASES)
