"""Timings (criterion 1.2): every common action measured 10 times on a
learner with a 35-day history; p50/p95 go to results/perf.json.

- page load to first meaningful content: p95 <= 2.5 s
- non-AI actions (navigation, picking, saving, searching): p95 <= 1.0 s
- visible feedback on a press: <= 100 ms (measured in test_ai.py)
"""
import json
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

import flows
from conftest import RESULTS, covers

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import seed_history  # noqa: E402

N = 10
LOAD_P95, ACTION_P95 = 2.5, 1.0
_results = {}


def p95(xs):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(0.95 * (len(xs) - 1))))]


def record(name, xs, limit):
    _results[name] = {"n": len(xs), "p50": round(statistics.median(xs), 3), "p95": round(p95(xs), 3),
                      "max": round(max(xs), 3), "limit": limit}
    out = RESULTS / "perf.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    have = json.loads(out.read_text()) if out.exists() else {}
    have.update(_results)
    out.write_text(json.dumps(have, indent=1))


@pytest.fixture(scope="module")
def learner(public_app, browser):
    import conftest
    p = conftest.Page(browser, width=1440)
    email = f"perf-{int(time.time() * 1000)}@example.com"
    flows.sign_in(p, public_app, email=email)
    flows.onboard(p, reading=True)
    today = datetime.now(ZoneInfo("Asia/Taipei")).date()
    public_app.seed_entries(email, seed_history.build(today, days=35))
    flows.open_app(p, public_app)
    yield p
    p.close()


def until(page, check, timeout=15):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            if check():
                return time.time() - t0
        except Exception:
            pass
        page.wait_for_timeout(20)
    return timeout


def text_has(page, s):
    return lambda: s in page.evaluate("document.body.innerText")


@pytest.mark.parametrize("path,marker", [("/", "Start this lesson"), ("/records", "Longest streak"),
                                         ("/settings", "Daily pace"), ("/reading", "Start a new book"),
                                         ("/subject?subject=philosophy", "Where you are")])
def test_page_load(public_app, learner, path, marker):
    covers("W-topnav-p")
    page = learner.page
    xs = []
    for _ in range(N):
        t0 = time.time()
        page.goto(public_app.url + path)
        until(page, text_has(page, marker), 20)
        xs.append(time.time() - t0)
        flows.idle(page)
    record(f"load {path}", xs, LOAD_P95)
    assert p95(xs) <= LOAD_P95, f"{path}: p95 {p95(xs):.2f} s"


@pytest.mark.parametrize("name,frm,to_label,marker", [
    ("nav Today→Progress", "/", "Progress", "Longest streak"),
    ("nav Progress→Settings", "/records", "Settings", "Daily pace"),
    ("nav Settings→Today", "/settings", "Today", "Start this lesson"),
    ("nav Today→Reading", "/", "Reading", "Start a new book"),
])
def test_navigation(public_app, learner, name, frm, to_label, marker):
    covers("W-topnav-p")
    page = learner.page
    xs = []
    for _ in range(N):
        page.goto(public_app.url + frm)
        flows.idle(page)
        t0 = time.time()
        page.locator('.st-key-topnav [data-testid="stPageLink-NavLink"]', has_text=to_label).first.click()
        until(page, text_has(page, marker))
        xs.append(time.time() - t0)
        flows.idle(page)
    record(name, xs, ACTION_P95)
    assert p95(xs) <= ACTION_P95, f"{name}: p95 {p95(xs):.2f} s"


def test_calendar_day_and_month(public_app, learner):
    covers("W-records-name", "W-records-cal_prev")
    page = learner.page
    page.goto(public_app.url + "/records")
    flows.idle(page)
    days, months = [], []
    for k in range(N):
        buttons = page.locator('[class*="st-key-cal_20"][class*="_done"] button, [class*="st-key-cal_20"][class*="_partial"] button')
        target = buttons.nth(k % max(1, buttons.count()))
        label = target.inner_text()
        t0 = time.time()
        target.click()
        until(page, lambda: page.locator('[class*="st-key-prog_day_"]').count() and label in
              page.locator('[class*="st-key-prog_day_"]').first.inner_text())
        days.append(time.time() - t0)
        flows.idle(page)
        head = page.locator(".st-key-cal_head").inner_text()
        t0 = time.time()
        page.get_by_role("button", name="‹").click()
        until(page, lambda: page.locator(".st-key-cal_head").inner_text() != head)
        months.append(time.time() - t0)
        flows.idle(page)
        page.get_by_role("button", name="›").click()
        flows.idle(page)
    record("pick a calendar day", days, ACTION_P95)
    record("previous month", months, ACTION_P95)
    assert p95(days) <= ACTION_P95 and p95(months) <= ACTION_P95, (p95(days), p95(months))


def test_progress_views(public_app, learner):
    covers("W-records-prog_view")
    page = learner.page
    page.goto(public_app.url + "/records")
    flows.idle(page)
    xs = []
    for k in range(N):
        view, marker = [("Sessions", "sessions"), ("Subjects", " written so far"), ("Day", "Completed")][k % 3]
        t0 = time.time()
        page.get_by_role("radio", name=view).or_(page.get_by_role("button", name=view, exact=True)).first.click()
        until(page, text_has(page, marker))
        xs.append(time.time() - t0)
        flows.idle(page)
    record("switch Progress view", xs, ACTION_P95)
    assert p95(xs) <= ACTION_P95, p95(xs)


def test_settings_pick(public_app, learner):
    covers("W-choices-pick")
    page = learner.page
    page.goto(public_app.url + "/settings")
    flows.idle(page)
    xs = []
    for k in range(N):
        name = ["Focused", "Steady"][k % 2]
        t0 = time.time()
        page.locator(".st-key-set_sec_pace").get_by_role("button", name=name, exact=False).first.click()
        until(page, lambda: f"{name}, selected" in page.evaluate(
            "[...document.querySelectorAll('.st-key-set_sec_pace button')].map(b => b.innerText).join('|')"))
        xs.append(time.time() - t0)
        flows.idle(page)
    record("change daily pace", xs, ACTION_P95)
    assert p95(xs) <= ACTION_P95, p95(xs)


def test_search(public_app, learner):
    covers("W-topnav-search_q")
    page = learner.page
    page.goto(public_app.url + "/")
    flows.idle(page)
    xs = []
    for k in range(N):
        page.get_by_role("button", name="Search").first.click()
        box = page.get_by_placeholder("Lessons, subjects, books, your notes…")
        box.wait_for()
        box.fill(["seed", "key idea", "philosophy", "grows"][k % 4])
        t0 = time.time()
        box.press("Enter")
        until(page, text_has(page, "result"))
        xs.append(time.time() - t0)
        page.keyboard.press("Escape")
        flows.idle(page)
    record("search", xs, ACTION_P95)
    assert p95(xs) <= ACTION_P95, p95(xs)


def test_save_thoughts(public_app, learner):
    covers("W-daily-save_my_thoughts")
    page = learner.page
    page.goto(public_app.url + "/")
    flows.idle(page)
    if page.get_by_role("button", name="Start this lesson").count():     # the thoughts box comes with a lesson
        flows.start_lesson(learner)
    xs = []
    page.get_by_text("My thoughts on the question to explore", exact=False).click()
    for k in range(N):
        page.get_by_label("Question to explore").fill(f"thought {k}")
        page.keyboard.press("Tab")
        flows.idle(page)
        t0 = time.time()
        page.get_by_role("button", name="Save my thoughts").click()
        until(page, text_has(page, "Saved."))
        xs.append(time.time() - t0)
        flows.idle(page)
        page.wait_for_timeout(300)
    record("save my thoughts", xs, ACTION_P95)
    assert p95(xs) <= ACTION_P95, p95(xs)
