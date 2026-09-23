from datetime import date

import streamlit as st

from coach import core, llm, reading, tokens, ui

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
    st.session_state.coach_date = _query_date() or ui.today()
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
            [{"role": "user", "content": core.build_kickoff_message(topic, today)},
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
    with st.chat_message("user"):
        st.markdown(kickoff)
    lesson, error = llm.stream_reply(
        core.build_system_prompt(log, topic, today), chat, max_tokens=tokens.LESSON_MAX_TOKENS,
    )
    if error:
        chat.pop()
        failed("kickoff", error, focus=focus)
    chat.append({"role": "assistant", "content": lesson})
    new_entry = core.start_entry(log, today, topic)
    new_entry["lesson"] = lesson
    new_entry["title"] = core.extract_section(lesson, "今日主題")
    new_entry["followup_question"] = core.extract_section(lesson, "延伸提問")
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
    chat.append({"role": "assistant", "content": reply})
    entry = core.find_entry(log, today, topic)
    if entry is not None:
        entry["followups"] = chat[2:]          # everything after the lesson
        ui.save_entry(log, entry)


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
# SIDEBAR
# ============================================================
with st.sidebar:
    st.markdown("### ◎ 每日學習教練")
    st.caption("每天 15 到 20 分鐘，一個知識點、一個小任務。")

    client_ready = bool(st.session_state.api_key) and llm.GROQ_AVAILABLE
    if not client_ready:
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

    if "w_date" not in st.session_state:
        st.session_state.w_date = st.session_state.coach_date
    today = st.date_input("日期", key="w_date")
    st.session_state.coach_date = today

    st.divider()
    streak = core.current_streak(log, today)
    col_a, col_b = st.columns(2)
    col_a.metric("連續完成", f"{streak} 天")
    col_b.metric("累計完成", f"{len(core.completed_dates(log))} 天")
    st.page_link("views/records.py", label="看完整學習紀錄", icon=":material/history:")


# ============================================================
# TOPIC PICKER
# ============================================================
scheduled = core.scheduled_topic(today)
topic_keys = list(core.TOPICS)
st.markdown(f"## {today.isoformat()}　{core.weekday_zh(today)}")

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
    f"這是你第 {session_number} 次接觸「{core.TOPICS[topic]}」，"
    f"難度：{core.level_for_session(session_number)}"
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
for message in chat:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if entry is not None:
    st.divider()
    done = st.checkbox(
        "✅ 今天的任務完成了",
        value=entry.get("completed", False),
        help="只做了一部分也算數。",
        key=f"done_{today.isoformat()}_{topic}",
    )
    if done != entry.get("completed", False):
        entry["completed"] = done
        ui.save_entry(log, entry)
        st.rerun()
    if entry.get("completed"):
        st.caption(f"已打勾。目前連續完成 {core.current_streak(log, today)} 天。")
    else:
        st.caption("做了一部分也算數，打勾就好。")

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
                st.success("存好了。")
            else:
                ui.show_pending_error()

show_retry()
prompt = st.chat_input("想追問、回報進度，或聊聊今天的內容……")
if prompt is not None and prompt.strip():
    st.session_state.coach_retry = None
    run_followup(prompt)
