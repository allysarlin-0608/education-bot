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

from coach import catalog, core, course, curriculum, habit, lesson_view, mastery, practice, quiz, review, settings, ui, visuals

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
level = core.lesson_level(min(m["done"] + 1, curriculum.TOTAL), settings.start_level(config, topic))
st.html('<div id="course-page"></div>')


# ============================================================
# A LESSON, OPENED: read it again, its quiz, her notes
# ============================================================
@st.dialog("Lesson", width="large")
def open_lesson(n):
    found = course.lesson_record(log, topic, n)
    if found is None:
        st.caption("This lesson hasn't been written yet.")
        return
    entry, slot, passed = found
    st.markdown(f"### Lesson {n}: {slot['title']}")
    q = slot.get("quiz") or {}
    meta = [slot.get("unit") or ""]
    meta.append(f"passed {course.short_date(passed)}" if passed else f"started {course.short_date(entry['date'])}")
    if q.get("best") is not None:
        meta.append(f"best {q['best']}%")
    st.caption(" · ".join(x for x in meta if x))
    read, quiz_tab, notes = st.tabs(["Lesson", "Quiz", "Notes"])
    with read:
        lesson_view.render_tabs(slot["lesson"], topic, key=f"cm_{topic}_{n}", title=slot.get("title", ""))
    with quiz_tab:
        if q and q.get("answers") is not None and q.get("score") is None:
            st.caption("Your last answers are in, but the short answers weren't marked yet: Today marks them.")
        elif not q or q.get("answers") is None:
            st.caption("No quiz taken on this lesson yet." if not passed else "Passed before quizzes were kept.")
        else:
            attempts = q.get("attempts") or 1
            st.markdown(f"**Last attempt: {q.get('score')}%** · {quiz.points(q)} points · "
                        f"{attempts} {'attempt' if attempts == 1 else 'attempts'}, best {q.get('best')}%")
            for k, item in enumerate(q["questions"]):
                mark = (q.get("marks") or [None] * len(q["questions"]))[k]
                sign = "✓" if mark == 1 else ("◐" if mark else "✗")
                st.markdown(f"{sign} {k + 1}. {item['question']}")
                if item.get("from"):
                    st.caption("From an earlier lesson · not part of the score")
                if item["type"] in quiz.WRITTEN:
                    st.caption(f"{'What a good answer shows' if item['type'] == 'apply' else 'A good answer'}: "
                               f"{item['answer']}")
                else:
                    st.caption(f"Answer: {review._answer_text(item)}. {item.get('why') or ''}".strip())
    with notes:
        chat = slot.get("followups") or []
        reflection = entry.get("reflection", "").strip()
        if not chat and not reflection and not slot.get("explain"):
            st.caption("No notes for this lesson: questions you asked the coach and your thoughts on the "
                       "day's question would be kept here.")
        for msg in chat:
            who = "You" if msg["role"] == "user" else "Coach"
            body, where, _ = practice.split_reply(msg["content"], slot.get("lesson", ""))
            st.markdown(f"**{who}:** {body}")
            if practice.based_label(where):
                st.caption(practice.based_label(where))
        if slot.get("explain", {}).get("feedback"):
            ex = slot["explain"]
            st.markdown(f"**You explained it:** {ex['text']}")
            st.caption(" ".join(x for x in (ex["feedback"]["right"], ex["feedback"]["missing"]) if x))
        if reflection:
            st.markdown(f"**Your thoughts that day:** {reflection}")


# ============================================================
# WHERE SHE IS: the subject, how far, and the next step
# ============================================================
share = m["done"] / m["written"] if m["written"] else 0
st.html('<p class="cm-eyebrow cm-top">Course map</p>')
st.markdown(f"## {escape(course.subject_name(topic))}")
goal = catalog.path(topic)
if goal:                    # her goal: what the path is for
    st.html(f'<p class="cm-outcome">{escape(goal["outcome"])}</p>')
st.html(f'<div class="cm-head"><div class="rv-line"><span style="width:{share * 100:.1f}%"></span></div>'
        f'<p>{m["done"]} of {m["written"]} lessons passed · {level}'
        + (" · more are added as you go" if m["written"] < m["total"] else "") + "</p></div>")

# how far she has come on it: where she started, where she is now (coach/habit.py)
j = habit.journey(log, topic, settings.start_level(config, topic))
if j["started"]:
    began = date.fromisoformat(j["started"])
    then_now = (f'Started {began:%B} {began.day}, {began.year} at {j["start_level"]} · now {j["done"]} '
                f'{"lesson" if j["done"] == 1 else "lessons"} passed, in “{j["unit"]}”, at {j["level"]}')
    trend = (f' · quiz average {j["first_avg"]}% in your first lessons, {j["recent_avg"]}% in your latest'
             if j["first_avg"] is not None else "")
    st.html(f'<p class="cm-journey">{escape(then_now + trend)}</p>')

with st.container(key="cm_next"):
    nxt = m["next"]
    if nxt is None:
        st.markdown("**You've passed every lesson written so far.** New lessons are added as you go.")
    else:
        title = curriculum.lesson(topic, nxt)["title"]
        if is_today:
            if st.button(f"Continue · Lesson {nxt}: {title}", type="primary", key="cm_continue", width="stretch"):
                st.switch_page("views/daily.py")
        else:
            when = ui.next_study_day(topic)
            day = "" if when is None else f" · on {when:%A}, {when:%b} {when.day}"
            st.markdown(f"**Next: Lesson {nxt}, {escape(title)}**{day}")
            st.caption(f"Today is {catalog.name(ui.topic_for(today), 'another subject')}'s day: "
                       "your subjects take turns, one a day.")
    with st.container(key="cm_links", horizontal=True):
        if st.button("Knowledge map", type="tertiary", key="cm_skills"):
            st.session_state.sk_topic = topic
            st.switch_page("views/skills.py")
        if visuals.known(topic) and st.button(f"Enter {course.subject_name(topic)}", type="tertiary", key="cm_world"):
            ui.enter_world(topic)       # (a goal has no world)
        others = [t for t in mine if t != topic and curriculum.has_syllabus(t)]
        for t in others:
            if st.button(course.subject_name(t), type="tertiary", key=f"cm_other_{t}"):
                ui.open_course(t)


# ============================================================
# THE PATH: units in order, lessons in each
# ============================================================
STATE_WORDS = {"today": "Today", "next": "Next", "started": "Started"}
known = {x["n"]: x for x in mastery.ideas(log, topic, today)}       # what she knows, idea by idea


def rows(unit):
    """A unit's lessons, one line each; a lesson she has written opens."""
    for x in unit["lessons"]:
        meta = ""
        if x["state"] == "done":
            meta = f"passed {course.short_date(x['passed'])}" if x["passed"] else "passed"
            meta += f" · {x['best']}%" if x["best"] is not None else ""
        elif x["state"] in STATE_WORDS:
            meta = STATE_WORDS[x["state"]]
        idea = known.get(x["n"])
        level = (f'<span class="sk-chip sk-{idea["level"]}{" sk-fading" if idea["fading"] else ""}">'
                 f'{mastery.LEVEL_NAMES[idea["level"]]}{" · fading" if idea["fading"] else ""}</span>'
                 if idea and idea["level"] != "new" else "")
        with st.container(key=f"cm_row_{x['n']}_{x['state']}", horizontal=True, vertical_alignment="center"):
            st.html(f'<div class="cm-row"><span class="cm-n">{x["n"]}</span>'
                    f'<span class="cm-t">{escape(x["title"])}{level}</span><span class="cm-m">{escape(meta)}</span></div>')
            if x["readable"]:
                if st.button("Read", key=f"cm_read_{x['n']}", type="tertiary"):
                    open_lesson(x["n"])


units, cur = m["units"], m["current"]
with st.container(key="cm_path"):
    if cur is None:
        st.caption("This subject's course isn't available yet.")
    else:
        behind = [u for k, u in enumerate(units) if k < cur]
        done_units = [u for u in behind if u["state"] == "done"]
        if behind:
            with st.expander(f"Finished · {len(done_units)} of {len(behind)} "
                             f"{'topic' if len(behind) == 1 else 'topics'} before this one", expanded=False):
                for u in behind:
                    st.markdown(f"#### {'✓ ' if u['state'] == 'done' else ''}{escape(u['name'])}")
                    rows(u)
        for k in (cur, cur + 1):
            if k < len(units):
                u = units[k]
                st.html(f'<p class="cm-eyebrow">{"You are here" if k == cur else "Up next"}</p>')
                st.markdown(f"#### {escape(u['name'])}")
                c = mastery.counts([known[x["n"]] for x in u["lessons"] if x["n"] in known])
                strong = c["solid"] + c["mastered"]
                st.caption(f"Lessons {u['first']}–{u['last']} · {u['done_count']} of {len(u['lessons'])} passed"
                           + (f" · {strong} solid or mastered" if strong else ""))
                rows(u)
        later = units[cur + 2:]
        if later:
            with st.expander(f"Later in the course · {len(later)} more topics, "
                             f"{sum(len(u['lessons']) for u in later)} lessons"):
                st.html('<div class="cm-later">' + "".join(
                    f'<div class="cm-unit"><p class="cm-u">{escape(u["name"])}'
                    f'<span>Lessons {u["first"]}–{u["last"]}</span></p><ol start="{u["first"]}">'
                    + "".join(f"<li>{escape(x['title'])}</li>" for x in u["lessons"]) + "</ol></div>"
                    for u in later) + "</div>")
