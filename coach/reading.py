"""Reading (part 4.3): the book tracker on the Reading page."""
import streamlit as st

from coach import books, core, llm, place, progress_bar, shelf, tokens, ui

SWITCH_MESSAGE = "OK, let's set up a new book. "
RESTART_MESSAGE = "OK, let's start over. "


def render(log, today):
    store = st.session_state.coach_store
    if store.books_error:
        st.warning(store.books_error)
        return
    # A book being set up or previewed lives only in this session; it is
    # written to the database when she presses 確認進度表.
    book = st.session_state.get("book_draft") or books.current_book(log["books"])
    if book is None:
        _render_bookshelf_start(log, today)
        _render_shelf(log, today)
        return
    if book["status"] == "reading" and today.isoformat() < book["started_on"]:
        # A date before the book started: no progress to show for it.
        st.markdown(f"### {book['title']}")
        st.info(f"You started {book['title']} on {book['started_on']}, so there's no reading for this date yet.")
        return

    chat = _chat(book, today)
    if book["status"] == "reading":
        _render_now_reading(log, book, chat, today)
    else:
        _render_header(book)
    for message in chat:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    reply_spot = st.container()           # a new message and its answer appear here, under the others
    if st.session_state.pop("book_follow", False):
        # pressed "I've finished today's reading" above: go to the coach's question
        n = st.session_state.coach_scroll_n = st.session_state.get("coach_scroll_n", 0) + 1
        with reply_spot:
            st.html(place.follow(n), unsafe_allow_javascript=True)

    if book["status"] == "planning":
        _render_plan_controls(log, book, chat, today)
    _render_other_options(log, book, today)
    _render_shelf(log, today)

    _render_retry(log, book, chat, today)
    # stays at the bottom of the screen (sticky, see style.py); not Streamlit's
    # own bottom bar, which would keep the page scrolled to the end
    with st.container(key="chat_dock"):
        text = st.chat_input(_placeholder(book))
    if text is None or not text.strip():
        return
    st.session_state.book_retry = None
    with reply_spot:
        _handle_message(log, book, chat, text.strip(), today)


def _handle_message(log, book, chat, text, today):
    chat.append({"role": "user", "content": text})
    n = st.session_state.coach_scroll_n = st.session_state.get("coach_scroll_n", 0) + 1
    st.html(place.follow(n), unsafe_allow_javascript=True)      # the page follows her message
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
    greeting (e.g. "Let's pick up from Day X" after a few days away)."""
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
    """Drafts (setup / preview) stay in the session; confirmed books are
    written to storage."""
    book["last_active_on"] = today.isoformat()
    if book["status"] in ("setup", "planning"):
        st.session_state.book_draft = book
        return True
    return ui.save_book(log, book)


def _say(chat, text):
    chat.append({"role": "assistant", "content": text})


def _system(task_prompt):
    """Shared core + the reading module + this call's task."""
    return f"{core.load_system_prompt('reading')}\n\n{task_prompt}"


def _failed(book, chat, error, text):
    """A model call failed: take back her message, remember it, and show a
    friendly note with Retry (the raw error is only in the log)."""
    if chat and chat[-1] == {"role": "user", "content": text}:
        chat.pop()
    st.session_state.book_retry = {"id": book["id"], "text": text, "error": error}
    st.rerun()


def _render_retry(log, book, chat, today):
    retry = st.session_state.get("book_retry")
    if not retry or retry["id"] != book["id"]:
        return
    st.warning(retry["error"])
    if st.button("Retry", key=f"book_retry_{book['id']}"):
        st.session_state.book_retry = None
        _handle_message(log, book, chat, retry["text"], today)


def _placeholder(book):
    if book["status"] == "setup":
        return "Answer the coach's question…"
    if book["status"] == "planning":
        return "What would you like to change? Or just say \"looks good\"…"
    if _awaiting_day(book):
        return "Tell me in your own words what you read today…"
    return "Tell me when you've finished, or talk about the book…"


# ============================================================
# Layout pieces
# ============================================================

def _render_header(book):
    if not book["title"]:
        st.markdown("### A new book")
        return
    st.markdown(f"### {book['title']}")        # (a book being read has its own block: _render_now_reading)


def _render_now_reading(log, book, chat, today):
    """Currently reading: the book, its fourteen days as a thin line, today's
    reading and the button to say it's done."""
    with st.container(key="now_reading"):
        st.html('<div class="bk-label">Currently reading</div>'
                f'<div class="bk-now"><span class="bk-now-title">{shelf._e(book["title"])}</span>'
                + (f'<span class="bk-now-author">{shelf._e(book["author"])}</span>' if book.get("author") else "")
                + "</div>" + shelf.line_html(book, flowing=progress_bar.entering()) + shelf.today_html(book, today))
        _render_reading_controls(log, book, chat, today)
        with st.expander("14-day plan"):
            st.markdown(books.plan_table(book))


def _render_bookshelf_start(log, today):
    """No book being read: one line and the way to start one."""
    with st.container(key="now_reading"):
        st.html('<div class="bk-label">Currently reading</div>')
        finished = [b for b in log["books"] if b["status"] == "finished"]
        last = finished[-1] if finished else None
        if last and not last.get("final_summary"):
            # the wrap-up of the book just finished didn't come through: offer it again
            st.warning(st.session_state.get("book_summary_error") or llm.FAILED)
            if st.button("Retry", key=f"summary_retry_{last['id']}"):
                if _write_final_summary(log, last, today):
                    st.rerun()
        st.markdown("Nothing on the go. We split a book into 14 days together, then each day you read "
                    "your part and come back to talk about it.")
        if st.button("Start a new book", type="primary", use_container_width=True):
            _start_new_book(log, today, intro=None)
            st.rerun()


def _render_shelf(log, today):
    """Books finished or stopped, most recent first; a book finished today
    opens on its own, with its wrap-up."""
    st.markdown("#### Bookshelf")
    just = next((b["id"] for b in shelf.on_shelf(log["books"]) if b.get("finished_on") == today.isoformat()), "")
    st.html(shelf.shelf_html(log["books"], open_id=just))


def _start_new_book(log, today, intro):
    book = books.new_book(today)
    _save(log, book, today)          # a draft: not in log["books"] yet
    opening = books.question_for(book)
    st.session_state[f"book_chat_{book['id']}"] = [
        {"role": "assistant", "content": f"{intro}{opening}" if intro else opening}
    ]
    _set_awaiting(book, None)
    return book


def _render_other_options(log, book, today):
    with st.expander("More options"):
        if book["chapters"] and book["status"] in ("planning", "reading"):
            _render_title_editor(log, book, today)
            st.divider()
        if book["status"] == "reading":
            st.caption("Switching books is completely fine. This one's progress stays on your bookshelf and we set up the new one.")
            if st.button("Stop this book and start another", key=f"switch_{book['id']}"):
                book["status"] = "switched"
                if _save(log, book, today):
                    _start_new_book(log, today, intro=SWITCH_MESSAGE)
                st.rerun()
        else:
            st.caption("The plan isn't confirmed yet, so you can start the setup over at any time.")
            if st.button("Start the setup over", key=f"restart_{book['id']}"):
                st.session_state.book_draft = None
                _start_new_book(log, today, intro=RESTART_MESSAGE)
                st.rerun()


def _render_title_editor(log, book, today):
    st.markdown("**Rename a chapter**")
    number = st.selectbox(
        "Chapter", list(range(1, len(book["chapters"]) + 1)),
        format_func=lambda n: f"Chapter {n}: {book['chapters'][n - 1]}",
        key=f"edit_ch_{book['id']}",
    )
    new_title = st.text_input("New title", key=f"edit_title_{book['id']}_{number}",
                              value=book["chapters"][number - 1])
    if st.button("Save title", key=f"edit_save_{book['id']}") and new_title.strip():
        book["chapters"][number - 1] = new_title.strip()
        if _save(log, book, today):
            chat = _chat(book, today)
            if book["status"] == "planning":
                _say(chat, f"Done: Chapter {number} is now \"{new_title.strip()}\". The updated plan:\n\n{books.plan_table(book)}")
            else:
                _say(chat, f"Done: Chapter {number} is now \"{new_title.strip()}\".")
        st.rerun()


# ============================================================
# Phase 1: setup
# ============================================================

def _handle_setup(log, book, chat, text, today):
    _say(chat, books.answer_setup(book, text))
    _save(log, book, today)
    st.rerun()


# ============================================================
# Phase 1: adjusting and confirming the plan
# ============================================================

def _render_plan_controls(log, book, chat, today):
    with st.expander("Adjust a day yourself"):
        day = st.selectbox(
            "Day", list(range(1, books.DAYS)), format_func=lambda d: f"Day {d}",
            key=f"adjust_day_{book['id']}",
        )
        col1, col2 = st.columns(2)
        if col1.button(f"Lighter: move its last chapter to Day {day + 1}", use_container_width=True):
            _apply_manual_move(log, book, chat, today, books.move_last_to_next, day,
                               f"I moved Day {day}'s last chapter to Day {day + 1}.")
        if col2.button(f"Heavier: bring over Day {day + 1}'s first chapter", use_container_width=True):
            _apply_manual_move(log, book, chat, today, books.move_first_from_next, day,
                               f"I moved Day {day + 1}'s first chapter to Day {day}.")
    if st.button("Confirm the plan", type="primary", use_container_width=True):
        _confirm_plan(log, book, chat, today)
        st.rerun()


def _apply_manual_move(log, book, chat, today, move, day, done_text):
    if not move(book["plan"], day):
        st.toast("There's no chapter to move on that day.")
        return
    _say(chat, f"OK. {done_text} The updated plan:\n\n{books.plan_table(book)}")
    _save(log, book, today)
    st.rerun()


def _confirm_plan(log, book, chat, today):
    """The first time the book is written to storage. The day she
    confirms is day 1."""
    book["status"] = "reading"
    book["started_on"] = today.isoformat()
    if book not in log["books"]:
        log["books"].append(book)
    if not _save(log, book, today):
        # Not saved: stay a draft so nothing is lost and she can retry.
        book["status"] = "planning"
        log["books"].remove(book)
        return
    st.session_state.book_draft = None
    _say(chat, books.PLAN_CONFIRMED)


def _handle_planning(log, book, chat, text, today):
    if books.is_yes(text):
        _confirm_plan(log, book, chat, today)
        st.rerun()
    with st.spinner("Adjusting the plan…"):
        data, error = llm.ask_json(_system(books.adjust_prompt(book)), [{"role": "user", "content": text}])
    if error:
        _failed(book, chat, error, text)
    applied = books.apply_moves(book["plan"], data.get("moves"))
    reply = str(data.get("reply") or "").strip()
    if applied:
        reply = f"{reply}\n\nThe updated plan:\n\n{books.plan_table(book)}".strip()
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
        if st.button("Not now, maybe later", key=f"cancel_{book['id']}"):
            _set_awaiting(book, None)
            _say(chat, "No problem. Tell me when you're ready.")
            st.rerun()
    elif day and books.is_open(book, day, today):      # (otherwise the line above says when it opens)
        if st.button("I've finished today's reading", type="primary", use_container_width=True):
            chat.append({"role": "user", "content": f"I've read Day {day}."})
            _start_check(book, chat, day)
            st.session_state.book_follow = True
            st.rerun()


def _start_check(book, chat, day):
    _set_awaiting(book, day)
    _say(chat, books.check_start_message(book, day))


def _handle_reading(log, book, chat, text, today):
    day = _awaiting_day(book)
    if day is None and books.says_finished_reading(text):
        day = books.next_day(book)
        if not books.is_open(book, day, today):
            _say(chat, books.not_open_message(book, day))
            st.rerun()
        # A short "讀完了" gets the reminder and the invitation to share;
        # a longer message already is her sharing, so check it right away.
        if len(text) < 40:
            _start_check(book, chat, day)
            st.rerun()
    if day is None:
        reply, error = llm.stream_reply(_system(books.chat_prompt(book)), chat[-12:],
                                        max_tokens=tokens.CHAT_MAX_TOKENS)
        if error:
            _failed(book, chat, error, text)
        _say(chat, core.finalize_reply(reply, lesson=False, topic="reading"))
        st.rerun()

    with st.spinner("The coach is reading what you shared…"):
        data, error = llm.ask_json(_system(books.judge_prompt(book, day)),
                                   [{"role": "user", "content": text}])
    if error:
        _set_awaiting(book, day)
        _failed(book, chat, error, text)
    reply = str(data.get("reply") or "").strip()
    if data.get("passed") is not True:
        # Not marked, not advanced; her next message is checked again.
        _set_awaiting(book, day)
        _say(chat, reply or "Have another look and come back to tell me about it; we'll just check again.")
        st.rerun()

    books.record_pass(book, day, text, today)
    _set_awaiting(book, None)
    _say(chat, reply or "That counts for today.")
    _record_learning_entry(log, book, today)
    _save(log, book, today)
    if book["status"] == "finished":
        _write_final_summary(log, book, today)
    st.rerun()


def _write_final_summary(log, book, today):
    """Stream the end-of-book wrap-up. Her daily notes are clipped until
    the request fits the token budget. On failure the book stays
    finished and the bookshelf view offers Retry."""
    messages = [{"role": "user", "content": f"I've finished all of {book['title']}."}]
    for chars in (150, 100, 60, 30, 0):
        system = _system(books.final_summary_prompt(book, summary_chars=chars))
        if tokens.estimate_request(system, messages, tokens.LESSON_MAX_TOKENS) <= tokens.REQUEST_BUDGET:
            break
    summary, error = llm.stream_reply(system, messages, max_tokens=tokens.LESSON_MAX_TOKENS)
    if error:
        st.session_state.book_summary_error = error
        return False
    st.session_state.book_summary_error = None
    book["final_summary"] = summary
    _save(log, book, today)
    return True


def _record_learning_entry(log, book, today):
    """Mirror today's passed days into the learning log, so streaks and the
    record page count reading days like any other topic."""
    days = sorted(int(d) for d, c in book["checks"].items() if c["passed_on"] == today.isoformat())
    span = f"Day {days[0]}" if len(days) == 1 else f"Days {days[0]}–{days[-1]}"
    chapters = [c for d in days for c in book["plan"][d - 1]]
    entry = core.start_entry(log, today, "reading")
    entry["title"] = f"{book['title']}, {span}: {books.chapter_range(chapters)}"
    entry["completed"] = True
    entry["reflection"] = "\n\n".join(book["checks"][str(d)]["summary"] for d in days)
    ui.save_entry(log, entry)
