"""Reading: a book set up by talking with the coach (pasted contents or one
chapter at a time), the 14-day plan (adjusted by hand or by asking),
confirming it, the daily check on a clock that moves day by day, the
wrap-up at the end, errors with Retry, More options, and books of odd
sizes (1, 14, 15, 200 chapters; 1 and 5,000 pages)."""
import itertools
import json
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

import flows
from conftest import covers

_n = itertools.count()
SHARE = "Today I read about how the author grew up and why the first chapter matters to the story."


@pytest.fixture
def clock(public_app):
    yield public_app.set_clock
    public_app.set_clock(None)


def today():
    return datetime.now(ZoneInfo("Asia/Taipei")).date()


def reader(app, pages, width=1440):
    p = pages(width=width)
    p.email = f"read{next(_n)}-{int(time.time() * 1000)}@example.com"
    flows.sign_in(p, app, email=p.email)
    flows.onboard(p, reading=True)
    app.set_llm()
    flows.open_app(p, app, "/reading")
    return p


def text(p):
    return p.page.evaluate("document.body.innerText")


def say(p, message, expect=None, timeout=30):
    box = p.page.locator(".st-key-chat_dock textarea").first
    box.fill(message)
    box.press("Enter")
    flows.idle(p.page, timeout)
    if expect:
        assert flows.wait_text(p.page, expect, timeout), f"after {message[:40]!r}: no {expect!r}"


def books_of(app, email):
    d = app.get("/__dump")
    uid = next(u["id"] for u in d["users"] if u["email"] == email)
    return [r["data"] for r in d["tables"].get("reading_books", []) if r["user_id"] == uid], \
        [e for e in d["tables"]["learning_entries"] if e["user_id"] == uid]


def _words(k):
    """A chapter title without digits (a trailing number reads as a page number)."""
    ones = "zero one two three four five six seven eight nine".split()
    return "-".join(ones[int(c)] for c in str(k))


def set_up(p, title="The Test Book", author="A. Writer", chapters=5, pages_=200, paste=True, start=True):
    if start:
        flows.button(p, "Start a new book")
    assert flows.wait_text(p.page, "Which book would you like to start?")
    say(p, title, "Who's the author?")
    say(p, author, "How many chapters")
    say(p, str(chapters), "how many pages")
    say(p, str(pages_), "chapter titles")
    names = [f"Chapter {k}: Part {_words(k)}" for k in range(1, chapters + 1)]
    if chapters == 1:
        say(p, "Chapter 1: The only part", "14-day preview")
    elif paste:
        say(p, "\n".join(names), expect=None)
        say(p, "yes", "14-day preview")
    else:
        for k, line in enumerate(names):
            say(p, line, "14-day preview" if k == chapters - 1 else f"Chapter {k + 2}")


def test_set_up_adjust_confirm_and_read_day_one(public_app, pages):
    covers("W-reading-placeholder_book", "W-reading-start_book", "W-reading-adjust_a_day_yourself", "W-reading-adjust_open",
           "W-reading-adjust_day", "W-reading-lighter_move_its_last_chapter_to_day",
           "W-reading-heavier_bring_over_day_s_first_chapter", "W-reading-confirm_the_plan", "W-reading-14_day_plan",
           "W-reading-i_ve_finished_today_s_reading", "AI-reading-ask_json", "D-reading-save_book",
           "D-reading-save_entry", "D-ui-save_book")
    app = public_app
    p = reader(app, pages)
    set_up(p, chapters=20, pages_=400)
    assert books_of(app, p.email)[0] == [], "a draft isn't saved before it's confirmed"
    p.page.get_by_text("Adjust a day yourself").click()
    flows.idle(p.page)
    flows.button(p, "Lighter: move its last chapter to Day 2", exact=False)
    assert flows.wait_text(p.page, "I moved Day 1's last chapter to Day 2.")
    flows.button(p, "Heavier: bring over Day 2's first chapter", exact=False)
    assert flows.wait_text(p.page, "I moved Day 2's first chapter to Day 1.")
    flows.button(p, "Confirm the plan")
    assert flows.wait_text(p.page, "Your plan is set.")
    saved, _ = books_of(app, p.email)
    assert len(saved) == 1 and saved[0]["status"] == "reading" and saved[0]["started_on"] == today().isoformat()
    assert sum(len(d) for d in saved[0]["plan"]) == 20, "every chapter is on some day"
    p.page.get_by_text("14-day plan", exact=True).click()
    assert flows.wait_text(p.page, "Day 14")
    flows.button(p, "I've finished today's reading")
    assert "Tell me in your own words" in p.page.locator(".st-key-chat_dock textarea").get_attribute("placeholder")
    app.reset_calls()
    say(p, SHARE, "Day done")
    assert app.calls("reading_judge")
    saved, entries = books_of(app, p.email)
    assert "1" in saved[0]["checks"]
    reading = [e for e in entries if e["topic"] == "reading"]
    assert len(reading) == 1 and reading[0]["completed"] is True and SHARE in reading[0]["reflection"]
    # the next day hasn't opened yet
    say(p, "I finished reading", "opens on")


def test_a_too_short_share_is_asked_again_and_not_now(public_app, pages):
    covers("W-reading-cancel", "AI-reading-ask_json")
    app = public_app
    p = reader(app, pages)
    set_up(p, chapters=14, pages_=280)
    flows.button(p, "Confirm the plan")
    flows.button(p, "I've finished today's reading")
    say(p, "Good.", "Tell me a bit more")
    saved, _ = books_of(app, p.email)
    assert "1" not in saved[0]["checks"], "a failed check doesn't count"
    flows.button(p, "Not now, maybe later")
    assert flows.wait_text(p.page, "No problem. Tell me when you're ready.")


def test_plan_by_asking_the_coach_and_yes_confirms(public_app, pages):
    covers("AI-reading-ask_json-2")
    app = public_app
    p = reader(app, pages)
    set_up(p, chapters=15, pages_=300, paste=False)
    app.reset_calls()
    say(p, "Could you make day two a little lighter please", "Sounds good.")
    assert app.calls("reading_adjust")
    say(p, "looks good", "Your plan is set.")
    saved, _ = books_of(app, p.email)
    assert saved[0]["status"] == "reading"


def test_talking_about_the_book(public_app, pages):
    covers("AI-reading-stream_reply")
    app = public_app
    p = reader(app, pages)
    set_up(p, chapters=3, pages_=90)
    flows.button(p, "Confirm the plan")
    app.reset_calls()
    say(p, "Who is your favourite character so far and why?", "Thanks for sharing.")
    assert [c["kind"] for c in app.calls()] == ["reading_chat"]


def test_a_whole_book_over_fourteen_days_and_the_wrap_up(public_app, pages, clock):
    covers("AI-reading-stream_reply-2", "W-reading-i_ve_finished_today_s_reading")
    app = public_app
    start = today()
    clock(start)
    p = reader(app, pages)
    set_up(p, chapters=14, pages_=140)
    flows.button(p, "Confirm the plan")
    for day in range(1, 15):
        clock(start + timedelta(days=day - 1))
        flows.open_app(p, app, "/reading")
        flows.button(p, "I've finished today's reading")
        say(p, SHARE + f" (day {day})", None)
    assert flows.wait_text(p.page, "BOOKSHELF", 10)
    saved, entries = books_of(app, p.email)
    assert saved[0]["status"] == "finished" and saved[0]["final_summary"], "the wrap-up is saved"
    assert len(saved[0]["checks"]) == 14
    assert len([e for e in entries if e["topic"] == "reading" and e["completed"]]) == 14
    assert "The Test Book" in p.page.locator(".st-key-read_main").inner_text()
    assert flows.wait_text(p.page, "Start a new book")


def test_the_wrap_up_fails_then_retry(public_app, pages, clock):
    covers("W-reading-summary_retry")
    app = public_app
    clock(today())
    p = reader(app, pages)
    set_up(p, chapters=1, pages_=1)
    flows.button(p, "Confirm the plan")
    flows.button(p, "I've finished today's reading")
    app.set_llm(mode="500", fail_kinds=["reading_final"])
    say(p, SHARE, "busy", 40)
    saved, _ = books_of(app, p.email)
    assert saved[0]["status"] == "finished" and not saved[0].get("final_summary"), "the book is finished anyway"
    app.set_llm()
    flows.button(p, "Retry")
    flows.idle(p.page, 40)
    saved, _ = books_of(app, p.email)
    assert saved[0]["final_summary"], "Retry wrote the wrap-up"


def test_errors_show_retry(public_app, pages):
    covers("W-reading-book_retry")
    app = public_app
    p = reader(app, pages)
    set_up(p, chapters=3, pages_=90)
    flows.button(p, "Confirm the plan")
    flows.button(p, "I've finished today's reading")
    app.set_llm(mode="429")
    say(p, SHARE, "busy", 40)
    app.set_llm()
    flows.button(p, "Retry")
    assert flows.wait_text(p.page, "Day done", 30)


def test_more_options_rename_switch_and_restart(public_app, pages):
    covers("W-reading-more_options", "W-reading-edit_ch", "W-reading-edit_title", "W-reading-edit_save",
           "W-reading-switch", "W-reading-restart")
    app = public_app
    p = reader(app, pages)
    set_up(p, chapters=4, pages_=100)
    # restart the setup while still planning
    p.page.get_by_text("More options", exact=True).click()
    flows.button(p, "Start the setup over")
    assert flows.wait_text(p.page, "OK, let's start over.")
    set_up(p, title="Second Try", chapters=4, pages_=100, start=False)
    flows.button(p, "Confirm the plan")
    p.page.get_by_text("More options", exact=True).click()
    flows.idle(p.page)
    flows.choose(p, p.page.locator('[data-testid="stSelectbox"]').filter(has_text="Chapter").first,
                 "Chapter 2: Part two")
    box = p.page.get_by_label("New title")
    for _ in range(50):                        # the box for the chapter picked, once the page has redrawn
        if box.input_value() == "Part two":
            break
        p.page.wait_for_timeout(100)
    assert box.input_value() == "Part two", "picking Chapter 2 didn't show its title"
    box.fill("A better name")
    p.page.keyboard.press("Tab")
    flows.button(p, "Save title")
    assert flows.wait_text(p.page, 'Chapter 2 is now "A better name"')
    saved, _ = books_of(app, p.email)
    assert saved[0]["chapters"][1] == "A better name"
    p.page.get_by_text("More options", exact=True).click()
    flows.button(p, "Stop this book and start another")
    assert flows.wait_text(p.page, "OK, let's set up a new book.")
    saved, _ = books_of(app, p.email)
    assert saved[0]["status"] == "switched"
    assert "Second Try" in p.page.locator(".st-key-read_main").inner_text(), "the stopped book is on the shelf"


@pytest.mark.parametrize("chapters,pages_", [(1, 1), (14, 5000), (15, 300), (200, 5000)])
def test_books_of_every_size(public_app, pages, chapters, pages_):
    covers("W-reading-confirm_the_plan", "D-reading-save_book")
    app = public_app
    p = reader(app, pages)
    set_up(p, chapters=chapters, pages_=pages_)
    flows.button(p, "Confirm the plan")
    assert flows.wait_text(p.page, "Your plan is set.")
    saved, _ = books_of(app, p.email)
    plan = saved[0]["plan"]
    assert len(plan) == 14
    assert sorted(c for d in plan for c in d) == list(range(1, chapters + 1)), "each chapter exactly once, in order"
    assert all(a <= b for d in plan for a, b in zip(d, d[1:]))
    assert "Traceback" not in text(p)
    assert p.page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")


def test_a_messy_pasted_contents_page(public_app, pages):
    covers("W-reading-placeholder_book")
    app = public_app
    p = reader(app, pages)
    flows.button(p, "Start a new book")
    say(p, "《Messy Book》", "Who's the author?")
    say(p, "Someone", "How many chapters")
    say(p, "about 6 chapters", "how many pages")
    say(p, "roughly 240 pages", "chapter titles")
    toc = ("Contents\nPreface ..... iii\nChapter 1 Beginnings ..... 1\nChapter 2 The Middle ..... 23\n"
           "Chapter 3 Turning ..... 51\nChapter 4 Late ..... 77\nChapter 5 End ..... 99\nChapter 6 After ..... 120\n"
           "Index ..... 230")
    say(p, toc)
    t = text(p)
    assert "Beginnings" in t and "After" in t
    say(p, "yes", "14-day preview")
    assert "Preface" not in p.page.locator(".st-key-read_main").inner_text().split("14-day preview")[-1]


@pytest.mark.parametrize("width", [390, 768, 1024])
def test_reading_on_touch_widths(public_app, pages, width):
    covers("W-reading-i_ve_finished_today_s_reading")
    app = public_app
    p = reader(app, pages, width=width)
    set_up(p, chapters=5, pages_=100)
    flows.button(p, "Confirm the plan")
    flows.button(p, "I've finished today's reading")
    say(p, SHARE, "Day done")
    assert p.page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")


def test_leaving_while_the_coach_reads_loses_nothing(public_app, pages):
    covers("AI-reading-ask_json", "W-reading-book_retry")
    app = public_app
    p = reader(app, pages)
    set_up(p, chapters=3, pages_=90)
    flows.button(p, "Confirm the plan")
    flows.button(p, "I've finished today's reading")
    app.set_llm(delay=4.0)                        # the check takes a while
    box = p.page.locator(".st-key-chat_dock textarea").first
    box.fill(SHARE)
    box.press("Enter")
    p.page.wait_for_timeout(1500)
    flows.go(p, app, "Progress")                  # leave while it's being checked
    app.set_llm()
    p.page.wait_for_timeout(4000)
    flows.go(p, app, "Reading")
    t = text(p)
    saved, _ = books_of(app, p.email)
    if "1" in saved[0]["checks"]:
        return                                    # the check finished anyway: fine
    # otherwise what she wrote is not left hanging without an answer or a way to send it again
    assert "interrupted before the coach answered" in t and "Retry" in t, "her message sits there unanswered"
    flows.button(p, "Retry")
    assert flows.wait_text(p.page, "Day done", 30), "Retry sends what she wrote"
