"""Stage 1 of the audit plan: her turns move with study, not the calendar
(a goal added comes right after the one she studied last; Your days keeps
that one last); and the AI allowance holds when it can't be read."""
from datetime import timedelta, timezone

from coach import catalog, clock, settings
from test_goal_pages import has, stored
from test_goals import a_path
from test_pages_smoke import app, loads


def studied(log, day, topic):
    log["entries"].append({"date": day.isoformat(), "topic": topic, "lessons": [{"n": 1, "completed": True}]})


def test_a_goal_added_comes_right_after_the_one_studied_last():
    a, b, new = a_path(title="A"), a_path(title="B"), a_path(title="New")
    catalog.use([a, b, new])
    today = clock.today()
    s = dict(settings.blank("u"), subjects=[a["id"], b["id"]], onboarded_at="2026-09-01T01:00:00+00:00")
    log = {"entries": []}
    studied(log, today - timedelta(days=3), a["id"])          # then days off: B is next
    assert settings.topic_for(s, today, timezone.utc, log) == b["id"]
    s2 = settings.add_goal(s, new["id"], "now", today, timezone.utc, log)
    assert [t for _, t in settings.days_ahead(s2, today, timezone.utc, log)] == [new["id"], b["id"], a["id"]]
    studied(log, today, b["id"])                               # today taken: the new goal tomorrow
    s3 = settings.add_goal(s, new["id"], "now", today + timedelta(days=1), timezone.utc, log)
    assert settings.topic_for(s3, today, timezone.utc, log) == b["id"]
    assert settings.topic_for(s3, today + timedelta(days=1), timezone.utc, log) == new["id"]


def test_your_days_keeps_the_one_studied_last_at_the_end(monkeypatch, tmp_path):
    import seed_history
    a, b, c = a_path(title="A"), a_path(title="B"), a_path(title="C")
    catalog.use([a, b, c])
    entries = seed_history.build(clock.today() - timedelta(days=1), days=1, topics=(a["id"],))   # A, two days ago
    at = app(monkeypatch, tmp_path, subjects=(a["id"], b["id"], c["id"]), paths=[a, b, c], entries=entries)
    loads(at, "views/settings.py")
    assert not has(at, "setday_up_2") and "studied last" in " ".join(str(h.proto) for h in at.get("html"))
    at.button(key="setday_down_0").click().run()               # B and C swap; A stays last
    s, log = stored(tmp_path)
    catalog.use(log["paths"])
    order = [t for _, t in settings.days_ahead(s, clock.today(), timezone.utc, log)]
    assert order == [c["id"], b["id"], a["id"]]


def test_every_ai_call_says_how_long_she_waited_and_how_it_ended(monkeypatch, caplog):
    import logging
    import types
    from coach import llm
    reply = types.SimpleNamespace(usage=types.SimpleNamespace(total_tokens=10), choices=[types.SimpleNamespace(
        message=types.SimpleNamespace(content='{"ok": 1}'), finish_reason="stop")])
    ok = types.SimpleNamespace(chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=lambda **k: reply)))
    monkeypatch.setattr(llm, "get_client", lambda: ok)
    with caplog.at_level(logging.INFO, logger=llm.logger.name):
        assert llm.ask_json("s", [{"role": "user", "content": "q"}]) == ({"ok": 1}, None)

    def refuse(**k):
        raise RuntimeError("bad request")
    monkeypatch.setattr(llm, "get_client",
                        lambda: types.SimpleNamespace(chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=refuse))))
    with caplog.at_level(logging.INFO, logger=llm.logger.name):
        llm.ask_json("s", [{"role": "user", "content": "q"}])
    lines = [r.getMessage() for r in caplog.records if r.getMessage().startswith("ai_call ")]
    assert lines[0].startswith("ai_call outcome=ok wait_s=") and "outcome=failed" in lines[-1]
