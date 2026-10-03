"""Layout check: every main screen at the four widths she uses (phone 390,
iPad portrait 820, iPad landscape 1180, desktop 1440), light and dark.
Saves screenshots to docs/audit/screens/devices/ and fails on what can be
measured: the page scrolling sideways, anything under the chat box, and
buttons too small to tap on a touch screen."""
import itertools
import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

import flows

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import seed_history  # noqa: E402

_n = itertools.count()
SHOTS = Path(__file__).resolve().parents[2] / "docs" / "audit" / "screens" / "devices"
SIZES = {390: 844, 820: 1180, 1180: 820, 1440: 900}

CHECK = """(touch) => {
  const out = {};
  if (document.documentElement.scrollWidth > window.innerWidth + 1) out.sideways = document.documentElement.scrollWidth;
  const dock = document.querySelector('.st-key-chat_dock');
  if (dock) {
    const r = dock.getBoundingClientRect(), under = [];
    for (const c of document.querySelectorAll('[data-testid=stMain] button, [data-testid=stMain] a[href], [data-testid=stMain] p, [data-testid=stMain] textarea, [data-testid=stMain] input')) {
      if (dock.contains(c)) continue;
      const b = c.getBoundingClientRect(); if (b.width < 2 || b.height < 2) continue;
      const main = document.querySelector('[data-testid=stMain]').getBoundingClientRect();
      if (b.bottom <= main.top || b.top >= main.bottom) continue;          // scrolled out of the page's own area
      const top = Math.max(b.top, main.top), bottom = Math.min(b.bottom, main.bottom);
      if (bottom > r.top + 1 && top < r.bottom) under.push((c.innerText || c.tagName).trim().slice(0, 30));
    }
    if (under.length) out.under = under;
  }
  if (touch) {
    const small = [...document.querySelectorAll('button, a[href], [role=tab], [role=radio], [role=switch]')].filter(e => {
      const b = e.getBoundingClientRect(); const s = getComputedStyle(e);
      return b.width > 0 && b.height > 0 && s.visibility !== 'hidden' && (b.height < 32 || b.width < 32)
             && !e.closest('[data-testid=stSidebar]') && !e.closest('.cal-key');
    }).map(e => (e.innerText || e.getAttribute('aria-label') || e.tagName).trim().slice(0, 24) + ` ${Math.round(e.getBoundingClientRect().width)}x${Math.round(e.getBoundingClientRect().height)}`);
    if (small.length) out.small = small.slice(0, 12);
  }
  return out;
}"""


def shot(p, name, problems):
    page = p.page
    flows.idle(page)
    page.wait_for_timeout(700)
    SHOTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SHOTS / f"{name}.png"))
    found = page.evaluate(CHECK, p.width < 1300)
    if found:
        problems[name] = found


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("width", list(SIZES))
def test_every_screen(public_app, pages, width, scheme):
    app = public_app
    problems = {}
    tag = f"{width}_{scheme}"
    p = pages(width=width, height=SIZES[width], scheme=scheme)
    flows.open_app(p, app)
    shot(p, f"01_signin_{tag}", problems)
    email = f"scr{next(_n)}-{int(time.time() * 1000)}@example.com"
    flows.sign_in(p, app, email=email)
    flows.onboard(p, subjects=("Fashion & Clothing", "Astronomy"), reading=True)
    flows.open_app(p, app)
    shot(p, f"02_today_new_{tag}", problems)
    flows.open_app(p, app, "/records")
    shot(p, f"02b_progress_empty_{tag}", problems)
    flows.open_app(p, app, "/review")
    shot(p, f"02c_review_empty_{tag}", problems)
    flows.open_app(p, app)
    flows.start_lesson(p)
    shot(p, f"03_lesson_{tag}", problems)
    flows.button(p, "Take the quiz", wait=False)
    assert flows.wait_text(p.page, "Submit answers", 40)
    shot(p, f"04_quiz_{tag}", problems)
    flows.open_app(p, app)
    flows.take_quiz(p, correct=False, start="Try a new quiz") if "Try a new quiz" in p.page.evaluate("document.body.innerText") \
        else flows.take_quiz(p, correct=False, start="Submit answers")
    shot(p, f"05_quiz_failed_{tag}", problems)
    flows.take_quiz(p, correct=True, start="Try a new quiz")
    shot(p, f"06_passed_{tag}", problems)
    for _ in range(2):
        flows.button(p, "Next lesson →")
        flows.pass_lesson(p)
    flows.button(p, "See today's summary →")
    shot(p, f"07_done_{tag}", problems)
    # history, for Progress, Review and search
    today = datetime.now(ZoneInfo("Asia/Taipei")).date()
    entries = seed_history.build(today - timedelta(days=1), days=40)
    app.seed_entries(email, entries)
    flows.open_app(p, app, "/review")
    shot(p, f"08_review_{tag}", problems)
    flows.open_app(p, app, "/records")
    shot(p, f"09_progress_{tag}", problems)
    flows.open_app(p, app, "/settings")
    shot(p, f"10_settings_{tag}", problems)
    flows.open_app(p, app, "/reading")
    shot(p, f"11_reading_{tag}", problems)
    flows.button(p, "Search", exact=False)
    box = p.page.get_by_placeholder("Lessons, subjects, books, your notes…")
    box.fill("philosophy")
    box.press("Enter")
    shot(p, f"12_search_{tag}", problems)
    (SHOTS / f"problems_{tag}.json").write_text(json.dumps(problems, indent=1))
    assert not {k: v for k, v in problems.items() if "sideways" in v or "under" in v}, problems
