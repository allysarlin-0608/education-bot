"""Accounts: one internal id per person whatever the sign-in method; roles
give permissions; setup settings and preferences come back as the domain
reads them; counts add up (a visit once a day); the audit log keeps what
was done."""
from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from coach import prefs, settings
from gnosis.data import schema as t
from gnosis.data.repositories import accounts

D = date(2026, 11, 2)


def test_one_person_many_ways_to_sign_in(conn):
    uid = accounts.create_user(conn, email="Ann@Example.com", legacy_id="supa-ann", display_name="Ann")
    assert accounts.by_email(conn, "ann@example.com") == uid == accounts.by_legacy_id(conn, "supa-ann")
    accounts.add_identity(conn, uid, "google", "g-123", "ann@example.com")
    accounts.add_identity(conn, uid, "email", "ann@example.com")
    accounts.add_identity(conn, uid, "google", "g-123")                 # the same again: nothing new
    assert [i["provider"] for i in accounts.identities(conn, uid)] == ["email", "google"]
    other = accounts.create_user(conn, email="bob@example.com")
    accounts.add_identity(conn, other, "google", "g-123")             # someone else's Google account: refused quietly
    assert accounts.identities(conn, other) == []
    accounts.set_credential(conn, uid, "$2a$10$abcdefghijklmnopqrstuuabcdefghijklmnopqrstuvwxyz012", "bcrypt")
    assert accounts.credential(conn, uid)["algorithm"] == "bcrypt"
    with pytest.raises(IntegrityError):
        accounts.set_credential(conn, uid, "x", "md5")                 # only the algorithms we accept


def test_roles_give_permissions_and_status_changes(conn):
    uid = accounts.create_user(conn, email="admin@example.com")
    assert accounts.permissions_of(conn, uid) == set()
    accounts.grant_role(conn, uid, "staff")
    accounts.grant_role(conn, uid, "editor")
    assert accounts.roles_of(conn, uid) == ["editor", "staff"]
    assert accounts.permissions_of(conn, uid) == {"users.read", "learning.read", "content.edit"}
    accounts.revoke_role(conn, uid, "editor")
    assert "content.edit" not in accounts.permissions_of(conn, uid)
    accounts.set_status(conn, uid, "suspended")
    assert accounts.user(conn, uid)["status"] == "suspended"
    with pytest.raises(IntegrityError):
        accounts.set_status(conn, uid, "banished")


def test_settings_and_preferences_come_back_as_the_domain_reads_them(conn):
    uid = accounts.create_user(conn, email="c@example.com")
    assert accounts.load_settings(conn, uid) is None
    row = dict(settings.blank(uid), subjects=["g-1234abcd", "philosophy", "cosmos"], units_per_day=3,
               subject_levels={"philosophy": "Intermediate", "cosmos": "Beginner", "fashion": "Advanced"},
               reading_enabled=True, onboarded_at="2026-11-01T10:00:00+00:00", updated_at="2026-11-02T10:00:00+00:00",
               onboarding={"step": 2, "subjects": ["cosmos"]})
    accounts.save_settings(conn, uid, row)
    assert settings.normalize(accounts.load_settings(conn, uid), uid) == settings.normalize(row, uid)
    p = dict(prefs.blank(), reminder_on=True, reminder_time="08:30", seen=["streak-7"])
    accounts.save_prefs(conn, uid, p)
    accounts.save_prefs(conn, uid, dict(p, light_day="2026-11-02"))
    assert prefs.normalize(accounts.load_prefs(conn, uid)) == prefs.normalize(dict(p, light_day="2026-11-02"))


def test_counts_add_up_and_a_visit_counts_once_a_day(conn):
    uid = accounts.create_user(conn, email="d@example.com")
    accounts.add_usage(conn, uid, D, 1, 1200)
    accounts.add_usage(conn, uid, D, 2, 800)
    assert accounts.usage_on(conn, uid, D) == {"request_count": 3, "token_count": 2000}
    assert accounts.usage_on(conn, uid, date(2026, 1, 1)) == {"request_count": 0, "token_count": 0}
    for _ in range(3):
        accounts.add_count(conn, uid, D, "visit", once_a_day=True)
        accounts.add_count(conn, uid, D, "lesson_passed")
    accounts.add_count(conn, uid, D, "recovered", table=t.learning_signals)
    assert accounts.counts_of(conn, uid, t.usage_events) == [
        {"day": "2026-11-02", "event": "lesson_passed", "count": 3}, {"day": "2026-11-02", "event": "visit", "count": 1}]
    assert accounts.counts_of(conn, uid, t.learning_signals)[0]["event"] == "recovered"


def test_invites_and_the_audit_log(conn):
    admin = accounts.create_user(conn, email="root@example.com")
    accounts.add_invite(conn, "New@Example.com", "friend", invited_by=admin)
    assert accounts.is_invited(conn, "new@example.com") and not accounts.is_invited(conn, "x@example.com")
    accounts.audit(conn, "invite.add", actor=admin, target_type="invite", target_id="new@example.com", ip="1.2.3.4")
    row = conn.execute(select(t.audit_log)).mappings().one()
    assert row["action"] == "invite.add" and row["actor_user_id"] == admin and row["details"] == {}


def test_deleting_a_person_takes_everything_of_theirs_with_them(conn):
    from gnosis.data.repositories import learning
    uid = accounts.create_user(conn, email="e@example.com")
    accounts.add_identity(conn, uid, "google", "g-e")
    accounts.save_prefs(conn, uid, prefs.blank())
    learning.save_entry(conn, uid, {"date": "2026-11-02", "topic": "philosophy", "lessons": [
        {"n": 1, "title": "T", "unit": "U", "lesson": "x", "completed": True, "cards": [], "ev": []}]})
    conn.execute(t.users.delete().where(t.users.c.id == uid))
    for table in (t.identities, t.preferences, t.study_days, t.day_lessons):
        assert conn.execute(select(table).where(table.c.user_id == uid)).first() is None, table.name
