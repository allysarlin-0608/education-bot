"""The end-of-lesson quiz: parsing, shuffling, grading, the 90% bar."""
import random

from coach import curriculum, quiz, tokens


def model_reply(n=10, answer=0):
    return {"questions": [
        {"question": f"Q{k}?", "options": [f"right {k}", f"b{k}", f"c{k}", f"d{k}"], "answer": answer, "why": "Because."}
        for k in range(n)]}


def test_parse_keeps_the_right_answer_after_shuffling():
    questions = quiz.parse(model_reply(), rng=random.Random(3))
    assert len(questions) == quiz.QUESTIONS
    assert all(q["options"][q["answer"]].startswith("right") for q in questions)
    assert any(q["answer"] != 0 for q in questions)       # not always first any more


def test_parse_rejects_too_few_usable_questions():
    bad = model_reply(11)
    bad["questions"][0]["answer"] = 7                     # out of range
    bad["questions"][1]["options"] = ["a", "a", "b", "c"]  # duplicate options
    assert quiz.parse(bad) is None                        # only 9 usable
    assert quiz.parse(model_reply(12)) and len(quiz.parse(model_reply(12))) == 10
    assert quiz.parse({"nope": 1}) is None and quiz.parse(None) is None


def test_nine_of_ten_passes_eight_does_not():
    q = quiz.new(quiz.parse(model_reply(), rng=random.Random(1)))
    right = [item["answer"] for item in q["questions"]]
    wrong = lambda k: (right[k] + 1) % 4                  # noqa: E731
    assert quiz.grade(q, [wrong(0), wrong(1)] + right[2:]) == 80 and not quiz.passed(80)
    retake = quiz.new(q["questions"], q)
    assert retake["attempts"] == 1 and retake["best"] == 80 and retake["answers"] is None
    assert quiz.grade(retake, [wrong(0)] + right[1:]) == 90 and quiz.passed(90)
    assert retake["attempts"] == 2 and retake["best"] == 90


def test_saved_quiz_round_trips_and_junk_is_dropped():
    q = quiz.new(quiz.parse(model_reply()))
    quiz.grade(q, [0] * 10)
    assert quiz.parse_saved(q) == q
    assert quiz.parse_saved({"questions": [{"question": "x"}]}) is None
    slot = curriculum.parse_slots([{"n": 1, "quiz": q}])[0]
    assert slot["quiz"]["score"] == q["score"]


def test_a_long_lesson_quiz_fits_the_budget():
    slot = {"n": 7, "title": "A long lesson", "lesson": "word " * 1400}   # ~7000 characters
    system, messages = quiz.request(slot)
    assert tokens.estimate_request(system, messages, tokens.QUIZ_MAX_TOKENS) <= tokens.REQUEST_BUDGET
