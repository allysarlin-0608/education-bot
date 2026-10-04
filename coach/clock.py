"""The one clock: the learner's date and the time records are stamped with.

Every "today" and "now" in GNOSIS comes from here, so the learner's
timezone is set in one place (COACH_TIMEZONE, Asia/Taipei by default: her
date, not the server's) and a test can move time for the whole app by
replacing today() and now_iso() (tests/e2e/harness/app_entry.py).

The usage numbers (coach/metrics.py, supabase/goals.sql) keep their own
fixed zone: they must agree with the database's."""
import os
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo


def _zone() -> ZoneInfo:
    return ZoneInfo(os.environ.get("COACH_TIMEZONE", "Asia/Taipei"))


TIMEZONE = _zone()


def today() -> date:
    """The learner's date now."""
    return datetime.now(TIMEZONE).date()


def now() -> datetime:
    """The learner's local time now (for her reminder time)."""
    return datetime.now(TIMEZONE)


def now_iso() -> str:
    """Now, as stored on records (UTC, ISO 8601)."""
    return datetime.now(timezone.utc).isoformat()
