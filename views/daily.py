from datetime import date, timedelta
from html import escape

import streamlit as st

from coach import (attempts, auth, capstone, catalog, clock, core, curriculum, diagnostic, exercise, goalmaker, habit,
                   learner, lesson_view, progression,
                   lessonprep, llm, mastery, mathcourse, paths, place, practice, progress_bar, quiz, quizgen, quizprep,
                   quota, report_ui, review, session, session_ui, settings, steps, tokens, ui, unitcheck, visuals, i18n)
from coach import prefs as prefs_
from coach.i18n import N_, tr, trn

log = st.session_state.coach_log
config = ui.config()        # her subjects, daily pace and starting levels


# Today is always the real today (past days are in the Progress history).
today = ui.today()


def chat_key(slot):
    return f"{today.isoformat()}|{topic}|{slot['n']}"


def get_chat(slot):
    """This lesson's chat; rebuilt from the saved lesson (and the follow-ups
    after it) when this session doesn't have it yet, so a lesson is never
    generated twice."""
    chats = st.session_state.coach_chats
    if chat_key(slot) not in chats:
        chats[chat_key(slot)] = (
            [{"role": "user", "content": slot["kickoff"] or core.build_kickoff_message(topic, today, slot=slot)},
             {"role": "assistant", "content": slot["lesson"]}] + slot["followups"]
            if slot.get("lesson") else []
        )
    return chats[chat_key(slot)]


def day_entry():
    """Today's entry with its lessons fixed; created when the first lesson
    starts, so an untouched day doesn't reserve lessons."""
    entry = core.start_entry(log, today, topic)
    if not entry["lessons"]:
        entry["lessons"] = [dict(s) for s in plan]
    elif [s["n"] for s in entry["lessons"]] != [s["n"] for s in plan]:
        # her pace changed since the day started (curriculum.fit): the
        # lessons she began are the same objects, the rest follow the pace
        entry["lessons"] = plan
        entry["completed"] = curriculum.day_complete(plan)
    return entry


def shown_entry():
    """Today's entry for drawing the page: the stored one, or the day as
    planned. Unlike day_entry() it adds nothing to her record: only doing
    something (a lesson, an answer, a note) makes the day one she studied."""
    e = core.find_entry(log, today, topic)
    if e is None:
        return {"date": today.isoformat(), "topic": topic, "lessons": plan, "completed": False, "reflection": ""}
    if [s["n"] for s in e["lessons"]] != [s["n"] for s in plan]:
        return {**e, "lessons": plan, "completed": curriculum.day_complete(plan)}
    return e


def work(entry, i):
    """(the entry to save, the slot holding the lesson) for lesson i of the
    day: for a lesson carried over from an earlier day, its original slot
    there (curriculum.origin): its chat and quizzes are written back to it."""
    found = curriculum.origin(log, topic, entry["lessons"][i])
    return found if found else (entry, entry["lessons"][i])


def save(entry, owner):
    """Save the day, and the earlier day a carried-over lesson belongs to,
    each written into the day as stored now (ui.save_day): the quiz sheet
    saves from a fragment, which doesn't re-read either day first."""
    ok = ui.save_day(log, entry, [s["n"] for s in entry["lessons"]], recount=True, page_day=today)
    if owner is entry:
        return ok
    carried = [s["n"] for s in entry["lessons"] if s.get("from") == owner["date"]]
    return ui.save_day(log, owner, carried, page_day=today) and ok


def failed(kind, error, slot, **payload):
    """Remember a failed call so the page can show a friendly message and
    a Retry button that repeats it (the raw error only goes to the log)."""
    st.session_state.coach_retry = {"kind": kind, "error": error, "key": chat_key(slot), **payload}
    st.rerun()


def run_kickoff(i):
    entry = day_entry()
    owner, slot = work(entry, i)
    if curriculum.blocking(entry["lessons"], i):     # strictly in order
        st.rerun()
    chat = get_chat(slot)
    if chat:        # already generated (e.g. in another tab): never call again
        st.rerun()
    kickoff = core.build_kickoff_message(topic, today, slot=slot)
    # Written in the background during the warm-up (coach/lessonprep.py): taken
    # when ready, waited for if nearly there; otherwise written here, streamed.
    # The chat only changes once the lesson is complete: a run interrupted
    # mid-stream (she clicks elsewhere) must not leave a lesson half there.
    k = lessonprep.key(quizprep.session_id(), topic, slot["n"], today.isoformat())
    lesson, error = None, None
    if lessonprep.state(k) != "none":
        with st.spinner(tr("Finishing today's lesson…")):
            ready = lessonprep.take(k)
        if ready and ready[0]:
            lesson = ready[0]
    if lesson is None:
        lesson, error = llm.stream_reply(*lesson_request(slot), max_tokens=tokens.LESSON_MAX_TOKENS)
    if error:
        failed("kickoff", error, slot, i=i)       # (the day it made is dropped on the rerun: ui.refresh_entry)
    lesson = core.truthful_note(core.finalize_reply(lesson, lesson=True, topic=topic),
                                core.note_fact(log, topic, today, slot["n"]))
    chat += [{"role": "user", "content": kickoff}, {"role": "assistant", "content": lesson}]
    slot["kickoff"], slot["lesson"] = kickoff, lesson
    first, last = entry["lessons"][0]["n"], entry["lessons"][-1]["n"]
    entry["title"] = f"Lessons {first}–{last}"
    entry["level"] = core.lesson_level(first, start_level, topic)
    entry["followup_question"] = core.extract_section(lesson, "Question to Explore")
    # into the day as stored now (the stream took a while: another tab may have saved since)
    ui.save_day(log, entry, [slot["n"]], keep=("title", "level", "followup_question"), recount=True, page_day=today)
    st.rerun()


def lesson_request(slot):
    """(instructions, messages) for writing lesson `slot`: the same on the page
    and in the background (coach/lessonprep.py)."""
    kickoff = core.build_kickoff_message(topic, today, slot=slot)
    return (core.build_system_prompt(log, topic, today, slot=slot, start_level=start_level, public=auth.is_public(),
                                     weak=practice.weak_titles(log, topic, slot["n"], today)),     # earlier shaky ideas
            [{"role": "user", "content": kickoff}])


def prepare_lesson(i) -> None:
    """Start writing lesson i in the background (during the warm-up), unless
    it is written, can't be started yet, or the AI can't be used now."""
    if i is None or not quizprep.enabled() or llm.get_client() is None or quota.blocked():
        return
    slot = curriculum.content(log, topic, plan[i])
    if slot.get("lesson") or curriculum.blocking(plan, i) or slot.get("from") or progression.gate(log, topic):
        return                  # (written, waiting for an earlier one, or behind a unit check: nothing to write)
    k = lessonprep.key(quizprep.session_id(), topic, slot["n"], today.isoformat())
    if lessonprep.state(k) == "none":
        lessonprep.start(k, *lesson_request(slot), where=f"{topic} lesson {slot['n']}")


def run_followup(i, text):
    entry = day_entry()
    owner, slot = work(entry, i)
    chat = get_chat(slot)
    asked = chat + [{"role": "user", "content": text}]     # kept only once answered (as in run_kickoff)
    n = st.session_state.coach_scroll_n = st.session_state.get("coach_scroll_n", 0) + 1
    st.html(place.follow(n), unsafe_allow_javascript=True)      # the page follows her question
    with st.chat_message("user"):
        st.markdown(text)
    reply, error = llm.stream_reply(
        core.build_system_prompt(log, topic, today, followup=True, slot=slot, start_level=start_level,
                                public=auth.is_public()), asked,
        max_tokens=tokens.CHAT_MAX_TOKENS,
    )
    if error:
        failed("followup", error, slot, i=i, text=text)
    answer = core.finalize_reply(reply, lesson=False, topic=topic)
    chat += [asked[-1], {"role": "assistant", "content": answer}]
    slot["followups"] = chat[2:]               # everything after the lesson
    _, _, confused = practice.split_reply(answer, slot.get("lesson", ""))
    if confused:            # a question that showed a misunderstanding: the skill map and review hear of it
        ui.learned(slot, owner["date"], "ask", 0.3, source=f"ask-{len(slot['followups'])}")
        review.keep(log, slot)
        review.add_key_idea(slot, today, topic)          # its key idea comes back tomorrow
        for c in slot.get("cards") or []:
            if c["kind"] == "point" and c["front"].startswith("Key idea ·") and c["due"] > (today + timedelta(days=1)).isoformat():
                c["due"] = (today + timedelta(days=1)).isoformat()
    save(entry, owner)
    ui.record("tutor_question")
    if confused:
        ui.record("tutor_confused")
    st.session_state.coach_scroll = (place.LATEST, False)      # and stays on it after the redraw
    st.rerun()                                 # show the checked text, not the raw stream


def run_rewrite(i):
    """An earlier lesson not passed yet, written again under today's rules (she
    asked: one AI call). Her questions and their answers stay; a quiz she
    hasn't answered is written again too, when she starts it."""
    entry = day_entry()
    owner, slot = work(entry, i)
    if slot.get("completed") or not slot.get("lesson"):
        st.rerun()
    with st.spinner(tr("Rewriting the lesson…")):
        lesson, error = llm.stream_reply(
            core.build_system_prompt(log, topic, today, slot=slot, start_level=start_level, public=auth.is_public(),
                                     weak=practice.weak_titles(log, topic, slot["n"], today)),
            [{"role": "user", "content": slot.get("kickoff") or core.build_kickoff_message(topic, today, slot=slot)}],
            max_tokens=tokens.LESSON_MAX_TOKENS)
    if error:
        failed("kickoff", error, slot, i=i)
    slot["lesson"] = core.truthful_note(core.finalize_reply(lesson, lesson=True, topic=topic),
                                        core.note_fact(log, topic, today, slot["n"]))
    if slot.get("quiz") and slot["quiz"].get("answers") is None:
        slot["quiz"] = quiz.retire(slot["quiz"])          # about the old text: written again when she starts it
    ui.save_day(log, owner, [slot["n"]], page_day=today)
    st.session_state.coach_rewritten = slot["n"]
    st.rerun()


def run_quiz(i):
    """Write a fresh quiz for lesson i (a new set on every retake), checked
    answer by answer (coach/quizgen.py)."""
    entry = day_entry()
    owner, slot = work(entry, i)
    if curriculum.blocking(entry["lessons"], i):     # strictly in order
        st.rerun()
    where = f"{topic} lesson {slot['n']}"
    k = quizprep.key(quizprep.session_id(), topic, slot)
    ready = None
    if quizprep.state(k) == "running":               # prepared while she read (coach/quizprep.py): what's left
        with st.spinner(tr("Finishing your quiz…")):
            ready = quizprep.take(k)
    elif quizprep.state(k) == "ready":
        ready = quizprep.take(k)
    if ready and ready[0]:
        questions, error = ready
    else:                                            # nothing prepared, or it didn't work out: written now
        context = practice.quiz_context(log, topic, slot, today, goal=catalog.path(topic))
        questions, error = quizgen.make(slot, where, step=st.spinner, context=context)
    if questions is None:
        failed("quiz", error, slot, i=i)
    check = [q for q in questions if q.get("role") != "practice"]
    slot["quiz"] = quiz.new(check, slot.get("quiz"))
    place_ = session.keep(slot)
    if place_.get("guided") is None:                 # the guided practice, written with the first set
        guided = [q for q in questions if q.get("role") == "practice"]
        place_["guided"] = session.new_guided(guided, problem_first(slot, owner))
    save(entry, owner)
    st.rerun()


def problem_first(slot, owner) -> bool:
    """Start practice with the problem (the worked steps only after a miss):
    an idea she probably knows already, or the "problem first" arm."""
    known = mastery.state(mastery.evidence(slot, owner["date"]), today)["strength"] >= session.KNOWN
    return known or ui.arm("fading", topic, slot["n"]) == "problem_first"


PREPARING = N_("Preparing your quiz…")


def prepare_quiz(slot) -> None:
    """Start writing this lesson's quiz in the background (coach/quizprep.py),
    unless the AI can't be used just now (no key, the daily allowance)."""
    if not quizprep.enabled() or slot.get("completed") or not slot.get("lesson") or llm.get_client() is None:
        return
    q = slot.get("quiz")
    if q is not None and not quiz.outdated(q) and not (q.get("answers") is not None and not quiz.passed(q.get("score"))):
        return                  # a set is waiting for her already: nothing to prepare (and no call spent)
    k = quizprep.key(quizprep.session_id(), topic, slot)
    if quizprep.state(k) != "none" or quota.blocked():
        return
    context = practice.quiz_context(log, topic, slot, today, goal=catalog.path(topic))
    quizprep.start(k, slot, f"{topic} lesson {slot['n']}", context)


def show_retry(slot, kinds):
    """Friendly message + Retry for the last failed call on this lesson, if
    it was one of `kinds`. Each kind is shown in one place on the page (the
    lesson start, the quiz, the chat), so there is only ever one Retry."""
    retry = st.session_state.get("coach_retry")
    if not retry or retry["key"] != chat_key(slot) or retry["kind"] not in kinds:
        return False
    spot = st.empty()           # the message and its Retry give way while it runs (no second click)
    with spot.container():
        st.warning(retry["error"])
        again = st.button(tr("Retry"), key=f"coach_retry_{retry['kind']}")
    if again:
        st.session_state.coach_retry = None
        spot.empty()
        if retry["kind"] == "kickoff":
            run_kickoff(retry["i"])
        elif retry["kind"] == "quiz":
            spot.button(tr(PREPARING), disabled=True, type="primary", use_container_width=True, key="quiz_preparing")
            run_quiz(retry["i"])
        elif retry["kind"] == "grade":
            run_grading(retry["i"])
        elif retry["kind"] == "explain":
            run_explain(retry["i"], retry["text"])
        elif retry["kind"] == "follow":
            run_follow(retry["i"], retry["text"])
        else:
            run_followup(retry["i"], retry["text"])
    return True


# ============================================================
# TODAY'S SESSION (coach/session.py): what she did, measured (coach/attempts.py)
# ============================================================
def reached(step: str, n: int = 0) -> None:
    """She reached a step of the session (once a day each): where sessions stop."""
    seen = st.session_state.setdefault("ss_reached", set())
    if (today, topic, n, step) in seen:
        return
    seen.add((today, topic, n, step))
    ui.attempt([attempts.row(today, topic, n, "step", step)])


def gap_of(held, owner_date):
    return attempts.gap(mastery.evidence(held, owner_date), today)


def day_set(name: str):
    """Today's warm-up or mixed set, as stored now (another tab may have moved on)."""
    s = ui.prefs().get(name)
    return s if s and s["date"] == today.isoformat() else None


def answer_set_item(name: str, k: int, item: dict, owner_topic: str, n: int, mark: float, conf, ctx: str,
                    variants=()) -> None:
    """One warm-up or mixed item answered: its idea hears of it (and a card is
    rescheduled by its memory), the answer is recorded, her place is kept."""
    ui.load_prefs()
    s = day_set(name)
    if s is None or s["marks"][k] is not None:
        return                                        # (already answered: a second click, or another tab)
    src = s["items"][k]
    gap = None
    if src["src"] == "card":
        found = review.find(log, src["id"])
        if found is not None:
            ui.refresh_entry(log, date.fromisoformat(found[0]["date"]), found[0]["topic"])
            found = review.find(log, src["id"])
        if found is not None and "cards" not in found[1]:
            review.keep(log, found[1])
            found = review.find(log, src["id"])
        if found is not None:
            e, held, card = found
            gap = gap_of(held, e["date"])
            review.grade(card, mark == 1, today, confidence=conf, target=ui.target_retention())
            ui.learned(held, e["date"], "review", mark, source=f"{card['id']}-{card['reviews']}")
            if not ui.save_entry(log, e):
                ui.show_pending_error()
    elif src.get("spot"):                 # a unit she skipped as known, asked about again
        every = dict(ui.prefs().get("diag") or {})
        placed = every.get(owner_topic)
        if placed:
            every[owner_topic] = diagnostic.spot_answered(placed, diagnostic.units(owner_topic), src["spot"], mark == 1)
            ui.update_prefs(diag=every)
            ui.load_prefs()
            s = day_set(name)
    else:
        held = mastery.holder(log, owner_topic, n)
        if held:
            gap = gap_of(held[1], held[0]["date"])
        ui.learned_elsewhere(log, owner_topic, n, "practice", mark, source=f"{session.item_id(item)}-{today.isoformat()}")
    s["marks"][k], s["conf"][k] = mark, conf
    if not session.set_left(s):
        s["done"] = True
    ui.update_prefs(**{name: s})
    ui.attempt([session_ui.row(today, owner_topic, n, "diag" if src.get("spot") else ctx, item, mark, True, conf,
                               session_ui.seconds(f"{name}{k}_0"), gap, variants)])


def set_card(name: str, k: int):
    """(item, recall, topic, n) for item k of a set; None if its card is gone."""
    src = day_set(name)["items"][k]
    if src["src"] == "bank":
        return src["q"], None, src["topic"], src["n"]
    found = review.find(log, src["id"])
    if found is None:
        return None
    item, recall = session_ui.card_item(log, found[2])
    return item, recall, found[0]["topic"], found[2].get("n") or 0


def run_set(name: str, ctx: str, title: str, sub: str, variants=()) -> bool:
    """A warm-up or mixed set, one item at a time. True once it's done."""
    s = day_set(name)
    if s is None or s["done"] or s["skipped"]:
        return True
    shown_key = f"ss_{name}_shown"
    with st.container(key=f"ss_{name}"):
        session_ui.eyebrow(title, sub)
        left = session.set_left(s)
        k = st.session_state.get(shown_key)
        if k is None and not left:
            return True
        if k is None:
            k = left[0]
        found = set_card(name, k)
        if found is None:                       # a card deleted since: left out
            s["items"].pop(k), s["marks"].pop(k), s["conf"].pop(k)
            s["done"] = not session.set_left(s)
            ui.update_prefs(**{name: s})
            st.rerun()
        item, recall, owner_topic, n = found
        session_ui.pace(len(s["marks"]) - len(left), len(s["marks"]))
        st.caption(session_ui.source_line(owner_topic, n, log))
        if st.session_state.get(shown_key) is not None:            # just answered: how it went
            mark = s["marks"][k]
            if item is not None:
                answer = st.session_state.get(f"ss_{name}_answer")
                st.markdown(f"**{item['question']}**")
                session_ui.exercise_done(item, answer, mark, 1)
            else:
                st.markdown(f"**{recall[0]}**")
                st.markdown(recall[1])
                st.html(f'<p class="ss-verdict">{exercise.sign(mark)} '
                        + (tr("Good: it comes back further apart now.") if mark == 1 else tr("It comes back tomorrow."))
                        + "</p>")
            last = not session.set_left(s)
            if st.button(tr("Continue") if last else tr("Next"), type="primary", key=f"ss_{name}_next", width="stretch"):
                st.session_state[shown_key] = None
                st.rerun()
            return False
        if item is not None:
            got = session_ui.exercise_try(item, f"{name}{k}", 0)
            if got:
                answer, conf = got
                st.session_state[f"ss_{name}_answer"] = answer
                answer_set_item(name, k, item, owner_topic, n, quiz.mark(item, answer), conf, ctx, variants)
                st.session_state[shown_key] = k
                st.rerun()
        else:
            session_ui.shown(f"{name}{k}_0")
            knew = session_ui.recall_buttons(f"ss_{name}_{k}", *recall)
            if knew is not None:
                answer_set_item(name, k, {"type": "point"}, owner_topic, n, 1.0 if knew else 0.0, None, ctx, variants)
                st.session_state[shown_key] = k
                st.rerun()
        if st.button(tr("Skip the rest"), type="tertiary", key=f"ss_{name}_skip"):
            s["skipped"] = True
            ui.update_prefs(**{name: s})
            st.rerun()
    return False


def answer_quick(i, k, check, answer, conf) -> None:
    """Quick check k of lesson i answered (a second try after the hint)."""
    entry = day_entry()
    owner, slot = work(entry, i)
    before = (session.of(slot)["checks"].get(str(k)) or {}).get("tries", 0)
    right = answer == check["answer"]
    session.answer_check(slot, k, answer, right, conf)
    gap = gap_of(slot, owner["date"])
    if before == 0:                         # her first answer is the evidence (the second came after a hint)
        ui.learned(slot, owner["date"], "check", 1.0 if right else 0.0, source=f"qc{k}")
    save(entry, owner)
    ui.attempt([session_ui.row(today, topic, slot["n"], "check", check, 1.0 if right else 0.0, before == 0,
                               conf, session_ui.seconds(f"qc_{slot['n']}_{k}_{before}"), gap)])
    st.rerun()


def quick_check(i, slot, k, check) -> None:
    c = session.of(slot)["checks"].get(str(k)) or {"a": None, "tries": 0, "right": False}
    with st.container(key=f"qc_{slot['n']}_{k}"):
        st.html('<p class="hb-eyebrow">' + tr("Quick check") + "</p>")
        if c["right"] or c["tries"] >= session.TRIES:
            st.markdown(f"**{check['question']}**")
            session_ui.exercise_done(check, c["a"], 1.0 if c["right"] else 0.0, c["tries"])
            return
        got = session_ui.exercise_try(check, f"qc_{slot['n']}_{k}", c["tries"], c["a"], tag=False)
        if got:
            answer_quick(i, k, check, *got)


def answer_guided(i, k, answer, conf) -> None:
    entry = day_entry()
    owner, slot = work(entry, i)
    g = session.of(slot).get("guided")
    if not g:
        st.rerun()
    before = g["tries"][k]
    item = g["items"][k]
    mark = session.answer_guided(g, k, answer, conf)
    gap = gap_of(slot, owner["date"])
    if before == 0:
        ui.learned(slot, owner["date"], "check", mark, source=f"g{k}")
    save(entry, owner)
    ui.attempt([session_ui.row(today, topic, slot["n"], "guided", item, mark, before == 0, conf,
                               session_ui.seconds(f"g_{slot['n']}_{k}_{before}"), gap,
                               (f"fading:{g['order']}",))])
    if mark == 1 or g["tries"][k] >= session.TRIES:
        st.session_state.ss_g_shown = (slot["n"], k)
    st.rerun()


def set_stage(i, to: str) -> None:
    entry = day_entry()
    owner, slot = work(entry, i)
    session.move(slot, to)
    save(entry, owner)
    st.session_state.coach_scroll = ("current-lesson", False)
    st.session_state.coach_scroll_n = st.session_state.get("coach_scroll_n", 0) + 1
    st.rerun()


def jol(i, value: int, text: str) -> None:
    """The day's reflection: how sure she is she'll remember (compared later
    with how she does) and, if she likes, the one thing she takes away."""
    entry = day_entry()
    owner, slot = work(entry, i)
    session.keep(slot)["jol"] = value
    if text.strip():
        entry["reflection"] = text.strip()[:1000]
    ui.save_day(log, entry, [s["n"] for s in entry["lessons"]], keep=("reflection",) if text.strip() else (),
                recount=True, page_day=today)
    if owner is not entry:
        ui.save_day(log, owner, [slot["n"]], page_day=today)
    ui.update_prefs(reflected=today.isoformat())
    ui.attempt([attempts.row(today, topic, slot["n"], "jol", "jol", conf=value)])
    st.rerun()


# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    # A personal app with no key yet can take one here. The box never shows
    # the key from the app's secrets (it would be sent to the browser), and a
    # public app never offers it.
    client_ready = bool(st.session_state.api_key) and llm.GROQ_AVAILABLE
    if not client_ready and not auth.is_public():
        with st.expander(tr("Set the API key"), expanded=not st.session_state.api_key):
            if not llm.GROQ_AVAILABLE:
                st.caption(tr("Missing package: run `pip install groq`."))
            else:
                entered_key = st.text_input(
                    tr("Groq API key"),
                    type="password",
                    value="",
                    key="groq_key_entry",
                    help=tr("You can also set GROQ_API_KEY as an environment variable or secret."),
                )
                if entered_key and entered_key != st.session_state.api_key:
                    st.session_state.api_key = entered_key
                    st.rerun()


# ============================================================
# TODAY'S TOPIC: her subjects take turns, one a day (settings; Reading has its own page)
# ============================================================
topic = ui.topic_for(today)
start_level = settings.start_level(config, topic)
st.markdown("## " + i18n.day_long(today))
# with more than one subject or goal: which one today is, what comes next, and where to change it
coming = settings.days_ahead(config, today, ui.TIMEZONE, log)
if len(coming) >= 2:
    with st.container(key="today_turns", horizontal=True, vertical_alignment="center"):
        nxt = coming[1][1]
        then = (tr("then {n} more, in turn", n=len(coming) - 2) if len(coming) > 2 else tr("then they take turns"))
        st.html('<p class="today-turns">' + tr("Today: {today} · Tomorrow: {tomorrow} · {then}",
                                               today=escape(catalog.name(topic)), tomorrow=escape(catalog.name(nxt)),
                                               then=then) + "</p>")
        if st.button(tr("Change the order"), type="tertiary", key="today_order"):
            st.switch_page("views/settings.py")
with st.container(key="today_links", horizontal=True):
    if visuals.known(topic):         # into the day's subject, its world (a goal of hers has none)
        with st.container(key=f"enter_{topic}", horizontal=True):
            if st.button(tr('Enter {p0}', p0=catalog.name(topic)), type="tertiary", key="today_world"):
                ui.enter_world(topic)
    # the whole path, and how well she knows each idea on it (the learning map)
    if st.button(tr("Learning map"), type="tertiary", key="today_course"):
        ui.open_course(topic)
    short_on_time = st.container()         # (filled below, once her day is known)
# a unit just finished, its check never taken: pointed to once, here (the learning map keeps it)
fresh_unit = unitcheck.just_finished(log, topic, today)
if fresh_unit:
    with st.container(key="today_extras", gap=None):
        if st.button(tr('Unit check · {p0} · {p1} questions', p0=fresh_unit['name'], p1=unitcheck.size(log, topic, fresh_unit)),
                     type="tertiary", key="today_unit"):
            ui.open_unit(topic, fresh_unit["key"])
# ============================================================
# COMING BACK (coach/habit.py): a welcome after a break, a light day, her
# reminder, a milestone just reached, last week in review. Calm, and never
# more than one or two of them at once.
# ============================================================
habits = ui.prefs()
pace = settings.units(config)
light = habit.light_today(habits, today)
studied_today = today in core.streak_dates(log)
day_done = bool((core.find_entry(log, today, topic) or {}).get("completed"))


def set_light(on: bool) -> None:
    """A light day (one lesson), or back to her pace; today's day follows at once."""
    if ui.update_prefs(light_day=today.isoformat() if on else ""):
        ui.refit_today(habit.LIGHT_LESSONS if on else pace)


def set_brief(on: bool) -> None:
    """A five-minute day: recall and mixed practice, no new lesson (it counts)."""
    ui.update_prefs(brief_day=today.isoformat() if on else "")


brief = habits.get("brief_day") == today.isoformat()
returning = habit.returning(log, today) and not studied_today
if returning:
    r = habit.recap(log, today)
    where = (tr("Last time you were in {name}: Lesson {n}, “{title}”.", name=r['name'], n=r['n'], title=r['title']) + " "
             if r else "")
    with st.container(key="welcome_back"):
        st.html(tr('<p class="hb-eyebrow">Welcome back</p><p class="hb-text">{p0}We\'ll start with a few things to recall, then carry on from there. Take it at your own pace.</p>', p0=escape(where)))
        if not light and pace > habit.LIGHT_LESSONS:
            st.button(tr("Start with one lesson"), key="wb_light", on_click=set_light, args=(True,))
if not day_done and not (brief and today.isoformat() in habits.get("brief_days", [])):
    with st.container(key="light_day", horizontal=True, vertical_alignment="center"):
        if brief:
            st.html(tr('<p class="hb-text">A five-minute day: recall and a little practice. It counts.</p>'))
            st.button(tr("Do a lesson too"), key="brief_off", type="tertiary", on_click=set_brief, args=(False,))
        elif light:
            st.html(tr('<p class="hb-text">A light day: one lesson today.</p>'))
            st.button(tr('Back to {pace} lessons', pace=pace), key="light_off", type="tertiary", on_click=set_light, args=(False,))
        else:
            with short_on_time, st.popover(tr("Short on time?"), key="light_menu", type="tertiary"):
                st.caption(tr("Any of these counts as a day."))
                st.button(tr("Five minutes: recall and practice"), key="brief_on", type="tertiary",
                          on_click=set_brief, args=(True,), width="stretch")
                if pace > habit.LIGHT_LESSONS:
                    st.button(tr("One lesson today"), key="light_on", type="tertiary",
                              on_click=set_light, args=(True,), width="stretch")

# her reminder, shown here once its time has come and nothing is studied yet
if habit.reminder_due(habits, log, clock.now()) and ui.update_prefs(reminded_on=today.isoformat()):
    ui.record("reminder_shown")
    habits = ui.prefs()
if habits.get("reminded_on") == today.isoformat() and not studied_today:
    st.html(tr('<p class="hb-reminder">It\'s past your {p0} learning time. One short lesson is plenty today.</p>', p0=escape(habits["reminder_time"])))

def seen_now(keys: list) -> None:
    """Milestones shown: never again (added to what is stored now)."""
    ui.load_prefs()
    ui.update_prefs(seen=prefs_.mark_seen(ui.prefs(), keys)["seen"])


# a milestone she has just reached (what she had earned before is not news)
if not habits.get("seen_init"):
    ui.update_prefs(seen=[m["key"] for m in habit.milestones(log, today)], seen_init=True)
elif (fresh := habit.new_milestones(log, today, habits["seen"])):
    with st.container(key="milestone", horizontal=True, vertical_alignment="center"):
        more = " " + tr("(and {n} more in your Learning Record)", n=len(fresh) - 1) if len(fresh) > 1 else ""
        st.html(tr('<p class="hb-text"><span class="hb-eyebrow">Milestone</span>{p0}{p1}</p>', p0=escape(fresh[-1]["text"]), p1=escape(more)))
        st.button(tr("Thanks"), key="ms_seen", type="tertiary", on_click=seen_now, args=([m["key"] for m in fresh],))

# last week, in review: pointed to once a new week has begun
last_monday = habit.week_of(today) - timedelta(days=7)
if habits.get("week_seen") != habit.week_key(last_monday) and habit.week(log, last_monday, today)["lessons"]:
    if st.button(tr("Last week in review"), type="tertiary", key="today_week"):
        st.session_state.wk_which = "Last week"
        st.session_state.rec_tab_next = "Your week"         # the Learning Record's week tab
        st.switch_page("views/records.py")

# her own goal, before its first lesson: the path made for her, and what today holds
goal = catalog.path(topic)
if catalog.is_goal(topic) and goal is None:       # her goal couldn't be read just now (never a lesson in its place)
    st.warning(getattr(st.session_state.coach_store, "paths_error", None)
               or tr("Today's goal couldn't be found. Choose your goals again in Goals & Settings."))
    st.stop()
if goal and not paths.started(log, topic):
    with st.container(key="goal_intro"):
        st.html(goalmaker.summary_html(goal, settings.units(config), eyebrow=N_("Made for you · day one"),
                                       title=False))       # (the card below names it)
# before the first lesson of a path that can be placed: skip what she already knows (coach/diagnostic.py)
placed = (ui.prefs().get("diag") or {}).get(topic)
if diagnostic.offered(topic) and not curriculum.completed_numbers(log, topic) and not (placed and placed["applied"]):
    with st.container(key="diag_offer", horizontal=True, vertical_alignment="center"):
        st.html('<p class="hb-text">' + tr("Know some of this already? A five-minute check finds where you start, "
                                           "so you skip what you know.") + "</p>")
        if st.button(tr("Find my starting point"), type="tertiary", key="diag_open"):
            st.session_state.course_topic = topic
            st.switch_page("views/diagnostic.py", query_params={"subject": topic})
if "date" in st.query_params or "topic" in st.query_params:     # links from the old date picker
    st.query_params.clear()

if st.session_state.get("coach_toast"):           # set just before a rerun, shown after it
    st.toast(st.session_state.pop("coach_toast"))

entry = core.find_entry(log, today, topic)      # (re-read as stored at the start of this run: gnosis.py)
# a lesson carried over is written back to the day it began (work()): that
# day is refreshed too, or a save here would put an old copy of it back (ISS-010)
for began in sorted({s["from"] for s in curriculum.day_plan(log, topic, entry, ui.units_today()) if s.get("from")}):
    ui.refresh_entry(log, date.fromisoformat(began), topic)
plan = curriculum.day_plan(log, topic, entry, ui.units_today())

store = st.session_state.coach_store
if "lessons" in getattr(store, "missing_columns", ()):
    st.warning(
        tr("The database can't store lesson progress yet. Run supabase/lessons.sql in "
        "Supabase's SQL Editor, then refresh this page to start.")
    )
    st.stop()
if not plan:
    ready = capstone.offered(log, topic)
    if ready and goal:              # her goal, every lesson done: the last step is to use it (coach/capstone.py)
        with st.container(key="capstone_offer"):
            st.html('<div class="done"><p class="done-eyebrow">' + tr("Goal complete") + "</p><h3>"
                    + escape(goal.get("title") or catalog.name(topic)) + '</h3><p class="done-sub">'
                    + tr("Every lesson is done. One last step makes it yours: a real task that uses all of it.") + "</p></div>")
            if st.button(tr("Open your capstone"), type="primary", key="capstone_open"):
                st.switch_page("views/capstone.py", query_params={"subject": topic, "key": ready[0]["key"]})
    else:
        st.info(tr("You've finished all {p0} lessons written so far for {p1}. The next ones will appear once they're added.", p0=curriculum.written(topic), p1=catalog.name(topic)))
    st.stop()

# ============================================================
# WARM-UP: recall before reading (coach/session.py); the lesson is written meanwhile
# ============================================================
def start_mixed() -> None:
    """Today's mixed practice on earlier ideas (the interleaving experiment
    decides the order for the day)."""
    arm = ui.arm("interleave", today.isoformat())
    items = session.mixed(log, today, tuple((topic, x["n"]) for x in plan), interleaved=arm == "mixed")
    ui.update_prefs(mixed=session.new_set(today, items, arm=arm))


def spot_items() -> list:
    """A week after she skipped units as known: one question on each, in the
    warm-up (coach/diagnostic.py); missed, that unit comes back."""
    placed = (ui.prefs().get("diag") or {}).get(topic)
    if not placed or not placed["applied"]:
        return []
    by = {u["id"]: u for u in diagnostic.units(topic)}
    return [{"src": "bank", "topic": topic, "n": by[x["unit"]]["first"], "q": placed["items"][x["unit"]],
             "spot": x["unit"]} for x in diagnostic.due_spots(placed, today) if x["unit"] in by]


if day_set("warmup") is None and not day_done:
    size = session.WARMUP_BACK if returning else session.WARMUP
    spots = spot_items()
    ui.update_prefs(warmup=session.new_set(today, spots + session.warmup(log, today, max(1, size - len(spots)))))
warm = day_set("warmup")
if warm is not None and not warm["done"] and not warm["skipped"]:
    reached("warmup")
    prepare_lesson(steps.current(plan))          # written in the background while she recalls
    n_warm = len(warm["items"])
    if not run_set("warmup", "warmup", tr("Warm-up"),
                   trn("One thing to recall before today's lesson. Remembering it is what makes it stick.",
                       "{n} things to recall before today's lesson. Remembering them is what makes them stick.",
                       n_warm)):
        st.stop()

if brief:
    if day_set("mixed") is None:
        start_mixed()
    warm, mix = day_set("warmup"), day_set("mixed")
    answered_any = any(m is not None for x in (warm, mix) if x for m in x["marks"])
    if not (warm and warm["items"]) and not (mix and mix["items"]):
        # nothing to recall yet (her first days): one short lesson instead
        ui.update_prefs(brief_day="")
        set_light(True)
        st.session_state.coach_toast = tr("Nothing to recall yet, so today is one short lesson instead.")
        st.rerun()
    arm = mix["arm"] if mix else ""
    if not run_set("mixed", "mixed", tr("Mixed practice"),
                   tr("Earlier ideas, mixed: choosing the right method is part of the skill."),
                   variants=(f"interleave:{arm}",) if arm else ()):
        st.stop()
    if answered_any and today.isoformat() not in habits.get("brief_days", []):
        ui.update_prefs(brief_days=habits.get("brief_days", []) + [today.isoformat()])
    with st.container(key="brief_done"):
        st.html('<div class="done"><p class="done-eyebrow">' + tr("Complete") + "</p><h3>" + tr("Five minutes, done")
                + '</h3><p class="done-sub">' + tr("Recall and practice on a busy day keep what you know from fading. "
                                                    "It counts for today.") + "</p></div>")
        st.button(tr("Do a lesson too"), key="brief_more", on_click=set_brief, args=(False,))
    st.stop()

# ============================================================
# COURSE CARD: the bar, and the day's lessons as steps under it
# ============================================================
unit = curriculum.unit_progress(log, topic)

# Which lesson is open: her pick if it can be opened, otherwise the current
# one; once all are done nothing is open and the day's summary shows.
sel_key = f"lesson_{today.isoformat()}_{topic}"
i = st.session_state[sel_key] = steps.viewing(plan, st.session_state.get(sel_key))
now = steps.current(plan)
done_count = steps.done(plan)


def open_lesson(k, anchor="current-lesson", restore=False):
    """Open lesson k (None: the day's summary) and take the page to it."""
    st.session_state[sel_key] = k
    st.session_state.coach_scroll = (anchor, restore)
    st.session_state.coach_scroll_n = st.session_state.get("coach_scroll_n", 0) + 1
    st.rerun()


with st.container(key="course_card"):
    # title and one percentage; the five segments below are the bar itself
    progress_bar.render(f"card_{topic}", catalog.name(topic), done_count, len(plan),
                        bar=False, label=N_("Your goal") if goal else N_("Subject"), topic=unit["unit"])
    # the segment of a lesson just passed fills from left to right, once
    shown = st.session_state.setdefault("steps_shown", {})
    fresh = steps.just_completed(shown.get(sel_key), plan)
    shown[sel_key] = [p["completed"] for p in plan]
    # arriving on the page, the completed lessons fill one after another
    with st.container(key="lesson_steps_flow" if progress_bar.entering() else "lesson_steps", horizontal=True):
        for k, step in enumerate(steps.states(plan, i)):
            name = (f"step_{k}_{step['state']}" + ("_viewing" if step["viewing"] else "")
                    + ("_fresh" if k in fresh else ""))
            if st.button(str(plan[k]["n"]), key=name):
                if step["state"] == steps.LOCKED:
                    st.toast(steps.unlock_message(plan, k))     # stays on the lesson she has open
                elif k != i:
                    open_lesson(k, anchor="top")
    st.html(progress_bar.meta_row(steps.label(plan), old={"left": steps.label(plan)}))    # a label: it doesn't roll

# Remembers where she scrolled to in each lesson, and carries out a move
# (Back to the current lesson, Next lesson, a new answer) once the page has
# redrawn.
scroll_to, restore = st.session_state.pop("coach_scroll", ("", False))
st.html(place.html(chat_key(plan[i]) if i is not None else f"{today.isoformat()}|{topic}|done",
                   scroll_to, tr("Lesson {n}:", n=plan[i]['n']) if scroll_to and i is not None else "",
                   st.session_state.get("coach_scroll_n", 0), restore=restore),
        unsafe_allow_javascript=True)

# ============================================================
# THE QUIZ AND EXPLAINING IT BACK: what the lesson and the day's close draw
# ============================================================
def drop_reported(i, text):
    """A question she reported: its review card goes, and none is made from it again."""
    entry = day_entry()
    owner, held = work(entry, i)
    review.keep(log, held)
    review.drop_question(held, topic, text)
    save(entry, owner)


def report_question(q):
    report_ui.question(f"rep_q_{q['id']}", topic, slot["n"], slot.get("title", ""), q["questions"],
                       on_reported=lambda text: drop_reported(i, text))


def show_results(q, missed_only=False):
    """Each question with her answer, the right answer and the specific
    mistake (only the ones she lost points on with missed_only)."""
    for k, item in enumerate(q["questions"]):
        mark, mine = q["marks"][k], q["answers"][k]
        if mark == 1 and missed_only:
            continue
        if item.get("from"):
            st.html(tr('<p class="ex-earlier">From an earlier lesson · not part of the score</p>'))
        exercise.result(item, mine, mark, q["feedback"][k], k=k + 1)


def conclude(i):
    """Every question is marked: score it; a pass finishes the lesson. She
    stays on the lesson to read the explanations; Next lesson moves on."""
    entry = day_entry()
    owner, slot = work(entry, i)
    mastery.seed(slot, owner["date"])                        # (a lesson from before mastery: what it had first)
    gap = gap_of(slot, owner["date"])
    score = quiz.finish(slot["quiz"])
    q = slot["quiz"]
    sure = q.get("conf") or [None] * len(q["questions"])
    ui.learned(slot, owner["date"], "quiz", score / 100, source=f"{q['id']}-{q['attempts']}")   # the skill map
    review.keep(log, slot)                                   # (a lesson from before review: its old cards first)
    review.add_missed(slot, slot["quiz"], today, topic)      # what she missed comes back in a few days
    for k, item in enumerate(q["questions"]):                # wrong and sure: that card comes back first
        if learner.overconfident((q["marks"][k] or 0) >= 1, sure[k]) and not item.get("from"):
            card_id = review.question_card_id(topic, slot["n"], item["question"])
            for c in slot.get("cards") or []:
                if c["id"] == card_id:
                    c["hc"] = True
    if quiz.passed(score):
        review.add_key_idea(slot, today, topic)              # and, once it's passed, its key idea and words
        review.add_words(slot, today, topic)
        entry["lessons"][i]["completed"] = True
        if owner is not entry:          # the original day stays as it was; the lesson notes when
            slot["passed_on"] = today.isoformat()
        entry["completed"] = curriculum.day_complete(entry["lessons"])
        st.session_state.coach_toast = tr("Passed with {score}%.", score=score)
        # the page goes to the result, so Next lesson is in view (not under the chat box)
        st.session_state.coach_scroll = ("current-quiz", False)
        st.session_state.coach_scroll_n = st.session_state.get("coach_scroll_n", 0) + 1
    saved = save(entry, owner)
    for k, item in enumerate(q["questions"]):                # the question on an earlier idea: evidence for it
        if item.get("from") and q["marks"][k] is not None:
            ui.learned_elsewhere(log, topic, item["from"], "recall", q["marks"][k], source=f"{q['id']}-{k}")
    ui.attempt([session_ui.row(today, topic, item.get("from") or slot["n"], "quiz", item, q["marks"][k], True,
                               sure[k], None, None if item.get("from") else gap)
                for k, item in enumerate(q["questions"]) if q["marks"][k] is not None])
    if quiz.passed(score):
        reached("passed", slot["n"])
    if saved and quiz.passed(score):
        ui.record("lesson_passed")
        p = ui.prefs()                   # a lesson after today's reminder: did the reminder help? (coach/metrics.py)
        if p.get("reminded_on") == today.isoformat() and p.get("reminder_hit") != today.isoformat():
            if ui.update_prefs(reminder_hit=today.isoformat()):
                ui.record("reminded_session")
    st.rerun()


def run_grading(i):
    """Have the model mark the short answers, then score the quiz."""
    entry = day_entry()
    owner, slot = work(entry, i)
    system, messages = quiz.grading_request(slot["quiz"])
    with st.spinner(tr("Marking your answers…")):
        data, error = llm.ask_json(system, messages)
    if error or not quiz.apply_grading(slot["quiz"], data):
        save(entry, owner)               # keep her answers; Retry marks them
        failed("grade", error or llm.FAILED, slot, i=i)
    conclude(i)


def lesson_title(n):
    found = curriculum.lesson(topic, n)
    return tr("Lesson {n}: {title}", n=n, title=found['title']) if found else tr("Lesson {n}", n=n)


def run_explain(i, text):
    """The coach reads her explanation (one call) and answers as a teacher."""
    entry = day_entry()
    owner, slot = work(entry, i)
    if slot.get("explain") or practice.explained_today(log, today) >= practice.EXPLAIN_PER_DAY:
        st.rerun()                      # (already sent: a second click, or another tab)
    system, messages = practice.explain_request(slot, slot["title"], text)
    with st.spinner(tr("Your coach is reading it…")):
        data, error = llm.ask_json(system, messages)
    fb = practice.read_explain(data) if data else None
    if error or fb is None:
        failed("explain", error or llm.FAILED, slot, i=i, text=text)
    slot["explain"] = {"at": clock.now_iso(), "text": text.strip(), "feedback": fb}
    ui.learned(slot, owner["date"], "explain", fb["score"], source="explain")
    if save(entry, owner):
        ui.record("explained")
    ui.attempt([attempts.row(today, topic, slot["n"], "explain", "explain", score=fb["score"])])
    st.rerun()


def run_follow(i, text):
    """Her answer to the coach's one follow-up question (one call)."""
    entry = day_entry()
    owner, slot = work(entry, i)
    asked = (slot.get("explain") or {}).get("feedback", {}).get("question")
    if not asked or slot["explain"].get("reply_feedback"):
        st.rerun()
    system, messages = practice.follow_request(slot, slot["title"], asked, text)
    with st.spinner(tr("Your coach is reading it…")):
        data, error = llm.ask_json(system, messages)
    fb = practice.read_follow(data) if data else None
    if error or fb is None:
        failed("follow", error or llm.FAILED, slot, i=i, text=text)
    slot["explain"].update(reply=text.strip(), reply_feedback=fb)
    ui.learned(slot, owner["date"], "explain", fb["score"], source="explain-follow")
    save(entry, owner)
    st.rerun()


VERDICT = {1.0: N_("✓ Clear and correct."), 0.5: N_("◐ On the right track."), 0.0: N_("✗ Not there yet.")}


def explain_back(i, slot):
    """Explain it back: after a lesson is passed, once a day, she teaches its
    idea in her own words and the coach answers like a good teacher."""
    done = slot.get("explain")
    if not done and not practice.invite(log, topic, slot, today):
        return
    with st.container(key="explain_back"):
        st.html(tr('<p class="hb-eyebrow">Explain it back</p>'))
        if not done:
            st.html(tr('<p class="hb-text">Teach “{p0}” to a friend in two or three sentences: what it is, and why it matters. Putting it in your own words is one of the surest ways to make it stick.</p>', p0=escape(slot["title"])))
            if show_retry(slot, ("explain",)):
                return
            text = st.text_area(tr("Your explanation"), key=f"explain_{today}_{slot['n']}", height=110,
                                placeholder=tr("In my own words…"), label_visibility="collapsed")
            spot = st.empty()
            if spot.button(tr("Get feedback"), type="primary", key="explain_send"):
                problem = practice.precheck(text)
                if problem:
                    st.warning(problem)
                else:
                    spot.button(tr("Reading…"), disabled=True, key="explain_wait")
                    st.session_state.coach_retry = None
                    run_explain(i, text)
            st.caption(tr("Optional. A good explanation has the core idea, why it works, and no misconceptions."))
            return
        fb = done["feedback"]
        st.caption(tr('You wrote: {p0}', p0=done['text']))
        st.markdown(f"**{tr(VERDICT.get(fb['score'], ''))}** {fb['right']}")
        if fb.get("rubric"):            # what a good explanation has, and which of it hers had
            names = {"idea": tr("The core idea"), "why": tr("Why it works"), "accurate": tr("No misconceptions")}
            st.html('<ul class="ex-rubric">' + "".join(
                f'<li class="{"yes" if fb["rubric"][k] else "no"}">{"✓" if fb["rubric"][k] else "○"} {escape(names[k])}</li>'
                for k in practice.RUBRIC) + "</ul>")
        if fb.get("missing"):
            st.markdown(tr('**What to add:** {p0}', p0=fb['missing']))
        if fb.get("question") and not done.get("reply_feedback"):
            st.markdown(tr('**One question:** {p0}', p0=fb['question']))
            if show_retry(slot, ("follow",)):
                return
            reply = st.text_area(tr("Your answer"), key=f"explain_reply_{today}_{slot['n']}", height=80,
                                 placeholder=tr("Your answer (optional)"), label_visibility="collapsed")
            spot = st.empty()
            if spot.button(tr("Send"), key="explain_reply_send"):
                problem = practice.precheck(reply) if len((reply or "").split()) < 3 else ""
                if problem:
                    st.warning(problem)
                else:
                    spot.button(tr("Reading…"), disabled=True, key="explain_reply_wait")
                    st.session_state.coach_retry = None
                    run_follow(i, reply)
        elif done.get("reply_feedback"):
            st.markdown(tr('**One question:** {p0}', p0=fb['question']))
            st.caption(tr('You answered: {p0}', p0=done['reply']))
            rf = done["reply_feedback"]
            st.markdown(f"**{tr(VERDICT.get(rf['score'], ''))}** {rf['feedback']}")


@st.fragment
def answer_sheet(i, q):
    """The quiz questions. Each answer is kept the moment she gives it
    (widget state, plus a draft saved with the lesson, so answers survive
    reruns, a dropped connection, page switches and a reload), and only
    this block reruns while she answers."""
    if q.get("draft") is None:
        q["draft"] = quiz.blank_draft(q)
    draft = q["draft"]
    if not isinstance(q.get("conf"), list) or len(q["conf"]) != len(q["questions"]):
        q["conf"] = [None] * len(q["questions"])
    sure = q["conf"]
    saved = [list(a) if isinstance(a, list) else a for a in draft], list(sure)
    for k, item in enumerate(q["questions"]):
        if item.get("from"):            # one question on an earlier idea she found hard
            st.html(tr('<p class="ex-earlier">From an earlier lesson ({p0}) · it doesn\'t count toward your score</p>', p0=escape(lesson_title(item["from"]))))
        draft[k] = exercise.field(item, f"quiz_{q['id']}_{k}", draft[k], k=k + 1)
        # how sure she is of it (compared with how she did: calibration)
        ckey = f"quizconf_{q['id']}_{k}"
        sure[k] = st.segmented_control(tr("How sure are you?"), (1, 2, 3), key=ckey,
                                       default=sure[k] if ckey not in st.session_state else None,
                                       format_func=lambda c: tr(session_ui.CONF_LABELS[c]))
    if (draft, sure) != saved:
        save(day_entry(), work(day_entry(), i)[0])      # every answer is saved as she gives it
    submit = st.empty()
    if not submit.button(tr("Submit answers"), type="primary", use_container_width=True, key=f"submit_{q['id']}"):
        return
    entry = day_entry()
    if curriculum.blocking(entry["lessons"], i):    # finished strictly in order
        st.rerun()
    answers = [list(a) if isinstance(a, list) else a for a in draft]
    missing = [k + 1 for k, (item, a) in enumerate(zip(q["questions"], answers)) if not quiz.answered(item, a)]
    if missing:
        st.warning(tr("Answer every question first (still open: {numbers}).", numbers=", ".join(map(str, missing))))
        return
    submit.empty()
    owner, slot = work(entry, i)
    if quiz.submit(slot["quiz"], answers):
        save(entry, owner)
        run_grading(i)
    conclude(i)


# ============================================================
# ALL DONE: the day's summary
# ============================================================
if i is None:
    # a calm moment: what she did, what she knows now, and what tomorrow holds (the
    # streak is in the Learning Record: progress here is what she learned, not a count)
    rows = []
    for s in plan:
        score = (curriculum.content(log, topic, s).get("quiz") or {}).get("score")
        rows.append(f'<li><span class="n">{s["n"]}</span><span class="t">{escape(s["title"])}</span>'
                    f'<span class="q">{f"{score}%" if score is not None else ""}</span></li>')
    tomorrow = today + timedelta(days=1)
    t_next = ui.topic_for(tomorrow)
    upcoming = curriculum.next_numbers(log, t_next, settings.units(config)) if catalog.known(t_next) else []
    ahead = (tr("Tomorrow · {subject} · {which}", subject=catalog.name(t_next),
                which=(tr("Lesson {n}", n=upcoming[0]) if len(upcoming) == 1 else
                       tr("Lessons {first}–{last}", first=upcoming[0], last=upcoming[-1])))
             if upcoming else "")
    known = mastery.counts([x for x in mastery.ideas(log, topic, today) if x["reached"]])
    with st.container(key="day_done"):
        passed = (tr("The lesson is passed.") if len(plan) == 1 else tr("All {n} lessons passed.", n=len(plan)))
        knows = tr("In {subject} you now know {solid} ideas well, and {learning} are on their way.",
                   subject=catalog.name(topic), solid=known["solid"] + known["mastered"], learning=known["learning"])
        st.html('<div class="done"><p class="done-eyebrow">' + tr("Complete") + "</p><h3>" + tr("Today's done")
                + f'</h3><p class="done-sub">{passed} {escape(knows)}</p>'
                f'<ol class="done-list">{"".join(rows)}</ol>'
                + (f'<p class="done-next">{escape(ahead)}</p>' if ahead else "") + '</div>')
    # before she goes: mixed practice, her own words, a reflection (each once a day, each optional)
    last = len(plan) - 1
    last_slot = curriculum.content(log, topic, plan[last])
    if day_set("mixed") is None:
        start_mixed()
    mix = day_set("mixed")
    st.markdown(tr("#### Before you go"))
    if mix and not mix["done"] and not mix["skipped"]:
        reached("mixed")
        run_set("mixed", "mixed", tr("Mixed practice"),       # (each part is hers to do or leave)
                tr("A few earlier ideas, mixed: choosing the right method is part of the skill."),
                variants=(f"interleave:{mix['arm']}",) if mix["arm"] else ())
    if practice.invite(log, topic, last_slot, today) or (last_slot.get("explain") or {}).get("at", "")[:10] == today.isoformat():
        reached("explain", last_slot["n"])
        explain_back(last, last_slot)
    if ui.prefs().get("reflected") != today.isoformat():
        reached("reflect", last_slot["n"])
        with st.container(key="reflect"):
            st.html('<p class="hb-eyebrow">' + tr("Reflect") + "</p>")
            st.caption(tr("Saying how sure you are, then seeing how you do in a week, trains you to judge what you "
                          "really know."))
            thought = st.text_input(tr("The one thing you'll take from today (optional)"), key=f"reflect_{today}",
                                    placeholder=tr("In a sentence…"))
            value = session_ui.jol_buttons(f"reflect_{today}")
            if value:
                jol(last, value, thought or "")
    else:
        st.caption(tr("Reflection saved. See you next time."))
    st.stop()

slot = curriculum.content(log, topic, plan[i])     # a lesson carried over: its original
# Reviewing an earlier lesson: say so, with the way back to the current one.
if i != now:
    with st.container(key="review_bar", horizontal=True, vertical_alignment="center"):
        st.markdown(tr("You're reviewing Lesson {p0} · Completed", p0=slot['n']))
        way = steps.arrow(i, now)               # the arrow (drawn by CSS) points to where it goes
        if now is not None:
            if st.button(tr('Back to Lesson {p0}', p0=plan[now]['n']), key=f"back_to_current_{way}"):
                open_lesson(now, anchor="current-quiz" if curriculum.content(log, topic, plan[now]).get("lesson") else "current-lesson",
                            restore=True)
        elif st.button(tr("Back to today's summary"), key=f"back_to_current_{way}"):
            open_lesson(None, anchor="top")
if slot["unit"] and slot["unit"] != unit["unit"]:      # the card already names the current unit
    st.markdown(f"#### {slot['unit']}")
st.html('<div class="jump-anchor" id="current-lesson"></div>')
st.markdown(tr('### Lesson {p0}: {p1}', p0=slot['n'], p1=slot['title']))
aim = catalog.goal_objective(topic, slot["n"]) if goal else ""
if aim:                 # what she'll be able to do by the end (her goal's outline: coach/paths.py)
    st.html(tr('<p class="lesson-aim"><span>You\'ll be able to</span>{p0}</p>', p0=escape(aim)))

chat = get_chat(slot)
if not chat:
    show_retry(slot, ("kickoff",))
    gate = progression.gate(log, topic) if i == now else None
    if (before := curriculum.blocking(plan, i)):
        st.caption(tr('Pass the quiz for Lesson {p0} first, then start this one.', p0=before['n']))
    elif gate is not None:
        # mastery before moving on (coach/progression.py): the unit this one builds on, shown learned as a whole
        with st.container(key="unit_gate"):
            st.html('<p class="hb-eyebrow">' + tr("Before the next unit") + "</p>"
                    + '<p class="hb-text">' + tr("“{opens}” builds on “{unit}”. Show you've learned it as a whole: "
                                                 "{n} questions from its lessons, {mark}% to pass. Missed ideas get "
                                                 "practice, then a fresh set.", opens=escape(gate["opens"]),
                                                 unit=escape(gate["name"]), n=unitcheck.size(log, topic, gate),
                                                 mark=unitcheck.PASS_MARK) + "</p>")
            if st.button(tr("Take the unit check"), type="primary", key="gate_check", width="stretch"):
                ui.open_unit(topic, gate["key"])
    else:
        start = st.empty()          # the button goes away while the lesson is written
        if start.button(tr("Start this lesson"), type="primary", use_container_width=True):
            start.empty()
            st.session_state.coach_retry = None
            run_kickoff(i)
    st.stop()

# ============================================================
# LESSON + CHAT: read (with its quick checks), practise, check (coach/session.py)
# ============================================================
passed_early = shown_entry()["lessons"][i]["completed"]
stage = "check" if passed_early else session.stage(slot)
session_ui.stepper(stage, passed_early)
reading = stage == "learn" and not passed_early
lesson_text = slot.get("lesson", "")
checks = session.quick_checks(lesson_text)
if not passed_early:
    reached(stage if stage != "check" else "quiz", slot["n"])
    prepare_quiz(slot)              # the check and its practice, written and checked while she reads


def sources_for(slot) -> list:
    """Where she can check the lesson herself: the curriculum's sources for
    its unit (linked only: their text is never given to the AI)."""
    if topic != "math":
        return []
    unit_ = mathcourse.units().get((slot.get("unit") or "").split(" ")[0])
    return [(x.get("organization") or x["title"], x["url"]) for x in mathcourse.sources_of(unit_)][:3] if unit_ else []


def show_lesson(text: str) -> None:
    """The lesson in its sections, each of the first two followed by its quick check."""
    for j, (kind, part) in enumerate(session.without_checks(text)):
        if kind == "text":
            lesson_view.render(part, topic, key=f"{chat_key(slot)}|{j}", title=slot.get("title", ""), links=False)
        elif part < len(checks):
            quick_check(i, slot, part, checks[part])
    lesson_view.check_links(slot.get("title", ""), sources_for(slot))


last_question = max((k for k, m in enumerate(chat) if k > 1 and m["role"] == "user"), default=None)
for k, message in enumerate(chat[1:], start=1):   # the kickoff line is shown as the heading
    if k == last_question:
        st.html(place.latest_anchor())
    with st.chat_message(message["role"]):
        if k == 1 and reading:
            show_lesson(message["content"])       # cards, tables, diagrams, and its quick checks
        elif k == 1:
            with st.expander(tr("The lesson"), expanded=False):      # there to look back at, out of the way
                lesson_view.render_tabs(session.strip_checks(message["content"]), topic, key=chat_key(slot),
                                        title=slot.get("title", ""))
        elif message["role"] == "assistant":
            body, where, _ = practice.split_reply(message["content"], slot.get("lesson", ""))
            st.markdown(body)
            if practice.based_label(where):          # where the answer comes from, or that it isn't sure
                st.html(f'<p class="tutor-based">{escape(practice.based_label(where))}</p>')
        else:
            st.markdown(message["content"])
reply_spot = st.container()     # a new question and its answer appear here, under the others
# an earlier day's lesson not passed yet may have been written under older rules: hers to rewrite
if st.session_state.pop("coach_rewritten", None) == slot["n"]:
    st.html(tr('<p class="ob-note" role="status">Rewritten with our latest guidelines.</p>'))
elif not slot.get("completed") and slot.get("lesson") and plan[i].get("from"):      # (carried over)
    if st.button(tr("Rewrite this lesson"), type="tertiary", key=f"rewrite_{slot['n']}",
                 help=tr("Written again with our latest guidelines (one of today's AI requests). "
                      "Your questions and progress stay.")):
        run_rewrite(i)

with st.container(key="lesson_tools", horizontal=True):
    # Key points she wants back later (review): the Key Idea and each Deep Dive point
    points = review.key_points(slot.get("lesson", ""))
    if points:
        with st.popover(tr("Save for review"), key=f"save_menu_{slot['n']}"):
            st.caption(tr("A saved point comes back in your warm-up, then further apart each time you know it."))
            for k, (label, text) in enumerate(points):
                kept = review.saved(slot, label)
                if st.button(label, key=f"save_point_{slot['n']}_{k}", disabled=kept, help=text[:240],
                             icon=":material/check:" if kept else None, type="tertiary"):
                    entry = day_entry()
                    owner, held = work(entry, i)
                    review.keep(log, held)
                    review.save_point(held, label, text, today, topic)
                    if save(entry, owner):
                        st.toast(tr('Saved for review: {label}', label=label))
                    st.rerun()
    # something wrong or unclear in it: said in two taps (audit stage 2; what is sent: coach/report_ui.py)
    report_ui.lesson(f"rep_lesson_{topic}_{slot['n']}", topic, slot["n"], slot.get("title", ""), slot.get("lesson", ""))

entry = shown_entry()
owner, slot = work(entry, i)
passed_here = entry["lessons"][i]["completed"]     # (a carried-over lesson: passed on this day)
place_ = session.of(slot)

# ------------------------------------------------------------- read: then practise
if reading:
    st.html('<div class="jump-anchor" id="current-quiz"></div>')
    with st.container(key="stage_next"):
        if checks and not session.checks_done(slot, len(checks)):
            st.caption(tr("The quick checks above are there to help it stick. Do them, or go on when you're ready."))
        if st.button(tr("Next: practise it →"), type="primary", width="stretch", key="to_practice"):
            set_stage(i, "practice")
        if st.button(tr("I know this: straight to the check"), type="tertiary", key="to_check"):
            set_stage(i, "check")

# ------------------------------------------------------------- practise: guided practice
elif stage == "practice" and not passed_here:
    st.html('<div class="jump-anchor" id="current-quiz"></div>')
    st.markdown(tr("#### Practice"))
    g = place_.get("guided")
    if g is None:
        # the check and its practice: prepared while she read (coach/quizprep.py), or written now
        if not show_retry(slot, ("quiz",)):
            spot = st.empty()
            spot.button(tr("Getting your practice ready…"), disabled=True, type="primary", width="stretch",
                        key="practice_preparing")
            run_quiz(i)
        st.stop()
    left = session.guided_left(g)
    just = st.session_state.get("ss_g_shown")
    k = just[1] if just and just[0] == slot["n"] and just[1] < len(g["items"]) else (left[0] if left else None)
    if k is None:
        right = sum(1 for m in g["marks"] if m == 1)
        st.caption(tr("Practice done: {right} of {n} right. Now the check: six questions on what this lesson teaches.",
                      right=right, n=len(g["items"])) if g["items"] else
                   tr("No practice this time. On to the check: six questions on what this lesson teaches."))
        if st.button(tr("Next: the check →"), type="primary", width="stretch", key="to_check_done"):
            set_stage(i, "check")
    else:
        item = g["items"][k]
        lead = (tr("A worked example with a step or two left for you. Follow the steps, then fill in the gaps.")
                if item["type"] == "steps" else tr("Now one on your own."))
        with st.container(key=f"guided_{slot['n']}_{k}"):
            st.html(f'<p class="ss-sub">{escape(lead)}</p>')
            if just:
                st.markdown(f"**{item['question']}**")
                session_ui.exercise_done(item, g["answers"][k], g["marks"][k], g["tries"][k])
                if st.button(tr("Next"), type="primary", width="stretch", key="guided_next"):
                    st.session_state.ss_g_shown = None
                    st.rerun()
            else:
                got = session_ui.exercise_try(item, f"g_{slot['n']}_{k}", g["tries"][k], g["answers"][k])
                if got:
                    answer_guided(i, k, *got)
        if not just and st.button(tr("Skip to the check"), type="tertiary", key="guided_skip"):
            set_stage(i, "check")

# ------------------------------------------------------------- check: the mastery check
else:
    st.html('<div class="jump-anchor" id="current-quiz"></div>')
    st.markdown(tr("#### Check"))
    q = slot.get("quiz")
    # a quiz written under older rules that she hasn't answered: a new one, written and checked under
    # today's rules, takes its place when she starts (attempts and best score carry over; one she
    # answered stays as it was). Started answers on the old one are hers to keep or let go.
    renewed = not passed_here and quiz.outdated(q) and not quiz.has_draft(q)
    if renewed:
        q = None
    if passed_here:
        if q and quiz.passed(q.get("score")):
            st.markdown("**" + progress_bar.rolled(f"quiz_pass_{q['id']}", tr("Passed with {score}%", score=q['score']))
                        + "** · " + progress_bar.rolled(f"quiz_points_{q['id']}", tr("{n} points.", n=quiz.points(q))),
                        unsafe_allow_html=True)
            with st.expander(tr("See the check")):     # this attempt's answers and explanations
                show_results(q)
                report_question(q)
        else:
            st.caption(tr("This lesson is done."))
        if goal and slot["n"] == 1:          # her goal's first lesson: a small win, said plainly
            left_n = paths.lesson_count(goal) - 1
            st.html(trn('<p class="goal-win"><b>First step done.</b> {n} lesson to go on “{goal}”.</p>', '<p class="goal-win"><b>First step done.</b> {n} lessons to go on “{goal}”.</p>', left_n, goal=escape(goal["title"])))
        # just passed: on to the lesson this one unlocked, or the day's close after the last
        if now is not None and now == i + 1:
            if st.button(tr("Next lesson →"), type="primary", use_container_width=True, key="next_lesson"):
                open_lesson(now)
        elif now is None and i == len(plan) - 1:
            if st.button(tr("Finish today →"), type="primary", use_container_width=True, key="next_lesson"):
                open_lesson(None, anchor="top")
        # what she knows of it: below the way on, never in front of it
        idea = mastery.state(mastery.evidence(slot, owner["date"]), today)
        st.html(tr('<p class="idea-state">This idea: <b>{p0}</b> · {p1}</p>', p0=tr(mastery.LEVEL_NAMES[idea["level"]]), p1=escape(mastery.describe(dict(idea, reached=True)))))
    elif (before := curriculum.blocking(entry["lessons"], i)):
        # e.g. a lesson started under the old tick box before the one ahead of it was finished
        st.caption(tr('Pass the check for Lesson {p0} first; this one opens after that.', p0=before['n']))
    elif q is not None and quiz.needs_grading(q):
        # submitted, but marking the short answers (a quiz from before) didn't go through yet
        st.caption(tr("Your answers are saved. They just need marking."))
        retrying = show_retry(slot, ("grade",))
        mark = st.empty()
        if not retrying and mark.button(
                tr("Mark my answers"), type="primary", use_container_width=True):
            mark.empty()
            run_grading(i)
    elif q is None or q["answers"] is not None and not quiz.passed(q["score"]):
        if q is not None:               # the last attempt fell short: what was missed, why, and a way back
            st.markdown("**" + progress_bar.rolled(f"quiz_score_{q['id']}", f"{q['score']}%") + "** · "
                        + progress_bar.rolled(f"quiz_points_{q['id']}", tr("{n} points.", n=quiz.points(q))) + " "
                        + tr("You need {mark}% to move on. Look at what you missed and why, then a new set is "
                             "ready when you are.", mark=quiz.PASS_MARK),
                        unsafe_allow_html=True)
            with st.expander(tr("See what you missed"), expanded=True):
                show_results(q, missed_only=True)
                report_question(q)
            if st.button(tr("Read the lesson again"), type="tertiary", key="reread"):
                set_stage(i, "learn")
        elif renewed:
            st.caption(tr("This check has been rewritten with our latest checks for clear, correct questions. "
                       "Your earlier attempts still count."))
        else:
            st.caption(tr('{p0} questions on what this lesson teaches: choices, a situation, a blank to fill, matching or ordering, and a mistake to spot. Score {p1}% or more to finish it.', p0=quiz.QUESTIONS, p1=quiz.PASS_MARK))
        retrying = show_retry(slot, ("quiz",))
        take = st.empty()               # can't be pressed again while the quiz is being written
        if not retrying and take.button(tr("Start the check") if q is None else tr("Try a new set"), type="primary", use_container_width=True, key="take_check"):
            take.button(tr(PREPARING), disabled=True, type="primary", use_container_width=True, key="quiz_preparing")
            st.session_state.coach_retry = None
            run_quiz(i)
    else:
        if quiz.outdated(q):           # older rules, answers started: hers to finish, or the new quiz instead
            with st.container(key="quiz_renew", horizontal=True, vertical_alignment="center"):
                st.html(tr('<p class="ob-note">A newer, checked version of this quiz is available.</p>'))
                if st.button(tr("Use the new quiz"), type="tertiary", key="quiz_renew_go",
                             help=tr("Your answers so far on this one are cleared; earlier attempts still count.")):
                    run_quiz(i)
        answer_sheet(i, q)

if entry["completed"]:
    st.caption(tr('All {lessons} lessons done for today.', lessons=len(entry['lessons'])))
else:
    left_n = sum(1 for s in entry["lessons"] if not s["completed"])
    st.caption(trn('{n} lesson to go today.', '{n} lessons to go today.', left_n))

show_retry(slot, ("followup",))
# The chat box stays at the bottom of the screen wherever she has scrolled
# (it sticks there with CSS). It isn't Streamlit's own bottom bar: that one
# keeps the page scrolled to the end, so Today wouldn't open at the top.
with st.container(key="chat_dock"):
    prompt = st.chat_input(tr('Ask about Lesson {p0}…', p0=slot['n']))
if prompt is not None and prompt.strip():
    st.session_state.coach_retry = None
    with reply_spot:
        run_followup(i, prompt)
