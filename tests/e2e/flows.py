"""What a person does in the app, as reusable steps for the tests."""
import time

from playwright.sync_api import TimeoutError as PlaywrightTimeout

from conftest import ADMIN, PASSWORD, record_timing

TOUCH_W = 900


def _visible_text(page):
    return page.evaluate("document.body.innerText")


def wait_text(page, text, timeout=20):
    """True once text is in the visible page (innerText skips hidden parts)."""
    end = time.time() + timeout
    while time.time() < end:
        try:
            if text in _visible_text(page):
                return True
        except Exception:
            pass
        page.wait_for_timeout(150)
    return False


def gone_text(page, text, timeout=20):
    end = time.time() + timeout
    while time.time() < end:
        try:
            if text not in _visible_text(page):
                return True
        except Exception:
            pass
        page.wait_for_timeout(150)
    return False


def idle(page, timeout=30):
    """The script has finished its run (Streamlit's running indicator gone,
    twice in a row). A navigation in between (a sign-in redirect) is waited out."""
    end = time.time() + timeout
    page.wait_for_timeout(120)
    quiet = 0
    while time.time() < end:
        try:
            page.wait_for_load_state("domcontentloaded", timeout=5000)
            running = page.evaluate("!!document.querySelector('[data-testid=\"stStatusWidget\"]')")
        except Exception:
            running = True
        quiet = 0 if running else quiet + 1
        if quiet >= 3:              # ~450 ms without a run: a rerun that follows a rerun has started by then
            return True
        page.wait_for_timeout(150)
    return False


def tap(p, locator):
    (locator.tap() if p.width < TOUCH_W else locator.click())


def button(p, name, exact=True, wait=True):
    loc = p.page.get_by_role("button", name=name, exact=exact).first
    tap(p, loc)
    if wait:
        idle(p.page)


def timed_click(p, action, locator, done, timeout=30):
    """Press like a person (down, ~90 ms, up), then measure: first visible
    feedback (the pressed style on the control, a change in the page, or the
    result) and completion (done(page))."""
    page = p.page
    page.evaluate("""() => { window.__fb = null; window.__t0 = null;
        const hit = () => { if (window.__fb === null && window.__t0 !== null) window.__fb = performance.now() - window.__t0; };
        const obs = new MutationObserver(hit);
        obs.observe(document.body, {subtree: true, childList: true, attributes: true, characterData: true});
        window.__obs = obs;
        document.addEventListener('pointerdown', (e) => {
            window.__t0 = performance.now();
            const el = e.target.closest('button, a, [role=button], summary') || e.target;
            const look = () => { const c = getComputedStyle(el); return [c.transform, c.backgroundColor, c.color, c.opacity, c.boxShadow].join('|'); };
            const before = look();
            const check = () => { if (window.__fb !== null) return;
                if (look() !== before) hit(); else if (performance.now() - window.__t0 < 1000) requestAnimationFrame(check); };
            requestAnimationFrame(check);
        }, {capture: true, once: true}); }""")
    t0 = time.time()
    if p.width < TOUCH_W:
        locator.tap()
    else:
        locator.hover()
        page.mouse.down()
        page.wait_for_timeout(90)
        page.mouse.up()
    end = t0 + timeout
    while time.time() < end and not done(page):
        page.wait_for_timeout(50)
    total = time.time() - t0
    feedback = page.evaluate("() => { window.__obs && window.__obs.disconnect(); return window.__fb; }")
    record_timing(action, total, feedback_ms=feedback, width=p.width)
    return total, feedback


# ---- signing in -------------------------------------------------------------
def open_app(p, app, path="/"):
    """Load a page (a new session). A personal app asks for its password
    again on every load, as it always has; that's entered here."""
    p.page.goto(app.url + path)
    idle(p.page, 40)
    if app.mode == "personal" and p.page.get_by_label("Password", exact=True).count():
        p.page.get_by_label("Password", exact=True).fill("pw")
        button(p, "Enter")
        idle(p.page)


def personal_sign_in(p, app):
    p.app, p.email = app, ""
    open_app(p, app)


def public_sign_in(p, app, email, password=PASSWORD, create=True):
    """A confirmed, invited account (made through the fake's test door), then
    signed in through the real sign-in form."""
    if create:
        app.post("/__user", {"email": email, "password": password})
    p.app, p.email = app, email          # (for onboard: whose settings)
    open_app(p, app)
    p.page.get_by_label("Email", exact=True).fill(email)
    p.page.get_by_label("Password", exact=True).fill(password)
    button(p, "Sign in")
    wait_text(p.page, "Get started", 15) or wait_text(p.page, "Today", 5)
    idle(p.page)


def sign_in(p, app, email="learner@example.com"):
    if app.mode == "personal":
        personal_sign_in(p, app)
    else:
        public_sign_in(p, app, email)


def admin_sign_in(p, app):
    public_sign_in(p, app, ADMIN)


# ---- setup ------------------------------------------------------------------
# the built-in subjects (people already learning them keep them; new learners
# aren't offered them): their names on the pages → their ids
SUBJECT_IDS = {"Philosophy": "philosophy", "Astronomy": "cosmos", "Stocks, Investing & Crypto": "investing",
               "Business Planning": "business", "Fashion & Clothing": "fashion", "Jewelry & Craft": "jewelry",
               "General Knowledge": "free"}
PACES = {"Light": 1, "Steady": 3, "Focused": 5}


def to_goal(p, identity="Working adult"):
    """From who she is (asked once) to what she wants to learn."""
    button(p, identity)
    button(p, "Get started")


def onboard(p, subjects=("Philosophy",), pace=None, reading=False):
    """Someone already learning these subjects: her settings, as a setup
    finished before (the setup itself no longer offers our subjects; it is
    walked through in test_setup.py and test_goals.py). Then the app, fresh."""
    p.app.seed_settings(p.email, {"subjects": [SUBJECT_IDS[s] for s in subjects],
                                  "units_per_day": PACES.get(pace, 3), "reading_enabled": bool(reading)})
    open_app(p, p.app)


def set_up_goal(p, goal="Read a company's financial statements", identity="Working adult", each=None):
    """The setup, as a new learner walks it: who she is, what she wants to
    learn (designed by the fake model), all of it, what it's for, Start
    learning. each(name): called on every step, before leaving it."""
    each = each or (lambda name: None)
    each("identity")
    to_goal(p, identity)
    each("want")
    p.page.get_by_label("In your own words").fill(goal)
    button(p, "Design my path")
    wait_text(p.page, "All of it, or some parts?", 40)
    tap(p, p.page.get_by_text("Yes, all of it", exact=True))
    idle(p.page)
    each("scope")
    button(p, "Continue")
    tap(p, p.page.locator('[class*="st-key-obp_pp_0"] button').first)       # (the first goal offered)
    idle(p.page)
    each("purpose")
    button(p, "Continue")
    wait_text(p.page, "Is this right?")
    each("confirm")
    button(p, "Start learning")
    idle(p.page, 30)


# the bar's short names, and the pages' full names in the Menu
FULL = {"Record": "Learning Record", "Goals": "Goals & Settings", "Reading": "Reading Plan"}


def go(p, app, name):
    """Top navigation by its label (on a phone, the pages that aren't in the
    bar are reached through the Menu, by their full names)."""
    loc = p.page.locator('.st-key-topnav [data-testid="stPageLink-NavLink"]', has_text=name).first
    if loc.count() and loc.is_visible():
        tap(p, loc)
        idle(p.page)
    else:
        menu(p, FULL.get(name, name))


def open_menu(p):
    """The Menu at the top: every part of GNOSIS, grouped."""
    tap(p, p.page.locator(".st-key-site_menu button").first)
    idle(p.page)
    assert wait_text(p.page, "Goals & Settings", 10), "the menu didn't open"


def menu(p, label):
    """A page by its name in the Menu."""
    open_menu(p)
    tap(p, p.page.get_by_role("link", name=label, exact=True).last)
    idle(p.page)


# ---- lessons and quizzes ----------------------------------------------------
def start_lesson(p):
    button(p, "Start this lesson", wait=False)
    assert wait_text(p.page, "Take the quiz", 40), "the lesson didn't finish"
    idle(p.page)


MEANINGS = {"Axis": "The line Earth spins around", "Rotation": "One spin a day", "Orbit": "One trip around the Sun",
            "Sunrise": "When the Sun comes into view"}
STEPS = {"1st": "Taipei turns toward the Sun", "2nd": "The Sun rises in Taipei", "3rd": "Taipei turns away: night falls"}


def take_quiz(p, correct=True, start="Take the quiz", before_submit=None):
    """Answer the (fake) quiz, every kind of question: all right, or all wrong."""
    page = p.page
    button(p, start, wait=False)
    assert wait_text(page, "Submit answers", 40), "the quiz didn't appear"
    idle(page)
    answer_all(p, correct)
    if before_submit:
        before_submit(page)
    button(p, "Submit answers", wait=False)
    assert wait_text(page, "Passed with" if correct else "You need 80%", 40), "the quiz result didn't show"
    idle(page)


def answer_all(p, correct=True, scope=None):
    """Answer every exercise on the page (or in `scope`) of the fake model's kinds."""
    page = p.page
    idle(page)                      # (the page settled first: a field filled mid-rerun is redrawn empty)
    root = scope or page
    groups = root.locator('[data-testid="stRadio"]')
    for g in range(groups.count()):
        group = groups.nth(g)
        target = group.get_by_text("It spins on its axis" if correct else "Solar flares", exact=True)
        if not target.count():          # a seeded lesson's question: "Right" is right
            target = group.get_by_text("Right", exact=True) if correct else group.locator("label").last
        tap(p, target)
        page.wait_for_timeout(120)
    boxes = root.locator('[data-testid="stSelectbox"]')
    labels = [boxes.nth(j).locator("label").inner_text().strip() for j in range(boxes.count())]
    for j, label in enumerate(labels):
        if label in STEPS:
            names = list(STEPS.values())
            k = list(STEPS).index(label)
            choose(p, boxes.nth(j), names[k] if correct else names[(k + 1) % len(names)])
        else:
            names = list(MEANINGS.values())
            k = list(MEANINGS).index(label)
            choose(p, boxes.nth(j), names[k] if correct else names[(k + 1) % len(names)])
    blanks = root.locator('input[placeholder="The missing word or phrase"]')
    for j in range(blanks.count()):
        blanks.nth(j).fill("axis" if correct else "banana")
        page.keyboard.press("Tab")
        page.wait_for_timeout(150)
    areas = root.locator('textarea[placeholder^="Answer in a sentence"], textarea[placeholder^="One real example"]')
    for j in range(areas.count()):
        areas.nth(j).fill("Because Earth spins on its axis." if correct else "No idea.")
        page.keyboard.press("Tab")
        page.wait_for_timeout(150)
    idle(page)


def choose(p, box, text):
    """Pick an option in a selectbox: by typing it on a computer (as a
    keyboard user would), by tapping the list on a touch screen."""
    page = p.page
    if p.width < TOUCH_W:
        opt = page.get_by_role("option", name=text, exact=True).first
        listbox = page.get_by_role("listbox")
        for attempt in range(4):        # (ISS-055: in the test browser's touch emulation a list can close
            # again at once; another tap opens it. Open on a real iPhone.) Never tapped while a list
            # is open: near the bottom of a phone screen the list opens over the box, and the tap
            # would pick whatever option lies there (then taken, and not offered where it belongs).
            if listbox.count() and listbox.first.is_visible():
                page.keyboard.press("Escape")
                page.wait_for_timeout(200)
            box.locator("input").first.tap()
            page.wait_for_timeout(300 + 300 * attempt)
            try:
                if opt.is_visible():
                    opt.tap(timeout=3000)
                    idle(page)
                    if box.locator("input").first.input_value() == text:      # it took: the box shows it
                        return
            except PlaywrightTimeout:   # it closed between seen and tapped: open it again
                pass
        page.keyboard.press("Escape")             # still closing on its own: choose it as a keyboard user would
        inp = box.locator("input").first
        inp.focus()
        page.keyboard.type(text)
        page.get_by_role("option", name=text, exact=True).first.wait_for(timeout=5000)
        page.keyboard.press("Enter")
    else:
        inp = box.locator("input").first
        inp.click()
        page.keyboard.type(text)
        page.get_by_role("option", name=text, exact=True).first.wait_for(timeout=5000)
        page.keyboard.press("Enter")          # the one option left, as a keyboard user picks it
    idle(page)
    shown = box.locator("input").first.input_value()
    assert shown == text, f"picked {text!r} but the box shows {shown!r}"


def pass_lesson(p):
    start_lesson(p)
    take_quiz(p, correct=True)


def open_panel(p, label):
    """Open an expander by its label (only if it's closed: a click toggles it)."""
    summary = p.page.locator("details > summary", has_text=label).first
    if summary.evaluate("s => !s.parentElement.open"):
        tap(p, summary)
        idle(p.page)
