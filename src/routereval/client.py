"""Talking to a deployed Flowise AgentFlow over its prediction endpoint.

Uses `urllib` from the standard library rather than `requests`: one POST with a
JSON body and a bearer token does not justify a dependency, and writing the
retry and timeout handling explicitly is the point — the notebook this replaces
called `requests.post(...)` with no retry and a bare `raise_for_status`, so a
single 502 ended the whole evaluation run.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Protocol

DEFAULT_TIMEOUT = 60.0
DEFAULT_RETRIES = 3

#: Status codes worth retrying. 429 and 5xx are transient; 4xx is not, and
#: retrying a 401 three times just takes three times as long to tell you the key
#: is wrong.
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


class FlowiseError(RuntimeError):
    """The endpoint could not be used."""


class AuthError(FlowiseError):
    """Missing or rejected credential."""


@dataclass(frozen=True, slots=True)
class Answer:
    """One response from the flow."""

    text: str
    raw: dict[str, Any] = field(default_factory=dict)
    attempts: int = 1
    seconds: float = 0.0

    @property
    def trace(self) -> list[dict[str, Any]]:
        """The per-node execution record, if the flow returned one.

        This is the field that makes the evaluation possible at all — see
        `detect.py`. Flowise has moved it between keys across versions, so both
        are accepted.
        """
        for key in ("agentFlowExecutedData", "agentReasoning"):
            value = self.raw.get(key)
            if isinstance(value, list):
                return value
        return []


class Client(Protocol):
    """What the evaluation needs. `ScriptedClient` implements it for tests."""

    def ask(self, question: str) -> Answer: ...


@dataclass(frozen=True, slots=True)
class FlowiseClient:
    """A live Flowise prediction endpoint."""

    url: str
    api_key: str | None = None
    timeout: float = DEFAULT_TIMEOUT
    retries: int = DEFAULT_RETRIES
    backoff: float = 1.0
    session_id: str | None = None

    @classmethod
    def from_env(cls, **overrides) -> FlowiseClient:
        """Build from FLOWISE_URL and FLOWISE_API_KEY.

        The key is never a parameter with a default and never appears in a
        repr: this class is frozen and printed in error messages, and a secret
        that reaches a traceback reaches every log that traceback lands in.
        """
        url = overrides.pop("url", None) or os.environ.get("FLOWISE_URL")
        if not url:
            raise AuthError(
                "set FLOWISE_URL to the prediction endpoint, e.g. "
                "https://cloud.flowiseai.com/api/v1/prediction/<flow-id>"
            )
        return cls(url=url, api_key=os.environ.get("FLOWISE_API_KEY"), **overrides)

    def ask(self, question: str) -> Answer:
        if not question.strip():
            raise ValueError("question must not be empty")

        payload: dict[str, Any] = {"question": question}
        if self.session_id:
            # Without an explicit session the flow may carry conversation state
            # between test cases, which turns an evaluation into a dialogue and
            # makes every case after the first depend on the ones before it.
            payload["overrideConfig"] = {"sessionId": self.session_id}

        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        started = time.perf_counter()
        last_error: Exception | None = None

        for attempt in range(1, self.retries + 1):
            request = urllib.request.Request(
                self.url, data=body, headers=headers, method="POST"
            )
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    raw = json.loads(response.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as exc:
                if exc.code in (401, 403):
                    raise AuthError(
                        f"endpoint rejected the credential ({exc.code}); "
                        f"set FLOWISE_API_KEY"
                    ) from exc
                last_error = exc
                if exc.code not in RETRYABLE_STATUS or attempt == self.retries:
                    raise FlowiseError(f"HTTP {exc.code} from {self.url}") from exc
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt == self.retries:
                    raise FlowiseError(
                        f"request failed after {attempt} attempt(s): {exc}"
                    ) from exc
            self._sleep(self.backoff * 2 ** (attempt - 1))
        else:  # pragma: no cover - the loop always breaks or raises
            raise FlowiseError(str(last_error))

        text = raw.get("text")
        if not isinstance(text, str):
            raise FlowiseError(f"response has no 'text' field; keys were {sorted(raw)}")
        return Answer(
            text=text,
            raw=raw,
            attempts=attempt,
            seconds=time.perf_counter() - started,
        )

    @staticmethod
    def _sleep(seconds: float) -> None:  # pragma: no cover - patched in tests
        time.sleep(seconds)


@dataclass
class ScriptedClient:
    """A deterministic stand-in for the deployed flow.

    Every test and the offline example run against this. A harness that has only
    ever been exercised against a live endpoint is untested in exactly the cases
    that matter — the malformed response, the missing trace, the branch that
    answers without being asked.
    """

    answers: dict[str, Answer] = field(default_factory=dict)
    default: Answer | None = None
    calls: list[str] = field(default_factory=list)
    fail_times: int = 0

    def ask(self, question: str) -> Answer:
        self.calls.append(question)
        if self.fail_times > 0:
            self.fail_times -= 1
            raise FlowiseError("scripted transient failure")
        if question in self.answers:
            return self.answers[question]
        if self.default is not None:
            return self.default
        raise KeyError(f"ScriptedClient has no answer for {question!r}")
