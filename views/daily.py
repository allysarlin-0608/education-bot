import streamlit as st

from coach import core, llm, reading, ui

log = st.session_state.coach_log


# ============================================================
# SIDEBAR
# ============================================================
today_default = ui.today()

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

    today = st.date_input("日期", value=today_default)

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

topic = st.selectbox(
    "今天的主題",
    topic_keys,
    index=topic_keys.index(scheduled),
    format_func=lambda k: core.TOPICS[k] + ("（今日行程）" if k == scheduled else ""),
)
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
active_key = (today.isoformat(), topic)

# Switching date/topic: reload that day's saved lesson (if any) into the chat.
if st.session_state.coach_active != active_key:
    st.session_state.coach_active = active_key
    st.session_state.coach_messages = []
    if entry and entry.get("lesson"):
        st.session_state.coach_messages = [
            {"role": "user", "content": core.build_kickoff_message(topic, today)},
            {"role": "assistant", "content": entry["lesson"]},
        ]

if not st.session_state.coach_messages:
    focus = st.text_input(
        "今天有特別想了解的方向嗎？（選填）",
        placeholder="例如：斯多葛學派、區塊鏈、黑洞……",
    )
    if st.button("開始今天的學習", type="primary", use_container_width=True):
        kickoff = core.build_kickoff_message(topic, today, focus)
        st.session_state.coach_messages.append({"role": "user", "content": kickoff})
        with st.chat_message("user"):
            st.markdown(kickoff)
        lesson = llm.stream_reply(core.build_system_prompt(log, topic, today), st.session_state.coach_messages)
        if lesson:
            st.session_state.coach_messages.append({"role": "assistant", "content": lesson})
            entry = core.start_entry(log, today, topic)
            entry["lesson"] = lesson
            entry["title"] = core.extract_section(lesson, "今日主題")
            entry["followup_question"] = core.extract_section(lesson, "延伸提問")
            ui.save_entry(log, entry)
            st.rerun()
        else:
            st.session_state.coach_messages.pop()
    st.stop()

# ============================================================
# LESSON + CHAT
# ============================================================
for message in st.session_state.coach_messages:
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

prompt = st.chat_input("想追問、回報進度，或聊聊今天的內容……")
if prompt is not None and prompt.strip():
    st.session_state.coach_messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    reply = llm.stream_reply(core.build_system_prompt(log, topic, today, followup=True), st.session_state.coach_messages)
    if reply:
        st.session_state.coach_messages.append({"role": "assistant", "content": reply})
    else:
        st.session_state.coach_messages.pop()
