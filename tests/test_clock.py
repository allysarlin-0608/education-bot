"""One clock (coach/clock.py): every "today" and "now" comes from it, so
moving it moves the whole app (the browser tests' clock does exactly that)."""
import re
from datetime import date
from pathlib import Path

from coach import books, clock, core, paths, settings, storage, ui

ROOT = Path(__file__).resolve().parents[1]
DAY = date(2031, 2, 3)


def test_moving_the_clock_moves_every_date_and_stamp(monkeypatch):
    monkeypatch.setattr(clock, "today", lambda: DAY)
    monkeypatch.setattr(clock, "now_iso", lambda: "2031-02-03T01:00:00+00:00")
    assert ui.today() == DAY
    book = core.parse_log({"entries": [], "books": [{"id": "b1", "status": "reading", "chapters": ["a", "b"],
                                                      "started_on": "soon"}]})["books"][0]
    assert book["started_on"] == DAY.isoformat(), "a book's missing date is the learner's today"
    assert settings.now_iso() == paths.now_iso() == storage._now() == "2031-02-03T01:00:00+00:00"


def test_no_module_reads_the_system_clock_but_the_clock():
    """A second clock is how dates drift apart (the learner's today vs the
    server's): only coach/clock.py may ask the system for the date."""
    allowed = {"clock.py"}
    offenders = []
    for f in sorted((ROOT / "coach").glob("*.py")) + sorted((ROOT / "views").glob("*.py")):
        if f.name in allowed:
            continue
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"\b(datetime\.now|date\.today)\(", line):
                offenders.append(f"{f.relative_to(ROOT)}:{n}")
    assert not offenders, offenders
