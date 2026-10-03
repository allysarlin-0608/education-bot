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
