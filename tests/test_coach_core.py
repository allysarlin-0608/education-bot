from datetime import date

from coach import core

WED = date(2026, 9, 23)


def make_log(*entries):
    log = core.empty_log()
    for day, topic, completed in entries:
        e = core.start_entry(log, day, topic)
        e["completed"] = completed
    return log


def test_weekly_schedule():
    assert core.scheduled_topic(date(2026, 9, 21)) == "fashion"      # Mon
    assert core.scheduled_topic(date(2026, 9, 22)) == "philosophy"   # Tue
    assert core.scheduled_topic(WED) == "reading"
    assert core.scheduled_topic(date(2026, 9, 24)) == "cosmos"
    assert core.scheduled_topic(date(2026, 9, 25)) == "fashion"
    assert core.scheduled_topic(date(2026, 9, 26)) == "reading"
    assert core.scheduled_topic(date(2026, 9, 27)) == "free"
    assert core.weekday_zh(WED) == "星期三"


def test_levels_follow_part_six():
    assert [core.level_for_session(n) for n in (1, 3, 4, 7, 8, 20)] == [
        "入門", "入門", "中階", "中階", "進階", "進階"]


def test_session_number_is_per_topic():
    log = make_log(
        (date(2026, 9, 1), "philosophy", True),
        (date(2026, 9, 8), "philosophy", True),
        (date(2026, 9, 2), "reading", True),
    )
    assert core.topic_session_number(log, "philosophy", WED) == 3
    assert core.topic_session_number(log, "reading", WED) == 2
    assert core.topic_session_number(log, "cosmos", WED) == 1


def test_start_entry_is_idempotent_for_same_day():
    log = core.empty_log()
    a = core.start_entry(log, WED, "reading")
    b = core.start_entry(log, WED, "reading")
    assert a is b and len(log["entries"]) == 1


def test_streak_counts_through_yesterday_until_today_done():
    log = make_log(
        (date(2026, 9, 20), "free", True),
        (date(2026, 9, 21), "fashion", True),
        (date(2026, 9, 22), "philosophy", True),
        (WED, "reading", False),
    )
    assert core.current_streak(log, WED) == 3
    core.find_entry(log, WED, "reading")["completed"] = True
    assert core.current_streak(log, WED) == 4


def test_streak_resets_after_gap():
    log = make_log((date(2026, 9, 20), "free", True))
    assert core.current_streak(log, WED) == 0


def test_extract_section_handles_markdown():
    lesson = (
        "**【今日主題】**：哲學 — 控制二分法（入門）\n"
        "【核心概念】：重點。\n"
        "### 【延伸提問】：哪些是你能控制的？\n"
        "【小提醒】：很好。\n"
        "完成後記得打勾，連續完成比完美更重要。"
    )
    assert core.extract_section(lesson, "今日主題") == "哲學 — 控制二分法（入門）"
    assert core.extract_section(lesson, "延伸提問") == "哪些是你能控制的？"
    assert core.extract_section(lesson, "不存在") == ""


def test_history_context_mentions_past_and_gap():
    log = make_log((date(2026, 9, 9), "reading", True))
    e = log["entries"][0]
    e["title"] = "看書 — 《原子習慣》第一章（入門）"
    e["followup_question"] = "你最想養成哪個習慣？"
    e["reflection"] = "每天寫商業計劃"
    ctx = core.build_history_context(log, "reading", WED)
    assert "第 2 次" in ctx and "入門" in ctx
    assert "《原子習慣》" in ctx
    assert "每天寫商業計劃" in ctx
    assert "14 天" in ctx and "情境二" in ctx


def test_system_prompt_is_core_plus_one_topic():
    prompt = core.build_system_prompt(core.empty_log(), "free", date(2026, 9, 27))
    assert prompt.startswith("你是Allysa的專屬「每日興趣學習教練」")
    assert core.CLOSING_LINE in prompt
    assert "4.7 自由主題" in prompt
    assert "4.2 哲學" not in prompt and "4.3 看書" not in prompt   # only today's topic
    assert "過去七天各主題互動次數" in prompt


def test_log_round_trip(tmp_path):
    path = tmp_path / "log.json"
    log = make_log((WED, "cosmos", True))
    core.save_log(log, path)
    assert core.load_log(path) == log
    assert core.load_log(tmp_path / "missing.json") == core.empty_log()


def test_followup_prompt_relaxes_six_block_format():
    lesson_prompt = core.build_system_prompt(core.empty_log(), "reading", WED)
    followup_prompt = core.build_system_prompt(core.empty_log(), "reading", WED, followup=True)
    assert core.FOLLOWUP_NOTE not in lesson_prompt
    assert followup_prompt == f"{lesson_prompt}\n\n{core.FOLLOWUP_NOTE}"


def test_longest_streak_finds_best_run():
    log = make_log(
        (date(2026, 9, 1), "reading", True),
        (date(2026, 9, 2), "cosmos", True),
        (date(2026, 9, 3), "fashion", True),
        (date(2026, 9, 5), "free", True),
        (date(2026, 9, 6), "free", False),
    )
    assert core.longest_streak(log) == 3
    assert core.longest_streak(core.empty_log()) == 0


def test_topic_progress_levels():
    assert core.topic_progress(core.empty_log(), "cosmos") == {
        "sessions": 0, "completed": 0, "level": None,
        "next_level": "中階", "remaining": 3, "fraction": 0.0}
    log = make_log(*[(date(2026, 9, d), "philosophy", d % 2 == 0) for d in range(1, 6)])
    p = core.topic_progress(log, "philosophy")
    assert (p["sessions"], p["completed"], p["level"]) == (5, 2, "中階")
    assert (p["next_level"], p["remaining"], p["fraction"]) == ("進階", 2, 0.5)
    log = make_log(*[(date(2026, 9, d), "reading", True) for d in range(1, 9)])
    p = core.topic_progress(log, "reading")
    assert (p["level"], p["next_level"], p["remaining"], p["fraction"]) == ("進階", None, None, 1.0)


def test_calendar_weeks_statuses():
    log = make_log((date(2026, 9, 21), "fashion", True), (date(2026, 9, 22), "philosophy", False))
    weeks = core.calendar_weeks(log, WED, weeks=2)
    assert weeks[0][0][0] == date(2026, 9, 14)            # starts on a Monday
    statuses = {day: s for row in weeks for day, s in row}
    assert statuses[date(2026, 9, 21)] == "done"
    assert statuses[date(2026, 9, 22)] == "started"
    assert statuses[WED] == "none"
    assert statuses[date(2026, 9, 24)] == "future"
