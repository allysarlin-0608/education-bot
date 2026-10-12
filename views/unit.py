"""A unit check (coach/unitcheck.py): once every lesson of a unit is
passed, ten questions she has met in its lessons, marked at once, 80% to
pass, a fresh set as often as she likes. Reached from the course map and
from Home when a unit has just been finished. No AI call."""
from datetime import date
import streamlit as st

from coach import catalog, course, curriculum, exercise, quiz, ui, unitcheck

log = st.session_state.coach_log
today = ui.today()

topic = st.query_params.get("subject") or st.session_state.get("course_topic")
key = st.query_params.get("unit", "")
unit = unitcheck.find(log, topic, key) if catalog.known(topic) and curriculum.has_syllabus(topic) else None

st.html('<div id="unit-page" hidden></div>')
st.html('<p class="cm-eyebrow">Unit check</p>')
if unit is None or not unitcheck.offered(log, topic, unit):
    st.markdown("## Nothing to check here yet")
    st.caption("A unit check opens once every lesson of a unit is passed, with questions from those lessons.")
    if st.button("Back to Home", type="tertiary", key="uc_back_none"):
        st.switch_page("views/daily.py")
    st.stop()

st.markdown(f"## {unit['name']}")
done = unitcheck.result(log, topic, unit)
n_items = unitcheck.size(log, topic, unit)
status = ""
if done.get("passed_on"):
    status = f" · passed on {course.short_date(done['passed_on'])}, best {done['best']}%"
elif done.get("attempts"):
    status = f" · best so far {done['best']}%"
st.caption(f"{catalog.name(topic)} · lessons {unit['first']}–{unit['last']}{status}")
st.html(f'<p class="ob-note">{n_items} questions from this unit\'s lessons, to show you\'ve learned it as a whole. '
        f"{unitcheck.PASS_MARK}% passes it. No time limit.</p>")


def back() -> None:
    if st.button("Back to the course map", type="tertiary", key="uc_back"):
        st.session_state.pop("uc_marked", None)
        ui.open_course(topic)


def submit(items: list, answers: list) -> None:
    """Mark the set, keep the result on the unit's last lesson, show how it went."""
    marks, percent = unitcheck.score(items, answers)
    held = unitcheck.holder(log, topic, unit)
    if held is not None:
        ui.refresh_entry(log, date.fromisoformat(held[0]["date"]), topic)     # the day as stored now
        held = unitcheck.holder(log, topic, unit)
    if held is not None:
        unitcheck.record(held[1], percent, today)
        ui.save_day(log, held[0], [unit["last"]])
    st.session_state.uc_marked = {"unit": f"{topic}|{key}", "items": items, "answers": answers,
                                  "marks": marks, "percent": percent}


# ------------------------------------------------------------ a set just marked
marked = st.session_state.get("uc_marked")
if marked and marked["unit"] == f"{topic}|{key}":
    ui.show_pending_error()
    ok = quiz.passed(marked["percent"])
    right = sum(1 for m in marked["marks"] if m == 1)
    with st.container(key="uc_result"):
        st.markdown(f"### {marked['percent']}% · {'Passed' if ok else 'Not yet'}")
        st.html(f'<p class="ob-note">{right} of {len(marked["marks"])} fully right. '
                + ("You know this unit as a whole. Review keeps it that way." if ok else
                   f"You need {unitcheck.PASS_MARK}%. Look again at the lessons of the questions you missed, "
                   "then try a new set.") + "</p>")
    with st.container(key="uc_answers"):
        for k, (it, a, m) in enumerate(zip(marked["items"], marked["answers"], marked["marks"]), start=1):
            with st.container(key=f"uc_a_{k}", gap=None):
                exercise.result(it["q"], a, m, k=k)
                st.caption(f"From lesson {it['n']}")
    with st.container(key="uc_after", horizontal=True):
        if st.button("Try a new set", type="primary" if not ok else "secondary", key="uc_again"):
            st.session_state.pop("uc_marked", None)
            st.rerun()
        back()
    st.stop()

# ------------------------------------------------------------ the set
attempt = done.get("attempts", 0)
items = unitcheck.build(log, topic, unit, attempt)
answers = []
with st.container(key="uc_set"):
    for k, it in enumerate(items, start=1):
        with st.container(key=f"uc_q_{k}"):
            answers.append(exercise.field(it["q"], f"uc_{key}_{attempt}_{k}", k=k))
left = sum(1 for it, a in zip(items, answers) if not quiz.answered(it["q"], a))
with st.container(key="uc_send", horizontal=True, vertical_alignment="center"):
    if st.button("Check my answers", type="primary", key="uc_check", disabled=bool(left)):
        submit(items, answers)
        st.rerun()
    if left:
        st.html(f'<p class="ob-note">{left} {"question" if left == 1 else "questions"} still to answer</p>')
back()
st.html('<p class="ob-note">Questions come from what you have already met; ones you reported are left out.</p>')
