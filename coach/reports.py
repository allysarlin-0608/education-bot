"""Reports of a problem in a lesson or a quiz question (audit stage 2): what
a learner sends, and the numbers an admin sees. The same rules as
supabase/reports.sql (add_content_report, content_reports_summary), for the
local store and the tests. Pure functions, no Streamlit."""
from datetime import date

REASONS = {"wrong": "Something is wrong", "unclear": "It's unclear",
           "not_taught": "The lesson didn't teach this", "other": "Something else"}
LESSON_REASONS = ("wrong", "unclear", "other")
QUESTION_REASONS = ("wrong", "unclear", "not_taught", "other")
KINDS = ("lesson", "question")
PER_DAY = 30                  # reports one person can send a day
RECENT = 20


def make(topic: str, n: int, title: str, kind: str, reason: str, excerpt: str = "", note: str = ""):
    """A report as stored (the store adds who and when), or None if it isn't one."""
    if kind not in KINDS or reason not in REASONS or not topic or not isinstance(n, int) or not 1 <= n <= 1000:
        return None
    return {"topic": str(topic)[:40], "lesson_no": n, "lesson_title": str(title or "")[:200], "kind": kind,
            "reason": reason, "excerpt": str(excerpt or "")[:600], "note": str(note or "").strip()[:500]}


def summarize(rows: list, since: date, lessons_passed: int) -> dict:
    """What content_reports_summary gives: how many since a day, by reason, how
    many lessons were passed then (for a rate), and the latest few (never who)."""
    mine = [r for r in rows if str(r.get("at", ""))[:10] >= since.isoformat()]
    by_reason = {}
    for r in mine:
        by_reason[r["reason"]] = by_reason.get(r["reason"], 0) + 1
    recent = sorted(mine, key=lambda r: r["at"], reverse=True)[:RECENT]
    return {"reports": len(mine), "by_reason": by_reason, "lessons_passed": lessons_passed,
            "recent": [{k: v for k, v in r.items() if k != "user_id"} for r in recent]}


def per_hundred(summary: dict):
    """Reports per 100 lessons passed (None before any lesson is passed)."""
    passed = summary.get("lessons_passed") or 0
    return round(100 * summary.get("reports", 0) / passed, 1) if passed else None
