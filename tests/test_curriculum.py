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
        {"n": 2, "title": "", "unit": "", "kickoff": "", "lesson": "", "followups": [], "completed": False}]


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
