"""Every name the app takes from its own modules exists.

The course map crashed on `ui.open_course` (BUG-030). Whatever the route by
which code and module drift apart (a rename, a deleted helper, a module
not saved with the change), the result is the same: a page calls a name
the module doesn't have, and nothing notices until someone presses the
button. This reads every app file (pages, the entry points, coach/) and
checks each `module.name` and `from coach.module import name` against the
module itself, so such a call fails here, before any push."""
import ast
import importlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FILES = sorted([*ROOT.glob("coach/*.py"), *ROOT.glob("views/*.py"), ROOT / "gnosis.py", ROOT / "streamlit_app.py"])


def references(path: Path):
    """(line, module name, attribute) for each use of an app module's name in this file."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    aliases = {}                                  # local name -> "coach.x"
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "coach":
            for a in node.names:
                aliases[a.asname or a.name] = f"coach.{a.name}"
        elif isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("coach."):
            for a in node.names:
                out.append((node.lineno, node.module, a.name))
        elif isinstance(node, ast.Import):
            for a in node.names:
                if a.name.startswith("coach.") and a.asname:
                    aliases[a.asname] = a.name
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in aliases:
            out.append((node.lineno, aliases[node.value.id], node.attr))
    return out


@pytest.mark.parametrize("path", FILES, ids=lambda p: str(p.relative_to(ROOT)))
def test_every_name_taken_from_an_app_module_exists(path):
    missing = []
    for line, module, name in references(path):
        mod = importlib.import_module(module)
        if not hasattr(mod, name):
            missing.append(f"{path.relative_to(ROOT)}:{line} {module}.{name}")
    assert not missing, "names that don't exist: " + ", ".join(missing)


def test_the_check_would_have_caught_the_course_map_crash(tmp_path):
    page = tmp_path / "page.py"
    page.write_text("from coach import ui\nui.open_course_map('x')\n")
    assert (2, "coach.ui", "open_course_map") in references(page)
    assert not hasattr(importlib.import_module("coach.ui"), "open_course_map")


@pytest.mark.parametrize("path", FILES, ids=lambda p: str(p.relative_to(ROOT)))
def test_no_file_relies_on_something_python_is_retiring(path):
    """An invalid escape like "\\/" in a string (a JavaScript regex inside a
    Python string) is a warning today and an error in a later Python."""
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
