"""Add or update an entry in BUGLOG.md (the audit's bug log).

    python tools/buglog.py add ID SEV "page/flow" "summary" "status" \\
        --repro "..." --expected "..." --actual "..." --cause "..." --fix "..." --files "..." --test "..."
    python tools/buglog.py status ID "fixed (abc1234)"
"""
import argparse
import re
from pathlib import Path

LOG = Path(__file__).resolve().parents[1] / "BUGLOG.md"
FIELDS = ["repro", "expected", "actual", "cause", "fix", "files", "test"]
NAMES = {"repro": "Steps to reproduce", "expected": "Expected", "actual": "Actual", "cause": "Root cause",
         "fix": "Fix", "files": "Files changed", "test": "Covered by"}


def add(a):
    text = LOG.read_text(encoding="utf-8")
    head, _, details = text.partition("## Details")
    row = f"| {a.id} | {a.sev} | {a.page} | {a.summary} | {a.status} |"
    if f"| {a.id} |" in head:
        head = re.sub(rf"^\| {re.escape(a.id)} \|.*$", row, head, flags=re.M)
    else:
        head = head.rstrip("\n") + "\n" + row + "\n\n"
    block = [f"### {a.id} ({a.sev}) — {a.summary}", f"- **Page / flow:** {a.page}", f"- **Status:** {a.status}"]
    block += [f"- **{NAMES[f]}:** {getattr(a, f)}" for f in FIELDS if getattr(a, f)]
    block = "\n".join(block) + "\n"
    details = re.sub(rf"\n### {re.escape(a.id)} \(.*?(?=\n### |\Z)", "\n", details, flags=re.S)
    LOG.write_text(head + "## Details" + details.rstrip("\n") + "\n\n" + block, encoding="utf-8")


def status(a):
    text = LOG.read_text(encoding="utf-8")
    text = re.sub(rf"^(\| {re.escape(a.id)} \|[^|]*\|[^|]*\|[^|]*\|)[^|]*\|", rf"\1 {a.status} |", text, flags=re.M)
    text = re.sub(rf"(### {re.escape(a.id)} .*?\n(?:.*\n)*?- \*\*Status:\*\* ).*", rf"\g<1>{a.status}", text, count=1)
    LOG.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("add")
    for x in ("id", "sev", "page", "summary", "status"):
        p.add_argument(x)
    for f in FIELDS:
        p.add_argument("--" + f, default="")
    s = sub.add_parser("status")
    s.add_argument("id")
    s.add_argument("status")
    a = ap.parse_args()
    (add if a.cmd == "add" else status)(a)
