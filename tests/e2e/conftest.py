"""End-to-end fixtures: the real app in a real browser (Chromium via Playwright).

    pytest tests/e2e                 # the full suite
    pytest tests/e2e -m smoke        # a quick smoke test
    python tests/e2e/monkey.py       # the monkey test

Two app servers can run: APP_MODE=public (with a fake Supabase: Auth, RLS,
outbox) and APP_MODE=personal (password; local files). Neither touches a
real database or a real model (harness/fake_groq.py). Every test:
- fails if the server log shows a Python traceback while it ran;
- fails if the page raised a JavaScript error or opened an alert() (an
  injected script that ran);
- can record timings (results/timings.jsonl) and screenshots (results/shots).
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
EXE = os.environ.get("E2E_CHROMIUM", "/opt/pw-browsers/chromium-1194/chrome-linux/chrome")
IPHONE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) "
          "Version/17.5 Mobile/15E148 Safari/604.1")
IPAD = ("Mozilla/5.0 (iPad; CPU OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.5 Mobile/15E148 Safari/604.1")
WIDTHS = {390: 844, 768: 1024, 1024: 768, 1180: 820, 1440: 900, 1920: 1080}
ADMIN = "admin@example.com"
PASSWORD = "learn well 7"


def covers(*ids):
    """Marks which FEATURE_INVENTORY items a test exercises (read by tools/inventory.py)."""
    return ids


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait(url, timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        try:
            urllib.request.urlopen(url, timeout=2)
            return
        except Exception:
            time.sleep(0.3)
    raise RuntimeError(f"{url} did not come up")


class App:
    """One running app server (and, in public mode, its fake Supabase)."""

    def __init__(self, mode):
        self.mode = mode
        self.state = RESULTS / "state" / mode
        shutil.rmtree(self.state, ignore_errors=True)
        self.state.mkdir(parents=True)
        self.port = _free_port()
        self.url = f"http://localhost:{self.port}"
        self.procs = []
        env = dict(os.environ, E2E_STATE_DIR=str(self.state), PYTHONUNBUFFERED="1",
                   STREAMLIT_SERVER_COOKIE_SECRET="e2e-cookie-secret-0123456789abcdef-0123456789",
                   STREAMLIT_BROWSER_GATHER_USAGE_STATS="false",
                   # one server here serves many people's lessons a minute; the
                   # per-minute pacing itself is tested in tests/test_llm.py
                   GROQ_TPM_LIMIT="10000000")
        secrets = {"GROQ_API_KEY": "fake-key-for-tests"}
        if mode == "public":
            self.fake_port = _free_port()
            self.fake = f"http://127.0.0.1:{self.fake_port}"
            fenv = dict(env, FAKE_SUPABASE_PORT=str(self.fake_port), FAKE_ACCESS_TTL="3600")
            self.fake_log = open(self.state / "fake.log", "w")
            self.procs.append(subprocess.Popen([sys.executable, str(ROOT / "tests" / "fake_supabase.py")],
                                               cwd=ROOT, env=fenv, stdout=self.fake_log, stderr=subprocess.STDOUT))
            _wait(self.fake + "/__outbox")
            secrets.update(APP_MODE="public", APP_URL=self.url, SUPABASE_URL=self.fake,
                           SUPABASE_KEY="sb_publishable_test",
                           auth={"cookie_secret": "e2e-cookie-secret-0123456789abcdef-0123456789",
                                 "expose_tokens": "access"})
            self.post("/__seed", {"app_admins": [{"email": ADMIN}]})
        else:
            secrets.update(APP_MODE="personal", APP_PASSWORD="pw", COACH_USER_ID="e2e-owner")
            env.update(COACH_LOG_PATH=str(self.state / "learning_log.json"),
                       COACH_SETTINGS_PATH=str(self.state / "user_settings.json"))
        env["E2E_SECRETS"] = json.dumps(secrets)
        self.log_path = self.state / "server.log"
        self.log = open(self.log_path, "w")
        self.procs.append(subprocess.Popen(
            [sys.executable, "-m", "streamlit", "run", str(HERE / "harness" / "app_entry.py"),
             "--server.port", str(self.port), "--server.headless", "true", "--server.runOnSave", "false",
             "--server.fileWatcherType", "none"],
            cwd=ROOT, env=env, stdout=self.log, stderr=subprocess.STDOUT))
        _wait(self.url + "/_stcore/health", 90)
        self.set_llm()

    # ---- control
    def set_llm(self, **ctl):
        (self.state / "llm.json").write_text(json.dumps(ctl))
        (self.state / "flagged_once").unlink(missing_ok=True)

    def set_clock(self, day=None, time_="02:00:00"):
        if day is None:
            (self.state / "clock.json").unlink(missing_ok=True)
        else:
            (self.state / "clock.json").write_text(json.dumps({"date": str(day), "time": time_}))

    def calls(self, kind=None):
        try:
            rows = [json.loads(line) for line in open(self.state / "calls.jsonl")]
        except FileNotFoundError:
            return []
        return [r for r in rows if kind is None or r["kind"] == kind]

    def reset_calls(self):
        (self.state / "calls.jsonl").unlink(missing_ok=True)

    def post(self, path, body):
        req = urllib.request.Request(self.fake + path, data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        return json.loads(urllib.request.urlopen(req).read() or b"null")

    def get(self, path):
        return json.loads(urllib.request.urlopen(self.fake + path).read())

    def seed_entries(self, email, entries):
        """Put learning entries straight into this app's store (the fake
        database, or the personal app's file)."""
        if self.mode == "public":
            uid = next(u["id"] for u in self.get("/__dump")["users"] if u["email"] == email.lower())
            self.post("/__seed", {"learning_entries": [dict(e, user_id=uid) for e in entries]})
        else:
            path = self.state / "learning_log.json"
            try:
                have = json.loads(path.read_text())["entries"]
            except FileNotFoundError:
                have = []
            keep = {(e["date"], e["topic"]) for e in entries}
            path.write_text(json.dumps({"version": 1, "entries": [e for e in have if (e["date"], e["topic"]) not in keep]
                                        + entries}))

    def log_text(self):
        return self.log_path.read_text(errors="replace")

    def stop(self):
        for p in self.procs:
            p.terminate()
        for p in self.procs:
            try:
                p.wait(10)
            except subprocess.TimeoutExpired:
                p.kill()


_apps = {}


def app_for(mode):
    if mode not in _apps:
        _apps[mode] = App(mode)
    return _apps[mode]


@pytest.fixture(scope="session")
def public_app():
    return app_for("public")


@pytest.fixture(scope="session")
def personal_app():
    return app_for("personal")


def pytest_sessionfinish(session, exitstatus):
    for a in _apps.values():
        a.stop()


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=EXE)
        yield b
        b.close()


class Page:
    """A browser tab with what the audit checks recorded."""

    def __init__(self, browser, width=1440, height=None, scheme="light", device=None, reduced_motion=False):
        touch = width < 1300          # phones and both iPad orientations (her iPad, landscape, is 1180)
        ua = IPHONE if width < 500 else (IPAD if device == "ipad" or 700 < width < 1300 and touch else None)
        self.ctx = browser.new_context(viewport={"width": width, "height": height or WIDTHS.get(width, 900)},
                                       color_scheme=scheme, has_touch=touch, is_mobile=touch and width < 500,
                                       reduced_motion="reduce" if reduced_motion else "no-preference",
                                       accept_downloads=True, **({"user_agent": ua} if ua else {}))
        self.page = self.ctx.new_page()
        self.width = width
        self.errors, self.dialogs, self.console = [], [], []
        self.page.on("pageerror", lambda e: self.errors.append(str(e)[:300]))
        self.page.on("console", lambda m: self.console.append((m.type, m.text[:300])) if m.type in ("error", "warning") else None)

        def on_dialog(d):
            self.dialogs.append(d.message)
            d.dismiss()
        self.page.on("dialog", on_dialog)
        self.page.route("https://fonts.g*/**", lambda r: r.abort())

    def close(self):
        self.ctx.close()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    setattr(item, "rep_" + rep.when, rep)


@pytest.fixture
def pages(browser, request):
    made = []

    def make(**kw):
        p = Page(browser, **kw)
        made.append(p)
        return p
    yield make
    rep = getattr(request.node, "rep_call", None)
    if rep is not None and rep.failed:
        shots = RESULTS / "failures"
        shots.mkdir(parents=True, exist_ok=True)
        name = "".join(c if c.isalnum() else "_" for c in request.node.nodeid)[-120:]
        for k, p in enumerate(made):
            try:
                p.page.screenshot(path=str(shots / f"{name}_{k}.png"), full_page=True)
            except Exception:
                pass
    problems = []
    for p in made:
        if p.errors:
            problems.append(f"JavaScript errors: {p.errors}")
        if p.dialogs:
            problems.append(f"alert() ran (injected script executed): {p.dialogs}")
        errors = [c for c in p.console if c[0] == "error" and "fonts.g" not in c[1] and "net::ERR_FAILED" not in c[1]]
        if errors:
            _record("console_errors", {"test": request.node.nodeid, "errors": errors})
        p.close()
    assert not problems, problems


@pytest.fixture(autouse=True)
def no_leftover_failures():
    """Failures a test injected but didn't use up never reach the next test."""
    yield
    if "public" in _apps:
        _apps["public"].post("/__fail", {"clear": True})


@pytest.fixture(autouse=True)
def no_server_tracebacks(request):
    """Fail the test if any running app logged a Python traceback during it."""
    before = {m: len(a.log_text()) for m, a in _apps.items()}
    yield
    for m, a in _apps.items():
        new = a.log_text()[before.get(m, 0):]
        if "Traceback (most recent call last)" in new or "Uncaught app exception" in new:
            pytest.fail(f"{m} server logged a traceback:\n{new[-3000:]}")


def _record(kind, row):
    RESULTS.mkdir(parents=True, exist_ok=True)
    with open(RESULTS / f"{kind}.jsonl", "a") as f:
        f.write(json.dumps(row) + "\n")


def record_timing(action, seconds, **extra):
    _record("timings", {"action": action, "seconds": round(seconds, 3), **extra})
