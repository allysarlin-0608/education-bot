"""Search: her lessons, her notes, her books, her goals, the lessons still
to come in her courses, and her review cards, by words. Pure functions over
the log, so they can be tested.

Every word she types has to appear (any order, any case). A word in English
(or any language with spaces) matches the start of a word, so "art" finds
"artist" but not "start"; Chinese, Japanese and Korean have no spaces, so
there a word matches anywhere. Results come best first: a word in a title
counts more than one in a unit's name, more than one in the text; then
newest first."""
import re

from coach import catalog

SNIPPET = 90
# how much a word found in each kind of field counts
TITLE, UNIT, META, TEXT = 3.0, 2.0, 1.5, 1.0
# lessons still to come and review cards come after what she has done
COMING, CARD = 0.6, 0.8
MORE_AT_MOST = 8               # of each of those two kinds
_CJK = re.compile(r"[぀-ヿ㐀-鿿가-힯豈-﫿]")


def _plain(text: str) -> str:
    """Lesson text without its markdown and 【block】 marks, on one line."""
    text = re.sub(r"【[^】]*】", " ", text or "")
    text = re.sub(r"[*_#>`|]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _patterns(query: str) -> list:
    out = []
    for w in query.lower().split():
        if _CJK.search(w):
            out.append(re.compile(re.escape(w)))
        else:
            out.append(re.compile(r"(?<![^\W_])" + re.escape(w), re.IGNORECASE))   # at the start of a word
    return out


def _score(patterns: list, *fields) -> float:
    """How well the fields ((text, weight) pairs) answer every word: 0 when a
    word is in none of them; else, for each word, the weight of the best field
    it is in, added up."""
    total = 0.0
    for p in patterns:
        best = max((w for text, w in fields if text and p.search(text)), default=0.0)
        if not best:
            return 0.0
        total += best
    return total


def _snippet(text: str, patterns: list) -> str:
    """A short window of `text` around the first word found."""
    at = min((m.start() for m in (p.search(text) for p in patterns) if m), default=0)
    start = max(0, at - SNIPPET // 3)
    cut = text[start:start + SNIPPET].strip()
    return ("…" if start else "") + cut + ("…" if start + SNIPPET < len(text) else "")


def find(log: dict, query: str, limit: int = 30, topics=(), cards=()) -> list:
    """Results for `query`, best first: lessons (title, unit, subject, text),
    her reflections, books (title, author, chapters, what she wrote each
    day), her goals, the lessons still to come in `topics` (her subjects and
    goals), and `cards` (her review cards, as review.cards gives them). Each
    result says where it opens: a day on Progress, a book on Reading, a
    course map, or Review."""
    patterns = _patterns(query)
    if not patterns:
        return []
    out = []

    def add(score, **result):
        if score:
            out.append(dict(result, score=score))

    written = {}
    for e in log["entries"]:
        subject = catalog.name(e["topic"])
        for s in e.get("lessons") or []:
            written.setdefault(e["topic"], set()).add(s["n"])
            if s.get("from"):           # carried over: found on the day it was written
                continue
            text = _plain(s.get("lesson", ""))
            score = _score(patterns, (s.get("title"), TITLE), (s.get("unit"), UNIT), (subject, META), (text, TEXT))
            in_title = _score(patterns, (s.get("title"), TITLE), (s.get("unit"), UNIT))
            add(score, kind="lesson", date=e["date"], title=f"Lesson {s['n']}: {s.get('title', '')}", meta=subject,
                snippet=s.get("unit", "") if in_title else _snippet(text, patterns), open=("day", e["date"]))
        if not e.get("lessons"):
            add(_score(patterns, (e.get("title"), TITLE), (subject, META)), kind="lesson", date=e["date"],
                title=e.get("title") or subject, meta=subject, snippet="", open=("day", e["date"]))
        if e.get("reflection"):
            add(_score(patterns, (e["reflection"], TEXT)), kind="note", date=e["date"], title="Your reflection",
                meta=subject, snippet=_snippet(e["reflection"], patterns), open=("day", e["date"]))
    for b in log.get("books", []):
        if b.get("status") not in ("reading", "finished", "switched"):
            continue
        when = b.get("finished_on") or b.get("last_active_on") or b.get("started_on") or ""
        add(_score(patterns, (b.get("title"), TITLE), (b.get("author"), META), (" ".join(b.get("chapters") or []), TEXT)),
            kind="book", date=when, title=b.get("title") or "(untitled)", meta=b.get("author") or "Book", snippet="",
            open=("book", b["id"]))
        for day, check in sorted((b.get("checks") or {}).items(), key=lambda kv: int(kv[0])):
            if check.get("summary"):
                add(_score(patterns, (check["summary"], TEXT)), kind="note", date=check.get("passed_on", when),
                    title=f"{b.get('title')}, day {day}", meta="Your notes",
                    snippet=_snippet(check["summary"], patterns), open=("book", b["id"]))
    # her goals: what she asked for, and what it leads to
    for g in catalog.goals(active_only=False):
        add(_score(patterns, (g.get("title"), TITLE), (g.get("goal"), UNIT), (g.get("outcome"), TEXT)),
            kind="goal", date=str(g.get("created_at") or "")[:10], title=g.get("title", ""),
            meta="Your goal" + ("" if g.get("status") == "active" else " · paused"),
            snippet=g.get("outcome", ""), open=("course", g["id"]))
    # the lessons still to come in her courses (by their titles; nothing is written yet)
    coming = []
    for t in topics:
        done = written.get(t, set())
        for n, (unit, title) in enumerate(_syllabus(t), start=1):
            if n in done:
                continue
            score = _score(patterns, (title, TITLE), (unit, UNIT)) * COMING
            if score:
                coming.append(dict(kind="coming", date="", title=f"Lesson {n}: {title}",
                                   meta=f"{catalog.name(t)} · coming up", snippet=unit, open=("course", t), score=score))
    out += sorted(coming, key=lambda r: -r["score"])[:MORE_AT_MOST]
    # her review cards
    found = []
    for e, _, c in cards:
        if c.get("paused") or catalog.removed(e["topic"]):
            continue
        score = _score(patterns, (c.get("front"), TITLE), (c.get("back"), TEXT)) * CARD
        if score:
            found.append(dict(kind="card", date=c.get("added", ""), title=c.get("front", "")[:90],
                              meta=f"Review card · {catalog.name(e['topic'])}", snippet=c.get("back", "")[:90],
                              open=("review", query.strip()), score=score))
    out += sorted(found, key=lambda r: -r["score"])[:MORE_AT_MOST]
    out.sort(key=lambda r: r["date"], reverse=True)          # newest first among equals...
    out.sort(key=lambda r: -r["score"])                      # ...best first (a stable sort keeps that order)
    return out[:limit]


def _syllabus(topic: str) -> tuple:
    """A course's lessons in order: [(unit, title)] (a goal's path, or one of ours)."""
    if catalog.is_goal(topic):
        return catalog.goal_lessons(topic)
    from coach import curriculum
    return tuple(curriculum._load(topic)) if catalog.builtin(topic) else ()
