"""Run the integrity checks (supabase/audit/*.sql) on a throwaway local
Postgres: the repo's own migrations, a stand-in for Supabase's auth schema,
a realistic history made by the app's own code (tests/seed_history.py), and
then a second pass with deliberately broken rows to show every check catches
what it should.

    python tools/integrity_local.py            # needs Postgres 16 binaries

Never connects to any Supabase project.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
import seed_history  # noqa: E402
from coach import books  # noqa: E402

BIN = Path(os.environ.get("PG_BIN", "/usr/lib/postgresql/16/bin"))
ROLES = """create role anon nologin; create role authenticated nologin; create role service_role nologin;
create role supabase_auth_admin nologin;"""
SUPABASE_STANDIN = """
create schema auth;
create table auth.users (id uuid primary key, email text not null);
create function auth.uid() returns uuid language sql stable as $$ select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid $$;
create function auth.jwt() returns jsonb language sql stable as $$ select coalesce(nullif(current_setting('request.jwt.claims', true), ''), '{}')::jsonb $$;
"""
MIGRATIONS = ["schema.sql", "lessons.sql", "followups.sql", "kickoff.sql", "user_settings.sql",
              "multiuser.sql", "accounts.sql"]


def q(value):
    return "'" + str(value).replace("'", "''") + "'"


class Pg:
    def __init__(self):
        self.dir = Path(tempfile.mkdtemp(prefix="gnosis-pg-"))
        self.sock = self.dir / "sock"
        self.sock.mkdir()
        # Postgres refuses to run as root: then the server runs as the postgres user
        self.as_pg = ["runuser", "-u", "postgres", "--"] if os.geteuid() == 0 else []
        if self.as_pg:
            shutil.chown(self.dir, "postgres")
            shutil.chown(self.sock, "postgres")
        subprocess.run(self.as_pg + [BIN / "initdb", "-D", self.dir / "data", "-U", "postgres", "-A", "trust"],
                       check=True, capture_output=True)
        subprocess.run(self.as_pg + [BIN / "pg_ctl", "-D", self.dir / "data", "-o",
                                     f"-k {self.sock} -c listen_addresses=''", "-l", self.dir / "log", "start", "-w"],
                       check=True, capture_output=True)

    def sql(self, text, db="postgres"):
        r = subprocess.run(["psql", "-h", str(self.sock), "-U", "postgres", "-d", db, "-v", "ON_ERROR_STOP=1",
                            "-q", "-A", "-F", " | ", "-P", "footer=off"], input=text, text=True, capture_output=True)
        if r.returncode:
            raise RuntimeError(r.stderr)
        return r.stdout

    def stop(self):
        subprocess.run(self.as_pg + [BIN / "pg_ctl", "-D", self.dir / "data", "stop", "-m", "fast"], capture_output=True)
        shutil.rmtree(self.dir, ignore_errors=True)


def entry_row(uid, e):
    return (f"insert into public.learning_entries (user_id, date, topic, session_number, level, completed, title, "
            f"followup_question, reflection, lesson, followups, kickoff, lessons) values ({q(uid)}, {q(e['date'])}, "
            f"{q(e['topic'])}, {e['session_number']}, {q(e['level'])}, {str(e['completed']).lower()}, {q(e['title'])}, "
            f"{q(e['followup_question'])}, {q(e['reflection'])}, {q(e['lesson'])}, {q(json.dumps(e['followups']))}, "
            f"{q(e['kickoff'])}, {q(json.dumps(e['lessons']))});")


def clean_data(today):
    out = []
    for k in range(3):
        uid, email = str(uuid.uuid4()), f"learner{k}@example.com"
        out += [f"insert into auth.users values ({q(uid)}, {q(email)});",
                f"insert into public.users (user_id, email) values ({q(uid)}, {q(email)});",
                f"insert into public.allowed_users (email) values ({q(email)});",
                f"insert into public.user_settings (user_id, subjects, units_per_day, subject_levels, reading_enabled, "
                f"onboarded_at) values ({q(uid)}, '[\"philosophy\"]', 3, '{{}}', true, now());",
                f"insert into public.ai_usage values ({q(uid)}, {q(today)}, 12, 34000);"]
        out += [entry_row(uid, e) for e in seed_history.build(today, days=35 + 10 * k)]
        book = books.new_book(today - timedelta(days=5))
        book.update(title="A book", author="Someone", chapter_count=14, total_pages=280, status="reading",
                    started_on=(today - timedelta(days=5)).isoformat(), chapters=[f"C{n}" for n in range(1, 15)],
                    plan=books.allocate(14))
        out.append(f"insert into public.reading_books (user_id, id, data) values ({q(uid)}, {q(book['id'])}, "
                   f"{q(json.dumps(book))});")
    return "\n".join(out)


def broken_data(today):
    """One row for each kind of problem the checks look for."""
    ghost = str(uuid.uuid4())
    uid = str(uuid.uuid4())
    e = seed_history.build(today, days=3)[-1]
    bad = []
    bad.append(entry_row(ghost, dict(e, date=(today - timedelta(days=40)).isoformat())))             # orphan
    bad.append(f"insert into auth.users values ({q(uid)}, 'someone@example.com');")                     # not invited
    bad.append(entry_row(uid, dict(e, date=(today + timedelta(days=9)).isoformat())))                 # future
    done_open = dict(e, date=(today - timedelta(days=50)).isoformat(), completed=True,
                     lessons=[dict(e["lessons"][0], completed=False)])
    bad.append(entry_row(uid, done_open))                                                              # completed, lesson open
    twice = dict(e, date=(today - timedelta(days=51)).isoformat(), lessons=[e["lessons"][0], e["lessons"][0]])
    bad.append(entry_row(uid, twice))                                                                  # same lesson twice
    low = dict(e["lessons"][0], quiz=dict(e["lessons"][0]["quiz"], score=40, best=40))
    bad.append(entry_row(uid, dict(e, date=(today - timedelta(days=52)).isoformat(), lessons=[low])))  # passed below 80
    bad.append(f"insert into public.reading_books (user_id, id, data) values ({q(uid)}, 'x1', "
               f"'{{\"id\": \"x2\", \"status\": \"reading\", \"plan\": [[1]]}}');")                     # id, plan
    bad.append(f"insert into public.ai_usage values ({q(uid)}, {q(today)}, -1, 0);")                  # negative
    return "\n".join(bad)


def run_checks(pg, db, file):
    return pg.sql((ROOT / "supabase" / "audit" / file).read_text(), db)


def main():
    today = datetime.now(ZoneInfo("Asia/Taipei")).date()
    pg = Pg()
    try:
        pg.sql(ROLES)
        for db in ("clean", "broken", "personal"):
            pg.sql(f"create database {db};")
        for db in ("clean", "broken"):
            pg.sql(SUPABASE_STANDIN, db)
            for m in MIGRATIONS:
                pg.sql((ROOT / "supabase" / m).read_text(), db)
        # the personal database: the app's tables before accounts (no user_id)
        pg.sql(SUPABASE_STANDIN, "personal")
        for m in ["schema.sql", "lessons.sql", "followups.sql", "kickoff.sql", "user_settings.sql"]:
            pg.sql((ROOT / "supabase" / m).read_text(), "personal")
        personal = [entry_row("x", e).replace("(user_id, ", "(").replace("'x', ", "", 1)
                    for e in seed_history.build(today, days=40)]
        pg.sql("\n".join(personal), "personal")
        pg.sql(clean_data(today), "clean")
        pg.sql(clean_data(today) + "\n" + broken_data(today), "broken")
        print("== TEST database checks, realistic data (expect all 0) ==")
        print(run_checks(pg, "clean", "integrity_test_db.sql"))
        print("== TEST database checks, with one broken row of each kind (expect them found) ==")
        print(run_checks(pg, "broken", "integrity_test_db.sql"))
        print("== PERSONAL database checks, realistic data (expect all 0) ==")
        print(run_checks(pg, "personal", "integrity_personal_db.sql"))
    finally:
        pg.stop()


if __name__ == "__main__":
    main()
