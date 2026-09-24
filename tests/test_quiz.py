"""The end-of-lesson quiz: three kinds of question, parsing, marking, the 90% bar."""
import random

from coach import core, curriculum, quiz, tokens


def model_reply(choice=7, match=1, short=2):
    qs = [{"type": "choice", "question": f"C{k}?", "options": [f"right {k}", f"b{k}", f"c{k}", f"d{k}"],
           "answer": 0, "why": "Because."} for k in range(choice)]
    qs += [{"type": "match", "question": "Match them.", "pairs": [[f"t{j}", f"m{j}"] for j in range(4)],
            "why": "."} for _ in range(match)]
    qs += [{"type": "short", "question": f"Why {k}?", "answer": f"Model {k}.", "why": "."} for k in range(short)]
    random.Random(0).shuffle(qs)
    return {"questions": qs}


def right_answers(q):
    out = []
    for item in q["questions"]:
        out.append({"choice": lambda: item["answer"], "match": lambda: list(item["key"]),
                    "short": lambda: "My answer."}[item["type"]]())
    return out


def test_parse_mixes_and_orders_the_kinds():
    questions = quiz.parse(model_reply(), rng=random.Random(3))
    assert [q["type"] for q in questions] == ["choice"] * 7 + ["match"] + ["short"] * 2
    assert all(q["options"][q["answer"]].startswith("right") for q in questions if q["type"] == "choice")
    match = questions[7]
    assert [match["right"][k] for k in match["key"]] == ["m0", "m1", "m2", "m3"]   # key survives shuffling


def test_parse_rejects_junk_and_short_sets():
    bad = model_reply()
    for item in bad["questions"]:
        if item["type"] == "match":
            item["pairs"] = [["a", "x"], ["a", "y"], ["b", "z"], ["c", "w"]]      # duplicate term
    assert quiz.parse(bad) is None                                             # only 9 usable
    assert quiz.parse({"questions": [{"type": "essay", "question": "?"}] * 12}) is None
    assert quiz.parse({"nope": 1}) is None and quiz.parse(None) is None
    legacy = {"questions": [{"question": f"Q{k}", "options": ["a", "b", "c", "d"], "answer": 1} for k in range(10)]}
    assert len(quiz.parse(legacy)) == 10                                       # no "type": multiple choice


def test_marking_matching_partially_and_short_answers_by_the_model():
    q = quiz.new(quiz.parse(model_reply(), rng=random.Random(1)))
    answers = right_answers(q)
    answers[7] = [answers[7][1], answers[7][0]] + answers[7][2:]               # two pairs swapped
    assert quiz.submit(q, answers) is True and quiz.needs_grading(q)
    system, messages = quiz.grading_request(q)
    assert "id 8" in messages[0]["content"] and "Her answer: My answer." in messages[0]["content"]
    assert "say specifically why" in system                                   # wrong answers get a reason
    assert not quiz.apply_grading(q, {"results": [{"id": 8, "correct": True}]})   # id 9 missing
    ok = quiz.apply_grading(q, {"results": [{"id": 8, "correct": True, "feedback": "Good."},
                                            {"id": 9, "correct": False, "feedback": "It misses the tilt."}]})
    assert ok and not quiz.needs_grading(q) and q["feedback"][9] == "It misses the tilt."
    assert quiz.finish(q) == 85 and quiz.passed(85) and quiz.points(q) == "8.5 of 10"


def test_eight_points_pass_seven_do_not_and_retakes_carry_the_best():
    q = quiz.new(quiz.parse(model_reply(short=0, choice=9), rng=random.Random(2)))
    answers = right_answers(q)
    wrong = lambda a: (a + 1) % 4                                               # noqa: E731
    first = [wrong(a) for a in answers[:3]] + answers[3:]
    assert quiz.submit(q, first) is False                                      # nothing for the model
    assert quiz.finish(q) == 70 and not quiz.passed(70)
    retake = quiz.new(q["questions"], q)
    assert retake["attempts"] == 1 and retake["best"] == 70 and retake["answers"] is None
    quiz.submit(retake, [wrong(answers[0]), wrong(answers[1])] + answers[2:])
    assert quiz.finish(retake) == 80 and quiz.passed(80) and retake["best"] == 80
    assert quiz.PASS_MARK == 80 and quiz.MIX == {"choice": 7, "match": 1, "short": 2}


def test_answered_checks_every_kind():
    questions = quiz.parse(model_reply(), rng=random.Random(4))
    choice, match, short = questions[0], questions[7], questions[8]
    assert not quiz.answered(choice, None) and quiz.answered(choice, 0)
    assert not quiz.answered(match, [0, None, 1, 2]) and quiz.answered(match, [0, 1, 2, 3])
    assert not quiz.answered(short, "   ") and quiz.answered(short, "Because of the tilt.")


def test_saved_quiz_round_trips_and_old_quizzes_still_load():
    q = quiz.new(quiz.parse(model_reply(), rng=random.Random(5)))
    quiz.submit(q, right_answers(q))
    assert quiz.parse_saved(q) == q
    assert curriculum.parse_slots([{"n": 1, "quiz": q}])[0]["quiz"]["marks"] == q["marks"]
    old = {"id": "abc", "questions": [{"question": f"Q{k}", "options": ["a", "b", "c", "d"], "answer": 0,
                                       "why": ""} for k in range(10)],
           "answers": [0] * 9 + [1], "score": 90, "attempts": 1, "best": 90}      # saved before kinds
    loaded = quiz.parse_saved(old)
    assert loaded["questions"][0]["type"] == "choice" and loaded["marks"] == [1.0] * 9 + [0.0]
    assert quiz.parse_saved({"questions": [{"question": "x"}]}) is None


def test_quiz_and_grading_requests_fit_the_budget():
    slot = {"n": 7, "title": "A long lesson", "lesson": "word " * 1400}    # ~7000 characters
    system, messages = quiz.request(slot)
    assert tokens.estimate_request(system, messages, tokens.QUIZ_MAX_TOKENS) <= tokens.REQUEST_BUDGET
    q = quiz.new(quiz.parse(model_reply(choice=0, match=0, short=10)))
    quiz.submit(q, ["An answer of a few sentences. " * 12] * 10)
    system, messages = quiz.grading_request(q)
    assert tokens.estimate_request(system, messages, tokens.JSON_MAX_TOKENS) <= tokens.REQUEST_BUDGET


def test_lessons_saved_with_the_old_closing_line_still_parse():
    for closing in ("Tick it off when you're done — consistency beats perfection.", core.CLOSING_LINE):
        assert core.extract_section(f"【Note】 Keep going.\n\n{closing}", "Note") == "Keep going."


def test_the_checker_sees_every_keyed_answer_and_flags_are_rewritten():
    questions = quiz.parse(model_reply(), rng=random.Random(6))
    gold = {"type": "choice", "question": "Why does metal purity affect durability?",
            "options": ["Higher purity metals are more resistant to wear", "Pure gold is soft; alloys are harder",
                        "Purity has no effect", "Only colour changes"], "answer": 0, "why": "."}
    questions[0] = quiz.parse_items({"questions": [gold]}, rng=random.Random(0))[0]
    system, messages = quiz.check_request(questions)
    text = messages[0]["content"]
    assert "ONLY defensible" in system and "most common" in system
    assert "* Higher purity metals are more resistant to wear" in text          # the keyed answer is marked
    assert "id 7 (match)" in text and "model answer:" in text
    assert quiz.problems({"problems": []}, 10) == {}
    assert quiz.problems({"problems": [{"id": 0, "issue": "Pure gold is soft."}, {"id": 99}]}, 10) == {0: "Pure gold is soft."}
    assert quiz.problems({"nope": 1}, 10) is None
    flagged = {0: "Pure gold is soft; the keyed answer is wrong.", 8: "Model answer is wrong."}
    system, messages = quiz.rewrite_request({"n": 3, "title": "Gold", "lesson": "Gold lesson."}, questions, flagged)
    assert 'Write exactly 2 replacement questions (1 "choice", 1 "short")' in system
    assert "Pure gold is soft; the keyed answer is wrong." in messages[0]["content"]
    fresh = quiz.parse_items({"questions": [
        {"type": "short", "question": "Why are gold alloys used in rings?", "answer": "Alloys are harder than pure gold."},
        {"type": "choice", "question": "Which is harder?", "options": ["18K gold", "24K gold", "Lead", "Tin"], "answer": 0}]})
    fixed = quiz.replace(questions, flagged, fresh)
    assert fixed[0]["question"] == "Which is harder?" and fixed[8]["question"].startswith("Why are gold alloys")
    assert fixed[1:8] == questions[1:8] and fixed[9] == questions[9]
    assert quiz.replace(questions, flagged, fresh[:1]) is None                 # a kind is missing


def test_prompt_demands_correct_unique_answers():
    for rule in ("factually correct in the real world", "only correct option", "don't ask",
                 "No two options may both be defensible", "true answer must be\n  among the options"):
        assert rule in quiz.SYSTEM, rule
