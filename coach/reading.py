"""看書 (part 4.3): the book tracker shown on the lesson page on 看書 days."""
import streamlit as st

from coach import books, core, llm, ui

TOC_RETRY = (
    "這段文字我沒辦法整理出章節，可以再貼一次，"
    "或是一章一章告訴我也可以，從「第1章：___」開始。"
)
SWITCH_MESSAGE = "好，我們來設定新的一本。"


def render(log, today):
    store = st.session_state.coach_store
    if store.books_error:
        st.warning(store.books_error)
        return
    book = books.current_book(log["books"])
    if book is None:
        _render_bookshelf_start(log, today)
        return

    chat = _chat(book, today)
    _render_header(book)
    for message in chat:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if book["status"] == "planning":
        _render_plan_controls(log, book, chat, today)
    elif book["status"] == "reading":
        _render_reading_controls(log, book, chat, today)
    _render_other_options(log, book, today)

    text = st.chat_input(_placeholder(book))
    if text is None or not text.strip():
        return
    text = text.strip()
    chat.append({"role": "user", "content": text})
    with st.chat_message("user"):
        st.markdown(text)
    if book["status"] == "setup":
        _handle_setup(log, book, chat, text, today)
    elif book["status"] == "planning":
        _handle_planning(log, book, chat, text, today)
    else:
        _handle_reading(log, book, chat, text, today)


# ============================================================
# State helpers
# ============================================================

def _chat(book, today):
    """This session's conversation about the book, opened with the right
    greeting (e.g. 我們從第X天繼續 after a few days away)."""
    key = f"book_chat_{book['id']}"
    if key not in st.session_state:
        st.session_state[key] = [
            {"role": "assistant", "content": books.resume_message(book, today)}
        ]
    return st.session_state[key]


def _awaiting_day(book):
    awaiting = st.session_state.get("book_awaiting")
    if awaiting and awaiting["id"] == book["id"]:
        return awaiting["day"]
    return None


def _set_awaiting(book, day):
    st.session_state.book_awaiting = {"id": book["id"], "day": day} if day else None


def _save(log, book, today):
    book["last_active_on"] = today.isoformat()
    ui.save_book(log, book)


def _say(chat, text):
    chat.append({"role": "assistant", "content": text})


def _placeholder(book):
    if book["status"] == "setup":
        return "回答教練的問題……"
    if book["status"] == "planning":
        return "想怎麼調整？或跟我說「可以」……"
    if _awaiting_day(book):
        return "用你自己的話說說今天讀到的內容……"
    return "讀完了跟我說一聲，或聊聊這本書……"


# ============================================================
# Layout pieces
# ============================================================

def _render_header(book):
    if not book["title"]:
        st.markdown("#### 看書：新的一本書")
        return
    st.markdown(f"#### 看書：《{book['title']}》")
    if book["status"] == "reading":
        reading_days = [d for d in range(1, books.DAYS + 1) if book["plan"][d - 1]]
        done = len([d for d in reading_days if str(d) in book["checks"]])
        st.progress(done / len(reading_days), text=f"已確認 {done} / {len(reading_days)} 個閱讀日")
        with st.expander("14 天進度表"):
            st.markdown(books.plan_table(book))


def _render_bookshelf_start(log, today):
    finished = [b for b in log["books"] if b["status"] == "finished"]
    last = finished[-1] if finished else None
    if last:
        st.markdown(f"#### 看書：《{last['title']}》讀完了")
        if last.get("final_summary"):
            with st.chat_message("assistant"):
                st.markdown(last["final_summary"])
        label = "開始規劃下一本書"
    else:
        st.markdown("#### 看書")
        st.markdown(
            "看書用的是 14 天的進度追蹤：先一起把一本書分成 14 天，"
            "之後每天讀完指定範圍，回來聊聊讀到的內容。"
        )
        label = "開始一本新書"
    if st.button(label, type="primary", use_container_width=True):
        _start_new_book(log, today, intro=None)
        st.rerun()


def _start_new_book(log, today, intro):
    book = books.new_book(today)
    log["books"].append(book)
    _save(log, book, today)
    opening = books.question_for(book)
    st.session_state[f"book_chat_{book['id']}"] = [
        {"role": "assistant", "content": f"{intro}{opening}" if intro else opening}
    ]
    _set_awaiting(book, None)
    return book


def _render_other_options(log, book, today):
    with st.expander("其他選項"):
        st.caption("想換一本書也完全沒問題，我們直接設定新的一本就好。")
        if st.button("換一本書", key=f"switch_{book['id']}"):
            book["status"] = "switched"
            _save(log, book, today)
            _start_new_book(log, today, intro=SWITCH_MESSAGE)
            st.rerun()


# ============================================================
# Phase 1: setup
# ============================================================

def _handle_setup(log, book, chat, text, today):
    reply, needs_toc_help = books.answer_setup(book, text)
    if needs_toc_help:
        with st.spinner("整理目錄中……"):
            data, error = llm.ask_json(
                books.toc_prompt(book["chapter_count"]),
                [{"role": "user", "content": text}],
            )
        titles = data.get("chapters") if data else None
        if isinstance(titles, list) and titles and all(isinstance(t, str) for t in titles):
            reply = books.apply_toc(book, [t.strip() for t in titles])
        else:
            reply = error or TOC_RETRY
    _say(chat, reply)
    _save(log, book, today)
    st.rerun()


# ============================================================
# Phase 1: adjusting and confirming the plan
# ============================================================

def _render_plan_controls(log, book, chat, today):
    with st.expander("自己微調某一天的份量"):
        day = st.selectbox(
            "哪一天", list(range(1, books.DAYS)), format_func=lambda d: f"第{d}天",
            key=f"adjust_day_{book['id']}",
        )
        col1, col2 = st.columns(2)
        if col1.button(f"減輕：最後一章移到第{day + 1}天", use_container_width=True):
            _apply_manual_move(log, book, chat, today, books.move_last_to_next, day,
                               f"把第{day}天的最後一章移到第{day + 1}天了。")
        if col2.button(f"加重：把第{day + 1}天第一章移過來", use_container_width=True):
            _apply_manual_move(log, book, chat, today, books.move_first_from_next, day,
                               f"把第{day + 1}天的第一章移到第{day}天了。")
    if st.button("就這樣，開始讀吧", type="primary", use_container_width=True):
        _confirm_plan(log, book, chat, today)
        st.rerun()


def _apply_manual_move(log, book, chat, today, move, day, done_text):
    if not move(book["plan"], day):
        st.toast("那一天沒有章節可以移動。")
        return
    _say(chat, f"好，{done_text}更新後的進度表：\n\n{books.plan_table(book)}")
    _save(log, book, today)
    st.rerun()


def _confirm_plan(log, book, chat, today):
    book["status"] = "reading"
    _say(chat, books.PLAN_CONFIRMED)
    _save(log, book, today)


def _handle_planning(log, book, chat, text, today):
    if books.is_yes(text):
        _confirm_plan(log, book, chat, today)
        st.rerun()
    with st.spinner("調整進度表中……"):
        data, error = llm.ask_json(books.adjust_prompt(book), [{"role": "user", "content": text}])
    if error:
        _say(chat, error)
        st.rerun()
    applied = books.apply_moves(book["plan"], data.get("moves"))
    reply = str(data.get("reply") or "").strip()
    if applied:
        reply = f"{reply}\n\n更新後的進度表：\n\n{books.plan_table(book)}".strip()
    if data.get("confirmed") is True:
        if reply:
            _say(chat, reply)
        _confirm_plan(log, book, chat, today)
    else:
        _say(chat, reply or books.PLAN_QUESTION)
        _save(log, book, today)
    st.rerun()


# ============================================================
# Phase 2: daily checks
# ============================================================

def _render_reading_controls(log, book, chat, today):
    awaiting = _awaiting_day(book)
    day = books.next_day(book)
    if awaiting:
        if st.button("先不確認了，晚點再說", key=f"cancel_{book['id']}"):
            _set_awaiting(book, None)
            _say(chat, "沒問題，準備好了再跟我說。")
            st.rerun()
    elif day:
        if st.button(f"我讀完第{day}天的範圍了", type="primary", use_container_width=True):
            chat.append({"role": "user", "content": f"我讀完第{day}天的範圍了"})
            _start_check(book, chat, day)
            st.rerun()


def _start_check(book, chat, day):
    _set_awaiting(book, day)
    _say(chat, books.check_start_message(book, day))


def _handle_reading(log, book, chat, text, today):
    day = _awaiting_day(book)
    if day is None and books.says_finished_reading(text):
        day = books.next_day(book)
        # A short "讀完了" gets the reminder and the invitation to share;
        # a longer message already is her sharing, so check it right away.
        if len(text) < 40:
            _start_check(book, chat, day)
            st.rerun()
    if day is None:
        reply = llm.stream_reply(books.chat_prompt(book), chat[-12:])
        if reply:
            _say(chat, reply)
        else:
            chat.pop()
        return

    with st.spinner("教練正在讀你的分享……"):
        data, error = llm.ask_json(books.judge_prompt(book, day), [{"role": "user", "content": text}])
    if error:
        _say(chat, error)
        st.rerun()
    reply = str(data.get("reply") or "").strip()
    if data.get("passed") is not True:
        # Not marked, not advanced; her next message is checked again.
        _set_awaiting(book, day)
        _say(chat, reply or "等你確認過再回來跟我聊聊，我們再確認一次就好。")
        st.rerun()

    books.record_pass(book, day, text, today)
    _set_awaiting(book, None)
    _say(chat, reply or "今天算完成了。")
    _record_learning_entry(log, book, today)
    _save(log, book, today)
    if book["status"] == "finished":
        summary = llm.stream_reply(
            books.final_summary_prompt(book),
            [{"role": "user", "content": f"我把《{book['title']}》全部讀完了。"}],
        )
        if summary:
            book["final_summary"] = summary
            _save(log, book, today)
    st.rerun()


def _record_learning_entry(log, book, today):
    """Mirror today's passed days into the learning log, so streaks and the
    record page count reading days like any other topic."""
    days = sorted(int(d) for d, c in book["checks"].items() if c["passed_on"] == today.isoformat())
    span = f"第{days[0]}天" if len(days) == 1 else f"第{days[0]}–{days[-1]}天"
    chapters = [c for d in days for c in book["plan"][d - 1]]
    entry = core.start_entry(log, today, "reading")
    entry["title"] = f"《{book['title']}》{span}：{books.chapter_range(chapters)}"
    entry["completed"] = True
    entry["reflection"] = "\n\n".join(book["checks"][str(d)]["summary"] for d in days)
    ui.save_entry(log, entry)
