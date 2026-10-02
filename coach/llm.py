"""Groq calls shared by the lesson page and the book tracker.

Every request is fitted to tokens.REQUEST_BUDGET before it is sent, rate
limits are retried with backoff, and failures reach the user only as a
short friendly sentence; the details go to the log (Streamlit Cloud:
Manage app → logs)."""
import collections
import json
import logging
import os
import random
import re
import threading
import time

import streamlit as st

from coach import tokens

try:
    import groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

MODEL_NAME = "openai/gpt-oss-120b"
MAX_RETRIES = 3            # after the first attempt, on 429 / connection errors
MAX_WAIT_SECONDS = 15.0    # cap on a single backoff wait
REQUEST_TIMEOUT = 20.0     # one request (for a stream: the wait for each next piece)
TOTAL_SECONDS = 28.0       # all attempts and waits together: the person hears back within 30 s

NO_KEY = "No Groq API key yet. Add one in the sidebar first."
BUSY = "The coach is busy right now. Wait a few seconds and try again."
FAILED = "The coach didn't manage to reply this time. Just try again."
LIMIT = "You've reached today's limit. Your progress is saved. See you tomorrow."   # quota.LIMIT_REACHED

logger = logging.getLogger("coach.llm")


def _sleep(seconds):
    time.sleep(seconds)


def _now():
    return time.monotonic()


class CoachError(Exception):
    """A failed model call. str(e) is safe to show the user."""


def get_client():
    key = st.session_state.get("api_key", "")
    if not key or not GROQ_AVAILABLE:
        return None
    return groq.Groq(api_key=key, max_retries=0, timeout=REQUEST_TIMEOUT)   # retries are handled here


def _status(error):
    return getattr(error, "status_code", None) or getattr(getattr(error, "response", None), "status_code", None)


def _retryable(error) -> bool:
    if GROQ_AVAILABLE and isinstance(error, (groq.APIConnectionError, groq.APITimeoutError)):
        return True
    return _status(error) in (429, 500, 502, 503)


def _wait_seconds(error, attempt: int) -> float:
    """Groq's retry-after header (or "try again in 7.5s" in the message),
    else exponential backoff: ~2s, ~4s."""
    headers = getattr(getattr(error, "response", None), "headers", None) or {}
    value = headers.get("retry-after")
    if value is None:
        match = re.search(r"try again in ([\d.]+)s", str(error))
        value = match.group(1) if match else None
    try:
        wait = float(value) if value is not None else 2 ** (attempt + 1)
    except ValueError:
        wait = 2 ** (attempt + 1)
    return min(wait + random.uniform(0, 0.5), MAX_WAIT_SECONDS)


# Groq's free tier allows tokens.MINUTE_LIMIT tokens per minute for the
# whole key, and refuses (429) a request that would go over. Every request
# this server sends is noted here (its estimate, then its real use once
# known), and a request that wouldn't fit waits for the oldest to age out
# of the minute instead of being refused. Shared by every session.
_window = collections.deque()          # [sent_at, tokens], oldest first
_window_lock = threading.Lock()


def _minute_limit() -> int:
    try:
        return int(os.environ.get("GROQ_TPM_LIMIT", tokens.MINUTE_LIMIT))
    except ValueError:
        return tokens.MINUTE_LIMIT


def _reserve(requested: int, deadline: float) -> list:
    """Wait (within the deadline, at most MAX_WAIT_SECONDS) until this
    request fits in the minute's allowance, then note it. Returns its record."""
    limit = _minute_limit()
    while True:
        with _window_lock:
            now = _now()
            while _window and _window[0][0] <= now - 60:
                _window.popleft()
            used, wait = sum(t for _, t in _window), 0.0
            if used + requested > limit:
                freed = used
                for sent, t in _window:            # until enough has aged out
                    freed -= t
                    wait = sent + 60 - now
                    if freed + requested <= limit:
                        break
            if wait <= 0 or wait > MAX_WAIT_SECONDS or now + wait + REQUEST_TIMEOUT / 4 >= deadline:
                if wait > 0:
                    logger.info("minute allowance: %d used + %d requested > %d; sending anyway", used, requested, limit)
                record = [now, requested]
                _window.append(record)
                return record
        logger.info("minute allowance: %d used + %d requested > %d; waiting %.1fs", used, requested, limit, wait)
        _sleep(wait + 0.2)


def _create(client, **kwargs):
    """client.chat.completions.create with retries. Raises CoachError.
    Every call made is counted against the person's daily allowance
    (quota.py): the request now, and its tokens (the reply's usage, or the
    request's estimate while a streamed reply is still coming)."""
    from coach import quota
    deadline = _now() + TOTAL_SECONDS
    requested = tokens.calibrated(tokens.estimate_request("", kwargs.get("messages", []), 0)) \
        + kwargs.get("max_completion_tokens", 0)
    for attempt in range(MAX_RETRIES + 1):
        record = _reserve(requested, deadline)
        try:
            resp = client.chat.completions.create(**kwargs)
            usage = getattr(resp, "usage", None)
            used = getattr(usage, "total_tokens", None)
            if isinstance(used, int):
                record[1] = used          # what the minute really counts once the reply is in
            quota.record(used or tokens.estimate_request("", kwargs.get("messages", []), kwargs.get("max_completion_tokens", 0)))
            return resp
        except Exception as e:   # noqa: BLE001 - every failure is mapped below
            if _status(e) in (400, 413, 429):
                record[1] = 0             # refused outright: nothing was used
            status = _status(e)
            wait = _wait_seconds(e, attempt) if _retryable(e) else 0
            if _retryable(e) and attempt < MAX_RETRIES and _now() + wait + REQUEST_TIMEOUT / 4 < deadline:
                logger.warning("groq %s on attempt %d, retrying in %.1fs: %s",
                               status or type(e).__name__, attempt + 1, wait, e)
                _sleep(wait)
                continue
            logger.error("groq call failed (status %s): %s", status, e)
            raise CoachError(BUSY if status == 429 or _retryable(e) else FAILED) from e


def _prepare(system, messages, max_tokens):
    fitted, dropped = tokens.fit_messages(system, messages, max_tokens)
    estimate = tokens.estimate_request(system, fitted, max_tokens)
    if dropped:
        logger.info("dropped %d oldest messages to fit the token budget", dropped)
    logger.info("request estimate %d tokens (budget %d)", estimate, tokens.REQUEST_BUDGET)
    return [{"role": "system", "content": system}] + [
        {"role": m["role"], "content": m["content"]} for m in fitted
    ]


def stream_text(system, messages, max_tokens):
    """Generator of reply text. Raises CoachError on any failure,
    including an empty reply."""
    from coach import quota
    if quota.over_limit():
        raise CoachError(LIMIT)
    client = get_client()
    if client is None:
        raise CoachError(NO_KEY)
    stream = _create(
        client,
        model=MODEL_NAME,
        messages=_prepare(system, messages, max_tokens),
        max_completion_tokens=max_tokens,
        reasoning_effort="low",
        stream=True,
    )
    produced = False
    finish = None
    try:
        for chunk in stream:
            choice = chunk.choices[0]
            finish = choice.finish_reason or finish
            if choice.delta.content:
                produced = True
                yield choice.delta.content
    except Exception as e:   # noqa: BLE001
        logger.error("groq stream broke off: %s", e)
        raise CoachError(FAILED) from e
    if not produced:
        logger.error("groq returned no text (finish_reason=%s)", finish)
        raise CoachError(FAILED)


def stream_reply(system, messages, max_tokens=tokens.CHAT_MAX_TOKENS):
    """Stream a reply into an assistant bubble. Returns (text, None) or
    (None, friendly_error)."""
    with st.chat_message("assistant"):
        try:
            return st.write_stream(stream_text(system, messages, max_tokens)), None
        except CoachError as e:
            return None, str(e)


def parse_json(text: str):
    """The first JSON object in a model reply, or None."""
    if not text:
        return None
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group())
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def ask_json(system, messages, max_tokens=tokens.JSON_MAX_TOKENS, salvage=None):
    """Ask for a JSON object (non-streaming). Returns (data, None) or
    (None, friendly_error). salvage(text) may make something usable of a
    reply that can't be read whole (e.g. one cut off at max_tokens: the
    quiz keeps its complete questions) instead of asking again."""
    from coach import quota
    if quota.over_limit():
        return None, LIMIT
    client = get_client()
    if client is None:
        return None, NO_KEY
    prepared = _prepare(system, messages, max_tokens)
    for attempt in range(2):          # an unreadable reply is asked for once more
        started = _now()
        try:
            resp = _create(
                client,
                model=MODEL_NAME,
                messages=prepared,
                max_completion_tokens=max_tokens,
                reasoning_effort="low",
                response_format={"type": "json_object"},
            )
        except CoachError as e:
            return None, str(e)
        data = parse_json(resp.choices[0].message.content)
        how = "read" if data is not None else "UNREADABLE"
        if data is None and salvage is not None:
            data = salvage(resp.choices[0].message.content)
            how = "SALVAGED" if data is not None else how
        usage = getattr(resp, "usage", None)
        logger.info("json call %s in %.1fs: prompt %s + reply %s tokens, finish_reason=%s",
                    how, _now() - started,
                    getattr(usage, "prompt_tokens", "?"), getattr(usage, "completion_tokens", "?"),
                    resp.choices[0].finish_reason)
        if data is not None:
            return data, None
        logger.error("groq returned unparseable JSON (attempt %d, finish_reason=%s): %.300r",
                     attempt + 1, resp.choices[0].finish_reason, resp.choices[0].message.content)
    return None, FAILED
