from datetime import date, timedelta
from html import escape

import streamlit as st

from coach import (auth, catalog, clock, core, curriculum, exercise, goalmaker, habit, lesson_view, llm, mastery,
                   paths, place, practice, progress_bar, quiz, quizgen, review, settings, steps, streaks, tokens, ui,
                   visuals)
from coach import prefs as prefs_

log = st.session_state.coach_log
config = ui.config()        # her subjects, daily pace and starting levels


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
    elif [s["n"] for s in entry["lessons"]] != [s["n"] for s in plan]:
        # her pace changed since the day started (curriculum.fit): the
        # lessons she began are the same objects, the rest follow the pace
        entry["lessons"] = plan
        entry["completed"] = curriculum.day_complete(plan)
    return entry


def shown_entry():
    """Today's entry for drawing the page: the stored one, or the day as
    planned. Unlike day_entry() it adds nothing to her record: only doing
    something (a lesson, an answer, a note) makes the day one she studied."""
    e = core.find_entry(log, today, topic)
    if e is None:
        return {"date": today.isoformat(), "topic": topic, "lessons": plan, "completed": False, "reflection": ""}
    if [s["n"] for s in e["lessons"]] != [s["n"] for s in plan]:
        return {**e, "lessons": plan, "completed": curriculum.day_complete(plan)}
    return e


def work(entry, i):
    """(the entry to save, the slot holding the lesson) for lesson i of the
    day: for a lesson carried over from an earlier day, its original slot
    there (curriculum.origin): its chat and quizzes are written back to it."""
    found = curriculum.origin(log, topic, entry["lessons"][i])
    return found if found else (entry, entry["lessons"][i])


def save(entry, owner):
    """Save the day, and the earlier day a carried-over lesson belongs to,
    each written into the day as stored now (ui.save_day): the quiz sheet
    saves from a fragment, which doesn't re-read either day first."""
    ok = ui.save_day(log, entry, [s["n"] for s in entry["lessons"]], recount=True, page_day=today)
    if owner is entry:
        return ok
    carried = [s["n"] for s in entry["lessons"] if s.get("from") == owner["date"]]
    return ui.save_day(log, owner, carried, page_day=today) and ok


def failed(kind, error, slot, **payload):
    """Remember a failed call so the page can show a friendly message and
    a Retry button that repeats it (the raw error only goes to the log)."""
    st.session_state.coach_retry = {"kind": kind, "error": error, "key": chat_key(slot), **payload}
    st.rerun()


def run_kickoff(i):
    entry = day_entry()
    owner, slot = work(entry, i)
    if curriculum.blocking(entry["lessons"], i):     # strictly in order
        st.rerun()
    chat = get_chat(slot)
    if chat:        # already generated (e.g. in another tab): never call again
        st.rerun()
    kickoff = core.build_kickoff_message(topic, today, slot=slot)
    # The chat only changes once the lesson is complete: a run interrupted
    # mid-stream (she clicks elsewhere) must not leave a lesson half there.
    lesson, error = llm.stream_reply(
        core.build_system_prompt(log, topic, today, slot=slot, start_level=start_level, public=auth.is_public(),
                                 weak=practice.weak_titles(log, topic, slot["n"], today)),     # earlier shaky ideas
        [{"role": "user", "content": kickoff}], max_tokens=tokens.LESSON_MAX_TOKENS,
    )
    if error:
        failed("kickoff", error, slot, i=i)       # (the day it made is dropped on the rerun: ui.refresh_entry)
    lesson = core.truthful_note(core.finalize_reply(lesson, lesson=True, topic=topic),
                                core.note_fact(log, topic, today, slot["n"]))
    chat += [{"role": "user", "content": kickoff}, {"role": "assistant", "content": lesson}]
    slot["kickoff"], slot["lesson"] = kickoff, lesson
    first, last = entry["lessons"][0]["n"], entry["lessons"][-1]["n"]
    entry["title"] = f"Lessons {first}–{last}"
    entry["level"] = core.lesson_level(first, start_level)
    entry["followup_question"] = core.extract_section(lesson, "Question to Explore")
    # into the day as stored now (the stream took a while: another tab may have saved since)
    ui.save_day(log, entry, [slot["n"]], keep=("title", "level", "followup_question"), recount=True, page_day=today)
    st.rerun()


def run_followup(i, text):
    entry = day_entry()
    owner, slot = work(entry, i)
    chat = get_chat(slot)
    asked = chat + [{"role": "user", "content": text}]     # kept only once answered (as in run_kickoff)
    n = st.session_state.coach_scroll_n = st.session_state.get("coach_scroll_n", 0) + 1
    st.html(place.follow(n), unsafe_allow_javascript=True)      # the page follows her question
    with st.chat_message("user"):
        st.markdown(text)
    reply, error = llm.stream_reply(
        core.build_system_prompt(log, topic, today, followup=True, slot=slot, start_level=start_level,
                                public=auth.is_public()), asked,
        max_tokens=tokens.CHAT_MAX_TOKENS,
    )
    if error:
        failed("followup", error, slot, i=i, text=text)
    answer = core.finalize_reply(reply, lesson=False, topic=topic)
    chat += [asked[-1], {"role": "assistant", "content": answer}]
    slot["followups"] = chat[2:]               # everything after the lesson
    _, _, confused = practice.split_reply(answer, slot.get("lesson", ""))
    if confused:            # a question that showed a misunderstanding: the skill map and review hear of it
        ui.learned(slot, owner["date"], "ask", 0.3, source=f"ask-{len(slot['followups'])}")
        review.keep(log, slot)
        review.add_key_idea(slot, today, topic)          # its key idea comes back tomorrow
        for c in slot.get("cards") or []:
            if c["kind"] == "point" and c["front"].startswith("Key idea ·") and c["due"] > (today + timedelta(days=1)).isoformat():
                c["due"] = (today + timedelta(days=1)).isoformat()
    save(entry, owner)
    ui.record("tutor_question")
    if confused:
        ui.record("tutor_confused")
    st.session_state.coach_scroll = (place.LATEST, False)      # and stays on it after the redraw
    st.rerun()                                 # show the checked text, not the raw stream


def run_quiz(i):
    """Write a fresh quiz for lesson i (a new set on every retake), checked
    answer by answer (coach/quizgen.py)."""
    entry = day_entry()
    owner, slot = work(entry, i)
    if curriculum.blocking(entry["lessons"], i):     # strictly in order
        st.rerun()
    context = practice.quiz_context(log, topic, slot, today, goal=catalog.path(topic))
    questions, error = quizgen.make(slot, f"{topic} lesson {slot['n']}", step=st.spinner, context=context)
    if questions is None:
        failed("quiz", error, slot, i=i)
    slot["quiz"] = quiz.new(questions, slot.get("quiz"))
    save(entry, owner)
    st.rerun()


PREPARING = "Preparing your quiz…"


def show_retry(slot, kinds):
    """Friendly message + Retry for the last failed call on this lesson, if
    it was one of `kinds`. Each kind is shown in one place on the page (the
    lesson start, the quiz, the chat), so there is only ever one Retry."""
    retry = st.session_state.get("coach_retry")
    if not retry or retry["key"] != chat_key(slot) or retry["kind"] not in kinds:
        return False
    spot = st.empty()           # the message and its Retry give way while it runs (no second click)
    with spot.container():
        st.warning(retry["error"])
        again = st.button("Retry", key=f"coach_retry_{retry['kind']}")
    if again:
        st.session_state.coach_retry = None
        spot.empty()
        if retry["kind"] == "kickoff":
            run_kickoff(retry["i"])
        elif retry["kind"] == "quiz":
            spot.button(PREPARING, disabled=True, type="primary", use_container_width=True, key="quiz_preparing")
            run_quiz(retry["i"])
        elif retry["kind"] == "grade":
            run_grading(retry["i"])
        elif retry["kind"] == "explain":
            run_explain(retry["i"], retry["text"])
        elif retry["kind"] == "follow":
            run_follow(retry["i"], retry["text"])
        else:
            run_followup(retry["i"], retry["text"])
    return True


# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    # A personal app with no key yet can take one here. The box never shows
    # the key from the app's secrets (it would be sent to the browser), and a
    # public app never offers it.
    client_ready = bool(st.session_state.api_key) and llm.GROQ_AVAILABLE
    if not client_ready and not auth.is_public():
        with st.expander("Set the API key", expanded=not st.session_state.api_key):
            if not llm.GROQ_AVAILABLE:
                st.caption("Missing package: run `pip install groq`.")
            else:
                entered_key = st.text_input(
                    "Groq API key",
                    type="password",
                    value="",
                    key="groq_key_entry",
                    help="You can also set GROQ_API_KEY as an environment variable or secret.",
                )
                if entered_key and entered_key != st.session_state.api_key:
                    st.session_state.api_key = entered_key
                    st.rerun()


# ============================================================
# TODAY'S TOPIC: her subjects take turns, one a day (settings; Reading has its own page)
# ============================================================
topic = ui.topic_for(today)
start_level = settings.start_level(config, topic)
st.markdown(f"## {core.weekday_name(today)}, {today:%B} {today.day}")
with st.container(key="today_links", horizontal=True):
    if visuals.known(topic):         # into the day's subject, its world (a goal of hers has none)
        with st.container(key=f"enter_{topic}", horizontal=True):
            if st.button(f"Enter {catalog.name(topic)}", type="tertiary", key="today_world"):
                ui.enter_world(topic)
    if st.button("Course map", type="tertiary", key="today_course"):   # the whole path
        ui.open_course(topic)
    if mastery.topics(log) and st.button("Knowledge map", type="tertiary", key="today_skills"):   # what she knows
        st.switch_page("views/skills.py")
# review: noticed when something is due, never in the way of the day's lesson
due_now = ui.review_due(log)
if due_now:
    with st.container(key="review_entry"):
        minutes = max(1, round(len(due_now) * 0.4))
        if st.button(f"Review · {len(due_now)} {'card' if len(due_now) == 1 else 'cards'} due · about {minutes} min",
                     type="tertiary", key="today_review"):
            st.switch_page("views/review.py")
# practice on the ideas she knows least: offered when some are shaky or fading, never in the way
shaky = mastery.needs_practice(log, today)
practised = (ui.prefs().get("practice") or {}).get("date") == today.isoformat()
if shaky and not practised:
    with st.container(key="practice_entry"):
        n_ideas = min(3, len(shaky))
        if st.button(f"Practice · {n_ideas} {'idea' if n_ideas == 1 else 'ideas'} to strengthen · about "
                     f"{min(practice.SET_SIZE, practice.PER_IDEA * n_ideas)} min", type="tertiary", key="today_practice"):
            st.switch_page("views/practice.py")
# ============================================================
# COMING BACK (coach/habit.py): a welcome after a break, a light day, her
# reminder, a milestone just reached, last week in review. Calm, and never
# more than one or two of them at once.
# ============================================================
habits = ui.prefs()
pace = settings.units(config)
light = habit.light_today(habits, today)
studied_today = today in core.streak_dates(log)
day_done = bool((core.find_entry(log, today, topic) or {}).get("completed"))


def set_light(on: bool) -> None:
    """A light day (one lesson), or back to her pace; today's day follows at once."""
    if ui.update_prefs(light_day=today.isoformat() if on else ""):
        ui.refit_today(habit.LIGHT_LESSONS if on else pace)


if habit.returning(log, today) and not studied_today:
    r = habit.recap(log, today)
    where = (f"Last time you were in {r['name']}: Lesson {r['n']}, “{r['title']}”. " if r else "")
    with st.container(key="welcome_back"):
        st.html(f'<p class="hb-eyebrow">Welcome back</p><p class="hb-text">{escape(where)}'
                "Today can be gentle: one lesson and a few review cards, then see how you feel.</p>")
        if not light and pace > habit.LIGHT_LESSONS:
            st.button("Start with one lesson", key="wb_light", on_click=set_light, args=(True,))
elif not day_done and pace > habit.LIGHT_LESSONS:
    with st.container(key="light_day", horizontal=True, vertical_alignment="center"):
        if light:
            st.html('<p class="hb-text">A light day: one lesson today.</p>')
            st.button(f"Back to {pace} lessons", key="light_off", type="tertiary", on_click=set_light, args=(False,))
        else:
            st.button("Busy today? Make it a light day", key="light_on", type="tertiary",
                      on_click=set_light, args=(True,))

# her reminder, shown here once its time has come and nothing is studied yet
if habit.reminder_due(habits, log, clock.now()) and ui.update_prefs(reminded_on=today.isoformat()):
    ui.record("reminder_shown")
    habits = ui.prefs()
if habits.get("reminded_on") == today.isoformat() and not studied_today:
    st.html(f'<p class="hb-reminder">It\'s past your {escape(habits["reminder_time"])} learning time. '
            "One short lesson is plenty today.</p>")

def seen_now(keys: list) -> None:
    """Milestones shown: never again (added to what is stored now)."""
    ui.load_prefs()
    ui.update_prefs(seen=prefs_.mark_seen(ui.prefs(), keys)["seen"])


# a milestone she has just reached (what she had earned before is not news)
if not habits.get("seen_init"):
    ui.update_prefs(seen=[m["key"] for m in habit.milestones(log, today)], seen_init=True)
elif (fresh := habit.new_milestones(log, today, habits["seen"])):
    with st.container(key="milestone", horizontal=True, vertical_alignment="center"):
        more = f" (and {len(fresh) - 1} more in your Learning Record)" if len(fresh) > 1 else ""
        st.html(f'<p class="hb-text"><span class="hb-eyebrow">Milestone</span>{escape(fresh[-1]["text"])}{escape(more)}</p>')
        st.button("Thanks", key="ms_seen", type="tertiary", on_click=seen_now, args=([m["key"] for m in fresh],))

# last week, in review: pointed to once a new week has begun
last_monday = habit.week_of(today) - timedelta(days=7)
if habits.get("week_seen") != habit.week_key(last_monday) and habit.week(log, last_monday, today)["lessons"]:
    if st.button("Last week in review", type="tertiary", key="today_week"):
        st.session_state.wk_which = "Last week"
        st.switch_page("views/week.py")

# her own goal, before its first lesson: the path made for her, and what today holds
goal = catalog.path(topic)
if catalog.is_goal(topic) and goal is None:       # her goal couldn't be read just now (never a lesson in its place)
    st.warning(getattr(st.session_state.coach_store, "paths_error", None)
               or "Today's goal couldn't be found. Choose your goals again in Learning Plan.")
    st.stop()
if goal and not paths.started(log, topic):
    with st.container(key="goal_intro"):
        st.html(goalmaker.summary_html(goal, settings.units(config), eyebrow="Made for you · day one",
                                       title=False))       # (the card below names it)
if "date" in st.query_params or "topic" in st.query_params:     # links from the old date picker
    st.query_params.clear()

if st.session_state.get("coach_toast"):           # set just before a rerun, shown after it
    st.toast(st.session_state.pop("coach_toast"))

entry = core.find_entry(log, today, topic)      # (re-read as stored at the start of this run: gnosis.py)
# a lesson carried over is written back to the day it began (work()): that
# day is refreshed too, or a save here would put an old copy of it back (ISS-010)
for began in sorted({s["from"] for s in curriculum.day_plan(log, topic, entry, ui.units_today()) if s.get("from")}):
    ui.refresh_entry(log, date.fromisoformat(began), topic)
plan = curriculum.day_plan(log, topic, entry, ui.units_today())

store = st.session_state.coach_store
if "lessons" in getattr(store, "missing_columns", ()):
    st.warning(
        "The database can't store lesson progress yet. Run supabase/lessons.sql in "
        "Supabase's SQL Editor, then refresh this page to start."
    )
    st.stop()
if not plan:
    st.info(f"You've finished all {curriculum.written(topic)} lessons written so far for "
            f"{catalog.name(topic)}. The next ones will appear once they're added.")
    st.stop()

# ============================================================
# COURSE CARD: the bar, and the day's lessons as steps under it
# ============================================================
unit = curriculum.unit_progress(log, topic)

# Which lesson is open: her pick if it can be opened, otherwise the current
# one; once all are done nothing is open and the day's summary shows.
sel_key = f"lesson_{today.isoformat()}_{topic}"
i = st.session_state[sel_key] = steps.viewing(plan, st.session_state.get(sel_key))
now = steps.current(plan)
done_count = steps.done(plan)


def open_lesson(k, anchor="current-lesson", restore=False):
    """Open lesson k (None: the day's summary) and take the page to it."""
    st.session_state[sel_key] = k
    st.session_state.coach_scroll = (anchor, restore)
    st.session_state.coach_scroll_n = st.session_state.get("coach_scroll_n", 0) + 1
    st.rerun()


with st.container(key="course_card"):
    # title and one percentage; the five segments below are the bar itself
    progress_bar.render(f"card_{topic}", catalog.name(topic), done_count, len(plan),
                        bar=False, label="Your goal" if goal else "Subject", topic=unit["unit"])
    # the segment of a lesson just passed fills from left to right, once
    shown = st.session_state.setdefault("steps_shown", {})
    fresh = steps.just_completed(shown.get(sel_key), plan)
    shown[sel_key] = [p["completed"] for p in plan]
    # arriving on the page, the completed lessons fill one after another
    with st.container(key="lesson_steps_flow" if progress_bar.entering() else "lesson_steps", horizontal=True):
        for k, step in enumerate(steps.states(plan, i)):
            name = (f"step_{k}_{step['state']}" + ("_viewing" if step["viewing"] else "")
                    + ("_fresh" if k in fresh else ""))
            if st.button(str(plan[k]["n"]), key=name):
                if step["state"] == steps.LOCKED:
                    st.toast(steps.unlock_message(plan, k))     # stays on the lesson she has open
                elif k != i:
                    open_lesson(k, anchor="top")
    st.html(progress_bar.meta_row(steps.label(plan), old={"left": steps.label(plan)}))    # a label: it doesn't roll

# Remembers where she scrolled to in each lesson, and carries out a move
# (Back to the current lesson, Next lesson, a new answer) once the page has
# redrawn.
scroll_to, restore = st.session_state.pop("coach_scroll", ("", False))
st.html(place.html(chat_key(plan[i]) if i is not None else f"{today.isoformat()}|{topic}|done",
                   scroll_to, f"Lesson {plan[i]['n']}:" if scroll_to and i is not None else "",
                   st.session_state.get("coach_scroll_n", 0), restore=restore),
        unsafe_allow_javascript=True)

# ============================================================
# ALL DONE: the day's summary
# ============================================================
if i is None:
    # a calm moment: what she did, the streak, and what tomorrow holds
    streak = core.current_streak(log, ui.today())
    rows = []
    for s in plan:
        score = (curriculum.content(log, topic, s).get("quiz") or {}).get("score")
        rows.append(f'<li><span class="n">{s["n"]}</span><span class="t">{escape(s["title"])}</span>'
                    f'<span class="q">{f"{score}%" if score is not None else ""}</span></li>')
    tomorrow = today + timedelta(days=1)
    t_next = ui.topic_for(tomorrow)
    upcoming = curriculum.next_numbers(log, t_next, settings.units(config)) if catalog.known(t_next) else []
    ahead = (f"Tomorrow · {catalog.name(t_next)} · "
             + (f"Lesson {upcoming[0]}" if len(upcoming) == 1 else f"Lessons {upcoming[0]}–{upcoming[-1]}")
             if upcoming else "")
    with st.container(key="day_done"):
        st.html(f'<div class="done"><p class="done-eyebrow">Complete</p><h3>Today\'s done</h3>'
                f'<p class="done-sub">All {len(plan)} {"lesson" if len(plan) == 1 else "lessons"} passed. '
                f'Current streak: {streak} {"day" if streak == 1 else "days"}. '
                f'{escape(streaks.explain(streaks.walk(core.streak_dates(log), today)))}</p>'
                f'<ol class="done-list">{"".join(rows)}</ol>'
                + (f'<p class="done-next">{escape(ahead)}</p>' if ahead else "") + '</div>')
    st.stop()

slot = curriculum.content(log, topic, plan[i])     # a lesson carried over: its original
# Reviewing an earlier lesson: say so, with the way back to the current one.
if i != now:
    with st.container(key="review_bar", horizontal=True, vertical_alignment="center"):
        st.markdown(f"You're reviewing Lesson {slot['n']} · Completed")
        way = steps.arrow(i, now)               # the arrow (drawn by CSS) points to where it goes
        if now is not None:
            if st.button(f"Back to Lesson {plan[now]['n']}", key=f"back_to_current_{way}"):
                open_lesson(now, anchor="current-quiz" if curriculum.content(log, topic, plan[now]).get("lesson") else "current-lesson",
                            restore=True)
        elif st.button("Back to today's summary", key=f"back_to_current_{way}"):
            open_lesson(None, anchor="top")
if slot["unit"] and slot["unit"] != unit["unit"]:      # the card already names the current unit
    st.markdown(f"#### {slot['unit']}")
st.html('<div class="jump-anchor" id="current-lesson"></div>')
st.markdown(f"### Lesson {slot['n']}: {slot['title']}")

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
            lesson_view.render(message["content"], topic, key=chat_key(slot), title=slot.get("title", ""))  # cards, tables, diagrams
        elif message["role"] == "assistant":
            body, where, _ = practice.split_reply(message["content"], slot.get("lesson", ""))
            st.markdown(body)
            if practice.based_label(where):          # where the answer comes from, or that it isn't sure
                st.html(f'<p class="tutor-based">{escape(practice.based_label(where))}</p>')
        else:
            st.markdown(message["content"])
reply_spot = st.container()     # a new question and its answer appear here, under the others

# Key points she wants back later (review): the Key Idea and each Deep Dive point
points = review.key_points(slot.get("lesson", ""))
if points:
    with st.popover("Save for review", key=f"save_menu_{slot['n']}"):
        st.caption("A saved point comes back in Review tomorrow, then further apart each time you know it.")
        for k, (label, text) in enumerate(points):
            kept = review.saved(slot, label)
            if st.button(label, key=f"save_point_{slot['n']}_{k}", disabled=kept, help=text[:240],
                         icon=":material/check:" if kept else None, type="tertiary"):
                entry = day_entry()
                owner, held = work(entry, i)
                review.keep(log, held)
                review.save_point(held, label, text, today, topic)
                if save(entry, owner):
                    st.toast(f"Saved for review: {label}")
                st.rerun()

st.divider()
entry = shown_entry()
owner, slot = work(entry, i)
passed_here = entry["lessons"][i]["completed"]     # (a carried-over lesson: passed on this day)


def show_results(q, missed_only=False):
    """Each question with her answer, the right answer and the specific
    mistake (only the ones she lost points on with missed_only)."""
    for k, item in enumerate(q["questions"]):
        mark, mine = q["marks"][k], q["answers"][k]
        if mark == 1 and missed_only:
            continue
        if item.get("from"):
            st.html('<p class="ex-earlier">From an earlier lesson · not part of the score</p>')
        exercise.result(item, mine, mark, q["feedback"][k], k=k + 1)


def conclude(i):
    """Every question is marked: score it; a pass finishes the lesson. She
    stays on the lesson to read the explanations; Next lesson moves on."""
    entry = day_entry()
    owner, slot = work(entry, i)
    mastery.seed(slot, owner["date"])                        # (a lesson from before mastery: what it had first)
    score = quiz.finish(slot["quiz"])
    q = slot["quiz"]
    ui.learned(slot, owner["date"], "quiz", score / 100, source=f"{q['id']}-{q['attempts']}")   # the skill map
    review.keep(log, slot)                                   # (a lesson from before review: its old cards first)
    review.add_missed(slot, slot["quiz"], today, topic)      # what she missed comes back in a few days
    if quiz.passed(score):
        review.add_key_idea(slot, today, topic)              # and, once it's passed, its key idea and words
        review.add_words(slot, today, topic)
        entry["lessons"][i]["completed"] = True
        if owner is not entry:          # the original day stays as it was; the lesson notes when
            slot["passed_on"] = today.isoformat()
        entry["completed"] = curriculum.day_complete(entry["lessons"])
        st.session_state.coach_toast = f"Passed with {score}%."
        # the page goes to the result, so Next lesson is in view (not under the chat box)
        st.session_state.coach_scroll = ("current-quiz", False)
        st.session_state.coach_scroll_n = st.session_state.get("coach_scroll_n", 0) + 1
    saved = save(entry, owner)
    for k, item in enumerate(q["questions"]):                # the question on an earlier idea: evidence for it
        if item.get("from") and q["marks"][k] is not None:
            ui.learned_elsewhere(log, topic, item["from"], "recall", q["marks"][k], source=f"{q['id']}-{k}")
    if saved and quiz.passed(score):
        ui.record("lesson_passed")
        p = ui.prefs()                   # a lesson after today's reminder: did the reminder help? (coach/metrics.py)
        if p.get("reminded_on") == today.isoformat() and p.get("reminder_hit") != today.isoformat():
            if ui.update_prefs(reminder_hit=today.isoformat()):
                ui.record("reminded_session")
    st.rerun()


def run_grading(i):
    """Have the model mark the short answers, then score the quiz."""
    entry = day_entry()
    owner, slot = work(entry, i)
    system, messages = quiz.grading_request(slot["quiz"])
    with st.spinner("Marking your answers…"):
        data, error = llm.ask_json(system, messages)
    if error or not quiz.apply_grading(slot["quiz"], data):
        save(entry, owner)               # keep her answers; Retry marks them
        failed("grade", error or llm.FAILED, slot, i=i)
    conclude(i)


def lesson_title(n):
    found = curriculum.lesson(topic, n)
    return f"Lesson {n}: {found['title']}" if found else f"Lesson {n}"


def run_explain(i, text):
    """The coach reads her explanation (one call) and answers as a teacher."""
    entry = day_entry()
    owner, slot = work(entry, i)
    if slot.get("explain") or practice.explained_today(log, today) >= practice.EXPLAIN_PER_DAY:
        st.rerun()                      # (already sent: a second click, or another tab)
    system, messages = practice.explain_request(slot, slot["title"], text)
    with st.spinner("Your coach is reading it…"):
        data, error = llm.ask_json(system, messages)
    fb = practice.read_explain(data) if data else None
    if error or fb is None:
        failed("explain", error or llm.FAILED, slot, i=i, text=text)
    slot["explain"] = {"at": clock.now_iso(), "text": text.strip(), "feedback": fb}
    ui.learned(slot, owner["date"], "explain", fb["score"], source="explain")
    if save(entry, owner):
        ui.record("explained")
    st.rerun()


def run_follow(i, text):
    """Her answer to the coach's one follow-up question (one call)."""
    entry = day_entry()
    owner, slot = work(entry, i)
    asked = (slot.get("explain") or {}).get("feedback", {}).get("question")
    if not asked or slot["explain"].get("reply_feedback"):
        st.rerun()
    system, messages = practice.follow_request(slot, slot["title"], asked, text)
    with st.spinner("Your coach is reading it…"):
        data, error = llm.ask_json(system, messages)
    fb = practice.read_follow(data) if data else None
    if error or fb is None:
        failed("follow", error or llm.FAILED, slot, i=i, text=text)
    slot["explain"].update(reply=text.strip(), reply_feedback=fb)
    ui.learned(slot, owner["date"], "explain", fb["score"], source="explain-follow")
    save(entry, owner)
    st.rerun()


VERDICT = {1.0: "✓ Clear and correct.", 0.5: "◐ On the right track.", 0.0: "✗ Not there yet."}


def explain_back(i, slot):
    """Explain it back: after a lesson is passed, once a day, she teaches its
    idea in her own words and the coach answers like a good teacher."""
    done = slot.get("explain")
    if not done and not practice.invite(log, topic, slot, today):
        return
    with st.container(key="explain_back"):
        st.html('<p class="hb-eyebrow">Explain it back</p>')
        if not done:
            st.html(f'<p class="hb-text">Teach “{escape(slot["title"])}” to a friend in two or three sentences: '
                    "what it is, and why it matters. Putting it in your own words is one of the surest ways "
                    "to make it stick.</p>")
            if show_retry(slot, ("explain",)):
                return
            text = st.text_area("Your explanation", key=f"explain_{today}_{slot['n']}", height=110,
                                placeholder="In my own words…", label_visibility="collapsed")
            spot = st.empty()
            if spot.button("Get feedback", type="primary", key="explain_send"):
                problem = practice.precheck(text)
                if problem:
                    st.warning(problem)
                else:
                    spot.button("Reading…", disabled=True, key="explain_wait")
                    st.session_state.coach_retry = None
                    run_explain(i, text)
            st.caption("Optional. It feeds your skill map; your lesson is already passed.")
            return
        fb = done["feedback"]
        st.caption(f"You wrote: {done['text']}")
        st.markdown(f"**{VERDICT.get(fb['score'], '')}** {fb['right']}")
        if fb.get("missing"):
            st.markdown(f"**What to add:** {fb['missing']}")
        if fb.get("question") and not done.get("reply_feedback"):
            st.markdown(f"**One question:** {fb['question']}")
            if show_retry(slot, ("follow",)):
                return
            reply = st.text_area("Your answer", key=f"explain_reply_{today}_{slot['n']}", height=80,
                                 placeholder="Your answer (optional)", label_visibility="collapsed")
            spot = st.empty()
            if spot.button("Send", key="explain_reply_send"):
                problem = practice.precheck(reply) if len((reply or "").split()) < 3 else ""
                if problem:
                    st.warning(problem)
                else:
                    spot.button("Reading…", disabled=True, key="explain_reply_wait")
                    st.session_state.coach_retry = None
                    run_follow(i, reply)
        elif done.get("reply_feedback"):
            st.markdown(f"**One question:** {fb['question']}")
            st.caption(f"You answered: {done['reply']}")
            rf = done["reply_feedback"]
            st.markdown(f"**{VERDICT.get(rf['score'], '')}** {rf['feedback']}")


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
        if item.get("from"):            # one question on an earlier idea she found hard
            st.html(f'<p class="ex-earlier">From an earlier lesson ({escape(lesson_title(item["from"]))}) · '
                    "it doesn't count toward your score</p>")
        draft[k] = exercise.field(item, f"quiz_{q['id']}_{k}", draft[k], k=k + 1)
    if draft != saved:
        save(day_entry(), work(day_entry(), i)[0])      # every answer is saved as she gives it
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
    owner, slot = work(entry, i)
    if quiz.submit(slot["quiz"], answers):
        save(entry, owner)
        run_grading(i)
    conclude(i)


# ============================================================
# QUIZ: 8 of 10 points (80%) or better completes the lesson
# ============================================================
st.html('<div class="jump-anchor" id="current-quiz"></div>')
st.markdown("#### Quiz")
q = slot.get("quiz")
if passed_here:
    if q and quiz.passed(q.get("score")):
        st.markdown("**" + progress_bar.rolled(f"quiz_pass_{q['id']}", f"Passed with {q['score']}%") + "** · "
                    + progress_bar.rolled(f"quiz_points_{q['id']}", f"{quiz.points(q)} points."), unsafe_allow_html=True)
        with st.expander("See the quiz"):     # this attempt's answers and explanations
            show_results(q)
    else:
        st.caption("This lesson is done.")
    if goal and slot["n"] == 1:          # her goal's first lesson: a small win, said plainly
        left = paths.lesson_count(goal) - 1
        st.html(f'<p class="goal-win"><b>First step done.</b> {left} {"lesson" if left == 1 else "lessons"} '
                f'to go on “{escape(goal["title"])}”.</p>')
    # just passed: on to the lesson this one unlocked, or the day's summary after the last
    if now is not None and now == i + 1:
        if st.button("Next lesson →", type="primary", use_container_width=True, key="next_lesson"):
            open_lesson(now)
    elif now is None and i == len(plan) - 1:
        if st.button("See today's summary →", type="primary", use_container_width=True, key="next_lesson"):
            open_lesson(None, anchor="top")
    # what she knows of it, and (once a day) explaining it back: below the way on, never in front of it
    idea = mastery.state(mastery.evidence(slot, owner["date"]), today)
    st.html(f'<p class="idea-state">This idea: <b>{mastery.LEVEL_NAMES[idea["level"]]}</b> · '
            f'{escape(mastery.describe(dict(idea, reached=True)))}</p>')
    explain_back(i, slot)
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
        st.caption(f"{quiz.QUESTIONS} questions on this lesson, of several kinds: choices, scenarios, a blank to "
                   f"fill, matching, putting steps in order, and two answers in your own words. "
                   f"Score {quiz.PASS_MARK}% or more to finish it.")
    retrying = show_retry(slot, ("quiz",))
    take = st.empty()               # can't be pressed again while the quiz is being written
    if not retrying and take.button("Take the quiz" if q is None else "Try a new quiz", type="primary", use_container_width=True):
        take.button(PREPARING, disabled=True, type="primary", use_container_width=True, key="quiz_preparing")
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
        if not reflection.strip() and core.find_entry(log, today, topic) is None:
            st.rerun()          # nothing written and no day yet: nothing to save, no day made (ISS-029)
        entry = day_entry()
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
    prompt = st.chat_input(f"Ask about Lesson {slot['n']}…")
if prompt is not None and prompt.strip():
    st.session_state.coach_retry = None
    with reply_spot:
        run_followup(i, prompt)
