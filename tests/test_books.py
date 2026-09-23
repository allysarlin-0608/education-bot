from datetime import date

from coach import books

TODAY = date(2026, 9, 23)


def setup_book(*answers, confirm=True):
    """Answer the setup questions; if they end on the chapter-list
    confirmation, answer 「對」 too (unless confirm=False)."""
    book = books.new_book(TODAY)
    replies = [books.answer_setup(book, a) for a in answers]
    if confirm and book["step"] == "confirm_toc":
        replies.append(books.answer_setup(book, "對"))
    return book, replies


# ---------- allocation ----------

def test_pages_for_day_follows_chapters_per_day():
    """L: 3 chapters / 60 pages is ~20 pages a day, not 60 / 14 = 4."""
    book, _ = setup_book("書", "作者", "3", "60", "第1章：A\n第2章：B\n第3章：C")
    assert [books.pages_for_day(book, d) for d in (1, 2, 3, 4)] == [20, 20, 20, 0]
    books.move_first_from_next(book["plan"], 1)                  # day 1 now has 2 chapters
    assert [books.pages_for_day(book, d) for d in (1, 2, 3)] == [40, 0, 20]
    table = books.plan_table(book)
    assert "| 第1天 | 第1–2章：A；B | 約 40 頁 |" in table


def test_pages_round_half_up():
    book, _ = setup_book("書", "作者", "2", "5", "第1章：A\n第2章：B")
    assert books.pages_for_day(book, 1) == 3                     # 2.5 -> 3 (round() gives 2)
    assert books.pages_per_chapter(book) == 3


def test_allocate_fewer_chapters_than_days():
    plan = books.allocate(10)
    assert plan[:10] == [[i] for i in range(1, 11)]
    assert plan[10:] == [[]] * 4


def test_allocate_exactly_fourteen():
    assert books.allocate(14) == [[i] for i in range(1, 15)]


def test_allocate_more_chapters_spreads_remainder_to_first_days():
    plan = books.allocate(31)                 # 31 = 2*14 + 3
    sizes = [len(d) for d in plan]
    assert sizes == [3, 3, 3] + [2] * 11
    flat = [c for d in plan for c in d]
    assert flat == list(range(1, 32))


def test_plan_table_lists_titles_and_early_finish():
    book, _ = setup_book("原子習慣", "James Clear", "3", "280", "第1章：A\n第2章：B\n第3章：C")
    table = books.plan_table(book)
    assert "| 第1天 | 第1章：A | 約 93 頁 |" in table     # 280 pages / 3 chapters
    assert "| 第4天 | 複習／休息 | — |" in table
    assert table.count(books.EARLY_FINISH_NOTE) == 1              # O: explained once, under the table
    assert f"※ 第4–14天：{books.EARLY_FINISH_NOTE}" in table
    assert len([l for l in table.splitlines() if l.startswith("|")]) == 16   # header + rule + 14 days


def test_adjust_moves_chapters_between_neighbours():
    plan = books.allocate(16)                 # [1,2],[3,4],[5],...
    assert books.move_last_to_next(plan, 1)
    assert plan[:3] == [[1], [2, 3, 4], [5]]
    assert books.move_first_from_next(plan, 1)
    assert plan[:2] == [[1, 2], [3, 4]]
    assert not books.move_last_to_next(plan, 14)
    empty = books.allocate(3)
    assert not books.move_first_from_next(empty, 5)   # nothing on day 6


def test_empty_middle_day_is_a_rest_day():
    book, _ = setup_book("書", "作者", "3", "90", "第1章：A\n第2章：B\n第3章：C")
    books.move_last_to_next(book["plan"], 2)      # day 2 now empty, day 3 has 2 and 3
    assert books.day_description(book, 2) == books.REVIEW_LABEL
    assert f"※ 第2天：{books.REST_DAY_NOTE}" in books.plan_table(book)
    assert books.day_description(book, 3) == "第2–3章：B；C"


# ---------- parsing ----------

def test_parse_number():
    assert books.parse_number("大概 320 頁") == 320
    assert books.parse_number("1,024") == 1024
    assert books.parse_number("十二章") == 12
    assert books.parse_number("三百二十") == 320
    assert books.parse_number("不知道") is None
    assert books.parse_number("0") is None


def test_parse_toc_formats():
    zh = "目錄\n序\n第一章　改變的力量 ..... 12\n第二章 習慣如何運作 35\n第三章：四大法則\n附錄"
    assert books.parse_toc(zh) == ["改變的力量", "習慣如何運作", "四大法則"]
    en = "Chapter 1: The Surprising Power\nChapter 2 How Habits Shape\nChapter 3. Make It Obvious"
    assert books.parse_toc(en) == ["The Surprising Power", "How Habits Shape", "Make It Obvious"]
    nums = "1. 開端\n2、轉折\n3) 結局"
    assert books.parse_toc(nums) == ["開端", "轉折", "結局"]
    assert books.parse_toc("只有一行") == []


def test_parse_toc_one_line_separated_by_punctuation():
    """The bug report: 20 chapters pasted on one line, separated by 、."""
    line = "、".join(f"第{i}章 測試{i}" for i in range(1, 21))
    assert books.parse_toc(line) == [f"測試{i}" for i in range(1, 21)]
    for sep in ("，", "；", ",", ";", " "):
        assert books.parse_toc(sep.join(f"第{i}章：T{i}" for i in range(1, 6))) == [f"T{i}" for i in range(1, 6)]
    assert books.parse_toc("Chapter 1 A, Chapter 2 B, Chapter 3 C") == ["A", "B", "C"]
    assert books.parse_toc("1. 開端、2. 轉折、3. 結局") == ["開端", "轉折", "結局"]
    assert books.parse_toc("認知革命、農業革命、人類的融合統一、科學革命") == ["認知革命", "農業革命", "人類的融合統一", "科學革命"]
    assert books.parse_toc("認知革命；農業革命；科學革命") == ["認知革命", "農業革命", "科學革命"]


def test_parse_toc_chinese_numerals_and_gaps():
    detail = books.parse_toc_detail("第一章 A 第二章 B 第四章 D")
    assert detail == {"titles": ["A", "B", "D"], "numbers": [1, 2, 4]}
    assert books.parse_toc("第十一章：甲\n第十二章：乙") == ["甲", "乙"]


def test_parse_toc_keeps_numbers_that_belong_to_titles():
    assert books.parse_toc("第1章：1984\n第2章：Part 2\n第3章：T3") == ["1984", "Part 2", "T3"]
    # Page numbers that go up are stripped; ones that go down aren't pages.
    assert books.parse_toc("1. 開端 3\n2. 轉折 40\n3. 結局 88") == ["開端", "轉折", "結局"]
    assert books.parse_toc("1. 第 3\n2. 第 2\n3. 第 1") == ["第 3", "第 2", "第 1"]


# ---------- phase 1 flow ----------

def test_setup_asks_one_question_at_a_time():
    book, replies = setup_book("《原子習慣》", "James Clear", "不確定欸", "3", "280")
    assert book["title"] == "原子習慣"
    assert replies[0] == "《原子習慣》，好。作者是誰呢？"
    assert replies[1] == books.QUESTIONS["chapter_count"]
    assert replies[2].startswith("我需要一個明確的數字")
    assert book["chapter_count"] == 3 and book["total_pages"] == 280
    assert replies[-1] == books.QUESTIONS["chapters"]


def test_chinese_numbers_for_counts_regression():
    book, _ = setup_book("書", "作者", "二十章", "四百五十頁")
    assert book["chapter_count"] == 20 and book["total_pages"] == 450


def test_pasted_one_line_toc_is_listed_for_confirmation_not_stored_as_one_title():
    line = "、".join(f"第{i}章 測試{i}" for i in range(1, 21))
    book, replies = setup_book("人類大歷史", "哈拉瑞", "20", "450", line, confirm=False)
    assert book["step"] == "confirm_toc" and book["chapters"] == []
    assert "我從目錄整理出 20 章" in replies[-1]
    assert "1. 測試1" in replies[-1] and "20. 測試20" in replies[-1]
    assert "第2章的標題是" not in replies[-1]
    reply = books.answer_setup(book, "對")
    assert book["chapters"] == [f"測試{i}" for i in range(1, 21)]
    assert book["status"] == "planning" and "14 天預覽" in reply


def test_toc_count_mismatch_names_the_missing_chapters():
    toc = "\n".join(f"第{i}章：T{i}" for i in range(1, 21) if i not in (5, 9))
    book, replies = setup_book("書", "作者", "20", "450", toc, confirm=False)
    msg = replies[-1]
    assert "整理出 18 章" in msg and "20 章不一樣（少了 2 章）" in msg
    assert "目錄裡沒有找到：第5章、第9章" in msg
    # She fixes it by pasting again
    full = "\n".join(f"第{i}章：T{i}" for i in range(1, 21))
    msg = books.answer_setup(book, full)
    assert "整理出 20 章" in msg and "不一樣" not in msg
    books.answer_setup(book, "對")
    assert len(book["chapters"]) == 20 and book["status"] == "planning"


def test_missing_chapters_can_be_added_one_at_a_time():
    """G: 18 of 20 numbered chapters pasted; 「第19章：標題」 adds it in place."""
    toc = "\n".join(f"第{i}章：T{i}" for i in range(1, 21) if i not in (5, 19))
    book, _ = setup_book("書", "作者", "20", "450", toc, confirm=False)
    reply = books.answer_setup(book, "第19章：T19")
    assert reply.startswith("補上第19章了") and "少了 1 章" in reply and "第5章" in reply
    reply = books.answer_setup(book, "第五章：T5")
    assert "整理出 20 章" in reply and "不一樣" not in reply
    books.answer_setup(book, "對")
    assert book["chapters"] == [f"T{i}" for i in range(1, 21)]


def test_unnumbered_list_can_be_extended_with_the_next_chapter():
    book, _ = setup_book("書", "作者", "4", "90", "A、B、C", confirm=False)
    assert books.answer_setup(book, "第4章：D").startswith("補上第4章了")
    books.answer_setup(book, "對")
    assert book["chapters"] == ["A", "B", "C", "D"]


def test_toc_unnumbered_mismatch_and_accepting_the_list():
    book, replies = setup_book("書", "作者", "4", "90", "A、B、C", confirm=False)
    assert "少了 1 章" in replies[-1] and "以這 3 章為準" in replies[-1]
    books.answer_setup(book, "對")
    assert book["chapter_count"] == 3 and book["status"] == "planning"


def test_toc_confirmation_edit_one_title_and_correct_count():
    book, _ = setup_book("書", "作者", "3", "90", "第1章：A\n第2章：錯字\n第3章：C", confirm=False)
    reply = books.answer_setup(book, "第2章：B")
    assert reply.startswith("改好了") and book["pending_toc"] == ["A", "B", "C"]
    assert "還不能補第9章" in books.answer_setup(book, "第9章：X")
    reply = books.answer_setup(book, "4")
    assert "少了 1 章" in reply
    books.answer_setup(book, "對")
    assert book["chapters"] == ["A", "B", "C"]


def test_setup_chapter_by_chapter():
    book, replies = setup_book("書", "作者", "3", "90", "第1章：開端", "轉折", "第3章：結局")
    assert replies[-2] == "第3章的標題是？（第3章：___）"
    assert book["chapters"] == ["開端", "轉折", "結局"]
    assert book["status"] == "planning"
    assert replies[-1].endswith(books.PLAN_QUESTION)


def test_one_title_containing_a_comma_is_kept_in_chapter_by_chapter_mode():
    book, _ = setup_book("書", "作者", "3", "90", "第1章：開端", "貨幣、信用與帝國", "結局")
    assert book["chapters"] == ["開端", "貨幣、信用與帝國", "結局"]


def test_first_title_with_a_comma_can_be_kept_as_one_chapter():
    book, replies = setup_book("書", "作者", "3", "90", "貨幣、信用與帝國", confirm=False)
    assert book["step"] == "confirm_toc" and "回答「這是一章」" in replies[-1]
    reply = books.answer_setup(book, "這是一章")
    assert book["chapters"] == ["貨幣、信用與帝國"] and "第2章的標題" in reply
    # A numbered / multi-line paste never offers that option.
    book, replies = setup_book("書", "作者", "3", "90", "第1章 A、第2章 B、第3章 C", confirm=False)
    assert "這是一章" not in replies[-1]


def test_several_chapters_mid_way_are_never_one_title():
    book, replies = setup_book("書", "作者", "3", "90", "第1章：A", "第2章 B、第3章 C", confirm=False)
    assert book["step"] == "confirm_toc" and "整理出 2 章" in replies[-1]


def test_setup_wrong_chapter_number_is_checked_gently():
    book, replies = setup_book("書", "作者", "3", "90", "第1章：A", "第5章：E")
    assert "幫你確認一下" in replies[-1] and book["chapters"] == ["A"]
    book, replies = setup_book("書", "作者", "3", "90", "第1章：A", "第5章：E", "5", "B", "C", "D", "E")
    assert book["chapter_count"] == 5 and book["status"] == "planning"


# ---------- phase 2 ----------

def test_next_day_and_finish():
    book, _ = setup_book("書", "作者", "2", "30", "第1章：A\n第2章：B")
    assert books.next_day(book) == 1
    books.record_pass(book, 1, "講了 A", TODAY)
    assert books.next_day(book) == 2 and book["status"] == "planning"
    books.record_pass(book, 2, "講了 B", TODAY)
    assert books.next_day(book) is None and book["status"] == "finished"
    assert book["finished_on"] == TODAY.isoformat()


def test_current_book_ignores_finished_and_switched():
    a, b = books.new_book(TODAY), books.new_book(TODAY)
    a["status"], b["status"] = "switched", "finished"
    assert books.current_book([a, b]) is None
    c = books.new_book(TODAY)
    assert books.current_book([a, c, b]) is None          # drafts aren't current
    c["status"] = "reading"
    assert books.current_book([a, c, b]) is c


def test_normalize_book_fills_defaults():
    assert books.normalize_book({"title": "x"}) is None
    book = books.normalize_book({"id": "abc", "title": "x", "junk": 1})
    assert book["id"] == "abc" and book["checks"] == {} and "junk" not in book


# ---------- helpers used by the page ----------

def reading_book(chapters=3):
    toc = "\n".join(f"第{i}章：T{i}" for i in range(1, chapters + 1))
    book, _ = setup_book("書", "作者", str(chapters), "140", toc)
    book["status"] = "reading"
    return book


def test_apply_moves_skips_invalid():
    book = reading_book(16)
    applied = books.apply_moves(book["plan"], [
        {"day": 1, "action": "to_next"},
        {"day": "2", "action": "to_next"},       # not an int
        {"day": 14, "action": "to_next"},        # no day 15
        {"day": 3, "action": "explode"},
        "junk",
    ])
    assert applied == 1 and book["plan"][:2] == [[1], [2, 3, 4]]
    assert books.apply_moves(book["plan"], None) == 0


def test_says_finished_reading():
    for text in ("我今天讀完了", "看完了！", "讀好了", "第3天完成了", "我讀到第5章"):
        assert books.says_finished_reading(text), text
    for text in ("這本書在講什麼？", "我還沒開始讀"):
        assert not books.says_finished_reading(text), text


def test_resume_message_after_days_away():
    book = reading_book()
    books.record_pass(book, 1, "講了 T1", date(2026, 9, 18))
    msg = books.resume_message(book, date(2026, 9, 23))
    assert msg.startswith("我們從第2天繼續")
    assert "你去哪" not in msg and "中斷" not in msg
    assert books.resume_message(book, date(2026, 9, 19)).startswith("《書》今天是第2天")


def test_resume_message_mid_setup():
    book, _ = setup_book("書", "作者", "3", "90", "第1章：A")
    assert "第2章的標題" in books.resume_message(book, TODAY)


def test_judge_prompt_knows_today_and_tomorrow():
    book = reading_book()
    prompt = books.judge_prompt(book, 1)
    assert "第1天的範圍是：第1章：T1" in prompt
    assert "明天進到第2天" in prompt and "第2章：T2" in prompt
    books.record_pass(book, 1, "x", TODAY)
    books.record_pass(book, 2, "y", TODAY)
    assert "最後一個閱讀日" in books.judge_prompt(book, 3)
    assert '"passed"' in prompt


def test_final_summary_prompt_quotes_her_words_clipped():
    book = reading_book()
    books.record_pass(book, 1, "習慣像複利" * 100, TODAY)
    prompt = books.final_summary_prompt(book, summary_chars=20)
    assert "不使用 JSON 課程格式" in prompt and "第1天（第1章）她分享：習慣像複利" in prompt
    assert "習慣像複利" * 5 not in prompt
