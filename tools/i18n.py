"""The site's sentences and their translations (coach/i18n.py).

    python tools/i18n.py                 how many sentences, and how many each language has
    python tools/i18n.py --missing zh-Hant   the sentences zh-Hant doesn't have yet, as JSON (to translate)
    python tools/i18n.py --unused zh-Hant    translations no sentence in the code uses any more

A sentence is the first argument of every tr("…"), N_("…") and tr_in(lang, "…")
call, and both of trn("…one…", "…many…", n)
in coach/, views/ and gnosis.py, plus the fixed texts listed in TEXTS (names,
descriptions and other words kept in data, not in a tr() call)."""
import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PARTS = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)[^{}]*\}")
TAGS = re.compile(r"</?([a-zA-Z][a-zA-Z0-9]*)")


def sentences() -> dict:
    """Every sentence → where it is first used ("file:line")."""
    out = {}
    files = sorted((ROOT / "coach").glob("*.py")) + sorted((ROOT / "views").glob("*.py")) + [ROOT / "gnosis.py"]
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for n in ast.walk(tree):
            if not isinstance(n, ast.Call) or not isinstance(n.func, ast.Name):
                continue
            arg = n.args[0] if n.func.id in ("tr", "N_") and n.args else (
                n.args[1] if n.func.id == "tr_in" and len(n.args) > 1 else None)
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                out.setdefault(arg.value, f"{path.relative_to(ROOT)}:{n.lineno}")
            if n.func.id == "trn":
                for a in n.args[:2]:
                    if isinstance(a, ast.Constant) and isinstance(a.value, str):
                        out.setdefault(a.value, f"{path.relative_to(ROOT)}:{n.lineno}")
    from coach import i18n
    for text in i18n.texts():
        out.setdefault(text, "data")
    return out


def problems(code: str) -> list:
    """What is wrong with a language's file: a translation whose {parts} or
    tags differ from its English."""
    from coach import i18n
    bad = []
    for en, local in i18n.catalog(code).items():
        if not isinstance(local, str) or not local.strip():
            bad.append(f"{code}: empty translation for {en[:60]!r}")
            continue
        if sorted(PARTS.findall(en)) != sorted(PARTS.findall(local)):
            bad.append(f"{code}: parts differ in {en[:60]!r}")
        if sorted(TAGS.findall(en)) != sorted(TAGS.findall(local)):
            bad.append(f"{code}: tags differ in {en[:60]!r}")
    return bad


if __name__ == "__main__":
    from coach import i18n
    every = sentences()
    if "--missing" in sys.argv:
        code = sys.argv[sys.argv.index("--missing") + 1]
        have = i18n.catalog(code)
        print(json.dumps({k: "" for k in every if k not in have}, ensure_ascii=False, indent=1))
    elif "--unused" in sys.argv:
        code = sys.argv[sys.argv.index("--unused") + 1]
        print("\n".join(k for k in i18n.catalog(code) if k not in every))
    else:
        print(f"{len(every)} sentences")
        for code in i18n.offered():
            if code != i18n.DEFAULT:
                have = i18n.catalog(code)
                print(f"{code}: {sum(1 for k in every if k in have)} translated, "
                      f"{sum(1 for k in every if k not in have)} missing, {len(problems(code))} problems")
