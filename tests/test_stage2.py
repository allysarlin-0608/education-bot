"""Stage 2 of the audit plan: "Report a problem" on a lesson or a quiz
question (what is sent, the review card that goes, the admin's numbers)."""
import json
from datetime import date, timedelta

from coach import reports, review, ui
from test_goal_pages import texts
from test_pages_smoke import app


def test_a_report_is_checked_before_it_is_kept():
    r = reports.make("philosophy", 3, "Plato's cave", "question", "wrong", "Which is true?" * 100, " too long? ")
    assert r["excerpt"] == ("Which is true?" * 100)[:600] and r["note"] == "too long?"
    assert reports.make("philosophy", 3, "", "question", "spam") is None
    assert reports.make("", 3, "", "lesson", "wrong") is None
    assert reports.make("philosophy", 0, "", "lesson", "wrong") is None


def test_the_admins_numbers_say_how_often_and_never_who():
    rows = [dict(reports.make("cosmos", 1, "Tides", "lesson", "wrong"), user_id="u1", at="2026-10-02T01:00:00+00:00"),
            dict(reports.make("cosmos", 2, "Moon", "question", "unclear", "Why?"), user_id="u2", at="2026-10-05T01:00:00+00:00"),
            dict(reports.make("cosmos", 2, "Moon", "question", "wrong", "Why?"), user_id="u2", at="2026-09-01T01:00:00+00:00")]
    s = reports.summarize(rows, date(2026, 10, 1), lessons_passed=40)
    assert s["reports"] == 2 and s["by_reason"] == {"wrong": 1, "unclear": 1}
    assert [x["lesson_title"] for x in s["recent"]] == ["Moon", "Tides"] and all("user_id" not in x for x in s["recent"])
    assert reports.per_hundred(s) == 5.0 and reports.per_hundred(dict(s, lessons_passed=0)) is None


def test_a_reported_question_never_becomes_a_review_card():
    slot = {"n": 4}
    item = {"type": "short", "question": "Why is the sky blue?", "answer": "Scattering.", "why": ""}
    q = {"questions": [item], "marks": [0]}
    assert review.add_missed(dict(slot), q, date(2026, 10, 1), "cosmos") == 1
    review.drop_question(slot, "cosmos", "Why is the sky blue?")
    assert review.add_missed(slot, q, date(2026, 10, 2), "cosmos") == 0, "reported: never made again"


def _today_failed_quiz():
    import seed_history
    entries = seed_history.build(ui.today() + timedelta(days=1), days=1, topics=("philosophy",), partial=())
    e = entries[0]
    e["completed"] = False
    for s in e["lessons"]:
        s["completed"] = False
        s.pop("quiz", None)
    e["lessons"][0]["quiz"] = seed_history._quiz("v2-1a2b3c4d", 5)            # marked: 50%, not passed
    return entries


def test_reporting_from_home_the_lesson_and_a_question(monkeypatch, tmp_path):
    # covers: W-report_ui-menu, W-report_ui-menu-2, W-report_ui-why, W-report_ui-note, W-report_ui-send, W-report_ui-which
    at = app(monkeypatch, tmp_path, subjects=("philosophy",), entries=_today_failed_quiz())
    lesson_key = next(r.key for r in at.radio if r.key.startswith("rep_lesson_"))[:-len("_why")]
    at.radio(key=f"{lesson_key}_why").set_value("unclear").run()
    at.text_input(key=f"{lesson_key}_note").input("The second part lost me").run()
    at.button(key=f"{lesson_key}_send").click().run()
    assert "Thanks. We'll check it." in texts(at)
    sent = json.loads((tmp_path / "content_reports.json").read_text())
    rows = sent if isinstance(sent, list) else next(iter(sent.values()))
    assert rows[-1]["kind"] == "lesson" and rows[-1]["reason"] == "unclear" and rows[-1]["note"] == "The second part lost me"
    # a question, from what she missed: sent, and its card is gone for good
    qkey = next(r.key for r in at.radio if r.key.startswith("rep_q_"))[:-len("_why")]
    at.selectbox(key=f"{qkey}_which").set_value(2).run()
    at.radio(key=f"{qkey}_why").set_value("wrong").run()
    at.button(key=f"{qkey}_send").click().run()
    sent = json.loads((tmp_path / "content_reports.json").read_text())
    rows = sent if isinstance(sent, list) else next(iter(sent.values()))
    assert rows[-1]["kind"] == "question" and rows[-1]["excerpt"] == "Seeded question 3?"
    log = json.loads((tmp_path / "log.json").read_text())
    slot = log["entries"][0]["lessons"][0]
    assert review.question_card_id("philosophy", slot["n"], "Seeded question 3?") in slot.get("removed", [])
