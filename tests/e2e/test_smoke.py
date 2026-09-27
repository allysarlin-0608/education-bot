"""Quick smoke test: `pytest tests/e2e -m smoke`."""
import pytest

import flows
from conftest import covers

pytestmark = pytest.mark.smoke


@pytest.mark.parametrize("mode", ["public", "personal"])
def test_new_person_learns_one_lesson(mode, pages, request):
    covers("W-setup-get_started", "W-daily-start_this_lesson", "W-daily-take_the_quiz", "AI-daily-stream_reply",
           "AI-daily-ask_json", "AI-daily-ask_json-2", "D-setup-save_settings-2", "D-daily-save_entry",
           # the servers are configured only through these, so both modes working covers them
           "S-supabase_url", "S-supabase_key", "S-coach_log_path", "S-coach_settings_path", "D-auth-touch_user")
    app = request.getfixturevalue(f"{mode}_app")
    if mode == "personal":              # the personal app has one person: start them afresh
        for f in ("learning_log.json", "user_settings.json"):
            (app.state / f).unlink(missing_ok=True)
    p = pages(width=1440)
    flows.sign_in(p, app, email=f"smoke-{mode}@example.com")
    assert flows.wait_text(p.page, "Get started"), "a new person starts with the setup"
    if mode == "public":        # signing in records who they are (public.users)
        d = app.get("/__dump")
        uid = next(u["id"] for u in d["users"] if u["email"] == "smoke-public@example.com")
        assert any(r["user_id"] == uid for r in d["tables"].get("users", [])), "no public.users row"
    flows.onboard(p)
    flows.open_app(p, app)
    flows.pass_lesson(p)
    assert flows.wait_text(p.page, "Next lesson"), "passing offers the next lesson"
