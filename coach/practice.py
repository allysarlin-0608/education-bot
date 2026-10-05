"""Practice that adapts, explaining it back, and the tutor's grounding: the
rules and the model's requests for Phase 3. Pure functions; the pages
(views/practice.py, views/daily.py) draw them and ui.py saves.

Practice. A short set (SET_SIZE exercises) on the ideas she knows least
(coach/mastery.weakest): at most PER_IDEA exercises an idea, ideas taken in
turn (A, B, C, A, B, C: interleaved), the kinds she can answer at once
(quiz.LOCAL), easier kinds first for an idea still being learned (choice,
matching) and harder ones for one that is fading or solid (blank, order,
scenario): no jumps, no loops on one idea. Exercises come from what she
already has, at no AI cost (the lesson's own quiz, its practice bank, its
missed questions); only when an idea has none left that she hasn't seen in
this set is the model asked to write some (write + check: two calls, once a
day, MAKE_PER_DAY), and they are kept in the lesson's bank for next time.

Explaining it back. She explains an idea as if teaching a friend; the model
answers as a good teacher (what's right, what's missing, at most one
follow-up question) and scores it right/partly/wrong; the score is evidence
for the skill map. Empty, too short or nonsense explanations are answered
here, with no call. One a day (EXPLAIN_PER_DAY), plus her answer to its
follow-up question.

The tutor. A question asked under a lesson is answered from the lesson,
her goal and her record (core.build_system_prompt), and the reply ends with
two lines the page takes off and shows its own way: which part of the
lesson it is based on, and whether the question showed confusion."""
import hashlib
import random
import re
from datetime import date

from coach import core, mastery, quiz

SET_SIZE = 6
PER_IDEA = 2
IDEAS_PER_SET = 3
MAKE_PER_DAY = 1               # sets of new exercises the model writes a day
MAKE_PER_IDEA = 2
EXPLAIN_PER_DAY = 1
MIN_WORDS = 6                  # an explanation shorter than this isn't sent
EASY = ("choice", "match", "scenario", "blank", "order")       # an idea still being learned
HARD = ("blank", "order", "scenario", "match", "choice")        # one that is fading or solid


def qid(q: dict) -> str:
    return hashlib.sha1(q["question"].casefold().encode()).hexdigest()[:10]


# ------------------------------------------------------------- the sources
def sources(slot: dict, topic: str) -> list:
    """Exercises she can do for one lesson, without a call: its practice
    bank, its latest quiz's questions she can answer at once, and the
    questions she missed (review cards). Each once."""
    found, seen = [], set()
    q = slot.get("quiz") or {}
    pool = list(slot.get("bank") or []) + [x for x in q.get("questions") or [] if not x.get("from")] + \
        [c["question"] for c in slot.get("cards") or [] if c.get("kind") == "question" and c.get("question")]
    for item in pool:
        if item["type"] in quiz.LOCAL and qid(item) not in seen:
            seen.add(qid(item))
            found.append(item)
    return found


def build(log: dict, today: date, avoid=(), size: int = SET_SIZE) -> dict:
    """Today's practice set: {"ideas": [(topic, n, title, level)], "items":
    [{"topic", "n", "q"}], "short": [(topic, n, title)] (ideas with no
    exercises left: the model may write some)}. `avoid`: question ids done
    in an earlier set today."""
    weak = mastery.weakest(log, today, limit=IDEAS_PER_SET)
    per = []
    short = []
    for topic, n, idea in weak:
        held = mastery.holder(log, topic, n)
        if held is None:
            continue
        order = HARD if idea["level"] != "learning" or idea["fading"] else EASY
        rng = random.Random(f"{today.isoformat()}|{topic}|{n}")
        mine = [q for q in sources(held[1], topic) if qid(q) not in avoid]
        rng.shuffle(mine)
        mine.sort(key=lambda q: order.index(q["type"]))
        picked = mine[:PER_IDEA]
        if len(picked) < PER_IDEA:
            short.append((topic, n, idea["title"]))
        per.append([{"topic": topic, "n": n, "q": q} for q in picked])
    items = []
    while any(per) and len(items) < size:          # one from each idea in turn
        for group in per:
            if group and len(items) < size:
                items.append(group.pop(0))
    return {"ideas": [(t, n, i["title"], i["level"]) for t, n, i in weak], "items": items, "short": short}


MAKER = f"""You write short practice exercises that help a learner strengthen ideas she finds hard.
For EACH idea you are given, write exactly {MAKE_PER_IDEA} exercises, of two different kinds from:
"choice", "scenario", "blank", "order" (order only if the idea has a real sequence), "match".
Same rules and JSON fields as a quiz:
- "choice": a question, exactly 4 options, one correct ("answer": its index), "notes": for each
  option a few words on the mistake behind it ("" for the right one).
- "scenario": "scenario" (a 2-3 sentence situation), "question", 4 options, "answer", "notes".
- "blank": one sentence with "____" where one key word or short phrase goes; "answer"; "accept":
  close variants that are also right.
- "order": "steps": 3-5 short steps in the correct order (exactly one defensible order).
- "match": "pairs": exactly 4 [term, meaning] pairs.
Every exercise has "idea" (the idea's number as given), "why" (one sentence explaining the answer).
Correctness first: the keyed answer must be factually correct in the real world and the only
defensible one. If you are not completely sure of a fact, don't use it. Exercises test using and
understanding the idea, not memorized wording. Simple, clear English.

Reply with JSON only: {{"questions": [{{"idea": 1, "type": "choice", ...}}, ...]}}"""


def make_request(ideas: list):
    """(system, messages) asking for exercises: ideas = [(number, title, key idea text)]."""
    lines = [f"Idea {k}: {title}\nWhat the lesson says: {key}" for k, title, key in ideas]
    return MAKER, [{"role": "user", "content": "\n\n".join(lines)}]


def key_text(slot: dict, limit: int = 500) -> str:
    """What a lesson says, briefly: its Key Idea (else its start)."""
    text = core.extract_section(slot.get("lesson", ""), "Key Idea") or re.sub(r"[*#【】]", "", slot.get("lesson", ""))
    text = " ".join(text.split())
    return text[:limit]


def made(data, count: int, rng=random) -> dict:
    """The model's exercises by idea number {k: [question]}, usable ones only."""
    items = data.get("questions") if isinstance(data, dict) else None
    out = {}
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict) or not isinstance(item.get("idea"), int) or not 1 <= item["idea"] <= count:
            continue
        parsed = quiz.parse_items({"questions": [item]}, rng)
        if parsed and parsed[0]["type"] in quiz.LOCAL:
            out.setdefault(item["idea"], []).append(parsed[0])
    return out


# ----------------------------------------------------------- explaining
EXPLAINER = """You are a warm, demanding teacher. A learner has just explained an idea in her own
words, as if teaching a friend. Judge it against what the lesson says (given) and real-world facts.
- "right": what she got right, specifically (one sentence). If nothing, say so kindly.
- "missing": the most important thing that is missing or wrong, specifically (one or two sentences;
  "" if nothing important is missing).
- "verdict": "right" (clear and correct, the key point is there), "partly" (on the right track,
  something important missing or a small error) or "wrong" (wrong, off-topic, empty or nonsense).
- "question": at most one short follow-up question that would make her think one step further,
  or "" if none is useful.
Encouraging and specific, never preachy, never long. Simple English. Don't repeat her words back.

Reply with JSON only: {"right": "...", "missing": "...", "verdict": "partly", "question": "..."}"""

FOLLOW = """You are a warm, demanding teacher. You asked a learner a follow-up question about an idea;
here is her answer. In one or two sentences say what is right in it and, if needed, what to add or
correct. "verdict": "right", "partly" or "wrong" as before. Simple English, never preachy.

Reply with JSON only: {"feedback": "...", "verdict": "right"}"""


def precheck(text: str) -> str:
    """A friendly reason not to send it to the coach, or ""."""
    words = re.findall(r"[A-Za-zÀ-ɏ一-鿿]{2,}", text or "")
    if not (text or "").strip():
        return "Write a few sentences first: what the idea is, and why it matters."
    if len(words) < MIN_WORDS:
        return "A little more, please: two or three sentences, as if explaining it to a friend."
    if len(set(w.lower() for w in words)) < 3:
        return "That doesn't read as an explanation yet. Try saying what the idea means, in your own words."
    return ""


def explain_request(slot: dict, title: str, text: str):
    lesson = key_text(slot, 900)
    return EXPLAINER, [{"role": "user", "content":
                        f"The idea: {title}\nWhat the lesson says: {lesson}\n\nHer explanation: {text.strip()[:1500]}"}]


def follow_request(slot: dict, title: str, asked: str, text: str):
    return FOLLOW, [{"role": "user", "content":
                     f"The idea: {title}\nWhat the lesson says: {key_text(slot, 600)}\n\n"
                     f"Your question: {asked}\nHer answer: {text.strip()[:1000]}"}]


def read_explain(data):
    """{"right", "missing", "question", "score"} from the coach's reply, or None."""
    if not isinstance(data, dict):
        return None
    score = quiz.verdict_mark(data)
    if score is None:
        return None
    text = lambda k: str(data.get(k) or "").strip()[:400]        # noqa: E731
    return {"right": text("right"), "missing": text("missing"), "question": text("question"), "score": score}


def read_follow(data):
    if not isinstance(data, dict) or quiz.verdict_mark(data) is None:
        return None
    return {"feedback": str(data.get("feedback") or "").strip()[:400], "score": quiz.verdict_mark(data)}


def parse_explain(data):
    """A saved explanation (database or backup), checked, or None."""
    if not isinstance(data, dict) or not isinstance(data.get("text"), str) or not isinstance(data.get("at"), str):
        return None
    out = {"at": data["at"][:32], "text": data["text"][:1500]}
    fb = data.get("feedback")
    if isinstance(fb, dict) and isinstance(fb.get("score"), (int, float)):
        out["feedback"] = {k: str(fb.get(k) or "")[:400] for k in ("right", "missing", "question")}
        out["feedback"]["score"] = float(fb["score"])
    if isinstance(data.get("reply"), str):
        out["reply"] = data["reply"][:1000]
    rf = data.get("reply_feedback")
    if isinstance(rf, dict) and isinstance(rf.get("score"), (int, float)):
        out["reply_feedback"] = {"feedback": str(rf.get("feedback") or "")[:400], "score": float(rf["score"])}
    return out


def explained_today(log: dict, today: date) -> int:
    """Explanations she has had marked today (any lesson)."""
    return sum(1 for e in log["entries"] for s in e.get("lessons") or []
               if (s.get("explain") or {}).get("at", "")[:10] == today.isoformat() and s["explain"].get("feedback"))


def invite(log: dict, topic: str, slot: dict, today: date) -> bool:
    """Invite her to explain this lesson's idea: it's passed, not explained
    yet, and she hasn't explained one today."""
    return bool((slot.get("completed") or slot.get("passed_on")) and not slot.get("explain")
                and explained_today(log, today) < EXPLAIN_PER_DAY)


# --------------------------------------------------------------- the tutor
TUTOR = """【App 補充：她在問家教問題（Phase 3 規則）】
- 回答要以今天這一課的內容為根據，並連到她的目標和學過的東西；保持在這個科目上。
- 問題和這個科目無關時：用一句話溫和地說明這裡只談這個科目，再提議一個相關的問題。
- 不確定的事就直接說不確定，不要編造事實、數字、引言或出處。
- 回答的最後一定加兩行（App 會拿掉，用自己的方式顯示）：
  Based on: <這一課的哪一段，用段落名稱，例如 Key Idea / Deep Dive / Example；超出這一課就寫 beyond this lesson；不確定時寫 not sure>
  Confused: <yes 或 no：她的問題是否顯示她誤解了這一課的觀念>"""

BASED = re.compile(r"^\s*\**based on\**\s*[:：]\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
CONFUSED = re.compile(r"^\s*\**confused\**\s*[:：]\s*(yes|no)\b.*$", re.IGNORECASE | re.MULTILINE)


def sections(lesson: str) -> list:
    """The lesson's block names (【Key Idea】 → "Key Idea")."""
    return [re.sub(r"[*#]", "", m).strip() for m in re.findall(r"【([^】\n]+)】", lesson or "")]


def split_reply(text: str, lesson: str = "") -> tuple:
    """(the reply without its two closing lines, what it's based on, confused?).
    "based on" is a block of the lesson when it names one, "beyond" when it
    went past the lesson, "unsure" when the coach wasn't sure, else ""."""
    based = BASED.search(text or "")
    confused = CONFUSED.search(text or "")
    body = CONFUSED.sub("", BASED.sub("", text or "")).rstrip()
    where = ""
    if based:
        said = based.group(1).strip().strip(".")
        low = said.lower()
        if "not sure" in low or "unsure" in low:
            where = "unsure"
        elif "beyond" in low:
            where = "beyond"
        else:
            names = sections(lesson)
            hit = next((n for n in names if n.lower() in low or low in n.lower()), None)
            where = hit or said[:40]
    return body, where, bool(confused and confused.group(1).lower() == "yes")


def based_label(where: str) -> str:
    if where == "unsure":
        return "The coach isn't sure about this one: check it in a trusted source."
    if where == "beyond":
        return "Goes beyond this lesson."
    return f"Based on this lesson: {where}" if where else ""


# --------------------------------------------------------------- the quiz
def quiz_context(log: dict, topic: str, slot: dict, today: date, goal: dict = None) -> dict:
    """What a lesson's quiz is told besides the lesson: her goal (for the
    question applying it to her life) and the earlier idea of this subject
    she knows least, if any (one question on it, from an earlier lesson)."""
    out = {}
    if goal:
        out["goal"] = (goal.get("goal") or goal.get("title") or "") + (f" (why: {goal['why']})" if goal.get("why") else "")
    weak = [w for w in mastery.weakest(log, today, limit=1, topic=topic, before=slot["n"])
            if w[2]["level"] == "learning" or w[2]["fading"]]
    if weak:
        t, n, idea = weak[0]
        held = mastery.holder(log, t, n)
        if held and key_text(held[1]):
            out["recall"] = {"n": n, "title": idea["title"], "key": key_text(held[1], 400)}
    return out


def weak_titles(log: dict, topic: str, n: int, today: date, limit: int = 2) -> list:
    """Earlier ideas of this subject still shaky, for the lesson to touch on."""
    return [f"Lesson {m}: {i['title']}" for _, m, i in mastery.weakest(log, today, limit=limit, topic=topic, before=n)
            if i["level"] == "learning" or i["fading"]]
