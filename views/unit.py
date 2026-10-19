"""A unit check (coach/unitcheck.py): once every lesson of a unit is
passed, ten questions she has met in its lessons, marked at once, 80% to
pass, a fresh set as often as she likes. Reached from the course map and
from Home when a unit has just been finished. No AI call."""
from datetime import date
import streamlit as st

from coach import catalog, course, curriculum, exercise, quiz, review, ui, unitcheck
from coach.i18n import tr, trn

log = st.session_state.coach_log
today = ui.today()

topic = st.query_params.get("subject") or st.session_state.get("course_topic")
key = st.query_params.get("unit", "")
unit = unitcheck.find(log, topic, key) if catalog.known(topic) and curriculum.has_syllabus(topic) else None

st.html('<div id="unit-page" hidden></div>')
st.html(tr('<p class="cm-eyebrow">Unit check</p>'))
if unit is None or not unitcheck.offered(log, topic, unit):
    st.markdown(tr("## Nothing to check here yet"))
    st.caption(tr("A unit check opens once every lesson of a unit is passed, with questions from those lessons."))
    if st.button(tr("Back to Home"), type="tertiary", key="uc_back_none"):
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
st.caption(tr('{p0} · lessons {p1}–{p2}{status}', p0=catalog.name(topic), p1=unit['first'], p2=unit['last'], status=status))
st.html(tr('<p class="ob-note">{n_items} questions from this unit\'s lessons, to show you\'ve learned it as a whole. {p0}% passes it. No time limit.</p>', n_items=n_items, p0=unitcheck.PASS_MARK))


def back() -> None:
    if st.button(tr("Back to the course map"), type="tertiary", key="uc_back"):
        st.session_state.pop("uc_marked", None)
        ui.open_course(topic)


def submit(items: list, answers: list) -> None:
    """Mark the set; for each lesson asked about, the evidence for the
    Knowledge Map and a review card for each question missed; the result on
    the unit's last lesson; then show how it went."""
    marks, percent = unitcheck.score(items, answers)
    attempt = unitcheck.result(log, topic, unit).get("attempts", 0)
    shown = unitcheck.by_lesson(items, marks)
    days, carded = {}, 0                             # each day touched, re-read once, saved once
    for n in sorted(set(shown) | {unit["last"]}):
        held = course.lesson_record(log, topic, n)
        if held is not None:
            days.setdefault(held[0]["date"], []).append(n)
    for day, ns in days.items():
        ui.refresh_entry(log, date.fromisoformat(day), topic)          # the day as stored now
        entry = None
        for n in ns:
            held = course.lesson_record(log, topic, n)
            if held is None:
                continue
            entry, slot = held[0], held[1]
            if n in shown:
                avg, asked = shown[n]
                ui.learned(slot, entry["date"], "recall", avg, source=f"unit-{key}-{attempt}")
                carded += review.add_missed(slot, asked, today, topic)
            if n == unit["last"]:
                unitcheck.record(slot, percent, today)
        if entry is not None:
            ui.save_day(log, entry, ns)
    st.session_state.uc_marked = {"unit": f"{topic}|{key}", "items": items, "answers": answers,
                                  "marks": marks, "percent": percent, "carded": carded}


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
        n = marked.get("carded", 0)
        if n:
            st.html(trn('<p class="ob-note">The question you missed is now in Review, to come back to.</p>', '<p class="ob-note">{n} questions you missed are now in Review, to come back to.</p>', n))
    with st.container(key="uc_answers"):
        for k, (it, a, m) in enumerate(zip(marked["items"], marked["answers"], marked["marks"]), start=1):
            with st.container(key=f"uc_a_{k}", gap=None):
                exercise.result(it["q"], a, m, k=k)
                st.caption(tr('From lesson {p0}', p0=it['n']))
    with st.container(key="uc_after", horizontal=True):
        if st.button(tr("Try a new set"), type="primary" if not ok else "secondary", key="uc_again"):
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
    if st.button(tr("Check my answers"), type="primary", key="uc_check", disabled=bool(left)):
        submit(items, answers)
        st.rerun()
    if left:
        st.html(trn('<p class="ob-note">{n} question still to answer</p>', '<p class="ob-note">{n} questions still to answer</p>', left))
back()
st.html(tr('<p class="ob-note">Questions come from what you have already met; ones you reported are left out.</p>'))
