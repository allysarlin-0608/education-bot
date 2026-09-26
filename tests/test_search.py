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
