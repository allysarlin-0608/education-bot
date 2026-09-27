"""Give one TEST account a 30+ day history (for trying Progress, streaks and
Search with real-looking data). For the TEST Supabase project only.

    python tools/seed_test_db.py --url https://<test-ref>.supabase.co --ref <test-ref> \\
        --user-id <their user id> [--days 35] [--apply]

The key is read from the environment (SUPABASE_SERVICE_KEY), never from the
command line, and never printed. Without --apply it only shows what it would
write (a dry run). It refuses to run when:
  - --ref doesn't match the project in --url (a typo guard: you name the
    project twice);
  - the database has no app_admins table (only the TEST project has the
    accounts setup; the personal database doesn't, so it is refused);
  - the user id isn't a signed-up person in public.users;
  - that person already has any learning entries (nothing is ever
    overwritten or deleted: new rows only).
"""
import argparse
import os
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
import seed_history  # noqa: E402
from coach import core  # noqa: E402


def refuse(why):
    sys.exit(f"Refused: {why}. Nothing was written.")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", required=True)
    ap.add_argument("--ref", required=True, help="the TEST project's reference, again (typo guard)")
    ap.add_argument("--user-id", required=True)
    ap.add_argument("--days", type=int, default=35)
    ap.add_argument("--apply", action="store_true", help="write (default: dry run)")
    a = ap.parse_args(argv)
    host = urlparse(a.url).hostname or ""
    if not host.endswith(".supabase.co") or host.split(".")[0] != a.ref:
        refuse(f"--ref {a.ref!r} is not the project in --url ({host})")
    key = os.environ.get("SUPABASE_SERVICE_KEY", "")
    if not key:
        refuse("set SUPABASE_SERVICE_KEY in the environment first")
    if not 1 <= a.days <= 400:
        refuse("--days must be between 1 and 400")
    s = requests.Session()
    s.headers.update({"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    rest = a.url.rstrip("/") + "/rest/v1/"

    def get(table, **params):
        r = s.get(rest + table, params=params, timeout=15)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()

    if get("app_admins", select="email", limit=1) is None:
        refuse("this database has no app_admins table, so it isn't the TEST project")
    if not get("users", select="user_id", user_id=f"eq.{a.user_id}"):
        refuse(f"no signed-up person with user id {a.user_id} (public.users)")
    if get("learning_entries", select="date", user_id=f"eq.{a.user_id}", limit=1):
        refuse("this person already has learning entries; nothing is overwritten")

    today = datetime.now(ZoneInfo("Asia/Taipei")).date()
    entries = seed_history.build(today, days=a.days)
    rows = [dict({k: e[k] for k in core.ENTRY_FIELDS}, user_id=a.user_id) for e in entries]
    exp = seed_history.expected(entries, today)
    print(f"{len(rows)} entries from {rows[0]['date']} to {rows[-1]['date']} for {a.user_id}")
    print(f"Progress should then show: {exp}")
    if not a.apply:
        print("Dry run: nothing written. Add --apply to write these rows.")
        return
    r = s.post(rest + "learning_entries", json=rows, timeout=30,
               headers={"Prefer": "resolution=ignore-duplicates,return=minimal"})
    r.raise_for_status()
    print(f"Written: {len(rows)} new rows.")


if __name__ == "__main__":
    main()
