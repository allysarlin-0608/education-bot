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


def test_429_every_time_gives_friendly_busy_message(monkeypatch, waits):
    use(monkeypatch, FakeClient([status_error(groq.RateLimitError, 429, retry_after=1)] * 4))
    with pytest.raises(llm.CoachError) as info:
        list(llm.stream_text(SYSTEM, MSGS, 500))
    assert str(info.value) == llm.BUSY
    assert ORG_LEAK not in str(info.value) and "Upgrade" not in str(info.value)
    assert len(waits) == llm.MAX_RETRIES  # every retry used, then give up


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


def _json_reply(text):
    return types.SimpleNamespace(choices=[types.SimpleNamespace(
        message=types.SimpleNamespace(content=text), finish_reason="stop")])


def test_bad_json_twice_is_friendly(monkeypatch, waits):
    client = use(monkeypatch, FakeClient([_json_reply("不是 JSON"), _json_reply("still not JSON")]))
    assert llm.ask_json(SYSTEM, MSGS) == (None, llm.FAILED)
    assert len(client.calls) == 2               # one automatic retry, then the friendly error


def test_bad_json_once_is_retried_automatically(monkeypatch, waits):
    """BUG-001: one unreadable reply is asked again once before any error shows."""
    client = use(monkeypatch, FakeClient([_json_reply("prose, not JSON"), _json_reply('{"ok": 1}')]))
    assert llm.ask_json(SYSTEM, MSGS) == ({"ok": 1}, None)
    assert len(client.calls) == 2


def test_retries_stop_within_the_time_budget(monkeypatch):
    """BUG-002: however the waits add up, the person hears back within ~30 s."""
    clock = {"t": 1000.0}
    monkeypatch.setattr(llm, "_sleep", lambda s: clock.__setitem__("t", clock["t"] + s))
    monkeypatch.setattr(llm, "_now", lambda: clock["t"])
    client = use(monkeypatch, FakeClient([status_error(groq.RateLimitError, 429, retry_after=14)] * 10))
    with pytest.raises(llm.CoachError, match="busy"):
        list(llm.stream_text(SYSTEM, MSGS, 500))
    assert clock["t"] - 1000.0 <= llm.TOTAL_SECONDS
    assert len(client.calls) < 1 + llm.MAX_RETRIES       # it gave up early rather than wait past the budget


def test_each_request_has_a_timeout(monkeypatch):
    """BUG-002: a hung connection can't hold a request for Groq's default minute."""
    made = {}
    monkeypatch.setattr(llm.groq, "Groq", lambda **kw: made.update(kw) or object())
    monkeypatch.setattr(llm.st, "session_state", {"api_key": "k"})
    llm.get_client()
    assert 0 < made["timeout"] <= llm.REQUEST_TIMEOUT <= 25


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


def _used(total, text='{"ok": 1}'):
    reply = _json_reply(text)
    reply.usage = types.SimpleNamespace(total_tokens=total)
    return reply


def test_a_request_that_would_go_over_the_minute_waits_instead_of_being_refused(monkeypatch):
    """Issue A (A5): the per-minute allowance is kept here, so the quiz after
    a lesson waits a few seconds rather than meeting a 429."""
    # covers: S-groq_tpm_limit
    clock = {"t": 1000.0}
    slept = []
    monkeypatch.setattr(llm, "_sleep", lambda s: (slept.append(s), clock.__setitem__("t", clock["t"] + s)))
    monkeypatch.setattr(llm, "_now", lambda: clock["t"])
    client = use(monkeypatch, FakeClient([_used(6000), _used(1000), _used(1000)]))
    assert llm.ask_json(SYSTEM, MSGS, max_tokens=900) == ({"ok": 1}, None)       # 6000 really used
    assert slept == []
    clock["t"] += 50                                                           # 10 s before it ages out
    assert llm.ask_json(SYSTEM, MSGS, max_tokens=2400) == ({"ok": 1}, None)
    assert len(slept) == 1 and 10 <= slept[0] <= 11, slept
    assert len(client.calls) == 2
    # within the allowance: no wait
    slept.clear()
    assert llm.ask_json(SYSTEM, MSGS, max_tokens=900) == ({"ok": 1}, None)
    assert slept == []


def test_a_wait_longer_than_the_cap_is_not_made(monkeypatch):
    """Pacing never holds a request past MAX_WAIT_SECONDS: it goes, and a 429
    (if it comes) is retried as before."""
    clock = {"t": 1000.0}
    slept = []
    monkeypatch.setattr(llm, "_sleep", lambda s: (slept.append(s), clock.__setitem__("t", clock["t"] + s)))
    monkeypatch.setattr(llm, "_now", lambda: clock["t"])
    use(monkeypatch, FakeClient([_used(7900), _used(500)]))
    llm.ask_json(SYSTEM, MSGS, max_tokens=50)
    clock["t"] += 5                                                            # 55 s still to go
    assert llm.ask_json(SYSTEM, MSGS, max_tokens=900) == ({"ok": 1}, None)
    assert slept == []


def test_a_refused_request_does_not_count_against_the_minute(monkeypatch, waits):
    use(monkeypatch, FakeClient([status_error(groq.RateLimitError, 429, retry_after=1), _used(100)]))
    assert llm.ask_json(SYSTEM, MSGS) == ({"ok": 1}, None)
    assert [t for _, t in llm._window] == [0, 100]


def test_a_reply_cut_off_can_be_salvaged_without_asking_again(monkeypatch, waits):
    client = use(monkeypatch, FakeClient([_json_reply('{"questions": [{"a": 1}, {"a": 2}, {"a"')]))
    data, error = llm.ask_json(SYSTEM, MSGS, salvage=lambda text: {"questions": [{"a": 1}, {"a": 2}]})
    assert (data, error) == ({"questions": [{"a": 1}, {"a": 2}]}, None)
    assert len(client.calls) == 1
