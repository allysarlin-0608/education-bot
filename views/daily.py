from datetime import date

import streamlit as st

import json

from coach import core, lesson_view, llm, reading, style, tokens, ui

log = st.session_state.coach_log


# ============================================================
# Which lesson is on screen (survives page switches and refreshes)
# ============================================================
# Widget state is dropped when she visits another page, so the choices
# live in plain session keys and are copied back into the widgets; they
# are also mirrored into the URL so a refresh keeps them.

def _query_date():
    try:
        return date.fromisoformat(st.query_params.get("date", ""))
    except ValueError:
        return None


if "coach_date" not in st.session_state:
    # A future date in the URL is clamped here, before the URL's topic is
    # filed under it, so the topic isn't lost along with the date.
    st.session_state.coach_date = min(_query_date() or ui.today(), ui.today())
    st.session_state.coach_topics = {}          # date iso -> chosen topic
    if st.query_params.get("topic") in core.TOPICS:
        st.session_state.coach_topics[st.session_state.coach_date.isoformat()] = st.query_params["topic"]


def chat_key():
    return f"{today.isoformat()}|{topic}"


def get_chat():
    """This lesson's chat; rebuilt from the saved entry (lesson and the
    follow-ups after it) when this session doesn't have it yet, so a
    finished lesson is never generated twice."""
    chats = st.session_state.coach_chats
    if chat_key() not in chats:
        entry = core.find_entry(log, today, topic)
        chats[chat_key()] = (
            [{"role": "user", "content": entry.get("kickoff") or core.build_kickoff_message(topic, today)},
             {"role": "assistant", "content": entry["lesson"]}] + entry["followups"]
            if entry and entry.get("lesson") else []
        )
    return chats[chat_key()]


def failed(kind, error, **payload):
    """Remember a failed call so the page can show a friendly message and
    a 重試 button that repeats it (the raw error only goes to the log)."""
    st.session_state.coach_retry = {"kind": kind, "error": error, "key": chat_key(), **payload}
    st.rerun()


def run_kickoff(focus):
    chat = get_chat()
    if chat:        # already generated (e.g. in another tab): never call again
        st.rerun()
    kickoff = core.build_kickoff_message(topic, today, focus)
    chat.append({"role": "user", "content": kickoff})
    with st.spinner("教練正在準備今天的課……"):
        raw, error = llm.ask_raw_json(
            core.build_system_prompt(log, topic, today), chat, max_tokens=tokens.LESSON_MAX_TOKENS,
        )
    lesson = core.parse_lesson(raw) if raw else None
    if lesson is None:
        if raw:
            llm.logger.error("lesson reply was not a usable JSON lesson: %.300r", raw)
        chat.pop()
        failed("kickoff", error or llm.FAILED, focus=focus)
    lesson = core.finalize_lesson(lesson)
    stored = json.dumps(lesson, ensure_ascii=False)
    chat.append({"role": "assistant", "content": stored})
    new_entry = core.start_entry(log, today, topic)
    new_entry["lesson"] = stored
    new_entry["kickoff"] = kickoff             # her whole message, 「我今天特別想了解…」 included
    new_entry["title"] = lesson["topic"]
    new_entry["followup_question"] = lesson["followup_question"]
    ui.save_entry(log, new_entry)
    st.rerun()


def run_followup(text):
    chat = get_chat()
    chat.append({"role": "user", "content": text})
    with st.chat_message("user"):
        st.markdown(text)
    reply, error = llm.stream_reply(
        core.build_system_prompt(log, topic, today, followup=True), chat,
        max_tokens=tokens.CHAT_MAX_TOKENS,
    )
    if error:
        chat.pop()
        failed("followup", error, text=text)
    chat.append({"role": "assistant", "content": core.finalize_reply(reply, lesson=False)})
    entry = core.find_entry(log, today, topic)
    if entry is not None:
        entry["followups"] = chat[2:]          # everything after the lesson
        ui.save_entry(log, entry)
    st.rerun()                                 # show the checked text, not the raw stream


def show_retry():
    """Friendly message + 重試 for the last failed call on this lesson."""
    retry = st.session_state.get("coach_retry")
    if not retry or retry["key"] != chat_key():
        return
    st.warning(retry["error"])
    if st.button("重試", key="coach_retry_button"):
        st.session_state.coach_retry = None
        if retry["kind"] == "kickoff":
            run_kickoff(retry["focus"])
        else:
            run_followup(retry["text"])


# ============================================================
# TOP: navigation, large title, date, stat tiles
# ============================================================
style.nav("today")

# No future dates: lessons "done" in the future would count toward the
# real streak and levels (and a date past max_value makes Streamlit error).
latest = ui.today()
if st.session_state.coach_date > latest:
    st.session_state.coach_date = latest
if "w_date" not in st.session_state or st.session_state.w_date > latest:
    st.session_state.w_date = st.session_state.coach_date
today = st.session_state.w_date

title_col, date_col = st.columns([3, 2], vertical_alignment="bottom")
with title_col:
    style.text("今天" if today == latest else f"{today.month}月{today.day}日", "t-large")
    style.text(f"{today.year}年{today.month}月{today.day}日　{core.weekday_zh(today)}", "t-footnote")
with date_col:
    with st.popover("換日期", icon=":material/calendar_today:", width="stretch"):
        st.date_input("日期", key="w_date", max_value=latest)
today = st.session_state.w_date
st.session_state.coach_date = today

# Same base date as the 紀錄 page (the real today), whatever date is picked.
style.stats([(f"{core.current_streak(log, ui.today())} 天", "連續完成"),
             (f"{len(core.completed_dates(log))} 天", "累計完成")])

if not (bool(st.session_state.api_key) and llm.GROQ_AVAILABLE):
    with st.expander("設定 API key", expanded=not st.session_state.api_key):
        entered_key = st.text_input(
            "Groq API key",
            type="password",
            value=st.session_state.api_key,
            help="也可以設定 GROQ_API_KEY 環境變數或 secret。",
        )
        if entered_key != st.session_state.api_key:
            st.session_state.api_key = entered_key
            st.rerun()
        if not llm.GROQ_AVAILABLE:
            st.caption("缺少套件：請執行 `pip install groq`。")


# ============================================================
# TOPIC PICKER
# ============================================================
scheduled = core.scheduled_topic(today)
topic_keys = list(core.TOPICS)

chosen = st.session_state.coach_topics.get(today.isoformat(), scheduled)
if st.session_state.get("w_topic_date") != today.isoformat() or "w_topic" not in st.session_state:
    st.session_state.w_topic = chosen
    st.session_state.w_topic_date = today.isoformat()
topic = st.selectbox(
    "今天的主題",
    topic_keys,
    key="w_topic",
    format_func=lambda k: core.TOPICS[k] + ("（今日行程）" if k == scheduled else ""),
)
st.session_state.coach_topics[today.isoformat()] = topic
if st.query_params.get("date") != today.isoformat() or st.query_params.get("topic") != topic:
    st.query_params.update(date=today.isoformat(), topic=topic)

if topic == "reading":
    # 看書 is a two-phase book tracker (part 4.3), not a daily lesson.
    reading.render(log, today)
    st.stop()

session_number = core.topic_session_number(log, topic, today)
st.caption(
    f"這是你第 {session_number} 次上「{core.TOPICS[topic]}」的課，"
    f"難度：{core.level_for_session(session_number)}（難度看上課次數，有沒有打勾都算）"
)

entry = core.find_entry(log, today, topic)
chat = get_chat()

if not chat:
    focus = st.text_input(
        "今天有特別想了解的方向嗎？（選填）",
        placeholder="例如：斯多葛學派、區塊鏈、黑洞……",
        max_chars=100,
    )
    show_retry()
    if st.button("開始今天的學習", type="primary", use_container_width=True):
        st.session_state.coach_retry = None
        run_kickoff(focus)
    st.stop()

# ============================================================
# LESSON + CHAT
# ============================================================
focus_said = chat[0]["content"].partition("我今天特別想了解：")[2]
if focus_said:
    style.text(f"你今天想了解：{focus_said}", "t-footnote")
lesson_view.render(chat[1]["content"], key=f"{today.isoformat()}_{topic}")

if len(chat) > 2:
    style.section("追問")
for message in chat[2:]:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if entry is not None:
    style.section("今天的進度")
    done = st.toggle(
        "今天的任務完成了",
        value=entry.get("completed", False),
        help="只做了一部分也算數。",
        key=f"done_{today.isoformat()}_{topic}",
    )
    if done != entry.get("completed", False):
        entry["completed"] = done
        ui.save_entry(log, entry)
        st.rerun()
    if entry.get("completed"):
        st.caption(f"已完成。目前連續完成 {core.current_streak(log, ui.today())} 天。")
    else:
        st.caption("做了一部分也算數，打開就好。")

    with st.expander("我對延伸提問的想法（選填，下次教練會接著聊）"):
        reflection = st.text_area(
            "延伸提問",
            value=entry.get("reflection", ""),
            label_visibility="collapsed",
            key=f"reflection_{today.isoformat()}_{topic}",
        )
        if st.button("儲存想法"):
            entry["reflection"] = reflection.strip()
            if ui.save_entry(log, entry):
                st.toast("存好了。")     # a toast isn't hidden behind the chat input
            else:
                ui.show_pending_error()

show_retry()
prompt = st.chat_input("想追問、回報進度，或聊聊今天的內容……")
if prompt is not None and prompt.strip():
    st.session_state.coach_retry = None
    run_followup(prompt)
