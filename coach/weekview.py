"""Her week in review (coach/habit.py), shown in the Learning Record
(views/records.py, its "Your week" tab): what she learned, how it went
against the week before, what's worth a second look, and one gentle idea
for the week ahead. Worked out from her record: no AI call. This week so
far, or the week before; showing it marks the finished week as seen (Home
stops pointing to it)."""
from datetime import timedelta
from html import escape

import streamlit as st

from coach import core, habit, mastery, streaks, ui
from coach import i18n
from coach.i18n import N_, tr, trn


def _figure(label, value, was=None, unit=""):
    change = ""
    if was is not None and value is not None and was != value:
        change = "<small>" + tr("{change} on the week before", change=f'{"+" if value > was else "−"}{abs(value - was)}{unit}') + "</small>"
    shown = "—" if value is None else f"{value}{unit}"
    return f'<div class="figure"><div class="figure-label">{escape(tr(label))}</div><div class="figure-value">{shown}</div>{change}</div>'


def render(log: dict) -> None:
    today = ui.today()
    this_monday = habit.week_of(today)
    last_monday = this_monday - timedelta(days=7)

    st.html('<div id="week-page" hidden></div>')
    st.session_state.setdefault("wk_which", "This week")
    choice = st.segmented_control(tr("Week"), [N_("This week"), N_("Last week")], key="wk_which", required=True,
                                  label_visibility="collapsed", format_func=tr)
    monday = this_monday if choice == "This week" else last_monday
    if ui.prefs().get("week_seen") != habit.week_key(last_monday):        # the finished week, now seen
        ui.update_prefs(week_seen=habit.week_key(last_monday))
    w = habit.week(log, monday, today)

    span = f"{i18n.date_long(w['monday'], year=False)} – {i18n.date_long(w['end'], year=False)}"
    st.html(f'<p class="wk-span">{escape(span)}{"" if w["over"] or choice == "Last week" else " · " + tr("so far")}</p>')
    finished = choice == "Last week"          # (a week still going isn't set against a whole one: never a "−18")
    st.html('<div class="figures wk-figures">'
            + _figure(N_("Days you studied"), w["days"], w["days_before"] if finished else None)
            + _figure(N_("Lessons passed"), w["lessons"], w["lessons_before"] if finished else None)
            + _figure(N_("Quiz average"), w["quiz_avg"], w["quiz_avg_before"] if finished else None, "%")
            + _figure(N_("Current streak"), w["streak"]) + "</div>")

    with st.container(key="wk_body"):
        st.markdown(tr("#### What you learned"))
        if not w["learned"]:
            st.html(tr('<p class="wk-note">Nothing yet this week. That\'s fine: one lesson is a good start.</p>')
                    if choice == "This week" else tr('<p class="wk-note">A quiet week.</p>'))
        for item in w["learned"]:
            st.html(f'<div class="wk-subject"><p class="wk-name">{escape(item["name"])}</p><ul>'
                    + "".join(f"<li>{escape(t)}</li>" for t in item["titles"]) + "</ul></div>")

        st.markdown(tr("#### What you know"))
        moved = mastery.changes(log, monday, min(w["end"], today))
        if moved["up"]:
            st.html('<p class="wk-idea">' + (trn("{n} idea grew stronger.", "{n} ideas grew stronger.", moved["up"])
                                             if not moved["mastered"] else
                                             trn("{n} idea grew stronger, {mastered} of them now mastered.",
                                                 "{n} ideas grew stronger, {mastered} of them now mastered.", moved["up"],
                                                 mastered=moved["mastered"])) + "</p>")
        else:
            st.html(tr('<p class="wk-note">No idea moved up a level yet this week. Review and Practice are how '
                    "ideas grow from learning to solid to mastered.</p>") if choice == "This week" else
                    tr('<p class="wk-note">No idea moved up a level that week.</p>'))
        shaky = mastery.needs_practice(log, today)[:3]
        if shaky:
            st.html('<p class="wk-note">' + tr("Shaky now: {ideas}.", ideas=", ".join(f"“{escape(x['title'])}”" for _, _, x in shaky)) + "</p>")
        if st.button(tr("Learning map"), type="tertiary", key="wk_skills"):
            st.switch_page("views/skills.py")

        st.markdown(tr("#### Worth a second look"))
        if w["review"]:
            st.html('<ul class="wk-review">' + "".join(
                f'<li><span>{escape(r["title"])}</span><small>{escape(r["name"])} · {tr("best {score}%", score=r["score"])}</small></li>'
                for r in w["review"]) + "</ul>")
        else:
            st.html(tr('<p class="wk-note">Every lesson you passed this week went well. Review keeps it that way.</p>'))
        if st.button(tr("Open Review"), type="tertiary", key="wk_review"):
            st.switch_page("views/review.py")

        st.markdown(tr("#### For the week ahead"))
        st.html(f'<p class="wk-idea">{escape(w["suggestion"])}</p>'
                f'<p class="wk-note">{escape(streaks.explain(streaks.walk(core.streak_dates(log), today)))}</p>')
