"""Progress: how she's doing overall, her history day by day, and where she
is now in each subject.

Two sides: the month on the left, and on the right one view at a time,
switched at its top: the day picked, every session, or the subjects. On a
wide page each side scrolls on its own; on a phone the month comes first
and the view under it. Lessons are read one at a time, a section at a
time, so opening them never makes the page long."""
import calendar
import json
from datetime import date
from html import escape

import streamlit as st

from coach import core, curriculum, history, lesson_view, progress_bar, rolling, settings, ui

log = st.session_state.coach_log
today = ui.today()
config = ui.config()
subjects = settings.shown_subjects(config)       # only the subjects she has chosen

st.html('<div id="progress-page" hidden></div>')      # lets the page use the width (style.py)
st.markdown("## Progress")

if not log["entries"]:
    st.info("No records yet. They start building up after your first lesson.")


def days(n):
    return f"{n} {'day' if n == 1 else 'days'}"


def go(ym, day=None, way="none"):
    """Show month `ym` (and pick `day`); `way` is the direction the month
    slides in from."""
    st.session_state.prog_month = ym
    st.session_state.prog_way = way
    if day is not None:
        st.session_state.prog_day = day.isoformat()
        st.session_state.prog_view_next = "Day"      # a picked day is shown right away
    st.rerun()


def lesson_rows(lessons):
    """The day's lessons, one line each: passed or not, number, title, quiz."""
    rows = []
    for s in lessons:
        q = s.get("quiz") or {}
        score = f'{q["best"]}%' if q.get("best") is not None else ""
        rows.append(f'<li class="{"done" if s["completed"] else "open"}"><span class="n">{s["n"]}</span>'
                    f'<span class="t">{escape(s["title"])}</span><span class="q">{score}</span></li>')
    st.html(f'<ol class="lesson-rows">{"".join(rows)}</ol>')


def show_entry(e, where):
    """One day's session, compact: where it sits in the course, its lessons
    one line each, and a lesson to read on request (one at a time, a section
    at a time). For a session from before the syllabus, her thoughts too.
    `where` keeps widget keys apart when a session shows twice."""
    key = f"{where}_{e['date']}_{e['topic']}"
    if e.get("lessons"):
        curriculum.refresh_titles(e["topic"], e["lessons"])
        ns = [s["n"] for s in e["lessons"]]
        done_count = sum(1 for s in e["lessons"] if s["completed"])
        st.caption(f"{core.TOPICS[e['topic']]} · Lessons {min(ns)}–{max(ns)} · {e['level']} · "
                   f"{done_count} of {len(ns)} passed")
        lesson_rows(e["lessons"])
        readable = {s["n"]: s for s in e["lessons"] if s.get("lesson")}
        if readable:
            pick = st.pills("Read a lesson", list(readable), format_func=lambda n: f"Lesson {n}",
                            key=f"read_{key}", label_visibility="collapsed")
            if pick in readable:
                s = readable[pick]
                with st.container(key=f"reader_{key}_{pick}"):
                    st.markdown(f"**Lesson {s['n']}: {s['title']}**")
                    lesson_view.render_tabs(s["lesson"], e["topic"], key=f"rec_{key}_{s['n']}")
        if e.get("followup_question"):
            st.markdown(f"**Question to explore:** {e['followup_question']}")
        return
    st.caption(f"{core.TOPICS[e['topic']]} · session {e['session_number']} · {e['level']} · "
               + ("finished" if e.get("completed") else "not finished"))
    if e.get("followup_question"):
        st.markdown(f"**Question to explore:** {e['followup_question']}")
    reflection = st.text_area(
        "My thoughts",
        value=e.get("reflection", ""),
        key=f"rec_reflection_{key}",
        placeholder="Your thoughts on the question; the coach picks it up next time",
    )
    if st.button("Save my thoughts", key=f"rec_save_{key}"):
        e["reflection"] = reflection.strip()
        if ui.save_entry(log, e):
            st.toast("Saved.")
        else:
            ui.show_pending_error()
    if e.get("lesson") and st.toggle("Read the lesson", key=f"rec_lesson_{key}"):
        with st.container(key=f"reader_{key}"):
            lesson_view.render_tabs(e["lesson"], e["topic"], key=f"rec_{key}")


# ============================================================
# OVERVIEW: the whole picture in one row
# ============================================================
lessons_passed = sum(sum(1 for s in e.get("lessons", []) if s["completed"]) for e in log["entries"])
figures = {
    "Current streak": days(core.current_streak(log, today)),
    "Longest streak": days(core.longest_streak(log)),
    "Days completed": days(len(core.completed_dates(log))),
    "Days studied": days(len({e['date'] for e in log['entries']})),
    "Lessons passed": f"{lessons_passed:,}",
}
before = progress_bar.seen("progress_figures", **{k.replace(" ", "_"): v for k, v in figures.items()})
st.html('<div class="figures">' + "".join(          # numbers roll when they change
    f'<div class="figure"><div class="figure-label">{label}</div>'
    f'<div class="figure-value">{rolling.html(value, before.get(label.replace(" ", "_")))}</div></div>'
    for label, value in figures.items()) + "</div>")

# the month and day shown: today if she has studied today, otherwise the last day she did
now = (today.year, today.month)
last = max((e["date"] for e in log["entries"] if e["date"] <= today.isoformat()), default=today.isoformat())
start = today.isoformat() if history.entries_on(log, today) else last
picked = date.fromisoformat(st.session_state.setdefault("prog_day", start))
if "prog_month" not in st.session_state or st.session_state.get("prog_month_for") != start:
    st.session_state.prog_month, st.session_state.prog_month_for = (picked.year, picked.month), start
year, month = st.session_state.prog_month
way = st.session_state.get("prog_way", "none")


def toward(ym):
    """Which way a move to month `ym` slides: from the right going forward."""
    return "none" if ym == (year, month) else "next" if ym > (year, month) else "prev"


def view_day():
    """The day picked: new for each day, so it eases in."""
    with st.container(key=f"prog_day_{picked.isoformat()}"):
        stats = history.day_stats(log, picked, today)
        st.markdown(f"#### {core.weekday_name(picked)}, {picked:%B} {picked.day}"
                    + (f", {picked.year}" if picked.year != today.year else ""))
        on_day = history.entries_on(log, picked)
        if not on_day:
            planned = core.TOPICS[ui.topic_for(picked)]
            if stats["status"] == "future":
                st.caption(f"Coming up: {planned}.")
            elif settings.is_legacy(config):
                st.caption(f"Nothing recorded. {core.weekday_name(picked)}s are for {planned}.")
            elif picked >= settings.start_day(config, ui.TIMEZONE):
                st.caption(f"Nothing recorded. This day was for {planned}.")
            else:
                st.caption("Nothing recorded.")
        else:
            st.markdown('<span class="day-status">' + {"done": "Completed", "partial": "Partly done"}.get(
                stats["status"], "") + "</span>", unsafe_allow_html=True)
            for e in on_day:
                show_entry(e, "day")
    if st.session_state.pop("prog_reveal", False):
        # a day just picked: if its card is out of sight (on a phone it sits
        # below the month), bring it up; beside the month it stays put
        st.html('<script>(function go(n) { const w = window.parent; const e = w.document.querySelector(\'[class*="st-key-prog_day_"]\');'
                ' if (!e) { if (n) setTimeout(() => go(n - 1), 80); return; }'
                ' const r = e.getBoundingClientRect();'
                ' if (r.top > w.innerHeight - 140 || r.bottom < 80) e.scrollIntoView({behavior: "smooth", block: "start"});'
                ' })(20);</script>', unsafe_allow_javascript=True)



def view_sessions():
    """Every session, newest first, a page at a time."""
    PAGE = 10
    if log["entries"]:
        with st.container(key="sessions_head", horizontal=True, vertical_alignment="center"):
            count_spot = st.empty()          # (the switch above already names the view)
            if st.session_state.get("sessions_topic") not in ("all", *subjects):
                st.session_state.pop("sessions_topic", None)     # a subject she has since taken out
            topic_filter = st.selectbox(
                "Subject",
                ["all", *subjects],
                format_func=lambda k: "All subjects" if k == "all" else core.TOPICS[k],
                label_visibility="collapsed",
                key="sessions_topic",
            )
        entries = [e for e in reversed(log["entries"])
                   if topic_filter == "all" or e["topic"] == topic_filter]
        count_spot.markdown(f'<span class="view-count">{len(entries)} {"session" if len(entries) == 1 else "sessions"}</span>',
                            unsafe_allow_html=True)
        if not entries:
            st.caption("Nothing recorded for this subject yet.")
        shown = st.session_state.setdefault("sessions_shown", PAGE)
        with st.container(key=f"sessions_list_{topic_filter}"):      # a new filter eases in
            for e in entries[:shown]:
                day = date.fromisoformat(e["date"])
                mark = "●" if e.get("completed") else "○"
                title = e.get("title") or core.TOPICS[e["topic"]]
                with st.expander(f"{mark} {core.weekday_name(day)[:3]}, {day:%b} {day.day}, {day.year} · {title}"):
                    if st.button("Show on the calendar", key=f"oncal_{e['date']}_{e['topic']}",
                                 icon=":material/event:", type="tertiary"):
                        st.session_state.prog_reveal = True
                        go((day.year, day.month), day, way=toward((day.year, day.month)))
                    show_entry(e, "list")
        if len(entries) > shown:
            if st.button(f"Show {min(PAGE, len(entries) - shown)} more of {len(entries) - shown}", key="sessions_more"):
                st.session_state.sessions_shown = shown + PAGE
                st.rerun()



def view_subjects():
    """Each subject and the topic (unit) she is in now; Reading links to its page."""
    st.caption(f"Each subject has {curriculum.TOTAL:,} lessons taken in order: 1–{curriculum.LEVEL_SIZE:,} "
               f"Beginner, {curriculum.LEVEL_SIZE + 1:,}–{2 * curriculum.LEVEL_SIZE:,} Intermediate, the rest "
               f"Advanced, or your starting level where that's higher. The bar is the topic you're in now.")
    shown = subjects + (["reading"] if settings.reading_on(config) else [])
    with st.container(key="subj_list"):
        for key in shown:
            label = core.TOPICS[key]
            if curriculum.has_syllabus(key):
                p = curriculum.progress(log, key)
                unit = curriculum.unit_progress(log, key)
                level = core.lesson_level(min(p["done"] + 1, curriculum.TOTAL), settings.start_level(config, key))
                progress_bar.render(
                    f"course_{key}", label, unit["done"], unit["total"],
                    f"{p['done']:,} of {p['total']:,} overall · {level}",
                    label="", compact=True, topic=unit["unit"],
                )
                with st.container(key=f"enter_{key}", horizontal=True):     # into its world
                    if st.button(f"Enter {label}", type="tertiary", key=f"prog_world_{key}",
                                 icon=":material/arrow_outward:"):
                        ui.enter_world(key)
                continue
            # Reading has no syllabus: one line, the books finished, and the way to the shelf
            finished = sum(1 for b in log["books"] if b["status"] == "finished")
            st.page_link("views/reading.py", label=f"{label} · {finished} {'book' if finished == 1 else 'books'} finished")


# ============================================================
# TWO SIDES: the month | one view at a time (the day, every session, the subjects)
# ============================================================
VIEWS = ["Day", "Sessions", "Subjects"]
with st.container(key="prog_main"):
    month_col, panel_col = st.columns([5, 6], gap="large")

with month_col:
    summary = history.month_summary(log, year, month, today)
    with st.container(key="cal_head", horizontal=True, vertical_alignment="center"):
        st.markdown(f"#### {calendar.month_name[month]} {year}")
        with st.container(key="cal_nav", horizontal=True, horizontal_alignment="right", gap="small"):
            if st.button("‹", key="cal_prev"):
                go(history.shift(year, month, -1), way="prev")
            if st.button("Today", key="cal_today", disabled=(year, month) == now and picked == today):
                go(now, today, way=toward(now))
            if st.button("›", key="cal_next"):
                go(history.shift(year, month, 1), way="next")
    st.markdown('<span class="cal-summary">' + progress_bar.rolled(   # the month's numbers roll when it changes
        "cal_summary", f"{days(summary['studied'])} studied · {days(summary['completed'])} completed · "
                       f"{summary['lessons']} {'lesson' if summary['lessons'] == 1 else 'lessons'} passed")
                + "</span>", unsafe_allow_html=True)

    # weekday names; on the old weekly schedule, each with the subject that day of the week is for
    weekly = settings.is_legacy(config)
    st.html('<div class="cal-week">' + "".join(
        f'<span><b>{name[:3]}</b>'
        + (f'<i>{history.short_topic(core.WEEKDAY_TOPIC[k])}</i>' if weekly else "") + "</span>"
        for k, name in enumerate(core.WEEKDAYS)) + "</div>")
    # the grid is new for each month (its key names the month), so it slides in
    with st.container(key=f"calgrid_{year}_{month}_{way}"):
        for w, week in enumerate(history.month_grid(log, year, month, today)):
            with st.container(key=f"calw_{w}", horizontal=True):
                for d in week:
                    name = (f"cal_{d['date'].isoformat()}_{d['status']}_a{history.amount(d)}"
                            + ("" if d["in_month"] else "_out") + ("_today" if d["date"] == today else "")
                            + ("_sel" if d["date"] == picked else ""))
                    # (no hover tip: Streamlit draws a second button for it; the day
                    # card says it all once the day is picked)
                    if st.button(str(d["date"].day), key=name):
                        st.session_state.prog_reveal = True     # on a phone the day shows below: bring it up
                        ym = (d["date"].year, d["date"].month)
                        go(ym, d["date"], way=toward(ym))
    st.html('<div class="cal-key"><span><i class="k-done"></i>Completed</span>'
            '<span><i class="k-part"></i>Partly done</span>'
            '<span>The line under a day grows with the lessons passed</span></div>')

with panel_col:
    # one view at a time, so the right side stays calm: the day picked on the
    # calendar, every session, or the subjects. Each eases in when switched to.
    st.session_state.setdefault("prog_view", "Day")
    if (pending := st.session_state.pop("prog_view_next", None)):
        st.session_state.prog_view = pending
    view = st.segmented_control("Show", VIEWS, key="prog_view", required=True,
                                label_visibility="collapsed", width="stretch") or "Day"
    with st.container(key=f"view_{view.lower()}"):
        {"Day": view_day, "Sessions": view_sessions, "Subjects": view_subjects}[view]()


# ============================================================
# BACKUP: tucked away, one click to open
# ============================================================
with st.expander("Backup and restore"):
    if ui.using_cloud():
        st.caption("Your records are in the Supabase database, so they survive app restarts. "
                   "Download a copy if you'd like one of your own.")
    else:
        st.caption("Your records are on the app's server and may be wiped when Streamlit Cloud restarts, "
                   "so download a backup now and then.")
    st.download_button(
        "Download a backup",
        data=json.dumps(log, ensure_ascii=False, indent=2),
        file_name=f"learning_log_{today.isoformat()}.json",
        mime="application/json",
    )
    uploaded = st.file_uploader("Import a backup", type="json")
    if uploaded is not None and st.button("Replace my records with this backup"):
        try:
            new_log = core.parse_log(json.load(uploaded))
        except (ValueError, json.JSONDecodeError) as err:
            st.error(f"Import failed: {err}")
        else:
            if ui.replace_log(new_log):
                st.session_state.coach_log = new_log
                ui.reset_chat()
                st.rerun()
