"""Settings: subjects, pace, starting level, reading, invites (admins),
your data (download, delete), and that each change reaches the other pages
and the database."""
import itertools
import json
import time

import pytest

import flows
from conftest import ADMIN, covers

_n = itertools.count()


def person(app, pages, width=1440, email=None, **onboard):
    p = pages(width=width)
    email = email or f"set{next(_n)}-{int(time.time() * 1000)}@example.com"
    flows.sign_in(p, app, email=email)
    if flows.wait_text(p.page, "Get started", 3):      # (an account used before is already set up)
        flows.onboard(p, **onboard)
    flows.open_app(p, app, "/settings")
    return p, email


def text(p):
    return p.page.evaluate("document.body.innerText")


def dump_user(app, email):
    d = app.get("/__dump")
    uid = next((u["id"] for u in d["users"] if u["email"] == email), None)
    return d, uid


def settings_row(app, email):
    d, uid = dump_user(app, email)
    return next(r for r in d["tables"]["user_settings"] if r["user_id"] == uid)


def pick(p, scope, name):
    flows.tap(p, p.page.locator(scope).get_by_role("button", name=name, exact=False).first)
    flows.idle(p.page)


def test_pace_changes_today(public_app, pages):
    covers("D-settings-save_settings", "D-ui-save_settings")
    app = public_app
    p, email = person(app, pages)
    pick(p, ".st-key-set_sec_pace", "Focused")
    assert settings_row(app, email)["units_per_day"] == 5
    flows.go(p, app, "Today")
    assert flows.wait_text(p.page, "Lesson 1 of 5"), "Today follows the new pace"


def test_subjects_add_remove_and_keep_one(public_app, pages):
    covers("W-choices-pick", "D-settings-save_settings")
    app = public_app
    p, email = person(app, pages)
    pick(p, ".st-key-set_sec_subjects", "Astronomy")
    assert settings_row(app, email)["subjects"] == ["philosophy", "cosmos"]
    assert flows.wait_text(p.page, "Your existing learning history will be preserved.")
    pick(p, ".st-key-set_sec_subjects", "Philosophy")
    assert settings_row(app, email)["subjects"] == ["cosmos"]
    pick(p, ".st-key-set_sec_subjects", "Astronomy")          # the last one can't go
    assert flows.wait_text(p.page, "Keep at least one subject.")
    assert settings_row(app, email)["subjects"] == ["cosmos"]
    flows.go(p, app, "Today")
    assert flows.wait_text(p.page, "Astronomy"), "Today's subject follows the change"


def test_retake_placement_and_cancel(public_app, pages):
    covers("W-settings-setretake", "W-settings-setcancel", "W-choices-pqnext", "W-choices-pqagain")
    app = public_app
    p, email = person(app, pages)
    flows.button(p, "Retake placement quiz")
    assert flows.wait_text(p.page, "QUESTION 1 OF 5")
    flows.button(p, "Cancel")
    assert "QUESTION 1 OF 5" not in text(p)
    assert settings_row(app, email)["subject_levels"].get("philosophy") in (None, "Beginner")
    flows.button(p, "Retake placement quiz")
    answers = ["Epistemology", "Valid", "Marcus Aurelius",                    # three right,
               "a virtuous person would follow", "God's plan for each person"]  # two wrong
    for k in range(5):
        pick(p, ".st-key-set_sec_level", answers[k])
        flows.button(p, "See my level" if k == 4 else "Next question")
    assert flows.wait_text(p.page, "Philosophy now starts at Intermediate (3 of 5 right).")
    assert settings_row(app, email)["subject_levels"]["philosophy"] == "Intermediate"


def test_reading_toggle_adds_and_removes_the_page(public_app, pages):
    covers("W-settings-set_reading", "W-records-views_reading_py")
    app = public_app
    p, email = person(app, pages)
    assert "Reading" not in p.page.locator(".st-key-topnav").inner_text()
    p.page.locator('.st-key-set_sec_reading [role="switch"], .st-key-set_sec_reading input').first.check(force=True)
    flows.idle(p.page)
    assert settings_row(app, email)["reading_enabled"] is True
    assert flows.wait_text(p.page, "Reading", 5) and "Reading" in p.page.locator(".st-key-topnav").inner_text()
    flows.go(p, app, "Progress")
    p.page.get_by_role("radio", name="Subjects").or_(p.page.get_by_role("button", name="Subjects", exact=True)).first.click()
    flows.idle(p.page)
    flows.tap(p, p.page.get_by_role("link", name="Reading · 0 books finished"))
    flows.idle(p.page)
    assert "/reading" in p.page.url
    flows.go(p, app, "Settings")
    p.page.locator('.st-key-set_sec_reading [role="switch"], .st-key-set_sec_reading input').first.uncheck(force=True)
    flows.idle(p.page)
    assert settings_row(app, email)["reading_enabled"] is False
    assert "Reading" not in p.page.locator(".st-key-topnav").inner_text()


def test_enter_a_world_from_settings(public_app, pages):
    covers("W-settings-set_world")
    app = public_app
    p, _ = person(app, pages)
    flows.button(p, "Enter Philosophy", exact=False)
    assert "subject=philosophy" in p.page.url


def test_invites_only_for_admins(public_app, pages):
    covers("W-settings-inv_email", "W-settings-inv_note", "W-settings-inv_add_btn", "W-settings-inv_rm",
           "D-settings-add_invite", "D-settings-remove_invite")
    app = public_app
    p, _ = person(app, pages)
    assert "Invites" not in text(p), "a learner sees no invite list"
    p.close()
    p, _ = person(app, pages, email=ADMIN)
    assert flows.wait_text(p.page, "Invites")
    box = p.page.locator(".st-key-inv_add")
    box.get_by_label("Email").fill("not an email")
    flows.button(p, "Invite")
    assert flows.wait_text(p.page, "That doesn't look like an email address.")
    new = f"friend{int(time.time() * 1000)}@Example.com"
    box.get_by_label("Email").fill(new)
    box.get_by_label("Note").fill("<b>cousin</b>")
    flows.button(p, "Invite")
    assert flows.wait_text(p.page, new.lower())
    assert p.page.locator(".st-key-set_sec_invites b b").count() == 0, "the note is text, not markup"
    rows = app.get("/__dump")["tables"]["allowed_users"]
    assert any(r["email"] == new.lower() and r["note"] == "<b>cousin</b>" for r in rows)
    slug = "".join(c if c.isalnum() else "_" for c in new.lower())
    flows.tap(p, p.page.locator(f".st-key-inv_rm_{slug} button"))
    flows.idle(p.page)
    assert not any(r["email"] == new.lower() for r in app.get("/__dump")["tables"]["allowed_users"])


def test_download_my_data_is_only_mine(public_app, pages):
    covers("W-settings-data_download")
    app = public_app
    other, _ = person(app, pages)
    flows.go(other, app, "Today")
    flows.start_lesson(other)
    other.close()
    p, email = person(app, pages)
    with p.page.expect_download() as dl:
        p.page.get_by_role("button", name="Download my data").click()
    data = json.loads(open(dl.value.path()).read())
    _, uid = dump_user(app, email)
    blob = json.dumps(data)
    others = [u["id"] for u in app.get("/__dump")["users"] if u["id"] != uid]
    assert not any(o in blob for o in others), "someone else's rows are in my download"
    assert email in blob


def test_delete_my_account_removes_everything(public_app, pages):
    covers("W-settings-data_delete", "W-settings-del_confirm", "W-settings-del_go", "W-settings-del_cancel",
           "D-settings-delete_my_account")
    app = public_app
    p, email = person(app, pages)
    flows.go(p, app, "Today")
    flows.start_lesson(p)
    flows.go(p, app, "Settings")
    flows.button(p, "Delete my account")
    assert flows.wait_text(p.page, "This permanently deletes your account")
    go = p.page.get_by_role("button", name="Delete everything")
    assert go.is_disabled()
    p.page.get_by_label("Type DELETE to confirm").fill("delete")
    p.page.keyboard.press("Tab")
    flows.idle(p.page)
    assert go.is_disabled(), "only DELETE, exactly, confirms"
    flows.button(p, "Cancel")
    assert "This permanently deletes" not in text(p)
    _, uid = dump_user(app, email)
    assert uid
    flows.button(p, "Delete my account")
    p.page.get_by_label("Type DELETE to confirm").fill("DELETE")
    p.page.keyboard.press("Tab")
    flows.idle(p.page)
    flows.button(p, "Delete everything")
    flows.idle(p.page, 40)
    assert flows.wait_text(p.page, "Your account and all your learning history have been deleted.", 20)
    d = app.get("/__dump")
    assert not any(u["email"] == email for u in d["users"])
    for table, rows in d["tables"].items():
        assert not any(r.get("user_id") == uid for r in rows), f"rows left in {table}"


def test_personal_mode_has_no_account_sections(personal_app, pages):
    covers("W-settings-data_download")
    app = personal_app
    p = pages(width=1440)
    flows.open_app(p, app, "/settings")
    if flows.wait_text(p.page, "Get started", 3):
        flows.onboard(p)
        flows.open_app(p, app, "/settings")
    t = text(p)
    assert "Settings" in t and "Your data" not in t and "Invites" not in t


@pytest.mark.parametrize("width", [390, 1024])
def test_settings_fit(public_app, pages, width):
    covers("W-settings-set_reading")
    app = public_app
    p, _ = person(app, pages, width=width)
    assert p.page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
