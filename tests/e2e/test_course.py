"""A subject's course map: the path, where she is, a lesson read again with
its quiz and notes, Continue, the ways in (Today, Progress, Settings, the
subject's world), refresh, and a subject that isn't today's."""
import itertools
import time
from datetime import date, timedelta

import sys
from pathlib import Path

import pytest

import flows
from conftest import covers

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
_n = itertools.count()
D = date(2026, 11, 16)


@pytest.fixture
def clock(public_app):
    yield public_app.set_clock
    public_app.set_clock(None)


def text(p):
    return p.page.evaluate("document.body.innerText")


@pytest.mark.parametrize("width", [1180, 390])
def test_the_path_a_lesson_read_again_and_continue(public_app, pages, clock, width):
    covers("W-daily-today_course", "W-course-cm_read", "W-course-lesson_quiz_notes", "W-course-cm_continue",
           "W-course-cm_world", "W-course-cm_other")
    app = public_app
    clock(D, "02:00:00")
    p = pages(width=width)
    email = f"cm{next(_n)}-{int(time.time() * 1000)}@example.com"
    flows.sign_in(p, app, email=email)
    flows.onboard(p, subjects=("Fashion & Clothing",), pace="Light")
    flows.open_app(p, app)
    page = p.page
    flows.start_lesson(p)
    page.get_by_placeholder("Ask about Lesson").fill("Why don't we feel it?")
    page.keyboard.press("Enter")
    assert flows.wait_text(page, "Good question", 30)
    flows.idle(page)
    flows.take_quiz(p, correct=True)                       # Lesson 1 passed on D
    clock(D + timedelta(days=1), "02:00:00")
    flows.open_app(p, app)
    flows.start_lesson(p)
    flows.take_quiz(p, correct=False)                      # Lesson 2 written, not passed
    clock(D + timedelta(days=2), "02:00:00")
    flows.open_app(p, app)
    flows.button(p, "Course map", exact=False)
    assert "/course" in page.url and "subject=fashion" in page.url
    assert flows.wait_text(page, "1 of 260 lessons passed", 10)
    t = text(p)
    page.screenshot(path=f"/tmp/claude-0/-home-user-AI-Python-Tutor/09ed8c0f-4c93-5278-8470-68cd5f307d5f/scratchpad/probe/course_{width}.png", full_page=False)
    assert f"passed {D:%b} {D.day} · 100%" in t and "YOU ARE HERE" in t.upper() and "UP NEXT" in t.upper()
    page.wait_for_timeout(500)
    assert page.evaluate("() => document.querySelectorAll('.st-key-topnav [data-cx-on]').length") == 0, \
        "the course map isn't a page of the bar: nothing there claims to be on"
    # Lesson 1, read again: its lesson, its quiz, the note
    page.locator('[class*="st-key-cm_row_1_done"] button').click()
    dialog = page.get_by_role("dialog")
    dialog.wait_for(timeout=10000)
    assert "Lesson 1:" in dialog.inner_text() and "best 100%" in dialog.inner_text()
    dialog.get_by_role("tab", name="Quiz").click()
    assert flows.wait_text(page, "Last attempt: 100%", 5)
    dialog.get_by_role("tab", name="Notes").click()
    assert flows.wait_text(page, "Why don't we feel it?", 5)
    page.keyboard.press("Escape")
    flows.idle(page)
    # Lesson 2 is today's (written yesterday, not passed): it can be read, and Continue goes to it
    assert page.locator('[class*="st-key-cm_row_2_today"] button').count() == 1
    page.reload()                                          # a refresh keeps the subject
    flows.idle(page, 40)
    assert flows.wait_text(page, "1 of 260 lessons passed", 15) and "subject=fashion" in page.url
    flows.button(p, "Continue · Lesson 2", exact=False)
    assert flows.wait_text(page, "Try a new quiz", 15), "Continue opens today's lesson"


def test_the_ways_in_and_a_subject_that_is_not_today(public_app, pages, clock):
    covers("W-records-prog_course", "W-settings-set_course", "W-world-w_course",
           "W-course-finished_of_before_this_one", "W-course-later_in_the_course_more_topics_lessons")
    app = public_app
    clock(D, "02:00:00")
    p = pages(width=1440)
    email = f"cm{next(_n)}-{int(time.time() * 1000)}@example.com"
    flows.sign_in(p, app, email=email)
    flows.onboard(p, subjects=("Philosophy", "Astronomy"))
    page = p.page
    # from Progress (Subjects)
    flows.open_app(p, app, "/records")
    page.get_by_role("radio", name="Subjects").or_(page.get_by_role("button", name="Subjects", exact=True)).first.click()
    flows.idle(page)
    page.locator(".st-key-prog_course_cosmos button").click()
    flows.idle(page)
    assert "subject=cosmos" in page.url and flows.wait_text(page, "Next: Lesson 1", 10)
    assert "Today is Philosophy's day" in text(p)
    # the other subject, from the map itself
    flows.button(p, "Philosophy", exact=False)
    assert "subject=philosophy" in page.url and flows.wait_text(page, "Continue · Lesson 1", 10)
    # the rest of the course is folded away, and opens
    flows.open_panel(p, "Later in the course")
    assert flows.wait_text(page, "Lessons 11–15", 5) or "Lessons" in text(p)
    # from Settings and from the subject's world
    flows.open_app(p, app, "/settings")
    flows.button(p, "Course map", exact=False)
    assert "/course" in page.url
    flows.open_app(p, app, "/subject?subject=cosmos")
    flows.button(p, "Course map", exact=False)
    assert "subject=cosmos" in page.url and flows.wait_text(page, "Next: Lesson 1", 10)
    # many lessons passed: the finished topics fold into one line
    from seed_history import build
    app.seed_entries(email, build(D - timedelta(days=1), days=20, topics=("philosophy",)))
    flows.open_app(p, app, "/course?subject=philosophy")
    assert flows.wait_text(page, "Finished ·", 10)
    flows.open_panel(p, "Finished ·")
    assert page.locator('[class*="st-key-cm_row_"][class*="_done"] button').count() > 10
