import json
from datetime import date

import streamlit as st

from coach import books, core, curriculum, lesson_view, progress_bar, rolling, ui

log = st.session_state.coach_log
today = ui.today()

st.markdown("## Progress")

if not log["entries"]:
    st.info("No records yet. They start building up after your first lesson.")

# ============================================================
# OVERVIEW
# ============================================================
def days(n):
    return f"{n} {'day' if n == 1 else 'days'}"


figures = {
    "Current streak": days(core.current_streak(log, today)),
    "Longest streak": days(core.longest_streak(log)),
    "Days completed": days(len(core.completed_dates(log))),
    "Days studied": days(len({e['date'] for e in log['entries']})),
}
before = progress_bar.seen("progress_figures", **{k.replace(" ", "_"): v for k, v in figures.items()})
st.html('<div class="figures">' + "".join(          # numbers roll when they change
    f'<div class="figure"><div class="figure-label">{label}</div>'
    f'<div class="figure-value">{rolling.html(value, before.get(label.replace(" ", "_")))}</div></div>'
    for label, value in figures.items()) + "</div>")

# ============================================================
# LAST FOUR WEEKS
# ============================================================
st.markdown("#### Last four weeks")
weeks = core.calendar_weeks(log, today, weeks=4)
first = weeks[0][0][0]
cells = [f'<span class="cal-wd">{d[:3]}</span>' for d in core.WEEKDAYS]
for week in weeks:
    for day, status in week:
        label = f"{day.month}/{day.day}" if day.day == 1 else str(day.day)
        classes = f"cal-day {status}" + (" today" if day == today else "")
        cells.append(f'<span class="{classes}" title="{day.isoformat()}"><b>{label}</b><i></i></span>')
st.html(
    '<div class="cal">'
    f'<div class="cal-head"><span class="cal-month">{progress_bar.rolled("cal_month", f"{today:%B %Y}")}</span>'
    f'<span class="cal-range">{progress_bar.rolled("cal_range", f"{first:%b} {first.day} – {today:%b} {today.day}")}</span></div>'
    f'<div class="cal-grid">{"".join(cells)}</div>'
    '<div class="cal-legend"><span><i style="background:var(--label)"></i>Completed</span>'
    '<span><i style="border:1px solid var(--label-2)"></i>Studied, not finished</span></div>'
    '</div>'
)

# ============================================================
# PER-TOPIC PROGRESS
# ============================================================
st.markdown("#### Progress by subject")
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

# ============================================================
# BOOKSHELF
# ============================================================
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
# HISTORY
# ============================================================
st.markdown("#### Every session")
topic_filter = st.selectbox(
    "Subject",
    ["all", *core.TOPICS],
    format_func=lambda k: "All" if k == "all" else core.TOPICS[k],
)
entries = [e for e in reversed(log["entries"])
           if topic_filter == "all" or e["topic"] == topic_filter]
if log["entries"] and not entries:
    st.caption("Nothing recorded for this subject yet.")

for e in entries:
    day = date.fromisoformat(e["date"])
    mark = "●" if e.get("completed") else "○"
    title = e.get("title") or core.TOPICS[e["topic"]]
    with st.expander(f"{mark} {core.weekday_name(day)[:3]}, {day:%b} {day.day}, {day.year} · {title}"):
        key = f"{e['date']}_{e['topic']}"
        if e.get("lessons"):
            # A syllabus day: done when every lesson is ticked on the daily page.
            curriculum.refresh_titles(e["topic"], e["lessons"])
            done_count = sum(1 for s in e["lessons"] if s["completed"])
            st.caption(f"{core.TOPICS[e['topic']]} · {e['level']} · {done_count} of {len(e['lessons'])} lessons done")
            for s in e["lessons"]:
                q = s.get("quiz") or {}
                score = f" · quiz {q['best']}%" if q.get("best") is not None else ""
                st.markdown(f"{'●' if s['completed'] else '○'} Lesson {s['n']}: {s['title']}{score}")
            show = st.toggle("Show the lessons", key=f"rec_lessons_{key}")
            for s in e["lessons"]:
                if show and s.get("lesson"):
                    with st.container(border=True):
                        st.markdown(f"**Lesson {s['n']}: {s['title']}**")
                        lesson_view.render(s["lesson"], e["topic"], key=f"rec_{key}_{s['n']}")
            if e.get("followup_question"):
                st.markdown(f"**Question to explore:** {e['followup_question']}")
            continue
        st.caption(f"{core.TOPICS[e['topic']]} · session {e['session_number']} · {e['level']}")
        st.caption("Finished" if e.get("completed") else "Not finished")
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
# BACKUP
# ============================================================
st.divider()
st.markdown("#### Backup")
if ui.using_cloud():
    st.caption("Your records are in the Supabase database, so they survive app restarts. Download a copy if you'd like one of your own.")
else:
    st.caption("Your records are on the app's server and may be wiped when Streamlit Cloud restarts, so download a backup now and then.")
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
