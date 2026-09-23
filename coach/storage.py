"""Where the learning log lives: a Supabase table when SUPABASE_URL and
SUPABASE_KEY are configured, otherwise a local JSON file (which Streamlit
Cloud wipes on restart)."""
import requests

from coach import core

TABLE = "learning_entries"
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


class StorageError(Exception):
    pass


class FileStore:
    name = "file"

    def __init__(self, path=core.DEFAULT_LOG_PATH):
        self.path = path

    def load(self) -> dict:
        return core.load_log(self.path)

    def save_entry(self, log: dict, entry: dict) -> None:
        try:
            core.save_log(log, self.path)
        except OSError as e:
            raise StorageError(str(e)) from e

    def replace(self, log: dict) -> None:
        self.save_entry(log, None)


class SupabaseStore:
    name = "supabase"

    def __init__(self, url: str, key: str, session=None):
        self.endpoint = f"{url.rstrip('/')}/rest/v1/{TABLE}"
        self.session = session or requests.Session()
        self.headers = {"apikey": key, "Content-Type": "application/json"}
        # Legacy service_role keys are JWTs and also go in Authorization;
        # new sb_secret_ keys only go in the apikey header.
        if key.startswith("eyJ"):
            self.headers["Authorization"] = f"Bearer {key}"

    def _request(self, method, params=None, json=None, prefer=None):
        headers = dict(self.headers)
        if prefer:
            headers["Prefer"] = prefer
        try:
            resp = self.session.request(
                method, self.endpoint, params=params, json=json,
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
        return core.parse_log({"entries": [
            {k: v for k, v in row.items() if k in core.ENTRY_FIELDS} for row in rows
        ]})

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

    def replace(self, log: dict) -> None:
        """Make the table hold exactly this log (used by backup import)."""
        # PostgREST refuses an unfiltered DELETE, so filter on a condition
        # every row meets.
        self._request("DELETE", params={"date": "gte.1900-01-01"}, prefer="return=minimal")
        self._upsert(log["entries"])


def make_store(url: str = "", key: str = "", session=None):
    if url and key:
        return SupabaseStore(url, key, session=session)
    return FileStore()
