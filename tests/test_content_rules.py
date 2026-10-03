"""B / C / I / J: prompt rules and the checks applied to every reply."""
from datetime import date

from coach import core

TODAY = date(2026, 9, 27)
CLOSE = core.CLOSING_LINE

LESSON_C = (   # the reported 自由主題 lesson: pick 3 stocks/coins, no disclaimer
    "【今日主題】：自由主題 — 機率與投資（入門）\n【核心概念】：……\n【具體例子】：……\n"
    "【今日任務】：挑 3 支股票或幣，算平均報酬，選出最高的那一支。\n"
    "【延伸提問】：……\n【小提醒】：……\n" + CLOSE
)
LESSON_I = (   # the reported investing lesson: disclaimer after the closing line
    "【今日主題】：本益比（入門）\n【核心概念】：本益比……\n【小提醒】：……\n" + CLOSE +
    "\n\n本內容為教育性質，不構成投資建議。"
)


def test_investing_lesson_without_disclaimer_gets_one_before_the_closing_line():
    out = core.finalize_reply(LESSON_C, lesson=True, topic="investing")
    assert core.DISCLAIMER in out
    assert out.endswith(CLOSE) and out.count(CLOSE) == 1
    assert out.index(core.DISCLAIMER) < out.index(CLOSE)


def test_closing_line_is_always_last_even_if_the_model_put_the_disclaimer_after_it():
    out = core.finalize_reply(LESSON_I, lesson=True, topic="investing")
    assert out.endswith(CLOSE) and out.count(CLOSE) == 1
    assert "不構成投資建議" in out and core.DISCLAIMER not in out   # kept, not duplicated


def test_non_investing_lesson_is_untouched_apart_from_the_closing_line():
    lesson = "【今日主題】：棉與聚酯（入門）\n【核心概念】：棉吸濕但乾得慢。\n" + CLOSE
    assert core.finalize_reply(lesson, lesson=True) == lesson
    missing = "【今日主題】：棉與聚酯（入門）"
    assert core.finalize_reply(missing, lesson=True).endswith(CLOSE)


def test_followups_get_the_disclaimer_but_no_closing_line():
    out = core.finalize_reply("可以看看這支 ETF 的殖利率。", lesson=False, topic="investing")
    assert out.endswith(core.DISCLAIMER) and CLOSE not in out
    assert core.finalize_reply("棉比較吸汗。", lesson=False) == "棉比較吸汗。"


def test_everyday_use_of_the_word_investment_is_not_flagged():
    assert core.finalize_reply("把時間投資在基本功上。", lesson=False, topic="investing") == "把時間投資在基本功上。"
    assert core.finalize_reply("她成立了一個教育基金會。", lesson=False, topic="investing") == "她成立了一個教育基金會。"
    assert core.DISCLAIMER in core.finalize_reply("指數型基金的費用比較低。", lesson=False, topic="investing")


def test_prompt_has_fact_and_investing_rules_for_every_topic():
    for topic in core.TOPICS:
        prompt = core.load_system_prompt(topic)
        assert "只寫確定正確的事實" in prompt
        assert "不論哪個主題" in prompt and "not investment advice" in prompt
        assert "延續今天的核心概念" in prompt
        assert "送出前逐項檢查" in prompt


def test_topic_modules_state_the_facts_that_were_wrong():
    assert "棉吸濕性好，但乾得慢" in core.load_system_prompt("fashion")
    canvas = core.load_system_prompt("business")
    assert "Unfair Advantage" in canvas and "Customer Segments" in canvas and "Key Assumptions" in canvas
    philosophy = core.load_system_prompt("philosophy")
    assert "最多人" in philosophy and "期望報酬" in philosophy
    jewelry = core.load_system_prompt("jewelry")
    assert "18K含金75%" in jewelry and "白金" in jewelry and "免責聲明" in jewelry


def test_fashion_jewelry_and_general_topics_stay_in_their_lanes():
    assert "珠寶在星期五" in core.load_system_prompt("fashion")
    assert "衣服與穿搭在星期一" in core.load_system_prompt("jewelry")
    general = core.load_system_prompt("free")
    assert "4.7 通識" in general and "不要講時尚、珠寶、哲學、天文學、商業、投資本身的內容" in general


# ---------- English lessons ----------

EN_LESSON = (
    "【Topic】：What Astronomers Study — Beginner\n"
    "【Key Idea】：Astronomy studies everything beyond Earth's atmosphere.\n"
    "【Vocabulary】：\n| Word | Meaning | Example |\n|---|---|---|\n| orbit | the path around a star | Earth orbits the Sun. |\n"
    "【Question to Explore】：How could we measure a star's distance?\n"
    "【Note】：One idea is enough today.\n" + CLOSE
)


def test_english_titles_are_found_by_either_name():
    for name in ("Question to Explore", "延伸提問"):
        assert core.extract_section(EN_LESSON, name) == "How could we measure a star's distance?"
    assert core.extract_section(EN_LESSON, "Topic").startswith("What Astronomers Study")
    assert "| orbit | the path around a star |" in core.extract_section(EN_LESSON, "Vocabulary")


def test_old_chinese_lessons_still_parse():
    old = "【延伸提問】：哪些是你能控制的？\n【小提醒】：……\n完成後記得打勾，連續完成比完美更重要。"
    for name in ("Question to Explore", "延伸提問"):
        assert core.extract_section(old, name) == "哪些是你能控制的？"
    assert core.extract_section(old, "小提醒") == "……"


def test_english_investing_words_get_the_english_disclaimer():
    lesson = EN_LESSON.replace("Astronomy studies", "A stock is a small piece of a company; astronomy studies")
    out = core.finalize_reply(lesson, lesson=True, topic="investing")
    assert core.DISCLAIMER in out and out.endswith(CLOSE)
    assert "not investment advice" in core.DISCLAIMER
    assert not any("\u4e00" <= c <= "\u9fff" for c in core.DISCLAIMER + CLOSE)   # no Chinese
    assert core.DISCLAIMER in core.finalize_reply("Index funds usually cost less.", lesson=False, topic="investing")


def test_an_english_disclaimer_from_the_model_is_not_doubled():
    reply = "Bitcoin has a fixed supply. This is for education only and not investment advice."
    assert core.finalize_reply(reply, lesson=False, topic="investing") == reply


def test_everyday_english_is_not_mistaken_for_investing():
    for text in ("Share your thoughts next time.", "Build a portfolio of your design work.",
                 "Invest time in practice."):
        assert core.finalize_reply(text, lesson=False) == text, text


def test_prompt_asks_for_english_only_and_an_english_vocabulary_table():
    prompt = core.load_system_prompt("cosmos")
    assert "課程全部用英文寫，不要出現中文" in prompt and "photosynthesis" not in prompt
    assert "【Vocabulary】" in prompt and "Word｜Meaning" in prompt and "Example" in prompt
    assert core.CLOSING_LINE in prompt
    followup = core.build_system_prompt(core.empty_log(), "cosmos", date(2026, 9, 24), followup=True)
    assert "只用英文" in followup


def test_the_disclaimer_is_only_for_the_investing_subject():
    gold = ("【Key Idea】 Gold keeps its value, and some people buy stocks of mining companies.\n\n"
            "※ For education only — this is not investment advice.\n\n" + CLOSE)
    for topic in ("jewelry", "fashion", "business", "free", "reading"):
        out = core.finalize_reply(gold, lesson=True, topic=topic)
        assert "not investment advice" not in out and core.DISCLAIMER not in out, topic
        assert out.endswith(CLOSE) and "Gold keeps its value" in out
    assert core.DISCLAIMER not in core.finalize_reply("Index funds usually cost less.", lesson=False, topic="jewelry")
    assert "not investment advice" in core.finalize_reply(gold, lesson=True, topic="investing")


def test_the_note_only_credits_what_she_really_did():
    """1.5: the Note never praises something she hasn't done (the prompt's rule)."""
    from pathlib import Path
    prompt = (Path(__file__).resolve().parents[1] / "coach" / "prompts" / "core.md").read_text(encoding="utf-8")
    note = next(line for line in prompt.splitlines() if line.startswith("【Note】"))
    assert "只肯定學習紀錄裡她真的做過的事" in note and "不能說成她做過" in note
    assert "今天的任務和例子不能說成她做過" in note and "you've already" in note           # today's task is never treated as done


def test_a_note_claiming_what_she_has_not_done_is_replaced_by_a_true_one():
    """Issue 2: "You've already gathered…" about today's task never reaches her."""
    from coach import core
    lesson = ("【Topic】: Fibres\n\n【Today's Task】: Look at three labels.\n\n"
              "【Note】: You've already gathered the fibre info from three pieces of clothing — great work!\n\n"
              + core.CLOSING_LINE)
    fixed = core.truthful_note(lesson, "Your first lesson in Fashion & Clothing. One clear idea is enough for today.")
    assert "gathered" not in fixed and "Your first lesson in Fashion" in fixed and fixed.endswith(core.CLOSING_LINE)
    assert "Look at three labels." in fixed
    fine = lesson.replace("You've already gathered the fibre info from three pieces of clothing — great work!",
                          "Fibre labels are a quick way to start.")
    assert core.truthful_note(fine, "x") == fine
    assert core.truthful_note(lesson.replace("You've already gathered", "**You gathered"), "F").count("F") >= 1
    log = {"entries": [{"date": "2026-10-02", "topic": "fashion", "completed": False,
                        "lessons": [{"n": 1, "completed": True}]}]}
    from datetime import date
    assert core.note_fact(log, "fashion", date(2026, 10, 3), 2) == \
        "Lesson 2 of Fashion & Clothing, building on the 1 you've passed so far."
