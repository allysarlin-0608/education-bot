"""Where the learning log lives: a Supabase table when SUPABASE_URL and
SUPABASE_KEY are configured, otherwise a local JSON file (which Streamlit
Cloud wipes on restart)."""
from datetime import datetime, timezone

import requests

from coach import core

TABLE = "learning_entries"
BOOKS_TABLE = "reading_books"
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

BOOKS_TABLE_MISSING = (
    "Supabase 裡還沒有 reading_books 資料表。到 Supabase 的 SQL Editor 執行 "
    "supabase/books.sql 的內容，就可以開始用看書的進度追蹤。"
)


class StorageError(Exception):
    pass


class FileStore:
    name = "file"

    def __init__(self, path=core.DEFAULT_LOG_PATH):
        self.path = path

    books_error = None

    def load(self) -> dict:
        return core.load_log(self.path)

    def save_entry(self, log: dict, entry: dict) -> None:
        try:
            core.save_log(log, self.path)
        except OSError as e:
            raise StorageError(str(e)) from e

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
            raise StorageError(f"連不到 Supabase：{e}") from e
        if resp.status_code >= 400:
            raise StorageError(f"Supabase 回應 {resp.status_code}：{resp.text[:300]}")
        return resp

    def load(self) -> dict:
        resp = self._request("GET", params={"select": "*", "order": "date.asc,topic.asc"})
        rows = resp.json()
        return core.parse_log({
            "entries": [{k: v for k, v in row.items() if k in core.ENTRY_FIELDS} for row in rows],
            "books": self._load_books(),
        })

    def _load_books(self) -> list:
        try:
            resp = self._request("GET", params={"select": "data", "order": "updated_at.asc"},
                                 table=BOOKS_TABLE)
        except StorageError as e:
            self.books_error = BOOKS_TABLE_MISSING if "404" in str(e) or "42P01" in str(e) else str(e)
            return []
        self.books_error = None
        return [row["data"] for row in resp.json()]

    def _upsert(self, entries: list) -> None:
        if not entries:
            return
        rows = [{k: e[k] for k in core.ENTRY_FIELDS} for e in entries]
        self._request(
            "POST",
            params={"on_conflict": "date,topic"},
            json=rows,
            prefer="resolution=merge-duplicates,return=minimal",
        )

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
