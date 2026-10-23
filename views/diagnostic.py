"""Where to start (coach/diagnostic.py): a few questions on a goal's units,
chosen one by one, to skip what she already knows. No right or wrong is
shown as she goes; at the end she sees where she starts and what she
skips, and chooses: from there, or from the beginning. Its questions are
written a few at a time (two calls each) and, for the mathematics
curriculum, shared (coach/itembank.py)."""
from html import escape

import streamlit as st

from coach import attempts, catalog, diagnostic, exercise, i18n, itembank, llm, quiz, session_ui, ui
from coach.i18n import tr, trn

log = st.session_state.coach_log
today = ui.today()
topic = st.query_params.get("subject") or st.session_state.get("course_topic")
st.html('<div id="diagnostic-page" hidden></div>')
st.html('<p class="cm-eyebrow">' + tr("Where to start") + "</p>")

if not topic or not catalog.known(topic) or not diagnostic.offered(topic):
    st.markdown(tr("## Nothing to place here"))
    st.caption(tr("A starting-point check is offered for a goal of yours and for the mathematics curriculum."))
    if st.button(tr("Back to Home"), type="tertiary", key="dg_back_none"):
        st.switch_page("views/daily.py")
    st.stop()

us = diagnostic.units(topic)
st.markdown(f"## {catalog.name(topic)}")


def stored():
    ui.load_prefs()
    return (ui.prefs().get("diag") or {}).get(topic)


def keep(state) -> bool:
    every = dict(ui.prefs().get("diag") or {})
    every[topic] = state
    return ui.update_prefs(diag=every)


def write_items(state, ids) -> bool:
    """Questions for these units: the shared bank's first, the rest written and
    checked now (two calls), then kept (and shared, for the curriculum)."""
    lang = i18n.current()
    shared = itembank.MATH if topic == "math" else None
    have = {}
    if shared:
        for uid, (q, item_id) in itembank.get(shared, lang, ids).items():
            have[uid] = q
            if item_id is not None:
                state.setdefault("bank", {})[uid] = item_id
    need = [k for k in ids if k not in have and k not in state["items"]]
    if need:
        system, messages = diagnostic.write_request(us, need)
        with st.spinner(tr("Writing the next questions…")):
            data, error = llm.ask_json(system, messages, max_tokens=1800, salvage=quiz.salvage)
        written = diagnostic.read_written(data, need) if data else {}
        if written:
            ordered = list(written.items())
            system, messages = quiz.check_request([q for _, q in ordered])
            with st.spinner(tr("Checking every answer…")):
                verdict, error = llm.ask_json(system, messages)
            flagged = quiz.problems(verdict, len(ordered)) if verdict else None
            if flagged is None:
                written = {}
            else:
                written = {uid: q for k, (uid, q) in enumerate(ordered) if k not in flagged}
                if shared:
                    itembank.add(shared, lang, written)
        if error and not written and not have:
            st.session_state.dg_problem = error
        have.update(written)
    state["items"].update(have)
    return bool(have) or not need


state = stored()
problem = st.session_state.pop("dg_problem", "")

# ------------------------------------------------------------------ the start
if state is None or (not state["asked"] and not state["done"] and not st.session_state.get("dg_going")):
    st.html('<p class="ss-sub">' + tr("A few questions on this path, about five minutes. Each one decides the next, so "
                                      "you'll only see what tells us something. Answer what you can: “I don't know yet” "
                                      "is a fine answer. Then you skip what you already know.") + "</p>")
    if problem:
        st.warning(problem)
    with st.container(key="dg_start", horizontal=True):
        if st.button(tr("Find my starting point"), type="primary", key="dg_go"):
            st.session_state.dg_going = True
            keep(diagnostic.blank(today))
            st.rerun()
        if st.button(tr("Start from the beginning"), type="tertiary", key="dg_skip"):
            st.switch_page("views/daily.py")
    st.stop()

# ------------------------------------------------------------------ the result
if state["done"]:
    known = set(state["known"])
    skipped = [u for u in us if u["id"] in known]
    start = next((u for u in us if u["first"] <= state["start"] <= u["last"]), None)
    if state["applied"]:
        st.html('<p class="ss-sub">' + tr("Your path starts from your result.") + "</p>")
    with st.container(key="dg_result"):
        if skipped:
            st.markdown(trn("### You can skip {n} unit", "### You can skip {n} units", len(skipped)))
            st.caption(trn("{n} lesson you already know.", "{n} lessons you already know.", len(state["skip"])))
            st.html('<ul class="dg-known">' + "".join(f"<li>{escape(u['name'])}</li>" for u in skipped[:30]) + "</ul>")
        else:
            st.markdown(tr("### Start from the beginning"))
            st.caption(tr("Every unit has something new for you. The first lessons will move quickly if you know a little."))
        if start is not None:
            st.html('<p class="ss-sub">' + tr("You start at Lesson {n}, in “{unit}”.", n=state["start"], unit=escape(start["name"]))
                    + "</p>")
        st.caption(tr("In a week, one question on a unit you skipped comes back in your warm-up, to be sure. "
                      "Missed, its lessons come back into your path."))
    if not state["applied"]:
        with st.container(key="dg_choose", horizontal=True):
            if st.button(tr("Start from there"), type="primary", key="dg_apply", disabled=not skipped):
                keep(diagnostic.spot_checks(state, us, today))
                st.session_state.coach_toast = tr("Your path now starts at Lesson {n}.", n=state["start"])
                st.switch_page("views/daily.py")
            if st.button(tr("Start from the beginning"), type="tertiary", key="dg_none"):
                keep(dict(state, skip=[], applied=True, spot=[]))
                st.switch_page("views/daily.py")
    else:
        if st.button(tr("Back to Home"), type="primary", key="dg_home"):
            st.switch_page("views/daily.py")
    st.stop()

# ------------------------------------------------------------------ a question
uid = diagnostic.next_unit(us, set(state["known"]), set(state["unknown"]), len(state["asked"]))
if uid is None:
    keep(diagnostic.finish(state, us))
    st.rerun()
if uid not in state["items"]:
    if not write_items(state, diagnostic.ahead(us, set(state["known"]), set(state["unknown"]), len(state["asked"]))):
        st.warning(st.session_state.pop("dg_problem", "") or tr("The questions couldn't be written just now. Try again in a moment."))
        st.button(tr("Try again"), key="dg_retry")
        st.stop()
    keep(state)
if uid not in state["items"]:                 # (its question didn't pass the check: settled as not known)
    keep(diagnostic.answer(state, us, uid, False))
    st.rerun()

q = state["items"][uid]
unit = next(u for u in us if u["id"] == uid)
asked = len(state["asked"])
session_ui.pace(asked, max(asked + 1, min(diagnostic.MAX_ITEMS, asked + 3)))
st.caption(tr("About: {unit}", unit=unit["name"]))
session_ui.shown(f"dg{asked}")
value = exercise.field(q, f"dg_{topic}_{asked}", None, tag=False)


def record(right: bool, conf=None) -> None:
    ui.attempt([attempts.row(today, topic, unit["first"], "diag", "choice", score=1.0 if right else 0.0,
                             conf=conf, secs=session_ui.seconds(f"dg{asked}"), diff=q.get("diff"))])
    keep(diagnostic.answer(state, us, uid, right))
    st.rerun()


got = session_ui.confidence_buttons(f"dg_{asked}", quiz.answered(q, value))
if got:
    record(quiz.mark(q, value) == 1, got)
with st.container(key="dg_tools", horizontal=True):
    if st.button(tr("I don't know yet"), type="tertiary", key=f"dg_idk_{asked}"):
        record(False)
    shared_id = (state.get("bank") or {}).get(uid)
    if shared_id is not None and st.button(tr("This question is wrong"), type="tertiary", key=f"dg_bad_{asked}"):
        itembank.report(shared_id)
        state["items"].pop(uid, None)
        keep(state)
        st.toast(tr("Thanks. It won't be asked again."))
        st.rerun()
st.caption(tr("Nothing is marked as you go: this only finds where you start."))
