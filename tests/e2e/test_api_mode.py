"""The current site on our own backend (step M2), in a real browser: sign-in
is still the old one, but every read and write goes to our API and our
PostgreSQL, and nothing to Supabase's tables. A learner who isn't invited
in our database is stopped; an invited one sets up, passes a lesson, comes
back after a refresh to the same place; it is all in our tables."""
import time

import flows


def text(p):
    return p.page.evaluate("document.body.innerText")


def test_the_site_runs_on_our_backend(api_app, pages):
    app = api_app
    app.set_llm()
    email = f"api-{int(time.time() * 1000)}@example.com"
    p = pages(width=1180)
    flows.sign_in(p, app, email=email)
    assert flows.wait_text(p.page, "invitation", 20) or flows.wait_text(p.page, "invite", 5), \
        "invited in the old system only: our backend's list decides now"
    app.api_sql("insert into invites (email, note) values (:e, 'e2e')", e=email)
    flows.open_app(p, app)
    flows.onboard(p, subjects=("Philosophy",), pace="Light")
    flows.open_app(p, app)
    flows.pass_lesson(p)
    assert flows.wait_text(p.page, "Passed with")
    flows.open_app(p, app)                                      # a refresh: from our database
    assert flows.wait_text(p.page, "Today's done", 20) or flows.wait_text(p.page, "lesson", 5)
    users = app.api_sql("select id, email from users where email = :e", e=email)
    assert len(users) == 1
    uid = users[0]["id"]
    days = app.api_sql("select subject, completed from study_days where user_id = :u", u=uid)
    assert days == [{"subject": "philosophy", "completed": True}]
    quiz = app.api_sql("select q.score from quizzes q join day_lessons d on d.id = q.slot_id where d.user_id = :u", u=uid)
    assert quiz and quiz[0]["score"] == 100
    ev = app.api_sql("select e.kind from mastery_evidence e join day_lessons d on d.id = e.slot_id "
                     "where d.user_id = :u", u=uid)
    assert [e["kind"] for e in ev] == ["quiz"], "the skill map's evidence is in our tables"
    settings = app.api_sql("select units_per_day from user_settings where user_id = :u", u=uid)
    assert settings == [{"units_per_day": 1}]
    counts = {r["event"] for r in app.api_sql("select event from usage_events where user_id = :u", u=uid)}
    assert {"setup_done", "lesson_passed", "visit"} <= counts
    old = app.get("/__dump")["tables"].get("learning_entries", [])
    assert not [r for r in old if r.get("lessons")], "nothing written to the old system's tables"
    flows.go(p, app, "Record")
    assert flows.wait_text(p.page, "Lessons passed") and "Traceback" not in text(p)
