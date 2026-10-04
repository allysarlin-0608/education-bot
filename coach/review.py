"""Review: what she has learned comes back a few days later (spaced
repetition), without any model calls.

Cards come from three places and live on the lesson they came from, in
slot["cards"] (a lesson carried over to a later day keeps them on its
original slot, curriculum.origin), so they are saved, backed up and
restored with the lessons:

- "question": a quiz question she lost points on (the question as it was,
  options and all), added whenever a quiz is marked;
- "word":     a word from a passed lesson's Vocabulary, asked as "which
  meaning?" with other words' meanings as the wrong options;
- "point":    a key point she saved from a lesson (the Key Idea or a Deep
  Dive point), recalled and then checked by her.

Each card sits in a box. A right answer moves it up a box and its next
review further away (INTERVALS days); a wrong one puts it back in the
first box, due tomorrow. At most DAILY_LIMIT cards are offered a day, the
oldest due first; reviews never hold up the day's lessons and never count
for the streak (they change no day's completion)."""
import hashlib
import random
import re
from datetime import date, timedelta

from coach import catalog, core, quiz

INTERVALS = (1, 3, 7, 14, 30, 60)       # days until the next review, by box
DAILY_LIMIT = 20                        # cards offered a day
KINDS = ("question", "word", "point")
KIND_NAMES = {"question": "Missed question", "word": "Vocabulary", "point": "Key point"}
# What she learned before review existed comes back too: each lesson she had
# finished (or taken a quiz on) gives its cards, two lessons' worth a day
# from LEGACY_FROM on, oldest first, so the first days aren't a flood. They
# are worked out from her record (nothing is written) until she answers,
# pauses or deletes one; then that lesson's cards are kept like any others.
LEGACY_FROM = date(2026, 10, 5)
LEGACY_PER_DAY = 2                      # lessons' worth of old cards a day


def _id(*parts) -> str:
    return hashlib.sha1("|".join(parts).casefold().encode()).hexdigest()[:10]


def _card(kind, front, back, today, **extra) -> dict:
    # one lesson's card: the same word in two lessons is two cards, never one id
    return {"id": _id(kind, str(extra.get("topic", "")), str(extra.get("n", "")), front), "kind": kind, "front": front, "back": back, "box": 0,
            "due": (today + timedelta(days=INTERVALS[0])).isoformat(), "added": today.isoformat(),
            "last": None, "reviews": 0, "lapses": 0, "paused": False, **extra}


def _add(slot, card) -> bool:
    cards = slot.setdefault("cards", [])
    if any(c["id"] == card["id"] for c in cards):
        return False
    cards.append(card)
    return True


# ---------------------------------------------------------------- sources
def vocabulary(lesson: str) -> list:
    """(word, meaning, example) rows from a lesson's Vocabulary block."""
    rows = []
    for line in core.extract_section(lesson, "Vocabulary").splitlines():
        cells = [c.strip(" *`") for c in re.split(r"[|｜]", line.strip().strip("|｜"))]
        cells = [c for c in cells if c]
        if len(cells) < 2 or set("".join(cells)) <= set("-: ") or cells[0].lower() in ("word", "單字"):
            continue
        rows.append((cells[0], cells[1], cells[2] if len(cells) > 2 else ""))
    return rows


def key_points(lesson: str) -> list:
    """(label, text) for what she can save: the Key Idea, then each Deep Dive point."""
    points = []
    key = core.extract_section(lesson, "Key Idea")
    if key:
        points.append(("Key idea", key.strip()))
    for line in core.extract_section(lesson, "Deep Dive").splitlines():
        m = re.match(r"^\s*(?:[-*•]|\d+[.)])?\s*\**([^*:：]{2,60})\**\s*[:：]\s*(.+)$", line)
        if m:
            points.append((m.group(1).strip(), m.group(2).strip()))
    return points


def add_missed(slot: dict, q: dict, today: date, topic: str) -> int:
    """A card for each question she lost points on in this marked quiz."""
    added = 0
    for item, mark in zip(q["questions"], q["marks"] or []):
        if mark is not None and mark < 1:
            added += _add(slot, _card("question", item["question"], _answer_text(item), today,
                                      question=item, topic=topic, n=slot["n"]))
    return added


def add_key_idea(slot: dict, today: date, topic: str) -> int:
    """A passed lesson's Key Idea, as a card to recall."""
    points = key_points(slot.get("lesson", ""))
    if not points or points[0][0] != "Key idea" or saved(slot, "Key idea"):
        return 0
    return int(save_point(slot, "Key idea", points[0][1], today, topic))


def add_words(slot: dict, today: date, topic: str) -> int:
    """A card for each word of a passed lesson's Vocabulary."""
    added = 0
    for word, meaning, example in vocabulary(slot.get("lesson", "")):
        added += _add(slot, _card("word", word, meaning, today, example=example, topic=topic, n=slot["n"]))
    return added


def save_point(slot: dict, label: str, text: str, today: date, topic: str) -> bool:
    return _add(slot, _card("point", f"{label} · Lesson {slot['n']}: {slot['title']}", text, today,
                            topic=topic, n=slot["n"]))


def saved(slot: dict, label: str) -> bool:
    return any(c["kind"] == "point" and c["front"].startswith(f"{label} · Lesson {slot['n']}:")
               for c in slot.get("cards") or [])


def _answer_text(item: dict) -> str:
    if item["type"] == "choice":
        return item["options"][item["answer"]]
    if item["type"] == "match":
        return "; ".join(f"{left} → {item['right'][k]}" for left, k in zip(item["left"], item["key"]))
    return item["answer"]


# ---------------------------------------------------------------- the deck
def _studied(slot: dict) -> bool:
    """A lesson with something to review: written, and passed or quizzed."""
    q = slot.get("quiz") or {}
    return bool(slot.get("lesson")) and not slot.get("from") and bool(
        slot.get("completed") or slot.get("passed_on") or q.get("answers") is not None)


def _old_cards(slot: dict, topic: str, added: date, due: date) -> list:
    """The cards a lesson from before review would have made."""
    held = {"n": slot["n"], "title": slot.get("title", ""), "lesson": slot.get("lesson", ""), "cards": []}
    q = slot.get("quiz")
    if q and q.get("answers") is not None and q.get("marks"):
        add_missed(held, q, added, topic)
    if slot.get("completed") or slot.get("passed_on"):
        add_key_idea(held, added, topic)
        add_words(held, added, topic)
    for c in held["cards"]:
        c["due"] = due.isoformat()
    return held["cards"]


def legacy(log: dict) -> list:
    """(entry, slot, card) for lessons studied before review: worked out, not stored."""
    studied = sorted(((e, s) for e in log["entries"] for s in e.get("lessons") or [] if _studied(s)),
                     key=lambda x: (x[0]["date"], x[0]["topic"], x[1]["n"]))
    out = []
    for k, (e, slot) in enumerate(studied):
        if "cards" in slot:              # made (or kept) since review began
            continue
        due = LEGACY_FROM + timedelta(days=k // LEGACY_PER_DAY)
        out += [(e, slot, c) for c in _old_cards(slot, e["topic"], date.fromisoformat(e["date"]), due)]
    return out


def keep(log: dict, slot: dict) -> None:
    """Before changing one of a lesson's worked-out cards: store them all."""
    if "cards" not in slot:
        slot["cards"] = [c for _, s, c in legacy(log) if s is slot]


def cards(log: dict) -> list:
    """Every card: (entry, slot, card), the stored ones and the worked-out old ones."""
    out = []
    for e in log["entries"]:
        for slot in e.get("lessons") or []:
            for c in slot.get("cards") or []:
                out.append((e, slot, c))
    return out + legacy(log)


def reviewed_today(log: dict, today: date) -> int:
    return sum(1 for _, _, c in cards(log) if c.get("last") == today.isoformat())


def due(log: dict, today: date) -> list:
    """Today's cards still to do: due by today, not paused, oldest due first,
    up to what's left of the daily limit."""
    waiting = [x for x in cards(log) if not x[2]["paused"] and x[2]["due"] <= today.isoformat()
               and x[2].get("last") != today.isoformat()]
    waiting.sort(key=lambda x: (x[2]["due"], x[2]["added"], x[2]["id"]))
    return waiting[:max(0, DAILY_LIMIT - reviewed_today(log, today))]


def next_due(log: dict, today: date):
    later = [c["due"] for _, _, c in cards(log) if not c["paused"] and c["due"] > today.isoformat()]
    return date.fromisoformat(min(later)) if later else None


def grade(card: dict, right: bool, today: date) -> None:
    """A right answer: up a box, next review further away. A wrong one: back
    to the first box, due tomorrow."""
    card["box"] = min(card["box"] + 1, len(INTERVALS) - 1) if right else 0
    card["lapses"] += 0 if right else 1
    card["reviews"] += 1
    card["last"] = today.isoformat()
    card["due"] = (today + timedelta(days=INTERVALS[card["box"]])).isoformat()


def word_question(log: dict, card: dict) -> dict:
    """A word card as a multiple-choice question: its meaning among three
    other words' meanings (none if she hasn't three other words yet)."""
    others = sorted({c["back"] for _, _, c in cards(log) if c["kind"] == "word" and c["back"] != card["back"]})
    if len(others) < quiz.OPTIONS - 1:
        return None
    rng = random.Random(card["id"] + str(card["reviews"]))
    options = rng.sample(others, quiz.OPTIONS - 1) + [card["back"]]
    rng.shuffle(options)
    return {"type": "choice", "question": f"What does “{card['front']}” mean?", "options": options,
            "answer": options.index(card["back"]), "why": card.get("example", "")}


def find(log: dict, card_id: str):
    return next((x for x in cards(log) if x[2]["id"] == card_id), None)


def remove(slot: dict, card_id: str) -> None:
    """Delete a card, and note its id: a page holding an older copy of the
    lesson (another tab) then can't bring it back when it saves (ISS-032)."""
    slot["cards"] = [c for c in slot.get("cards") or [] if c["id"] != card_id]
    slot["removed"] = sorted(set(slot.get("removed") or []) | {card_id})


def search(log: dict, query: str, kind: str = None) -> list:
    words = [w for w in query.lower().split() if w]
    out = []
    for x in cards(log):
        c = x[2]
        if kind and c["kind"] != kind:
            continue
        text = f"{c['front']} {c['back']} {catalog.name(c.get('topic'), '')}".lower()
        if all(w in text for w in words):
            out.append(x)
    return sorted(out, key=lambda x: (x[2]["paused"], x[2]["due"]))


# ---------------------------------------------------------------- saved form
def parse_cards(data) -> list:
    """Validate saved cards (from the database or a backup)."""
    out = []
    for c in data if isinstance(data, list) else []:
        if not isinstance(c, dict) or c.get("kind") not in KINDS:
            continue
        front, back = c.get("front"), c.get("back")
        if not isinstance(front, str) or not isinstance(back, str) or not front.strip():
            continue
        if not _iso(c.get("due")) or not _iso(c.get("added")):
            continue
        box = c.get("box")
        card = {"id": str(c.get("id") or _id(c["kind"], front)), "kind": c["kind"], "front": front, "back": back,
                "box": box if isinstance(box, int) and not isinstance(box, bool) and 0 <= box < len(INTERVALS) else 0,
                "due": c["due"], "added": c["added"], "last": c["last"] if _iso(c.get("last")) else None,
                "reviews": _count(c.get("reviews")), "lapses": _count(c.get("lapses")),
                "paused": c.get("paused") is True}
        for field in ("topic", "example"):
            if isinstance(c.get(field), str):
                card[field] = c[field]
        if isinstance(c.get("n"), int):
            card["n"] = c["n"]
        if c["kind"] == "question":
            q = quiz._saved_question(c.get("question"))
            if q is None:
                continue
            card["question"] = q
        out.append(card)
    return out


def _iso(value) -> bool:
    try:
        return isinstance(value, str) and bool(date.fromisoformat(value))
    except ValueError:
        return False


def _count(value) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0

