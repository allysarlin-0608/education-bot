"""A subject's course map: the whole path, and where she is on it.

The units of the syllabus in order: the ones she has finished folded to a
line each, the one she is in and the next open, the rest of the course
gathered at the end. A lesson she has written (passed or not) opens to be
read again with its quiz and her notes; the lesson she is on goes straight
to Today. Lessons not reached show their titles only: they are written
when she gets to them, so the map never costs a model call."""
from datetime import date
from html import escape

import streamlit as st

from coach import (capstone, catalog, core, diagnostic, i18n, course, curriculum, habit, lesson_view, mastery, practice,
                   progression, quiz, review, settings, ui, unitcheck, visuals)
from coach.i18n import N_, tr, trn

log = st.session_state.coach_log
config = ui.config()
today = ui.today()
mine = settings.shown_subjects(config)

# the subject: named in the address (a link, a refresh), else her session, else today's
asked = st.query_params.get("subject")
# (a subject, or one of her goals)
topic = asked if catalog.known(asked) and curriculum.has_syllabus(asked) else st.session_state.get("course_topic")
if not (catalog.known(topic) and curriculum.has_syllabus(topic)):
    topic = ui.topic_for(today) if catalog.known(ui.topic_for(today)) else (mine[0] if mine else "philosophy")
st.session_state.course_topic = topic
if asked != topic:
    st.query_params["subject"] = topic

is_today = ui.topic_for(today) == topic
plan = curriculum.day_plan(log, topic, core.find_entry(log, today, topic), ui.units_today()) if is_today else []
m = course.build(log, topic, plan)
level = core.lesson_level(min(m["done"] + 1, curriculum.TOTAL), settings.start_level(config, topic), topic)
st.html('<div id="course-page"></div>')


# ============================================================
# A LESSON, OPENED: read it again, its quiz, her notes
# ============================================================
@st.dialog(tr("Lesson"), width="large")
def open_lesson(n):
    found = course.lesson_record(log, topic, n)
    if found is None:
        st.caption(tr("This lesson hasn't been written yet."))
        return
    entry, slot, passed = found
    st.markdown(tr('### Lesson {n}: {p0}', n=n, p0=slot['title']))
    aim = catalog.goal_objective(topic, n)
    if aim:
        st.html(tr('<p class="lesson-aim"><span>You\'ll be able to</span>{p0}</p>', p0=escape(aim)))
    q = slot.get("quiz") or {}
    meta = [slot.get("unit") or ""]
    meta.append(tr("passed {date}", date=course.short_date(passed)) if passed else
                tr("started {date}", date=course.short_date(entry['date'])))
    if q.get("best") is not None:
        meta.append(tr("best {score}%", score=q['best']))
    st.caption(" · ".join(x for x in meta if x))
    read, quiz_tab, notes = st.tabs([tr("Lesson"), tr("Quiz"), tr("Notes")])
    with read:
        lesson_view.render_tabs(slot["lesson"], topic, key=f"cm_{topic}_{n}", title=slot.get("title", ""))
    with quiz_tab:
        if q and q.get("answers") is not None and q.get("score") is None:
            st.caption(tr("Your last answers are in, but the short answers weren't marked yet: they're marked on Home."))
        elif not q or q.get("answers") is None:
            st.caption(tr("No quiz taken on this lesson yet.") if not passed else tr("Passed before quizzes were kept."))
        else:
            attempts = q.get("attempts") or 1
            st.markdown(trn('**Last attempt: {score}%** · {points} points · {n} attempt, best {best}%', '**Last attempt: {score}%** · {points} points · {n} attempts, best {best}%', attempts, score=q.get('score'), points=quiz.points(q), best=q.get('best')))
            for k, item in enumerate(q["questions"]):
                mark = (q.get("marks") or [None] * len(q["questions"]))[k]
                sign = "✓" if mark == 1 else ("◐" if mark else "✗")
                st.markdown(f"{sign} {k + 1}. {item['question']}")
                if item.get("from"):
                    st.caption(tr("From an earlier lesson · not part of the score"))
                if item["type"] in quiz.WRITTEN:
                    st.caption((tr("What a good answer shows: {answer}", answer=item['answer']) if item['type'] == 'apply'
                                else tr("A good answer: {answer}", answer=item['answer'])))
                else:
                    st.caption(tr("Answer: {answer}.", answer=review._answer_text(item))
                               + (" " + item['why'] if item.get('why') else ""))
    with notes:
        chat = slot.get("followups") or []
        reflection = entry.get("reflection", "").strip()
        if not chat and not reflection and not slot.get("explain"):
            st.caption(tr("No notes for this lesson: questions you asked the coach and your thoughts on the "
                       "day's question would be kept here."))
        for msg in chat:
            who = "You" if msg["role"] == "user" else "Coach"
            body, where, _ = practice.split_reply(msg["content"], slot.get("lesson", ""))
            st.markdown(f"**{who}:** {body}")
            if practice.based_label(where):
                st.caption(practice.based_label(where))
        if slot.get("explain", {}).get("feedback"):
            ex = slot["explain"]
            st.markdown(tr('**You explained it:** {p0}', p0=ex['text']))
            st.caption(" ".join(x for x in (ex["feedback"]["right"], ex["feedback"]["missing"]) if x))
        if reflection:
            st.markdown(tr('**Your thoughts that day:** {reflection}', reflection=reflection))


# ============================================================
# WHERE SHE IS: the subject, how far, and the next step
# ============================================================
share = m["done"] / m["written"] if m["written"] else 0
st.html(tr('<p class="cm-eyebrow cm-top">Learning map</p>'))
st.markdown(f"## {escape(course.subject_name(topic))}")
goal = catalog.path(topic)
if goal:                    # her goal: what the path is for
    st.html(f'<p class="cm-outcome">{escape(goal["outcome"])}</p>')
st.html(f'<div class="cm-head"><div class="rv-line"><span style="width:{share * 100:.1f}%"></span></div>'
        + '<p>' + tr("{done} of {written} lessons passed · {level}", done=m["done"], written=m["written"], level=tr(level))
        + (" · " + tr("more are added as you go") if m["written"] < m["total"] and topic != "math" else "") + "</p></div>")

# how far she has come on it: where she started, where she is now (coach/habit.py)
j = habit.journey(log, topic, settings.start_level(config, topic))
if j["started"]:
    began = date.fromisoformat(j["started"])
    then_now = trn("Started {date} at {start} · now {n} lesson passed, in “{unit}”, at {level}",
                   "Started {date} at {start} · now {n} lessons passed, in “{unit}”, at {level}", j["done"],
                   date=i18n.date_long(began),
                   start=tr(j["start_level"]), unit=j["unit"], level=tr(j["level"]))
    trend = (" · " + tr("quiz average {first}% in your first lessons, {recent}% in your latest",
                        first=j["first_avg"], recent=j["recent_avg"]) if j["first_avg"] is not None else "")
    st.html(f'<p class="cm-journey">{escape(then_now + trend)}</p>')

# what she knows on this path, idea by idea (the Knowledge Map's picture, here beside the path)
known = {x["n"]: x for x in mastery.ideas(log, topic, today)}
reached = [x for x in known.values() if x["reached"]]
if reached:
    c = mastery.counts(reached)
    fading = sum(1 for x in reached if x["fading"])
    total = sum(c[lv] for lv in ("learning", "solid", "mastered")) or 1
    segs = "".join(f'<span class="sk-seg sk-{lv}" style="width:{c[lv] / total * 100:.1f}%"></span>'
                   for lv in ("mastered", "solid", "learning") if c[lv])
    keys = "".join(f'<span class="sk-key"><i class="sk-dot sk-{lv}"></i>{c[lv]} {tr(mastery.LEVEL_NAMES[lv]).lower()}</span>'
                   for lv in ("mastered", "solid", "learning"))
    st.html(f'<div class="sk-summary"><div class="sk-bar">{segs}</div><p class="sk-legend">{keys}'
            + ('<span class="sk-key">· ' + tr("{n} fading", n=fading) + "</span>" if fading else "") + "</p></div>")
    st.caption(tr("An idea is solid once it holds on another day, mastered once it keeps holding over a week or "
                  "more, and it fades if it isn't practised."))

with st.container(key="cm_next"):
    nxt = m["next"]
    if nxt is None:
        st.markdown(tr("**You've passed every lesson written so far.** New lessons are added as you go."))
    else:
        title = curriculum.lesson(topic, nxt)["title"]
        if is_today:
            if st.button(tr('Continue · Lesson {nxt}: {title}', nxt=nxt, title=title), type="primary", key="cm_continue", width="stretch"):
                st.switch_page("views/daily.py")
        else:
            when = ui.next_study_day(topic)
            day = "" if when is None else " · " + tr("on {day}", day=i18n.day_long(when))
            st.markdown(tr('**Next: Lesson {nxt}, {p0}**{day}', nxt=nxt, p0=escape(title), day=day))
            st.caption(tr("Today is {p0}'s day: your subjects take turns, one a day.", p0=catalog.name(ui.topic_for(today), 'another subject')))
    with st.container(key="cm_links", horizontal=True):
        if mastery.needs_practice(log, today) and st.button(tr("Practise the shakiest"), type="tertiary", key="cm_skills"):
            st.switch_page("views/practice.py")
        placed = (ui.prefs().get("diag") or {}).get(topic)
        if diagnostic.offered(topic) and not (placed and placed["applied"]) and \
                st.button(tr("Find my starting point"), type="tertiary", key="cm_diag"):
            st.switch_page("views/diagnostic.py", query_params={"subject": topic})
        for c_ in capstone.offered(log, topic):        # a goal, or a math phase, done: its capstone
            if st.button(tr("Capstone · {title}", title=c_["title"]), type="tertiary", key=f"cm_cap_{c_['key']}"):
                st.switch_page("views/capstone.py", query_params={"subject": topic, "key": c_["key"]})
        if visuals.known(topic) and st.button(tr('Enter {p0}', p0=course.subject_name(topic)), type="tertiary", key="cm_world"):
            ui.enter_world(topic)       # (a goal has no world)
        if topic == "math" and st.button(tr("The whole curriculum"), type="tertiary", key="cm_math"):
            here = m["units"][m["current"]]["name"].split(" ")[0] if m["current"] is not None else None
            st.switch_page("views/math.py", query_params={"unit": here} if here else None)
        others = [t for t in mine if t != topic and curriculum.has_syllabus(t)]
        for t in others:                     # her other courses' maps, named as such
            if st.button(tr("{p0}: learning map", p0=course.subject_name(t)), type="tertiary", key=f"cm_other_{t}"):
                ui.open_course(t)


# ============================================================
# THE PATH: units in order, lessons in each
# ============================================================
STATE_WORDS = {"today": N_("Today"), "next": N_("Next"), "started": N_("Started")}
gate = progression.gate(log, topic)            # a unit check standing before the next unit


def rows(unit):
    """A unit's lessons, one line each; a lesson she has written opens."""
    for x in unit["lessons"]:
        meta = ""
        if x.get("skipped"):
            meta = tr("known already")
        elif x["state"] == "done":
            meta = tr("passed {date}", date=course.short_date(x['passed'])) if x["passed"] else tr("passed")
            meta += f" · {x['best']}%" if x["best"] is not None else ""
        elif x["state"] in STATE_WORDS:
            meta = tr(STATE_WORDS[x["state"]])
        idea = known.get(x["n"])
        level = (f'<span class="sk-chip sk-{idea["level"]}{" sk-fading" if idea["fading"] else ""}">'
                 f'{tr(mastery.LEVEL_NAMES[idea["level"]])}{" · " + tr("fading") if idea["fading"] else ""}</span>'
                 if idea and idea["level"] != "new" else "")
        with st.container(key=f"cm_row_{x['n']}_{x['state']}", horizontal=True, vertical_alignment="center"):
            st.html(f'<div class="cm-row"><span class="cm-n">{x["n"]}</span>'
                    f'<span class="cm-t">{escape(x["title"])}{level}</span><span class="cm-m">{escape(meta)}</span></div>')
            if x["readable"]:
                if st.button(tr("Read"), key=f"cm_read_{x['n']}", type="tertiary"):
                    open_lesson(x["n"])


def unit_check(u, named=False):
    """Under a unit whose lessons are all passed: its check, and how it went
    (`named`: shown away from its lessons, so it says which unit)."""
    u = dict(u, key=f"u{u['first']}")
    if not unitcheck.offered(log, topic, u):
        return
    r = unitcheck.result(log, topic, u)
    needed = gate is not None and gate["key"] == u["key"]
    said = (tr("Unit check passed · best {score}%", score=r['best']) if r.get("passed_on") else
            tr("Unit check · needed before “{opens}”", opens=gate["opens"]) if needed else
            tr("Unit check · best so far {score}%", score=r['best']) if r.get("attempts") else
            tr("Unit check · ready: show you've learned this unit as a whole"))
    if named:
        said = f"{u['name']}: {said[:1].lower()}{said[1:]}"
    with st.container(key=f"cm_uc_{u['key']}", horizontal=True, vertical_alignment="center"):
        st.html(f'<p class="cm-uc">{escape(said)}</p>')
        if st.button(tr("Take it again") if r.get("passed_on") else tr("Take the check"), type="tertiary",
                     key=f"cm_uc_go_{u['key']}"):
            ui.open_unit(topic, u["key"])


units, cur = m["units"], m["current"]
with st.container(key="cm_path"):
    if cur is None:
        st.caption(tr("There's nothing on this learning map yet: its lessons appear here once they're set."))
    else:
        behind = [u for k, u in enumerate(units) if k < cur]
        done_units = [u for u in behind if u["state"] == "done"]
        if behind:
            with st.expander(trn('Finished · {done} of {n} topic before this one', 'Finished · {done} of {n} topics before this one', len(behind), done=len(done_units)), expanded=False):
                for u in behind:
                    st.markdown(f"#### {'✓ ' if u['state'] == 'done' else ''}{escape(u['name'])}")
                    rows(u)
                    if u is not behind[-1]:
                        unit_check(u)
            unit_check(behind[-1], named=True)        # the unit just finished: its check in sight
        for k in (cur, cur + 1):
            if k < len(units):
                u = units[k]
                st.html(f'<p class="cm-eyebrow">{tr("You are here") if k == cur else tr("Up next")}</p>')
                st.markdown(f"#### {escape(u['name'])}")
                c = mastery.counts([known[x["n"]] for x in u["lessons"] if x["n"] in known])
                strong = c["solid"] + c["mastered"]
                st.caption(tr("Lessons {first}–{last} · {done} of {n} passed", first=u['first'], last=u['last'],
                              done=u['done_count'], n=len(u['lessons']))
                           + (" · " + tr("{n} solid or mastered", n=strong) if strong else ""))
                rows(u)
                unit_check(u)
        later = units[cur + 2:]
        if later:
            with st.expander(tr('Later in the course · {p0} more topics, {p1} lessons', p0=len(later), p1=sum(len(u['lessons']) for u in later))):
                st.html('<div class="cm-later">' + "".join(
                    f'<div class="cm-unit"><p class="cm-u">{escape(u["name"])}'
                    f'<span>{tr("Lessons {first}–{last}", first=u["first"], last=u["last"])}</span></p><ol start="{u["first"]}">'
                    + "".join(f"<li>{escape(x['title'])}</li>" for x in u["lessons"]) + "</ol></div>"
                    for u in later) + "</div>")
