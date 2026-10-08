"""Her learning record survives the move into tables exactly: every kind of
day and slot the app has ever written (old single-lesson days, links to the
day a lesson was written, quizzes submitted, marked in part or still a
draft, every kind of question, review cards and deleted ones, mastery
evidence, practice exercises, explanations), books and goals. What goes in
comes back as `coach.core.parse_log` would have it; one person never sees
another's rows."""
import copy
import random
from datetime import date, timedelta

import pytest

import seed_history
from coach import core, mastery, paths, quiz
from gnosis.data.repositories import accounts, learning

D = date(2026, 11, 2)


def question(kind, k=0):
    items = {
        "choice": {"type": "choice", "question": f"C{k}?", "options": ["a", "b", "c", "d"], "answer": 1,
                   "notes": ["x", "", "y", "z"], "why": "Because."},
        "scenario": {"type": "scenario", "scenario": "A day.", "question": f"S{k}?", "options": ["a", "b", "c", "d"],
                     "answer": 0, "why": "."},
        "blank": {"type": "blank", "question": f"The ____ {k}.", "answer": "axis", "accept": ["axes"], "why": "."},
        "order": {"type": "order", "question": f"Order {k}.", "steps": ["one", "two", "three"], "why": "."},
        "match": {"type": "match", "question": "Match.", "pairs": [["a", "1"], ["b", "2"], ["c", "3"], ["d", "4"]]},
        "short": {"type": "short", "question": f"Why {k}?", "answer": "Model.", "why": "."},
        "apply": {"type": "apply", "question": f"Use {k}?", "answer": "Criteria.", "why": "."},
    }
    return quiz.parse_items({"questions": [items[kind]]}, random.Random(k))[0]


def rich_log():
    """Every shape a stored record can have."""
    entries = seed_history.build(D, days=6, topics=("philosophy", "cosmos"), gaps=(2,), partial=(4,))
    day = entries[-1]
    s0 = day["lessons"][0]
    qs = [question(k, j) for j, k in enumerate(quiz.KINDS)] + [dict(question("choice", 9), **{"from": 1})]
    q = quiz.new(qs)
    answers = [1, 0, "axes!", list(reversed(qs[3]["key"])), [0, 1, 3, 2], "An answer.", "My example.", 2]
    quiz.submit(q, answers)
    q["marks"][5], q["feedback"][5] = 0.5, "Half right."          # marked in part; the apply answer not yet
    s0["quiz"] = q
    s0["followups"] = [{"role": "user", "content": "Why?"}, {"role": "assistant", "content": "Because.\n\nBased on: Key Idea\nConfused: no"}]
    s0["cards"] = [
        {"id": "c1", "kind": "word", "front": "axis", "back": "a line", "box": 2, "due": "2026-11-05",
         "added": "2026-11-01", "last": "2026-11-02", "reviews": 3, "lapses": 1, "paused": False,
         "topic": "philosophy", "n": s0["n"], "example": "Earth's axis."},
        {"id": "c2", "kind": "question", "front": "C9?", "back": "b", "box": 0, "due": "2026-11-03",
         "added": "2026-11-02", "last": None, "reviews": 0, "lapses": 0, "paused": True,
         "question": quiz._saved_question(qs[0])},
    ]
    s0["removed"] = ["gone2", "gone1"]
    s0["ev"] = [mastery.event("quiz", 0.8, D, "a"), mastery.event("review", 1.0, D, "b"),
                mastery.event("practice", 0.33, D + timedelta(days=1), "c")]
    s0["bank"] = [question("blank", 3), question("order", 4)]
    s0["explain"] = {"at": "2026-11-02T10:00:00+08:00", "text": "My words.",
                     "feedback": {"right": "Good.", "missing": "", "question": "Why?", "score": 1.0},
                     "reply": "Because.", "reply_feedback": {"feedback": "Yes.", "score": 0.5}}
    s1 = day["lessons"][1]
    s1["quiz"] = quiz.new([question("choice", k) for k in range(10)])
    s1["quiz"]["draft"] = [0, None] + [None] * 8                     # answers given so far, not submitted
    s1["cards"] = []                                                  # made since review began: none yet
    s1["ev"] = []
    nxt = {"date": (D + timedelta(days=1)).isoformat(), "topic": day["topic"], "completed": False, "lessons": [
        dict(s1, quiz=None, kickoff="", lesson="", followups=[], **{"from": day["date"]}),
        dict(s1, n=s1["n"] + 5, title="Later", passed_on=(D + timedelta(days=3)).isoformat())]}
    nxt["lessons"][0].pop("cards"), nxt["lessons"][0].pop("ev")
    old = {"date": "2026-09-01", "topic": "cosmos", "session_number": 1, "level": "入門", "completed": True,
           "title": "Old day", "lesson": "One old lesson.", "kickoff": "Hi", "reflection": "I liked it.",
           "followups": [{"role": "user", "content": "Q"}, {"role": "assistant", "content": "A"}]}
    goal = paths.parse_path({"id": "g-1234abcd", "title": "Read statements", "outcome": "Read them.", "level": "Beginner",
                             "units": [{"name": "Basics", "lessons": ["One", "Two"]}], "goal": "read", "why": "money",
                             "status": "active", "created": "2026-10-01T00:00:00+00:00"})
    book = {"id": "b1", "title": "A book", "author": "Someone", "pages": 100, "days": 14, "start": "2026-10-20",
            "plan": [], "checkins": {}}
    return {"version": 1, "entries": entries + [nxt, old], "books": [book], "paths": [goal]}


@pytest.fixture
def user(conn):
    return accounts.create_user(conn, email="Learner@Example.com", legacy_id="supa-1")


def test_a_whole_record_comes_back_exactly(conn, user):
    log = rich_log()
    expected = core.parse_log(copy.deepcopy(log))
    assert expected["paths"] and expected["entries"][-1]["lessons"][0].get("from"), "the fixture has every shape"
    written = learning.save_log(conn, user, log)
    back = learning.load_log(conn, user)
    assert back == expected
    assert learning.counts(back) == written
    assert written["evidence"] == 3 and written["cards"] == 2 and written["goals"] == 1 and written["books"] == 1


def test_a_day_saved_again_replaces_it_and_touches_nothing_else(conn, user):
    learning.save_log(conn, user, rich_log())
    before = learning.load_log(conn, user)
    k = next(j for j, e in enumerate(before["entries"]) if e["lessons"])
    day = copy.deepcopy(before["entries"][k])
    day["reflection"] = "Changed."
    day["lessons"][0]["completed"] = not day["lessons"][0]["completed"]
    learning.save_entry(conn, user, day)
    after = learning.load_log(conn, user)
    assert after["entries"][k] == day
    assert after["entries"][:k] + after["entries"][k + 1:] == before["entries"][:k] + before["entries"][k + 1:]
    assert learning.load_entry(conn, user, day["date"], day["topic"])["reflection"] == "Changed."
    assert learning.load_entry(conn, user, "2001-01-01", "philosophy") is None


def test_one_person_never_sees_anothers_record(conn, user):
    other = accounts.create_user(conn, email="other@example.com")
    learning.save_log(conn, user, rich_log())
    assert learning.load_log(conn, other)["entries"] == []
    learning.save_log(conn, other, {"entries": [], "books": [], "paths": []})
    assert learning.counts(learning.load_log(conn, user))["days"] > 0, "her record untouched by the other's save"


def test_an_invalid_day_is_refused_not_half_written(conn, user):
    with pytest.raises(ValueError):
        learning.save_entry(conn, user, {"date": "not a date", "topic": "philosophy"})
    with pytest.raises(ValueError):
        learning.save_goal(conn, user, {"id": "nope"})
