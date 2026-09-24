"""看書 (part 4.3): a book tracker instead of a daily lesson.

Phase 1 collects title, author, chapter count, page count and chapter
titles one question at a time, then splits the book over 14 days.
Phase 2 checks each day's reading. Everything here is pure logic; the
model is only used for judging her summaries and for tables of contents
too messy for parse_toc."""
import re
import uuid
from datetime import date, timedelta

DAYS = 14

REVIEW_LABEL = "複習／休息"
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


# A chapter marker anywhere in the text: 第3章 / 第十二回 / Chapter 3 / Ch. 3,
# or "3." / "3、" / "3)" at the start of a line or right after a separator.
MARKER = re.compile(
    r"第\s*(?P<zh>\d+|[零〇一二兩三四五六七八九十百]+)\s*[章回篇]"
    r"|(?:chapter|ch\.)\s*(?P<en>\d+)"
    r"|(?:^|(?<=[\n、，,；;。]))\s*(?P<num>\d{1,3})\s*[.．、)）](?!\d)",
    re.IGNORECASE | re.MULTILINE,
)
SEPARATORS = re.compile(r"[\n、，,；;]+")
EDGE_PUNCTUATION = " \t\u3000、，,；;:：.．。-—–)）"
FRONT_BACK_MATTER = {
    "目錄", "目次", "contents", "序", "序言", "自序", "前言", "推薦序", "導讀", "導論", "引言",
    "後記", "結語", "附錄", "致謝", "謝辭", "參考資料", "參考書目", "註釋", "注釋", "索引",
}


def _marker_number(match):
    raw = match.group("zh") or match.group("en") or match.group("num")
    return int(raw) if raw.isdigit() else cn_to_int(raw)


def parse_toc_detail(text: str) -> dict:
    """Split a pasted table of contents into chapter titles, without AI.

    With chapter markers (第N章 / Chapter N / N.) the text is cut at each
    marker, whatever separates them (new lines, 、，；, or nothing), and
    the chapter numbers are kept so gaps can be pointed out. Without
    markers it is split on new lines, or else on 、，；. Front/back matter
    such as 序 or 附錄 is dropped.

    Returns {"titles": [...], "numbers": [...] or None}."""
    text = text.replace("\r", "")
    markers = [m for m in MARKER.finditer(text) if _marker_number(m)]
    if len(markers) >= 2:
        titles, numbers = [], []
        for m, nxt in zip(markers, markers[1:] + [None]):
            body = text[m.end(): nxt.start() if nxt else len(text)]
            # Stop at a line break: what follows on later lines before the
            # next marker (e.g. 附錄, a part heading) isn't this chapter's title.
            body = body.strip(EDGE_PUNCTUATION + "\n").split("\n")[0]
            numbers.append(_marker_number(m))
            titles.append(body.strip(EDGE_PUNCTUATION))
        titles = strip_page_numbers(titles)
        return {"titles": [t or f"第{n}章" for t, n in zip(titles, numbers)], "numbers": numbers}

    parts = [p.strip(EDGE_PUNCTUATION) for p in (text.split("\n") if "\n" in text.strip() else SEPARATORS.split(text))]
    parts = [p for p in parts if p and p.lower() not in FRONT_BACK_MATTER]
    return {"titles": strip_page_numbers(parts), "numbers": None}


def parse_toc(text: str) -> list:
    """Chapter titles from a pasted table of contents ([] if fewer than 2)."""
    titles = parse_toc_detail(text)["titles"]
    return titles if len(titles) >= 2 else []


def has_several_chapters(text: str) -> bool:
    """True when an answer clearly holds more than one chapter, so it must
    never be stored as a single title."""
    return len([m for m in MARKER.finditer(text) if _marker_number(m)]) >= 2


def is_yes(text: str) -> bool:
    return text.strip().rstrip("。!！~～") in YES_WORDS or text.strip().startswith(("是", "對", "沒錯"))


# ------------------------------------------------------------
# 14-day allocation
# ------------------------------------------------------------

def _round_half_up(numerator: int, denominator: int) -> int:
    """numerator / denominator rounded half up (Python's round() is
    half-to-even)."""
    return (numerator * 2 + denominator) // (denominator * 2)


def pages_per_chapter(book: dict) -> int:
    if not book["chapter_count"]:
        return 0
    return _round_half_up(book["total_pages"], book["chapter_count"])


def pages_for_day(book: dict, day: int) -> int:
    """總頁數 ÷ 總章數 × 當天章數, so a 2-chapter day shows twice a
    1-chapter day and it follows manual adjustments."""
    chapters = len(book["plan"][day - 1])
    if not chapters or not book["chapter_count"]:
        return 0
    return _round_half_up(book["total_pages"] * chapters, book["chapter_count"])


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
        return REVIEW_LABEL
    titles = "；".join(book["chapters"][c - 1] for c in chapters)
    return f"{chapter_range(chapters)}：{titles}"


def plan_table(book: dict) -> str:
    rows = ["| 天 | 章節範圍與標題 | 約略頁數 |", "| --- | --- | --- |"]
    for day in range(1, DAYS + 1):
        mark = "・已確認" if str(day) in book["checks"] else ""
        page_hint = f"約 {pages_for_day(book, day)} 頁" if book["plan"][day - 1] else "—"
        rows.append(f"| 第{day}天{mark} | {day_description(book, day)} | {page_hint} |")
    table = "\n".join(rows)
    # The explanation for 複習／休息 days goes under the table, once.
    last = last_reading_day(book["plan"])
    empty = [d for d in range(1, DAYS + 1) if not book["plan"][d - 1]]
    notes = []
    rest = [d for d in empty if d < last]
    if rest:
        notes.append(f"※ {_day_list(rest)}{REST_DAY_NOTE}。")
    early = [d for d in empty if d > last]
    if early:
        notes.append(f"※ {_day_list(early)}{EARLY_FINISH_NOTE}。")
    return table + ("\n\n" + "\n".join(notes) if notes else "")


def _day_list(days: list) -> str:
    """「第11–14天：」 for a run of days, 「第3、5天：」 otherwise."""
    if len(days) > 1 and days == list(range(days[0], days[-1] + 1)):
        return f"第{days[0]}–{days[-1]}天："
    return "第" + "、".join(map(str, days)) + "天："


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
        "pending_numbers": [],
        "pending_raw": "",
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
    """The confirmed book she's reading, if any. Books still being set up
    are session drafts; setup/planning rows left in storage by older
    versions are ignored."""
    active = [b for b in books if b["status"] == "reading"]
    return active[-1] if active else None


def next_day(book: dict):
    """First day with chapters that hasn't passed its check, or None."""
    for day in range(1, DAYS + 1):
        if book["plan"][day - 1] and str(day) not in book["checks"]:
            return day
    return None


def opens_on(book: dict, day: int) -> date:
    """Day N of the plan opens N-1 days after the book started: days she
    missed can be caught up, but she can't read ahead of the calendar."""
    return date.fromisoformat(book["started_on"]) + timedelta(days=day - 1)


def is_open(book: dict, day: int, today: date) -> bool:
    return today >= opens_on(book, day)


def not_open_message(book: dict, day: int) -> str:
    opens = opens_on(book, day)
    return (
        f"今天的份量已經完成了。第{day}天的範圍（{day_description(book, day)}）"
        f"{opens.month}月{opens.day}日才開放，一天讀一點比較記得住，到時候再回來跟我聊。"
    )


def question_for(book: dict) -> str:
    return QUESTIONS[book["step"]].format(title=book["title"])


TOC_HELP = (
    "沒問題的話回答「對」；想改或補某一章就打「第3章：標題」；"
    "也可以整份重新貼一次，或直接告訴我正確的章數。"
)


def toc_preview(book: dict) -> str:
    """The parsed chapter list, with any mismatch against the chapter
    count she gave spelled out, for her to confirm."""
    titles = book["pending_toc"]
    listing = "\n".join(f"{i}. {t}" for i, t in enumerate(titles, 1))
    count = book["chapter_count"]
    lines = [f"我從目錄整理出 {len(titles)} 章：\n\n{listing}\n"]
    if len(titles) != count:
        diff = f"多了 {len(titles) - count} 章" if len(titles) > count else f"少了 {count - len(titles)} 章"
        lines.append(f"跟你一開始說的 {count} 章不一樣（{diff}），幫你確認一下。")
        numbers = book.get("pending_numbers") or []
        if numbers:
            missing = [n for n in range(1, max(max(numbers), count) + 1) if n not in numbers]
            repeated = sorted({n for n in numbers if numbers.count(n) > 1})
            if missing:
                lines.append("目錄裡沒有找到：" + "、".join(f"第{n}章" for n in missing) + "。")
            if repeated:
                lines.append("出現不只一次：" + "、".join(f"第{n}章" for n in repeated) + "。")
        lines.append(f"回答「對」就以這 {len(titles)} 章為準。")
    lines.append(TOC_HELP)
    if book.get("pending_raw"):
        lines.append("如果這其實是同一章的標題，回答「這是一章」就好。")
    return "\n".join(lines)


def _show_toc(book: dict, titles: list, numbers=None, raw="") -> str:
    book["pending_toc"] = list(titles)
    book["pending_numbers"] = list(numbers or [])
    # Only set when a single line was split on 、，； with no chapter
    # markers: that could have been one title, so she can undo the split.
    book["pending_raw"] = raw if not numbers and "\n" not in raw.strip() else ""
    book["step"] = "confirm_toc"
    return toc_preview(book)


def _finish_setup(book: dict) -> str:
    book["chapter_count"] = len(book["chapters"])
    book["plan"] = allocate(book["chapter_count"])
    book["status"] = "planning"
    book["step"] = None
    book["pending_toc"] = []
    book["pending_numbers"] = []
    book["pending_raw"] = ""
    return (
        f"《{book['title']}》共 {book['chapter_count']} 章、{book['total_pages']} 頁，"
        f"分成 14 天，平均每章大約 {pages_per_chapter(book)} 頁，每天的頁數寫在表格裡。"
        f"下面是完整的 14 天預覽，按「確認進度表」之後才會正式開始：\n\n"
        f"{plan_table(book)}\n\n{PLAN_QUESTION}"
    )


def answer_setup(book: dict, text: str) -> str:
    """Advance phase 1 with her answer and return the coach's reply."""
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
            return NEED_NUMBER.format(example=example, question=question_for(book))
        book[step] = value
        book["step"] = "total_pages" if step == "chapter_count" else "chapters"
    elif step == "chapters":
        return _answer_chapters(book, text)
    elif step == "confirm_toc":
        return _answer_confirm_toc(book, text)
    return question_for(book)


def _answer_chapters(book: dict, text: str) -> str:
    # Several chapters in one answer (a pasted table of contents, on one
    # line or many): list them for her to confirm, never store as one title.
    if has_several_chapters(text) or not book["chapters"]:
        detail = parse_toc_detail(text)
        if len(detail["titles"]) >= 2:
            return _show_toc(book, detail["titles"], detail["numbers"], raw=text)

    expected = len(book["chapters"]) + 1
    parsed = parse_chapter_line(text)
    if parsed:
        number, title = parsed
        if number != expected:
            return (
                f"幫你確認一下：現在輪到第{expected}章，你寫的是第{number}章。"
                f"如果這本書的章數跟一開始說的 {book['chapter_count']} 章不一樣，直接告訴我正確的章數；"
                f"不然就給我第{expected}章的標題就好。"
            )
    else:
        # A bare number here is a corrected chapter count, not a title.
        if re.fullmatch(r"\d+\s*章?", text):
            book["chapter_count"] = int(re.match(r"\d+", text).group())
            if len(book["chapters"]) >= book["chapter_count"]:
                book["chapters"] = book["chapters"][: book["chapter_count"]]
                return _finish_setup(book)
            return f"好，是 {book['chapter_count']} 章。第{expected}章的標題是？（第{expected}章：___）"
        title = text
    book["chapters"].append(title or f"第{expected}章")
    if len(book["chapters"]) >= book["chapter_count"]:
        return _finish_setup(book)
    n = len(book["chapters"]) + 1
    return f"第{n}章的標題是？（第{n}章：___）"


EDIT_TITLE = re.compile(r"^\s*第\s*(\d+|[零〇一二兩三四五六七八九十百]+)\s*章\s*[:：]\s*(.+)$")


def parse_title_edit(text: str):
    """(chapter number, new title) for 「第3章：新的標題」, else None."""
    match = EDIT_TITLE.match(text)
    if not match or has_several_chapters(text):
        return None
    raw = match.group(1)
    number = int(raw) if raw.isdigit() else cn_to_int(raw)
    return (number, match.group(2).strip()) if number else None


def _edit_or_add_chapter(book: dict, number: int, title: str) -> str:
    """「第N章：標題」 while confirming the list: change chapter N, or add it
    when it's missing (so a short list can be completed without pasting
    the whole table of contents again)."""
    titles, numbers = book["pending_toc"], book.get("pending_numbers") or []
    limit = max(book["chapter_count"], len(titles) + 1)
    if number > limit and number not in numbers:
        return (
            f"幫你確認一下：你說這本書有 {book['chapter_count']} 章，清單現在有 {len(titles)} 章，"
            f"所以還不能補第{number}章。如果章數不對，直接告訴我正確的章數就好。"
        )
    if numbers:
        # A numbered list: chapter N is the entry labelled N, and a missing
        # N is slotted in by number.
        if number in numbers:
            titles[numbers.index(number)] = title
            return f"改好了。\n\n{toc_preview(book)}"
        at = len([n for n in numbers if n < number])
        numbers.insert(at, number)
        titles.insert(at, title)
        return f"補上第{number}章了。\n\n{toc_preview(book)}"
    if 1 <= number <= len(titles):
        titles[number - 1] = title
        return f"改好了。\n\n{toc_preview(book)}"
    if number == len(titles) + 1:
        titles.append(title)
        return f"補上第{number}章了。\n\n{toc_preview(book)}"
    return (
        f"目前清單有 {len(titles)} 章，要補的話請從第{len(titles) + 1}章開始補，"
        f"例如「第{len(titles) + 1}章：標題」。{TOC_HELP}"
    )


def _answer_confirm_toc(book: dict, text: str) -> str:
    titles = book["pending_toc"]
    if is_yes(text):
        book["chapters"] = list(titles)
        return _finish_setup(book)
    if book.get("pending_raw") and re.fullmatch(r"(這|那)?(其實)?(是|只是)?(同)?一章(的標題)?[。!！]?|不是|不對", text):
        book["chapters"] = [book["pending_raw"].strip()]
        book["pending_toc"], book["pending_numbers"], book["pending_raw"] = [], [], ""
        book["step"] = "chapters"
        if len(book["chapters"]) >= book["chapter_count"]:
            return _finish_setup(book)
        return f"好，第1章是「{book['chapters'][0]}」。第2章的標題是？（第2章：___）"
    edit = parse_title_edit(text)
    if edit:
        number, title = edit
        return _edit_or_add_chapter(book, number, title)
    if re.fullmatch(r"\d+\s*章?", text) or re.fullmatch(r"[零〇一二兩三四五六七八九十百]+\s*章", text):
        book["chapter_count"] = parse_number(text)
        return toc_preview(book)
    detail = parse_toc_detail(text)
    if len(detail["titles"]) >= 2:
        return _show_toc(book, detail["titles"], detail["numbers"], raw=text)
    return f"我不太確定要怎麼改。{TOC_HELP}"


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
    "【App 補充：現在是看書模式】不使用每日課程的區塊格式，也不需要結尾固定句式，用自然的對話語氣。"
    "進度、天數、章節範圍由 App 精確處理，以下面的資料為準。"
)
SUMMARY_CHARS = 150    # per-day cap on her own words quoted back to the model


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + "…"


def book_header(book: dict) -> str:
    return (
        f"{BOOK_MODE_NOTE}\n"
        f"書名：《{book['title']}》　作者：{book['author']}　"
        f"共 {book['chapter_count']} 章、{book['total_pages']} 頁，平均每章約 {pages_per_chapter(book)} 頁"
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
        if book["step"] == "confirm_toc":
            return toc_preview(book)
        return question_for(book)
    if book["status"] == "planning":
        return f"《{book['title']}》的 14 天進度表：\n\n{plan_table(book)}\n\n{PLAN_QUESTION}"
    day = next_day(book)
    if not is_open(book, day, today):
        return not_open_message(book, day)
    pages = pages_for_day(book, day)
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
