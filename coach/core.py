"""Pure logic for the daily learning coach: weekly schedule, per-topic
difficulty, streaks, the learning log, and the history context handed to
the model. Nothing in here imports Streamlit, so it can be unit tested."""
import json
import os
import re
from datetime import date, timedelta
from pathlib import Path

from coach import books, curriculum

# What is sent to the model: a shared core plus the one topic module for
# the day (see coach/prompts/). system_prompt.md is the full original
# spec, kept as the reference those modules were made from; it is too
# large to send (Groq's 8000 TPM limit) and is not read at runtime.
PROMPTS_DIR = Path(__file__).with_name("prompts")
DEFAULT_LOG_PATH = Path(
    os.environ.get(
        "COACH_LOG_PATH",
        Path(__file__).resolve().parent.parent / "data" / "learning_log.json",
    )
)

# Topic keys map to the seven areas in part 4 of the system prompt.
TOPICS = {
    "fashion": "Fashion & Clothing",
    "jewelry": "Jewelry & Craft",
    "philosophy": "Philosophy",
    "reading": "Reading",
    "cosmos": "Astronomy",
    "business": "Business Planning",
    "investing": "Stocks, Investing & Crypto",
    "free": "General Knowledge",
}

# date.weekday(): Monday == 0. One topic per day, fixed. 看書 isn't a
# weekday topic: it is a daily task on its own page.
WEEKDAY_TOPIC = {
    0: "fashion",
    1: "philosophy",
    2: "business",
    3: "cosmos",
    4: "jewelry",
    5: "investing",
    6: "free",
}
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

LEVELS = ("Beginner", "Intermediate", "Advanced")
# Older entries stored the level in Chinese.
LEGACY_LEVELS = {"入門": "Beginner", "中階": "Intermediate", "進階": "Advanced"}
CLOSING_LINE = "Tick it off when you're done — consistency beats perfection."
# Block names: English lessons, and the Chinese titles older lessons used.
SECTION_ALIASES = {
    "Topic": ("Topic", "今日主題"),
    "Key Idea": ("Key Idea", "核心概念"),
    "Question to Explore": ("Question to Explore", "延伸提問"),
    "Vocabulary": ("Vocabulary", "單字"),
}
for _name, _aliases in list(SECTION_ALIASES.items()):
    for _alias in _aliases:
        SECTION_ALIASES.setdefault(_alias, _aliases)


def load_system_prompt(topic: str) -> str:
    """Shared core + that topic's section of the knowledge map."""
    core_text = (PROMPTS_DIR / "core.md").read_text(encoding="utf-8")
    topic_text = (PROMPTS_DIR / "topics" / f"{topic}.md").read_text(encoding="utf-8")
    return f"{core_text}\n今天的主題範圍：\n{topic_text}"


def scheduled_topic(day: date) -> str:
    return WEEKDAY_TOPIC[day.weekday()]


def weekday_name(day: date) -> str:
    return WEEKDAYS[day.weekday()]


def level_for_session(session_number: int) -> str:
    """Part 6: sessions 1–3 are Beginner, 4–7 Intermediate, 8 and later Advanced."""
    if session_number <= 3:
        return "Beginner"
    if session_number <= 7:
        return "Intermediate"
    return "Advanced"


# ------------------------------------------------------------
# Learning log
# ------------------------------------------------------------
# One entry per (date, topic), following part 12 of the prompt:
#   date, topic, level, session_number, completed, title,
#   followup_question, reflection, lesson

def empty_log() -> dict:
    return {"version": 1, "entries": [], "books": []}


def load_log(path: Path = DEFAULT_LOG_PATH) -> dict:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return empty_log()
    return parse_log(data)


ENTRY_FIELDS = (
    "date", "topic", "session_number", "level", "completed",
    "title", "followup_question", "reflection", "lesson", "followups", "kickoff",
    "lessons",
)
TEXT_FIELDS = ("title", "followup_question", "reflection", "lesson", "kickoff")


def parse_log(data) -> dict:
    """Validate a log loaded from disk, the database, or a user upload, and
    fill in any missing fields so every entry has the full shape."""
    if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
        raise ValueError("this isn't a learning-record backup")
    entries = {}
    for e in data["entries"]:
        if not isinstance(e, dict) or e.get("topic") not in TOPICS:
            continue
        try:
            day = date.fromisoformat(str(e.get("date")))
        except ValueError:
            continue
        entry = {
            "date": day.isoformat(),
            "topic": e["topic"],
            "session_number": e.get("session_number") or 0,
            "level": LEGACY_LEVELS.get(e.get("level"), e.get("level") if e.get("level") in LEVELS else ""),
            "completed": bool(e.get("completed")),
        }
        for field in TEXT_FIELDS:
            entry[field] = e.get(field) or ""
        entry["followups"] = parse_followups(e.get("followups"))
        entry["lessons"] = curriculum.parse_slots(e.get("lessons"))
        # One entry per (date, topic); a later duplicate wins.
        entries[(entry["date"], entry["topic"])] = entry
    ordered = sorted(entries.values(), key=lambda e: (e["date"], e["topic"]))
    counts = {}
    for entry in ordered:
        counts[entry["topic"]] = counts.get(entry["topic"], 0) + 1
        if not entry["session_number"]:
            entry["session_number"] = counts[entry["topic"]]
        if not entry["level"]:
            entry["level"] = level_for_session(entry["session_number"])
    book_list = [b for b in map(books.normalize_book, data.get("books") or []) if b]
    return {
        "version": 1,
        "entries": [{k: e[k] for k in ENTRY_FIELDS} for e in ordered],
        "books": book_list,
    }


def parse_followups(data) -> list:
    """The chat after a lesson: [{"role": "user"|"assistant", "content": str}]."""
    if not isinstance(data, list):
        return []
    return [
        {"role": m["role"], "content": m["content"]}
        for m in data
        if isinstance(m, dict) and m.get("role") in ("user", "assistant")
        and isinstance(m.get("content"), str)
    ]


def save_log(log: dict, path: Path = DEFAULT_LOG_PATH) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def find_entry(log: dict, day: date, topic: str):
    for entry in log["entries"]:
        if entry["date"] == day.isoformat() and entry["topic"] == topic:
            return entry
    return None


def topic_session_number(log: dict, topic: str, day: date) -> int:
    """How many times she has met this topic, counting today. Counted per
    topic (not global days), as part 12 asks."""
    prior = {
        e["date"] for e in log["entries"]
        if e["topic"] == topic and e["date"] < day.isoformat()
    }
    return len(prior) + 1


def start_entry(log: dict, day: date, topic: str) -> dict:
    """Return today's entry for this topic, creating it if needed."""
    entry = find_entry(log, day, topic)
    if entry is not None:
        return entry
    session_number = topic_session_number(log, topic, day)
    entry = {
        "date": day.isoformat(),
        "topic": topic,
        "session_number": session_number,
        "level": level_for_session(session_number),
        "completed": False,
        "title": "",
        "followup_question": "",
        "reflection": "",
        "lesson": "",
        "followups": [],
        "kickoff": "",
        "lessons": [],
    }
    log["entries"].append(entry)
    log["entries"].sort(key=lambda e: e["date"])
    return entry


def completed_dates(log: dict) -> set:
    return {date.fromisoformat(e["date"]) for e in log["entries"] if e.get("completed")}


def current_streak(log: dict, today: date) -> int:
    """Consecutive completed days ending today. If today isn't done yet the
    streak still counts through yesterday, so it never reads as broken
    before she's had a chance to finish today."""
    done = completed_dates(log)
    day = today if today in done else today - timedelta(days=1)
    streak = 0
    while day in done:
        streak += 1
        day -= timedelta(days=1)
    return streak


def days_since_last_visit(log: dict, today: date):
    """Days since the most recent entry before today, or None if none."""
    earlier = [date.fromisoformat(e["date"]) for e in log["entries"]
               if e["date"] < today.isoformat()]
    if not earlier:
        return None
    return (today - max(earlier)).days


# ------------------------------------------------------------
# Checks applied to every reply before it is shown and saved
# ------------------------------------------------------------
# The prompt asks for these too, but a prompt can't guarantee them, so the
# app enforces them on the text the model returns.

INVESTING_WORDS = re.compile(
    r"股票|股價|個股|選股|股市|基金(?!會)|ETF|加密貨幣|虛擬貨幣|比特幣|以太幣|幣價|選幣|"
    r"殖利率|本益比|報酬率|投資組合|投資建議|進場|出場|"
    # Lessons are mostly in English now.
    r"\bstocks?\b|\bstock (?:market|price)s?\b|\bmutual funds?\b|\bindex funds?\b|\bcrypto|"
    r"\bbitcoin\b|\bethereum\b|\bdividends?\b|\bP/E\b|price-to-earnings|investment portfolio|"
    r"\binvestment advice\b",
    re.IGNORECASE,
)
DISCLAIMER = (
    "※ For education only — this is not investment advice. Do your own research and weigh "
    "the risks carefully before making any real decision."
)


def has_disclaimer(text: str) -> bool:
    lowered = text.lower()
    return ("不構成" in text and "投資建議" in text) or "not investment advice" in lowered \
        or "not financial advice" in lowered


def finalize_reply(text: str, lesson: bool) -> str:
    """Add the investing disclaimer when the reply touches investing and
    lacks one, and (for a lesson) make the fixed closing line the very
    last line, with the disclaimer right before it."""
    text = text.strip()
    needs_disclaimer = bool(INVESTING_WORDS.search(text)) and not has_disclaimer(text)
    closing_ok = not lesson or (text.endswith(CLOSING_LINE) and text.count(CLOSING_LINE) == 1)
    if closing_ok and not needs_disclaimer:
        return text                     # already right: leave it exactly as written
    if lesson:
        text = text.replace(CLOSING_LINE, "").rstrip()
    if INVESTING_WORDS.search(text) and not has_disclaimer(text):
        text = f"{text}\n\n{DISCLAIMER}"
    if lesson:
        text = f"{text}\n\n{CLOSING_LINE}"
    return text


# ------------------------------------------------------------
# Parsing the coach's lesson blocks
# ------------------------------------------------------------

def extract_section(text: str, name: str) -> str:
    """Pull one 【...】 block's body out of a lesson, tolerating markdown
    bold/heading markers around the block titles. A title only has to
    contain one of the block's names, so English lessons (【Question to
    Explore】) and older Chinese ones (【延伸提問】) both parse."""
    clean = re.sub(r"[*#]+", "", text)
    for alias in SECTION_ALIASES.get(name, (name,)):
        pattern = (rf"【[^】\n]*{re.escape(alias)}[^】\n]*】\s*[:：]?\s*(.+?)"
                   rf"(?=\n\s*【|{re.escape(CLOSING_LINE[:6])}|完成後記得打勾|\Z)")
        match = re.search(pattern, clean, flags=re.DOTALL)
        if match:
            return match.group(1).strip()
    return ""


# ------------------------------------------------------------
# Context sent to the model
# ------------------------------------------------------------

def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + "…"


def _syllabus_lines(topic: str, slot: dict) -> list:
    """Where this lesson sits in the fixed syllabus, so the model teaches
    exactly this title at this level and doesn't run ahead."""
    n = slot["n"]
    lines = [
        f"- 今天要上的課（依固定課綱，照這個標題講，不要換題目）：第 {n} 課「{slot['title']}」",
        f"- 所屬單元：{slot['unit'] or '（無）'}；難度（依課綱位置）：{curriculum.level_for(n)}",
    ]
    before, after = curriculum.lesson(topic, n - 1), curriculum.lesson(topic, n + 1)
    if before:
        lines.append(f"- 上一課是「{before['title']}」，可以自然銜接，但不要重講。")
    if after:
        lines.append(f"- 下一課是「{after['title']}」，這一課不要提前講它的內容。")
    return lines


def build_history_context(log: dict, topic: str, today: date, slot: dict = None) -> str:
    """Summarize her track record for the model, so it can apply part 6
    (no repeats, the right difficulty, a specific 小提醒). With a syllabus
    lesson (slot), the title and level come from the syllabus."""
    lines = [
        "【App 自動提供的學習紀錄】",
        f"- 今天：{today.isoformat()}（{weekday_name(today)}）",
        f"- 今天的主題：{TOPICS[topic]}",
    ]
    if slot is not None:
        lines += _syllabus_lines(topic, slot)
    else:
        session_number = topic_session_number(log, topic, today)
        lines.append(f"- 這是她第 {session_number} 次接觸這個主題，依難度規則，難度為：{level_for_session(session_number)}")
    lines += [
        f"- 目前連續完成天數：{current_streak(log, today)} 天",
        f"- 累計完成天數：{len(completed_dates(log))} 天",
    ]

    gap = days_since_last_visit(log, today)
    if gap is None:
        lines.append("- 這是她第一次使用，沒有更早的紀錄。")
    elif gap > 1:
        lines.append(
            f"- 距離上次互動已經 {gap} 天。請依特殊情境二處理："
            "不要提到中斷，直接自然地「從這裡繼續」。"
        )

    past = [e for e in log["entries"]
            if e["topic"] == topic and e["date"] < today.isoformat()]
    if past:
        lines.append("- 這個主題學過的內容（避免重複）：")
        for e in past[-5:]:
            status = "已完成" if e.get("completed") else "未打勾"
            lines.append(f"  - {e['date']}：{_clip(e.get('title') or '（無標題）', 50)}（{status}）")
        # Clipped so the whole request stays inside tokens.REQUEST_BUDGET.
        last = past[-1]
        if last.get("followup_question"):
            lines.append(f"- 上次留給她的延伸提問：{_clip(last['followup_question'], 120)}")
        if last.get("reflection"):
            lines.append(f"- 她對上次延伸提問的回應：{_clip(last['reflection'], 150)}")

    lines.append("- App 已自動記錄學習軌跡，不用再問她要不要記錄。")
    return "\n".join(lines)


# Appended only after today's lesson has been given, so follow-up chat
# reads like a conversation instead of a fresh six-block lesson each time.
FOLLOWUP_NOTE = """【App 補充：今天的課程已經給過了】
她現在是在今天的課程之後追問、回報進度或聊天。這時候七個區塊的課程格式不適用，也不需要加結尾固定句式：
- 直接用自然的對話回答，通常幾句話到一小段就好，只回應她這次說的內容。
- 跟課程一樣只用英文，不要出現中文；她用中文問也用英文回答，看起來卡住時換更簡單的英文說明。
- 其他規則照舊：語氣、特殊情境、投資內容結尾的免責聲明。
- 她回報完成任務（包括只做了一部分）時，具體肯定「完成」這件事本身，並提醒她可以在頁面上打勾。
- 只有在她明確要求一則新的課程內容時，才重新使用完整的七個區塊與結尾固定句式。"""


def build_system_prompt(log: dict, topic: str, today: date, followup: bool = False,
                        slot: dict = None) -> str:
    prompt = f"{load_system_prompt(topic)}\n\n{build_history_context(log, topic, today, slot)}"
    if followup:
        prompt += f"\n\n{FOLLOWUP_NOTE}"
    return prompt


def build_kickoff_message(topic: str, today: date, focus: str = "", slot: dict = None) -> str:
    message = f"Today is {weekday_name(today)}, {today.isoformat()}. Subject: {TOPICS[topic]}."
    if slot is not None:
        message += f" Lesson {slot['n']}: {slot['title']}"
    if focus.strip():
        message += f" I'd especially like to learn about: {focus.strip()}"
    return message


# ------------------------------------------------------------
# Learning-record page summaries
# ------------------------------------------------------------

# Session number at which each level starts (see level_for_session).
LEVEL_STARTS = {"Beginner": 1, "Intermediate": 4, "Advanced": 8}


def longest_streak(log: dict) -> int:
    done = sorted(completed_dates(log))
    best = run = 0
    prev = None
    for day in done:
        run = run + 1 if prev and day - prev == timedelta(days=1) else 1
        best = max(best, run)
        prev = day
    return best


def topic_progress(log: dict, topic: str) -> dict:
    """Sessions so far on a topic, its current level, and how many more
    sessions until the next level (None once Advanced)."""
    sessions = len({e["date"] for e in log["entries"] if e["topic"] == topic})
    completed = len({e["date"] for e in log["entries"]
                     if e["topic"] == topic and e.get("completed")})
    level = level_for_session(sessions) if sessions else None
    next_level = {"Beginner": "Intermediate", "Intermediate": "Advanced"}.get(level or "Beginner")
    if next_level is None:
        remaining, fraction = None, 1.0
    else:
        start = LEVEL_STARTS[level] - 1 if level else 0
        target = LEVEL_STARTS[next_level] - 1
        remaining = target - sessions
        fraction = (sessions - start) / (target - start)
    return {
        "sessions": sessions,
        "completed": completed,
        "level": level,
        "next_level": next_level,
        "remaining": remaining,
        "fraction": fraction,
    }


def calendar_weeks(log: dict, today: date, weeks: int = 4) -> list:
    """Monday-first weeks ending with the current one. Each day is
    (date, status), status one of "done", "started", "none", "future"."""
    done = completed_dates(log)
    started = {date.fromisoformat(e["date"]) for e in log["entries"]}
    monday = today - timedelta(days=today.weekday()) - timedelta(weeks=weeks - 1)
    rows = []
    for w in range(weeks):
        row = []
        for d in range(7):
            day = monday + timedelta(weeks=w, days=d)
            if day > today:
                status = "future"
            elif day in done:
                status = "done"
            elif day in started:
                status = "started"
            else:
                status = "none"
            row.append((day, status))
        rows.append(row)
    return rows
