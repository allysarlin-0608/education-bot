"""Each person's daily allowance of AI calls (public mode only).

Every call to the model (a lesson, a quiz, its marking, a chat reply, a
placement check) is counted in ai_usage: one request and its tokens, by
the signed-in person and today's date. Past AI_DAILY_REQUEST_LIMIT
requests or AI_DAILY_TOKEN_LIMIT tokens in a day (secrets; 80 and 150000
by default) no more calls are made that day. Admins have no limit. A
personal app neither counts nor limits, as before."""
import logging

import streamlit as st

from coach import auth, storage, ui

LIMIT_REACHED = "You've reached today's limit. Your progress is saved. See you tomorrow."
DEFAULT_REQUESTS, DEFAULT_TOKENS = 80, 150_000

logger = logging.getLogger("coach.quota")


def _limit(name: str, default: int) -> int:
    try:
        return int(ui.get_setting(name) or default)
    except ValueError:
        return default


def limits() -> tuple:
    return _limit("AI_DAILY_REQUEST_LIMIT", DEFAULT_REQUESTS), _limit("AI_DAILY_TOKEN_LIMIT", DEFAULT_TOKENS)


def _store():
    return st.session_state.get("coach_store")


def counted() -> bool:
    return auth.is_public() and _store() is not None and auth.get_current_user_id() is not None


def over_limit() -> bool:
    """True when this person has used up today's allowance (never for admins)."""
    if not counted() or auth.is_admin():
        return False
    try:
        used = _store().usage_today(ui.today().isoformat())
    except storage.StorageError as e:          # can't tell: let the call through, and say so in the log
        logger.error("couldn't read today's AI usage: %s", e)
        return False
    max_requests, max_tokens = limits()
    return used["request_count"] >= max_requests or used["token_count"] >= max_tokens


def record(tokens_used: int) -> None:
    """Count one call and its tokens (admins are counted too, just not limited)."""
    if not counted():
        return
    try:
        _store().add_usage(ui.today().isoformat(), 1, max(int(tokens_used), 0))
    except storage.StorageError as e:
        logger.error("couldn't record AI usage: %s", e)
