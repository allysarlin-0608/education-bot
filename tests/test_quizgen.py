"""Issue A: how a quiz is written when the model's reply isn't usable as it
comes (coach/quizgen.py): keep the good questions, ask only for the missing
ones, then for the whole quiz again; at most quiz.RECOVERIES extra calls."""
import json

import pytest

from coach import llm, quiz, quizgen
from test_quiz import model_reply

SLOT = {"n": 4, "title": "Orbits", "lesson": "A lesson about orbits."}
CLEAN = {"problems": []}


def short_by(k):
    """A full reply with k questions made unusable (a choice with no options)."""
    reply = model_reply()
    for j, item in enumerate(reply["questions"][:k]):
        item.clear()
        item.update(type="choice", question=f"Broken {j}?")
    return reply


def fill_of(n):
    return {"questions": [{"type": "choice", "question": f"Fill {j}?", "options": ["a", "b", "c", "d"], "answer": 2}
                          for j in range(n)]}


@pytest.fixture
def model(monkeypatch):
    """Scripted replies, by kind of request, in order; records what was asked."""
    script, asked = {}, []

    def ask(system, messages, max_tokens=900, salvage=None):
        kind = ("fill" if "replacement questions" in system else
                "quiz" if system.startswith("You write") else "check")
        asked.append(kind)
        reply = script[kind].pop(0)
        if isinstance(reply, str) and reply in (llm.BUSY, llm.FAILED, llm.LIMIT):
            return None, reply
        if isinstance(reply, str):                        # raw text: unreadable, maybe salvageable
            return (salvage(reply) if salvage else None), (None if salvage and salvage(reply) else llm.FAILED)
        return reply, None
    monkeypatch.setattr(llm, "ask_json", ask)
    return script, asked


def test_a_clean_quiz_is_two_calls(model):
    script, asked = model
    script.update(quiz=[model_reply()], check=[CLEAN])
    questions, error = quizgen.make(SLOT, "test")
    assert error is None and len(questions) == 10 and asked == ["quiz", "check"]


def test_one_bad_question_asks_for_just_that_one(model):
    script, asked = model
    script.update(quiz=[short_by(1)], fill=[fill_of(1)], check=[CLEAN])
    questions, error = quizgen.make(SLOT, "test")
    assert error is None and asked == ["quiz", "fill", "check"]
    assert "Fill 0?" in [q["question"] for q in questions]


def test_a_cut_off_reply_keeps_its_questions_and_fills_the_rest(model):
    script, asked = model
    text = json.dumps(model_reply())
    cut = text[:text.index('"type"', len(text) * 3 // 4) - 3]
    kept = len(quiz.parse_items(quiz.salvage(cut)))
    script.update(quiz=[cut], fill=[fill_of(10 - kept)], check=[CLEAN])
    questions, error = quizgen.make(SLOT, "test")
    assert error is None and asked == ["quiz", "fill", "check"], asked


def test_a_failed_fill_falls_back_to_the_whole_quiz(model):
    script, asked = model
    script.update(quiz=[short_by(2), model_reply()], fill=[{"questions": []}], check=[CLEAN])
    questions, error = quizgen.make(SLOT, "test")
    assert error is None and asked == ["quiz", "fill", "quiz", "check"]


def test_many_missing_asks_for_the_whole_quiz_at_once(model):
    script, asked = model
    script.update(quiz=[short_by(quiz.FILL_AT_MOST + 1), model_reply()], check=[CLEAN])
    questions, error = quizgen.make(SLOT, "test")
    assert error is None and asked == ["quiz", "quiz", "check"]


def test_it_gives_up_after_the_allowed_extra_calls(model):
    script, asked = model
    script.update(quiz=["junk", "junk", "junk"], check=[CLEAN])
    questions, error = quizgen.make(SLOT, "test")
    assert questions is None and error == llm.FAILED
    assert asked == ["quiz"] * (1 + quiz.RECOVERIES)


@pytest.mark.parametrize("stop", [llm.BUSY, llm.LIMIT])
def test_busy_or_the_daily_limit_ends_it_at_once(model, stop):
    script, asked = model
    script.update(quiz=[stop])
    assert quizgen.make(SLOT, "test") == (None, stop) and asked == ["quiz"]


def test_a_flagged_question_is_rewritten_and_checked_again(model):
    script, asked = model
    script.update(quiz=[model_reply()], fill=[fill_of(1)], check=[{"problems": [{"id": 0, "issue": "x"}]}, CLEAN])
    questions, error = quizgen.make(SLOT, "test")
    assert error is None and asked == ["quiz", "check", "fill", "check"]
