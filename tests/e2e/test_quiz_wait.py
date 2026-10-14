"""How long "Take the quiz" makes her wait (ISS-101), with a slow model:
every call takes DELAY seconds and the checker sends one question back to
be rewritten, so a quiz is four calls in a row (write, check, rewrite,
check), as in the 75-second report. Pressed the moment the lesson appears
(what every press cost before: nothing was prepared), and after reading it
(the quiz was prepared meanwhile). The two waits are kept in the timings."""
import time

import flows
from conftest import record_timing

DELAY = 8.0           # seconds per model call
READING = 45          # seconds she spends on the lesson


def text(p):
    return p.page.evaluate("document.body.innerText")


def one_learner(app, pages, read_for):
    p = pages(width=1440)
    flows.sign_in(p, app, email=f"wait{read_for}-{int(time.time() * 1000)}@example.com")
    flows.onboard(p, subjects=("Philosophy",))
    app.set_llm(delay=DELAY, quiz_flag_first=True)
    flows.button(p, "Start this lesson", wait=False)
    assert flows.wait_text(p.page, "Take the quiz", 90), "the lesson didn't finish"
    flows.idle(p.page)
    p.page.wait_for_timeout(read_for * 1000)
    t0 = time.monotonic()
    flows.button(p, "Take the quiz", wait=False)
    assert flows.wait_text(p.page, "Submit answers", 120), "the quiz didn't appear"
    waited = time.monotonic() - t0
    assert "Traceback" not in text(p)
    return waited


def test_the_quiz_is_ready_after_reading(public_app, pages):
    app = public_app
    app.set_llm()
    at_once = one_learner(app, pages, 0)
    app.set_llm()
    after_reading = one_learner(app, pages, READING)
    app.set_llm()
    record_timing("quiz wait, pressed at once", at_once, model_delay=DELAY)
    record_timing("quiz wait, after reading", after_reading, model_delay=DELAY, reading=READING)
    print(f"\nquiz wait: pressed at once {at_once:.1f}s, after {READING}s of reading {after_reading:.1f}s")
    assert at_once > 3 * DELAY, "the slow model was in play"
    assert after_reading < 3, f"after reading, the quiz should be there: {after_reading:.1f}s"
