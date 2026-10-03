"""Review (spaced repetition): cards from missed questions, vocabulary and
saved points; boxes and intervals; the daily limit; no model calls."""
import json
from datetime import date, timedelta

from coach import core, curriculum, quiz, review
from test_quiz import model_reply, right_answers

D = date(2026, 10, 3)
LESSON = ("【Key Idea】: Fibres decide how cloth behaves.\n\n"
          "【Deep Dive】:\n- **Natural fibres**: cotton, wool and silk come from plants and animals.\n"
          "- **Synthetic fibres**: polyester and nylon are made from oil.\n\n"
          "【Vocabulary】:\n| Word | Meaning | Example |\n|---|---|---|\n"
          "| fibre | a thin thread | Cotton is a fibre. |\n| weave | how threads cross | A plain weave. |\n"
          "| blend | a mix of fibres | A cotton blend. |\n| drape | how cloth hangs | Silk drapes well. |\n\n"
          "【Note】: Keep going.")


def slot():
    s = curriculum.new_slot("fashion", 1)
    s["lesson"] = LESSON
    return s


def old_slot():
    """A lesson saved before review existed: no "cards" key."""
    s = slot()
    s.pop("cards", None)
    return s


def test_sources_vocabulary_and_points_are_read_from_the_lesson():
    assert review.vocabulary(LESSON)[0] == ("fibre", "a thin thread", "Cotton is a fibre.")
    assert len(review.vocabulary(LESSON)) == 4
    assert review.vocabulary("【Vocabulary】: axis｜the line it spins around｜Earth spins on its axis.") == \
        [("axis", "the line it spins around", "Earth spins on its axis.")]
    labels = [label for label, _ in review.key_points(LESSON)]
    assert labels == ["Key idea", "Natural fibres", "Synthetic fibres"]


def test_missed_questions_and_words_become_cards_once():
    s = slot()
    q = quiz.new(quiz.parse(model_reply()))
    answers = right_answers(q)
    answers[0] = (answers[0] + 1) % 4                  # one wrong
    quiz.submit(q, answers)
    assert review.add_missed(s, q, D, "fashion") == 1
    assert review.add_missed(s, q, D, "fashion") == 0  # the same question isn't added twice
    assert review.add_words(s, D, "fashion") == 4
    card = s["cards"][0]
    assert card["kind"] == "question" and card["due"] == (D + timedelta(days=1)).isoformat()


def test_right_moves_it_further_away_wrong_starts_again():
    c = review._card("point", "front", "back", D)
    review.grade(c, True, D + timedelta(days=1))
    assert c["box"] == 1 and c["due"] == (D + timedelta(days=4)).isoformat()
    review.grade(c, True, D + timedelta(days=4))
    assert c["box"] == 2 and c["due"] == (D + timedelta(days=11)).isoformat()
    review.grade(c, False, D + timedelta(days=11))
    assert c["box"] == 0 and c["due"] == (D + timedelta(days=12)).isoformat() and c["lapses"] == 1


def test_due_respects_the_daily_limit_pause_and_what_was_done_today():
    s = slot()
    for k in range(review.DAILY_LIMIT + 5):
        review._add(s, review._card("point", f"p{k}", "b", D - timedelta(days=3)))
    log = {"entries": [{"date": D.isoformat(), "topic": "fashion", "completed": False, "lessons": [s]}]}
    assert len(review.due(log, D)) == review.DAILY_LIMIT
    s["cards"][0]["paused"] = True
    first = review.due(log, D)[0][2]
    review.grade(first, True, D)
    assert len(review.due(log, D)) == review.DAILY_LIMIT - 1      # one done today counts against the limit
    assert first not in [c for _, _, c in review.due(log, D)]


def test_a_word_is_asked_with_other_words_meanings_and_reviews_change_no_day():
    s = slot()
    review.add_words(s, D, "fashion")
    log = {"entries": [{"date": D.isoformat(), "topic": "fashion", "completed": False, "lessons": [s]}]}
    q = review.word_question(log, s["cards"][0])
    assert q["options"][q["answer"]] == "a thin thread" and len(set(q["options"])) == 4
    before = core.current_streak(log, D + timedelta(days=1)), core.completed_dates(log)
    for _, _, c in review.due(log, D + timedelta(days=1)):
        review.grade(c, True, D + timedelta(days=1))
    assert (core.current_streak(log, D + timedelta(days=1)), core.completed_dates(log)) == before


def test_cards_survive_a_backup_and_bad_ones_are_dropped():
    s = slot()
    review.add_words(s, D, "fashion")
    review.save_point(s, "Key idea", "Fibres decide how cloth behaves.", D, "fashion")
    s["cards"].append({"kind": "nonsense"})
    log = {"version": 1, "entries": [{"date": D.isoformat(), "topic": "fashion", "lessons": [s]}], "books": []}
    restored = core.parse_log(json.loads(json.dumps(log)))
    cards = restored["entries"][0]["lessons"][0]["cards"]
    assert [c["kind"] for c in cards] == ["word"] * 4 + ["point"]
    assert review.saved(restored["entries"][0]["lessons"][0], "Key idea")


def test_lessons_from_before_review_give_cards_spread_over_days_without_writing():
    """Part 1: what she learned before review existed comes back, two
    lessons' worth a day from LEGACY_FROM, and nothing is stored until she acts."""
    old = []
    for k in range(5):
        s = old_slot()
        s["n"] = k + 1
        s["completed"] = True
        old.append({"date": f"2026-09-{20 + k}", "topic": "fashion", "completed": True, "lessons": [s]})
    log = {"entries": old}
    snapshot = json.dumps(log, sort_keys=True)
    cards = review.cards(log)
    assert len(cards) == 5 * (1 + 4)                         # key idea + 4 words each
    dues = sorted({c["due"] for _, _, c in cards})
    assert dues == [str(review.LEGACY_FROM + timedelta(days=d)) for d in (0, 1, 2)]
    assert json.dumps(log, sort_keys=True) == snapshot      # worked out, not written
    assert len(review.due(log, review.LEGACY_FROM)) == 10     # two lessons' worth on the first day
    # answering one keeps that lesson's cards; the other lessons keep their days
    e, s, c = review.due(log, review.LEGACY_FROM)[0]
    review.keep(log, s)
    review.grade(review.find(log, c["id"])[2], True, review.LEGACY_FROM)
    assert len(s["cards"]) == 5 and len(review.cards(log)) == 25
    assert sorted({c["due"] for _, s2, c in review.cards(log) if s2 is not s}) == dues
    # a lesson concluded after review began has its own cards: no old ones on top
    new = slot()
    new["completed"] = True
    review.add_words(new, D, "fashion")
    log["entries"].append({"date": D.isoformat(), "topic": "fashion", "completed": True, "lessons": [new]})
    assert len(review.cards(log)) == 25 + 4


def test_the_same_word_in_two_lessons_is_two_cards_each_answered_on_its_own():
    a, b = slot(), slot()
    b["n"] = 2
    review.add_words(a, D, "fashion")
    review.add_words(b, D, "fashion")
    ids = [c["id"] for c in a["cards"] + b["cards"]]
    assert len(set(ids)) == len(ids) == 8
    log = {"entries": [{"date": D.isoformat(), "topic": "fashion", "completed": True, "lessons": [a, b]}]}
    later = D + timedelta(days=1)
    for _ in range(8):                          # every due card can be answered and leaves the list
        _, _, c = review.due(log, later)[0]
        review.grade(review.find(log, c["id"])[2], True, later)
    assert review.due(log, later) == []


def test_a_new_lessons_missed_questions_come_back_tomorrow_whatever_came_before():
    """ISS-007: a first quiz on a new lesson was taken for a lesson from
    before review, so its missed questions got a backfill date weeks out."""
    history = []
    for k in range(40):                                   # 40 old lessons passed
        s = old_slot()
        s["n"], s["completed"] = k + 1, True
        history.append({"date": (D - timedelta(days=60 - k)).isoformat(), "topic": "fashion", "lessons": [s]})
    new = curriculum.new_slot("fashion", 41)
    new["lesson"] = LESSON
    log = {"entries": history + [{"date": D.isoformat(), "topic": "fashion", "lessons": [new]}]}
    new["quiz"] = q = quiz.new(quiz.parse(model_reply()))
    answers = right_answers(q)
    answers[0] = (answers[0] + 1) % 4
    quiz.submit(q, answers)
    review.keep(log, new)                                 # what conclude() does first
    review.add_missed(new, q, D, "fashion")
    assert [c["due"] for c in new["cards"]] == [(D + timedelta(days=1)).isoformat()]


def test_cards_she_deleted_stay_deleted_after_a_save():
    """ISS-008: no cards left was saved as [], read back as "never had any",
    and the lesson's cards were worked out again."""
    s = old_slot()
    s["completed"] = True
    log = {"version": 1, "entries": [{"date": D.isoformat(), "topic": "fashion", "lessons": [s]}], "books": []}
    assert review.cards(log)
    review.keep(log, s)
    for c in list(s["cards"]):
        review.remove(s, c["id"])
    restored = core.parse_log(json.loads(json.dumps(log)))
    assert review.cards(restored) == []
