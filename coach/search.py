"""Search: her lessons, her notes and her books, by words. Pure functions
over the log, so they can be tested. Every word she types has to appear
(in any order, any case); newest first."""
import re

from coach import core

SNIPPET = 90


def _plain(text: str) -> str:
    """Lesson text without its markdown and 【block】 marks, on one line."""
    text = re.sub(r"【[^】]*】", " ", text or "")
    text = re.sub(r"[*_#>`|]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _snippet(text: str, words: list) -> str:
    """A short window of `text` around the first word found."""
    low = text.lower()
    at = min((low.find(w) for w in words if w in low), default=0)
    start = max(0, at - SNIPPET // 3)
    cut = text[start:start + SNIPPET].strip()
    return ("…" if start else "") + cut + ("…" if start + SNIPPET < len(text) else "")


def _hit(words: list, *fields) -> bool:
    haystack = " ".join(f for f in fields if f).lower()
    return all(w in haystack for w in words)


def find(log: dict, query: str, limit: int = 30) -> list:
    """Results for `query`: lessons (title, topic, text), her reflections,
    and books (title, author, chapters, what she wrote each day). Each
    result says where it opens: a day on Progress, or a book on Reading."""
    words = [w for w in query.lower().split() if w]
    if not words:
        return []
    out = []
    for e in log["entries"]:
        subject = core.TOPICS.get(e["topic"], e["topic"])
        for s in e.get("lessons") or []:
            text = _plain(s.get("lesson", ""))
            if _hit(words, s.get("title"), s.get("unit"), subject, text):
                where = s.get("title", "") + " " + s.get("unit", "")
                out.append({"kind": "lesson", "date": e["date"], "title": f"Lesson {s['n']}: {s.get('title', '')}",
                            "meta": subject, "snippet": _snippet(text, words) if not _hit(words, where) else s.get("unit", ""),
                            "open": ("day", e["date"])})
        if not e.get("lessons") and _hit(words, e.get("title"), subject):
            out.append({"kind": "lesson", "date": e["date"], "title": e.get("title") or subject, "meta": subject,
                        "snippet": "", "open": ("day", e["date"])})
        if e.get("reflection") and _hit(words, e["reflection"]):
            out.append({"kind": "note", "date": e["date"], "title": "Your reflection", "meta": subject,
                        "snippet": _snippet(e["reflection"], words), "open": ("day", e["date"])})
    for b in log.get("books", []):
        if b.get("status") not in ("reading", "finished", "switched"):
            continue
        when = b.get("finished_on") or b.get("last_active_on") or b.get("started_on") or ""
        if _hit(words, b.get("title"), b.get("author"), " ".join(b.get("chapters") or [])):
            out.append({"kind": "book", "date": when, "title": b.get("title") or "(untitled)",
                        "meta": b.get("author") or "Book", "snippet": "", "open": ("book", b["id"])})
        for day, check in sorted((b.get("checks") or {}).items(), key=lambda kv: int(kv[0])):
            if check.get("summary") and _hit(words, check["summary"]):
                out.append({"kind": "note", "date": check.get("passed_on", when), "title": f"{b.get('title')}, day {day}",
                            "meta": "Your notes", "snippet": _snippet(check["summary"], words), "open": ("book", b["id"])})
    out.sort(key=lambda r: r["date"], reverse=True)
    return out[:limit]
