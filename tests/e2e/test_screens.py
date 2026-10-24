"""Layout check: every main screen at the four widths she uses (phone 390,
iPad portrait 820, iPad landscape 1180, desktop 1440), light and dark.
Saves screenshots to docs/audit/screens/devices/ and fails on what can be
measured: the page scrolling sideways, anything under the chat box, text
on top of text, and buttons too small to tap on a touch screen."""
import itertools
import json
import sys
import time
from datetime import timedelta
from pathlib import Path

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
  // words on top of words: two pieces of text whose boxes overlap (what made
  // the collection's cards unreadable on the iPad)
  const head = (document.querySelector('[data-testid=stHeader]') || { getBoundingClientRect: () => ({ bottom: 0 }) }).getBoundingClientRect().bottom;
  const texts = [...document.querySelectorAll('[data-testid=stMain] :is(p, h1, h2, h3, h4, li, button, label)')].filter(e => {
    if (e.closest('.st-key-chat_dock') || e.closest('[data-testid=stSidebar]')) return false;
    if (!(e.innerText || '').trim()) return false;
    const s = getComputedStyle(e), b = e.getBoundingClientRect();
    if (s.visibility === 'hidden' || +s.opacity === 0 || b.width < 2 || b.height < 2) return false;
    if (b.top < head || b.bottom > window.innerHeight) return false;
    // drawn where it is, or under other words (the overlap this looks for); not hidden behind another
    // layer, like a list passing under the subject stage that stays put
    const hit = document.elementFromPoint(b.left + Math.min(b.width, 12) / 2, b.top + b.height / 2);
    return !!hit && (e.contains(hit) || hit.contains(e) || !!hit.closest('p, h1, h2, h3, h4, li, button, label'));
  });
  const overlap = [];
  for (let i = 0; i < texts.length; i++) for (let j = i + 1; j < texts.length; j++) {
    const a = texts[i], c = texts[j];
    if (a.contains(c) || c.contains(a)) continue;
    const x = a.getBoundingClientRect(), y = c.getBoundingClientRect();
    const w = Math.min(x.right, y.right) - Math.max(x.left, y.left), h = Math.min(x.bottom, y.bottom) - Math.max(x.top, y.top);
    if (w > 4 && h > 3) overlap.push(a.innerText.trim().slice(0, 24) + ' / ' + c.innerText.trim().slice(0, 24));
  }
  if (overlap.length) out.overlap = overlap.slice(0, 8);
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
    from coach import review
    day = review.LEGACY_FROM + timedelta(days=1)       # old lessons' review cards are due
    app.set_clock(day, "02:00:00")
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
    flows.to_check(p)
    assert flows.wait_text(p.page, "Submit answers", 40)
    shot(p, f"04_quiz_{tag}", problems)
    flows.open_app(p, app)
    flows.take_quiz(p, correct=False)
    shot(p, f"05_quiz_failed_{tag}", problems)
    flows.take_quiz(p, correct=True, start="Try a new set")
    shot(p, f"06_passed_{tag}", problems)
    for _ in range(2):
        flows.button(p, "Next lesson →")
        flows.pass_lesson(p)
    flows.button(p, "Finish today →")
    shot(p, f"07_done_{tag}", problems)
    # history, for Progress, Review and search
    entries = seed_history.build(day - timedelta(days=1), days=40)
    app.seed_entries(email, entries)
    flows.open_app(p, app, warmup=True)
    shot(p, f"07b_today_warm_up_{tag}", problems)
    flows.open_app(p, app, "/practice")
    shot(p, f"07c_practice_{tag}", problems)
    flows.open_app(p, app, "/review")
    shot(p, f"08_review_{tag}", problems)
    p.page.get_by_role("button", name="Collection").or_(p.page.get_by_role("radio", name="Collection")).first.click()
    shot(p, f"08b_collection_{tag}", problems)
    flows.open_app(p, app, "/course?subject=fashion")
    shot(p, f"13_course_{tag}", problems)
    flows.open_app(p, app, "/course?subject=philosophy")     # (the seeded history: many lessons passed)
    flows.open_panel(p, "Finished ·")
    shot(p, f"13b_course_finished_{tag}", problems)
    flows.open_app(p, app, "/records")
    shot(p, f"09_progress_{tag}", problems)
    flows.open_app(p, app, "/settings")
    shot(p, f"10_settings_{tag}", problems)
    for path, name in (("/courses", "14_courses"), ("/account", "16_account")):
        flows.open_app(p, app, path)
        shot(p, f"{name}_{tag}", problems)
    flows.open_menu(p)
    shot(p, f"17_menu_{tag}", problems)
    flows.open_app(p, app, "/reading")
    shot(p, f"11_reading_{tag}", problems)
    flows.button(p, "Search", exact=False)
    box = p.page.get_by_placeholder("Lessons, goals, review cards, books, your notes…")
    box.fill("philosophy")
    box.press("Enter")
    shot(p, f"12_search_{tag}", problems)
    (SHOTS / f"problems_{tag}.json").write_text(json.dumps(problems, indent=1))
    assert not {k: v for k, v in problems.items() if "sideways" in v or "under" in v or "overlap" in v}, problems



@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("width", list(SIZES))
def test_goal_screens(public_app, pages, width, scheme):
    """A goal of her own: her words, an answer to a vague goal, her path,
    the summary, Today made for her, the first win, Settings and the New
    goal page, and the numbers (admins)."""
    app = public_app
    app.set_llm()
    problems = {}
    tag = f"{width}_{scheme}"
    p = pages(width=width, height=SIZES[width], scheme=scheme)
    email = f"gscr{next(_n)}-{int(time.time() * 1000)}@example.com"
    flows.sign_in(p, app, email=email)
    shot(p, f"20_welcome_{tag}", problems)
    flows.button(p, "Working adult")
    flows.button(p, "Get started")
    shot(p, f"21_goal_{tag}", problems)
    flows.button(p, "I don't know yet")
    shot(p, f"21b_directions_{tag}", problems)
    flows.tap(p, p.page.get_by_role("button", name="Society", exact=False).first)
    flows.idle(p.page)
    shot(p, f"21c_directions_narrower_{tag}", problems)
    flows.button(p, "I'll write it myself")
    box = p.page.get_by_label("In your own words")
    box.fill("Get better at business stuff")
    p.page.keyboard.press("Tab")
    flows.button(p, "Design my path", wait=False)
    assert flows.wait_text(p.page, "What would you like to be able to do?", 40)
    shot(p, f"22_goal_clarify_{tag}", problems)
    box.fill("Read a company's financial statements")
    p.page.keyboard.press("Tab")
    flows.button(p, "Design my path", wait=False)
    assert flows.wait_text(p.page, "All of it, or some parts?", 40)
    flows.tap(p, p.page.get_by_text("No, only some parts", exact=True))
    flows.idle(p.page)
    shot(p, f"22b_goal_outline_{tag}", problems)
    flows.button(p, "Continue")
    flows.tap(p, p.page.locator('[class*="st-key-obp_pp_0"] button').first)
    flows.idle(p.page)
    shot(p, f"23_purpose_{tag}", problems)
    flows.button(p, "Continue")
    shot(p, f"24_confirm_{tag}", problems)
    flows.button(p, "Start learning")
    flows.idle(p.page, 30)
    shot(p, f"25_today_goal_{tag}", problems)
    flows.pass_lesson(p)
    shot(p, f"26_first_win_{tag}", problems)
    flows.open_app(p, app, "/settings")
    shot(p, f"27_settings_{tag}", problems)            # (the page, measured from its top)
    flows.idle(p.page)                                   # her goals: the section itself (the subjects'
    p.page.locator(".st-key-set_sec_goals").screenshot(  # picture stays at the top over the list below it)
        path=str(SHOTS / f"27b_settings_goals_{tag}.png"))
    flows.open_app(p, app, "/goal")
    shot(p, f"28_new_goal_{tag}", problems)
    flows.open_app(p, app, "/records")
    shot(p, f"29_progress_goal_{tag}", problems)
    q = pages(width=width, height=SIZES[width], scheme=scheme)
    flows.admin_sign_in(q, app)
    if flows.wait_text(q.page, "Get started", 3):
        flows.onboard(q)
    flows.open_app(q, app, "/account")
    flows.idle(q.page)
    q.page.locator(".st-key-set_sec_insights").screenshot(path=str(SHOTS / f"30_insights_{tag}.png"))
    (SHOTS / f"problems_goals_{tag}.json").write_text(json.dumps(problems, indent=1))
    assert not {k: v for k, v in problems.items() if "sideways" in v or "under" in v or "overlap" in v}, problems


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("width", list(SIZES))
def test_habit_screens(public_app, pages, width, scheme):
    """Coming back: a week of lessons, the rest day covering a missed day,
    the welcome after a break with its light day, the reminder note, the
    week in review, reminders in Settings, the course map's journey."""
    from datetime import date
    app = public_app
    app.set_llm()
    problems = {}
    tag = f"{width}_{scheme}"
    mon = date(2026, 11, 2)
    app.set_clock(mon, "02:00:00")
    p = pages(width=width, height=SIZES[width], scheme=scheme)
    email = f"hscr{next(_n)}-{int(time.time() * 1000)}@example.com"
    flows.sign_in(p, app, email=email)
    flows.onboard(p, subjects=("Philosophy", "Astronomy"), pace="Light")
    entries = seed_history.build(mon + timedelta(days=8), days=8, topics=("philosophy", "cosmos"), gaps=(), partial=())
    app.seed_entries(email, entries)
    app.set_clock(mon + timedelta(days=9), "02:00:00")          # one day missed: a rest day covers it
    flows.open_app(p, app, "/records")
    shot(p, f"40_progress_rest_{tag}", problems)
    flows.open_app(p, app, "/week")
    shot(p, f"41_week_{tag}", problems)
    flows.open_app(p, app, "/settings")
    p.page.get_by_text("Remind me to learn").click()
    flows.idle(p.page)
    p.page.locator(".st-key-set_sec_reminders").screenshot(path=str(SHOTS / f"42_reminders_{tag}.png"))
    app.set_clock(mon + timedelta(days=9), "11:30:00")           # 19:30 in Taipei: past her time
    flows.open_app(p, app)
    shot(p, f"43_today_reminder_{tag}", problems)
    app.set_clock(mon + timedelta(days=20), "02:00:00")          # back after a long break
    flows.open_app(p, app)
    shot(p, f"44_welcome_back_{tag}", problems)
    flows.open_app(p, app, "/course?subject=philosophy")
    shot(p, f"45_course_journey_{tag}", problems)
    (SHOTS / f"problems_habit_{tag}.json").write_text(json.dumps(problems, indent=1))
    assert not {k: v for k, v in problems.items() if "sideways" in v or "under" in v or "overlap" in v}, problems


@pytest.fixture(autouse=True)
def _real_clock_after(public_app):
    yield
    public_app.set_clock(None)


def into_view(p, selector):
    loc = p.page.locator(selector).first
    if loc.count():
        loc.scroll_into_view_if_needed()
        p.page.evaluate("window.scrollBy(0, -80)")
        flows.idle(p.page)


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("width", list(SIZES))
def test_mastery_screens(public_app, pages, width, scheme):
    """Phase 3: the quiz's kinds of exercise, its feedback on each mistake,
    explaining it back, the tutor's grounding, the skill map, practice from
    start to finish, the course map's levels, Progress's ideas."""
    from datetime import date
    from coach import mastery
    app = public_app
    app.set_llm()
    problems = {}
    tag = f"{width}_{scheme}"
    d0 = date(2026, 11, 2)
    app.set_clock(d0 + timedelta(days=8), "02:00:00")
    p = pages(width=width, height=SIZES[width], scheme=scheme)
    email = f"mscr{next(_n)}-{int(time.time() * 1000)}@example.com"
    flows.sign_in(p, app, email=email)
    flows.onboard(p, subjects=("Philosophy",), pace="Light")
    entries = seed_history.build(d0 + timedelta(days=8), days=8, topics=("philosophy",), gaps=(), partial=())
    for k, e in enumerate(entries):          # a mix: some ideas solid, some still being learned, one shaky
        for s in e["lessons"]:
            day = date.fromisoformat(e["date"])
            s["ev"] = [mastery.event("quiz", 0.9, day, "q")]
            if s["n"] % 3 == 0:
                s["ev"].append(mastery.event("review", 1.0, day + timedelta(days=1), "r"))
            if s["n"] % 5 == 0:
                s["ev"].append(mastery.event("practice", 0.0, day + timedelta(days=1), "p"))
    app.seed_entries(email, entries)
    flows.open_app(p, app)
    flows.start_lesson(p)
    flows.to_check(p)
    assert flows.wait_text(p.page, "Submit answers", 40)
    into_view(p, ".ex-scenario")
    shot(p, f"50_quiz_kinds_{tag}", problems)
    flows.answer_all(p, correct=False)
    flows.button(p, "Submit answers", wait=False)
    assert flows.wait_text(p.page, "You need 80%", 40)
    into_view(p, "[data-testid=stExpander]")
    shot(p, f"51_quiz_feedback_{tag}", problems)
    flows.take_quiz(p, correct=True, start="Try a new set")
    chat = p.page.locator('[data-testid="stChatInputTextArea"]')
    chat.fill("So a day comes from the orbit, right?")
    chat.press("Enter")
    assert flows.wait_text(p.page, "Based on this lesson", 30)
    into_view(p, ".tutor-based")
    shot(p, f"53_tutor_{tag}", problems)
    flows.button(p, "Finish today →")                # explaining it back: at the day's close
    box = p.page.locator(".st-key-explain_back textarea")
    box.fill("Philosophy asks what is real, what we can know and how to live, because Earth spins on its axis.")
    p.page.keyboard.press("Tab")
    flows.button(p, "Get feedback", wait=False)
    assert flows.wait_text(p.page, "Clear and correct.", 30)
    into_view(p, ".st-key-explain_back")
    shot(p, f"52_explain_{tag}", problems)
    flows.open_app(p, app, "/skills")               # (now the learning map)
    shot(p, f"54_skills_{tag}", problems)
    flows.open_app(p, app, "/practice")
    shot(p, f"56_practice_start_{tag}", problems)
    flows.button(p, "Start practice", wait=False)
    assert flows.wait_text(p.page, " done", 30)
    shot(p, f"57_practice_exercise_{tag}", problems)
    flows.answer_all(p, correct=False)
    flows.button(p, "Check")
    shot(p, f"58_practice_feedback_{tag}", problems)
    while "See how it went" not in p.page.evaluate("document.body.innerText"):
        flows.button(p, "Next")
        flows.answer_all(p, correct=True)
        flows.button(p, "Check")
    flows.button(p, "See how it went")
    shot(p, f"59_practice_done_{tag}", problems)
    flows.open_app(p, app, "/course?subject=philosophy")
    into_view(p, ".cm-row .sk-chip")
    shot(p, f"60_course_levels_{tag}", problems)
    flows.open_app(p, app, "/records")
    shot(p, f"61_progress_ideas_{tag}", problems)
    (SHOTS / f"problems_mastery_{tag}.json").write_text(json.dumps(problems, indent=1))
    assert not {k: v for k, v in problems.items() if "sideways" in v or "under" in v or "overlap" in v}, problems


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("width", list(SIZES))
def test_unit_check_screens(public_app, pages, width, scheme):
    """A unit check: Home's pointer, the set, its result, the course map after."""
    from datetime import date
    app = public_app
    problems = {}
    tag = f"{width}_{scheme}"
    d = date(2026, 11, 12)
    app.set_clock(d, "02:00:00")
    p = pages(width=width, height=SIZES[width], scheme=scheme)
    email = f"uscr{next(_n)}-{int(time.time() * 1000)}@example.com"
    flows.sign_in(p, app, email=email)
    flows.onboard(p, subjects=("Philosophy",), pace="Light")
    app.seed_entries(email, seed_history.build(d, days=6, topics=("philosophy",), gaps=(), partial=()))
    flows.open_app(p, app)
    shot(p, f"70_today_unit_{tag}", problems)
    flows.button(p, "Unit check", exact=False)
    shot(p, f"71_unit_set_{tag}", problems)
    for group in p.page.get_by_role("radiogroup").all():
        group.get_by_text("Right", exact=True).first.click()
    flows.button(p, "Check my answers")
    shot(p, f"72_unit_passed_{tag}", problems)
    flows.button(p, "Back to the learning map")
    shot(p, f"73_course_unit_{tag}", problems)
    app.set_clock(None)
    (SHOTS / f"problems_unit_{tag}.json").write_text(json.dumps(problems, indent=1))
    assert not {k: v for k, v in problems.items() if "sideways" in v or "under" in v or "overlap" in v}, problems


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("width", list(SIZES))
def test_round_five_screens(public_app, pages, width, scheme):
    """The fifth round's fixes: a lesson's top (its level, no Topic card) and
    end (no empty section; the disclaimer a footnote), the report menu with
    Send not ready yet, and the reading switch the Menu leads to."""
    app = public_app
    app.set_llm()
    problems = {}
    tag = f"{width}_{scheme}"
    p = pages(width=width, height=SIZES[width], scheme=scheme)
    flows.sign_in(p, app, email=f"r5{next(_n)}-{int(time.time() * 1000)}@example.com")
    flows.onboard(p, subjects=("Philosophy",))
    flows.start_lesson(p)
    p.page.locator(".st-key-current_lesson, [class*='st-key-lcard_']").first.scroll_into_view_if_needed()
    shot(p, f"80_lesson_top_{tag}", problems)
    flows.tap(p, p.page.locator('[class*="st-key-rep_lesson_"] button').first)
    flows.idle(p.page)
    shot(p, f"81_report_menu_{tag}", problems)
    send = p.page.get_by_test_id("stPopoverBody").get_by_role("button", name="Send", exact=True)
    assert send.is_disabled() and send.inner_text().strip() == "Send", "Send reads as a button before a reason"
    p.page.keyboard.press("Escape")
    flows.open_app(p, app, "/settings?open=reading")
    p.page.wait_for_timeout(1200)
    shot(p, f"82_reading_switch_{tag}", problems)
    (SHOTS / f"problems_r5_{tag}.json").write_text(json.dumps(problems, indent=1))
    assert not {k: v for k, v in problems.items() if "sideways" in v or "under" in v or "overlap" in v}, problems


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("width", list(SIZES))
def test_math_curriculum_screens(public_app, pages, width, scheme):
    """The math curriculum (views/math.py): the phases folded, one opened with
    its units, a prerequisite pressed opens its unit in another phase, and
    the sources at the end; reached from the Menu."""
    app = public_app
    problems = {}
    tag = f"{width}_{scheme}"
    p = pages(width=width, height=SIZES[width], scheme=scheme)
    flows.sign_in(p, app, email=f"mc{next(_n)}-{int(time.time() * 1000)}@example.com")
    flows.onboard(p, subjects=("Philosophy",))
    flows.tap(p, p.page.locator(".st-key-site_menu button").first)
    flows.tap(p, p.page.get_by_role("link", name="Math Curriculum"))
    assert flows.wait_text(p.page, "數學：從零到研究前沿", 20)
    flows.idle(p.page)
    shot(p, f"90_math_phases_{tag}", problems)
    flows.tap(p, p.page.get_by_text("L1 · 分數、比例與代數入門", exact=False).first)
    flows.idle(p.page)
    p.page.locator(".st-key-mc_u_L1_03").scroll_into_view_if_needed()
    shot(p, f"91_math_unit_{tag}", problems)
    assert p.page.locator(".st-key-mc_u_L1_03 a[target=_blank]").count() >= 1, "its sources open in a new tab"
    flows.tap(p, p.page.locator(".st-key-mc_go_L1-03_L0-08 button:visible").first)
    flows.idle(p.page)
    p.page.wait_for_timeout(900)
    assert "unit=L0-08" in p.page.url
    assert p.page.locator('[class*="st-key-mc_u_L0_08_here"]').is_visible(), "the prerequisite is open and in view"
    shot(p, f"92_math_prerequisite_{tag}", problems)
    p.page.locator(".st-key-mc_sources").scroll_into_view_if_needed()
    shot(p, f"93_math_sources_{tag}", problems)
    (SHOTS / f"problems_math_{tag}.json").write_text(json.dumps(problems, indent=1))
    assert not {k: v for k, v in problems.items() if "sideways" in v or "under" in v or "overlap" in v}, problems


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("width", list(SIZES))
def test_math_subject_screens(public_app, pages, width, scheme):
    """Mathematics as a subject: its first lesson (a learning outcome of
    L0-01), its course map with the way to the whole curriculum, which opens
    at the unit she is in, and its place on the subjects' stage."""
    app = public_app
    app.set_llm()
    problems = {}
    tag = f"{width}_{scheme}"
    p = pages(width=width, height=SIZES[width], scheme=scheme)
    flows.sign_in(p, app, email=f"ms{next(_n)}-{int(time.time() * 1000)}@example.com")
    flows.onboard(p, subjects=("Mathematics",))
    assert flows.wait_text(p.page, "Count a set of objects and explain that the last number said is the total", 20), "lesson 1 is the first outcome"
    flows.start_lesson(p)
    p.page.locator(".st-key-current_lesson, [class*='st-key-lcard_']").first.scroll_into_view_if_needed()
    shot(p, f"94_math_lesson_{tag}", problems)
    flows.open_app(p, app, "/course?subject=math")
    assert flows.wait_text(p.page, "L0-01 Counting and Numerals", 20)
    shot(p, f"95_math_course_map_{tag}", problems)
    flows.tap(p, p.page.locator(".st-key-cm_math button:visible").first)
    p.page.wait_for_timeout(900)
    assert "unit=L0-01" in p.page.url and p.page.locator('[class*="st-key-mc_u_L0_01_here"]').is_visible()
    assert flows.wait_text(p.page, "You're learning this", 10)
    shot(p, f"96_math_from_course_map_{tag}", problems)
    flows.open_app(p, app, "/settings?subject=math")
    p.page.wait_for_timeout(1200)
    shot(p, f"97_math_stage_{tag}", problems)
    flows.open_app(p, app, "/subject?subject=math")
    p.page.wait_for_timeout(1200)
    shot(p, f"98_math_world_{tag}", problems)
    (SHOTS / f"problems_math_subject_{tag}.json").write_text(json.dumps(problems, indent=1))
    assert not {k: v for k, v in problems.items() if "sideways" in v or "under" in v or "overlap" in v}, problems


def test_a_new_learner_adds_mathematics_from_the_curriculum(public_app, pages):
    """Someone learning only a goal of her own (no built-in subject offered
    in Goals & Settings) adds Mathematics from its curriculum page."""
    app = public_app
    p = pages(width=1440, height=900)
    flows.sign_in(p, app, email=f"ma{next(_n)}-{int(time.time() * 1000)}@example.com")
    flows.onboard(p, subjects=("Philosophy",))
    flows.open_app(p, app, "/math")
    assert flows.wait_text(p.page, "Learn it day by day", 20)
    flows.tap(p, p.page.locator(".st-key-mc_add button:visible").first)
    assert flows.wait_text(p.page, "Added. Mathematics takes its turn", 15)
    assert flows.wait_text(p.page, "Your learning map", 10)
