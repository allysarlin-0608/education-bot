"""Moving around: the top bar, Search, the subjects' worlds, the browser's
Back and Forward, and a refresh on every page (it stays on that page)."""
import itertools
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import pytest

import flows
from conftest import covers

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import seed_history  # noqa: E402

_n = itertools.count()


def today():
    return datetime.now(ZoneInfo("Asia/Taipei")).date()


def person(app, pages, width=1440, subjects=("Philosophy", "Astronomy"), history=False):
    p = pages(width=width)
    email = f"nav{next(_n)}-{int(time.time() * 1000)}@example.com"
    flows.sign_in(p, app, email=email)
    flows.onboard(p, subjects=subjects)
    entries = []
    if history:
        entries = seed_history.build(today(), days=35)
        entries[-1]["reflection"] = "Zebras <b>stripe</b> notes"
        app.seed_entries(email, entries)
    flows.open_app(p, app)
    return p, email, entries


def text(p):
    return p.page.evaluate("document.body.innerText")


def test_top_bar_goes_everywhere_and_back_forward_work(public_app, pages):
    covers("W-topnav-p")
    app = public_app
    p, _, _ = person(app, pages)
    for name, path in (("Record", "/records"), ("Plan", "/settings"), ("Home", "/")):
        flows.go(p, app, name)
        assert (urlparse(p.page.url).path.rstrip("/") or "/") == (path.rstrip("/") or "/"), p.page.url
    p.page.go_back()
    flows.idle(p.page)
    assert "/settings" in p.page.url and flows.wait_text(p.page, "Daily pace", 10)
    p.page.go_back()
    flows.idle(p.page)
    assert "/records" in p.page.url and flows.wait_text(p.page, "Backup and restore", 10)
    p.page.go_forward()
    flows.idle(p.page)
    assert "/settings" in p.page.url and flows.wait_text(p.page, "Daily pace", 10)


def test_the_menu_reaches_every_part_and_names_what_isnt_built(public_app, pages):
    covers("W-topnav-site_menu", "W-topnav-page", "W-topnav-by_title_learning_plan")
    app = public_app
    p, _, _ = person(app, pages)
    reached = {"Subjects & Courses": ("/courses", "More subjects"),
               "Learning Path": ("/path", "Your next days"), "Learning Plan": ("/settings", "Daily pace"),
               "Knowledge Map": ("/skills", "Knowledge Map"), "Review": ("/review", "Review"),
               "Practice": ("/practice", "Practice"), "Learning Record": ("/records", "Learning Record"),
               "Your week": ("/week", "week"), "Profile": ("/account", "Profile"),
               "Home": ("/", "Start this lesson")}
    for label, (path, marker) in reached.items():
        flows.menu(p, label)
        assert (urlparse(p.page.url).path.rstrip("/") or "/") == (path.rstrip("/") or "/"), (label, p.page.url)
        assert flows.wait_text(p.page, marker, 15), (label, marker)
        assert "Traceback" not in text(p)
    flows.menu(p, "Profile")
    flows.open_menu(p)
    t = text(p)
    assert "Subscription & Account Settings" in t and t.count("you are here") == 2, "Account: both its entries marked"
    for soon in ("Knowledge Exploration", "Examinations", "Research Portfolio", "Certificates"):
        assert soon in t, soon
    assert t.count("not available yet") >= 5, "the parts not built are named as such, not linked"
    assert "Reading Plan · off" in t, "no reading plan: the menu says where to turn it on"


@pytest.mark.parametrize("path,marker", [("/records", "Backup and restore"), ("/settings", "Daily pace"),
                                         ("/subject?subject=cosmos", "Astronomy")])
def test_a_refresh_stays_on_the_page(public_app, pages, path, marker):
    covers("W-topnav-p")
    app = public_app
    p, _, _ = person(app, pages)
    flows.open_app(p, app, path)
    assert flows.wait_text(p.page, marker, 15)
    p.page.reload()
    flows.idle(p.page, 40)
    assert flows.wait_text(p.page, marker, 15), f"a refresh on {path} lost the page"
    assert path.split("?")[0] in p.page.url


def test_search(public_app, pages):
    covers("W-topnav-nav_search", "W-topnav-search_q", "W-topnav-sopen")
    app = public_app
    p, _, entries = person(app, pages, history=True)
    flows.button(p, "Search", exact=False)
    box = p.page.get_by_placeholder("Lessons, subjects, books, your notes…")
    assert flows.wait_text(p.page, "Type a word or two", 5)
    box.fill("qwertyuiop")
    box.press("Enter")
    flows.idle(p.page)
    assert flows.wait_text(p.page, "No results for ‘qwertyuiop’.", 5)
    box.fill("<script>alert(1)</script>")
    box.press("Enter")
    flows.idle(p.page)
    box.fill("zebras")
    box.press("Enter")
    flows.idle(p.page)
    assert flows.wait_text(p.page, "1 result", 5)
    assert p.page.locator('[role="dialog"] b', has_text="stripe").count() == 0, "a note is shown as text"
    flows.tap(p, p.page.locator('[class*="st-key-sopen_0"] button'))
    flows.idle(p.page)
    d = datetime.fromisoformat(entries[-1]["date"]).date()
    assert "/records" in p.page.url and flows.wait_text(p.page, f"{d:%B} {d.day}", 10)
    # the dialog is gone once a result is opened
    assert p.page.locator('[role="dialog"]').count() == 0


def test_worlds(public_app, pages):
    covers("W-world-w_all", "W-world-w_today", "W-world-w_history", "W-world-w_enter")
    app = public_app
    p, _, _ = person(app, pages, history=True)
    today_subject = "Philosophy"
    flows.open_app(p, app, "/subject?subject=philosophy")
    assert flows.wait_text(p.page, "Where you are", 10)
    flows.button(p, "Begin today's lessons")
    assert flows.wait_text(p.page, "Start this lesson", 10)
    flows.open_app(p, app, "/subject?subject=cosmos")
    assert flows.wait_text(p.page, "Next on", 10), "a subject not on today says when it's next"
    flows.button(p, "Enter Philosophy", exact=False)
    assert "subject=philosophy" in p.page.url
    flows.button(p, "See its lessons so far")
    assert "/records" in p.page.url and flows.wait_text(p.page, "sessions", 10)
    flows.open_app(p, app, "/subject?subject=philosophy")
    flows.button(p, "All subjects", exact=False)
    assert "/settings" in p.page.url and "subject=philosophy" in p.page.url
    assert today_subject in text(p)


def test_an_unknown_subject_address_is_corrected(public_app, pages):
    covers("W-world-w_all")
    app = public_app
    p, _, _ = person(app, pages)
    flows.open_app(p, app, "/subject?subject=../../etc/passwd")
    assert flows.wait_text(p.page, "Where you are", 10)
    assert "subject=philosophy" in p.page.url or "subject=cosmos" in p.page.url
    assert "Traceback" not in text(p)


@pytest.mark.parametrize("width", [390, 768, 1024, 1180, 1440, 1920])
def test_world_fits(public_app, pages, width):
    covers("W-world-w_enter")
    app = public_app
    p, _, _ = person(app, pages, width=width)
    flows.open_app(p, app, "/subject?subject=philosophy")
    assert flows.wait_text(p.page, "Where you are", 10)
    assert p.page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), "horizontal scroll"


def test_the_first_enter_always_searches(public_app, pages):
    """Issue E: 20 tries, typed or with the word still an unconfirmed keyboard
    suggestion (autocorrect / predictive text) when Enter comes; right after
    opening and after changing pages. Every one searches on the first Enter,
    and the query stays in the box."""
    covers("W-topnav-search_q", "W-topnav-nav_search")
    app = public_app
    p, _, _ = person(app, pages, width=1024, history=True)
    page = p.page
    cdp = p.ctx.new_cdp_session(page)
    words = ["seed", "grows", "philosophy", "key idea"]
    failures = []
    for k in range(20):
        if k % 5 == 2:
            flows.go(p, app, ["Record", "Plan", "Home"][k % 3])
        flows.button(p, "Search", exact=False, wait=False)
        box = page.get_by_placeholder("Lessons, subjects, books, your notes…")
        box.wait_for(timeout=10000)
        word = words[k % 4]
        if k % 2:                                  # still a keyboard suggestion when Enter comes
            box.click()
            page.wait_for_timeout(120)             # (the old query gets selected on opening)
            box.press("Control+a")
            cdp.send("Input.imeSetComposition", {"text": word, "selectionStart": len(word), "selectionEnd": len(word)})
            page.keyboard.press("Enter")
            cdp.send("Input.insertText", {"text": word})
        else:
            page.wait_for_timeout(120)
            page.keyboard.type(word, delay=15)     # replaces the selected old query
            page.keyboard.press("Enter")
        shown = flows.wait_text(page, "result", 6)
        value = box.input_value()
        if not shown or value != word:
            failures.append((k, word, value, shown))
        page.keyboard.press("Escape")
        flows.idle(page)
    assert not failures, failures
