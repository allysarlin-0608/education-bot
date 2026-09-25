import calendar
import json
from datetime import date

import streamlit as st

from coach import books, core, curriculum, history, lesson_view, progress_bar, rolling, ui

log = st.session_state.coach_log
today = ui.today()

st.html('<div id="progress-page" hidden></div>')      # lets the page use the width (style.py)
st.markdown("## Progress")

if not log["entries"]:
    st.info("No records yet. They start building up after your first lesson.")


def days(n):
    return f"{n} {'day' if n == 1 else 'days'}"


def show_entry(e, where):
    """One day's session: its lessons and quiz scores, the question to explore,
    the lessons themselves on request; for a session from before the
    syllabus, her thoughts too. `where` keeps widget keys apart when the same
    session shows twice (the selected day and the list)."""
    key = f"{where}_{e['date']}_{e['topic']}"
    if e.get("lessons"):
        curriculum.refresh_titles(e["topic"], e["lessons"])
        done_count = sum(1 for s in e["lessons"] if s["completed"])
        st.caption(f"{core.TOPICS[e['topic']]} · {e['level']} · {done_count} of {len(e['lessons'])} lessons passed")
        for s in e["lessons"]:
            q = s.get("quiz") or {}
            score = f" · quiz {q['best']}%" if q.get("best") is not None else ""
            st.markdown(f"{'●' if s['completed'] else '○'} Lesson {s['n']}: {s['title']}{score}")
        if e.get("followup_question"):
            st.markdown(f"**Question to explore:** {e['followup_question']}")
        if any(s.get("lesson") for s in e["lessons"]) and st.toggle("Show the lessons", key=f"rec_lessons_{key}"):
            for s in e["lessons"]:
                if s.get("lesson"):
                    with st.container(border=True):
                        st.markdown(f"**Lesson {s['n']}: {s['title']}**")
                        lesson_view.render(s["lesson"], e["topic"], key=f"rec_{key}_{s['n']}")
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
    if e.get("lesson") and st.toggle("Show the lesson", key=f"rec_lesson_{key}"):
        with st.container(border=True):
            lesson_view.render(e["lesson"], e["topic"], key=f"rec_{key}")


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

# ============================================================
# HISTORY (calendar and the day picked) | WHERE SHE IS (subjects, books)
# ============================================================
with st.container(key="prog_main"):
    history_col, subjects_col = st.columns([7, 5], gap="large")

with history_col:
    # ---- the month: pick any day to see what she studied ----
    earliest = history.first_month(log, today)
    now = (today.year, today.month)
    # the day shown at first: today if she has studied, otherwise the last day she did
    last = max((e["date"] for e in log["entries"] if e["date"] <= today.isoformat()), default=today.isoformat())
    start = today.isoformat() if history.entries_on(log, today) else last
    picked = date.fromisoformat(st.session_state.setdefault("prog_day", start))
    if "prog_month" not in st.session_state or st.session_state.get("prog_month_for") != start:
        st.session_state.prog_month, st.session_state.prog_month_for = (picked.year, picked.month), start
    year, month = st.session_state.prog_month

    def go(ym, day=None):
        st.session_state.prog_month = ym
        if day is not None:
            st.session_state.prog_day = day.isoformat()
        st.rerun()

    summary = history.month_summary(log, year, month, today)
    with st.container(key="cal_head", horizontal=True, vertical_alignment="center"):
        st.markdown(f"#### {calendar.month_name[month]} {year}")
        with st.container(key="cal_nav", horizontal=True, horizontal_alignment="right", gap="small"):
            if st.button("‹", key="cal_prev", disabled=(year, month) <= earliest):
                go(history.shift(year, month, -1))
            if st.button("Today", key="cal_today", disabled=(year, month) == now and picked == today):
                go(now, today)
            if st.button("›", key="cal_next", disabled=(year, month) >= now):
                go(history.shift(year, month, 1))
    st.caption(f"{days(summary['studied'])} studied · {days(summary['completed'])} completed · "
               f"{summary['lessons']} {'lesson' if summary['lessons'] == 1 else 'lessons'} passed")

    # weekday names, each with the subject that day of the week is for
    st.html('<div class="cal-week">' + "".join(
        f'<span><b>{name[:3]}</b><i>{history.short_topic(core.WEEKDAY_TOPIC[k])}</i></span>'
        for k, name in enumerate(core.WEEKDAYS)) + "</div>")
    with st.container(key="cal_month"):
        for w, week in enumerate(history.month_grid(log, year, month, today)):
            with st.container(key=f"calw_{w}", horizontal=True):
                for d in week:
                    name = (f"cal_{d['date'].isoformat()}_{d['status']}_a{history.amount(d)}"
                            + ("" if d["in_month"] else "_out") + ("_today" if d["date"] == today else "")
                            + ("_sel" if d["date"] == picked else ""))
                    # (no hover tip: Streamlit draws a second button for it; the day
                    # card says it all once the day is picked)
                    if st.button(str(d["date"].day), key=name, disabled=d["status"] == "future"):
                        go((d["date"].year, d["date"].month), d["date"])
    st.html('<div class="cal-key"><span><i class="k-done"></i>Completed</span>'
            '<span><i class="k-part"></i>Partly done</span>'
            '<span>The line under a day grows with the lessons passed</span></div>')

    # ---- the day picked ----
    with st.container(key="prog_day"):
        stats = history.day_stats(log, picked, today)
        st.markdown(f"#### {core.weekday_name(picked)}, {picked:%B} {picked.day}"
                    + (f", {picked.year}" if picked.year != today.year else ""))
        on_day = history.entries_on(log, picked)
        if not on_day:
            planned = core.TOPICS[core.scheduled_topic(picked)]
            st.caption(f"Nothing recorded. {core.weekday_name(picked)}s are for {planned}."
                       if stats["status"] != "future" else f"Coming up: {planned}.")
        else:
            st.caption({"done": "Completed", "partial": "Partly done"}.get(stats["status"], "")
                       + (f" · {stats['done']} of {stats['total']} lessons passed" if stats["total"] else ""))
            for e in on_day:
                show_entry(e, "day")

    # ---- every session, newest first, a page at a time ----
    PAGE = 10
    if log["entries"]:
        with st.container(key="sessions_head", horizontal=True, vertical_alignment="bottom"):
            st.markdown("#### Every session")
            topic_filter = st.selectbox(
                "Subject",
                ["all", *core.TOPICS],
                format_func=lambda k: "All subjects" if k == "all" else core.TOPICS[k],
                label_visibility="collapsed",
                key="sessions_topic",
            )
        entries = [e for e in reversed(log["entries"])
                   if topic_filter == "all" or e["topic"] == topic_filter]
        if not entries:
            st.caption("Nothing recorded for this subject yet.")
        shown = st.session_state.setdefault("sessions_shown", PAGE)
        with st.container(key="sessions_list"):
            for e in entries[:shown]:
                day = date.fromisoformat(e["date"])
                mark = "●" if e.get("completed") else "○"
                title = e.get("title") or core.TOPICS[e["topic"]]
                with st.expander(f"{mark} {core.weekday_name(day)[:3]}, {day:%b} {day.day}, {day.year} · {title}"):
                    show_entry(e, "list")
        if len(entries) > shown:
            if st.button(f"Show {min(PAGE, len(entries) - shown)} more of {len(entries) - shown}", key="sessions_more"):
                st.session_state.sessions_shown = shown + PAGE
                st.rerun()


with subjects_col:
    # ---- each subject: the unit she's in now ----
    st.markdown("#### By subject")
    st.caption(f"Each bar is the unit you're in now. Every subject has {curriculum.TOTAL:,} lessons taken in "
               f"order: lessons 1–{curriculum.LEVEL_SIZE:,} are Beginner, {curriculum.LEVEL_SIZE + 1:,}–"
               f"{2 * curriculum.LEVEL_SIZE:,} Intermediate, the rest Advanced. Reading follows the book "
               f"you're reading.")
    for key, label in core.TOPICS.items():
        if curriculum.has_syllabus(key):
            p = curriculum.progress(log, key)
            unit = curriculum.unit_progress(log, key)
            progress_bar.render(
                f"course_{key}", unit["unit"], unit["done"], unit["total"],
                f"{p['done']:,} of {p['total']:,} overall · {p['level']}",
                label=label, compact=True,
            )
            continue
        # Reading has no syllabus: its bar is the book she is reading now.
        book = books.current_book(log["books"])
        finished = sum(1 for b in log["books"] if b["status"] == "finished")
        shelf_note = f"{finished} {'book' if finished == 1 else 'books'} finished"
        if book and book["status"] == "reading":
            reading_days = [d for d in range(1, books.DAYS + 1) if book["plan"][d - 1]]
            done = len([d for d in reading_days if str(d) in book["checks"]])
            progress_bar.render(f"course_{key}", book["title"] or "(untitled)", done, len(reading_days),
                                shelf_note, label=label, compact=True, noun="reading day")
        else:
            progress_bar.render(f"course_{key}", "No book in progress", 0, 1, shelf_note,
                                label=label, compact=True, left="Start one on the Reading page")

    # ---- bookshelf ----
    shelf = [b for b in log["books"] if b["status"] in ("reading", "finished", "switched")]
    if shelf:
        st.markdown("#### Bookshelf")
        for b in reversed(shelf):
            passed = len(b["checks"])
            reading_days = len([d for d in b["plan"] if d])
            status = {
                "setup": "setting up",
                "planning": "planning",
                "reading": f"reading · {passed} of {reading_days} reading days confirmed",
                "finished": f"finished {b['finished_on']}",
                "switched": f"switched to another book after day {passed}",
            }[b["status"]]
            author = f" by {b['author']}" if b["author"] else ""
            with st.expander(f"{b['title'] or '(untitled)'}{author} · {status}"):
                if b["plan"]:
                    st.markdown(books.plan_table(b))
                for day, check in sorted(b["checks"].items(), key=lambda kv: int(kv[0])):
                    st.markdown(f"**Day {day}** ({check['passed_on']}): {check['summary']}")
                if b.get("final_summary"):
                    with st.container(border=True):
                        st.markdown(b["final_summary"])

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
