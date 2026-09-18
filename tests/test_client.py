"""HTTP behaviour: retries, credentials, and malformed responses."""

import json
import urllib.error

import pytest

from routereval.client import (
    RETRYABLE_STATUS,
    Answer,
    AuthError,
    FlowiseClient,
    FlowiseError,
    ScriptedClient,
)


class FakeResponse:
    def __init__(self, payload):
        self._body = json.dumps(payload).encode()

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def patch_urlopen(monkeypatch, responses):
    """`responses` is a list of payloads or exceptions, consumed in order."""
    calls = []

    def fake(request, timeout=None):
        calls.append(request)
        item = responses[min(len(calls) - 1, len(responses) - 1)]
        if isinstance(item, Exception):
            raise item
        return FakeResponse(item)

    monkeypatch.setattr("urllib.request.urlopen", fake)
    monkeypatch.setattr(FlowiseClient, "_sleep", staticmethod(lambda seconds: None))
    return calls


def http_error(code):
    return urllib.error.HTTPError("http://x", code, "err", {}, None)


def client(**kwargs):
    return FlowiseClient(url="http://example/api", api_key="k", **kwargs)


def test_a_successful_call(monkeypatch):
    patch_urlopen(monkeypatch, [{"text": "hello"}])
    answer = client().ask("a question")
    assert answer.text == "hello"
    assert answer.attempts == 1


def test_the_bearer_token_is_sent(monkeypatch):
    calls = patch_urlopen(monkeypatch, [{"text": "hi"}])
    client().ask("q")
    assert calls[0].headers["Authorization"] == "Bearer k"


def test_no_authorization_header_without_a_key(monkeypatch):
    calls = patch_urlopen(monkeypatch, [{"text": "hi"}])
    FlowiseClient(url="http://example/api").ask("q")
    assert "Authorization" not in calls[0].headers


def test_the_session_id_is_sent_so_cases_cannot_contaminate_each_other(monkeypatch):
    calls = patch_urlopen(monkeypatch, [{"text": "hi"}])
    client(session_id="eval-1").ask("q")
    assert json.loads(calls[0].data)["overrideConfig"]["sessionId"] == "eval-1"


def test_no_override_config_without_a_session(monkeypatch):
    calls = patch_urlopen(monkeypatch, [{"text": "hi"}])
    client().ask("q")
    assert "overrideConfig" not in json.loads(calls[0].data)


@pytest.mark.parametrize("code", sorted(RETRYABLE_STATUS))
def test_transient_failures_are_retried(monkeypatch, code):
    calls = patch_urlopen(monkeypatch, [http_error(code), {"text": "recovered"}])
    answer = client(retries=3).ask("q")
    assert answer.text == "recovered"
    assert answer.attempts == 2
    assert len(calls) == 2


def test_retries_eventually_give_up(monkeypatch):
    calls = patch_urlopen(monkeypatch, [http_error(503)])
    with pytest.raises(FlowiseError, match="503"):
        client(retries=3).ask("q")
    assert len(calls) == 3


@pytest.mark.parametrize("code", [400, 404, 422])
def test_client_errors_are_not_retried(monkeypatch, code):
    # Retrying a 404 three times just takes three times as long to fail.
    calls = patch_urlopen(monkeypatch, [http_error(code)])
    with pytest.raises(FlowiseError):
        client(retries=3).ask("q")
    assert len(calls) == 1


@pytest.mark.parametrize("code", [401, 403])
def test_a_rejected_credential_says_so_immediately(monkeypatch, code):
    calls = patch_urlopen(monkeypatch, [http_error(code)])
    with pytest.raises(AuthError, match="FLOWISE_API_KEY"):
        client(retries=3).ask("q")
    assert len(calls) == 1


def test_a_network_error_is_retried_then_reported(monkeypatch):
    patch_urlopen(monkeypatch, [urllib.error.URLError("no route")])
    with pytest.raises(FlowiseError, match="3 attempt"):
        client(retries=3).ask("q")


def test_a_response_without_text_names_the_keys_it_had(monkeypatch):
    patch_urlopen(monkeypatch, [{"error": "flow not found"}])
    with pytest.raises(FlowiseError, match="error"):
        client().ask("q")


def test_a_non_string_text_field_is_rejected(monkeypatch):
    patch_urlopen(monkeypatch, [{"text": {"nested": "object"}}])
    with pytest.raises(FlowiseError, match="no 'text' field"):
        client().ask("q")


def test_an_empty_question_is_rejected():
    with pytest.raises(ValueError, match="must not be empty"):
        client().ask("   ")


def test_from_env_requires_a_url(monkeypatch):
    monkeypatch.delenv("FLOWISE_URL", raising=False)
    with pytest.raises(AuthError, match="FLOWISE_URL"):
        FlowiseClient.from_env()


def test_from_env_reads_both_variables(monkeypatch):
    monkeypatch.setenv("FLOWISE_URL", "http://example/api")
    monkeypatch.setenv("FLOWISE_API_KEY", "secret")
    built = FlowiseClient.from_env()
    assert built.url == "http://example/api"
    assert built.api_key == "secret"


def test_the_scripted_client_records_calls():
    scripted = ScriptedClient(answers={"q": Answer(text="a")})
    assert scripted.ask("q").text == "a"
    assert scripted.calls == ["q"]


def test_the_scripted_client_can_fail_on_demand():
    scripted = ScriptedClient(default=Answer(text="a"), fail_times=1)
    with pytest.raises(FlowiseError):
        scripted.ask("q")
    assert scripted.ask("q").text == "a"


def test_the_scripted_client_refuses_an_unscripted_question():
    with pytest.raises(KeyError):
        ScriptedClient().ask("unexpected")
