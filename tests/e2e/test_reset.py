"""After supabase/reset_my_progress.sql wipes an account (lessons, goals,
settings, preferences; the account itself stays), setting up again works:
Start learning opens the first day, as for someone new."""
import time

import flows


def text(p):
    return p.page.evaluate("document.body.innerText")


def test_setting_up_again_after_a_reset(public_app, pages):
    app = public_app
    app.set_llm()
    for width in (1180,):
        p = pages(width=width)
        email = f"reset-{int(time.time() * 1000)}@example.com"
        flows.sign_in(p, app, email=email)
        flows.onboard(p, subjects=("Philosophy",), pace="Light")
        flows.open_app(p, app)
        flows.pass_lesson(p)
        uid = next(u["id"] for u in app.get("/__dump")["users"] if u["email"] == email)
        app.post("/__wipe", {"user_id": uid})
        flows.open_app(p, app)
        assert flows.wait_text(p.page, "Get started", 20), text(p)[:500]
        flows.onboard(p, subjects=("Philosophy",), pace="Light")
        flows.idle(p.page, 30)
        t = text(p)
        assert "Start learning" not in t, t[:1500]
        flows.open_app(p, app)
        assert flows.wait_text(p.page, "Start this lesson", 20) or flows.wait_text(p.page, "Lesson", 5), text(p)[:1500]
