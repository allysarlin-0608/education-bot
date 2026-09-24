from datetime import date

import streamlit as st

from coach import core, curriculum, lesson_view, llm, progress_bar, quiz, tokens, ui

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


def run_quiz(i):
    """Write a fresh quiz for lesson i (a new set on every retake)."""
    entry = day_entry()
    slot = entry["lessons"][i]
    system, messages = quiz.request(slot)
    with st.spinner("Writing your quiz…"):
        data, error = llm.ask_json(system, messages, max_tokens=tokens.QUIZ_MAX_TOKENS)
    questions = quiz.parse(data) if data else None
    if error or questions is None:
        failed("quiz", error or llm.FAILED, slot, i=i)
    slot["quiz"] = quiz.new(questions, slot.get("quiz"))
    ui.save_entry(log, entry)
    st.rerun()


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
        elif retry["kind"] == "quiz":
            run_quiz(retry["i"])
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
if st.query_params.get("date") != today.isoformat() or "topic" in st.query_params:
    st.query_params.clear()
    st.query_params["date"] = today.isoformat()

if st.session_state.get("coach_toast"):           # set just before a rerun, shown after it
    st.toast(st.session_state.pop("coach_toast"))

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

# ============================================================
# COURSE CARD: the day's lessons are the progress bar
# ============================================================
# Each lesson is one stretch of the liquid line, filled once ticked, with
# its number below to open it. Opening an earlier lesson to review it only
# changes which number is marked; the bar never empties.
unit = curriculum.unit_progress(log, topic)

# Which lesson is open: the first unfinished one unless she picked another.
sel_key = f"lesson_{today.isoformat()}_{topic}"
first_open = next((i for i, s in enumerate(plan) if not s["completed"]), len(plan) - 1)
goto = st.session_state.pop("lesson_goto", None)     # set after ticking a lesson
if goto and goto[0] == sel_key:
    st.session_state[sel_key] = goto[1]
if st.session_state.get(sel_key) is None or st.session_state[sel_key] >= len(plan):
    st.session_state[sel_key] = first_open

done_flags = [s["completed"] for s in plan]
done_count = sum(done_flags)
motion = progress_bar.lesson_motion(sel_key, done_flags)
with st.container(key=f"course_card_{motion}"):
    st.html(progress_bar.build(f"{core.TOPICS[topic]}: {unit['unit']}", done_count, len(plan), bar=False))
    i = st.segmented_control(
        "Today's lessons",
        list(range(len(plan))),
        # the icon marks a ticked lesson (the CSS fills its stretch and hides it)
        format_func=lambda k: (":material/check: " if plan[k]["completed"] else "") + str(plan[k]["n"]),
        key=sel_key,
        label_visibility="collapsed",
    ) or 0
    st.html(progress_bar.meta_row(
        f"{done_count} / {len(plan)} lessons today",
        f"Unit {unit['done']} of {unit['total']} · {curriculum.level_for(plan[0]['n'])}",
    ))

slot = plan[i]
if slot["unit"] and slot["unit"] != unit["unit"]:      # the card already names the current unit
    st.markdown(f"#### {slot['unit']}")
st.markdown(f"### Lesson {slot['n']}: {slot['title']}")

chat = get_chat(slot)
if not chat:
    show_retry(slot)
    if i > 0 and not plan[i - 1]["completed"]:
        st.caption(f"Pass the quiz for Lesson {plan[i - 1]['n']} first, then start this one.")
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


def show_results(q, missed_only=False):
    """The questions with her answer, the right one and why."""
    for k, item in enumerate(q["questions"]):
        mine = q["answers"][k]
        right = mine == item["answer"]
        if right and missed_only:
            continue
        st.markdown(f"{'✓' if right else '✗'} {k + 1}. {item['question']}")
        if not right:
            yours = item["options"][mine] if mine is not None else "no answer"
            st.caption(f"Your answer: {yours} · Correct: {item['options'][item['answer']]}. {item['why']}")


# ============================================================
# QUIZ: 9 of 10 (90%) or better completes the lesson
# ============================================================
st.markdown("#### Quiz")
q = slot.get("quiz")
if slot["completed"]:
    if q and quiz.passed(q.get("score")):
        st.caption(f"Passed with {q['score']}%. This lesson is done.")
        with st.expander("See the quiz"):
            show_results(q)
    else:
        st.caption("This lesson is done.")
elif q is None or q["answers"] is not None and not quiz.passed(q["score"]):
    if q is not None:               # the last attempt fell short
        right = sum(1 for item, a in zip(q["questions"], q["answers"]) if a == item["answer"])
        st.markdown(f"**{q['score']}%** · {right} of {len(q['questions'])} right. "
                    f"You need {quiz.PASS_MARK}% to move on; a new set of questions is ready when you are.")
        with st.expander("See what you missed", expanded=True):
            show_results(q, missed_only=True)
    else:
        st.caption(f"{quiz.QUESTIONS} questions on this lesson. Score {quiz.PASS_MARK}% or more "
                   f"to finish it and move on to the next one.")
    show_retry(slot)
    if st.button("Take the quiz" if q is None else "Try a new quiz", type="primary", use_container_width=True):
        st.session_state.coach_retry = None
        run_quiz(i)
else:
    with st.form(f"quiz_{today.isoformat()}_{topic}_{slot['n']}_{q['id']}"):
        choices = []
        for k, item in enumerate(q["questions"]):
            choices.append(st.radio(
                f"**{k + 1}.** {item['question']}", range(len(item["options"])),
                format_func=lambda o, item=item: item["options"][o], index=None,
                key=f"quiz_{q['id']}_{k}",
            ))
        submitted = st.form_submit_button("Submit answers", type="primary", use_container_width=True)
    if submitted:
        if None in choices:
            st.warning(f"Answer all {len(choices)} questions first.")
        else:
            score = quiz.grade(q, choices)
            if quiz.passed(score):
                slot["completed"] = True
                entry["completed"] = curriculum.day_complete(entry["lessons"])
                if i + 1 < len(entry["lessons"]):
                    st.session_state.lesson_goto = (sel_key, i + 1)   # straight on to the next lesson
                st.session_state.coach_toast = (f"Passed with {score}%. On to the next lesson."
                                                if i + 1 < len(entry["lessons"]) else f"Passed with {score}%.")
            ui.save_entry(log, entry)
            st.rerun()

if entry["completed"]:
    streak = core.current_streak(log, ui.today())
    st.caption(f"All {len(entry['lessons'])} lessons done for today. Current streak: {streak} {'day' if streak == 1 else 'days'}.")
else:
    left = sum(1 for s in entry["lessons"] if not s["completed"])
    st.caption(f"{left} {'lesson' if left == 1 else 'lessons'} to go. Pass each quiz to complete the day.")

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
