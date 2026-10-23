"""A lesson's quiz, prepared while she reads it (ISS-101).

Writing a quiz and checking every answer takes several AI calls, one after
the other (coach/quizgen.py), and the per-minute token allowance often
makes the first wait for the lesson's own call to age out: up to a minute
or more after "Take the quiz". So the same work starts in the background as
soon as the lesson is on her screen (and again after a quiz she didn't
pass, for the new set she will ask for). When she presses "Take the quiz"
the checked questions are usually waiting; if not, the page waits only for
what is left.

Nothing changes in what is asked of the model, how it is checked, or how
many calls a quiz takes: the calls just happen earlier. A quiz prepared and
never taken is the only extra cost (a lesson opened and left without its
quiz), and none is prepared when the AI can't be used now (no key, the
daily allowance). One job per (session, lesson, attempt), kept in this
process for JOB_TTL; the session's own Streamlit context goes with the
thread, so the allowance is counted to her as before. Off with
GNOSIS_QUIZ_PREP=0 (the unit tests: no background calls)."""
import copy
import dataclasses
import hashlib
import logging
import os
import threading
import time

from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx

from coach import quizgen

JOB_TTL = 3 * 3600          # seconds a prepared quiz is kept for
MAX_JOBS = 200              # in this process, all sessions (the oldest go first)

logger = logging.getLogger("coach.quizprep")
_jobs = {}
_lock = threading.Lock()


class _Job:
    def __init__(self):
        self.started = time.monotonic()
        self.done = threading.Event()
        self.result = (None, None)


def enabled() -> bool:
    return os.environ.get("GNOSIS_QUIZ_PREP", "1") != "0"


def key(session: str, topic: str, slot: dict) -> str:
    """The job for this session, this lesson as written now, and this attempt
    (a new set after a quiz she didn't pass is a new job)."""
    q = slot.get("quiz") or {}
    raw = "|".join([session, str(topic), str(slot.get("n")), str(q.get("id") or ""),
                    hashlib.sha1((slot.get("lesson") or "").encode()).hexdigest()])
    return hashlib.sha1(raw.encode()).hexdigest()


def background_ctx():
    """Her session's context for a background thread: her allowance and her
    store, as before, but one that a rerun of her page can't stop. (The
    page's own context raises Streamlit's stop signal in any thread that
    reads her session while the page is being rerun: a lesson or quiz
    written in the background was lost when she clicked meanwhile.) It reads
    and writes the same session state, under the same lock."""
    ctx = get_script_run_ctx()
    if ctx is None:
        return None
    from streamlit.runtime.state.safe_session_state import SafeSessionState
    state = SafeSessionState(ctx.session_state._state, lambda: None)
    object.__setattr__(state, "_lock", ctx.session_state._lock)
    return dataclasses.replace(ctx, session_state=state)


def session_id() -> str:
    ctx = get_script_run_ctx()
    return ctx.session_id if ctx is not None else ""


def _forget_old() -> None:
    now = time.monotonic()
    for k in [k for k, j in _jobs.items() if now - j.started > JOB_TTL]:
        del _jobs[k]
    while len(_jobs) > MAX_JOBS:
        del _jobs[min(_jobs, key=lambda k: _jobs[k].started)]


def start(k: str, slot: dict, where: str, context=None) -> bool:
    """Begin preparing this quiz in the background, once. True if a job runs
    (or ran) for it."""
    if not enabled() or not (slot.get("lesson") or "").strip():
        return False
    with _lock:
        _forget_old()
        if k in _jobs:
            return True
        job = _jobs[k] = _Job()
    lesson = copy.deepcopy(slot)

    def run():
        try:
            job.result = quizgen.make(lesson, where, context=context)
        except Exception as e:  # noqa: BLE001 - a failed preparation is only a missed head start
            logger.exception("preparing the quiz for %s failed", where)
            job.result = (None, str(e) or "failed")
        finally:
            logger.info("quiz for %s prepared in the background in %.1fs (%s)", where,
                        time.monotonic() - job.started, "ready" if job.result[0] else "not ready")
            job.done.set()

    thread = threading.Thread(target=run, name=f"quizprep-{k[:8]}", daemon=True)
    add_script_run_ctx(thread, background_ctx())            # her session: her allowance, her store
    thread.start()
    return True


def state(k: str) -> str:
    """"none" (never started), "running" or "ready"."""
    job = _jobs.get(k)
    return "none" if job is None else ("ready" if job.done.is_set() else "running")


def take(k: str, timeout: float = 180):
    """The prepared (questions, error), waiting for it if it is still being
    written (None: nothing was prepared, or it didn't finish in time). A
    prepared quiz is handed out once."""
    job = _jobs.get(k)
    if job is None or not job.done.wait(timeout):
        return None
    with _lock:
        _jobs.pop(k, None)
    return job.result
