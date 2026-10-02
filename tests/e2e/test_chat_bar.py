"""Issue F: the floating chat box never hides a control or the page's last
line. Today in its lesson, quiz and result states, at 390/768/1180/1440 and
with a short window (the iPad's keyboard open); and a Retry that appears
right where the box floats is brought into view. Screenshots of the end of
each state go to docs/audit/screens/chat_bar/."""
import itertools
import time
from pathlib import Path

import pytest

import flows
from conftest import covers

_n = itertools.count()
SHOTS = Path(__file__).resolve().parents[2] / "docs" / "audit" / "screens" / "chat_bar"

UNDER = """() => { const dock = document.querySelector('.st-key-chat_dock'); if (!dock) return ['no chat box'];
  const r = dock.getBoundingClientRect(); const out = [];
  for (const c of document.querySelectorAll('button, a[href], textarea, input, [data-testid=stAlert], p, li, h3, h4')) {
    if (dock.contains(c) || c.closest('details:not([open]) > :not(summary)')) continue;
    const b = c.getBoundingClientRect(); if (b.width < 2 || b.height < 2) continue;
    if (b.bottom > r.top + 1 && b.top < r.bottom && b.right > r.left && b.left < r.right)
      out.push((c.innerText || c.getAttribute('aria-label') || c.tagName).trim().slice(0, 40));
  } return out; }"""


def at_end(page):
    page.evaluate("""() => {      // the element that actually scrolls (Streamlit's main area, or the window)
        const dock = document.querySelector('.st-key-chat_dock');
        for (let e = dock; e; e = e.parentElement) {
            const o = getComputedStyle(e).overflowY;
            if ((o === 'auto' || o === 'scroll') && e.scrollHeight > e.clientHeight) { e.scrollTop = e.scrollHeight; return; }
        }
        window.scrollTo(0, document.scrollingElement.scrollHeight); }""")
    last = None
    for _ in range(40):                       # smooth scrolling: wait until it has arrived
        page.wait_for_timeout(100)
        pos = page.evaluate("() => [...document.querySelectorAll('*')].reduce((a, e) => a + e.scrollTop, 0)")
        if pos == last:
            break
        last = pos
    return page.evaluate(UNDER)


@pytest.mark.parametrize("width,height", [(390, 844), (768, 1024), (1180, 820), (1440, 900), (1024, 420)])
def test_the_end_of_today_is_never_under_the_chat_box(public_app, pages, width, height):
    covers("W-daily-ask_about_lesson_report_your_progress_or")
    app = public_app
    SHOTS.mkdir(parents=True, exist_ok=True)
    p = pages(width=width)                          # set up at the device's usual height
    flows.sign_in(p, app, email=f"bar{next(_n)}-{int(time.time() * 1000)}@example.com")
    flows.onboard(p)
    p.page.set_viewport_size({"width": width, "height": height})     # (420: the on-screen keyboard is open)
    flows.open_app(p, app)
    app.set_llm()
    page = p.page
    problems = {}
    flows.start_lesson(p)                                    # the lesson state
    problems["lesson"] = at_end(page)
    page.screenshot(path=str(SHOTS / f"lesson_{width}x{height}.png"))
    flows.button(p, "Take the quiz", wait=False)             # the quiz state
    assert flows.wait_text(page, "Submit answers", 40)
    flows.idle(page)
    problems["quiz"] = at_end(page)
    page.screenshot(path=str(SHOTS / f"quiz_{width}x{height}.png"))
    # answer it (all right) and submit: the result state
    for g in range(page.locator('[data-testid="stRadio"]').count()):
        flows.tap(p, page.locator('[data-testid="stRadio"]').nth(g).get_by_text("It spins on its axis", exact=True))
        page.wait_for_timeout(80)
    rights = ["The line Earth spins around", "One spin a day", "One trip around the Sun", "When the Sun comes into view"]
    for j in range(page.locator('[data-testid="stSelectbox"]').count()):
        flows.choose(p, page.locator('[data-testid="stSelectbox"]').nth(j), rights[j])
    for j in range(page.locator('textarea[placeholder^="Answer in a sentence"]').count()):
        page.locator('textarea[placeholder^="Answer in a sentence"]').nth(j).fill("Because Earth spins on its axis.")
        page.keyboard.press("Tab")
    flows.idle(page)
    flows.button(p, "Submit answers", wait=False)
    assert flows.wait_text(page, "Passed with", 40)
    flows.idle(page)
    problems["result"] = at_end(page)
    page.screenshot(path=str(SHOTS / f"result_{width}x{height}.png"))
    problems = {k: v for k, v in problems.items() if v}
    assert not problems, problems


@pytest.mark.parametrize("width,height", [(390, 844), (1024, 768)])
def test_a_retry_that_appears_under_the_chat_box_is_brought_into_view(public_app, pages, width, height):
    covers("W-daily-coach_retry")
    app = public_app
    p = pages(width=width, height=height)
    flows.sign_in(p, app, email=f"bar{next(_n)}-{int(time.time() * 1000)}@example.com")
    flows.onboard(p)
    flows.open_app(p, app)
    app.set_llm()
    flows.start_lesson(p)
    page = p.page
    # the button low on the screen, just above the chat box, as when she taps it
    page.evaluate("""() => { const b = [...document.querySelectorAll('button')].find(x => x.innerText.trim() === 'Take the quiz');
        const d = document.querySelector('.st-key-chat_dock').getBoundingClientRect();
        window.scrollBy(0, b.getBoundingClientRect().bottom - d.top + 8); }""")
    app.set_llm(mode="invalid")
    flows.tap(p, page.get_by_role("button", name="Take the quiz", exact=True))
    assert flows.wait_text(page, "didn't manage", 40)
    flows.idle(page)
    page.wait_for_timeout(900)
    covered = [x for x in page.evaluate(UNDER) if x.startswith(("Retry", "The coach"))]
    app.set_llm()
    assert not covered, f"under the chat box: {covered}"


@pytest.mark.parametrize("width,height", [(390, 844), (1180, 820), (1440, 900)])
def test_next_lesson_after_a_pass_is_in_view_above_the_chat_box(public_app, pages, width, height):
    """After passing a quiz, Next lesson is on screen and clear of the chat
    box without scrolling."""
    covers("W-daily-next_lesson")
    app = public_app
    p = pages(width=width, height=height)
    flows.sign_in(p, app, email=f"bar{next(_n)}-{int(time.time() * 1000)}@example.com")
    flows.onboard(p)                                   # three lessons a day: a pass offers Next lesson
    flows.open_app(p, app)
    app.set_llm()
    flows.start_lesson(p)
    page = p.page

    def at_the_bottom(page):                           # she taps Submit at the end of the page, just above the box
        at_end(page)
        page.wait_for_timeout(300)
    app.set_llm(delay=1.5)                             # marking takes a moment, as with the real model
    flows.take_quiz(p, correct=True, before_submit=at_the_bottom)
    app.set_llm()
    page.wait_for_timeout(1500)                        # (the smooth scroll)
    box = page.evaluate("""() => { const b = [...document.querySelectorAll('button')].find(x => x.innerText.includes('Next lesson'));
        const d = document.querySelector('.st-key-chat_dock').getBoundingClientRect();
        if (!b) return null; const r = b.getBoundingClientRect(); return {top: r.top, bottom: r.bottom, dock: d.top}; }""")
    assert box is not None, "no Next lesson button"
    assert box["top"] >= 0 and box["bottom"] <= box["dock"] - 48, f"Next lesson is hidden or near the chat box: {box}"
