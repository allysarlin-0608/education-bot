"""Build FEATURE_INVENTORY.md from the code: every widget, callback, database
write, AI call and setting, each with a stable ID; and, with --coverage,
which of them the tests cover.

A test covers an item by naming its ID in a `covers(...)` call or a
`# covers: ID, ID` comment anywhere under tests/.

    python tools/inventory.py             # write FEATURE_INVENTORY.md
    python tools/inventory.py --coverage  # also list uncovered items; exit 1 if any
"""
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = [ROOT / "gnosis.py", *sorted((ROOT / "coach").glob("*.py")), *sorted((ROOT / "views").glob("*.py"))]
WIDGETS = {"button", "text_input", "text_area", "radio", "selectbox", "toggle", "chat_input", "expander",
           "form", "form_submit_button", "file_uploader", "checkbox", "segmented_control", "pills",
           "download_button", "page_link", "popover", "slider", "number_input", "tabs", "link_button",
           "multiselect"}
WRITES = {"save_entry", "save_day", "save_book", "save_settings", "replace", "touch_user", "add_invite", "remove_invite",
          "add_usage", "delete_my_account"}
AI = {"ask_json", "stream_reply", "stream_text"}


# settings read under a name built at run time
EXTRA_SETTINGS = [("AI_DAILY_REQUEST_LIMIT", "coach/quota.py:23"), ("AI_DAILY_TOKEN_LIMIT", "coach/quota.py:23")]


def _text(node) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(v.value if isinstance(v, ast.Constant) else "{…}" for v in node.values)
    return ast.unparse(node) if node is not None else ""


def _kw(call, name):
    for k in call.keywords:
        if k.arg == name:
            return k.value
    return None


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")[:40] or "x"


def scan():
    items = []
    for path in SOURCES:
        rel = path.relative_to(ROOT).as_posix()
        mod = path.stem
        tree = ast.parse(path.read_text(encoding="utf-8"))
        seen = {}
        calls = sorted((n for n in ast.walk(tree) if isinstance(n, ast.Call)), key=lambda n: (n.lineno, n.col_offset))
        for node in calls:
            if not isinstance(node, ast.Call):
                continue
            f = node.func
            name = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else "")
            owner = ast.unparse(f.value) if isinstance(f, ast.Attribute) else ""
            kind = None
            if name in WIDGETS and owner.split(".")[-1] in ("st", "start", "slot", "box", "col", "c") or \
                    (name in WIDGETS and owner.endswith("st")):
                kind = "widget"
            elif name in WIDGETS and isinstance(f, ast.Attribute) and owner not in ("self",):
                kind = "widget"
            elif name in WRITES and ("store" in owner or owner.endswith("coach_store") or owner == "ui"):
                kind = "write"
            elif name in AI and owner == "llm":
                kind = "ai"
            elif name == "get_setting":
                kind = "setting"
            elif name in ("get", "getenv") and owner in ("os.environ", "os"):
                kind = "setting"
            if not kind:
                continue
            label = _text(node.args[0]) if node.args else ""
            key = _text(_kw(node, "key")) if _kw(node, "key") is not None else ""
            cb = _kw(node, "on_click") or _kw(node, "on_change")
            if kind == "setting" and not (node.args and isinstance(node.args[0], ast.Constant)):
                continue                     # a name built at run time: listed from EXTRA_SETTINGS
            base = {"widget": f"W-{mod}-{_slug(key or label or name)}", "write": f"D-{mod}-{name}",
                    "ai": f"AI-{mod}-{name}", "setting": f"S-{_slug(label)}"}[kind]
            if kind == "setting":
                if any(i["id"] == base for i in items):
                    continue
            n = seen.get(base, 0)
            seen[base] = n + 1
            iid = base if n == 0 else f"{base}-{n + 1}"
            items.append({"id": iid, "kind": kind, "type": name, "file": f"{rel}:{node.lineno}",
                          "label": label, "key": key, "callback": ast.unparse(cb) if cb is not None else ""})
    for name, where in EXTRA_SETTINGS:
        items.append({"id": f"S-{_slug(name)}", "kind": "setting", "type": "get_setting", "file": where,
                      "label": name, "key": "", "callback": ""})
    return sorted(items, key=lambda i: (i["kind"], i["file"].split(":")[0], int(i["file"].split(":")[1])))


def covered_ids():
    ids = set()
    for p in (ROOT / "tests").rglob("*.py"):
        text = p.read_text(encoding="utf-8")
        for m in re.finditer(r"covers\(([^)]*)\)|#\s*covers:\s*([^\n]+)", text):
            ids.update(re.findall(r"[A-Z]{1,2}-[A-Za-z0-9_\-{}…]+", m.group(1) or m.group(2)))
    return ids


def write(items, cov):
    kinds = [("widget", "Widgets (every interactive element)"), ("write", "Database writes"),
             ("ai", "AI calls"), ("setting", "Settings and environment variables")]
    lines = ["# Feature inventory", "",
             "Generated by `python tools/inventory.py` from the code (do not edit by hand).",
             "A test covers an item by naming its ID (`covers(\"ID\")` or `# covers: ID`).", ""]
    total = len(items)
    done = sum(1 for i in items if i["id"] in cov)
    lines += [f"**Coverage: {done}/{total} ({100 * done // max(total, 1)}%)**", ""]
    for kind, title in kinds:
        rows = [i for i in items if i["kind"] == kind]
        lines += [f"## {title} ({len(rows)})", "", "| ID | Type | Where | Label / name | Key | Callback | Covered |",
                  "|---|---|---|---|---|---|---|"]
        for i in rows:
            esc = lambda s: s.replace("|", "\\|").replace("\n", " ")[:70]  # noqa: E731
            lines.append(f"| {i['id']} | {i['type']} | {i['file']} | {esc(i['label'])} | {esc(i['key'])} | "
                         f"{esc(i['callback'])} | {'✅' if i['id'] in cov else '—'} |")
        lines.append("")
    (ROOT / "FEATURE_INVENTORY.md").write_text("\n".join(lines), encoding="utf-8")
    return done, total


if __name__ == "__main__":
    items = scan()
    cov = covered_ids()
    if "--check" in sys.argv:          # (before a push: say what's uncovered, write nothing)
        missing = [i["id"] for i in items if i["id"] not in cov]
        for m in missing:
            print("UNCOVERED", m)
        print(f"{len(items)} items, {len(items) - len(missing)} covered")
        sys.exit(1 if missing else 0)
    done, total = write(items, cov)
    print(f"{total} items, {done} covered")
    if "--coverage" in sys.argv:
        missing = [i["id"] for i in items if i["id"] not in cov]
        for m in missing:
            print("UNCOVERED", m)
        sys.exit(1 if missing else 0)
