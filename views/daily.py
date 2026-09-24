from datetime import date

import streamlit as st

from coach import core, curriculum, lesson_view, llm, tokens, ui

log = st.session_state.coach_log


# ============================================================
# Which day is on screen (survives page switches and refreshes)
# ============================================================
# Widget state is dropped when she visits another page, so the date lives
# in a plain session key and is copied back into the widget; it is also
# mirrored into the URL so a refresh keeps it. The topic is always the
# one scheduled for that day.

def _query_date():
    try:
        return date.fromisoformat(st.query_params.get("date", ""))
    except ValueError:
        return None


if "coach_date" not in st.session_state:
    st.session_state.coach_date = _query_date() or ui.today()


def chat_key(slot):
    return f"{today.isoformat()}|{topic}|{slot['n']}"


def get_chat(slot):
    """This lesson's chat; rebuilt from the saved lesson (and the follow-ups
    after it) when this session doesn't have it yet, so a lesson is never
    generated twice."""
    chats = st.session_state.coach_chats
    if chat_key(slot) not in chats:
        chats[chat_key(slot)] = (
            [{"role": "user", "content": slot["kickoff"] or core.build_kickoff_message(topic, today, slot=slot)},
             {"role": "assistant", "content": slot["lesson"]}] + slot["followups"]
            if slot.get("lesson") else []
        )
    return chats[chat_key(slot)]


def day_entry():
    """Today's entry with its lessons fixed; created when the first lesson
    starts, so an untouched day doesn't reserve lessons."""
    entry = core.start_entry(log, today, topic)
    if not entry["lessons"]:
        entry["lessons"] = [dict(s) for s in plan]
    return entry


def failed(kind, error, slot, **payload):
    """Remember a failed call so the page can show a friendly message and
    a Retry button that repeats it (the raw error only goes to the log)."""
    st.session_state.coach_retry = {"kind": kind, "error": error, "key": chat_key(slot), **payload}
    st.rerun()


def run_kickoff(i):
    entry = day_entry()
    slot = entry["lessons"][i]
    chat = get_chat(slot)
    if chat:        # already generated (e.g. in another tab): never call again
        st.rerun()
    kickoff = core.build_kickoff_message(topic, today, slot=slot)
    chat.append({"role": "user", "content": kickoff})
    lesson, error = llm.stream_reply(
        core.build_system_prompt(log, topic, today, slot=slot), chat, max_tokens=tokens.LESSON_MAX_TOKENS,
    )
    if error:
        chat.pop()
        failed("kickoff", error, slot, i=i)
    lesson = core.finalize_reply(lesson, lesson=True)
    chat.append({"role": "assistant", "content": lesson})
    slot["kickoff"], slot["lesson"] = kickoff, lesson
    first, last = entry["lessons"][0]["n"], entry["lessons"][-1]["n"]
    entry["title"] = f"Lessons {first}–{last}"
    entry["level"] = curriculum.level_for(first)
    entry["followup_question"] = core.extract_section(lesson, "Question to Explore")
    ui.save_entry(log, entry)
    st.rerun()


def run_followup(i, text):
    entry = day_entry()
    slot = entry["lessons"][i]
    chat = get_chat(slot)
    chat.append({"role": "user", "content": text})
    with st.chat_message("user"):
        st.markdown(text)
    reply, error = llm.stream_reply(
        core.build_system_prompt(log, topic, today, followup=True, slot=slot), chat,
        max_tokens=tokens.CHAT_MAX_TOKENS,
    )
    if error:
        chat.pop()
        failed("followup", error, slot, i=i, text=text)
    chat.append({"role": "assistant", "content": core.finalize_reply(reply, lesson=False)})
    slot["followups"] = chat[2:]               # everything after the lesson
    ui.save_entry(log, entry)
    st.rerun()                                 # show the checked text, not the raw stream


def show_retry(slot):
    """Friendly message + Retry for the last failed call on this lesson."""
    retry = st.session_state.get("coach_retry")
    if not retry or retry["key"] != chat_key(slot):
        return
    st.warning(retry["error"])
    if st.button("Retry", key="coach_retry_button"):
        st.session_state.coach_retry = None
        if retry["kind"] == "kickoff":
            run_kickoff(retry["i"])
        else:
            run_followup(retry["i"], retry["text"])


# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.markdown("### Daily Learning Coach")
    st.caption("A few focused lessons a day, one idea and one small task at a time.")

    client_ready = bool(st.session_state.api_key) and llm.GROQ_AVAILABLE
    if not client_ready:
        with st.expander("Set the API key", expanded=not st.session_state.api_key):
            entered_key = st.text_input(
                "Groq API key",
                type="password",
                value=st.session_state.api_key,
                help="You can also set GROQ_API_KEY as an environment variable or secret.",
            )
            if entered_key != st.session_state.api_key:
                st.session_state.api_key = entered_key
                st.rerun()
            if not llm.GROQ_AVAILABLE:
                st.caption("Missing package: run `pip install groq`.")

    # No future dates: lessons "done" in the future would count toward the
    # real streak and levels (and a date past max_value makes Streamlit error).
    latest = ui.today()
    if st.session_state.coach_date > latest:
        st.session_state.coach_date = latest
    if "w_date" not in st.session_state or st.session_state.w_date > latest:
        st.session_state.w_date = st.session_state.coach_date
    today = st.date_input("Date", key="w_date", max_value=latest)
    st.session_state.coach_date = today

    st.divider()
    # Same base date as the Progress page (the real today), whatever date
    # is picked above.
    streak = core.current_streak(log, ui.today())
    col_a, col_b = st.columns(2)
    col_a.metric("Current streak", f"{streak} {'day' if streak == 1 else 'days'}")
    done_days = len(core.completed_dates(log))
    col_b.metric("Days completed", f"{done_days} {'day' if done_days == 1 else 'days'}")
    st.page_link("views/records.py", label="See full progress")


# ============================================================
# TODAY'S TOPIC: fixed by the weekly schedule (Reading has its own page)
# ============================================================
topic = core.scheduled_topic(today)
st.markdown(f"## {core.weekday_name(today)}, {today:%B} {today.day}")
st.markdown(f"### {core.TOPICS[topic]}")
if st.query_params.get("date") != today.isoformat() or "topic" in st.query_params:
    st.query_params.clear()
    st.query_params["date"] = today.isoformat()

entry = core.find_entry(log, today, topic)
plan = curriculum.day_plan(log, topic, entry)

store = st.session_state.coach_store
if "lessons" in getattr(store, "missing_columns", ()):
    st.warning(
        "The database can't store lesson progress yet. Run supabase/lessons.sql in "
        "Supabase's SQL Editor, then refresh this page to start."
    )
    st.stop()
if not plan:
    st.info(f"You've finished all {curriculum.written(topic)} lessons written so far for "
            f"{core.TOPICS[topic]}. The next ones will appear once they're added.")
    st.stop()

done_count = sum(1 for s in plan if s["completed"])
st.caption(
    f"Lessons {plan[0]['n']}–{plan[-1]['n']} · {curriculum.level_for(plan[0]['n'])} · "
    f"finish all {len(plan)} to complete the day ({done_count} of {len(plan)} done)"
)

# Which lesson is open: the first unfinished one unless she picked another.
sel_key = f"lesson_{today.isoformat()}_{topic}"
first_open = next((i for i, s in enumerate(plan) if not s["completed"]), len(plan) - 1)
goto = st.session_state.pop("lesson_goto", None)     # set after ticking a lesson
if goto and goto[0] == sel_key:
    st.session_state[sel_key] = goto[1]
if st.session_state.get(sel_key) is None or st.session_state[sel_key] >= len(plan):
    st.session_state[sel_key] = first_open
i = st.segmented_control(
    "Today's lessons",
    list(range(len(plan))),
    format_func=lambda k: f"Lesson {plan[k]['n']}" + (" · done" if plan[k]["completed"] else ""),
    key=sel_key,
    label_visibility="collapsed",
) or 0
slot = plan[i]
if slot["unit"]:
    st.markdown(f"#### {slot['unit']}")
st.markdown(f"### Lesson {slot['n']}: {slot['title']}")

chat = get_chat(slot)
if not chat:
    show_retry(slot)
    if i > 0 and not plan[i - 1]["completed"]:
        st.caption(f"Finish and tick off Lesson {plan[i - 1]['n']} first, then start this one.")
    elif st.button("Start this lesson", type="primary", use_container_width=True):
        st.session_state.coach_retry = None
        run_kickoff(i)
    st.stop()

# ============================================================
# LESSON + CHAT
# ============================================================
for k, message in enumerate(chat[1:]):         # the kickoff line is shown as the heading
    with st.chat_message(message["role"]):
        if k == 0:
            lesson_view.render(message["content"])  # tables and diagrams
        else:
            st.markdown(message["content"])

st.divider()
entry = day_entry()
slot = entry["lessons"][i]
done = st.checkbox(
    "I finished this lesson",
    value=slot["completed"],
    key=f"done_{today.isoformat()}_{topic}_{slot['n']}",
)
if done != slot["completed"]:
    slot["completed"] = done
    entry["completed"] = curriculum.day_complete(entry["lessons"])
    ui.save_entry(log, entry)
    if done and i + 1 < len(entry["lessons"]):
        st.session_state.lesson_goto = (sel_key, i + 1)   # straight on to the next lesson
    st.rerun()
if entry["completed"]:
    streak = core.current_streak(log, ui.today())
    st.caption(f"All {len(entry['lessons'])} lessons done for today. Current streak: {streak} {'day' if streak == 1 else 'days'}.")
else:
    left = sum(1 for s in entry["lessons"] if not s["completed"])
    st.caption(f"{left} {'lesson' if left == 1 else 'lessons'} to go. Tick them all off to complete the day.")

with st.expander("My thoughts on the question to explore (optional, the coach picks it up next time)"):
    reflection = st.text_area(
        "Question to explore",
        value=entry.get("reflection", ""),
        label_visibility="collapsed",
        key=f"reflection_{today.isoformat()}_{topic}",
    )
    if st.button("Save my thoughts"):
        entry["reflection"] = reflection.strip()
        if ui.save_entry(log, entry):
            st.toast("Saved.")     # a toast isn't hidden behind the chat input
        else:
            ui.show_pending_error()

show_retry(slot)
prompt = st.chat_input(f"Ask about Lesson {slot['n']}, report your progress, or just talk it through…")
if prompt is not None and prompt.strip():
    st.session_state.coach_retry = None
    run_followup(i, prompt)
