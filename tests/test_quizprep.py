"""A lesson's quiz, prepared while she reads it (coach/quizprep.py, ISS-101):
started once per lesson and attempt, handed out once, waited for only for
what is left, never for a lesson without text, and the same checked quiz
"Take the quiz" would have written (one quiz's calls, not two)."""
import threading
import time
from datetime import timedelta

import pytest

import seed_history
from coach import llm, quizgen, quizprep, ui
from test_goal_pages import stored
from test_pages_smoke import app

SLOT = {"n": 3, "lesson": "A lesson about saving and investing.", "quiz": None}


@pytest.fixture
def on(monkeypatch):
    monkeypatch.setenv("GNOSIS_QUIZ_PREP", "1")
    quizprep._jobs.clear()
    yield
    quizprep._jobs.clear()


def test_started_once_handed_out_once(on, monkeypatch):
    gate, calls = threading.Event(), []

    def make(slot, where, step=None, context=None):
        calls.append(where)
        gate.wait(5)
        return ["q"], None
    monkeypatch.setattr(quizgen, "make", make)
    k = quizprep.key("s1", "investing", SLOT)
    assert quizprep.state(k) == "none" and quizprep.take(k, timeout=0) is None
    assert quizprep.start(k, SLOT, "investing lesson 3") and quizprep.start(k, SLOT, "again")
    assert quizprep.state(k) == "running" and quizprep.take(k, timeout=0.05) is None, "not finished: not handed out"
    gate.set()
    assert quizprep.take(k) == (["q"], None)
    assert calls == ["investing lesson 3"], "one job for one lesson and attempt"
    assert quizprep.state(k) == "none", "handed out once"


def test_each_session_lesson_and_attempt_is_its_own_job():
    k = quizprep.key("s1", "investing", SLOT)
    assert k != quizprep.key("s2", "investing", SLOT), "never another person's quiz"
    assert k != quizprep.key("s1", "investing", dict(SLOT, quiz={"id": "v2-abc"})), "a new set after a quiz not passed"
    assert k != quizprep.key("s1", "investing", dict(SLOT, lesson="Rewritten.")), "a rewritten lesson"


def test_nothing_prepared_when_off_or_without_a_lesson(monkeypatch):
    monkeypatch.setenv("GNOSIS_QUIZ_PREP", "0")
    assert not quizprep.start("k1", SLOT, "x")
    monkeypatch.setenv("GNOSIS_QUIZ_PREP", "1")
    assert not quizprep.start("k2", dict(SLOT, lesson=" "), "x")


def test_a_failure_while_preparing_is_only_a_missed_head_start(on, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("model down")
    monkeypatch.setattr(quizgen, "make", boom)
    quizprep.start("k3", SLOT, "x")
    questions, error = quizprep.take("k3")
    assert questions is None and error


def today_with_a_lesson_read():
    entries = seed_history.build(ui.today() + timedelta(days=1), days=1, topics=("philosophy",), partial=())
    e = entries[0]
    e["completed"] = False
    for s in e["lessons"]:
        s["completed"] = False
        s.pop("quiz", None)
    return entries


def test_take_the_quiz_uses_the_one_prepared_while_she_read(on, monkeypatch, tmp_path):
    # covers: S-gnosis_quiz_prep
    fresh = seed_history._quiz("x", 10)["questions"]
    made = []

    def make(slot, where, step=None, context=None):
        made.append(where)
        time.sleep(0.2)
        return fresh, None
    monkeypatch.setattr(quizgen, "make", make)
    monkeypatch.setattr(llm, "get_client", lambda: object())
    at = app(monkeypatch, tmp_path, subjects=("philosophy",), entries=today_with_a_lesson_read())
    assert not at.exception
    assert len(quizprep._jobs) == 1, "the quiz is being prepared while she reads"
    next(iter(quizprep._jobs.values())).done.wait(5)
    next(b for b in at.button if b.label == "Take the quiz").click().run()
    assert not at.exception
    _, log = stored(tmp_path)
    q = log["entries"][0]["lessons"][0]["quiz"]
    assert q and [x["question"] for x in q["questions"]] == [x["question"] for x in fresh]
    assert len(made) == 1, "the prepared quiz, not a second one"
