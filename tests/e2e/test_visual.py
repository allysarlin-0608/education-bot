"""Layout on every page at every width, light and dark, on a fixed date
with a 35-day history:
- no horizontal scroll, nothing cut off at the right edge;
- no layout shift after the page has drawn (CLS);
- the floating chat box and the top bar never cover the page's content
  (also with a short window, as with an on-screen keyboard);
- visual regression: screenshots at 390 and 1440 compared with the saved
  baselines (tests/e2e/baseline); a missing baseline is written, and a
  difference is saved next to the failure for review.

UPDATE_BASELINE=1 pytest tests/e2e/test_visual.py rewrites the baselines.
"""
import os
import sys
import time
from datetime import date
from pathlib import Path

import pytest

import flows
from conftest import RESULTS, WIDTHS, covers

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import seed_history  # noqa: E402

DAY = date(2026, 9, 28)
BASE = Path(__file__).resolve().parent / "baseline"
PAGES = [("today", "/", "Start this lesson"), ("progress", "/records", "Longest streak"),
         ("settings", "/settings", "Daily pace"), ("reading", "/reading", "Start a new book"),
         ("world", "/subject?subject=philosophy", "Where you are")]
SHIFT = """() => new Promise(done => { let cls = 0;
    new PerformanceObserver(l => { for (const e of l.getEntries()) if (!e.hadRecentInput) cls += e.value; })
        .observe({type: 'layout-shift', buffered: false});
    setTimeout(() => done(cls), 1500); })"""
COVERED = """() => {
  const dock = document.querySelector('.st-key-chat_dock'); const bar = document.querySelector('.st-key-topnav');
  const out = [];
  for (const [name, el] of [['chat box', dock], ['top bar', bar]]) {
    if (!el) continue; const r = el.getBoundingClientRect();
    if (getComputedStyle(el).position !== 'fixed' && getComputedStyle(el).position !== 'sticky') continue;
    // controls that sit under it and can't be scrolled out from under it
    const scroller = document.scrollingElement;
    const atEnd = scroller.scrollTop + innerHeight >= scroller.scrollHeight - 2;
    if (name === 'chat box' && !atEnd) continue;     // only the end of the page is at risk
    for (const c of document.querySelectorAll('button, a[href], input, textarea, [role=tab]')) {
      if (el.contains(c)) continue; const b = c.getBoundingClientRect();
      if (b.width < 2 || b.height < 2) continue;
      const overlap = Math.min(b.bottom, r.bottom) - Math.max(b.top, r.top);
      const across = Math.min(b.right, r.right) - Math.max(b.left, r.left);
      if (overlap > 4 && across > 4 && (name === 'chat box' || b.top >= r.top)) out.push(name + ' covers ' + (c.innerText || c.getAttribute('aria-label') || c.tagName).trim().slice(0, 30));
    }
  }
  return out; }"""


@pytest.fixture(scope="module")
def dated(public_app):
    public_app.set_clock(DAY)
    yield public_app
    public_app.set_clock(None)


@pytest.fixture(scope="module")
def account(dated, browser):
    import conftest
    p = conftest.Page(browser, width=1440)
    email = f"visual-{int(time.time() * 1000)}@example.com"
    flows.sign_in(p, dated, email=email)
    flows.onboard(p, reading=True)
    dated.seed_entries(email, seed_history.build(DAY, days=35))
    storage = p.ctx.storage_state()
    p.close()
    return storage


def open_page(browser, app, storage, width, scheme, path, marker, height=None):
    import conftest
    p = conftest.Page(browser, width=width, height=height, scheme=scheme, reduced_motion=True)
    p.ctx.add_cookies(storage["cookies"])
    flows.open_app(p, app, path)
    assert flows.wait_text(p.page, marker, 20), f"{path} at {width}: no {marker!r}"
    p.page.wait_for_timeout(400)
    return p


def compare(name, png):
    from PIL import Image, ImageChops
    import io
    BASE.mkdir(parents=True, exist_ok=True)
    base = BASE / f"{name}.png"
    if os.environ.get("UPDATE_BASELINE") or not base.exists():
        base.write_bytes(png)
        return None
    a, b = Image.open(base).convert("RGB"), Image.open(io.BytesIO(png)).convert("RGB")
    if a.size != b.size:
        return f"size {a.size} → {b.size}"
    diff = ImageChops.difference(a, b).convert("L").point(lambda v: 255 if v > 40 else 0)
    changed = sum(1 for v in diff.getdata() if v) / (a.size[0] * a.size[1])
    if changed > 0.004:
        out = RESULTS / "visual"
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{name}.now.png").write_bytes(png)
        diff.save(out / f"{name}.diff.png")
        return f"{changed:.2%} of pixels changed (see results/visual/{name}.*)"
    return None


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("width", list(WIDTHS))
def test_layout(dated, browser, account, width, scheme):
    covers("W-topnav-p")
    problems = []
    for name, path, marker in PAGES:
        p = open_page(browser, dated, account, width, scheme, path, marker)
        page = p.page
        if not page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"):
            wide = page.evaluate("""() => [...document.querySelectorAll('body *')].filter(e => e.getBoundingClientRect().right > innerWidth + 1)
                .slice(0, 3).map(e => e.className.toString().slice(0, 50) || e.tagName)""")
            problems.append(f"{name}: horizontal scroll ({wide})")
        cls = page.evaluate(SHIFT)
        if cls > 0.05:
            problems.append(f"{name}: layout shift {cls:.3f} after drawing")
        page.evaluate("window.scrollTo(0, document.scrollingElement.scrollHeight)")
        page.wait_for_timeout(300)
        covered = page.evaluate(COVERED)
        if covered:
            problems.append(f"{name}: {sorted(set(covered))[:4]}")
        if width in (390, 1440):
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(200)
            why = compare(f"{name}_{width}_{scheme}", page.screenshot())
            if why:
                problems.append(f"{name}: looks different: {why}")
        p.close()
    assert not problems, problems


@pytest.mark.parametrize("width,height", [(1024, 420), (768, 560), (390, 420)])
def test_a_short_window_keyboard_open(dated, browser, account, width, height):
    """An on-screen keyboard leaves a short window: the chat box must not
    sit over the text box she is typing in, or over the lesson's last lines."""
    covers("W-daily-ask_about_lesson_report_your_progress_or")
    p = open_page(browser, dated, account, width, "light", "/", "Start this lesson", height=height)
    page = p.page
    box = page.locator(".st-key-chat_dock textarea")
    if box.count():
        box.first.focus()
        page.wait_for_timeout(300)
        r = box.first.bounding_box()
        assert r and r["y"] + r["height"] <= height + 1, "the chat box is pushed out of the window"
    page.evaluate("window.scrollTo(0, document.scrollingElement.scrollHeight)")
    page.wait_for_timeout(300)
    assert page.evaluate(COVERED) == []
    p.close()
