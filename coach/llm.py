"""Groq calls shared by the lesson page and the book tracker.

Every request is fitted to tokens.REQUEST_BUDGET before it is sent, rate
limits are retried with backoff, and failures reach the user only as a
short friendly sentence; the details go to the log (Streamlit Cloud:
Manage app → logs)."""
import json
import logging
import random
import re
import time

import streamlit as st

from coach import tokens

try:
    import groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

MODEL_NAME = "openai/gpt-oss-120b"
MAX_RETRIES = 3            # after the first attempt, on 429 / connection errors (up to ~45s)
MAX_WAIT_SECONDS = 15.0    # cap on a single backoff wait

NO_KEY = "No Groq API key yet. Add one in the sidebar first."
BUSY = "The coach is busy right now. Wait a few seconds and try again."
FAILED = "The coach didn't manage to reply this time. Just try again."

logger = logging.getLogger("coach.llm")


def _sleep(seconds):
    time.sleep(seconds)


class CoachError(Exception):
    """A failed model call. str(e) is safe to show the user."""


def get_client():
    key = st.session_state.get("api_key", "")
    if not key or not GROQ_AVAILABLE:
        return None
    return groq.Groq(api_key=key, max_retries=0)   # retries are handled here


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


def _create(client, **kwargs):
    """client.chat.completions.create with retries. Raises CoachError."""
    for attempt in range(MAX_RETRIES + 1):
        try:
            return client.chat.completions.create(**kwargs)
        except Exception as e:   # noqa: BLE001 - every failure is mapped below
            status = _status(e)
            if _retryable(e) and attempt < MAX_RETRIES:
                wait = _wait_seconds(e, attempt)
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


def ask_json(system, messages, max_tokens=tokens.JSON_MAX_TOKENS):
    """Ask for a JSON object (non-streaming). Returns (data, None) or
    (None, friendly_error)."""
    client = get_client()
    if client is None:
        return None, NO_KEY
    try:
        resp = _create(
            client,
            model=MODEL_NAME,
            messages=_prepare(system, messages, max_tokens),
            max_completion_tokens=max_tokens,
            reasoning_effort="low",
            response_format={"type": "json_object"},
        )
    except CoachError as e:
        return None, str(e)
    data = parse_json(resp.choices[0].message.content)
    if data is None:
        logger.error("groq returned unparseable JSON (finish_reason=%s): %.300r",
                     resp.choices[0].finish_reason, resp.choices[0].message.content)
        return None, FAILED
    return data, None
