"""The site in her language (coach/i18n.py, ISS-108): every sentence the
code shows has a translation in each language offered, with the same
{parts} and tags; dates, numbers and plurals read right; her choice is
kept with her preferences; the model is asked to write in it; and every
page loads in it."""
import json
import sys
from datetime import date
from pathlib import Path

import pytest

from coach import i18n, prefs
from test_pages_smoke import PAGES, app, loads

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import i18n as tool  # noqa: E402  (tools/i18n.py)

OTHER = [c for c in i18n.offered() if c != i18n.DEFAULT]


def test_the_languages_planned_and_offered():
    assert len(i18n.LANGS) == 16 and {"en", "zh-Hant", "zh-Hans", "hi", "es", "ar"} <= set(i18n.LANGS)
    assert i18n.offered()[0] == "en" and "zh-Hant" in i18n.offered()
    assert i18n.rtl("ar") and i18n.rtl("ur") and not i18n.rtl("zh-Hant")


@pytest.mark.parametrize("code", OTHER)
def test_every_sentence_is_translated_with_its_parts_and_tags(code):
    every = tool.sentences()
    have = i18n.catalog(code)
    missing = [k for k in every if k not in have]
    assert not missing, f"{code}: {len(missing)} missing, e.g. {missing[:5]}"
    assert tool.problems(code) == []


def test_a_sentence_falls_back_to_english_and_fills_its_parts():
    assert i18n.tr_in("zh-Hant", "Take the quiz") == "開始測驗"
    assert i18n.tr_in("zh-Hant", "No such sentence {n}", n=3) == "No such sentence 3"
    assert i18n.tr_in("en", "{done} of {written} lessons", done=2, written=9) == "2 of 9 lessons"
    assert i18n.tr_in("zh-Hant", "Lesson {n}: {title}", n=4, title="X") == "第 4 課：X"


def test_plurals_and_dates():
    assert i18n.trn("{n} lesson passed", "{n} lessons passed", 1) == "1 lesson passed"
    assert i18n.trn("{n} lesson passed", "{n} lessons passed", 3) == "3 lessons passed"
    d = date(2026, 10, 14)
    assert i18n.day_long(d) == "Wednesday, October 14" and i18n.day_short(d) == "Oct 14"
    assert i18n.relative_day(d, d) == "Today"


def test_her_browser_or_a_stored_choice_finds_the_nearest_language():
    assert i18n.match("zh-TW") == "zh-Hant" and i18n.match("zh_HK") == "zh-Hant"
    assert i18n.match("en-GB") == "en" and i18n.match("") == "en" and i18n.match(None) == "en"
    assert i18n.match("xx-YY") == "en"


def test_her_choice_is_kept_with_her_preferences():
    assert prefs.normalize({"language": "zh-Hant"})["language"] == "zh-Hant"
    assert prefs.normalize({"language": "klingon"})["language"] == ""
    assert prefs.blank()["language"] == ""


def test_the_model_writes_in_her_language():
    from coach import core, quiz
    system = core.load_system_prompt("philosophy", public=True)
    assert i18n.for_model(system, "en") == system
    zh = i18n.for_model(system, "zh-Hant")
    assert "Traditional Chinese" in zh and "【Topic】" in zh and "課程全部用英文寫" not in zh
    assert "LANGUAGE:" in zh and "Beginner" in zh
    q = i18n.for_model(quiz.SYSTEM, "zh-Hant")
    body = q.split("LANGUAGE:")[0]
    assert "in English" not in body and "in Traditional Chinese" in body


def test_a_lesson_written_in_her_language_keeps_the_markers_the_app_reads():
    from coach import lesson_view
    text = "【Topic】: 斯多葛 · Beginner\n【Key Idea】: 控制二分法。\n【Deep Dive】: 細節。"
    parts, level, _ = lesson_view.sections(text)
    assert level == "Beginner" and [h for h, _ in parts] == ["Key Idea", "Deep Dive"]
    assert i18n.tr_in("zh-Hant", "Key Idea") == "核心概念"


@pytest.mark.parametrize("code", OTHER)
def test_every_page_loads_in_each_language(monkeypatch, tmp_path, code):
    monkeypatch.setattr(i18n, "match", lambda asked: code)       # her browser asks for it, from the first run
    at = app(monkeypatch, tmp_path)
    for page in PAGES:
        loads(at, page)
    loads(at, "views/course.py", subject="philosophy")
    loads(at, "views/math.py")
    shown = json.dumps([str(m.value) for m in at.markdown], ensure_ascii=False)
    assert "數學" in shown or "課綱" in shown or code != "zh-Hant"


def test_the_language_picker_in_goals_and_settings(monkeypatch, tmp_path):
    # covers: W-ui-key
    at = loads(app(monkeypatch, tmp_path), "views/settings.py")
    pick = next(s for s in at.selectbox if s.key == "set_language")
    pick.set_value("zh-Hant").run()
    assert not at.exception and at.session_state["lang"] == "zh-Hant"
    assert at.session_state["coach_prefs"]["language"] == "zh-Hant"
    assert any("目標與設定" in str(m.value) for m in at.markdown)
