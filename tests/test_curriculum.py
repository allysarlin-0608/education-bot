"""The fixed syllabus: files, order, five lessons a day, progress."""
from datetime import date
from pathlib import Path

import pytest

from coach import core, curriculum, storage, tokens

from test_storage import FakePostgrest, make

TOPICS = [t for t in core.TOPICS if t != "reading"]
THU = date(2026, 9, 24)


@pytest.mark.parametrize("topic", TOPICS)
def test_every_lesson_topic_has_a_clean_syllabus(topic):
    lessons = curriculum._load(topic)
    titles = [title for _, title in lessons]
    assert 260 <= len(titles) <= curriculum.TOTAL
    assert len(set(titles)) == len(titles)                  # no lesson twice
    assert all(unit for unit, _ in lessons)                 # every lesson is in a unit
    assert not any(t.startswith("#") for t in titles)


def test_reading_has_no_syllabus():
    assert not curriculum.has_syllabus("reading")


def test_levels_follow_position_in_the_syllabus():
    assert [curriculum.level_for(n) for n in (1, 1000, 1001, 2000, 2001, 3000)] == \
        ["Beginner", "Beginner", "Intermediate", "Intermediate", "Advanced", "Advanced"]


def day(log, when, topic, done):
    """A day with the next five lessons; `done` = how many were ticked."""
    entry = core.start_entry(log, when, topic)
    entry["lessons"] = curriculum.day_plan(log, topic, None)
    for slot in entry["lessons"][:done]:
        slot["completed"] = True
    entry["completed"] = curriculum.day_complete(entry["lessons"])
    return entry


def test_five_new_lessons_a_day_in_order_and_unfinished_ones_come_back():
    log = core.empty_log()
    assert curriculum.next_numbers(log, "cosmos") == [1, 2, 3, 4, 5]
    first = day(log, date(2026, 9, 17), "cosmos", done=5)
    assert first["completed"]
    assert curriculum.next_numbers(log, "cosmos") == [6, 7, 8, 9, 10]
    second = day(log, THU, "cosmos", done=3)                # 6–8 done, 9 and 10 not
    assert not second["completed"]                          # all five are needed
    assert curriculum.next_numbers(log, "cosmos") == [9, 10, 11, 12, 13]


def test_a_started_day_keeps_its_lessons():
    log = core.empty_log()
    entry = day(log, THU, "cosmos", done=1)
    assert curriculum.day_plan(log, "cosmos", entry) is entry["lessons"]
    assert curriculum.day_plan(log, "cosmos", None)[0]["n"] == 2


def test_progress_counts_completed_lessons():
    log = core.empty_log()
    day(log, THU, "philosophy", done=4)
    p = curriculum.progress(log, "philosophy")
    assert (p["done"], p["total"], p["level"], p["level_done"]) == (4, 3000, "Beginner", 4)


def test_unit_progress_follows_the_next_lesson():
    log = core.empty_log()
    first = curriculum.unit_progress(log, "philosophy")
    assert first == {"unit": "What philosophy is", "first": 1, "last": 5, "total": 5, "done": 0}
    day(log, THU, "philosophy", 3)
    assert curriculum.unit_progress(log, "philosophy")["done"] == 3
    day(log, date(2026, 10, 1), "philosophy", 5)       # lessons 4–8: into the next unit
    now = curriculum.unit_progress(log, "philosophy")
    assert (now["unit"], now["first"], now["done"]) == ("Thinking tools: arguments", 6, 3)


def test_unit_progress_after_everything_written_is_done():
    log = core.empty_log()
    entry = core.start_entry(log, THU, "cosmos")
    entry["lessons"] = [dict(curriculum.new_slot("cosmos", n), completed=True)
                        for n in range(1, curriculum.written("cosmos") + 1)]
    last = curriculum.unit_progress(log, "cosmos")
    assert last["last"] == curriculum.written("cosmos") and last["done"] == last["total"]


def test_lessons_survive_save_and_load(tmp_path):
    log = core.empty_log()
    entry = day(log, THU, "jewelry", done=2)
    entry["lessons"][0].update(kickoff="k", lesson="L", followups=[{"role": "user", "content": "q"}])
    path = tmp_path / "log.json"
    core.save_log(log, path)
    loaded = core.load_log(path)["entries"][0]["lessons"]
    assert [s["n"] for s in loaded] == [1, 2, 3, 4, 5]
    assert loaded[0]["lesson"] == "L" and loaded[0]["followups"] == [{"role": "user", "content": "q"}]
    assert [s["completed"] for s in loaded] == [True, True, False, False, False]


def test_parse_slots_drops_junk():
    assert curriculum.parse_slots("nope") == []
    assert curriculum.parse_slots([{"n": "1"}, "x", {"n": 2, "followups": [{"role": "hacker", "content": "x"}]}]) == [
        {"n": 2, "title": "", "unit": "", "kickoff": "", "lesson": "", "followups": [], "completed": False, "quiz": None}]


def test_supabase_without_the_lessons_column_is_detected_on_load():
    fake, store = make(FakePostgrest(missing_columns={"lessons"}))
    store.load()
    assert "lessons" in store.missing_columns
    fake, store = make()
    store.load()
    assert "lessons" not in store.missing_columns


def test_lessons_sql_matches_the_file():
    sql = Path(__file__).resolve().parent.parent / "supabase" / "lessons.sql"
    assert "add column if not exists lessons jsonb" in sql.read_text(encoding="utf-8")
    assert "add column if not exists lessons jsonb" in storage.LESSONS_SQL


def test_prompt_names_this_lesson_and_fences_off_the_next():
    slot = curriculum.new_slot("cosmos", 2)
    prompt = core.build_system_prompt(core.empty_log(), "cosmos", THU, slot=slot)
    this, before, after = curriculum.lesson("cosmos", 2), curriculum.lesson("cosmos", 1), curriculum.lesson("cosmos", 3)
    assert f"第 2 課「{this['title']}」" in prompt and "難度（依課綱位置）：Beginner" in prompt
    assert before["title"] in prompt and after["title"] in prompt and "不要提前講" in prompt
    kickoff = core.build_kickoff_message("cosmos", THU, slot=slot)
    assert kickoff.endswith(f"Lesson 2: {this['title']}")


@pytest.mark.parametrize("topic", TOPICS)
def test_a_syllabus_lesson_request_fits_the_budget(topic):
    log = core.empty_log()
    for d in range(1, 22):
        day(log, date(2026, 8, d), topic, done=5)
    slot = curriculum.day_plan(log, topic, None)[0]
    system = core.build_system_prompt(log, topic, THU, slot=slot)
    kickoff = [{"role": "user", "content": core.build_kickoff_message(topic, THU, slot=slot)}]
    assert tokens.estimate_request(system, kickoff, tokens.LESSON_MAX_TOKENS) <= tokens.REQUEST_BUDGET


def test_lessons_are_finished_strictly_in_order():
    slots = [curriculum.new_slot("cosmos", n) for n in range(1, 6)]
    assert curriculum.blocking(slots, 0) is None
    assert curriculum.blocking(slots, 1)["n"] == 1         # lesson 2 waits for lesson 1
    slots[1]["completed"] = True                            # old data: lesson 2 done, lesson 1 not
    assert curriculum.blocking(slots, 2)["n"] == 1          # lesson 3 still waits for lesson 1
    slots[0]["completed"] = True
    assert curriculum.blocking(slots, 2) is None


def test_a_lesson_not_passed_is_linked_not_written_again_and_survives_a_backup():
    """D2: the next day's slot for an unpassed, written lesson is a link to
    it; the link keeps no content, and a backup round trip keeps both marks."""
    import json

    from coach import core
    first = curriculum.new_slot("philosophy", 1)
    first.update(lesson="【Key Idea】 x", kickoff="k", followups=[{"role": "user", "content": "q"}])
    log = {"entries": [{"date": "2026-10-14", "topic": "philosophy", "lessons": [first]}], "books": []}
    nxt = curriculum.day_plan(log, "philosophy", None, 1)[0]
    assert nxt["from"] == "2026-10-14" and nxt["lesson"] == "" and nxt["quiz"] is None
    entry, slot = curriculum.origin(log, "philosophy", nxt)
    assert slot is first and curriculum.content(log, "philosophy", nxt) is first
    nxt["completed"], first["passed_on"] = True, "2026-10-15"
    log["entries"].append({"date": "2026-10-15", "topic": "philosophy", "lessons": [nxt]})
    assert curriculum.next_numbers(log, "philosophy", 1) == [2]          # passed: never scheduled again
    restored = core.parse_log(json.loads(json.dumps(log)))
    a, b = restored["entries"][0]["lessons"][0], restored["entries"][1]["lessons"][0]
    assert a["passed_on"] == "2026-10-15" and not a["completed"] and a["lesson"]
    assert b["from"] == "2026-10-14" and b["completed"] and b["lesson"] == "" and b["followups"] == []
    # a lesson never written (no content) isn't linked: it's simply written on the day
    log2 = {"entries": [{"date": "2026-10-14", "topic": "philosophy",
                         "lessons": [curriculum.new_slot("philosophy", 1)]}], "books": []}
    assert "from" not in curriculum.day_plan(log2, "philosophy", None, 1)[0]


def test_a_carried_lesson_saved_from_an_old_copy_keeps_what_another_device_did():
    """ISS-021: the quiz sheet saved the day a carried lesson began from this
    session's copy, undoing review grades made on the phone meanwhile."""
    from datetime import date
    today = date(2026, 10, 4)
    def card(cid, added, box=0):
        return {"id": cid, "kind": "question", "front": cid, "back": "b", "box": box, "due": "2026-10-04",
                "added": added, "last": None, "reviews": 0, "lapses": 0, "paused": False}
    mine_slot = dict(curriculum.new_slot("cosmos", 4), lesson="L", quiz={"draft": ["mine"]},
                     cards=[card("q1", "2026-10-03"), card("q2", "2026-10-03"), card("new", "2026-10-04")])
    mine = {"date": "2026-10-03", "topic": "cosmos", "reflection": "",
            "lessons": [curriculum.new_slot("cosmos", 3), mine_slot]}
    phone_slot = dict(curriculum.new_slot("cosmos", 4), lesson="L", quiz={"draft": []},
                      cards=[card("q1", "2026-10-03", box=1)])          # q1 graded, q2 deleted on the phone
    stored = {"date": "2026-10-03", "topic": "cosmos", "reflection": "written on the phone",
              "lessons": [dict(curriculum.new_slot("cosmos", 3), completed=True), phone_slot]}
    curriculum.merge_day(mine, stored, [4], today)
    four = mine["lessons"][1]
    assert four is mine_slot and four["quiz"] == {"draft": ["mine"]}           # this page's answers
    assert [(c["id"], c["box"]) for c in four["cards"]] == [("q1", 1), ("new", 0)]
    assert mine["lessons"][0]["completed"] and mine["reflection"] == "written on the phone"


def test_a_save_from_an_old_copy_never_undoes_a_pass_made_elsewhere():
    """ISS-025: two tabs on lesson 2's quiz; she passes it on B; on A she
    changes an answer, and A's old copy of the day overwrote the pass."""
    from datetime import date
    today = date(2026, 10, 4)
    old = dict(curriculum.new_slot("cosmos", 2), lesson="L", quiz={"attempts": 0, "draft": ["a"]})
    mine = {"date": "2026-10-04", "topic": "cosmos", "completed": False, "reflection": "",
            "lessons": [dict(curriculum.new_slot("cosmos", 1), lesson="L", completed=True), old]}
    passed = dict(curriculum.new_slot("cosmos", 2), lesson="L", completed=True, quiz={"attempts": 1, "score": 90})
    stored = {"date": "2026-10-04", "topic": "cosmos", "completed": True, "reflection": "from B",
              "lessons": [dict(curriculum.new_slot("cosmos", 1), lesson="L", completed=True), passed]}
    curriculum.merge_day(mine, stored, [1, 2], today, recount=True)
    assert mine["lessons"][1] is old and old["completed"] and old["quiz"]["score"] == 90     # B's pass stays
    assert mine["completed"] and mine["reflection"] == "from B"
    # and her own newer work still goes in: a quiz answered here, not yet elsewhere
    ahead = dict(curriculum.new_slot("cosmos", 3), lesson="L", quiz={"attempts": 1})
    behind = dict(curriculum.new_slot("cosmos", 3), lesson="L", quiz={"attempts": 0})
    mine2 = {"date": "d", "topic": "cosmos", "lessons": [ahead]}
    curriculum.merge_day(mine2, {"date": "d", "topic": "cosmos", "lessons": [behind]}, [3], today)
    assert mine2["lessons"][0]["quiz"] == {"attempts": 1}


def test_thoughts_saved_from_progress_keep_what_was_saved_since():
    """ISS-025 (b): Progress → a day → Save my thoughts wrote the session's
    old copy of that day, losing a carried lesson's pass and its cards."""
    from datetime import date
    mine = {"date": "2026-10-01", "topic": "cosmos", "reflection": "my thoughts",
            "lessons": [dict(curriculum.new_slot("cosmos", 4), lesson="L")]}
    stored = {"date": "2026-10-01", "topic": "cosmos", "reflection": "",
              "lessons": [dict(curriculum.new_slot("cosmos", 4), lesson="L", passed_on="2026-10-03",
                               cards=[{"id": "c"}])]}
    curriculum.merge_day(mine, stored, [], date(2026, 10, 4), keep=("reflection",))
    assert mine["reflection"] == "my thoughts"
    assert mine["lessons"][0]["passed_on"] == "2026-10-03" and mine["lessons"][0]["cards"] == [{"id": "c"}]



def test_cards_made_by_a_quiz_submitted_after_midnight_are_kept():
    """ISS-028: the page (opened on the 3rd) made its cards dated the 3rd; the
    save compared them with the clock (the 4th) and dropped them all."""
    from datetime import date
    opened = date(2026, 10, 3)
    made = {"id": "q", "kind": "question", "added": "2026-10-03"}
    mine = {"date": "2026-10-03", "topic": "cosmos", "lessons": [dict(curriculum.new_slot("cosmos", 1), lesson="L",
                                                                      quiz={"attempts": 1}, cards=[made])]}
    stored = {"date": "2026-10-03", "topic": "cosmos", "lessons": [dict(curriculum.new_slot("cosmos", 1), lesson="L")]}
    curriculum.merge_day(mine, stored, [1], opened)
    assert mine["lessons"][0]["cards"] == [made]
    # work a save failed on (since None): every card the store doesn't have
    mine2 = {"date": "2026-10-01", "topic": "cosmos", "lessons": [dict(curriculum.new_slot("cosmos", 1), lesson="L",
                                                                       cards=[dict(made, added="2026-10-01")])]}
    stored2 = {"date": "2026-10-01", "topic": "cosmos", "lessons": [dict(curriculum.new_slot("cosmos", 1), lesson="L")]}
    curriculum.merge_day(mine2, stored2, [1], None)
    assert [c["id"] for c in mine2["lessons"][0]["cards"]] == ["q"]


def test_a_card_deleted_in_another_tab_isnt_brought_back_by_a_merge():
    """ISS-032: tab A holds lesson 1's word card (made today); tab B deletes
    it; A's quiz sheet saves the day and the card came back."""
    from datetime import date
    from coach import review
    card = {"id": "w1", "kind": "word", "added": "2026-10-04"}
    in_b = dict(curriculum.new_slot("cosmos", 1), lesson="L", completed=True, cards=[dict(card)])
    review.remove(in_b, "w1")
    stored = {"date": "2026-10-04", "topic": "cosmos",
              "lessons": curriculum.parse_slots([in_b])}                   # as saved and read back
    mine = {"date": "2026-10-04", "topic": "cosmos",
            "lessons": [dict(curriculum.new_slot("cosmos", 1), lesson="L", completed=True, cards=[dict(card)])]}
    curriculum.merge_day(mine, stored, [1], date(2026, 10, 4))
    assert mine["lessons"][0]["cards"] == [] and mine["lessons"][0]["removed"] == ["w1"]
    curriculum.merge_day(mine, stored, [1], None)                          # nor from a day a save failed on
    assert mine["lessons"][0]["cards"] == []
