"""看書 (part 4.3): a book tracker instead of a daily lesson.

Phase 1 collects title, author, chapter count, page count and chapter
titles one question at a time, then splits the book over 14 days.
Phase 2 checks each day's reading. Everything here is pure logic; the
model is only used for judging her summaries and for tables of contents
too messy for parse_toc."""
import re
import uuid
from datetime import date

DAYS = 14

EARLY_FINISH_NOTE = "本書進度已提前完成，這幾天可以拿來複習前面內容、整理筆記，或提前開始下一本書"
REST_DAY_NOTE = "這天沒有分配章節，可以休息或複習前面的內容"
PLAN_QUESTION = "這樣的分配感覺可以嗎？有沒有哪幾天想要加重或減輕份量？"
PLAN_CONFIRMED = (
    "進度表已經確定了，從今天開始，你每天讀完指定範圍之後，回來跟我聊聊內容就可以了，"
    "我會幫你確認有沒有真的讀懂。"
)

QUESTIONS = {
    "title": "想開始讀哪一本書呢？先跟我說書名就好。",
    "author": "《{title}》，好。作者是誰呢？",
    "chapter_count": "這本書總共有幾章？給我一個明確的數字就好，例如「12」。",
    "total_pages": "那總共有幾頁呢？一樣給我一個數字就好。",
    "chapters": (
        "最後是每一章的標題。你可以直接把整份目錄貼上來（從書店網頁複製、或拍照辨識的文字都可以），"
        "我會自己整理出來；也可以一章一章告訴我，從「第1章：___」開始。"
    ),
}
NEED_NUMBER = "我需要一個明確的數字，例如「{example}」，這樣分配才算得準。{question}"

CN_DIGITS = {"零": 0, "〇": 0, "一": 1, "二": 2, "兩": 2, "三": 3, "四": 4,
             "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
YES_WORDS = ("是", "對", "沒錯", "嗯", "好", "yes", "ok", "OK", "Yes", "可以")


# ------------------------------------------------------------
# Parsing her answers
# ------------------------------------------------------------

def cn_to_int(text: str):
    """Chinese numerals up to 9999, e.g. 十二 -> 12, 三百二十 -> 320."""
    if not text or any(c not in CN_DIGITS and c not in "十百千" for c in text):
        return None
    total, current = 0, 0
    for c in text:
        if c in CN_DIGITS:
            current = CN_DIGITS[c]
        else:
            unit = {"十": 10, "百": 100, "千": 1000}[c]
            total += (current or 1) * unit
            current = 0
    return total + current


def parse_number(text: str):
    """First positive whole number in an answer ("大概 320 頁", "十二章")."""
    match = re.search(r"\d+", text.replace(",", "").replace("，", ""))
    if match:
        value = int(match.group())
        return value if value > 0 else None
    match = re.search(r"[零〇一二兩三四五六七八九十百千]+", text)
    if match:
        value = cn_to_int(match.group())
        return value if value else None
    return None


CHAPTER_LINE = re.compile(
    r"^\s*(?:"
    r"第\s*(?P<zh>\d+|[零〇一二兩三四五六七八九十百]+)\s*[章回篇]"
    r"|(?:chapter|ch\.?)\s*(?P<en>\d+)"
    r"|(?P<num>\d+)\s*(?=[.、)）:：\s])"
    r")\s*[.、:：)）\-—–]*\s*(?P<title>.*?)\s*$",
    re.IGNORECASE,
)


def parse_chapter_line(line: str):
    """(number, title) for a line like 第3章：標題 / Chapter 3 Title / 3. 標題."""
    match = CHAPTER_LINE.match(line)
    if not match:
        return None
    raw = match.group("zh") or match.group("en") or match.group("num")
    number = int(raw) if raw.isdigit() else cn_to_int(raw)
    if not number:
        return None
    return number, match.group("title").strip()


PAGE_NUMBER = re.compile(r"^(?P<title>.*?)[\s.·…]+(?P<page>\d+)$")


def strip_page_numbers(titles: list) -> list:
    """Drop trailing page numbers copied along with a table of contents
    ("標題 ..... 23"), but only when they look like page numbers: most
    lines have one and they never go down. Otherwise titles that end in
    a number (《1984》, "Part 2") would lose it."""
    matches = [PAGE_NUMBER.match(t) for t in titles]
    pages = [int(m.group("page")) for m in matches if m]
    if len(pages) * 2 < len(titles) or pages != sorted(pages):
        return titles
    return [m.group("title").strip() if m else t for t, m in zip(titles, matches)]


def parse_toc(text: str) -> list:
    """Chapter titles, in order, from a pasted table of contents. Returns []
    unless the numbered lines run 1, 2, 3, ... without gaps."""
    found = [p for p in (parse_chapter_line(l) for l in text.splitlines()) if p]
    numbers = [n for n, _ in found]
    if len(found) < 2 or numbers != list(range(1, len(found) + 1)):
        return []
    titles = strip_page_numbers([title for _, title in found])
    return [title or f"第{n}章" for n, title in zip(numbers, titles)]


def looks_like_toc(text: str) -> bool:
    return len([l for l in text.splitlines() if l.strip()]) >= 3


def is_yes(text: str) -> bool:
    return text.strip().rstrip("。!！~～") in YES_WORDS or text.strip().startswith(("是", "對", "沒錯"))


# ------------------------------------------------------------
# 14-day allocation
# ------------------------------------------------------------

def pages_per_day(total_pages: int) -> int:
    """總頁數 ÷ 14, rounded half up (Python's round() is half-to-even)."""
    return (total_pages * 2 + DAYS) // (DAYS * 2)


def allocate(chapter_count: int) -> list:
    """Chapter numbers for each of the 14 days.

    ≤ 14 chapters: one per day from day 1; later days stay empty (early
    finish). > 14 chapters: every day gets count // 14, and the first
    count % 14 days get one more."""
    if chapter_count <= DAYS:
        return [[d + 1] if d < chapter_count else [] for d in range(DAYS)]
    base, extra = divmod(chapter_count, DAYS)
    plan, next_chapter = [], 1
    for d in range(DAYS):
        size = base + (1 if d < extra else 0)
        plan.append(list(range(next_chapter, next_chapter + size)))
        next_chapter += size
    return plan


def move_last_to_next(plan: list, day: int) -> bool:
    """Move day's last chapter to the start of the next day (days are
    1-based). Returns False if that isn't possible."""
    i = day - 1
    if not (0 <= i < DAYS - 1) or not plan[i]:
        return False
    plan[i + 1].insert(0, plan[i].pop())
    return True


def move_first_from_next(plan: list, day: int) -> bool:
    """Pull the next day's first chapter onto the end of this day."""
    i = day - 1
    if not (0 <= i < DAYS - 1) or not plan[i + 1]:
        return False
    plan[i].append(plan[i + 1].pop(0))
    return True


def last_reading_day(plan: list) -> int:
    return max((d + 1 for d, chapters in enumerate(plan) if chapters), default=0)


def chapter_range(chapters: list) -> str:
    if not chapters:
        return ""
    if len(chapters) == 1:
        return f"第{chapters[0]}章"
    return f"第{chapters[0]}–{chapters[-1]}章"


def day_description(book: dict, day: int) -> str:
    """"第3–4章：標題A；標題B" or the note for a day with no chapters."""
    chapters = book["plan"][day - 1]
    if not chapters:
        return EARLY_FINISH_NOTE if day > last_reading_day(book["plan"]) else REST_DAY_NOTE
    titles = "；".join(book["chapters"][c - 1] for c in chapters)
    return f"{chapter_range(chapters)}：{titles}"


def plan_table(book: dict) -> str:
    pages = pages_per_day(book["total_pages"])
    rows = ["| 天 | 章節範圍與標題 | 約略頁數 |", "| --- | --- | --- |"]
    for day in range(1, DAYS + 1):
        mark = " ✅" if str(day) in book["checks"] else ""
        page_hint = f"約 {pages} 頁" if book["plan"][day - 1] else "—"
        rows.append(f"| 第{day}天{mark} | {day_description(book, day)} | {page_hint} |")
    return "\n".join(rows)


# ------------------------------------------------------------
# Book state
# ------------------------------------------------------------

def new_book(today: date) -> dict:
    return {
        "id": uuid.uuid4().hex,
        "status": "setup",        # setup → planning → reading → finished; or switched
        "step": "title",
        "title": "",
        "author": "",
        "chapter_count": 0,
        "total_pages": 0,
        "chapters": [],
        "pending_toc": [],
        "plan": [],
        "checks": {},              # "day" -> {"passed_on": iso date, "summary": her words}
        "started_on": today.isoformat(),
        "last_active_on": today.isoformat(),
        "finished_on": "",
        "final_summary": "",
    }


def normalize_book(data):
    if not isinstance(data, dict) or not data.get("id"):
        return None
    book = new_book(date.today())
    book.update({k: v for k, v in data.items() if k in book})
    return book


def current_book(books: list):
    """The book she's working on (not finished or switched), if any."""
    active = [b for b in books if b["status"] in ("setup", "planning", "reading")]
    return active[-1] if active else None


def next_day(book: dict):
    """First day with chapters that hasn't passed its check, or None."""
    for day in range(1, DAYS + 1):
        if book["plan"][day - 1] and str(day) not in book["checks"]:
            return day
    return None


def question_for(book: dict) -> str:
    return QUESTIONS[book["step"]].format(title=book["title"])


def _finish_setup(book: dict) -> str:
    book["chapter_count"] = len(book["chapters"])
    book["plan"] = allocate(book["chapter_count"])
    book["status"] = "planning"
    book["step"] = None
    book["pending_toc"] = []
    return (
        f"《{book['title']}》共 {book['chapter_count']} 章、{book['total_pages']} 頁，"
        f"分成 14 天，每天大約 {pages_per_day(book['total_pages'])} 頁：\n\n"
        f"{plan_table(book)}\n\n{PLAN_QUESTION}"
    )


def apply_toc(book: dict, titles: list) -> str:
    """Use a parsed table of contents. Gently double-checks the chapter
    count when it disagrees with what she said earlier."""
    if len(titles) == book["chapter_count"]:
        book["chapters"] = list(titles)
        return _finish_setup(book)
    book["pending_toc"] = list(titles)
    book["step"] = "confirm_count"
    return (
        f"我從目錄整理出 {len(titles)} 章，跟你一開始說的 {book['chapter_count']} 章不太一樣，"
        f"幫你確認一下：這本書應該是 {len(titles)} 章嗎？回答「是」，或告訴我正確的章數就好。"
    )


def answer_setup(book: dict, text: str):
    """Advance phase 1 with her answer. Returns (reply, needs_toc_help):
    needs_toc_help means the answer looks like a pasted table of contents
    that parse_toc couldn't read, so the caller should ask the model to
    extract titles and pass them to apply_toc."""
    text = text.strip()
    step = book["step"]

    if step == "title":
        book["title"] = text.strip("《》〈〉「」\"' ")
        book["step"] = "author"
    elif step == "author":
        book["author"] = text
        book["step"] = "chapter_count"
    elif step in ("chapter_count", "total_pages"):
        value = parse_number(text)
        if value is None:
            example = "12" if step == "chapter_count" else "320"
            return NEED_NUMBER.format(example=example, question=question_for(book)), False
        book[step] = value
        book["step"] = "total_pages" if step == "chapter_count" else "chapters"
    elif step == "chapters":
        return _answer_chapters(book, text)
    elif step == "confirm_count":
        return _answer_confirm_count(book, text), False
    return question_for(book), False


def _answer_chapters(book: dict, text: str):
    toc = parse_toc(text)
    if toc:
        return apply_toc(book, toc), False
    if looks_like_toc(text) and not book["chapters"]:
        return "", True

    expected = len(book["chapters"]) + 1
    parsed = parse_chapter_line(text)
    if parsed:
        number, title = parsed
        if number != expected:
            return (
                f"幫你確認一下：現在輪到第{expected}章，你寫的是第{number}章。"
                f"如果這本書的章數跟一開始說的 {book['chapter_count']} 章不一樣，直接告訴我正確的章數；"
                f"不然就給我第{expected}章的標題就好。"
            ), False
    else:
        # A bare number here is a corrected chapter count, not a title.
        if re.fullmatch(r"\d+\s*章?", text):
            book["chapter_count"] = int(re.match(r"\d+", text).group())
            if len(book["chapters"]) >= book["chapter_count"]:
                book["chapters"] = book["chapters"][: book["chapter_count"]]
                return _finish_setup(book), False
            return f"好，是 {book['chapter_count']} 章。第{expected}章的標題是？（第{expected}章：___）", False
        title = text
    book["chapters"].append(title or f"第{expected}章")
    if len(book["chapters"]) >= book["chapter_count"]:
        return _finish_setup(book), False
    n = len(book["chapters"]) + 1
    return f"第{n}章的標題是？（第{n}章：___）", False


def _answer_confirm_count(book: dict, text: str) -> str:
    toc = book["pending_toc"]
    number = parse_number(text)
    if is_yes(text) or number == len(toc):
        book["chapters"] = toc
        return _finish_setup(book)
    if number is None:
        return f"這本書應該是 {len(toc)} 章嗎？回答「是」，或告訴我正確的章數就好。"
    book["chapter_count"] = number
    book["pending_toc"] = []
    book["step"] = "chapters"
    if number > len(toc):
        book["chapters"] = toc
        n = len(toc) + 1
        return f"好，是 {number} 章。目錄裡有 {len(toc)} 章，還差後面幾章：第{n}章的標題是？（第{n}章：___）"
    book["chapters"] = []
    return (
        f"好，是 {number} 章。目錄裡可能多了序、附錄之類的部分，"
        "可以再貼一次只有正式章節的目錄嗎？或是一章一章告訴我也可以，從「第1章：___」開始。"
    )


def record_pass(book: dict, day: int, summary: str, today: date) -> None:
    book["checks"][str(day)] = {"passed_on": today.isoformat(), "summary": summary}
    book["last_active_on"] = today.isoformat()
    if next_day(book) is None:
        book["status"] = "finished"
        book["finished_on"] = today.isoformat()


def days_away(book: dict, today: date) -> int:
    return (today - date.fromisoformat(book["last_active_on"])).days


# ------------------------------------------------------------
# Prompts for the model
# ------------------------------------------------------------
# These are appended to core + the 看書 module (see reading.py). They
# carry only what each call needs, never the whole 14-day table with
# titles, so every request stays inside the token budget.

BOOK_MODE_NOTE = (
    "【App 補充：現在是看書模式】不使用六個區塊的輸出格式，也不需要結尾固定句式，用自然的對話語氣。"
    "進度、天數、章節範圍由 App 精確處理，以下面的資料為準。"
)
SUMMARY_CHARS = 150    # per-day cap on her own words quoted back to the model


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + "…"


def book_header(book: dict) -> str:
    return (
        f"{BOOK_MODE_NOTE}\n"
        f"書名：《{book['title']}》　作者：{book['author']}　"
        f"共 {book['chapter_count']} 章、{book['total_pages']} 頁，每天約 {pages_per_day(book['total_pages'])} 頁"
    )


def compact_plan(book: dict) -> str:
    """Day → chapter range only (no titles), for plan adjustments."""
    return "\n".join(
        f"第{d}天：{chapter_range(book['plan'][d - 1]) or '（沒有章節）'}"
        for d in range(1, DAYS + 1)
    )


def judge_prompt(book: dict, day: int) -> str:
    """Ask for a JSON verdict on her summary of one day's reading."""
    upcoming = next_day({**book, "checks": {**book["checks"], str(day): {}}})
    if upcoming is None:
        after = "這是這本書最後一個閱讀日。通過時不用預告明天，App 會接著產生整本書的總結。"
    else:
        after = (
            f"通過時，明確告訴她「今天算完成了，明天進到第{upcoming}天」，"
            f"並用一句話預告第{upcoming}天的範圍：{_clip(day_description(book, upcoming), 200)}。"
        )
    return (
        f"{book_header(book)}\n\n"
        f"【現在的任務】她接下來的訊息，是用自己的話分享第{day}天的閱讀內容。"
        f"第{day}天的範圍是：{_clip(day_description(book, day), 400)}。\n"
        "依照上面的通過標準判斷她是否讀過並理解這個範圍的大意。\n"
        f"{after}\n"
        '只輸出一個 JSON 物件，格式：{"passed": true 或 false, "reply": "你要對她說的話"}'
    )


def adjust_prompt(book: dict) -> str:
    """Turn her free-text adjustment request into chapter moves."""
    return (
        f"{book_header(book)}\n\n目前的 14 天分配：\n{compact_plan(book)}\n\n"
        "【現在的任務】她正在看這份進度表，接下來的訊息是她的想法。"
        "如果她想調整某幾天的份量，把她的需求換成「在相鄰兩天之間移動章節」的操作："
        '{"day": 3, "action": "to_next"} 是把第3天的最後一章移到第4天；'
        '{"day": 3, "action": "from_next"} 是把第4天的第一章移到第3天。'
        "一次移動一章，需要移好幾章就列好幾個操作，依序執行。不要改變天數、不要重新分配整份表。\n"
        "如果她表示這樣可以、沒問題，confirmed 設為 true。如果她只是在問問題或聊天，moves 留空。\n"
        '只輸出一個 JSON 物件，格式：{"moves": [...], "confirmed": true 或 false, '
        '"reply": "你要對她說的話（有調整的話簡短說明調整了什麼，App 會把新的進度表附在後面）"}'
    )


def final_summary_prompt(book: dict, summary_chars: int = SUMMARY_CHARS) -> str:
    days = sorted(book["checks"].items(), key=lambda kv: int(kv[0]))
    shared = "\n".join(
        f"- 第{d}天（{chapter_range(book['plan'][int(d) - 1])}）她分享：{_clip(c['summary'], summary_chars)}"
        for d, c in days
    )
    return (
        f"{book_header(book)}\n\n她每天用自己的話分享的內容：\n{shared}\n\n"
        "【現在的任務】她剛剛把這本書的每一天都確認讀懂了。給她一個真誠而且具體的總結式肯定："
        "具體提到她在這幾天分別掌握了哪些重點或概念（用上面她自己分享過的內容），"
        "不要籠統地說「恭喜你讀完了」。最後自然地問她要不要開始規劃下一本書。"
    )


def chat_prompt(book: dict) -> str:
    day = next_day(book)
    today_range = f"目前進行到第{day}天：{_clip(day_description(book, day), 300)}" if day else ""
    return (
        f"{book_header(book)}\n{today_range}\n\n"
        "【現在的任務】她在聊這本書、問問題，或聊別的事情（不是在回報讀完今天的範圍，那個 App 會另外處理）。"
        "用自然、簡短的對話回應她這次說的內容。"
    )


def apply_moves(plan: list, moves) -> int:
    """Apply model-suggested moves, skipping any that are invalid.
    Returns how many were applied."""
    applied = 0
    for move in moves if isinstance(moves, list) else []:
        if not isinstance(move, dict):
            continue
        day = move.get("day")
        if not isinstance(day, int):
            continue
        action = {"to_next": move_last_to_next, "from_next": move_first_from_next}.get(move.get("action"))
        if action and action(plan, day):
            applied += 1
    return applied


FINISHED_READING_WORDS = re.compile(r"(讀|看)(完|好)了?|完成了|讀到了?第")


def says_finished_reading(text: str) -> bool:
    return bool(FINISHED_READING_WORDS.search(text))


def resume_message(book: dict, today: date) -> str:
    """What the coach says when she opens the book page."""
    if book["status"] == "setup":
        if book["step"] == "chapters" and book["chapters"]:
            n = len(book["chapters"]) + 1
            return f"我們繼續整理《{book['title']}》的章節。第{n}章的標題是？（第{n}章：___）"
        if book["step"] == "confirm_count":
            return f"幫你確認一下：《{book['title']}》應該是 {len(book['pending_toc'])} 章嗎？回答「是」，或告訴我正確的章數就好。"
        return question_for(book)
    if book["status"] == "planning":
        return f"《{book['title']}》的 14 天進度表：\n\n{plan_table(book)}\n\n{PLAN_QUESTION}"
    day = next_day(book)
    pages = pages_per_day(book["total_pages"])
    if days_away(book, today) > 1:
        return (
            f"我們從第{day}天繼續。《{book['title']}》第{day}天的範圍是{day_description(book, day)}，"
            f"大約 {pages} 頁。讀完之後回來跟我聊聊就好。"
        )
    return (
        f"《{book['title']}》今天是第{day}天：{day_description(book, day)}，大約 {pages} 頁。"
        "讀完之後按下面的按鈕，或直接跟我說一聲。"
    )


def check_start_message(book: dict, day: int) -> str:
    return (
        f"第{day}天的範圍是{day_description(book, day)}。\n\n"
        "用你自己的話跟我說說今天讀到了什麼：大概在講什麼、印象最深的片段，或任何想法都可以。"
        "這不是考試，不用寫得很工整，像跟朋友聊天分享一樣就好。"
    )
