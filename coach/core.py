"""Pure logic for the daily learning coach: weekly schedule, per-topic
difficulty, streaks, the learning log, and the history context handed to
the model. Nothing in here imports Streamlit, so it can be unit tested."""
import json
import os
import re
import tempfile
from datetime import date, timedelta
from pathlib import Path

from coach import books, catalog, curriculum, streaks

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
CLOSING_LINE = "Take the quiz when you're ready — consistency beats perfection."
# Closing lines of lessons saved before the quiz (and before English), so
# older lessons still parse.
OLD_CLOSING_LINES = ("Tick it off when you're done", "完成後記得打勾")
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


# The learner the coach is talking to. The personal app is one person's
# (learner.md); on the public site it is anyone, so the profile is generic and
# her own goal and reasons (below) do the personalizing.
# (and the lines elsewhere that speak of her: what each says on the public site)
PUBLIC_EDITS = {"語言：她準備出國留學，整個App都是英文。": "語言：整個App都是英文。",
                "雖然17歲不太可能立刻用到，但": ""}


def load_system_prompt(topic: str, public: bool = False) -> str:
    """Who she is + the shared core + that topic's section of the knowledge
    map (for one of her goals: her goal and its path, coach/paths.py)."""
    learner = (PROMPTS_DIR / ("learner_public.md" if public else "learner.md")).read_text(encoding="utf-8")
    core_text = (PROMPTS_DIR / "core.md").read_text(encoding="utf-8")
    if catalog.is_goal(topic):
        topic_text = goal_section(catalog.path(topic))
    else:
        topic_text = (PROMPTS_DIR / "topics" / f"{topic}.md").read_text(encoding="utf-8")
    prompt = f"{learner}\n{core_text}\n今天的主題範圍：\n{topic_text}"
    if public:
        for personal, general in PUBLIC_EDITS.items():
            prompt = prompt.replace(personal, general)
    return prompt


def goal_section(path) -> str:
    """The topic section for one of her goals: what she wants and why, the
    path, and the rules for a subject with no written knowledge map."""
    if not path:
        return "（她的目標已經不在了：照課程標題講。）"
    units = " → ".join(u["name"] for u in path["units"])
    lines = ["【她自己的學習目標】",
             f"- 目標（她的話）：{path.get('goal') or path['title']}"]
    if path.get("why"):
        lines.append(f"- 為什麼對她重要（她的話）：{path['why']}")
    lines += [f"- 這條學習路徑：「{path['title']}」；學完她能：{path['outcome']}",
              f"- 路徑的單元順序：{units}",
              "這個目標沒有預先寫好的知識地圖，所以：",
              "- 只教有共識、能查證的知識。不確定的數字、年份、人名、定義、規定就不要寫；各地不同的規定要說明「依地區而異」。",
              "- 重要的事實（數字、定義、規則、研究結論、歷史事件）在句子後面用括號註明一般能查到的出處，例如 (Source: WHO)、"
              "(Source: IFRS)、(Source: NASA)。只寫你確定存在的機構、標準或經典著作；絕不編造網址、書名、論文或引言。",
              "- 例子和今天的任務盡量連到她寫的原因，讓她看得出這是為她的目標設計的。",
              "- 健康、法律、財務的決定：只教觀念，不給個人建議；需要時提醒她請教專業人士。"]
    return "\n".join(lines)


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
    return {"version": 1, "entries": [], "books": [], "paths": []}


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
        if not isinstance(e, dict) or not catalog.valid(e.get("topic")):
            continue
        try:
            day = date.fromisoformat(str(e.get("date")))
        except ValueError:
            continue
        number = e.get("session_number")
        level = e.get("level") if isinstance(e.get("level"), str) else ""
        entry = {
            "date": day.isoformat(),
            "topic": e["topic"],
            # every field its own type: a backup can hold anything
            "session_number": number if isinstance(number, int) and not isinstance(number, bool)
            and 0 < number < 100000 else 0,
            "level": LEGACY_LEVELS.get(level, level if level in LEVELS else ""),
            "completed": e.get("completed") is True,
        }
        for field in TEXT_FIELDS:
            entry[field] = e.get(field) if isinstance(e.get(field), str) else ""
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
    from coach import paths as goal_paths            # (her own goals: coach/paths.py)
    path_list = list({p["id"]: p for p in map(goal_paths.parse_path, data.get("paths") or []) if p}.values())
    return {
        "version": 1,
        "entries": [{k: e[k] for k in ENTRY_FIELDS} for e in ordered],
        "books": book_list,
        "paths": path_list,
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
    write_json(path, log)


def write_json(path, data) -> None:
    """Write a JSON file whole: a temporary file of its own (two saves never
    share one), then swapped in, so a reader never sees half a file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False, indent=2))
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


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
    """Days completed: every entry that day completed (its lessons, and a
    reading check-in if there was one). The one definition Progress's
    figure, its calendar and its month line all use (ISS-012)."""
    by_day = {}
    for e in log["entries"]:
        by_day.setdefault(e["date"], []).append(bool(e.get("completed")))
    return {date.fromisoformat(d) for d, done in by_day.items() if all(done)}


def lessons_in(entry: dict) -> tuple:
    """(passed, planned) lessons in one entry. A reading check-in is a day's
    reading, not a lesson; a session from before the syllabus is one."""
    if entry["topic"] == "reading":
        return 0, 0
    if entry.get("lessons"):
        return sum(1 for s in entry["lessons"] if s.get("completed")), len(entry["lessons"])
    return (1 if entry.get("completed") else 0), 1


def lessons_passed(log: dict) -> int:
    return sum(lessons_in(e)[0] for e in log["entries"])


def streak_dates(log: dict) -> set:
    """Days that count for a streak: at least one lesson passed that day
    (a whole day finished, for sessions from before the syllabus)."""
    return {date.fromisoformat(e["date"]) for e in log["entries"]
            if e.get("completed") or any(s.get("completed") for s in e.get("lessons") or [])}


def current_streak(log: dict, today: date) -> int:
    """Study days in the streak going now. Rest days (coach/streaks.py)
    carry it over a missed day; today counts against her only once it's over."""
    return streaks.walk(streak_dates(log), today)["current"]


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


DISCLAIMER_LINE = re.compile(
    r"^.*(?:not (?:investment|financial) advice|不構成.*投資建議).*$\n?", re.IGNORECASE | re.MULTILINE)


def finalize_reply(text: str, lesson: bool, topic: str = None) -> str:
    """Put the investing disclaimer where it belongs and (for a lesson) make
    the fixed closing line the very last line, the disclaimer right before
    it. The disclaimer is only for the investing subject (when the reply
    touches investing); on every other subject it never appears, and one
    the model added anyway is taken out."""
    text = text.strip()
    investing = topic == "investing"
    if not investing and has_disclaimer(text):
        text = re.sub(r"\n{3,}", "\n\n", DISCLAIMER_LINE.sub("", text)).strip()
    needs_disclaimer = investing and bool(INVESTING_WORDS.search(text)) and not has_disclaimer(text)
    closing_ok = not lesson or (text.endswith(CLOSING_LINE) and text.count(CLOSING_LINE) == 1)
    if closing_ok and not needs_disclaimer:
        return text                     # already right: leave it exactly as written
    if lesson:
        text = text.replace(CLOSING_LINE, "").rstrip()
    if needs_disclaimer:
        text = f"{text}\n\n{DISCLAIMER}"
    if lesson:
        text = f"{text}\n\n{CLOSING_LINE}"
    return text


# The Note may only mention what really happened. The prompt says so, but a
# model can still write "You've already gathered…" about today's task; such
# a sentence is replaced with one built from her record (note_fact).
NOTE_BLOCK = re.compile(r"(【[^】\n]*(?:Note|叮嚀|提醒)[^】\n]*】\**\s*[:：]?\s*)(.+?)(?=\n\s*\**【|\n\s*Take the quiz|\Z)",
                        re.DOTALL)
CLAIM = re.compile(r"\byou(?:'ve|’ve| have| had| already| did| were)\b|\byou(?: just)? (?:noticed|gathered|collected|wrote|"
                   r"tried|completed|finished|looked|compared|watched|explored|made|took|spent|found|picked|chose|"
                   r"listed|observed|checked|sorted|noted|started)\b", re.IGNORECASE)


def note_fact(log: dict, topic: str, today: date, n: int) -> str:
    """A true sentence for the Note: from her record, nothing she hasn't done."""
    from coach import curriculum
    streak = current_streak(log, today)
    passed = len(curriculum.completed_numbers(log, topic))
    if streak >= 2:
        return f"{streak} days in a row with a lesson passed. Lesson {n} is today's next step."
    if passed:
        return f"Lesson {n} of {catalog.name(topic)}, building on the {passed} you've passed so far."
    return f"Your first lesson in {catalog.name(topic)}. One clear idea is enough for today."


def truthful_note(text: str, fact: str) -> str:
    """The lesson with its Note replaced by `fact` if the Note claims she did
    something (she has only just opened the lesson)."""
    match = NOTE_BLOCK.search(text)
    if not match or not CLAIM.search(match.group(2)):
        return text
    return text[:match.start(2)] + fact + text[match.end(2):]


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
                   rf"(?=\n\s*【|{re.escape(CLOSING_LINE[:6])}|"
                   + "|".join(re.escape(old) for old in OLD_CLOSING_LINES) + r"|\Z)")
        match = re.search(pattern, clean, flags=re.DOTALL)
        if match:
            return match.group(1).strip()
    return ""


# ------------------------------------------------------------
# Context sent to the model
# ------------------------------------------------------------

def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + "…"


def lesson_level(n: int, start_level: str = None) -> str:
    """A lesson's level: its place in the syllabus, or the level her
    settings start the subject at, whichever is higher."""
    level = curriculum.level_for(n)
    if start_level in LEVELS and LEVELS.index(start_level) > LEVELS.index(level):
        return start_level
    return level


def _syllabus_lines(topic: str, slot: dict, start_level: str = None) -> list:
    """Where this lesson sits in the fixed syllabus, so the model teaches
    exactly this title at this level and doesn't run ahead."""
    n = slot["n"]
    level = lesson_level(n, start_level)
    source = "依課綱位置" if level == curriculum.level_for(n) else "她的起始程度（程度測驗）"
    lines = [
        f"- 今天要上的課（依固定課綱，照這個標題講，不要換題目）：第 {n} 課「{slot['title']}」",
        f"- 所屬單元：{slot['unit'] or '（無）'}；難度（{source}）：{level}",
    ]
    if catalog.is_goal(topic) and n == 1:
        lines.append("- 這是她這個目標的第一課：寫短一點（約350到500字），今天的任務5分鐘內就做得完，"
                     "讓她今天就有一個看得見的小成功；【Note】用一句話把這課連到她寫的原因。")
    before, after = curriculum.lesson(topic, n - 1), curriculum.lesson(topic, n + 1)
    if before:
        lines.append(f"- 上一課是「{before['title']}」，可以自然銜接，但不要重講。")
    if after:
        lines.append(f"- 下一課是「{after['title']}」，這一課不要提前講它的內容。")
    return lines


def build_history_context(log: dict, topic: str, today: date, slot: dict = None,
                          start_level: str = None) -> str:
    """Summarize her track record for the model, so it can apply part 6
    (no repeats, the right difficulty, a specific 小提醒). With a syllabus
    lesson (slot), the title and level come from the syllabus."""
    lines = [
        "【App 自動提供的學習紀錄】",
        f"- 今天：{today.isoformat()}（{weekday_name(today)}）",
        f"- 今天的主題：{catalog.name(topic)}",
    ]
    if slot is not None:
        lines += _syllabus_lines(topic, slot, start_level)
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
            lines.append(f"  - {e['date']}：{_clip(e.get('title') or '（無標題）', 30)}（{status}）")
        # Clipped so the whole request stays inside tokens.REQUEST_BUDGET.
        last = past[-1]
        if last.get("followup_question"):
            lines.append(f"- 上次留給她的延伸提問：{_clip(last['followup_question'], 80)}")
        if last.get("reflection"):
            lines.append(f"- 她對上次延伸提問的回應：{_clip(last['reflection'], 100)}")

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
                        slot: dict = None, start_level: str = None, public: bool = False,
                        weak: list = ()) -> str:
    """The coach's instructions: who she is, the subject, her record. A
    lesson is told the earlier ideas she's still shaky on (`weak`,
    coach/practice.weak_titles) to touch on briefly; a question after it
    gets the tutor's rules (coach/practice.TUTOR)."""
    prompt = f"{load_system_prompt(topic, public)}\n\n{build_history_context(log, topic, today, slot, start_level)}"
    if weak and not followup:
        prompt += ("\n- 她還不熟的前面觀念（在今天的課裡自然地帶到一次：一句回顧或一個小問題，"
                   "不要另開段落、不要說她不熟）：" + "；".join(weak))
    if followup:
        from coach import practice
        prompt += f"\n\n{FOLLOWUP_NOTE}\n\n{practice.TUTOR}"
    return prompt


def build_kickoff_message(topic: str, today: date, focus: str = "", slot: dict = None) -> str:
    message = f"Today is {weekday_name(today)}, {today.isoformat()}. Subject: {catalog.name(topic)}."
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


def longest_streak(log: dict, today: date = None) -> int:
    """The longest streak ever, with the same rest days as the current one."""
    done = streak_dates(log)
    return streaks.walk(done, today or max(done, default=date.min))["longest"] if done else 0


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
