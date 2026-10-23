"""The capstone (coach/capstone.py): a goal's (or a math phase's) applied
task, written for her once she has done every lesson, the work she hands
in, and feedback on it against its rubric. Two calls; done in her own time."""
from html import escape

import streamlit as st

from coach import attempts, capstone, catalog, clock, llm, ui
from coach.i18n import tr

log = st.session_state.coach_log
today = ui.today()
topic = st.query_params.get("subject") or st.session_state.get("course_topic")
key = st.query_params.get("key") or topic
st.html('<div id="capstone-page" hidden></div>')
st.html('<p class="cm-eyebrow">' + tr("Capstone") + "</p>")

open_ = {c["key"]: c for c in capstone.offered(log, topic)} if topic and catalog.known(topic) else {}
mine = (ui.prefs().get("capstones") or {}).get(key)
if key not in open_ and mine is None:
    st.markdown(tr("## Not open yet"))
    st.caption(tr("The capstone opens once every lesson of your goal is done: one real task that uses all of it."))
    if st.button(tr("Back to Home"), type="tertiary", key="cp_back_none"):
        st.switch_page("views/daily.py")
    st.stop()

offer = open_.get(key) or {"title": catalog.name(topic), "outcomes": [], "why": ""}
st.markdown(f"## {offer['title']}")


def keep(value) -> bool:
    every = dict(ui.prefs().get("capstones") or {})
    every[key] = value
    return ui.update_prefs(capstones=every)


if mine is None:
    st.html('<p class="ss-sub">' + tr("You've done every lesson. The last step is to use it: one real task, built "
                                      "from what this path taught and why you started it. It takes 30 to 90 "
                                      "minutes, in your own time.") + "</p>")
    spot = st.empty()
    if spot.button(tr("Write my capstone brief"), type="primary", key="cp_brief"):
        spot.button(tr("Writing your brief…"), disabled=True, key="cp_brief_wait")
        system, messages = capstone.brief_request(offer["title"], offer["outcomes"], offer["why"])
        data, error = llm.ask_json(system, messages, max_tokens=1400)
        brief = capstone.read_brief(data) if data else None
        if brief is None:
            st.warning(error or llm.FAILED)
            st.stop()
        keep({"brief": brief, "work": "", "feedback": None, "at": "", "tries": 0})
        st.rerun()
    st.stop()

brief = mine["brief"]
with st.container(key="cp_brief_card"):
    st.markdown(f"### {brief['title']}")
    st.markdown(brief["situation"])
    st.markdown(f"**{tr('Your task')}:** {brief['task']}")
    st.markdown("\n".join(f"{k}. {x}" for k, x in enumerate(brief["steps"], start=1)))
    st.html('<p class="hb-eyebrow">' + tr("What good work shows") + "</p><ul class=\"cp-rubric\">"
            + "".join(f"<li><b>{escape(r['criterion'])}</b> {escape(r['good'])}</li>" for r in brief["rubric"]) + "</ul>")

fb = mine.get("feedback")
if fb:
    with st.container(key="cp_feedback"):
        st.markdown(tr("### Feedback"))
        names = {"met": tr("Met"), "partly": tr("Partly"), "not_yet": tr("Not yet")}
        st.html('<ul class="cp-levels">' + "".join(
            f'<li class="{c["level"]}"><span>{escape(names[c["level"]])}</span><b>{escape(c["criterion"])}</b> {escape(c["why"])}</li>'
            for c in fb["criteria"]) + "</ul>")
        if fb.get("overall"):
            st.markdown(fb["overall"])
        if fb.get("next"):
            st.markdown(f"**{tr('Next step')}:** {fb['next']}")
        st.caption(tr("You handed this in on {day}.", day=mine["at"][:10]))
    if mine.get("tries", 0) >= 2:
        st.stop()
    st.caption(tr("You can improve it and hand it in once more."))

work = st.text_area(tr("Your work"), value=mine.get("work", ""), height=280, key=f"cp_work_{key}",
                    max_chars=capstone.MAX_WORK, placeholder=tr("Write or paste what you made…"))
spot = st.empty()
if spot.button(tr("Hand it in for feedback"), type="primary", key="cp_send", disabled=len((work or "").split()) < 40):
    spot.button(tr("Reading your work…"), disabled=True, key="cp_send_wait")
    system, messages = capstone.feedback_request(brief, work)
    data, error = llm.ask_json(system, messages, max_tokens=1400)
    got = capstone.read_feedback(data, brief) if data else None
    if got is None:
        st.warning(error or llm.FAILED)
        st.stop()
    keep(dict(mine, work=work.strip(), feedback=got, at=clock.now_iso(), tries=mine.get("tries", 0) + 1))
    ui.attempt([attempts.row(today, topic, 0, "explain", "explain", score=capstone.score(got))])
    st.rerun()
if len((work or "").split()) < 40:
    st.caption(tr("A few paragraphs at least, so the feedback has something to go on."))
