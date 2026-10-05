"""Her week in review (coach/habit.py): what she learned, how it went
against the week before, what's worth a second look, and one gentle idea
for the week ahead. Worked out from her record: no AI call. This week so
far, or the week before; opening it marks the finished week as seen (Today
stops pointing to it)."""
from datetime import timedelta
from html import escape

import streamlit as st

from coach import core, habit, mastery, streaks, ui

log = st.session_state.coach_log
today = ui.today()
this_monday = habit.week_of(today)
last_monday = this_monday - timedelta(days=7)

st.html('<div id="week-page" hidden></div>')
st.markdown("## Your week")
choice = st.segmented_control("Week", ["This week", "Last week"], key="wk_which", required=True,
                              default=st.session_state.get("wk_default", "This week"), label_visibility="collapsed")
monday = this_monday if choice == "This week" else last_monday
if ui.prefs().get("week_seen") != habit.week_key(last_monday):        # the finished week, now seen
    ui.update_prefs(week_seen=habit.week_key(last_monday))
w = habit.week(log, monday, today)


def figure(label, value, was=None, unit=""):
    change = ""
    if was is not None and value is not None and was != value:
        change = f'<small>{"+" if value > was else "−"}{abs(value - was)}{unit} on the week before</small>'
    shown = "—" if value is None else f"{value}{unit}"
    return f'<div class="figure"><div class="figure-label">{escape(label)}</div><div class="figure-value">{shown}</div>{change}</div>'


span = f"{w['monday']:%B} {w['monday'].day} – {w['end']:%B} {w['end'].day}"
st.html(f'<p class="wk-span">{escape(span)}{"" if w["over"] or choice == "Last week" else " · so far"}</p>')
finished = choice == "Last week"          # (a week still going isn't set against a whole one: never a "−18")
st.html('<div class="figures wk-figures">'
        + figure("Days you studied", w["days"], w["days_before"] if finished else None)
        + figure("Lessons passed", w["lessons"], w["lessons_before"] if finished else None)
        + figure("Quiz average", w["quiz_avg"], w["quiz_avg_before"] if finished else None, "%")
        + figure("Current streak", w["streak"]) + "</div>")

with st.container(key="wk_body"):
    st.markdown("#### What you learned")
    if not w["learned"]:
        st.html('<p class="wk-note">Nothing yet this week. That\'s fine: one lesson is a good start.</p>'
                if choice == "This week" else '<p class="wk-note">A quiet week.</p>')
    for item in w["learned"]:
        st.html(f'<div class="wk-subject"><p class="wk-name">{escape(item["name"])}</p><ul>'
                + "".join(f"<li>{escape(t)}</li>" for t in item["titles"]) + "</ul></div>")

    st.markdown("#### What you know")
    moved = mastery.changes(log, monday, min(w["end"], today))
    if moved["up"]:
        st.html(f'<p class="wk-idea">{moved["up"]} {"idea" if moved["up"] == 1 else "ideas"} grew stronger'
                + (f', {moved["mastered"]} of them now mastered' if moved["mastered"] else "") + ".</p>")
    else:
        st.html('<p class="wk-note">No idea moved up a level yet this week. Review and Practice are how '
                "ideas grow from learning to solid to mastered.</p>" if choice == "This week" else
                '<p class="wk-note">No idea moved up a level that week.</p>')
    shaky = mastery.needs_practice(log, today)[:3]
    if shaky:
        st.html('<p class="wk-note">Shaky now: ' + ", ".join(f"“{escape(x['title'])}”" for _, _, x in shaky) + ".</p>")
    if st.button("Skill map", type="tertiary", key="wk_skills"):
        st.switch_page("views/skills.py")

    st.markdown("#### Worth a second look")
    if w["review"]:
        st.html('<ul class="wk-review">' + "".join(
            f'<li><span>{escape(r["title"])}</span><small>{escape(r["name"])} · best {r["score"]}%</small></li>'
            for r in w["review"]) + "</ul>")
    else:
        st.html('<p class="wk-note">Every lesson you passed this week went well. Review keeps it that way.</p>')
    if st.button("Open Review", type="tertiary", key="wk_review"):
        st.switch_page("views/review.py")

    st.markdown("#### For the week ahead")
    st.html(f'<p class="wk-idea">{escape(w["suggestion"])}</p>'
            f'<p class="wk-note">{escape(streaks.explain(streaks.walk(core.streak_dates(log), today)))}</p>')
