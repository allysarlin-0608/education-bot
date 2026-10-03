"""Progress with a real history (35 days, gaps, partial days, one legacy
session): every figure checked against the app's own definitions, the
calendar, the day, every session, the subjects, and the reader."""
import itertools
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

import flows
from conftest import covers

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import seed_history  # noqa: E402

_n = itertools.count()


def today():
    return datetime.now(ZoneInfo("Asia/Taipei")).date()


def legacy_entry(day):
    """A session from before the syllabus: one lesson, no lessons list."""
    return {"date": day.isoformat(), "topic": "philosophy", "session_number": 1, "level": "Beginner",
            "completed": True, "title": "An old session", "followup_question": "Old question?",
            "reflection": "", "lesson": seed_history.LESSON, "followups": [], "kickoff": "", "lessons": []}


def with_history(app, pages, width=1440, legacy=False):
    p = pages(width=width)
    email = f"prog{next(_n)}-{int(time.time() * 1000)}@example.com"
    flows.sign_in(p, app, email=email)
    flows.onboard(p)
    entries = seed_history.build(today(), days=35)
    if legacy:
        entries = [legacy_entry(today() - timedelta(days=60))] + entries
    app.seed_entries(email, entries)
    flows.open_app(p, app, "/records")
    return p, email, entries


def text(p):
    return p.page.evaluate("document.body.innerText")


def days(n):
    return f"{n} {'day' if n == 1 else 'days'}"


@pytest.mark.parametrize("mode", ["public", "personal"])
def test_the_figures_match_the_records(mode, pages, request):
    covers("W-records-prog_view")
    app = request.getfixturevalue(f"{mode}_app")
    if mode == "personal":
        for f in ("learning_log.json", "user_settings.json"):
            (app.state / f).unlink(missing_ok=True)
    p, _, entries = with_history(app, pages)
    exp = seed_history.expected(entries, today())
    figures = p.page.evaluate("""() => Object.fromEntries([...document.querySelectorAll('.figure')].map(f =>
        [f.querySelector('.figure-label').innerText.trim(), f.querySelector('.figure-value').innerText.replace(/\\s+/g, ' ').trim()]))""")
    assert figures["Current streak"] == days(exp["current_streak"]), figures
    assert figures["Longest streak"] == days(exp["longest_streak"]), figures
    assert figures["Days completed"] == days(exp["days_completed"]), figures
    assert figures["Days studied"] == days(exp["days_studied"]), figures
    assert figures["Lessons passed"] == f"{exp['lessons_passed']:,}", figures


def test_calendar_moves_and_picks_a_day(public_app, pages):
    covers("W-records-cal_prev", "W-records-cal_today", "W-records-cal_next", "W-records-name", "W-records-read",
           "W-lesson_view-title_for_title_in_parts")
    app = public_app
    p, _, entries = with_history(app, pages)
    t0 = today()
    month = t0.strftime("%B")
    assert f"{month} {t0.year}" in text(p)
    flows.button(p, "‹")
    prev = (t0.replace(day=1) - timedelta(days=1))
    assert flows.wait_text(p.page, f"{prev:%B} {prev.year}", 5)
    flows.button(p, "›")
    flows.button(p, "›")
    nxt = (t0.replace(day=28) + timedelta(days=5))
    assert flows.wait_text(p.page, f"{nxt:%B} {nxt.year}", 5)
    flows.button(p, "Today")
    assert flows.wait_text(p.page, f"{month} {t0.year}", 5)
    # pick a complete day in view
    done = next(e for e in reversed(entries) if e["completed"] and e["date"][:7] == t0.isoformat()[:7])
    d = datetime.fromisoformat(done["date"]).date()
    flows.tap(p, p.page.locator(f'[class*="st-key-cal_{done["date"]}_"] button').first)
    flows.idle(p.page)
    assert flows.wait_text(p.page, f"{d:%B} {d.day}", 5) and "Completed" in text(p)
    t = text(p)
    day_part = t[t.index(f"{d:%B} {d.day}"):]
    missing = [(s["title"], s["quiz"]["best"]) for s in done["lessons"]
               if s["title"] not in day_part or f"{s['quiz']['best']}%" not in day_part]
    assert not missing, (missing, day_part[:800])
    # read a lesson, one section at a time
    flows.tap(p, p.page.locator('[data-testid="stButtonGroup"] button', has_text=f"Lesson {done['lessons'][0]['n']}").first)
    flows.idle(p.page)
    tab = p.page.get_by_role("tab", name="Key Idea")
    flows.tap(p, tab)
    assert flows.wait_text(p.page, "Seeded key idea.", 5)
    # a day with nothing recorded
    gap = t0 - timedelta(days=3)
    if gap.month == t0.month:
        flows.tap(p, p.page.locator(f'[class*="st-key-cal_{gap.isoformat()}_"] button').first)
        flows.idle(p.page)
        assert flows.wait_text(p.page, "Nothing recorded", 5)


def test_sessions_list_filter_more_and_calendar_link(public_app, pages):
    covers("W-records-sessions_topic", "W-records-x", "W-records-oncal", "W-records-sessions_more")
    app = public_app
    p, _, entries = with_history(app, pages)
    p.page.get_by_role("radio", name="Sessions").or_(p.page.get_by_role("button", name="Sessions", exact=True)).first.click()
    flows.idle(p.page)
    assert flows.wait_text(p.page, f"{len(entries)} sessions", 5)
    expanders = p.page.locator('[data-testid="stExpander"] summary')
    first_page = expanders.count()
    flows.button(p, f"Show 10 more of {len(entries) - 10}")
    assert expanders.count() > first_page
    # the newest session, on the calendar
    newest = entries[-1]
    expanders.first.click()
    flows.idle(p.page)
    flows.button(p, "Show on the calendar", exact=False)
    d = datetime.fromisoformat(newest["date"]).date()
    assert flows.wait_text(p.page, f"{d:%B} {d.day}", 5)
    # filter by subject
    p.page.get_by_role("radio", name="Sessions").or_(p.page.get_by_role("button", name="Sessions", exact=True)).first.click()
    flows.idle(p.page)
    flows.choose(p, p.page.locator('.st-key-sessions_head [data-testid="stSelectbox"]'), "Philosophy")
    assert flows.wait_text(p.page, f"{len(entries)} sessions", 5)


def test_subjects_view_and_its_world(public_app, pages):
    covers("W-records-prog_world")
    app = public_app
    p, _, entries = with_history(app, pages)
    p.page.get_by_role("radio", name="Subjects").or_(p.page.get_by_role("button", name="Subjects", exact=True)).first.click()
    flows.idle(p.page)
    from coach import curriculum
    prog = curriculum.progress({"entries": entries, "books": []}, "philosophy")
    assert flows.wait_text(p.page, f"{prog['done']:,} of {prog['written']:,} written so far", 5), "the subject's count"
    flows.button(p, "Enter Philosophy", exact=False)
    assert "subject=philosophy" in p.page.url


def test_a_legacy_session_keeps_its_thoughts(public_app, pages):
    covers("W-records-rec_reflection", "W-records-rec_save", "W-records-rec_lesson", "D-records-save_entry")
    app = public_app
    p, email, _ = with_history(app, pages, legacy=True)
    p.page.get_by_role("radio", name="Sessions").or_(p.page.get_by_role("button", name="Sessions", exact=True)).first.click()
    flows.idle(p.page)
    while p.page.get_by_role("button", name="Show", exact=False).filter(has_text="more of").count():
        flows.tap(p, p.page.get_by_role("button", name="Show", exact=False).filter(has_text="more of").first)
        flows.idle(p.page)
    p.page.locator('[data-testid="stExpander"] summary', has_text="An old session").click()
    flows.idle(p.page)
    box = p.page.get_by_label("My thoughts").last
    box.fill("It still makes sense.")
    p.page.keyboard.press("Tab")
    flows.button(p, "Save my thoughts")
    assert flows.wait_text(p.page, "Saved.", 5)
    d = app.get("/__dump")
    uid = next(u["id"] for u in d["users"] if u["email"] == email)
    old = next(e for e in d["tables"]["learning_entries"] if e["user_id"] == uid and e["title"] == "An old session")
    assert old["reflection"] == "It still makes sense."
    p.page.get_by_text("Read the lesson", exact=True).last.click()
    assert flows.wait_text(p.page, "Seeded key idea.", 5) or p.page.get_by_role("tab", name="Key Idea").count()


@pytest.mark.parametrize("width", [390, 768, 1024, 1180, 1920])
def test_progress_fits_every_width(public_app, pages, width):
    covers("W-records-prog_view")
    app = public_app
    p, _, _ = with_history(app, pages, width=width)
    assert p.page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), "horizontal scroll"
    for view in ("Sessions", "Subjects", "Day"):
        p.page.get_by_role("radio", name=view).or_(p.page.get_by_role("button", name=view, exact=True)).first.click()
        flows.idle(p.page)
        assert p.page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), f"horizontal scroll on {view}"
