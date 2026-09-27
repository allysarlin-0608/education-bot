"""Backup download and import (Progress → Backup and restore): validation,
safety, and that a failed import never loses the records already there."""
import json
import time

import flows
from conftest import covers


def setup_with_a_lesson(app, pages, tag):
    p = pages(width=1440)
    flows.sign_in(p, app, email=f"imp-{tag}-{int(time.time() * 1000)}@example.com")
    flows.onboard(p)
    flows.open_app(p, app)
    flows.start_lesson(p)
    return p


def open_backup(p, app):
    flows.go(p, app, "Progress")
    p.page.get_by_text("Backup and restore", exact=True).click()
    flows.idle(p.page)


def upload(p, tmp_path, name, data: bytes):
    f = tmp_path / name
    f.write_bytes(data)
    p.page.locator('[data-testid="stFileUploaderDropzoneInput"]').set_input_files(str(f))
    flows.idle(p.page)
    if p.page.get_by_role("button", name="Replace my records with this backup").count():
        flows.button(p, "Replace my records with this backup")
    flows.idle(p.page)
    return p.page.evaluate("document.body.innerText")


def entries_of(app, email):
    d = app.get("/__dump")
    uid = next(u["id"] for u in d["users"] if u["email"] == email)
    return [e for e in d["tables"]["learning_entries"] if e["user_id"] == uid]


def test_download_backup_has_my_lesson(public_app, pages, tmp_path):
    covers("W-records-download_a_backup")
    app = public_app
    p = setup_with_a_lesson(app, pages, "dl")
    open_backup(p, app)
    with p.page.expect_download() as dl:
        p.page.get_by_role("button", name="Download a backup").click()
    data = json.loads(open(dl.value.path()).read())
    assert data["entries"] and data["entries"][0]["lessons"][0]["lesson"]


def test_malformed_files_are_refused_kindly(public_app, pages, tmp_path):
    covers("W-records-import_a_backup", "W-records-replace_my_records_with_this_backup")
    app = public_app
    p = setup_with_a_lesson(app, pages, "bad")
    open_backup(p, app)
    for name, data in [("not.json", b"this is not json"), ("binary.json", bytes(range(256)) * 10),
                       ("list.json", b"[1, 2, 3]"), ("empty.json", b"")]:
        text = upload(p, tmp_path, name, data)
        assert "Traceback" not in text and "Expecting value" not in text and "JSONDecodeError" not in text, name
        assert "isn't a backup from this app" in text, f"{name}: no clear message"
        p.page.reload()
        flows.idle(p.page)
        open_backup(p, app)


def test_wrong_types_never_break_a_page(public_app, pages, tmp_path):
    covers("D-ui-replace")
    app = public_app
    p = setup_with_a_lesson(app, pages, "types")
    open_backup(p, app)
    evil = {"entries": [
        {"date": "2026-09-01", "topic": "philosophy", "title": {"x": 1}, "session_number": "many",
         "lessons": "not a list", "followups": 5, "reflection": ["a"], "completed": "yes"},
        {"date": "2026-09-02", "topic": "philosophy", "title": "<script>alert(1)</script>",
         "lessons": [{"n": 1, "title": {"t": 1}, "quiz": "x"}]}],
        "books": [{"id": "b1", "title": 5, "plan": "nope", "checks": [], "status": "reading", "chapters": "x"}],
        "user_id": "someone-else"}
    text = upload(p, tmp_path, "evil.json", json.dumps(evil).encode())
    assert "Traceback" not in text
    for page_name in ("Today", "Progress", "Settings"):
        flows.go(p, app, page_name)
        assert "Traceback" not in p.page.evaluate("document.body.innerText"), page_name
    p.page.goto(app.url + "/reading")
    flows.idle(p.page)
    assert "Traceback" not in p.page.evaluate("document.body.innerText")


def test_a_huge_file_is_refused(public_app, pages, tmp_path):
    covers("W-records-import_a_backup")
    app = public_app
    p = setup_with_a_lesson(app, pages, "huge")
    open_backup(p, app)
    big = json.dumps({"entries": [{"date": "2026-09-01", "topic": "philosophy", "lesson": "x" * 1000}] * 25000})
    text = upload(p, tmp_path, "huge.json", big.encode())
    assert "too large" in text.lower(), "a 25 MB backup should be refused with a reason"


def test_a_failed_import_keeps_the_records(public_app, pages, tmp_path):
    covers("D-ui-replace")
    app = public_app
    email = f"imp-fail-{int(time.time() * 1000)}@example.com"
    p = pages(width=1440)
    flows.sign_in(p, app, email=email)
    flows.onboard(p)
    flows.open_app(p, app)
    flows.start_lesson(p)
    before = entries_of(app, email)
    assert len(before) == 1
    open_backup(p, app)
    app.post("/__fail", {"method": "POST", "table": "learning_entries", "times": 3})   # the write fails
    new = {"entries": [{"date": "2026-08-01", "topic": "philosophy", "title": "imported"}]}
    text = upload(p, tmp_path, "ok.json", json.dumps(new).encode())
    assert "wasn't saved" in text or "wasn't" in text, "the failure is reported"
    after = entries_of(app, email)
    assert any(e["date"] == before[0]["date"] for e in after), "the records already there were lost"
