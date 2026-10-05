"""Phase 3's exercises and coaching rules: every kind of exercise marked
right, wrong, partly right, empty or nonsense, with the specific mistake;
the question on an earlier idea; practice that adapts without loops;
explaining it back; the tutor's grounding (coach/quiz.py, coach/practice.py)."""
import random
from datetime import date, timedelta

from coach import mastery, practice, prefs, quiz

D = date(2026, 11, 2)


def one(item):
    return quiz.parse_items({"questions": [item]}, random.Random(1))[0]


BLANK = one({"type": "blank", "question": "Stoics say we control only our ____.", "answer": "judgements",
             "accept": ["judgments", "opinions"], "why": "Epictetus: what's up to us is our judgement."})
ORDER = one({"type": "order", "question": "Order the Socratic method.",
             "steps": ["Ask for a definition", "Find a counterexample", "Refine the definition"], "why": "."})
MATCH = one({"type": "match", "pairs": [["Ad hominem", "attacks the person"], ["Straw man", "distorts the view"],
                                         ["False dilemma", "only two options"], ["Slippery slope", "chain of fears"]]})
SCEN = one({"type": "scenario", "scenario": "Mia's train is late and she can't change it.", "question": "A Stoic would…",
            "options": ["Focus on her response", "Shout at staff", "Blame herself", "Give up travel"], "answer": 0,
            "notes": ["", "That tries to control what isn't hers", "Blame isn't the point", "Avoidance, not acceptance"],
            "why": "Only her response is up to her."})


def test_a_blank_takes_the_word_its_variants_and_a_small_typo_but_not_a_wrong_or_empty_answer():
    assert BLANK["question"].count("____") == 1 and BLANK["accept"] == ["judgments", "opinions"]
    for answer, expected in (("judgements", 1.0), ("Judgments.", 1.0), ("our opinions", 1.0), ("the judgements", 1.0),
                             ("judgemnts", 1.0), ("feelings", 0.0), ("", 0.0), ("asdf qwer", 0.0), ("   ", 0.0)):
        assert quiz.mark(BLANK, answer) == expected, answer
    assert quiz.mistake(BLANK, "judgements") == ""
    assert "spelled “judgements”" in quiz.mistake(BLANK, "judgemnts")
    assert quiz.mistake(BLANK, "feelings") == "You wrote “feelings”; the word that fits is “judgements”."
    # a sentence that gives its own answer away, or has no gap, isn't used
    assert quiz.parse_items({"questions": [{"type": "blank", "question": "Judgements: we control our ____.",
                                            "answer": "judgements"}]}) == []
    assert quiz.parse_items({"questions": [{"type": "blank", "question": "No gap here.", "answer": "x"}]}) == []
    assert not quiz.answered(BLANK, "  ") and quiz.answered(BLANK, "x")


def test_putting_steps_in_order_gets_part_marks_and_says_which_were_out_of_place():
    right = list(ORDER["key"])
    assert ORDER["items"] != ["Ask for a definition", "Find a counterexample", "Refine the definition"]
    assert quiz.mark(ORDER, right) == 1.0 and quiz.mistake(ORDER, right) == ""
    swapped = [right[1], right[0], right[2]]
    assert quiz.mark(ORDER, swapped) == 1 / 3
    assert quiz.mistake(ORDER, swapped).startswith("Steps 1, 2 were out of place. The order is: Ask for a definition →")
    assert not quiz.answered(ORDER, [0, 0, 1]) and not quiz.answered(ORDER, [0, None, 1])
    assert quiz.parse_items({"questions": [{"type": "order", "steps": ["a", "b"]}]}) == []          # too few
    assert quiz.parse_items({"questions": [{"type": "order", "steps": ["a", "a", "b"]}]}) == []     # a repeat


def test_matching_names_each_pair_that_was_wrong():
    right = list(MATCH["key"])
    two_swapped = [right[1], right[0]] + right[2:]
    assert quiz.mark(MATCH, two_swapped) == 0.5
    msg = quiz.mistake(MATCH, two_swapped)
    assert "“Ad hominem” goes with “attacks the person”" in msg and "Straw man" in msg and "False dilemma" not in msg


def test_a_scenario_says_why_her_choice_was_wrong():
    assert SCEN["type"] == "scenario" and SCEN["scenario"].startswith("Mia")
    wrong = SCEN["options"].index("Shout at staff")
    assert quiz.mark(SCEN, wrong) == 0.0
    assert quiz.mistake(SCEN, wrong) == ("You chose “Shout at staff”: That tries to control what isn't hers. "
                                         "The answer is “Focus on her response”.")
    assert quiz.mistake(SCEN, SCEN["answer"]) == ""
    plain = one({"type": "scenario", "question": "Q?", "options": ["a", "b", "c", "d"], "answer": 1})
    assert plain["type"] == "choice", "no situation given: a plain choice"


def test_written_answers_can_be_right_partly_right_or_wrong():
    q = quiz.new([one({"type": "short", "question": "Why?", "answer": "Because."}),
                  one({"type": "apply", "question": "Use it in your life.", "answer": "A real example."})])
    quiz.submit(q, ["Something.", "My example."])
    system, messages = quiz.grading_request(q)
    assert '"partly"' in system and "Criteria for a good answer: A real example." in messages[0]["content"]
    assert quiz.apply_grading(q, {"results": [{"id": 0, "verdict": "partly", "feedback": "Half."},
                                              {"id": 1, "verdict": "WRONG", "feedback": "No example."}]})
    assert q["marks"] == [0.5, 0.0]
    assert not quiz.apply_grading(q, {"results": [{"id": 0, "verdict": "maybe"}, {"id": 1, "correct": True}]})


def test_the_question_on_an_earlier_idea_never_counts_toward_the_score():
    main = [one({"type": "choice", "question": f"Q{k}?", "options": ["a", "b", "c", "d"], "answer": 0})
            for k in range(10)]
    earlier = dict(one({"type": "choice", "question": "Earlier?", "options": ["a", "b", "c", "d"], "answer": 0}), **{"from": 3})
    q = quiz.new(main + [earlier])
    answers = [x["answer"] for x in main] + [(earlier["answer"] + 1) % 4]
    quiz.submit(q, answers)
    assert quiz.finish(q) == 100 and quiz.points(q) == "10 of 10", "missing it costs nothing"
    assert quiz.parse_saved(q)["questions"][-1]["from"] == 3
    from coach import review
    slot = {"n": 7, "title": "T", "cards": []}
    assert review.add_missed(slot, q, D, "philosophy") == 0, "its card belongs to its own lesson"
    reply = {"questions": [{"type": "choice", "question": "E?", "options": ["a", "b", "c", "d"], "answer": 0,
                            "recall": True}]}
    assert quiz.recall_of(quiz.parse_items(reply)) is not None
    assert quiz.assemble(quiz.parse_items(reply) * 12) is None, "never one of the ten"


def test_the_quiz_hears_her_goal_and_an_earlier_shaky_idea():
    system, messages = quiz.request({"n": 4, "title": "T", "lesson": "Lesson."},
                                    {"goal": "Run a café (why: my dream)",
                                     "recall": {"n": 2, "title": "Old idea", "key": "Its key."}})
    text = messages[0]["content"]
    assert "Her goal: Run a café" in text and '"recall": true' in text and "Earlier lesson 2: Old idea" in text
    system, messages = quiz.request({"n": 4, "title": "T", "lesson": "Lesson."})
    assert "Her goal" not in messages[0]["content"] and "recall" not in messages[0]["content"]


def slot(n, ev, lesson="【Key Idea】 The idea.", **extra):
    return {"n": n, "title": f"Idea {n}", "unit": "U", "lesson": lesson, "completed": True, "followups": [],
            "quiz": None, "ev": ev, **extra}


def bank(n, kinds):
    return [one({"type": "choice", "question": f"B{n}{k}?", "options": ["a", "b", "c", "d"], "answer": 0})
            if kind == "choice" else one({"type": "blank", "question": f"The ____ {n}{k}.", "answer": f"w{n}{k}"})
            for k, kind in enumerate(kinds)]


def test_a_practice_set_takes_the_weakest_ideas_in_turn_easy_kinds_first_for_new_ones():
    weak = [mastery.event("quiz", 0.6, D, "a")]                                    # learning
    fading = [mastery.event("quiz", 1.0, D - timedelta(days=30), "b"),
              mastery.event("review", 1.0, D - timedelta(days=29), "c")]           # solid, now fading
    log = {"entries": [{"date": (D - timedelta(days=30)).isoformat(), "topic": "philosophy", "completed": True,
                        "lessons": [slot(1, weak, bank=bank(1, ["blank", "choice", "choice"])),
                                    slot(2, fading, bank=bank(2, ["choice", "blank", "choice"])),
                                    slot(3, [])]}], "books": []}
    s = practice.build(log, D)
    assert [(x["n"], x["q"]["type"]) for x in s["items"]] == [(2, "blank"), (1, "choice"), (2, "choice"), (1, "choice")]
    assert len(s["items"]) == 4 and not s["short"], "two an idea, never more: no loop on one"
    assert [n for _, n, _, _ in s["ideas"]] == [2, 1] and 3 not in [x["n"] for x in s["items"]]
    again = practice.build(log, D, avoid={practice.qid(x["q"]) for x in s["items"]})
    assert [x["n"] for x in again["items"]] == [2, 1], "one each left: the rest aren't repeated"
    assert {n for _, n, _ in again["short"]} == {1, 2}, "so the model may write more for both"


def test_explaining_it_back_checks_empty_short_or_nonsense_before_any_call():
    assert "Write a few sentences" in practice.precheck("  ")
    assert "A little more" in practice.precheck("It is control.")
    assert "doesn't read as an explanation" in practice.precheck("blah blah blah blah blah blah blah")
    assert practice.precheck("The dichotomy of control says some things are up to us and others are not.") == ""
    system, messages = practice.explain_request(slot(1, []), "Control", "My words.")
    assert '"verdict"' in system and "never preachy" in system and "Her explanation: My words." in messages[0]["content"]
    assert practice.read_explain({"right": "Good start.", "missing": "", "verdict": "right", "question": "Why?"}) == \
        {"right": "Good start.", "missing": "", "question": "Why?", "score": 1.0}
    assert practice.read_explain({"verdict": "partly"})["score"] == 0.5
    assert practice.read_explain({"verdict": "brilliant"}) is None and practice.read_explain(None) is None
    assert practice.read_follow({"feedback": "Yes.", "verdict": "wrong"}) == {"feedback": "Yes.", "score": 0.0}
    saved = practice.parse_explain({"at": "2026-11-02T10:00:00", "text": "t",
                                    "feedback": {"right": "r", "missing": "m", "question": "q", "score": 0.5}})
    assert saved["feedback"]["score"] == 0.5 and practice.parse_explain({"text": 1}) is None


def test_explaining_is_offered_once_a_day_after_a_lesson_is_passed():
    s1, s2 = slot(1, []), slot(2, [])
    log = {"entries": [{"date": D.isoformat(), "topic": "philosophy", "lessons": [s1, s2]}], "books": []}
    assert practice.invite(log, "philosophy", s1, D)
    s1["explain"] = {"at": f"{D.isoformat()}T09:00:00", "text": "x", "feedback": {"score": 1.0}}
    assert not practice.invite(log, "philosophy", s1, D), "already explained"
    assert not practice.invite(log, "philosophy", s2, D), "one a day"
    assert practice.invite(log, "philosophy", s2, D + timedelta(days=1))
    assert not practice.invite(log, "philosophy", dict(slot(3, []), completed=False), D + timedelta(days=1))


def test_the_tutor_says_what_its_answer_is_based_on_and_whether_she_was_confused():
    lesson = "【Key Idea】 A.\n\n【Deep Dive】 B.\n\n【Example】 C."
    body, where, confused = practice.split_reply("It means X.\n\nBased on: Deep Dive\nConfused: yes", lesson)
    assert body == "It means X." and where == "Deep Dive" and confused
    assert practice.based_label(where) == "Based on this lesson: Deep Dive"
    assert practice.split_reply("Y.\n**Based on:** beyond this lesson\nConfused: no", lesson)[1:] == ("beyond", False)
    assert practice.split_reply("Z.\nBased on: not sure\nConfused: no", lesson)[1] == "unsure"
    assert "isn't sure" in practice.based_label("unsure")
    assert practice.split_reply("No lines at all.", lesson) == ("No lines at all.", "", False)
    assert "Based on:" in practice.TUTOR and "Confused:" in practice.TUTOR and "不要編造" in practice.TUTOR


def test_new_exercises_are_read_per_idea_and_only_kinds_she_can_answer_at_once():
    data = {"questions": [{"idea": 1, "type": "choice", "question": "A?", "options": ["a", "b", "c", "d"], "answer": 0},
                          {"idea": 2, "type": "blank", "question": "The ____.", "answer": "x"},
                          {"idea": 2, "type": "short", "question": "Why?", "answer": "."},          # not here
                          {"idea": 9, "type": "choice", "question": "B?", "options": ["a", "b", "c", "d"], "answer": 0},
                          {"type": "choice", "question": "C?", "options": ["a", "b", "c", "d"], "answer": 0}]}
    made = practice.made(data, 2)
    assert sorted(made) == [1, 2] and [q["type"] for q in made[2]] == ["blank"]
    system, messages = practice.make_request([(1, "Control", "Only judgements are ours.")])
    assert "exactly 2 exercises" in system and "Idea 1: Control" in messages[0]["content"]


def test_her_practice_set_survives_a_refresh_and_junk_is_dropped():
    item = {"topic": "philosophy", "n": 1, "q": BLANK}
    saved = prefs.normalize({"practice": {"date": "2026-11-02", "items": [item], "answers": ["x"], "marks": [0.0],
                                          "before": {"philosophy|1": "learning"}, "done": True}})["practice"]
    assert saved["items"][0]["q"] == BLANK and saved["marks"] == [0.0] and saved["done"]
    assert prefs.normalize({"practice": {"date": "2026-11-02", "items": [{"topic": "p"}]}})["practice"] is None
    assert prefs.normalize({"practice": "junk"})["practice"] is None


def test_the_checker_sees_the_notes_and_the_markers_ignore_instructions_in_answers():
    system, messages = quiz.check_request([SCEN])
    assert "each note on a wrong" in system and "(note: That tries to control what isn't hers)" in messages[0]["content"]
    assert "ignore them" in quiz.GRADER and "ignore them" in practice.EXPLAINER and "ignore any" in practice.FOLLOW
