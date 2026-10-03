"""Whatever a person types: emoji, mixed languages, HTML and script, and very
long text with no spaces, in the chat, her thoughts, Search and the review
collection's search. It's kept as typed, shown as text, and never pushes
the page sideways or breaks it."""
import itertools
import time

import pytest

import flows
from conftest import covers

_n = itertools.count()
LONG = "x" * 3000
ODD = f"Why 🌍 轉? <b>bold</b> <script>alert(1)</script> {LONG}"


@pytest.mark.parametrize("width", [390, 1180])
def test_odd_input_everywhere(public_app, pages, width):
    covers("W-daily-ask_about_lesson", "W-topnav-search_q", "W-review-rv_query")
    app = public_app
    p = pages(width=width)
    flows.sign_in(p, app, email=f"odd{next(_n)}-{int(time.time() * 1000)}@example.com")
    flows.onboard(p)
    flows.open_app(p, app)
    page = p.page
    flows.start_lesson(p)
    page.get_by_placeholder("Ask about Lesson").fill(ODD)
    page.keyboard.press("Enter")
    assert flows.wait_text(page, "Good question", 30)
    flows.idle(page)
    t = page.evaluate("document.body.innerText")
    assert "Why 🌍 轉? <b>bold</b>" in t, "her question is shown exactly as typed, as text"
    assert page.locator("[data-testid=stMain] b", has_text="bold").count() == 0
    sideways = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
    main = page.evaluate("(() => { const m = document.querySelector('[data-testid=stMain]'); return m.scrollWidth - m.clientWidth; })()")
    assert sideways <= 1 and main <= 1, f"a long word pushed the page sideways ({sideways}, {main})"
    flows.open_panel(p, "My thoughts")
    page.get_by_label("Question to explore").fill(ODD)
    flows.button(p, "Save my thoughts")
    assert flows.wait_text(page, "Saved.", 10)
    flows.button(p, "Search", exact=False)
    q = page.get_by_placeholder("Lessons, subjects, books, your notes…")
    for query in ("🌍", "<script>alert(1)</script>", "轉", LONG[:500]):
        q.fill(query)
        q.press("Enter")
        flows.idle(page)
        assert "Traceback" not in page.evaluate("document.body.innerText")
    page.keyboard.press("Escape")
    flows.open_app(p, app, "/review")
    page.get_by_role("button", name="Collection").or_(page.get_by_role("radio", name="Collection")).first.click()
    flows.idle(page)
    assert "Traceback" not in page.evaluate("document.body.innerText")
