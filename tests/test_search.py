from coach import search

LOG = {
    "entries": [
        {"date": "2026-09-10", "topic": "cosmos", "reflection": "", "title": "",
         "lessons": [{"n": 24, "title": "What causes tides", "unit": "The Moon",
                      "lesson": "【Topic】 Tides\n\n【Key Idea】 The **Moon's** gravity pulls the oceans."}]},
        {"date": "2026-09-12", "topic": "fashion", "reflection": "Linen breathes better than I thought.", "title": "",
         "lessons": [{"n": 5, "title": "Natural fibres", "unit": "Fibres", "lesson": "Cotton and linen come from plants."}]},
        {"date": "2026-07-01", "topic": "philosophy", "title": "Plato's cave", "reflection": "", "lessons": []},
    ],
    "books": [
        {"id": "w", "status": "finished", "title": "Walden", "author": "Thoreau", "chapters": ["Economy", "Solitude"],
         "finished_on": "2026-09-13", "checks": {"2": {"passed_on": "2026-09-02", "summary": "Solitude is not loneliness."}}},
        {"id": "d", "status": "setup", "title": "Draft", "author": "", "chapters": [], "checks": {}},
    ],
}


def test_every_word_must_appear_in_any_case_and_order():
    r = search.find(LOG, "moon GRAVITY")
    assert [x["title"] for x in r] == ["Lesson 24: What causes tides"]
    assert r[0]["open"] == ("day", "2026-09-10") and "gravity" in r[0]["snippet"].lower()
    assert search.find(LOG, "moon plants") == []


def test_notes_and_books_are_found_and_open_their_book():
    r = search.find(LOG, "solitude")
    assert {x["kind"] for x in r} == {"book", "note"}
    assert all(x["open"] == ("book", "w") for x in r)


def test_reflections_and_old_sessions():
    assert search.find(LOG, "linen")[0]["date"] == "2026-09-12"
    assert [x["kind"] for x in search.find(LOG, "linen")] == ["lesson", "note"]
    assert search.find(LOG, "cave")[0]["open"] == ("day", "2026-07-01")


def test_newest_first_empty_query_and_drafts_left_out():
    dates = [x["date"] for x in search.find(LOG, "e")]
    assert dates == sorted(dates, reverse=True)
    assert search.find(LOG, "   ") == [] and search.find(LOG, "draft") == []


def test_lesson_markup_is_not_shown():
    assert "【" not in search.find(LOG, "tides")[0]["snippet"] and "**" not in search.find(LOG, "gravity")[0]["snippet"]


# ---------------------------------------------------------------- audit stage 2: accurate, ranked, wider
from coach import catalog                                    # noqa: E402
from test_goals import a_path                                 # noqa: E402


def test_a_word_matches_whole_words_not_inside_others():
    log = {"entries": [{"date": "2026-09-01", "topic": "philosophy", "title": "", "reflection": "",
                        "lessons": [{"n": 1, "title": "How to start a habit", "unit": "Habits", "lesson": "Begin small."},
                                    {"n": 2, "title": "Looking at art", "unit": "Art", "lesson": "Colour and line."}]}],
           "books": []}
    assert [r["title"] for r in search.find(log, "art")] == ["Lesson 2: Looking at art"], "never 'start'"
    assert search.find(log, "hab")[0]["title"] == "Lesson 1: How to start a habit", "the start of a word is enough"


def test_chinese_matches_inside_a_sentence():
    log = {"entries": [{"date": "2026-09-01", "topic": "philosophy", "title": "", "reflection": "我覺得投資要長期",
                        "lessons": []}], "books": []}
    assert search.find(log, "投資")[0]["kind"] == "note"


def test_a_title_counts_more_than_the_text():
    log = {"entries": [
        {"date": "2026-09-05", "topic": "cosmos", "title": "", "reflection": "",
         "lessons": [{"n": 3, "title": "Stars", "unit": "Sky", "lesson": "The Moon is not a star but it shines."}]},
        {"date": "2026-09-01", "topic": "cosmos", "title": "", "reflection": "",
         "lessons": [{"n": 1, "title": "The Moon", "unit": "Sky", "lesson": "Craters."}]}], "books": []}
    assert [r["title"] for r in search.find(log, "moon")] == ["Lesson 1: The Moon", "Lesson 3: Stars"], \
        "the lesson about it first, though older"


def test_goals_lessons_still_to_come_and_review_cards_are_found():
    goal = a_path()
    catalog.use([goal])
    log = {"entries": [], "books": []}
    r = search.find(log, "reading financial", topics=[goal["id"]])
    assert r[0]["kind"] == "goal" and r[0]["open"] == ("course", goal["id"])
    coming = search.find(log, "idea 2.1", topics=[goal["id"]])
    assert coming and coming[0]["kind"] == "coming" and coming[0]["open"] == ("course", goal["id"])
    entry = {"date": "2026-09-01", "topic": goal["id"]}
    card = {"front": "What does a balance sheet show?", "back": "Assets, liabilities, equity", "paused": False,
            "added": "2026-09-01"}
    found = search.find(log, "balance", cards=[(entry, {}, card)])
    assert found[0]["kind"] == "card" and found[0]["open"] == ("review", "balance")
    assert not search.find(log, "balance", cards=[(entry, {}, dict(card, paused=True))]), "paused cards stay out"
    catalog.use([])
