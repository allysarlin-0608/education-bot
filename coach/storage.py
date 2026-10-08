"""Where the learning log lives: a Supabase table when SUPABASE_URL and
SUPABASE_KEY are configured, otherwise a local JSON file (which Streamlit
Cloud wipes on restart).

This is the app's only way to its data: no other module talks to the
database. Every function finds whose data it is by calling
get_current_user_id() itself (the store is given it when it is made).

Two layouts:
- personal (APP_MODE=personal, the default): one person's app, exactly as
  it has always been; the learning log and books have no user_id column
  and settings are kept under one fixed id.
- scoped (APP_MODE=public): many people, each seeing only their own. Every
  table has a user_id; every read filters on it and every write sets it,
  from get_current_user_id() and nothing else. With no current user, every
  call refuses (StorageError). Also here: the users, allowed_users (the
  invitation list) and ai_usage tables, the export of one person's data,
  and the deletion of it all (one transaction, the delete_user_data
  function in supabase/multiuser.sql)."""
import json
import logging
import os
import threading
import time
from datetime import date
from pathlib import Path

import requests

from coach import clock, core
from coach.errors import StorageError  # noqa: F401  (storage.StorageError, as every caller names it)

TABLE = "learning_entries"
BOOKS_TABLE = "reading_books"
SETTINGS_TABLE = "user_settings"
USERS_TABLE = "users"
INVITES_TABLE = "allowed_users"
USAGE_TABLE = "ai_usage"
PATHS_TABLE = "learning_paths"
EVENTS_TABLE = "usage_events"
PREFS_TABLE = "learner_prefs"      # supabase/goals.sql (habits: reminders, light day, milestones seen)
SIGNALS_TABLE = "learning_signals"  # supabase/mastery.sql (is she learning? counts only, coach/metrics.py)
PATHS_TABLE_MISSING = (
    "Supabase doesn't have the learning_paths table yet. Run supabase/goals.sql in "
    "Supabase's SQL Editor, then refresh this page."
)
TIMEOUT = (3.05, 10)                 # seconds to connect, then to wait for the answer
READ_TRIES = 2                       # a read: once more after a transient failure (_request)
TRANSIENT = (502, 503, 504)          # the gateway, not the request: worth one more try
RETRY_PAUSE = 0.4                    # seconds


def _sleep(seconds: float) -> None:          # (replaced in tests)
    time.sleep(seconds)


# Run once in the Supabase SQL editor. RLS stays on with no policies, so
# only the secret key (kept server-side in Streamlit secrets) can reach it.
SCHEMA_SQL = """\
create table public.learning_entries (
  date date not null,
  topic text not null,
  session_number integer not null,
  level text not null,
  completed boolean not null default false,
  title text not null default '',
  followup_question text not null default '',
  reflection text not null default '',
  lesson text not null default '',
  followups jsonb not null default '[]'::jsonb,
  kickoff text not null default '',
  lessons jsonb not null default '[]'::jsonb,
  primary key (date, topic)
);
alter table public.learning_entries enable row level security;
grant select, insert, update, delete on public.learning_entries to service_role;
"""

# 看書 book tracker: one row per book, the book's state kept as JSON.
BOOKS_SQL = """\
create table public.reading_books (
  id text primary key,
  data jsonb not null,
  updated_at timestamptz not null default now()
);
alter table public.reading_books enable row level security;
grant select, insert, update, delete on public.reading_books to service_role;
"""

# Added after the first release: the chat after a lesson, so it survives a
# refresh. Databases created before that need this once.
FOLLOWUPS_SQL = """\
alter table public.learning_entries
  add column if not exists followups jsonb not null default '[]'::jsonb;
"""

# Run once: make sure only the app's secret key (service_role) can touch
# the tables. RLS on with no policies already blocks the public
# anon/authenticated roles; revoking their grants closes it twice.
HARDEN_SQL = """\
alter table public.learning_entries enable row level security;
alter table public.reading_books enable row level security;
revoke all on public.learning_entries from anon, authenticated;
revoke all on public.reading_books from anon, authenticated;
grant select, insert, update, delete on public.learning_entries to service_role;
grant select, insert, update, delete on public.reading_books to service_role;

-- 檢查：兩個資料表的 rls_enabled 都要是 true，policies 都要是 0。
select c.relname as table_name,
       c.relrowsecurity as rls_enabled,
       (select count(*) from pg_policies p where p.tablename = c.relname) as policies
from pg_class c
where c.relname in ('learning_entries', 'reading_books');
"""

# Added later still: her full opening message (with 「我今天特別想了解…」).
KICKOFF_SQL = """\
alter table public.learning_entries
  add column if not exists kickoff text not null default '';
"""

# Added with the fixed syllabus: the day's lessons (up to 5 per day).
LESSONS_SQL = """\
alter table public.learning_entries
  add column if not exists lessons jsonb not null default '[]'::jsonb;
"""

# Her settings (subjects, daily pace, starting levels, reading): one row
# per user, always read and written by user_id. Until this has been run
# the app keeps its old fixed setup (see settings.legacy).
SETTINGS_SQL = """\
create table public.user_settings (
  user_id text primary key,
  subjects jsonb not null default '[]'::jsonb,
  units_per_day integer not null default 3 check (units_per_day in (1, 3, 5)),
  subject_levels jsonb not null default '{}'::jsonb,
  reading_enabled boolean not null default false,
  onboarding jsonb,
  onboarded_at timestamptz,
  updated_at timestamptz,
  check (jsonb_array_length(subjects) <= 3),
  check (onboarded_at is null or jsonb_array_length(subjects) >= 1)
);
alter table public.user_settings enable row level security;
revoke all on public.user_settings from anon, authenticated;
grant select, insert, update, delete on public.user_settings to service_role;
"""

# Columns added after the first release. If a database doesn't have one
# yet, entries are saved without it instead of failing (the daily page
# warns when "lessons" is missing, since lesson progress needs it).
OPTIONAL_COLUMNS = ("followups", "kickoff", "lessons")

BOOKS_TABLE_MISSING = (
    "Supabase doesn't have the reading_books table yet. Run supabase/books.sql in "
    "Supabase's SQL Editor to start tracking your reading."
)


logger = logging.getLogger("coach.storage")
# one save at a time to a local file: every tab is a thread of one process
_FILE_LOCK = threading.Lock()

SETTINGS_COLUMNS = ("user_id", "subjects", "units_per_day", "subject_levels", "reading_enabled",
                    "onboarding", "onboarded_at", "updated_at")


NO_USER = "no one is signed in"


ADMINS_TABLE = "app_admins"


def _is_secret_key(key: str) -> bool:
    """A key that bypasses row level security: sb_secret_…, or a legacy JWT
    whose role is service_role."""
    if key.startswith("sb_secret_"):
        return True
    if key.startswith("eyJ"):
        import base64
        try:
            part = key.split(".")[1]
            claims = json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
        except (IndexError, ValueError):
            return True
        return claims.get("role") == "service_role"
    return False


def _now() -> str:
    return clock.now_iso()


class _Scope:
    """Whose data a call is about: current_user() is get_current_user_id()
    (auth.py), asked afresh on every call, never remembered."""

    def _uid(self) -> str:
        uid = self.current_user() if self.current_user else None
        if not uid:
            raise StorageError(NO_USER)
        return str(uid)


class FileStore(_Scope):
    name = "file"

    def __init__(self, path=None, settings_path=None, scoped=False, current_user=None):
        # read when the store is made, like the settings path below (not when
        # the module was first imported)
        self.path = Path(path or os.environ.get("COACH_LOG_PATH") or core.DEFAULT_LOG_PATH)
        self.settings_path = Path(settings_path or os.environ.get("COACH_SETTINGS_PATH")
                                  or self.path.with_name("user_settings.json"))
        self.scoped = scoped
        self.current_user = current_user

    def _log_path(self) -> Path:
        """personal: the one log file; scoped: one file per user, beside it."""
        if not self.scoped:
            return Path(self.path)
        uid = self._uid()
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in uid)
        return Path(self.path).with_name(f"{Path(self.path).stem}.{safe}.json")

    def _table_path(self, table: str) -> Path:
        return self.settings_path.with_name(f"{table}.json")

    def _rows(self, table: str) -> list:
        """A table's rows (none yet: no file). A file that can't be read is
        never taken for an empty one, or the next write would replace it."""
        path = self._table_path(table)
        try:
            rows = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return []
        except (ValueError, UnicodeDecodeError) as e:
            logger.error("the local %s file %s can't be read (%s); nothing was written", table, path, e)
            raise StorageError(f"the local {table} file can't be read; it was left as it is") from e
        if not isinstance(rows, list):
            logger.error("the local %s file %s isn't a list of rows; nothing was written", table, path)
            raise StorageError(f"the local {table} file can't be read; it was left as it is")
        return rows

    def _write_rows(self, table: str, rows: list) -> None:
        path = self._table_path(table)
        try:
            core.write_json(path, rows)
        except OSError as e:
            logger.error("saving %s failed: %s", table, e)
            raise StorageError("this couldn't be written to a file") from e

    books_error = None
    settings_missing = False

    def _settings_rows(self) -> list:
        """Everyone's settings rows. A file that can't be read is never taken
        for an empty one: the next save would write over every row in it
        with this one (as for the records, ISS-020)."""
        try:
            data = json.loads(self.settings_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return []
        except (ValueError, UnicodeDecodeError) as e:
            logger.error("the settings file %s can't be read (%s); nothing was written", self.settings_path, e)
            raise StorageError("your settings file can't be read; it was left as it is") from e
        rows = data.get("user_settings") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            logger.error("the settings file %s isn't a settings file; nothing was written", self.settings_path)
            raise StorageError("your settings file can't be read; it was left as it is")
        return [r for r in rows if isinstance(r, dict)]

    def load_settings(self):
        """The current user's settings row, or None if they have none yet."""
        uid = self._uid()
        return next((r for r in self._settings_rows() if r.get("user_id") == uid), None)

    def _write_settings(self, rows: list) -> None:
        try:
            core.write_json(self.settings_path, {"user_settings": rows})
        except OSError as e:
            logger.error("saving settings failed: %s", e)
            raise StorageError("your settings couldn't be written to a file") from e

    def save_settings(self, row: dict) -> None:
        uid = self._uid()
        with _FILE_LOCK:              # (read, change, write: two people saving at once keep both rows)
            rows = [r for r in self._settings_rows() if r.get("user_id") != uid]
            rows.append({**{k: row.get(k) for k in SETTINGS_COLUMNS}, "user_id": uid})
            self._write_settings(rows)

    def load(self) -> dict:
        with _FILE_LOCK:
            return self._stored()

    def load_entry(self, day: str, topic: str):
        """The stored entry for one day and subject, or None."""
        return core.find_entry(self.load(), date.fromisoformat(day), topic)

    def load_books(self) -> list:
        """The stored books (normalized), for pages that must build on them."""
        return self.load()["books"]

    def _write(self, log: dict) -> None:
        try:
            core.save_log(log, self._log_path())
        except OSError as e:
            logger.error("saving the local log failed: %s", e)
            raise StorageError("the records couldn't be written to a file") from e

    def _stored(self) -> dict:
        """What is stored now, to write one change into. A file that can't be
        read is never taken for an empty one: that would save over
        everything in it with this one change (ISS-020)."""
        path = self._log_path()
        if not path.exists():
            return core.empty_log()
        try:
            return core.parse_log(json.loads(path.read_text(encoding="utf-8")))
        except (ValueError, UnicodeDecodeError) as e:    # (not JSON, or not the shape of a log)
            logger.error("the local log %s can't be read (%s); nothing was written", path, e)
            raise StorageError("the records file can't be read, so nothing was saved over it") from e

    def save_entry(self, log: dict, entry: dict) -> None:
        """Write this one entry into what is stored now (as the database
        does): another tab's entries and books are kept, not overwritten
        by this tab's older copy of the whole log (ISS-009)."""
        with _FILE_LOCK:
            stored = self._stored()
            key = (entry["date"], entry["topic"])
            stored["entries"] = [e for e in stored["entries"] if (e["date"], e["topic"]) != key] + [entry]
            stored["entries"].sort(key=lambda e: (e["date"], e["topic"]))
            self._write(stored)

    # ---- accounts (scoped only) ----
    def touch_user(self, email: str, name: str, picture: str = "") -> None:
        uid = self._uid()
        with _FILE_LOCK:
            rows = self._rows(USERS_TABLE)
            mine = next((r for r in rows if r["user_id"] == uid), None)
            if mine is None:
                rows.append({"user_id": uid, "email": email, "display_name": name, "avatar_url": picture,
                             "created_at": _now(), "last_seen_at": _now()})
            else:
                mine.update(email=email, display_name=name, avatar_url=picture, last_seen_at=_now())
            self._write_rows(USERS_TABLE, rows)

    def user_row(self):
        uid = self._uid()
        return next((r for r in self._rows(USERS_TABLE) if r["user_id"] == uid), None)

    def is_invited(self, email: str) -> bool:
        return any(r["email"] == email.lower() for r in self._rows(INVITES_TABLE))

    def list_invites(self) -> list:
        return sorted(self._rows(INVITES_TABLE), key=lambda r: r["email"])

    def add_invite(self, email: str, note: str = "") -> None:
        with _FILE_LOCK:
            rows = [r for r in self._rows(INVITES_TABLE) if r["email"] != email.lower()]
            rows.append({"email": email.lower(), "invited_at": _now(), "note": note})
            self._write_rows(INVITES_TABLE, rows)

    def remove_invite(self, email: str) -> None:
        with _FILE_LOCK:
            self._write_rows(INVITES_TABLE, [r for r in self._rows(INVITES_TABLE) if r["email"] != email.lower()])

    def usage_today(self, day: str) -> dict:
        uid = self._uid()
        row = next((r for r in self._rows(USAGE_TABLE) if r["user_id"] == uid and r["date"] == day), None)
        return row or {"user_id": uid, "date": day, "request_count": 0, "token_count": 0}

    def add_usage(self, day: str, requests_: int, tokens_: int) -> None:
        uid = self._uid()
        with _FILE_LOCK:
            rows = self._rows(USAGE_TABLE)
            row = next((r for r in rows if r["user_id"] == uid and r["date"] == day), None)
            if row is None:
                rows.append({"user_id": uid, "date": day, "request_count": requests_, "token_count": tokens_})
            else:
                row["request_count"] += requests_
                row["token_count"] += tokens_
            self._write_rows(USAGE_TABLE, rows)

    def export_my_data(self) -> dict:
        uid = self._uid()
        log = self.load()
        return {"user": self.user_row(), "settings": self.load_settings(),
                "learning_entries": log["entries"], "reading_books": log.get("books", []),
                "learning_paths": log.get("paths", []),
                "ai_usage": [r for r in self._rows(USAGE_TABLE) if r["user_id"] == uid],
                "usage_events": [r for r in self._rows(EVENTS_TABLE) if r["user_id"] == uid],
                "learning_signals": [r for r in self._rows(SIGNALS_TABLE) if r["user_id"] == uid],
                "learner_prefs": self.load_prefs()}

    def load_prefs(self):
        """Her habit preferences (coach/prefs.py), or None if she has none yet."""
        uid = self._uid()
        row = next((r for r in self._rows(PREFS_TABLE) if r.get("user_id") == uid), None)
        return row["data"] if row else None

    def save_prefs(self, data: dict) -> None:
        uid = self._uid()
        with _FILE_LOCK:
            rows = [r for r in self._rows(PREFS_TABLE) if r.get("user_id") != uid]
            rows.append({"user_id": uid, "data": data, "updated_at": _now()})
            self._write_rows(PREFS_TABLE, rows)

    def add_event(self, day: str, event: str) -> None:
        from coach import metrics
        uid = self._uid()
        table = SIGNALS_TABLE if event in metrics.SIGNALS else EVENTS_TABLE
        with _FILE_LOCK:
            rows = self._rows(table)
            row = next((r for r in rows if r["user_id"] == uid and r["day"] == day and r["event"] == event), None)
            if row is None:
                rows.append({"user_id": uid, "day": day, "event": event, "count": 1})
            elif event != "visit":
                row["count"] += 1
            self._write_rows(table, rows)

    def metrics(self, since: date, today: date) -> dict:
        from coach import metrics
        return metrics.summarize(self._rows(USERS_TABLE), self._rows(EVENTS_TABLE) + self._rows(SIGNALS_TABLE),
                                 since, today)

    def delete_my_account(self) -> None:
        """Everything of the current user's, gone: the log file, their settings,
        their usage and their users row (the files each replaced whole)."""
        uid = self._uid()
        log_path = self._log_path()
        with _FILE_LOCK:              # (each file read, changed and written while no one else writes it)
            self._write_settings([r for r in self._settings_rows() if r.get("user_id") != uid])
            self._write_rows(USAGE_TABLE, [r for r in self._rows(USAGE_TABLE) if r["user_id"] != uid])
            self._write_rows(EVENTS_TABLE, [r for r in self._rows(EVENTS_TABLE) if r["user_id"] != uid])
            self._write_rows(SIGNALS_TABLE, [r for r in self._rows(SIGNALS_TABLE) if r["user_id"] != uid])
            self._write_rows(PREFS_TABLE, [r for r in self._rows(PREFS_TABLE) if r["user_id"] != uid])
            self._write_rows(USERS_TABLE, [r for r in self._rows(USERS_TABLE) if r["user_id"] != uid])
        try:
            log_path.unlink(missing_ok=True)
        except OSError as e:
            raise StorageError("your records couldn't be deleted") from e

    def is_admin(self, email: str) -> bool:
        return any(r["email"] == email.lower() for r in self._rows(ADMINS_TABLE))

    def save_book(self, log: dict, book: dict) -> None:
        with _FILE_LOCK:
            stored = self._stored()
            stored["books"] = [b for b in stored["books"] if b["id"] != book["id"]] + [book]
            self._write(stored)

    paths_error = None

    def save_path(self, log: dict, path: dict) -> None:
        with _FILE_LOCK:
            stored = self._stored()
            stored["paths"] = [p for p in stored.get("paths", []) if p["id"] != path["id"]] + [path]
            self._write(stored)

    def replace(self, log: dict) -> None:
        with _FILE_LOCK:
            self._write(log)


class SupabaseStore(_Scope):
    name = "supabase"

    def __init__(self, url: str, key: str, session=None, scoped=False, current_user=None, access_token=None):
        # Accept the Project URL with or without the /rest/v1 suffix that
        # Supabase's "API URL" field sometimes shows.
        url = url.strip().rstrip("/")
        if url.endswith("/rest/v1"):
            url = url[: -len("/rest/v1")]
        self.base = f"{url}/rest/v1"
        # Set when the books table can't be read; the rest keeps working.
        self.books_error = None
        # the same for her goals (supabase/goals.sql not run yet)
        self.paths_error = None
        # True when there is no user_settings table yet (settings.sql not run)
        self.settings_missing = False
        # Optional columns Supabase said it doesn't have (their .sql not run
        # yet); entries are saved without them instead of failing.
        self.missing_columns = set()
        self.session = session or requests.Session()
        self.headers = {"apikey": key, "Content-Type": "application/json"}
        # Legacy service_role keys are JWTs and also go in Authorization;
        # new sb_secret_ keys only go in the apikey header.
        if key.startswith("eyJ"):
            self.headers["Authorization"] = f"Bearer {key}"
        self.scoped = scoped
        self.current_user = current_user
        # Signed-in mode (APP_MODE=public): every request is made as the
        # person, with their access token, so the database's row level
        # security decides what they may read and write. The key must then be
        # the publishable one; a secret key would bypass that.
        self.access_token = access_token
        if access_token is not None and _is_secret_key(key):
            raise StorageError("the app is set up with a secret database key; public mode needs the publishable key")

    def _mine(self, params: dict) -> dict:
        """Scoped: the same query, only the current user's rows."""
        return {**params, "user_id": f"eq.{self._uid()}"} if self.scoped else params

    def _own(self, rows: list) -> list:
        """Scoped: the rows to write, each stamped with the current user's id."""
        if not self.scoped:
            return rows
        uid = self._uid()
        return [{**r, "user_id": uid} for r in rows]

    def _request(self, method, params=None, json=None, prefer=None, table=TABLE):
        headers = dict(self.headers)
        if self.access_token is not None:
            token = self.access_token()
            if not token:
                raise StorageError(NO_USER)
            headers["Authorization"] = f"Bearer {token}"
        if prefer:
            headers["Prefer"] = prefer
        # A read is asked again once after a moment if the connection failed
        # or the database's gateway was briefly unavailable; a write never is
        # (not every write may safely happen twice: a counter would count twice).
        # A read that was sent but not answered in time isn't asked again: the
        # database is slow, and asking twice would double the wait and its load.
        tries = READ_TRIES if method == "GET" else 1
        for attempt in range(1, tries + 1):
            try:
                resp = self.session.request(
                    method, f"{self.base}/{table}", params=params, json=json,
                    headers=headers, timeout=TIMEOUT,
                )
            except requests.RequestException as e:
                if attempt < tries and isinstance(e, requests.ConnectionError):
                    logger.warning("supabase %s %s unreachable (%s); trying once more", method, table, e)
                    _sleep(RETRY_PAUSE)
                    continue
                logger.error("supabase %s %s unreachable: %s", method, table, e)
                raise StorageError("can't reach the database right now") from e
            if resp.status_code in TRANSIENT and attempt < tries:
                logger.warning("supabase %s %s -> %s; trying once more", method, table, resp.status_code)
                _sleep(RETRY_PAUSE)
                continue
            break
        if resp.status_code >= 400:
            logger.error("supabase %s %s -> %s: %s", method, table, resp.status_code, resp.text[:500])
            if resp.status_code == 401 and self.access_token is not None:
                raise StorageError("your session has ended; refresh the page to continue", status=401,
                                   detail=resp.text[:300])
            raise StorageError("the database isn't responding right now", status=resp.status_code, detail=resp.text[:500])
        return resp

    def load(self) -> dict:
        resp = self._request("GET", params=self._mine({"select": "*", "order": "date.asc,topic.asc"}))
        rows = resp.json()
        self._check_lessons_column()
        return core.parse_log({
            "entries": [{k: v for k, v in row.items() if k in core.ENTRY_FIELDS} for row in rows],
            "books": self._load_books(),
            "paths": self._load_paths(),
        })

    def _load_paths(self) -> list:
        try:
            resp = self._request("GET", params=self._mine({"select": "data", "order": "updated_at.asc"}),
                                 table=PATHS_TABLE)
        except StorageError as e:
            self.paths_error = PATHS_TABLE_MISSING if e.status == 404 else f"Your goals: {e}. Refresh in a moment to try again."
            return []
        self.paths_error = None
        return [row["data"] for row in resp.json()]

    def save_path(self, log: dict, path: dict) -> None:
        if self.paths_error == PATHS_TABLE_MISSING:
            raise StorageError("goals can't be saved until supabase/goals.sql is run")
        self._request("POST", params={"on_conflict": "user_id,id" if self.scoped else "id"},
                      json=self._own([{"id": path["id"], "data": path, "updated_at": _now()}]),
                      prefer="resolution=merge-duplicates,return=minimal", table=PATHS_TABLE)

    def add_event(self, day: str, event: str) -> None:
        """Count one event for the current person (add_usage_event: the person's own row only,
        on the server's date: `day` is the local store's)."""
        from coach import metrics
        self._uid()
        self._request("POST", json={"p_event": event}, prefer="return=minimal",
                      table="rpc/add_learning_signal" if event in metrics.SIGNALS else "rpc/add_usage_event")

    def metrics(self, since: date, today: date) -> dict:
        """The key numbers (gnosis_metrics: totals, admins only)."""
        self._uid()
        return self._request("POST", json={"p_since": since.isoformat()}, table="rpc/gnosis_metrics").json()

    def load_entry(self, day: str, topic: str):
        """The stored entry for one day and subject (a small read), or None."""
        resp = self._request("GET", params=self._mine({"select": "*", "date": f"eq.{day}", "topic": f"eq.{topic}"}))
        rows = [{k: v for k, v in row.items() if k in core.ENTRY_FIELDS} for row in resp.json()]
        entries = core.parse_log({"entries": rows})["entries"] if rows else []
        return entries[0] if entries else None

    def load_books(self) -> list:
        """The stored books (normalized); raises StorageError if they can't be read."""
        resp = self._request("GET", params=self._mine({"select": "data", "order": "updated_at.asc"}), table=BOOKS_TABLE)
        return core.parse_log({"entries": [], "books": [row["data"] for row in resp.json()]})["books"]

    def _check_lessons_column(self) -> None:
        """Find out up front whether supabase/lessons.sql has been run, so the
        daily page can ask for it before a lesson is saved without it."""
        try:
            self._request("GET", params=self._mine({"select": "lessons", "limit": "1"}))
        except StorageError as e:
            if e.status != 400:
                raise
            logger.warning("learning_entries has no lessons column; run supabase/lessons.sql")
            self.missing_columns.add("lessons")

    def _load_books(self) -> list:
        try:
            resp = self._request("GET", params=self._mine({"select": "data", "order": "updated_at.asc"}),
                                 table=BOOKS_TABLE)
        except StorageError as e:
            self.books_error = BOOKS_TABLE_MISSING if e.status == 404 else f"Reading progress: {e}. Refresh in a moment to try again."
            return []
        self.books_error = None
        return [row["data"] for row in resp.json()]

    def _upsert(self, entries: list) -> None:
        if not entries:
            return
        fields = [f for f in core.ENTRY_FIELDS if f not in self.missing_columns]
        rows = self._own([{k: e[k] for k in fields} for e in entries])
        try:
            self._request(
                "POST",
                params={"on_conflict": "user_id,date,topic" if self.scoped else "date,topic"},
                json=rows,
                prefer="resolution=merge-duplicates,return=minimal",
            )
        except StorageError as e:
            missing = [c for c in OPTIONAL_COLUMNS
                       if c not in self.missing_columns and f"'{c}'" in e.detail]
            if e.status != 400 or not missing:
                raise
            logger.warning("learning_entries lacks column(s) %s; run the matching supabase/*.sql", missing)
            self.missing_columns.update(missing)
            self._upsert(entries)

    def save_entry(self, log: dict, entry: dict) -> None:
        self._upsert([entry])

    def save_book(self, log: dict, book: dict) -> None:
        self._upsert_books([book])

    def _upsert_books(self, book_list: list) -> None:
        if not book_list:
            return
        now = _now()
        self._request(
            "POST",
            params={"on_conflict": "user_id,id" if self.scoped else "id"},
            json=self._own([{"id": b["id"], "data": b, "updated_at": now} for b in book_list]),
            prefer="resolution=merge-duplicates,return=minimal",
            table=BOOKS_TABLE,
        )

    def load_settings(self):
        """The current user's settings row, or None if they have none yet (or
        the table doesn't exist yet: then settings_missing is set)."""
        try:
            resp = self._request("GET", params={"select": "*", "user_id": f"eq.{self._uid()}"},
                                 table=SETTINGS_TABLE)
        except StorageError as e:
            if e.status != 404:
                raise
            logger.warning("no user_settings table; run supabase/user_settings.sql")
            self.settings_missing = True
            return None
        self.settings_missing = False
        rows = resp.json()
        return rows[0] if rows else None

    def save_settings(self, row: dict) -> None:
        body = {k: row.get(k) for k in SETTINGS_COLUMNS}
        body["user_id"] = self._uid()
        self._request("POST", params={"on_conflict": "user_id"}, json=[body],
                      prefer="resolution=merge-duplicates,return=minimal", table=SETTINGS_TABLE)

    def replace(self, log: dict) -> None:
        """Make the tables hold exactly this log (used by backup import).

        The backup is written first; only then are the rows it doesn't have
        removed, one by one. A failure part way (a dropped connection, a
        database error) leaves extra rows at worst, never fewer: nothing
        already saved is lost, and importing again finishes the job."""
        self._upsert(log["entries"])
        keep = {(e["date"], e["topic"]) for e in log["entries"]}
        have = self._request("GET", params=self._mine({"select": "date,topic"})).json()
        for row in have:
            if (row["date"], row["topic"]) not in keep:
                self._request("DELETE", params=self._mine({"date": f"eq.{row['date']}", "topic": f"eq.{row['topic']}"}),
                              prefer="return=minimal")
        if self.paths_error is None:
            path_list = log.get("paths", [])
            if path_list:
                self._request("POST", params={"on_conflict": "user_id,id" if self.scoped else "id"},
                              json=self._own([{"id": p["id"], "data": p, "updated_at": _now()} for p in path_list]),
                              prefer="resolution=merge-duplicates,return=minimal", table=PATHS_TABLE)
            keep_ids = {p["id"] for p in path_list}
            for row in self._request("GET", params=self._mine({"select": "id"}), table=PATHS_TABLE).json():
                if row["id"] not in keep_ids:
                    self._request("DELETE", params=self._mine({"id": f"eq.{row['id']}"}), prefer="return=minimal",
                                  table=PATHS_TABLE)
        if self.books_error is None:
            book_list = log.get("books", [])
            self._upsert_books(book_list)
            keep_ids = {b["id"] for b in book_list}
            have_ids = self._request("GET", params=self._mine({"select": "id"}), table=BOOKS_TABLE).json()
            for row in have_ids:
                if row["id"] not in keep_ids:
                    self._request("DELETE", params=self._mine({"id": f"eq.{row['id']}"}), prefer="return=minimal",
                                  table=BOOKS_TABLE)

    # ---- accounts (scoped only) ----
    def touch_user(self, email: str, name: str, picture: str = "") -> None:
        """Their users row: made the first time, last_seen_at on every sign-in."""
        uid = self._uid()
        rows = self._request("GET", params={"select": "user_id", "user_id": f"eq.{uid}"}, table=USERS_TABLE).json()
        body = {"user_id": uid, "email": email, "display_name": name, "avatar_url": picture, "last_seen_at": _now()}
        if not rows:
            body["created_at"] = _now()
        self._request("POST", params={"on_conflict": "user_id"}, json=[body],
                      prefer="resolution=merge-duplicates,return=minimal", table=USERS_TABLE)

    def user_row(self):
        rows = self._request("GET", params={"select": "*", "user_id": f"eq.{self._uid()}"}, table=USERS_TABLE).json()
        return rows[0] if rows else None

    def is_invited(self, email: str) -> bool:
        rows = self._request("GET", params={"select": "email", "email": f"eq.{email.lower()}"},
                             table=INVITES_TABLE).json()
        return bool(rows)

    def list_invites(self) -> list:
        return self._request("GET", params={"select": "*", "order": "email.asc"}, table=INVITES_TABLE).json()

    def add_invite(self, email: str, note: str = "") -> None:
        self._request("POST", params={"on_conflict": "email"},
                      json=[{"email": email.lower(), "invited_at": _now(), "note": note}],
                      prefer="resolution=merge-duplicates,return=minimal", table=INVITES_TABLE)

    def remove_invite(self, email: str) -> None:
        self._request("DELETE", params={"email": f"eq.{email.lower()}"}, prefer="return=minimal",
                      table=INVITES_TABLE)

    def usage_today(self, day: str) -> dict:
        uid = self._uid()
        rows = self._request("GET", params={"select": "*", "user_id": f"eq.{uid}", "date": f"eq.{day}"},
                             table=USAGE_TABLE).json()
        return rows[0] if rows else {"user_id": uid, "date": day, "request_count": 0, "token_count": 0}

    def add_usage(self, day: str, requests_: int, tokens_: int) -> None:
        """Add to today's count, in the database (the add_ai_usage function,
        so two tabs counting at once both count)."""
        self._uid()
        self._request("POST", json={"p_date": day, "p_requests": requests_, "p_tokens": tokens_},
                      prefer="return=minimal", table="rpc/add_ai_usage")

    def export_my_data(self) -> dict:
        uid = self._uid()
        mine = {"select": "*", "user_id": f"eq.{uid}"}
        return {
            "user": self.user_row(),
            "settings": self.load_settings(),
            "learning_entries": self._request("GET", params={**mine, "order": "date.asc,topic.asc"}).json(),
            "reading_books": [r["data"] for r in
                              self._request("GET", params={**mine, "order": "updated_at.asc"}, table=BOOKS_TABLE).json()],
            "learning_paths": [] if self.paths_error else
                              [r["data"] for r in
                               self._request("GET", params={**mine, "order": "updated_at.asc"}, table=PATHS_TABLE).json()],
            "ai_usage": self._request("GET", params={**mine, "order": "date.asc"}, table=USAGE_TABLE).json(),
            # (her own counts: supabase/goals.sql, made with learning_paths)
            "usage_events": [] if self.paths_error else
                            self._request("GET", params={**mine, "order": "day.asc"}, table=EVENTS_TABLE).json(),
            "learning_signals": self._signals(mine),
            "learner_prefs": None if self.paths_error else self.load_prefs(),
        }

    def _signals(self, mine: dict) -> list:
        """Her learning counts (supabase/mastery.sql); none where that table isn't made yet."""
        try:
            return self._request("GET", params={**mine, "order": "day.asc"}, table=SIGNALS_TABLE).json()
        except StorageError as e:
            if e.status == 404:
                return []
            raise

    def load_prefs(self):
        """Her habit preferences (coach/prefs.py), or None if she has none yet."""
        rows = self._request("GET", params=self._mine({"select": "data"}), table=PREFS_TABLE).json()
        return rows[0]["data"] if rows else None

    def save_prefs(self, data: dict) -> None:
        self._request("POST", params={"on_conflict": "user_id"},
                      json=self._own([{"data": data, "updated_at": _now()}]),
                      prefer="resolution=merge-duplicates,return=minimal", table=PREFS_TABLE)

    def delete_my_account(self) -> None:
        """All of the current user's rows in every table, their users row and
        their sign-in account, in one transaction (the delete_my_account
        function, which only ever deletes the caller): all or nothing."""
        self._uid()
        self._request("POST", json={}, prefer="return=minimal", table="rpc/delete_my_account")

    def is_admin(self, email: str) -> bool:
        """Whether this person may manage invitations (the app_admins table;
        the database only shows a person their own row)."""
        rows = self._request("GET", params={"select": "email", "email": f"eq.{email.lower()}"},
                             table=ADMINS_TABLE).json()
        return bool(rows)


class ApiStore(_Scope):
    """The same operations, on our own backend (backend/, step M2 of
    docs/ARCHITECTURE_ASSESSMENT.md) instead of Supabase. This app's server
    signs people in as before and tells the API who is acting: a service
    token (a server secret, never sent to a browser) and the person's id and
    email. Reads are retried once on a dropped connection or a 502/503/504;
    writes never are (as in SupabaseStore)."""
    name = "api"
    settings_missing = False
    books_error = None
    paths_error = None

    def __init__(self, base_url: str, token: str, session=None, scoped=True, current_user=None, current_email=None):
        if not base_url or not token:
            raise StorageError("the API address or its service token is missing")
        self.base = base_url.strip().rstrip("/")
        self.token = token
        self.session = session or requests.Session()
        self.scoped = scoped
        self.current_user = current_user
        self.current_email = current_email or (lambda: "")
        self.missing_columns = set()

    def _headers(self, person: bool = True) -> dict:
        h = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
        if person:
            h["X-Gnosis-Subject"] = self._uid()
            email = self.current_email() or ""
            if email:
                h["X-Gnosis-Email"] = email
        return h

    def _request(self, method: str, path: str, json=None, params=None, person: bool = True):
        headers = self._headers(person)
        tries = READ_TRIES if method == "GET" else 1
        for attempt in range(1, tries + 1):
            try:
                resp = self.session.request(method, f"{self.base}{path}", json=json, params=params, headers=headers,
                                            timeout=TIMEOUT)
            except requests.RequestException as e:
                if attempt < tries and isinstance(e, requests.ConnectionError):
                    logger.warning("api %s %s unreachable (%s); trying once more", method, path.split("/")[2], e)
                    _sleep(RETRY_PAUSE)
                    continue
                logger.error("api %s %s unreachable: %s", method, path.split("/")[2], e)
                raise StorageError("can't reach the server right now") from e
            if resp.status_code in TRANSIENT and attempt < tries:
                _sleep(RETRY_PAUSE)
                continue
            break
        if resp.status_code >= 400:
            # (the path names the kind of call only: no dates, emails or ids in the log)
            logger.error("api %s %s -> %s: %s", method, "/".join(path.split("/")[:4]), resp.status_code, resp.text[:300])
            if resp.status_code == 401:
                # (the person is signed in here; a refusal means this app's service token is wrong: a setup
                # problem, not a session to refresh, so no status that would send her round a reload loop)
                raise StorageError("the app can't sign in to its server; this needs fixing in its settings",
                                   detail=resp.text[:300])
            raise StorageError("the server isn't responding right now", status=resp.status_code, detail=resp.text[:300])
        return resp

    # her record
    def load(self) -> dict:
        return core.parse_log(self._request("GET", "/v1/me/record").json())

    def load_entry(self, day: str, topic: str):
        found = self._request("GET", f"/v1/me/days/{day}/{topic}").json()["entry"]
        return core.parse_log({"entries": [found]})["entries"][0] if found else None

    def load_books(self) -> list:
        return self.load()["books"]

    def save_entry(self, log: dict, entry: dict) -> None:
        self._request("PUT", f"/v1/me/days/{entry['date']}/{entry['topic']}", json=entry)

    def save_book(self, log: dict, book: dict) -> None:
        self._request("PUT", f"/v1/me/books/{book['id']}", json=book)

    def save_path(self, log: dict, path: dict) -> None:
        self._request("PUT", f"/v1/me/goals/{path['id']}", json=path)

    def replace(self, log: dict) -> None:
        self._request("PUT", "/v1/me/record", json=log)

    # her account
    def load_settings(self):
        row = self._request("GET", "/v1/me/settings").json()["settings"]
        # (the row is hers: in this app's terms that is the id she signed in with, which settings.normalize checks)
        return dict(row, user_id=self._uid()) if row else None

    def save_settings(self, row: dict) -> None:
        self._request("PUT", "/v1/me/settings", json={k: row.get(k) for k in SETTINGS_COLUMNS})

    def load_prefs(self):
        return self._request("GET", "/v1/me/preferences").json()["preferences"]

    def save_prefs(self, data: dict) -> None:
        self._request("PUT", "/v1/me/preferences", json=data)

    def touch_user(self, email: str, name: str, picture: str = "") -> None:
        self._request("POST", "/v1/me/seen", json={"email": email, "display_name": name, "avatar_url": picture})

    def user_row(self):
        return self._request("GET", "/v1/me/export").json()["user"]

    def usage_today(self, day: str) -> dict:
        return self._request("GET", f"/v1/me/usage/{day}").json()

    def add_usage(self, day: str, requests_: int, tokens_: int) -> None:
        self._request("POST", "/v1/me/usage", json={"day": day, "requests": requests_, "tokens": tokens_})

    def add_event(self, day: str, event: str) -> None:
        self._request("POST", "/v1/me/events", json={"event": event})      # (the server's date, as before)

    def export_my_data(self) -> dict:
        return self._request("GET", "/v1/me/export").json()

    def delete_my_account(self) -> None:
        self._request("DELETE", "/v1/me")

    # invitations and admins
    def is_invited(self, email: str) -> bool:
        return self._request("GET", f"/v1/invites/{email.lower()}", person=False).json()["invited"]

    def is_admin(self, email: str) -> bool:
        roles = self._request("GET", f"/v1/people/{self._uid()}/roles", person=False).json()["roles"]
        return bool({"admin", "super_admin"} & set(roles))

    def list_invites(self) -> list:
        return self._request("GET", "/v1/admin/invites").json()

    def add_invite(self, email: str, note: str = "") -> None:
        self._request("POST", "/v1/admin/invites", json={"email": email, "note": note})

    def remove_invite(self, email: str) -> None:
        self._request("DELETE", f"/v1/admin/invites/{email.lower()}")

    def metrics(self, since: date, today: date) -> dict:
        return self._request("GET", "/v1/admin/metrics", params={"since": since.isoformat()}).json()


def make_store(url: str = "", key: str = "", session=None, scoped=False, current_user=None, access_token=None,
               api_url: str = "", api_token: str = "", current_email=None):
    """Our own backend when it is configured (GNOSIS_API_URL + GNOSIS_API_TOKEN),
    else Supabase when that is, else local files."""
    if api_url and api_token:
        return ApiStore(api_url, api_token, session=session, scoped=True, current_user=current_user,
                        current_email=current_email)
    if url and key:
        return SupabaseStore(url, key, session=session, scoped=scoped, current_user=current_user,
                             access_token=access_token)
    return FileStore(scoped=scoped, current_user=current_user)
