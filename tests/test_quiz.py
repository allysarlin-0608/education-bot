"""The mastery check and its guided practice (docs/LEARNING_DESIGN.md §3): the
kinds, parsing, marking, the 80% bar; quizzes from before still load and mark."""
import random

from coach import core, curriculum, quiz, tokens


def model_reply(choice=1, match=1, short=0, scenario=1, blank=1, order=1, apply=0, spot=1, steps=1, problem=1):
    qs = [{"role": "check", "type": "choice", "question": f"C{k}?", "options": [f"right {k}", f"b{k}", f"c{k}", f"d{k}"],
           "answer": 0, "notes": ["", f"nb{k}", f"nc{k}", f"nd{k}"], "why": "Because.", "diff": 1,
           "hint": f"Think of {k}."} for k in range(choice)]
    qs += [{"type": "scenario", "scenario": f"A situation {k}.", "question": f"S{k}?",
            "options": [f"sright {k}", f"sb{k}", f"sc{k}", f"sd{k}"], "answer": 0, "why": ".", "diff": 3} for k in range(scenario)]
    qs += [{"type": "blank", "question": f"The ____ of thing {k}.", "answer": f"heart{k}", "accept": [f"core{k}"],
            "why": ".", "diff": 1} for k in range(blank)]
    qs += [{"type": "order", "question": f"Order {k}.", "steps": ["first", "second", "third", "fourth"], "why": ".",
            "diff": 2} for k in range(order)]
    qs += [{"type": "match", "question": "Match them.", "pairs": [[f"t{j}", f"m{j}"] for j in range(4)],
            "why": "."} for _ in range(match)]
    qs += [{"type": "spot", "question": f"Which line is wrong {k}?", "lines": ["1. two plus two", "2. is five", "3. so four"],
            "answer": 1, "fix": "is four", "why": ".", "diff": 3} for k in range(spot)]
    qs += [{"type": "short", "question": f"Why {k}?", "answer": f"Model {k}.", "why": "."} for k in range(short)]
    qs += [{"type": "apply", "question": f"Use it {k}?", "answer": f"Criteria {k}.", "why": "."} for k in range(apply)]
    qs += [{"role": "practice", "type": "steps", "question": f"Work it out {k}.",
            "steps": ["Start with 3 apples", "Add 2 more: ____ apples", "So the total is five"], "answers": ["5"],
            "accept": [["five"]], "why": ".", "hint": "Count on from 3."} for k in range(steps)]
    qs += [{"role": "practice", "type": "problem", "question": f"Your turn {k}?",
            "options": [f"pright {k}", f"pb{k}", f"pc{k}", f"pd{k}"], "answer": 0,
            "notes": ["", "x", "y", "z"], "why": ".", "hint": "Look again."} for k in range(problem)]
    random.Random(0).shuffle(qs)
    return {"questions": qs}


OLD = dict(choice=7, match=1, short=2, scenario=0, blank=0, order=0, apply=0, spot=0, steps=0, problem=0)  # before Phase 3


def right_answers(q):
    out = []
    for item in q["questions"]:
        out.append({"choice": lambda: item["answer"], "scenario": lambda: item["answer"],
                    "problem": lambda: item["answer"], "spot": lambda: item["answer"],
                    "match": lambda: list(item["key"]), "order": lambda: list(item["key"]),
                    "blank": lambda: item["answer"].upper() + "!",
                    "steps": lambda: list(item["answers"]),
                    "short": lambda: "My answer.", "apply": lambda: "My example."}[item["type"]]())
    return out


def test_parse_mixes_and_orders_the_kinds():
    questions = quiz.parse(model_reply(), rng=random.Random(3))
    assert [q["type"] for q in questions] == ["choice", "scenario", "blank", "order", "match", "spot"]
    assert all(q["options"][q["answer"]].startswith("right") for q in questions if q["type"] == "choice")
    assert all(q["notes"][q["answer"]] == "" for q in questions if q["type"] == "choice")   # notes follow the shuffle
    assert questions[1]["scenario"].startswith("A situation")
    order = questions[3]
    assert [order["items"][k] for k in order["key"]] == ["first", "second", "third", "fourth"]
    assert order["items"] != ["first", "second", "third", "fourth"]                 # never shown in order
    match = questions[4]
    assert [match["right"][k] for k in match["key"]] == ["m0", "m1", "m2", "m3"]   # key survives shuffling
    spot = questions[5]
    assert spot["lines"] == ["two plus two", "is five", "so four"] and spot["answer"] == 1   # numbers taken off
    assert questions[0]["diff"] == 1 and questions[0]["hint"] == "Think of 0." and questions[1]["diff"] == 3
    assert not any(q.get("role") for q in questions)
    practice = quiz.practice_of(quiz.parse_items(model_reply(), rng=random.Random(3)))
    assert [q["type"] for q in practice] == ["steps", "problem"] and all(q["role"] == "practice" for q in practice)
    assert practice[0]["answers"] == ["5"] and practice[0]["accept"] == [["five"]]
    old = quiz.parse(model_reply(**OLD), rng=random.Random(3))                      # the old mix still makes a check
    assert len(old) == quiz.QUESTIONS and sum(q["type"] in quiz.WRITTEN for q in old) <= 2


def test_parse_rejects_junk_and_short_sets():
    bad = model_reply()
    for item in bad["questions"]:
        if item["type"] == "match":
            item["pairs"] = [["a", "x"], ["a", "y"], ["b", "z"], ["c", "w"]]      # duplicate term
    assert quiz.parse(bad) is None                                             # only 5 usable for the check
    assert quiz.parse({"questions": [{"type": "essay", "question": "?"}] * 12}) is None
    assert quiz.parse({"nope": 1}) is None and quiz.parse(None) is None
    legacy = {"questions": [{"question": f"Q{k}", "options": ["a", "b", "c", "d"], "answer": 1} for k in range(10)]}
    assert len(quiz.parse(legacy)) == quiz.QUESTIONS                          # no "type": multiple choice
    two_wrong = {"type": "spot", "question": "?", "lines": ["a", "b"], "answer": 0, "fix": "x"}        # too short
    no_gap = {"type": "steps", "question": "?", "steps": ["a", "b", "c"], "answers": ["x"]}
    three_gaps = {"type": "steps", "question": "?", "steps": ["____", "____", "____"], "answers": ["x", "y", "z"]}
    for junk in (two_wrong, no_gap, three_gaps):
        assert quiz.parse_items({"questions": [junk]}) == [], junk


def test_old_quizzes_mark_short_answers_by_the_model():
    q = quiz.new(quiz.parse_items(model_reply(**OLD), rng=random.Random(1)))      # ten, as quizzes were
    answers = right_answers(q)
    written = [k for k, item in enumerate(q["questions"]) if item["type"] in quiz.WRITTEN]
    assert quiz.submit(q, answers) is True and quiz.needs_grading(q)
    system, messages = quiz.grading_request(q)
    assert f"id {written[0]}" in messages[0]["content"] and "Her answer: My answer." in messages[0]["content"]
    assert "specifically what is wrong" in system                                   # wrong answers get a reason
    assert not quiz.apply_grading(q, {"results": [{"id": written[0], "correct": True}]})   # one missing
    ok = quiz.apply_grading(q, {"results": [{"id": written[0], "correct": True, "feedback": "Good."},
                                            {"id": written[1], "correct": False, "feedback": "It misses the tilt."}]})
    assert ok and not quiz.needs_grading(q) and q["feedback"][written[1]] == "It misses the tilt."
    assert quiz.finish(q) == 90 and quiz.passed(90) and quiz.points(q) == "9 of 10"


def test_new_checks_need_no_marking_call_and_part_marks_count():
    q = quiz.new(quiz.parse(model_reply(), rng=random.Random(1)))
    answers = right_answers(q)
    match = next(k for k, item in enumerate(q["questions"]) if item["type"] == "match")
    answers[match] = [answers[match][1], answers[match][0]] + answers[match][2:]   # two pairs swapped
    assert quiz.submit(q, answers) is False                                          # nothing for the model
    assert quiz.finish(q) == 92 and quiz.points(q) == "5.5 of 6"


def test_eighty_percent_passes_and_retakes_carry_the_best():
    q = quiz.new(quiz.parse(model_reply(), rng=random.Random(2)))
    answers = right_answers(q)
    wrong = lambda k: (answers[k] + 1) % len(q["questions"][k].get("options") or q["questions"][k]["lines"])   # noqa: E731
    one_off = [wrong(k) if k in (0, 1) else a for k, a in enumerate(answers)]          # choice and scenario wrong
    assert quiz.submit(q, one_off) is False
    assert quiz.finish(q) == 67 and not quiz.passed(67)
    retake = quiz.new(q["questions"], q)
    assert retake["attempts"] == 1 and retake["best"] == 67 and retake["answers"] is None
    quiz.submit(retake, [wrong(0)] + answers[1:])
    assert quiz.finish(retake) == 83 and quiz.passed(83) and retake["best"] == 83
    assert quiz.PASS_MARK == 80 and sum(quiz.MIX.values()) == quiz.QUESTIONS


def test_answered_checks_every_kind():
    items = quiz.parse_items(model_reply(short=1), rng=random.Random(4))
    by = {q["type"]: q for q in items}
    assert not quiz.answered(by["choice"], None) and quiz.answered(by["choice"], 0)
    assert not quiz.answered(by["match"], [0, None, 1, 2]) and quiz.answered(by["match"], [0, 1, 2, 3])
    assert not quiz.answered(by["short"], "   ") and quiz.answered(by["short"], "Because of the tilt.")
    assert not quiz.answered(by["spot"], None) and quiz.answered(by["spot"], 2)
    assert not quiz.answered(by["steps"], [""]) and quiz.answered(by["steps"], ["5"])
    assert quiz.blank_answer(by["steps"]) == [""]


def test_a_worked_problem_marks_each_gap_and_says_which_was_wrong():
    steps = quiz.parse_items({"questions": [{"type": "steps", "question": "3 + 2 + 4?",
                                             "steps": ["3 + 2 = ____", "Then 5 + 4 = ____", "So 9"],
                                             "answers": ["5", "9"], "accept": [["five"], ["nine"]]}]})[0]
    assert quiz.mark(steps, ["five", "9"]) == 1.0
    assert quiz.mark(steps, ["5", "8"]) == 0.5
    assert "Gap 2" in quiz.mistake(steps, ["5", "8"]) and "“9”" in quiz.mistake(steps, ["5", "8"])
    spot = quiz.parse_items({"questions": [{"type": "spot", "question": "Where?", "lines": ["a", "b", "c"],
                                            "answer": 2, "fix": "it should be d"}]})[0]
    assert quiz.mark(spot, 2) == 1.0 and quiz.mark(spot, 0) == 0.0
    assert "line 3" in quiz.mistake(spot, 0) and "it should be d" in quiz.mistake(spot, 0)


def test_saved_quiz_round_trips_and_old_quizzes_still_load():
    q = quiz.new(quiz.parse(model_reply(), rng=random.Random(5)))
    quiz.submit(q, right_answers(q))
    q["conf"] = [3, 2, 1, None, 3, 3]
    assert quiz.parse_saved(q) == q
    practice = quiz.practice_of(quiz.parse_items(model_reply()))
    assert [quiz._saved_question(x) for x in practice] == practice
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
    q = quiz.new(quiz.parse_items(model_reply(**dict(OLD, choice=0, match=0, short=10))))     # the worst case (old)
    quiz.submit(q, ["An answer of a few sentences. " * 12] * 10)
    system, messages = quiz.grading_request(q)
    assert tokens.estimate_request(system, messages, tokens.JSON_MAX_TOKENS) <= tokens.REQUEST_BUDGET


def test_lessons_saved_with_the_old_closing_line_still_parse():
    for closing in ("Tick it off when you're done — consistency beats perfection.", core.CLOSING_LINE):
        assert core.extract_section(f"【Note】 Keep going.\n\n{closing}", "Note") == "Keep going."


def test_the_checker_sees_every_keyed_answer_and_flags_are_rewritten():
    questions = quiz.parse(model_reply(), rng=random.Random(6)) + quiz.practice_of(quiz.parse_items(model_reply()))
    gold = {"type": "choice", "question": "Why does metal purity affect durability?",
            "options": ["Higher purity metals are more resistant to wear", "Pure gold is soft; alloys are harder",
                        "Purity has no effect", "Only colour changes"], "answer": 0, "why": "."}
    questions[0] = quiz.parse_items({"questions": [gold]}, rng=random.Random(0))[0]
    system, messages = quiz.check_request(questions)
    text = messages[0]["content"]
    assert "ONLY\n  defensible" in system and "most\n  common" in system
    assert "* Higher purity metals are more resistant to wear" in text          # the keyed answer is marked
    assert "id 4 (match)" in text and "id 5 (spot)" in text and "* line 2: is five" in text
    assert "id 6 (steps)" in text and "(gap: 5)" in text and "hint: Count on from 3." in text
    assert "gives the answer away" in system
    assert quiz.problems({"problems": []}, 8) == {}
    assert quiz.problems({"problems": [{"id": 0, "issue": "Pure gold is soft."}, {"id": 99}]}, 8) == {0: "Pure gold is soft."}
    assert quiz.problems({"nope": 1}, 8) is None
    flagged = {0: "Pure gold is soft; the keyed answer is wrong.", 5: "Two lines are wrong."}
    system, messages = quiz.rewrite_request({"n": 3, "title": "Gold", "lesson": "Gold lesson."}, questions, flagged)
    assert 'Write exactly 2 replacement questions (1 "choice", 1 "spot")' in system
    assert "Pure gold is soft; the keyed answer is wrong." in messages[0]["content"]
    fresh = quiz.parse_items({"questions": [
        {"type": "spot", "question": "Which line?", "lines": ["x", "y", "z"], "answer": 0, "fix": "w"},
        {"type": "choice", "question": "Which is harder?", "options": ["18K gold", "24K gold", "Lead", "Tin"], "answer": 0}]})
    fixed = quiz.replace(questions, flagged, fresh)
    assert fixed[0]["question"] == "Which is harder?" and fixed[5]["question"] == "Which line?"
    assert fixed[1:5] == questions[1:5] and fixed[6:] == questions[6:]
    assert quiz.replace(questions, flagged, fresh[:1]) is None                 # a kind is missing


def test_prompt_demands_correct_unique_answers():
    for rule in ("factually correct in the real world", "only correct option", "don't ask",
                 "No two options may both be defensible", "true answer must be\n  among the options"):
        assert rule in quiz.SYSTEM, rule


def test_small_slips_are_repaired_not_thrown_away():
    """Issue A (A3): the repairs that keep a question instead of failing the quiz."""
    rng = random.Random(1)
    lettered = {"type": "choice", "question": "Which?", "options": ["A) Gold", "B) Lead", "C) Tin", "D) Iron"], "answer": "A"}
    q = quiz.parse_items({"questions": [lettered]}, rng)[0]
    assert sorted(q["options"]) == ["Gold", "Iron", "Lead", "Tin"] and q["options"][q["answer"]] == "Gold"
    by_text = {"type": "choice", "question": "Which?", "options": ["Gold", "Lead", "Tin", "Iron"], "answer": "lead"}
    q = quiz.parse_items({"questions": [by_text]}, rng)[0]
    assert q["options"][q["answer"]] == "Lead"
    five = {"type": "choice", "question": "Which?", "options": ["Gold", "Lead", "Tin", "Iron", "Zinc"], "answer": 4}
    q = quiz.parse_items({"questions": [five]}, rng)[0]
    assert len(q["options"]) == 4 and q["options"][q["answer"]] == "Zinc"
    repeated = {"type": "choice", "question": "Which?", "options": ["Gold", "Lead", "lead", "Tin", "Iron"], "answer": 0}
    q = quiz.parse_items({"questions": [repeated]}, rng)[0]
    assert sorted(q["options"]) == ["Gold", "Iron", "Lead", "Tin"]
    pairs = {"type": "matching", "question": "Match.", "pairs": [{"term": f"t{j}", "meaning": f"m{j}"} for j in range(5)]}
    q = quiz.parse_items({"questions": [pairs]}, rng)[0]
    assert q["type"] == "match" and q["left"] == ["t0", "t1", "t2", "t3"]
    assert quiz.parse_items({"questions": [{"type": "short_answer", "question": "Why?", "model_answer": "Because."}]})[0]["type"] == "short"
    # still refused: what can't be repaired without guessing
    for bad in ({"type": "choice", "question": "Q", "options": ["a", "b", "c"], "answer": 0},            # 3 options
                {"type": "choice", "question": "Q", "options": ["a", "b", "c", "d"], "answer": 7},       # no such answer
                {"type": "choice", "question": "Q", "options": ["a", "A", "b", "c", "d"], "answer": 0},  # answer twice
                {"type": "choice", "question": "Q", "options": ["a", "b", "c", "d"], "answer": "e"}):
        assert quiz.parse_items({"questions": [bad]}) == [], bad


def test_a_quiz_short_of_questions_asks_only_for_what_is_missing():
    """Issue A (A2): keep the usable questions, ask for the missing kinds only."""
    reply = model_reply()
    broken = [k for k, item in enumerate(reply["questions"]) if item["type"] in ("spot", "choice")][:2]
    kinds = sorted(reply["questions"][k]["type"] for k in broken)
    for k in broken:
        reply["questions"][k]["options" if reply["questions"][k]["type"] == "choice" else "lines"] = []
    usable = quiz.parse_items(reply)
    assert len(usable) == 6 and quiz.assemble(usable) is None              # (four for the check, two practice)
    assert sorted(quiz.missing(usable)) == kinds
    system, messages = quiz.fill_request({"n": 2, "title": "Orbits", "lesson": "Lesson text."}, usable)
    assert "Write exactly 2 replacement questions" in system and "Lesson text." in messages[0]["content"]
    assert all(q["question"] in messages[0]["content"] for q in usable)       # don't repeat these
    fresh = [{"type": "choice", "question": "New C?", "options": ["w", "x", "y", "z"], "answer": 1},
             {"type": "spot", "question": "New S?", "lines": ["p", "q", "r"], "answer": 1, "fix": "s"}]
    done = quiz.assemble(usable + quiz.parse_items({"questions": fresh}))
    assert [q["type"] for q in done] == [q["type"] for q in quiz.parse(model_reply())]
    # a question repeated by the model counts once
    assert quiz.assemble(usable + usable) is None
    assert quiz.missing(quiz.parse(model_reply())) == []
    # never more than two answers for the model to mark, however many it wrote
    many = quiz.assemble(quiz.parse_items(model_reply(short=6, apply=3, choice=6)))
    assert sum(q["type"] in quiz.WRITTEN for q in many) <= 2


def test_a_reply_cut_off_keeps_its_complete_questions():
    """Issue A: a quiz cut off at the reply limit isn't thrown away whole."""
    import json
    text = json.dumps(model_reply())
    cut = text[:text.index('"type"', len(text) // 2) - 3]          # mid-list, inside nothing
    assert quiz.salvage(cut + ', {"type": "choice", "question": "Half {a} \\"b\\" [c')["questions"]
    kept = quiz.parse_items(quiz.salvage(cut))
    assert 0 < len(kept) < len(model_reply()["questions"])
    assert quiz.salvage("no json at all") is None and quiz.salvage('{"questions": [') is None
    tricky = '{"questions": [{"type": "short", "question": "Is } a brace? \\"yes\\"", "answer": "Yes {"}, {"ty'
    assert quiz.salvage(tricky)["questions"][0]["answer"] == "Yes {"
