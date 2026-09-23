"""Every request the app can send must fit the token budget (P0-1)."""
from datetime import date, timedelta

import pytest

from coach import books, core, tokens

TODAY = date(2026, 9, 23)
LONG = "這是一段刻意寫得很長的內容，用來測試最壞的情況會不會超出預算。" * 10


def heavy_log(topic):
    """Worst case for build_history_context: many past sessions with long
    titles, questions and reflections."""
    log = core.empty_log()
    for i in range(30):
        e = core.start_entry(log, TODAY - timedelta(days=30 - i), topic)
        e.update(completed=True, title=LONG[:120], followup_question=LONG[:200], reflection=LONG)
    for i, t in enumerate(core.TOPICS):
        core.start_entry(log, TODAY - timedelta(days=i + 1), t)
    return log


def test_calibration_overestimates_the_real_413_request():
    # The real failing request: old full prompt + kickoff = ~7391 prompt tokens.
    full = open("coach/system_prompt.md", encoding="utf-8").read()
    assert tokens.estimate(full) >= 7391


@pytest.mark.parametrize("topic", [t for t in core.TOPICS if t != "reading"])
def test_lesson_request_fits_for_every_topic(topic):
    log = heavy_log(topic)
    system = core.build_system_prompt(log, topic, TODAY)
    kickoff = [{"role": "user", "content": core.build_kickoff_message(topic, TODAY, "我想了解" + LONG[:96])}]
    total = tokens.estimate_request(system, kickoff, tokens.LESSON_MAX_TOKENS)
    assert total <= tokens.REQUEST_BUDGET, total


@pytest.mark.parametrize("topic", [t for t in core.TOPICS if t != "reading"])
def test_followups_are_trimmed_oldest_first(topic):
    system = core.build_system_prompt(heavy_log(topic), topic, TODAY, followup=True)
    history = []
    for i in range(20):
        history += [{"role": "user", "content": f"問題{i} " + LONG[:100]},
                    {"role": "assistant", "content": f"回答{i} " + LONG}]
    history.append({"role": "user", "content": "最後一個問題"})
    fitted, dropped = tokens.fit_messages(system, history, tokens.CHAT_MAX_TOKENS)
    assert dropped > 0 and fitted[-1]["content"] == "最後一個問題"
    assert fitted == history[dropped:]                      # oldest dropped, order kept
    assert tokens.estimate_request(system, fitted, tokens.CHAT_MAX_TOKENS) <= tokens.REQUEST_BUDGET


def test_a_single_huge_message_is_shortened_not_sent_over_budget():
    system = core.build_system_prompt(core.empty_log(), "cosmos", TODAY, followup=True)
    huge = [{"role": "user", "content": LONG * 20 + "真正的問題在最後"}]
    fitted, _ = tokens.fit_messages(system, huge, tokens.CHAT_MAX_TOKENS)
    assert fitted[0]["content"].endswith("真正的問題在最後")
    assert tokens.estimate_request(system, fitted, tokens.CHAT_MAX_TOKENS) <= tokens.REQUEST_BUDGET


def big_book(chapters=60):
    book = books.new_book(TODAY)
    book.update(title="人類大歷史" * 4, author="哈拉瑞" * 5, chapter_count=chapters, total_pages=900,
                chapters=[f"第{i}章很長很長的標題" + "字" * 40 for i in range(1, chapters + 1)],
                plan=books.allocate(chapters), status="reading")
    return book


def reading_system(task):
    return f"{core.load_system_prompt('reading')}\n\n{task}"


def test_book_judge_adjust_and_chat_fit_even_for_a_huge_book():
    book = big_book()
    msg = [{"role": "user", "content": LONG}]
    for task, max_tokens in [(books.judge_prompt(book, 1), tokens.JSON_MAX_TOKENS),
                             (books.adjust_prompt(book), tokens.JSON_MAX_TOKENS),
                             (books.chat_prompt(book), tokens.CHAT_MAX_TOKENS)]:
        total = tokens.estimate_request(reading_system(task), msg, max_tokens)
        assert total <= tokens.REQUEST_BUDGET, total


def test_final_summary_fits_after_clipping():
    book = big_book()
    for d in range(1, books.DAYS + 1):
        books.record_pass(book, d, LONG * 3, TODAY)
    msg = [{"role": "user", "content": "我全部讀完了。"}]
    fits = [chars for chars in (150, 100, 60, 30, 0)
            if tokens.estimate_request(reading_system(books.final_summary_prompt(book, chars)),
                                       msg, tokens.LESSON_MAX_TOKENS) <= tokens.REQUEST_BUDGET]
    assert fits, "even the most clipped summary prompt is over budget"
