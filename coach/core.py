"""Pure logic for the daily learning coach: weekly schedule, per-topic
difficulty, streaks, the learning log, and the history context handed to
the model. Nothing in here imports Streamlit, so it can be unit tested."""
import json
import os
import re
from datetime import date, timedelta
from pathlib import Path

from coach import books

SYSTEM_PROMPT_PATH = Path(__file__).with_name("system_prompt.md")
DEFAULT_LOG_PATH = Path(
    os.environ.get(
        "COACH_LOG_PATH",
        Path(__file__).resolve().parent.parent / "data" / "learning_log.json",
    )
)

# Topic keys map to the seven areas in part 4 of the system prompt.
TOPICS = {
    "fashion": "時尚、材質與珠寶",
    "philosophy": "哲學",
    "reading": "看書",
    "cosmos": "宇宙學、維度理論與地外文明",
    "business": "商業計劃",
    "investing": "股票、投資與加密貨幣",
    "free": "自由主題",
}

# date.weekday(): Monday == 0. Business and investing have no fixed day;
# they only run when she picks them.
WEEKDAY_TOPIC = {
    0: "fashion",
    1: "philosophy",
    2: "reading",
    3: "cosmos",
    4: "fashion",
    5: "reading",
    6: "free",
}
WEEKDAY_ZH = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]

LEVELS = ("入門", "中階", "進階")
CLOSING_LINE = "完成後記得打勾，連續完成比完美更重要。"
SECTION_NAMES = ("今日主題", "核心概念", "具體例子", "今日任務", "延伸提問", "小提醒")


def load_system_prompt() -> str:
    return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")


def scheduled_topic(day: date) -> str:
    return WEEKDAY_TOPIC[day.weekday()]


def weekday_zh(day: date) -> str:
    return WEEKDAY_ZH[day.weekday()]


def level_for_session(session_number: int) -> str:
    """Part 6: sessions 1–3 are 入門, 4–7 中階, 8 and later 進階."""
    if session_number <= 3:
        return "入門"
    if session_number <= 7:
        return "中階"
    return "進階"


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
    "title", "followup_question", "reflection", "lesson",
)
TEXT_FIELDS = ("title", "followup_question", "reflection", "lesson")


def parse_log(data) -> dict:
    """Validate a log loaded from disk, the database, or a user upload, and
    fill in any missing fields so every entry has the full shape."""
    if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
        raise ValueError("學習紀錄格式不正確")
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
            "level": e.get("level") if e.get("level") in LEVELS else "",
            "completed": bool(e.get("completed")),
        }
        for field in TEXT_FIELDS:
            entry[field] = e.get(field) or ""
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


def weekly_topic_counts(log: dict, today: date) -> dict:
    """Interactions per topic over the 7 days before today (for Sunday's
    free topic, which should favor what she touched least)."""
    start = (today - timedelta(days=7)).isoformat()
    counts = {key: 0 for key in TOPICS}
    for e in log["entries"]:
        if start <= e["date"] < today.isoformat():
            counts[e["topic"]] += 1
    return counts


# ------------------------------------------------------------
# Parsing the coach's six-block answer
# ------------------------------------------------------------

def extract_section(text: str, name: str) -> str:
    """Pull one 【...】 block's body out of a lesson, tolerating markdown
    bold/heading markers around the block titles."""
    clean = re.sub(r"[*#]+", "", text)
    pattern = rf"【{name}】\s*[:：]?\s*(.+?)(?=\n\s*【|{CLOSING_LINE[:6]}|\Z)"
    match = re.search(pattern, clean, flags=re.DOTALL)
    return match.group(1).strip() if match else ""


# ------------------------------------------------------------
# Context sent to the model
# ------------------------------------------------------------

def build_history_context(log: dict, topic: str, today: date) -> str:
    """Summarize her track record for the model, so it can apply part 6
    (no repeats, difficulty by per-topic count, a specific 小提醒)."""
    session_number = topic_session_number(log, topic, today)
    level = level_for_session(session_number)
    lines = [
        "【App 自動提供的學習紀錄】",
        f"- 今天：{today.isoformat()}（{weekday_zh(today)}）",
        f"- 今天的主題：{TOPICS[topic]}",
        f"- 這是她第 {session_number} 次接觸這個主題，依第六部分規則，難度為：{level}",
        f"- 目前連續完成天數：{current_streak(log, today)} 天",
        f"- 累計完成天數：{len(completed_dates(log))} 天",
    ]

    gap = days_since_last_visit(log, today)
    if gap is None:
        lines.append("- 這是她第一次使用，沒有更早的紀錄。")
    elif gap > 1:
        lines.append(
            f"- 距離上次互動已經 {gap} 天。請依第九部分情境二處理："
            "不要提到中斷，直接自然地「從這裡繼續」。"
        )

    past = [e for e in log["entries"]
            if e["topic"] == topic and e["date"] < today.isoformat()]
    if past:
        lines.append("- 這個主題過去學過的內容（避免重複，除非是刻意複習深化）：")
        for e in past[-10:]:
            status = "已完成" if e.get("completed") else "未打勾"
            lines.append(f"  - {e['date']}：{e.get('title') or '（無標題）'}（{status}）")
        last = past[-1]
        if last.get("followup_question"):
            lines.append(f"- 上次留給她的延伸提問：{last['followup_question']}")
        if last.get("reflection"):
            lines.append(f"- 她對上次延伸提問的回應：{last['reflection']}")

    if topic == "free":
        counts = weekly_topic_counts(log, today)
        summary = "、".join(
            f"{TOPICS[k]} {counts[k]} 次" for k in TOPICS if k != "free"
        )
        lines.append(f"- 過去七天各主題互動次數：{summary}")

    lines.append("- App 已經自動記錄學習軌跡，不需要再詢問她是否要開始記錄。")
    return "\n".join(lines)


# Appended only after today's lesson has been given, so follow-up chat
# reads like a conversation instead of a fresh six-block lesson each time.
FOLLOWUP_NOTE = """【App 補充：今天的課程已經給過了】
她現在是在今天的課程之後追問、回報進度或聊天。這時候第五部分的六個區塊格式不適用，也不需要加結尾固定句式：
- 直接用自然的對話回答，通常幾句話到一小段就好，只回應她這次說的內容。
- 其他規則照舊：語氣（第七部分）、行為設計（第八部分）、特殊情境（第九部分）、投資內容結尾的免責聲明。
- 她回報完成任務（包括只做了一部分）時，具體肯定「完成」這件事本身，並提醒她可以在頁面上打勾。
- 只有在她明確要求一則新的課程內容時，才重新使用完整的六個區塊與結尾固定句式。"""


def build_system_prompt(log: dict, topic: str, today: date, followup: bool = False) -> str:
    prompt = f"{load_system_prompt()}\n\n{build_history_context(log, topic, today)}"
    if followup:
        prompt += f"\n\n{FOLLOWUP_NOTE}"
    return prompt


def build_kickoff_message(topic: str, today: date, focus: str = "") -> str:
    message = f"今天是 {today.isoformat()}，{weekday_zh(today)}。今天的主題：{TOPICS[topic]}。"
    if focus.strip():
        message += f"我今天特別想了解：{focus.strip()}"
    return message


# ------------------------------------------------------------
# Learning-record page summaries
# ------------------------------------------------------------

# Session number at which each level starts (see level_for_session).
LEVEL_STARTS = {"入門": 1, "中階": 4, "進階": 8}


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
    sessions until the next level (None once at 進階)."""
    sessions = len({e["date"] for e in log["entries"] if e["topic"] == topic})
    completed = len({e["date"] for e in log["entries"]
                     if e["topic"] == topic and e.get("completed")})
    level = level_for_session(sessions) if sessions else None
    next_level = {"入門": "中階", "中階": "進階"}.get(level or "入門")
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
