"""What a person does in the app, as reusable steps for the tests."""
import time

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
    open_app(p, app)


def public_sign_in(p, app, email, password=PASSWORD, create=True):
    """A confirmed, invited account (made through the fake's test door), then
    signed in through the real sign-in form."""
    if create:
        app.post("/__user", {"email": email, "password": password})
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
def onboard(p, subjects=("Philosophy",), pace=None, reading=False):
    button(p, "Get started")
    for s in subjects:
        button(p, s)
    button(p, "Continue")                  # subjects
    if pace:
        button(p, pace)
    button(p, "Continue")                  # pace
    button(p, "Continue")                  # level
    if reading:
        p.page.locator('[data-testid="stToggle"] input, [role="switch"]').first.check(force=True)
        idle(p.page)
    button(p, "Continue")                  # reading
    button(p, "Start learning")
    idle(p.page, 30)


def go(p, app, name):
    """Top navigation by its label."""
    loc = p.page.locator('.st-key-topnav [data-testid="stPageLink-NavLink"]', has_text=name).first
    tap(p, loc)
    idle(p.page)


# ---- lessons and quizzes ----------------------------------------------------
def start_lesson(p):
    button(p, "Start this lesson", wait=False)
    assert wait_text(p.page, "Take the quiz", 40), "the lesson didn't finish"
    idle(p.page)


def take_quiz(p, correct=True, start="Take the quiz", before_submit=None):
    """Answer the (fake) quiz: all right, or all wrong."""
    page = p.page
    button(p, start, wait=False)
    assert wait_text(page, "Submit answers", 40), "the quiz didn't appear"
    idle(page)
    groups = page.locator('[data-testid="stRadio"]')
    for g in range(groups.count()):
        opt = "It spins on its axis" if correct else "Solar flares"
        tap(p, groups.nth(g).get_by_text(opt, exact=True))
        page.wait_for_timeout(120)
    rights = ["The line Earth spins around", "One spin a day", "One trip around the Sun", "When the Sun comes into view"]
    boxes = page.locator('[data-testid="stSelectbox"]')
    for j in range(boxes.count()):
        choose(p, boxes.nth(j), rights[j] if correct else rights[(j + 1) % 4])
    areas = page.locator('textarea[placeholder^="Answer in a sentence"]')
    for j in range(areas.count()):
        text = "Because Earth spins on its axis." if correct else "No idea."
        areas.nth(j).fill(text)
        page.keyboard.press("Tab")
        page.wait_for_timeout(150)
    idle(page)
    if before_submit:
        before_submit(page)
    button(p, "Submit answers", wait=False)
    assert wait_text(page, "Passed with" if correct else "You need 80%", 40), "the quiz result didn't show"
    idle(page)


def choose(p, box, text):
    """Pick an option in a selectbox: by typing it on a computer (as a
    keyboard user would), by tapping the list on a touch screen."""
    page = p.page
    if p.width < TOUCH_W:
        box.locator("input").first.tap()
        opt = page.get_by_role("option", name=text, exact=True).first
        opt.wait_for(timeout=5000)
        opt.tap()
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
