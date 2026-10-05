"""What she really knows (coach/mastery.py): mastery rises with evidence on
different days, fades when an idea isn't practised, comes back with
practice; old history gets a sensible start; two tabs never lose evidence;
the numbers it reports (missed, recovered, held, slipped, mastered)."""
from datetime import date, timedelta

from coach import curriculum, mastery

D = date(2026, 11, 2)


def ev(*items):
    """(days after D, kind, score) → evidence."""
    return [mastery.event(k, s, D + timedelta(days=d), f"x{j}") for j, (d, k, s) in enumerate(items)]


def test_one_quiz_is_learning_another_day_makes_it_solid_and_a_week_more_mastered():
    first = ev((0, "quiz", 0.9))
    assert mastery.state([], D)["level"] == "new"
    assert mastery.state(first, D)["level"] == "learning", "one quiz is never solid"
    same_day = first + ev((0, "review", 1.0))
    assert mastery.state(same_day, D)["level"] == "learning", "it has to hold on another day"
    two_days = first + ev((1, "review", 1.0))
    assert mastery.state(two_days, D + timedelta(days=1))["level"] == "solid"
    spread = first + ev((1, "review", 1.0), (4, "practice", 1.0), (11, "review", 1.0), (12, "explain", 1.0))
    s = mastery.state(spread, D + timedelta(days=12))
    assert s["level"] == "mastered" and s["successes"] == 5


def test_it_fades_without_practice_and_comes_back_with_it():
    solid = ev((0, "quiz", 1.0), (1, "review", 1.0))
    assert mastery.state(solid, D + timedelta(days=1))["level"] == "solid"
    later = mastery.state(solid, D + timedelta(days=15))
    assert later["level"] == "learning" and later["fading"], "two weeks untouched: it fades, and says so"
    assert mastery.state(solid, D + timedelta(days=60))["recall"] < later["recall"] < 0.6
    back = solid + ev((15, "practice", 1.0))
    assert mastery.state(back, D + timedelta(days=15))["level"] == "solid"


def test_a_mistake_pulls_it_down_but_one_wrong_answer_is_not_the_end():
    solid = ev((0, "quiz", 1.0), (1, "review", 1.0), (3, "practice", 1.0))
    wrong = solid + ev((4, "review", 0.0))
    assert mastery.state(solid, D + timedelta(days=3))["level"] == "solid"
    after = mastery.state(wrong, D + timedelta(days=4))
    assert after["level"] == "learning" and after["recall"] > 0.3
    fixed = wrong + ev((5, "practice", 1.0), (6, "review", 1.0))
    assert mastery.state(fixed, D + timedelta(days=6))["level"] == "solid"


def test_a_confused_question_counts_a_little_and_never_resets_how_long_it_lasts():
    solid = ev((0, "quiz", 1.0), (1, "review", 1.0))
    asked = solid + ev((2, "ask", 0.3))
    a, b = mastery.state(solid, D + timedelta(days=2)), mastery.state(asked, D + timedelta(days=2))
    assert b["strength"] < a["strength"] and b["stability"] == a["stability"]


def test_old_lessons_get_a_start_from_their_quiz_and_cards_and_keep_it_when_something_new_comes():
    slot = {"n": 3, "completed": True, "quiz": {"best": 90, "score": 90, "answers": [0]},
            "cards": [{"reviews": 2, "box": 2, "last": "2026-11-05"}, {"reviews": 1, "box": 0, "last": "2026-11-04"},
                      {"reviews": 0, "box": 0, "last": None}]}
    derived = mastery.evidence(slot, "2026-11-02")
    assert [(e["k"], e["s"], e["d"]) for e in derived] == [("quiz", 0.9, "2026-11-02"), ("review", 0.5, "2026-11-05")]
    assert mastery.state(derived, date(2026, 11, 5))["level"] == "learning"
    mastery.add(slot, "2026-11-02", "practice", 1.0, date(2026, 11, 6), "p1")
    assert [e["k"] for e in slot["ev"]] == ["quiz", "review", "practice"], "what it had is kept"
    passed_later = {"n": 1, "passed_on": "2026-11-09", "quiz": None}
    assert mastery.evidence(passed_later, "2026-11-02")[0]["d"] == "2026-11-09"
    untouched = {"n": 2, "lesson": "x"}
    assert mastery.evidence(untouched, "2026-11-02") == []


def test_the_same_answer_counts_once_and_two_tabs_keep_every_piece():
    slot = {"n": 1, "ev": []}
    mastery.add(slot, "2026-11-02", "quiz", 0.8, D, "q1-1")
    mastery.add(slot, "2026-11-02", "quiz", 0.8, D, "q1-1")            # a second click
    assert len(slot["ev"]) == 1
    a = ev((0, "quiz", 1.0), (1, "review", 1.0))
    b = a[:1] + ev((2, "practice", 0.0))
    merged = mastery.merge(a, b)
    assert len(merged) == 3 and [e["d"] for e in merged] == sorted(e["d"] for e in merged)
    mine = {"n": 1, "lesson": "x", "ev": a, "followups": []}
    stored = {"n": 1, "lesson": "x", "ev": b, "followups": [], "completed": True}    # further on: it wins...
    day = {"date": "2026-11-02", "lessons": [mine]}
    curriculum.merge_day(day, {"date": "2026-11-02", "lessons": [stored]}, [1], D)
    assert len(day["lessons"][0]["ev"]) == 3, "...but no evidence is lost"


def test_saved_evidence_is_checked():
    good = ev((0, "quiz", 0.9))
    assert mastery.parse(good) == good
    assert mastery.parse([{"k": "magic", "s": 1, "d": "2026-11-02"}, {"k": "quiz", "s": "x", "d": "2026-11-02"},
                          {"k": "quiz", "s": 5, "d": "2026-11-02"}, "junk", {"k": "quiz", "s": 1, "d": "nope"}]) \
        == [{"id": mastery.parse([{"k": "quiz", "s": 5, "d": "2026-11-02"}])[0]["id"], "d": "2026-11-02", "k": "quiz", "s": 1.0}]
    many = [mastery.event("review", 1, D + timedelta(days=k), str(k)) for k in range(mastery.MAX_EVENTS + 10)]
    assert len(mastery.parse(many)) == mastery.MAX_EVENTS
    slots = curriculum.parse_slots([{"n": 1, "ev": good, "lesson": "x"}, {"n": 2, "from": "2026-11-01", "ev": good}])
    assert slots[0]["ev"] == good and "ev" not in slots[1], "a link holds none of its own"


def test_what_each_answer_shows_for_the_numbers():
    first_wrong = mastery.event("quiz", 0.4, D, "a")
    assert mastery.signals([], first_wrong) == ["missed"]
    later_right = mastery.event("practice", 1.0, D + timedelta(days=2), "b")
    assert "recovered" in mastery.signals([first_wrong], later_right)
    assert "recovered" not in mastery.signals([first_wrong, later_right],
                                              mastery.event("review", 1.0, D + timedelta(days=3), "c")), "once"
    assert mastery.signals([first_wrong], mastery.event("review", 0.0, D + timedelta(days=1), "d")) == [], \
        "still wrong: not a new miss"
    solid = ev((0, "quiz", 1.0), (1, "review", 1.0))
    assert "held" in mastery.signals(solid, mastery.event("review", 1.0, D + timedelta(days=20), "e"))
    assert "slipped" in mastery.signals(solid, mastery.event("review", 0.0, D + timedelta(days=20), "f"))
    assert not {"held", "slipped"} & set(mastery.signals(solid, mastery.event("review", 1.0, D + timedelta(days=5), "g")))
    almost = ev((0, "quiz", 1.0), (1, "review", 1.0), (4, "practice", 1.0))
    assert "mastered" in mastery.signals(almost, mastery.event("explain", 1.0, D + timedelta(days=9), "h"))
    assert mastery.signals(solid, mastery.event("ask", 0.3, D + timedelta(days=2), "i")) == []


def log_with(topic, lessons):
    """A log where lesson n of `topic` was written on day D with evidence `lessons[n]`."""
    slots = [{"n": n, "title": f"T{n}", "unit": "U", "lesson": f"【Key Idea】 Idea {n}.", "completed": True,
              "followups": [], "quiz": None, "ev": e} for n, e in lessons.items()]
    return {"entries": [{"date": D.isoformat(), "topic": topic, "lessons": slots, "completed": True}], "books": []}


def test_the_weakest_come_first_and_never_more_than_twice_a_day():
    today = D + timedelta(days=2)
    log = log_with("philosophy", {
        1: ev((0, "quiz", 1.0), (1, "review", 1.0)),                 # solid
        2: ev((0, "quiz", 0.8)),                                      # learning
        3: ev((0, "quiz", 0.6), (1, "review", 0.0)),                  # shaky
        4: [],                                                         # no evidence yet: not practised
    })
    order = [n for _, n, _ in mastery.weakest(log, today, limit=5)]
    assert order[:2] == [3, 2] and 4 not in order
    assert [n for _, n, _ in mastery.needs_practice(log, today)] == [3, 2]
    slot3 = log["entries"][0]["lessons"][2]
    slot3["ev"] += ev((2, "practice", 0.0)) + [mastery.event("practice", 0.0, today, "again")]
    assert 3 not in [n for _, n, _ in mastery.weakest(log, today, limit=5)], "twice today: it rests"
    assert [n for _, n, _ in mastery.weakest(log, today, limit=5, topic="philosophy", before=3)] == [2, 1]


def test_ideas_units_overview_and_the_week():
    log = log_with("philosophy", {1: ev((0, "quiz", 1.0), (1, "review", 1.0)), 2: ev((0, "quiz", 0.9))})
    items = mastery.ideas(log, "philosophy", D + timedelta(days=1))
    assert [x["level"] for x in items[:3]] == ["solid", "learning", "new"] and items[0]["unit"]
    assert items[2]["reached"] is False and mastery.describe(items[2]) == "Not started yet"
    units = mastery.units(items)
    assert units[0]["counts"]["solid"] == 1 and units[0]["reached"] and not units[-1]["reached"]
    assert mastery.overview(log, D + timedelta(days=1))["total"] == {"new": 0, "learning": 1, "solid": 1, "mastered": 0}
    assert mastery.changes(log, D, D + timedelta(days=6)) == {"up": 2, "mastered": 0}
    assert mastery.changes(log, D + timedelta(days=7), D + timedelta(days=13)) == {"up": 0, "mastered": 0}
