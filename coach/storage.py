"""Where the learning log lives: a Supabase table when SUPABASE_URL and
SUPABASE_KEY are configured, otherwise a local JSON file (which Streamlit
Cloud wipes on restart)."""
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import requests

from coach import core

TABLE = "learning_entries"
BOOKS_TABLE = "reading_books"
SETTINGS_TABLE = "user_settings"
TIMEOUT = 10

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

SETTINGS_COLUMNS = ("user_id", "subjects", "units_per_day", "subject_levels", "reading_enabled",
                    "onboarding", "onboarded_at", "updated_at")


class StorageError(Exception):
    """str(e) is safe to show the user; details are logged, not shown.
    status is the HTTP status (None for connection problems)."""

    def __init__(self, message, status=None, detail=""):
        super().__init__(message)
        self.status = status
        self.detail = detail     # the raw response, for code paths only


class FileStore:
    name = "file"

    def __init__(self, path=core.DEFAULT_LOG_PATH, settings_path=None):
        self.path = path
        self.settings_path = Path(settings_path or os.environ.get("COACH_SETTINGS_PATH")
                                  or Path(path).with_name("user_settings.json"))

    books_error = None
    settings_missing = False

    def _settings_rows(self) -> list:
        try:
            rows = json.loads(self.settings_path.read_text(encoding="utf-8")).get("user_settings")
        except (FileNotFoundError, json.JSONDecodeError, AttributeError):
            return []
        return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []

    def load_settings(self, user_id: str):
        """This user's settings row, or None if she has none yet."""
        return next((r for r in self._settings_rows() if r.get("user_id") == user_id), None)

    def save_settings(self, user_id: str, row: dict) -> None:
        rows = [r for r in self._settings_rows() if r.get("user_id") != user_id]
        rows.append({**{k: row.get(k) for k in SETTINGS_COLUMNS}, "user_id": user_id})
        try:
            self.settings_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.settings_path.with_suffix(".tmp")
            tmp.write_text(json.dumps({"user_settings": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self.settings_path)
        except OSError as e:
            logger.error("saving settings failed: %s", e)
            raise StorageError("your settings couldn't be written to a file") from e

    def load(self) -> dict:
        return core.load_log(self.path)

    def save_entry(self, log: dict, entry: dict) -> None:
        try:
            core.save_log(log, self.path)
        except OSError as e:
            logger.error("saving the local log failed: %s", e)
            raise StorageError("the records couldn't be written to a file") from e

    def save_book(self, log: dict, book: dict) -> None:
        self.save_entry(log, None)

    def replace(self, log: dict) -> None:
        self.save_entry(log, None)


class SupabaseStore:
    name = "supabase"

    def __init__(self, url: str, key: str, session=None):
        # Accept the Project URL with or without the /rest/v1 suffix that
        # Supabase's "API URL" field sometimes shows.
        url = url.strip().rstrip("/")
        if url.endswith("/rest/v1"):
            url = url[: -len("/rest/v1")]
        self.base = f"{url}/rest/v1"
        # Set when the books table can't be read; the rest keeps working.
        self.books_error = None
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

    def _request(self, method, params=None, json=None, prefer=None, table=TABLE):
        headers = dict(self.headers)
        if prefer:
            headers["Prefer"] = prefer
        try:
            resp = self.session.request(
                method, f"{self.base}/{table}", params=params, json=json,
                headers=headers, timeout=TIMEOUT,
            )
        except requests.RequestException as e:
            logger.error("supabase %s %s unreachable: %s", method, table, e)
            raise StorageError("can't reach the database right now") from e
        if resp.status_code >= 400:
            logger.error("supabase %s %s -> %s: %s", method, table, resp.status_code, resp.text[:500])
            raise StorageError("the database isn't responding right now", status=resp.status_code, detail=resp.text[:500])
        return resp

    def load(self) -> dict:
        resp = self._request("GET", params={"select": "*", "order": "date.asc,topic.asc"})
        rows = resp.json()
        self._check_lessons_column()
        return core.parse_log({
            "entries": [{k: v for k, v in row.items() if k in core.ENTRY_FIELDS} for row in rows],
            "books": self._load_books(),
        })

    def _check_lessons_column(self) -> None:
        """Find out up front whether supabase/lessons.sql has been run, so the
        daily page can ask for it before a lesson is saved without it."""
        try:
            self._request("GET", params={"select": "lessons", "limit": "1"})
        except StorageError as e:
            if e.status != 400:
                raise
            logger.warning("learning_entries has no lessons column; run supabase/lessons.sql")
            self.missing_columns.add("lessons")

    def _load_books(self) -> list:
        try:
            resp = self._request("GET", params={"select": "data", "order": "updated_at.asc"},
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
        rows = [{k: e[k] for k in fields} for e in entries]
        try:
            self._request(
                "POST",
                params={"on_conflict": "date,topic"},
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
        now = datetime.now(timezone.utc).isoformat()
        self._request(
            "POST",
            params={"on_conflict": "id"},
            json=[{"id": b["id"], "data": b, "updated_at": now} for b in book_list],
            prefer="resolution=merge-duplicates,return=minimal",
            table=BOOKS_TABLE,
        )

    def load_settings(self, user_id: str):
        """This user's settings row, or None if she has none yet (or the
        table doesn't exist yet: then settings_missing is set)."""
        try:
            resp = self._request("GET", params={"select": "*", "user_id": f"eq.{user_id}"},
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

    def save_settings(self, user_id: str, row: dict) -> None:
        body = {k: row.get(k) for k in SETTINGS_COLUMNS}
        body["user_id"] = user_id
        self._request("POST", params={"on_conflict": "user_id"}, json=[body],
                      prefer="resolution=merge-duplicates,return=minimal", table=SETTINGS_TABLE)

    def replace(self, log: dict) -> None:
        """Make the tables hold exactly this log (used by backup import)."""
        # PostgREST refuses an unfiltered DELETE, so filter on a condition
        # every row meets.
        self._request("DELETE", params={"date": "gte.1900-01-01"}, prefer="return=minimal")
        self._upsert(log["entries"])
        if self.books_error is None:
            self._request("DELETE", params={"id": "neq."}, prefer="return=minimal",
                          table=BOOKS_TABLE)
            self._upsert_books(log.get("books", []))


def make_store(url: str = "", key: str = "", session=None):
    if url and key:
        return SupabaseStore(url, key, session=session)
    return FileStore()
