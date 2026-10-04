"""The layers stay layered (ARCHITECTURE.md): the rules of GNOSIS are pure
functions anyone can test without Streamlit, and the data, auth and AI
modules don't depend on the UI helpers."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "coach"

# what learning is: the day, the syllabus, quizzes, review, goals, settings, the numbers
PURE = ("books", "catalog", "clock", "core", "course", "curriculum", "history", "metrics", "paths",
        "placement", "plans", "quiz", "review", "search", "settings", "steps", "tokens")
# what talks to the outside: the database, sign-in, the model
NO_UI = ("appconfig", "llm", "quizgen", "quota", "routes", "session_cookie", "storage", "supa_auth")


def imports(name: str) -> set:
    tree = ast.parse((ROOT / f"{name}.py").read_text(encoding="utf-8"))
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            out |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            out |= {f"coach.{a.name}" for a in n.names} if n.module == "coach" else {n.module.split(".")[0]}
    return out


def test_the_rules_are_pure():
    io = {"streamlit", "coach.ui", "coach.storage", "requests", "groq"}
    bad = {m: sorted(imports(m) & io) for m in PURE}
    assert not {m: found for m, found in bad.items() if found}, bad


def test_data_auth_and_ai_dont_depend_on_the_ui_helpers():
    bad = {m: "coach.ui" for m in NO_UI if "coach.ui" in imports(m)}
    assert not bad, bad
