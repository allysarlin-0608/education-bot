"""Today's lesson, written while she does the warm-up (docs/LEARNING_DESIGN.md
§3 and §10: keep waits short).

Writing a lesson is one AI call of half a minute or so. On a day with a
warm-up, that call starts in the background the moment the warm-up is on
her screen, with exactly the instructions and message the page would send
itself (built on the page, then handed to the thread); when she finishes
the warm-up the lesson is usually waiting, and if not, the page waits only
for what is left. Nothing changes in what is asked or how many calls a
lesson takes: the call just happens earlier. A lesson prepared and never
opened is the only extra cost, and none is prepared when the AI can't be
used now (no key, the daily allowance). One job per (session, lesson),
kept in this process for JOB_TTL; the session's Streamlit context goes with
the thread, so the allowance is counted to her. Off with
GNOSIS_QUIZ_PREP=0, like the quiz's (the unit tests)."""
import hashlib
import logging
import threading
import time

from streamlit.runtime.scriptrunner import add_script_run_ctx

from coach import llm, quizprep, tokens

JOB_TTL = 3 * 3600
MAX_JOBS = 200

logger = logging.getLogger("coach.lessonprep")
_jobs = {}
_lock = threading.Lock()


class _Job:
    def __init__(self):
        self.started = time.monotonic()
        self.done = threading.Event()
        self.result = (None, None)


def key(session: str, topic: str, n: int, day: str) -> str:
    return hashlib.sha1("|".join([session, str(topic), str(n), day]).encode()).hexdigest()


def _forget_old() -> None:
    now = time.monotonic()
    for k in [k for k, j in _jobs.items() if now - j.started > JOB_TTL]:
        del _jobs[k]
    while len(_jobs) > MAX_JOBS:
        del _jobs[min(_jobs, key=lambda k: _jobs[k].started)]


def start(k: str, system: str, messages: list, where: str) -> bool:
    """Begin writing this lesson in the background, once."""
    if not quizprep.enabled():
        return False
    with _lock:
        _forget_old()
        if k in _jobs:
            return True
        job = _jobs[k] = _Job()

    def run():
        try:
            text = "".join(llm.stream_text(system, messages, tokens.LESSON_MAX_TOKENS))
            job.result = (text, None) if text.strip() else (None, llm.FAILED)
        except llm.CoachError as e:
            job.result = (None, str(e))
        except Exception as e:  # noqa: BLE001 - a failed head start: the page writes it itself
            logger.exception("writing the lesson for %s in the background failed", where)
            job.result = (None, str(e) or llm.FAILED)
        finally:
            logger.info("lesson for %s written in the background in %.1fs (%s)", where,
                        time.monotonic() - job.started, "ready" if job.result[0] else "not ready")
            job.done.set()

    thread = threading.Thread(target=run, name=f"lessonprep-{k[:8]}", daemon=True)
    add_script_run_ctx(thread, quizprep.background_ctx())       # (a rerun of her page can't stop it)
    thread.start()
    return True


def state(k: str) -> str:
    job = _jobs.get(k)
    return "none" if job is None else ("ready" if job.done.is_set() else "running")


def take(k: str, timeout: float = 90):
    """The written (text, error), waiting if it is still being written; None
    if nothing was prepared or it didn't finish in time. Handed out once."""
    job = _jobs.get(k)
    if job is None or not job.done.wait(timeout):
        return None
    with _lock:
        _jobs.pop(k, None)
    return job.result
