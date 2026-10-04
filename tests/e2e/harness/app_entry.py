"""The app as the end-to-end tests run it: the real GNOSIS app and its routes,
with only two things replaced, both read from the test's state directory:

- the Groq client (fake_groq.py): no real model, no cost; failures on demand;
- the clock: today's date and "now" come from clock.json when it exists, so
  tests can move through days and across midnight.

Run by conftest.py as `streamlit run tests/e2e/harness/app_entry.py`.
Secrets come from the environment (E2E_SECRETS as JSON), never from a file.
"""
import json
import os
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st  # noqa: E402

import fake_groq  # noqa: E402
from coach import clock, llm, routes  # noqa: E402

STATE = Path(os.environ["E2E_STATE_DIR"])


def _clock():
    try:
        return json.loads((STATE / "clock.json").read_text())
    except (FileNotFoundError, ValueError):
        return {}


_real_today = clock.today


def fake_today() -> date:
    c = _clock()
    return date.fromisoformat(c["date"]) if c.get("date") else _real_today()


def fake_now_iso() -> str:
    c = _clock()
    if c.get("date"):
        return datetime.fromisoformat(c["date"] + "T" + c.get("time", "02:00:00") + "+00:00").isoformat()
    return datetime.now(timezone.utc).isoformat()


clock.today = fake_today            # the one clock (coach/clock.py): the whole app moves with it
clock.now_iso = fake_now_iso
_real_get_client = llm.get_client
llm.get_client = lambda: fake_groq.FakeGroq() if st.session_state.get("api_key") else None
llm._sleep = lambda s: time.sleep(min(float(s), 0.05))       # backoff runs, just fast

app = st.App(str(ROOT / "gnosis.py"), routes=routes.all_routes(), middleware=routes.middleware(),
             secrets=json.loads(os.environ.get("E2E_SECRETS", "{}")))
