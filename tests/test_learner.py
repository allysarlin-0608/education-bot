"""The learner model (docs/LEARNING_DESIGN.md §2): knowledge tracing, FSRS,
the level floor that keeps existing learners' progress through the change,
experiment arms, and the rows that measure learning (coach/attempts.py)."""
from datetime import date, timedelta

from coach import attempts, experiments, learner, mastery, storage

D = date(2026, 11, 2)


def ev(*items, start=D):
    return [mastery.event(k, s, start + timedelta(days=d), f"t{j}") for j, (d, k, s) in enumerate(items)]


# ------------------------------------------------------------------ BKT
def test_right_answers_raise_the_chance_it_is_learned_and_a_miss_lowers_it():
    p = learner.P_INIT
    after_quiz = learner.bkt(p, 1.0, "quiz")
    assert 0.4 < after_quiz < 0.7, "one good quiz: probably learned, not certain"
    after_two = learner.bkt(after_quiz, 1.0, "review")
    assert after_two > 0.85
    assert learner.bkt(after_two, 0.0, "review") < after_two
    assert learner.bkt(p, 0.5, "quiz") < after_quiz, "a part-right answer moves it part of the way"


def test_an_easy_guess_says_less_than_a_whole_quiz():
    assert learner.bkt(0.1, 1.0, "check") < learner.bkt(0.1, 1.0, "quiz")


def test_a_confused_question_is_weak_evidence_and_teaches_nothing():
    p = 0.6
    assert learner.bkt(p, 0.3, "ask") < p and p - learner.bkt(p, 0.3, "ask") < p - learner.bkt(p, 0.0, "review")


# ------------------------------------------------------------------ FSRS
def test_recall_is_ninety_percent_after_stability_days_and_falls_after():
    assert abs(learner.retrievability(10, 10) - 0.9) < 1e-9
    assert learner.retrievability(30, 10) < learner.retrievability(10, 10) < learner.retrievability(1, 10)
    assert learner.interval(10, 0.9) == 10 and learner.interval(10, 0.85) > 10


def test_each_rating_moves_memory_the_right_way():
    s, d = learner.first(learner.GOOD)
    easy, _ = learner.review(s, d, s, learner.EASY)
    good, _ = learner.review(s, d, s, learner.GOOD)
    hard, _ = learner.review(s, d, s, learner.HARD)
    again, d_again = learner.review(s, d, s, learner.AGAIN)
    assert easy > good > hard > s > again and d_again > d
    assert learner.rating(False, 3) == learner.AGAIN and learner.rating(True, 1) == learner.HARD
    assert learner.rating(True, None) == learner.GOOD and learner.rating(True, 3) == learner.EASY
    assert learner.overconfident(False, 3) and not learner.overconfident(False, 1)


# ----------------------------------------------------- levels and the floor
def test_a_miss_means_it_has_to_hold_again_on_another_day():
    solid = ev((0, "quiz", 1.0), (1, "review", 1.0))
    assert mastery.state(solid, D + timedelta(days=1))["level"] == "solid"
    missed = solid + ev((3, "review", 0.0), start=D)
    assert mastery.state(missed, D + timedelta(days=3))["level"] == "learning"
    again = missed + ev((5, "practice", 1.0), start=D)
    assert mastery.state(again, D + timedelta(days=5))["level"] == "solid"


def test_progress_from_before_the_change_never_drops_because_of_it():
    """A learner whose idea the old model called solid keeps it solid,
    until she gets it wrong after the change."""
    before = mastery.SWITCH - timedelta(days=4)
    old = ev((0, "quiz", 0.9), (1, "practice", 0.8), (2, "review", 0.8), start=before)
    day = mastery.SWITCH
    legacy = mastery.legacy_state(old, day)["level"]
    assert mastery.LEVELS.index(mastery.state(old, day)["level"]) >= mastery.LEVELS.index(legacy)
    wrong_after = old + [mastery.event("review", 0.0, day, "after")]
    assert mastery.state(wrong_after, day)["level"] == mastery._capped(wrong_after, day, mastery._state)["level"]


def test_new_learners_get_knowledge_tracing_only():
    fresh = ev((0, "quiz", 1.0))
    s = mastery.state(fresh, D)
    assert s["level"] == "learning" and 0.4 < s["strength"] < 0.7


# --------------------------------------------------------------- experiments
def test_arms_are_stable_spread_and_off_means_the_first_arm():
    arms = {experiments.arm("fading", "learner-1", "math", n) for n in range(40)}
    assert arms == {"faded", "problem_first"}, "within one learner, ideas fall in both arms"
    assert experiments.arm("fading", "learner-1", "math", 3) == experiments.arm("fading", "learner-1", "math", 3)
    assert experiments.arm("fading", "learner-1", "math", 3, on=False) == "faded"
    assert experiments.arm("retention", "", on=True) == "r90"
    assert experiments.enabled("", public=True) and not experiments.enabled("off", public=True)
    assert not experiments.enabled("", public=False), "never in the personal app"
    assert experiments.target("x", on=False) == 0.9


# ------------------------------------------------------------------- the rows
def test_a_row_holds_only_numbers_and_labels_never_what_she_wrote():
    r = attempts.row(D, "math", 12, "quiz", "choice", score=1, conf=3, secs=14.6, gap=2, diff=2,
                     variants=("fading:faded",))
    assert r == {"day": D.isoformat(), "topic": "math", "n": 12, "ctx": "quiz", "kind": "choice", "score": 1.0,
                 "first": True, "conf": 3, "secs": 14, "gap": 2, "diff": 2, "variant": "fading:faded"}
    assert attempts.parse(dict(r, ctx="nope")) is None and attempts.parse(dict(r, conf=7))["conf"] is None
    assert attempts.row(D, "math", 1, "step", "learn")["score"] is None
    assert len(attempts.rows([r] * 100)) == attempts.MAX_ROWS
    assert attempts.gap([{"d": (D - timedelta(days=3)).isoformat()}, {"d": D.isoformat()}], D) == 3
    assert attempts.gap([], D) is None


def test_the_file_store_keeps_answers_and_admins_see_no_one(tmp_path):
    store = storage.FileStore(path=tmp_path / "log.json", scoped=True, current_user=lambda: "u-1")
    store.add_attempts([attempts.row(D, "g-1a2b3c4d", 1, "quiz", "choice", score=1),
                        attempts.row(D, "math", 2, "review", "word", score=0)])
    rows = store.attempts_since(D - timedelta(days=1))
    assert len(rows) == 2 and all("user_id" not in r for r in rows)
    assert rows[0]["topic"].startswith("goal:") and rows[1]["topic"] == "math"
    assert rows[0]["learner"] == rows[1]["learner"] != "u-1"
    assert len(store.export_my_data()["learning_attempts"]) == 2
