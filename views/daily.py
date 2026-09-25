import streamlit as st

from coach import core, curriculum, lesson_view, llm, place, progress_bar, quiz, tokens, ui

log = st.session_state.coach_log


# Today is always the real today (past days are in the Progress history).
today = ui.today()


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
    if curriculum.blocking(entry["lessons"], i):     # strictly in order
        st.rerun()
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
    lesson = core.finalize_reply(lesson, lesson=True, topic=topic)
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
    n = st.session_state.coach_scroll_n = st.session_state.get("coach_scroll_n", 0) + 1
    st.html(place.follow(n), unsafe_allow_javascript=True)      # the page follows her question
    with st.chat_message("user"):
        st.markdown(text)
    reply, error = llm.stream_reply(
        core.build_system_prompt(log, topic, today, followup=True, slot=slot), chat,
        max_tokens=tokens.CHAT_MAX_TOKENS,
    )
    if error:
        chat.pop()
        failed("followup", error, slot, i=i, text=text)
    chat.append({"role": "assistant", "content": core.finalize_reply(reply, lesson=False, topic=topic)})
    slot["followups"] = chat[2:]               # everything after the lesson
    ui.save_entry(log, entry)
    st.session_state.coach_scroll = place.LATEST       # and stays on it after the redraw
    st.rerun()                                 # show the checked text, not the raw stream


def run_quiz(i):
    """Write a fresh quiz for lesson i (a new set on every retake), have a
    second call check every keyed answer, and rewrite any question that
    fails the check, until the whole quiz passes."""
    entry = day_entry()
    slot = entry["lessons"][i]
    if curriculum.blocking(entry["lessons"], i):     # strictly in order
        st.rerun()
    system, messages = quiz.request(slot)
    with st.spinner("Writing your quiz…"):
        data, error = llm.ask_json(system, messages, max_tokens=tokens.QUIZ_MAX_TOKENS)
    questions = quiz.parse(data) if data else None
    if error or questions is None:
        failed("quiz", error or llm.FAILED, slot, i=i)
    for attempt in range(quiz.CHECK_ROUNDS + 1):
        system, messages = quiz.check_request(questions)
        with st.spinner("Checking every answer…"):
            data, error = llm.ask_json(system, messages)
        flagged = quiz.problems(data, len(questions)) if data else None
        if error or flagged is None:
            failed("quiz", error or llm.FAILED, slot, i=i)
        if not flagged:
            break
        llm.logger.info("quiz check flagged %s", flagged)
        if attempt == quiz.CHECK_ROUNDS:
            failed("quiz", "I couldn't write a quiz whose answers I'm sure of this time. Try again.", slot, i=i)
        system, messages = quiz.rewrite_request(slot, questions, flagged)
        with st.spinner(f"Rewriting {len(flagged)} {'question' if len(flagged) == 1 else 'questions'}…"):
            data, error = llm.ask_json(system, messages, max_tokens=tokens.QUIZ_MAX_TOKENS)
        fresh = quiz.replace(questions, flagged, quiz.parse_items(data)) if data else None
        if error or fresh is None:
            failed("quiz", error or llm.FAILED, slot, i=i)
        questions = fresh
    slot["quiz"] = quiz.new(questions, slot.get("quiz"))
    ui.save_entry(log, entry)
    st.rerun()


def show_retry(slot, kinds):
    """Friendly message + Retry for the last failed call on this lesson, if
    it was one of `kinds`. Each kind is shown in one place on the page (the
    lesson start, the quiz, the chat), so there is only ever one Retry."""
    retry = st.session_state.get("coach_retry")
    if not retry or retry["key"] != chat_key(slot) or retry["kind"] not in kinds:
        return False
    st.warning(retry["error"])
    if st.button("Retry", key=f"coach_retry_{retry['kind']}"):
        st.session_state.coach_retry = None
        if retry["kind"] == "kickoff":
            run_kickoff(retry["i"])
        elif retry["kind"] == "quiz":
            run_quiz(retry["i"])
        elif retry["kind"] == "grade":
            run_grading(retry["i"])
        else:
            run_followup(retry["i"], retry["text"])
    return True


# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
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


# ============================================================
# TODAY'S TOPIC: fixed by the weekly schedule (Reading has its own page)
# ============================================================
topic = core.scheduled_topic(today)
st.markdown("## " + progress_bar.rolled("today_date", f"{core.weekday_name(today)}, {today:%B} {today.day}"),
            unsafe_allow_html=True)
if "date" in st.query_params or "topic" in st.query_params:     # links from the old date picker
    st.query_params.clear()

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
goto = st.session_state.pop("lesson_goto", None)     # set after passing a quiz
if goto and goto[0] == sel_key:
    st.session_state[sel_key] = goto[1]
if st.session_state.get(sel_key) is None or st.session_state[sel_key] >= len(plan):
    st.session_state[sel_key] = first_open

done_flags = [s["completed"] for s in plan]
done_count = sum(done_flags)
motion = progress_bar.lesson_motion(sel_key, done_flags)
with st.container(key=f"course_card_{motion}"):
    card_left = f"{done_count} / {len(plan)} lessons today"
    card_right = (f"Unit lesson {min(unit['done'] + 1, unit['total'])} of {unit['total']} · "
                  f"{curriculum.level_for(plan[0]['n'])}")
    card_old = progress_bar.seen(f"card_{topic}", pct=progress_bar.percent(done_count, len(plan)),
                                 left=card_left, right=card_right)     # numbers roll when they change
    st.html(progress_bar.build(f"{core.TOPICS[topic]}: {unit['unit']}", done_count, len(plan), bar=False,
                               old=card_old))
    i = st.segmented_control(
        "Today's lessons",
        list(range(len(plan))),
        # the icon marks a ticked lesson (the CSS fills its stretch and hides it)
        format_func=lambda k: (":material/check: " if plan[k]["completed"] else "") + str(plan[k]["n"]),
        key=sel_key,
        label_visibility="collapsed",
    ) or 0
    st.html(progress_bar.meta_row(card_left, card_right, old=card_old))

# "Jump to current progress" floats at the side of the screen, so it is
# there wherever she has scrolled. It opens the current lesson if she is
# reviewing an earlier one, then goes to where she had scrolled to in it
# (or, the first time, its quiz, or the lesson itself before it's written).
with st.container(key="jump_button"):
    if st.button("Jump to current progress", icon=":material/my_location:", key="jump_to_current"):
        if i != first_open:
            st.session_state.lesson_goto = (sel_key, first_open)
        st.session_state.coach_scroll = "current-quiz" if plan[first_open].get("lesson") else "current-lesson"
        st.session_state.coach_scroll_n = st.session_state.get("coach_scroll_n", 0) + 1
        st.rerun()

# Remembers where she scrolled to in each lesson, and carries out the jump
# once the page has redrawn.
scroll_to = st.session_state.pop("coach_scroll", "")
st.html(place.html(chat_key(plan[i]), scroll_to, f"Lesson {plan[i]['n']}:" if scroll_to else "",
                   st.session_state.get("coach_scroll_n", 0), restore=scroll_to != place.LATEST),
        unsafe_allow_javascript=True)

slot = plan[i]
if slot["unit"] and slot["unit"] != unit["unit"]:      # the card already names the current unit
    st.markdown(f"#### {slot['unit']}")
st.html('<div class="jump-anchor" id="current-lesson"></div>')
st.markdown("### " + progress_bar.rolled(f"lesson_title_{chat_key(slot)}", f"Lesson {slot['n']}: {slot['title']}"),
            unsafe_allow_html=True)

chat = get_chat(slot)
if not chat:
    show_retry(slot, ("kickoff",))
    if (before := curriculum.blocking(plan, i)):
        st.caption(f"Pass the quiz for Lesson {before['n']} first, then start this one.")
    else:
        start = st.empty()          # the button goes away while the lesson is written
        if start.button("Start this lesson", type="primary", use_container_width=True):
            start.empty()
            st.session_state.coach_retry = None
            run_kickoff(i)
    st.stop()

# ============================================================
# LESSON + CHAT
# ============================================================
last_question = max((k for k, m in enumerate(chat) if k > 1 and m["role"] == "user"), default=None)
for k, message in enumerate(chat[1:], start=1):   # the kickoff line is shown as the heading
    if k == last_question:
        st.html(place.latest_anchor())
    with st.chat_message(message["role"]):
        if k == 1:
            lesson_view.render(message["content"], topic, key=chat_key(slot))  # cards, tables and diagrams
        else:
            st.markdown(message["content"])
reply_spot = st.container()     # a new question and its answer appear here, under the others

st.divider()
entry = day_entry()
slot = entry["lessons"][i]


def show_results(q, missed_only=False):
    """Each question with her answer, the right answer and why (only the
    ones she lost points on with missed_only)."""
    for k, item in enumerate(q["questions"]):
        mark, mine = q["marks"][k], q["answers"][k]
        if mark == 1 and missed_only:
            continue
        sign = "✓" if mark == 1 else ("◐" if mark else "✗")
        st.markdown(f"{sign} {k + 1}. {item['question']}")
        if item["type"] == "choice":
            yours, right = item["options"][mine], item["options"][item["answer"]]
            lead = f"Your answer: {yours}" + ("" if mark == 1 else f" · Correct: {right}")
            st.caption(f"{lead}. {item['why']}".strip())
        elif item["type"] == "match":
            pairs = "; ".join(f"{left} → {item['right'][key]}" for left, key in zip(item["left"], item["key"]))
            got = f"{mark * len(item['key']):g} of {len(item['key'])} pairs right. " if mark != 1 else ""
            st.caption(f"{got}Correct pairs: {pairs}. {item['why']}".strip())
        else:
            st.caption(f"Your answer: {mine}")
            note = q["feedback"][k] or item["why"]
            if mark == 1:
                st.caption(note)
            else:
                st.caption(f"Why it's marked wrong: {note}")
                st.caption(f"A good answer: {item['answer']}")


def conclude(i):
    """Every question is marked: score it; a pass finishes the lesson. She
    stays on the lesson to read the explanations; Next lesson moves on."""
    entry = day_entry()
    slot = entry["lessons"][i]
    score = quiz.finish(slot["quiz"])
    if quiz.passed(score):
        slot["completed"] = True
        entry["completed"] = curriculum.day_complete(entry["lessons"])
        st.session_state.coach_toast = f"Passed with {score}%."
    ui.save_entry(log, entry)
    st.rerun()


def run_grading(i):
    """Have the model mark the short answers, then score the quiz."""
    entry = day_entry()
    slot = entry["lessons"][i]
    system, messages = quiz.grading_request(slot["quiz"])
    with st.spinner("Marking your answers…"):
        data, error = llm.ask_json(system, messages)
    if error or not quiz.apply_grading(slot["quiz"], data):
        ui.save_entry(log, entry)               # keep her answers; Retry marks them
        failed("grade", error or llm.FAILED, slot, i=i)
    conclude(i)


@st.fragment
def answer_sheet(i, q):
    """The quiz questions. Each answer is kept the moment she gives it
    (widget state, plus a draft saved with the lesson, so answers survive
    reruns, a dropped connection, page switches and a reload), and only
    this block reruns while she answers."""
    if q.get("draft") is None:
        q["draft"] = quiz.blank_draft(q)
    draft = q["draft"]
    saved = [list(a) if isinstance(a, list) else a for a in draft]
    for k, item in enumerate(q["questions"]):
        key = f"quiz_{q['id']}_{k}"
        label = f"**{k + 1}.** {item['question']}"
        if item["type"] == "choice":
            draft[k] = st.radio(label, range(len(item["options"])), index=draft[k],
                                format_func=lambda o, item=item: item["options"][o], key=key)
        elif item["type"] == "match":
            st.markdown(label)
            keys = [f"{key}_{j}" for j in range(len(item["left"]))]
            chosen = [st.session_state.get(kk, draft[k][j]) for j, kk in enumerate(keys)]
            for j, left in enumerate(item["left"]):
                # a meaning already matched to another term isn't offered again
                taken = {c for m, c in enumerate(chosen) if m != j and c is not None}
                options = [o for o in range(len(item["right"])) if o not in taken]
                current = chosen[j] if chosen[j] in options else None
                draft[k][j] = st.selectbox(
                    left, options, index=options.index(current) if current is not None else None,
                    placeholder="Choose its match", format_func=lambda o, item=item: item["right"][o],
                    key=keys[j])
        else:
            draft[k] = st.text_area(label, value=draft[k], key=key, height=90,
                                    placeholder="Answer in a sentence or two, in your own words")
    if draft != saved:
        ui.save_entry(log, day_entry())         # every answer is saved as she gives it
    submit = st.empty()
    if not submit.button("Submit answers", type="primary", use_container_width=True, key=f"submit_{q['id']}"):
        return
    entry = day_entry()
    if curriculum.blocking(entry["lessons"], i):    # finished strictly in order
        st.rerun()
    answers = [list(a) if isinstance(a, list) else a for a in draft]
    missing = [k + 1 for k, (item, a) in enumerate(zip(q["questions"], answers)) if not quiz.answered(item, a)]
    if missing:
        st.warning("Answer every question first (still open: " + ", ".join(map(str, missing)) + ").")
        return
    submit.empty()
    if quiz.submit(entry["lessons"][i]["quiz"], answers):
        ui.save_entry(log, entry)
        run_grading(i)
    conclude(i)


# ============================================================
# QUIZ: 8 of 10 points (80%) or better completes the lesson
# ============================================================
st.html('<div class="jump-anchor" id="current-quiz"></div>')
st.markdown("#### Quiz")
q = slot.get("quiz")
if slot["completed"]:
    if q and quiz.passed(q.get("score")):
        st.markdown("**" + progress_bar.rolled(f"quiz_pass_{q['id']}", f"Passed with {q['score']}%") + "** · "
                    + progress_bar.rolled(f"quiz_points_{q['id']}", f"{quiz.points(q)} points."), unsafe_allow_html=True)
        with st.expander("See the quiz"):     # this attempt's answers and explanations
            show_results(q)
    else:
        st.caption("This lesson is done.")
    if i + 1 < len(entry["lessons"]):
        if st.button(f"Next lesson: Lesson {entry['lessons'][i + 1]['n']}", type="primary",
                     use_container_width=True):
            st.session_state.lesson_goto = (sel_key, i + 1)
            st.rerun()
elif (before := curriculum.blocking(entry["lessons"], i)):
    # e.g. a lesson started under the old tick box before the one ahead of it was finished
    st.caption(f"Pass the quiz for Lesson {before['n']} first; this quiz opens after that.")
elif q is not None and quiz.needs_grading(q):
    # submitted, but marking the short answers didn't go through yet
    st.caption("Your answers are saved. They just need marking.")
    retrying = show_retry(slot, ("grade",))
    mark = st.empty()
    if not retrying and mark.button(
            "Mark my answers", type="primary", use_container_width=True):
        mark.empty()
        run_grading(i)
elif q is None or q["answers"] is not None and not quiz.passed(q["score"]):
    if q is not None:               # the last attempt fell short
        st.markdown("**" + progress_bar.rolled(f"quiz_score_{q['id']}", f"{q['score']}%") + "** · "
                    + progress_bar.rolled(f"quiz_points_{q['id']}", f"{quiz.points(q)} points.")
                    + f" You need {quiz.PASS_MARK}% to move on; a new set of questions is ready when you are.",
                    unsafe_allow_html=True)
        with st.expander("See what you missed", expanded=True):
            show_results(q, missed_only=True)
    else:
        st.caption(f"{quiz.QUESTIONS} questions on this lesson: multiple choice, matching and short answers. "
                   f"Score {quiz.PASS_MARK}% or more to finish it.")
    retrying = show_retry(slot, ("quiz",))
    take = st.empty()               # hidden while the quiz is being written
    if not retrying and take.button("Take the quiz" if q is None else "Try a new quiz", type="primary", use_container_width=True):
        take.empty()
        st.session_state.coach_retry = None
        run_quiz(i)
else:
    answer_sheet(i, q)

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

show_retry(slot, ("followup",))
# The chat box stays at the bottom of the screen wherever she has scrolled
# (it sticks there with CSS). It isn't Streamlit's own bottom bar: that one
# keeps the page scrolled to the end, so Today wouldn't open at the top.
with st.container(key="chat_dock"):
    prompt = st.chat_input(f"Ask about Lesson {slot['n']}, report your progress, or just talk it through…")
if prompt is not None and prompt.strip():
    st.session_state.coach_retry = None
    with reply_spot:
        run_followup(i, prompt)
