"""Her learning record in our tables (ADR 0002).

The domain (the shared package `coach`) works on a record shaped like the
current app's: {"entries": [day…], "books": [...], "paths": [...]}, each
day holding its lesson slots (content, chat, quiz, cards, evidence,
practice exercises, explanation). This repository stores that record as
rows and gives it back exactly as `coach.core.parse_log` would have it, so
the domain functions and the current app run unchanged on our database.

A day is written whole, in one transaction (as the current stores do): its
slots and everything under them are replaced. Everything here takes the
user id explicitly: there is no query that isn't scoped to one person."""
from datetime import date

from sqlalchemy import delete, insert, select
from sqlalchemy.engine import Connection

from coach import books as books_
from coach import core, paths as paths_
from gnosis.data import schema as t


# ------------------------------------------------------------------ writing
def save_entry(conn: Connection, user_id: str, entry: dict) -> None:
    """Write one day of one subject (replacing what was stored for it)."""
    entry = _parsed_entry(entry)
    day = date.fromisoformat(entry["date"])
    conn.execute(delete(t.day_lessons).where(t.day_lessons.c.user_id == user_id, t.day_lessons.c.day == day,
                                             t.day_lessons.c.subject == entry["topic"]))
    conn.execute(delete(t.study_days).where(t.study_days.c.user_id == user_id, t.study_days.c.day == day,
                                            t.study_days.c.subject == entry["topic"]))
    conn.execute(insert(t.study_days).values(
        user_id=user_id, day=day, subject=entry["topic"], session_number=entry["session_number"],
        level=entry["level"], completed=entry["completed"], title=entry["title"],
        followup_question=entry["followup_question"], reflection=entry["reflection"],
        legacy_lesson=entry["lesson"], legacy_kickoff=entry["kickoff"], legacy_followups=entry["followups"]))
    for position, slot in enumerate(entry["lessons"]):
        _save_slot(conn, user_id, day, entry["topic"], position, slot)


def _parsed_entry(entry: dict) -> dict:
    """The entry as the domain validates it (a stored day is always a valid one)."""
    parsed = core.parse_log({"entries": [entry]})["entries"]
    if not parsed:
        raise ValueError(f"not a valid day: {entry.get('date')!r} {entry.get('topic')!r}")
    return parsed[0]


def _save_slot(conn, user_id, day, subject, position, s) -> None:
    slot_id = conn.execute(insert(t.day_lessons).values(
        user_id=user_id, day=day, subject=subject, lesson_no=s["n"], position=position, title=s["title"],
        unit=s["unit"], completed=s["completed"],
        from_day=date.fromisoformat(s["from"]) if s.get("from") else None,
        passed_on=date.fromisoformat(s["passed_on"]) if s.get("passed_on") else None,
        tracks_cards="cards" in s, tracks_evidence="ev" in s).returning(t.day_lessons.c.id)).scalar_one()
    if s.get("from"):
        return                                   # a link holds no content of its own
    if s["kickoff"] or s["lesson"]:
        conn.execute(insert(t.lesson_contents).values(slot_id=slot_id, kickoff=s["kickoff"], body=s["lesson"]))
    if s["followups"]:
        conn.execute(insert(t.lesson_messages), [
            {"slot_id": slot_id, "position": k, "role": m["role"], "content": m["content"]}
            for k, m in enumerate(s["followups"])])
    q = s.get("quiz")
    if q:
        submitted = q["answers"] is not None
        conn.execute(insert(t.quizzes).values(slot_id=slot_id, quiz_key=q["id"], submitted=submitted,
                                              score=q["score"], attempts=q["attempts"], best=q["best"],
                                              draft=q["draft"]))
        conn.execute(insert(t.quiz_questions), [
            {"slot_id": slot_id, "position": k, "kind": item["type"], "from_lesson": item.get("from"), "body": item,
             "answer": q["answers"][k] if submitted else None,
             "mark": q["marks"][k] if submitted and q["marks"] is not None else None,
             "feedback": q["feedback"][k] if submitted and q["feedback"] is not None else None}
            for k, item in enumerate(q["questions"])])
    for k, c in enumerate(s.get("cards") or []):
        conn.execute(insert(t.review_cards).values(
            slot_id=slot_id, position=k, card_id=c["id"], kind=c["kind"], front=c["front"], back=c["back"],
            box=c["box"], due=date.fromisoformat(c["due"]), added=date.fromisoformat(c["added"]),
            last=date.fromisoformat(c["last"]) if c["last"] else None, reviews=c["reviews"], lapses=c["lapses"],
            paused=c["paused"], card_topic=c.get("topic"), card_lesson_no=c.get("n"), example=c.get("example"),
            question=c.get("question")))
    if s.get("removed"):
        conn.execute(insert(t.review_card_removals), [{"slot_id": slot_id, "card_id": x} for x in s["removed"]])
    if s.get("ev"):
        conn.execute(insert(t.mastery_evidence), [
            {"slot_id": slot_id, "evidence_id": e["id"], "position": k, "day": date.fromisoformat(e["d"]),
             "kind": e["k"], "score": e["s"]} for k, e in enumerate(s["ev"])])
    if s.get("bank"):
        conn.execute(insert(t.practice_items), [{"slot_id": slot_id, "position": k, "body": b}
                                                for k, b in enumerate(s["bank"])])
    if s.get("explain"):
        ex = s["explain"]
        conn.execute(insert(t.explanations).values(slot_id=slot_id, at=ex["at"], text=ex["text"],
                                                   feedback=ex.get("feedback"), reply=ex.get("reply"),
                                                   reply_feedback=ex.get("reply_feedback")))


def save_book(conn: Connection, user_id: str, book: dict) -> None:
    book = books_.normalize_book(book)
    if book is None:
        raise ValueError("not a valid book")
    conn.execute(delete(t.reading_books).where(t.reading_books.c.user_id == user_id, t.reading_books.c.id == book["id"]))
    conn.execute(insert(t.reading_books).values(user_id=user_id, id=book["id"], data=book))


def save_goal(conn: Connection, user_id: str, path: dict) -> None:
    path = paths_.parse_path(path)
    if path is None:
        raise ValueError("not a valid goal")
    conn.execute(delete(t.goals).where(t.goals.c.user_id == user_id, t.goals.c.id == path["id"]))
    conn.execute(insert(t.goals).values(user_id=user_id, id=path["id"], path=path))


def save_log(conn: Connection, user_id: str, log: dict) -> dict:
    """Her whole record (an import, a backup restored): every day, book and
    goal she has replaces what was stored. Returns what was written, counted."""
    parsed = core.parse_log(log)
    for table in (t.study_days, t.day_lessons, t.reading_books, t.goals):
        conn.execute(delete(table).where(table.c.user_id == user_id))
    for e in parsed["entries"]:
        save_entry(conn, user_id, e)
    for b in parsed["books"]:
        save_book(conn, user_id, b)
    for p in parsed["paths"]:
        save_goal(conn, user_id, p)
    return counts(parsed)


# ------------------------------------------------------------------ reading
def load_entry(conn: Connection, user_id: str, day: str, subject: str):
    rows = _entries(conn, user_id, day=date.fromisoformat(day), subject=subject)
    return rows[0] if rows else None


def load_log(conn: Connection, user_id: str) -> dict:
    """Her whole record, shaped as `coach.core.parse_log` returns it."""
    entries = _entries(conn, user_id)
    book_rows = conn.execute(select(t.reading_books.c.data).where(t.reading_books.c.user_id == user_id)
                             .order_by(t.reading_books.c.updated_at, t.reading_books.c.id)).scalars().all()
    goal_rows = conn.execute(select(t.goals.c.path).where(t.goals.c.user_id == user_id)
                             .order_by(t.goals.c.updated_at, t.goals.c.id)).scalars().all()
    return core.parse_log({"entries": entries, "books": list(book_rows), "paths": list(goal_rows)})


def _entries(conn, user_id, day=None, subject=None) -> list:
    d = t.study_days
    q = select(d).where(d.c.user_id == user_id)
    if day is not None:
        q = q.where(d.c.day == day, d.c.subject == subject)
    days = conn.execute(q.order_by(d.c.day, d.c.subject)).mappings().all()
    if not days:
        return []
    sl = t.day_lessons
    sq = select(sl).where(sl.c.user_id == user_id)
    if day is not None:
        sq = sq.where(sl.c.day == day, sl.c.subject == subject)
    slots = conn.execute(sq.order_by(sl.c.day, sl.c.subject, sl.c.position)).mappings().all()
    ids = [s["id"] for s in slots]
    children = _children(conn, ids)
    by_day = {}
    for s in slots:
        by_day.setdefault((s["day"], s["subject"]), []).append(_slot(s, children))
    return [{"date": r["day"].isoformat(), "topic": r["subject"], "session_number": r["session_number"],
             "level": r["level"], "completed": r["completed"], "title": r["title"],
             "followup_question": r["followup_question"], "reflection": r["reflection"],
             "lesson": r["legacy_lesson"], "kickoff": r["legacy_kickoff"], "followups": r["legacy_followups"],
             "lessons": by_day.get((r["day"], r["subject"]), [])} for r in days]


def _children(conn, ids) -> dict:
    """Everything under the given slots, one query per kind (never one per slot)."""
    out = {name: {} for name in ("content", "messages", "quiz", "questions", "cards", "removed", "ev", "bank",
                                 "explain")}
    if not ids:
        return out

    def rows(table, order):
        return conn.execute(select(table).where(table.c.slot_id.in_(ids)).order_by(*order)).mappings().all()
    for r in rows(t.lesson_contents, [t.lesson_contents.c.slot_id]):
        out["content"][r["slot_id"]] = r
    for r in rows(t.lesson_messages, [t.lesson_messages.c.slot_id, t.lesson_messages.c.position]):
        out["messages"].setdefault(r["slot_id"], []).append({"role": r["role"], "content": r["content"]})
    for r in rows(t.quizzes, [t.quizzes.c.slot_id]):
        out["quiz"][r["slot_id"]] = r
    for r in rows(t.quiz_questions, [t.quiz_questions.c.slot_id, t.quiz_questions.c.position]):
        out["questions"].setdefault(r["slot_id"], []).append(r)
    for r in rows(t.review_cards, [t.review_cards.c.slot_id, t.review_cards.c.position]):
        out["cards"].setdefault(r["slot_id"], []).append(_card(r))
    for r in rows(t.review_card_removals, [t.review_card_removals.c.slot_id, t.review_card_removals.c.card_id]):
        out["removed"].setdefault(r["slot_id"], []).append(r["card_id"])
    for r in rows(t.mastery_evidence, [t.mastery_evidence.c.slot_id, t.mastery_evidence.c.position]):
        out["ev"].setdefault(r["slot_id"], []).append({"id": r["evidence_id"], "d": r["day"].isoformat(),
                                                       "k": r["kind"], "s": r["score"]})
    for r in rows(t.practice_items, [t.practice_items.c.slot_id, t.practice_items.c.position]):
        out["bank"].setdefault(r["slot_id"], []).append(r["body"])
    for r in rows(t.explanations, [t.explanations.c.slot_id]):
        out["explain"][r["slot_id"]] = r
    return out


def _slot(s, ch) -> dict:
    sid = s["id"]
    content = ch["content"].get(sid)
    slot = {"n": s["lesson_no"], "title": s["title"], "unit": s["unit"],
            "kickoff": content["kickoff"] if content else "", "lesson": content["body"] if content else "",
            "followups": ch["messages"].get(sid, []), "completed": s["completed"], "quiz": _quiz(ch, sid)}
    if s["from_day"]:
        slot["from"] = s["from_day"].isoformat()
    if s["passed_on"]:
        slot["passed_on"] = s["passed_on"].isoformat()
    if s["tracks_cards"]:
        slot["cards"] = ch["cards"].get(sid, [])
    if sid in ch["removed"]:
        slot["removed"] = ch["removed"][sid]
    if s["tracks_evidence"]:
        slot["ev"] = ch["ev"].get(sid, [])
    if sid in ch["bank"]:
        slot["bank"] = ch["bank"][sid]
    ex = ch["explain"].get(sid)
    if ex:
        slot["explain"] = {"at": ex["at"], "text": ex["text"]}
        for key in ("feedback", "reply", "reply_feedback"):
            if ex[key] is not None:
                slot["explain"][key] = ex[key]
    return slot


def _quiz(ch, sid):
    q = ch["quiz"].get(sid)
    if q is None:
        return None
    qs = ch["questions"].get(sid, [])
    sub = q["submitted"]
    return {"id": q["quiz_key"], "questions": [r["body"] for r in qs],
            "answers": [r["answer"] for r in qs] if sub else None,
            "marks": [r["mark"] for r in qs] if sub else None,
            "feedback": [r["feedback"] if r["feedback"] is not None else "" for r in qs] if sub else None,
            "score": q["score"], "attempts": q["attempts"], "best": q["best"], "draft": q["draft"]}


def _card(r) -> dict:
    c = {"id": r["card_id"], "kind": r["kind"], "front": r["front"], "back": r["back"], "box": r["box"],
         "due": r["due"].isoformat(), "added": r["added"].isoformat(),
         "last": r["last"].isoformat() if r["last"] else None, "reviews": r["reviews"], "lapses": r["lapses"],
         "paused": r["paused"]}
    for key, col in (("topic", "card_topic"), ("example", "example"), ("n", "card_lesson_no"),
                     ("question", "question")):
        if r[col] is not None:
            c[key] = r[col]
    return c


# ------------------------------------------------------------------ checking
def counts(log: dict) -> dict:
    """What a record holds, counted: an import is checked by these, both ways."""
    slots = [s for e in log["entries"] for s in e["lessons"]]
    return {"days": len(log["entries"]), "slots": len(slots),
            "lessons_passed": core.lessons_passed(log),
            "lessons_written": sum(1 for s in slots if s.get("lesson")),
            "quizzes": sum(1 for s in slots if s.get("quiz")),
            "cards": sum(len(s.get("cards") or []) for s in slots),
            "evidence": sum(len(s.get("ev") or []) for s in slots),
            "messages": sum(len(s.get("followups") or []) for s in slots),
            "books": len(log["books"]), "goals": len(log["paths"])}
