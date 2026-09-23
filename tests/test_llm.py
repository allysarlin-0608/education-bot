"""Retries, backoff and friendly errors for Groq calls (P0-2)."""
import types

import groq
import httpx
import pytest

from coach import llm, tokens

ORG_LEAK = "org_01abcdEXAMPLE"   # stands in for the org id in Groq's error body


def status_error(cls, status, retry_after=None):
    headers = {"retry-after": str(retry_after)} if retry_after is not None else {}
    response = httpx.Response(status, headers=headers,
                              request=httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions"))
    body = {"error": {"message": f"Rate limit reached for model in organization {ORG_LEAK} ... Upgrade to Dev Tier"}}
    return cls(f"Error code: {status} - {body}", response=response, body=body)


def chunk(text, finish=None):
    return types.SimpleNamespace(choices=[types.SimpleNamespace(
        delta=types.SimpleNamespace(content=text), finish_reason=finish)])


class FakeClient:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []
        self.chat = types.SimpleNamespace(completions=self)

    def create(self, **kwargs):
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.fixture
def waits(monkeypatch):
    slept = []
    monkeypatch.setattr(llm, "_sleep", slept.append)
    return slept


def use(monkeypatch, client):
    monkeypatch.setattr(llm, "get_client", lambda: client)
    return client


SYSTEM = "你是教練。"
MSGS = [{"role": "user", "content": "你好"}]


def test_429_is_retried_with_retry_after_then_succeeds(monkeypatch, waits):
    client = use(monkeypatch, FakeClient([
        status_error(groq.RateLimitError, 429, retry_after=3),
        status_error(groq.RateLimitError, 429),
        iter([chunk("好"), chunk("的", "stop")]),
    ]))
    assert "".join(llm.stream_text(SYSTEM, MSGS, 500)) == "好的"
    assert len(client.calls) == 3
    assert 3 <= waits[0] < 3.6            # honoured retry-after
    assert 4 <= waits[1] < 4.6            # then exponential: 2 ** 2


def test_429_three_times_gives_friendly_busy_message(monkeypatch, waits):
    use(monkeypatch, FakeClient([status_error(groq.RateLimitError, 429, retry_after=1)] * 3))
    with pytest.raises(llm.CoachError) as info:
        list(llm.stream_text(SYSTEM, MSGS, 500))
    assert str(info.value) == llm.BUSY
    assert ORG_LEAK not in str(info.value) and "Upgrade" not in str(info.value)
    assert len(waits) == 2                # 1–2 retries, then give up


def test_413_is_not_retried_and_is_friendly(monkeypatch, waits):
    client = use(monkeypatch, FakeClient([status_error(groq.APIStatusError, 413)]))
    data, error = llm.ask_json(SYSTEM, MSGS)
    assert data is None and error == llm.FAILED
    assert len(client.calls) == 1 and waits == []


def test_connection_error_is_retried(monkeypatch, waits):
    request = httpx.Request("POST", "https://api.groq.com")
    use(monkeypatch, FakeClient([
        groq.APIConnectionError(request=request),
        types.SimpleNamespace(choices=[types.SimpleNamespace(
            message=types.SimpleNamespace(content='{"passed": true, "reply": "好"}'), finish_reason="stop")]),
    ]))
    assert llm.ask_json(SYSTEM, MSGS) == ({"passed": True, "reply": "好"}, None)


def test_empty_reply_is_an_error_not_a_blank_bubble(monkeypatch, waits):
    use(monkeypatch, FakeClient([iter([chunk(None), chunk(None, "length")])]))
    with pytest.raises(llm.CoachError, match=llm.FAILED):
        list(llm.stream_text(SYSTEM, MSGS, 500))


def test_bad_json_is_friendly(monkeypatch, waits):
    use(monkeypatch, FakeClient([types.SimpleNamespace(choices=[types.SimpleNamespace(
        message=types.SimpleNamespace(content="不是 JSON"), finish_reason="stop")])]))
    assert llm.ask_json(SYSTEM, MSGS) == (None, llm.FAILED)


def test_every_request_sets_a_bounded_max_tokens_and_fits(monkeypatch, waits):
    client = use(monkeypatch, FakeClient([iter([chunk("好", "stop")])]))
    history = [{"role": "user", "content": "很長的問題" * 2000}]
    list(llm.stream_text(SYSTEM, history, tokens.CHAT_MAX_TOKENS))
    sent = client.calls[0]
    assert sent["max_completion_tokens"] == tokens.CHAT_MAX_TOKENS
    assert sent["reasoning_effort"] == "low"
    system, *rest = sent["messages"]
    assert tokens.estimate_request(system["content"], rest, sent["max_completion_tokens"]) <= tokens.REQUEST_BUDGET


def test_no_key_message(monkeypatch):
    monkeypatch.setattr(llm, "get_client", lambda: None)
    assert llm.ask_json(SYSTEM, MSGS) == (None, llm.NO_KEY)
