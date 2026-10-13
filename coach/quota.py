"""Each person's daily allowance of AI calls (public mode only).

Every call to the model (a lesson, a quiz, its marking, a chat reply, a
placement check) is counted in ai_usage: one request and its tokens, by
the signed-in person and today's date. Past AI_DAILY_REQUEST_LIMIT
requests or AI_DAILY_TOKEN_LIMIT tokens in a day (secrets; 80 and 150000
by default) no more calls are made that day, and none while the allowance
can't be read. Admins have no limit. A personal app neither counts nor
limits, as before."""
import logging

import streamlit as st

from coach import appconfig, auth, clock, storage

LIMIT_REACHED = "You've reached today's limit. Your progress is saved. See you tomorrow."
DEFAULT_REQUESTS, DEFAULT_TOKENS = 80, 150_000

logger = logging.getLogger("coach.quota")


def _limit(name: str, default: int) -> int:
    try:
        return int(appconfig.get_setting(name) or default)
    except ValueError:
        return default


def limits() -> tuple:
    return _limit("AI_DAILY_REQUEST_LIMIT", DEFAULT_REQUESTS), _limit("AI_DAILY_TOKEN_LIMIT", DEFAULT_TOKENS)


def _store():
    return st.session_state.get("coach_store")


def counted() -> bool:
    return auth.is_public() and _store() is not None and auth.get_current_user_id() is not None


UNCHECKED = "Your daily allowance couldn't be checked just now. Your progress is saved; try again in a moment."


def blocked():
    """Why no AI call can be made for this person now, or None. Past today's
    allowance; or the allowance can't be read (the database didn't answer):
    then no call is made either, so the limit always holds (it once let the
    call through, leaving the cost unguarded). Never for admins."""
    if not counted() or auth.is_admin():
        return None
    try:
        used = _store().usage_today(clock.today().isoformat())
    except storage.StorageError as e:
        logger.error("couldn't read today's AI usage, no call made: %s", e)
        return UNCHECKED
    max_requests, max_tokens = limits()
    if used["request_count"] >= max_requests or used["token_count"] >= max_tokens:
        return LIMIT_REACHED
    return None


def over_limit() -> bool:
    """True when no AI call may be made for this person now (blocked())."""
    return blocked() is not None


def record(tokens_used: int) -> None:
    """Count one call and its tokens (admins are counted too, just not limited)."""
    if not counted():
        return
    try:
        _store().add_usage(clock.today().isoformat(), 1, max(int(tokens_used), 0))
    except storage.StorageError as e:
        logger.error("couldn't record AI usage: %s", e)


def note_wait(kind: str) -> None:
    """Count one AI call that was busy, failed or slow (coach/metrics.wait_kind)
    for this person today, so admins see how often the AI made people wait
    (supabase/ai_health.sql). Counting never gets in her way: a failure (the
    table not there yet, the database not answering) is logged, not shown."""
    if not counted():
        return
    try:
        _store().add_ai_wait(kind)
    except (storage.StorageError, AttributeError) as e:
        logger.warning("couldn't count an AI %s (%s)", kind, e)
