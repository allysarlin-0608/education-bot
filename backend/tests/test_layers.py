"""The backend's boundaries (ADR 0001, 0003, 0005), checked on every run:
- nothing in `gnosis` imports Streamlit, the current app's UI or storage
  modules, a Supabase client or a model SDK;
- from the shared package it uses only the pure domain modules;
- routes don't reach into the database directly (api → services/data only
  through repositories)."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "gnosis"
FORBIDDEN = {"streamlit", "groq", "openai", "anthropic", "supabase", "requests",
             "coach.ui", "coach.storage", "coach.auth", "coach.supa_auth", "coach.routes", "coach.session_cookie",
             "coach.llm", "coach.quizgen", "coach.quota"}
PURE_DOMAIN = {"coach.books", "coach.catalog", "coach.clock", "coach.core", "coach.course", "coach.curriculum",
               "coach.habit", "coach.history", "coach.mastery", "coach.metrics", "coach.paths", "coach.placement",
               "coach.plans", "coach.practice", "coach.prefs", "coach.quiz", "coach.review", "coach.search",
               "coach.settings", "coach.steps", "coach.streaks", "coach.tokens"}


def imports(path: Path) -> set:
    out = set()
    for n in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(n, ast.Import):
            out |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            out |= {f"{n.module}.{a.name}" for a in n.names} if n.module == "coach" else {n.module}
    return out


def modules():
    return {p.relative_to(ROOT.parent).as_posix(): imports(p) for p in ROOT.rglob("*.py")}


def test_no_vendor_or_ui_code_in_the_backend():
    bad = {m: sorted(i for i in found if i in FORBIDDEN or i.split(".")[0] in FORBIDDEN)
           for m, found in modules().items()}
    assert not {m: v for m, v in bad.items() if v}, bad


def test_only_the_pure_domain_is_shared():
    used = {i for found in modules().values() for i in found if i.startswith("coach")}
    assert used <= PURE_DOMAIN, used - PURE_DOMAIN


def test_routes_go_through_services_and_repositories():
    """A route may name the connection type it is handed, never build a query or touch a table."""
    for m, found in modules().items():
        if m.startswith("gnosis/api/"):
            direct = {i for i in found if (i.startswith("sqlalchemy") and i != "sqlalchemy.engine")
                      or i.startswith("gnosis.data.schema")}
            assert not direct, f"{m} talks to the database itself: {direct}"
