"""Quiz quality (ISS-103): a keyed answer never goes against the lesson, no
two questions test the same point, no country-only fact unlabeled, and a
question she reported tells the lesson's next quiz what to avoid."""
import random
from datetime import date

from coach import curriculum, practice, quiz, review


def choice(question, right, options=("a", "b", "c")):
    return quiz.parse_items({"questions": [{"type": "choice", "question": question,
                                            "options": [right, *options], "answer": 0, "why": "w"}]},
                            random.Random(1))[0]


def test_the_writer_and_the_checker_are_told():
    for prompt in (quiz.SYSTEM, quiz.CHECKER):
        p = " ".join(prompt.split())
        assert "goes against a rule, number or definition the lesson gives" in p or "Never contradict the lesson" in p
        assert ("same point" in p or "different point" in p) and "only one country" in p


def test_two_questions_on_the_same_point_are_one():
    q1 = choice("Why do people invest money instead of only saving it?", "To help it grow over many years")
    q4 = choice("People invest instead of only saving money: why?", "Growth over the long run")
    q5 = choice("Why do people invest their money instead of saving all of it?", "To help it grow over many years")
    q6 = choice("What is an emergency fund for?", "To help it grow over many years")
    other = choice("Which account pays interest?", "A savings account")
    assert quiz.alike(q1, q4), "the same words, another order"
    assert quiz.alike(q1, q5), "much the same question, the same right answer"
    assert not quiz.alike(q1, q6), "another question that happens to share an answer: the checker's to judge"
    assert not quiz.alike(q1, other)
    explain = dict(q1, type="short")
    assert not quiz.alike(q1, explain) or quiz.same_as(q1) == quiz.same_as(explain), \
        "a choice and an explain-it question on one idea are two ways to test it"
    assert quiz.distinct([q1, q4, other]) == [q1, other]
    some = [choice(f"Question number {k} about topic {k}?", f"answer {k}") for k in range(quiz.QUESTIONS - 2)]
    assert quiz.assemble(some + [q1, q4, other]) is not None
    assert quiz.assemble(some + [q1, q4]) is None, "four plus one: a sixth is still needed"
    assert quiz.missing(some + [q1, q4]), "and asked for"


def test_a_reported_question_is_remembered_and_the_next_quiz_avoids_it():
    slot = {"n": 4, "title": "Investing versus saving", "lesson": "Money for 5+ years can be invested.", "quiz": None}
    review.drop_question(slot, "investing", "Q5: A house in 15 years: save or invest?")
    review.drop_question(slot, "investing", "Q5: A house in 15 years: save or invest?")
    assert slot["reported"] == ["Q5: A house in 15 years: save or invest?"], "once"
    kept = curriculum.parse_slots([dict(slot, completed=True)])[0]
    assert kept["reported"] == slot["reported"], "saved and read back"
    mine, stored = dict(kept), dict(kept, reported=["Another one?"])
    assert curriculum._extras(mine, stored)["reported"] == ["Another one?", slot["reported"][0]], "both copies kept"
    log = {"entries": [], "books": [], "paths": []}
    context = practice.quiz_context(log, "investing", kept, date(2026, 10, 13))
    _, messages = quiz.request(kept, context)
    assert "reported these questions" in messages[0]["content"] and "A house in 15 years" in messages[0]["content"]


def test_removing_a_goal_says_only_what_she_has():
    from coach import paths
    assert "lesson" not in paths.removal_note(0, 0) and "Nothing is deleted" in paths.removal_note(0, 0)
    assert "The lesson you passed stays" in paths.removal_note(1, 0)
    assert "The 3 lessons you passed stay" in paths.removal_note(3, 2) and "its 2 review cards stop" in paths.removal_note(3, 2)
    assert paths.removal_note(0, 1).startswith("It leaves your days and this list. Its review card stops")
