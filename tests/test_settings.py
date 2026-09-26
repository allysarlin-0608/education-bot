import json
from datetime import date, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from coach import core, curriculum, placement, settings, storage

TZ = ZoneInfo("Asia/Taipei")


def done(subjects, pace=3, levels=None, reading=False, when="2026-09-26T02:00:00+00:00"):
    s = settings.blank("u1")
    d = dict(settings.new_draft(), subjects=subjects, units_per_day=pace, reading_enabled=reading)
    for t, lv in (levels or {}).items():
        d["levels"][t] = {"way": "placement", "answers": [], "level": lv, "score": 3}
    return settings.finish(s, d, when)


def test_subjects_take_turns_in_the_order_chosen_from_setup_day():
    s = done(["philosophy", "investing", "fashion"])
    day1 = date(2026, 9, 26)       # 10:00 in Taipei
    got = [settings.topic_for(s, day1 + timedelta(days=k), TZ) for k in range(5)]
    assert got == ["philosophy", "investing", "fashion", "philosophy", "investing"]


def test_one_subject_every_day():
    s = done(["cosmos"])
    assert {settings.topic_for(s, date(2026, 9, 26) + timedelta(days=k), TZ) for k in range(9)} == {"cosmos"}


def test_rotation_follows_a_new_selection():
    s = done(["philosophy", "investing", "fashion"])
    s2 = settings.change(s, settings.now_iso(), subjects=["philosophy", "fashion"])
    assert [settings.topic_for(s2, date(2026, 9, 26) + timedelta(days=k), TZ) for k in range(3)] == \
        ["philosophy", "fashion", "philosophy"]


def test_setup_day_is_her_local_day():
    # 17:00 UTC on the 25th is already the 26th in Taipei
    s = done(["cosmos", "fashion"], when="2026-09-25T17:00:00+00:00")
    assert settings.start_day(s, TZ) == date(2026, 9, 26)
    assert settings.start_day(s, timezone.utc) == date(2026, 9, 25)


def test_legacy_keeps_the_weekday_schedule_five_lessons_and_reading():
    s = settings.legacy("u1")
    assert settings.onboarded(s) and settings.reading_on(s) and settings.units(s) == 5
    for k in range(7):
        day = date(2026, 9, 21) + timedelta(days=k)
        assert settings.topic_for(s, day, TZ) == core.scheduled_topic(day)
    assert settings.shown_subjects(s) == list(settings.SUBJECTS)


def test_finish_validates_and_never_saves_half_done():
    s = settings.blank("u1")
    with pytest.raises(ValueError):
        settings.finish(s, settings.new_draft(), "t")                 # no subjects
    d = dict(settings.new_draft(), subjects=["cosmos"])
    d["levels"]["cosmos"] = {"way": "placement", "answers": [1, 1], "level": None}
    with pytest.raises(ValueError):
        settings.finish(s, d, "t")                                    # placement unfinished
    d["levels"]["cosmos"] = {"way": "basics"}
    out = settings.finish(s, d, "t")
    assert out["onboarded_at"] == out["updated_at"] == "t" and out["onboarding"] is None
    assert out["subject_levels"] == {"cosmos": "Beginner"} and not settings.errors(out)


def test_levels_are_per_subject():
    s = done(["philosophy", "cosmos"], levels={"cosmos": "Advanced"})
    assert s["subject_levels"] == {"philosophy": "Beginner", "cosmos": "Advanced"}
    d = dict(settings.new_draft(), subjects=["philosophy", "cosmos"])
    assert settings.draft_levels(d) == {"philosophy": "Beginner", "cosmos": "Beginner"}


def test_toggle_keeps_order_and_caps_at_three():
    s = []
    for t in ("fashion", "cosmos", "free", "jewelry"):
        s = settings.toggle_subject(s, t)
    assert s == ["fashion", "cosmos", "free"]
    assert settings.toggle_subject(s, "cosmos") == ["fashion", "free"]


def test_change_keeps_levels_and_starts_new_subjects_at_beginner():
    s = done(["philosophy"], levels={"philosophy": "Advanced"})
    s2 = settings.change(s, "t2", subjects=["cosmos"])
    s3 = settings.change(s2, "t3", subjects=["cosmos", "philosophy"], units_per_day=5)
    assert s3["subject_levels"] == {"philosophy": "Advanced", "cosmos": "Beginner"}
    assert s3["units_per_day"] == 5 and s3["onboarded_at"] == s["onboarded_at"] and s3["updated_at"] == "t3"
    with pytest.raises(ValueError):
        settings.change(s, "t", subjects=[])
    with pytest.raises(ValueError):
        settings.change(s, "t", units_per_day=2)


def test_normalize_ignores_bad_values_and_other_users():
    row = {"user_id": "u1", "subjects": ["cosmos", "nope", "cosmos"], "units_per_day": 4,
           "subject_levels": {"cosmos": "Expert"}, "reading_enabled": 1}
    s = settings.normalize(row, "u1")
    assert s["subjects"] == ["cosmos"] and s["units_per_day"] == 3 and s["subject_levels"] == {}
    assert s["reading_enabled"] is True
    assert settings.normalize(row, "someone-else") == settings.blank("someone-else")


def test_draft_is_checked():
    s = dict(settings.blank("u1"), onboarding={"step": 9, "subjects": ["cosmos", "x"], "units_per_day": 1,
                                               "reading_enabled": True})
    d = settings.draft_of(s)
    assert d["step"] == 5 and d["subjects"] == ["cosmos"] and d["units_per_day"] == 1 and d["reading_enabled"]


def test_placement_rules():
    assert [placement.level_for(n) for n in range(6)] == \
        ["Beginner", "Beginner", "Beginner", "Intermediate", "Intermediate", "Advanced"]
    for topic in settings.SUBJECTS:
        qs = placement.questions(topic)
        assert len(qs) == placement.COUNT
        assert all(len(opts) == 4 and 0 <= right < 4 and len(set(opts)) == 4 for _, opts, right in qs)
        assert placement.score(topic, [r for _, _, r in qs]) == 5
        assert placement.score(topic, [None] * 5) == 0


def test_every_offered_subject_has_a_syllabus_and_a_description():
    for t in settings.SUBJECTS:
        assert curriculum.has_syllabus(t) and settings.DESCRIPTIONS[t] and t in core.TOPICS


def test_file_store_keeps_each_user_apart(tmp_path):
    store = storage.FileStore(tmp_path / "log.json", settings_path=tmp_path / "settings.json")
    assert store.load_settings("a") is None
    store.save_settings("a", dict(settings.blank("a"), subjects=["cosmos"]))
    store.save_settings("b", dict(settings.blank("b"), subjects=["fashion"], legacy=True))
    store.save_settings("a", dict(settings.blank("a"), subjects=["free"]))
    assert store.load_settings("a")["subjects"] == ["free"]
    assert store.load_settings("b")["subjects"] == ["fashion"]
    rows = json.loads((tmp_path / "settings.json").read_text())["user_settings"]
    assert len(rows) == 2 and all("legacy" not in r for r in rows)


class Resp:
    def __init__(self, status, body=None):
        self.status_code, self._body, self.text = status, body, json.dumps(body)

    def json(self):
        return self._body


class Session:
    def __init__(self, *responses):
        self.responses, self.calls = list(responses), []

    def request(self, method, url, params=None, json=None, headers=None, timeout=None):
        self.calls.append((method, url, params, json))
        return self.responses.pop(0)


def test_supabase_reads_and_writes_settings_by_user_id():
    session = Session(Resp(200, [{"user_id": "u1", "subjects": ["cosmos"]}]), Resp(201))
    store = storage.SupabaseStore("https://x.supabase.co", "sb_secret_k", session=session)
    assert store.load_settings("u1")["subjects"] == ["cosmos"]
    store.save_settings("u1", dict(settings.blank("u1"), subjects=["free"], legacy=True))
    (m1, url1, p1, _), (m2, url2, p2, body) = session.calls
    assert url1.endswith("/user_settings") and p1["user_id"] == "eq.u1"
    assert m2 == "POST" and p2 == {"on_conflict": "user_id"} and body[0]["user_id"] == "u1"
    assert "legacy" not in body[0] and body[0]["subjects"] == ["free"]


def test_supabase_without_the_table_keeps_the_old_setup():
    store = storage.SupabaseStore("https://x.supabase.co", "sb_secret_k", session=Session(Resp(404, {})))
    assert store.load_settings("u1") is None and store.settings_missing


def _log_with_day(slots):
    return {"entries": [{"date": "2026-09-26", "topic": "cosmos", "lessons": slots}], "books": []}


def test_pace_change_keeps_lessons_begun_and_follows_the_new_count():
    begun = dict(curriculum.new_slot("cosmos", 1), lesson="text")
    untouched = [curriculum.new_slot("cosmos", n) for n in (2, 3)]
    log = _log_with_day([begun, *untouched])
    entry = log["entries"][0]
    five = curriculum.day_plan(log, "cosmos", entry, 5)
    assert [s["n"] for s in five] == [1, 2, 3, 4, 5] and five[0] is begun
    one = curriculum.day_plan(log, "cosmos", entry, 1)
    assert [s["n"] for s in one] == [1] and one[0] is begun
    fresh = curriculum.day_plan({"entries": [], "books": []}, "cosmos", None, 3)
    assert [s["n"] for s in fresh] == [1, 2, 3]


def test_a_finished_day_stays_as_it_was():
    done_slot = dict(curriculum.new_slot("cosmos", 1), lesson="text", completed=True)
    log = _log_with_day([done_slot])
    assert [s["n"] for s in curriculum.day_plan(log, "cosmos", log["entries"][0], 5)] == [1]


def test_starting_level_raises_a_lesson_never_lowers_it():
    assert core.lesson_level(1) == "Beginner"
    assert core.lesson_level(1, "Intermediate") == "Intermediate"
    assert core.lesson_level(2500, "Beginner") == "Advanced"
    slot = curriculum.new_slot("cosmos", 1)
    ctx = core.build_history_context({"entries": [], "books": []}, "cosmos", date(2026, 9, 26), slot, "Advanced")
    assert "Advanced" in ctx and "起始程度" in ctx
