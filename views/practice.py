"""Practice: a short set on the ideas she knows least (coach/practice.py),
one exercise at a time, each marked at once with the specific mistake, each
answer evidence for its idea (coach/mastery.py). The set is kept in her
preferences, so a refresh or another device finds her place; an answer is
taken once (a second click changes nothing). Exercises come from what she
has; only when an idea has none left does the model write some (two calls,
once a day), and they are kept for next time."""
from html import escape

import streamlit as st

from coach import catalog, exercise, llm, mastery, practice, quiz, tokens, ui

log = st.session_state.coach_log
today = ui.today()
st.html('<div id="practice-page" hidden></div>')
st.markdown("## Practice")


def current():
    """Today's set as stored now (another tab may have moved on), or None."""
    ui.load_prefs()
    p = ui.prefs().get("practice")
    return p if p and p["date"] == today.isoformat() else None


def idea_key(topic, n) -> str:
    return f"{topic}|{n}"


def levels_now() -> dict:
    out = {}
    for t in mastery.topics(log):
        for x in mastery.ideas(log, t, today):
            if x["reached"]:
                out[idea_key(t, x["n"])] = x["level"]
    return out


def write_more(short: list) -> None:
    """The model writes exercises for ideas with none left (write + check),
    kept in each lesson's bank. Once a day; a failure leaves the set as it is."""
    ideas = []
    for k, (topic, n, title) in enumerate(short, start=1):
        held = mastery.holder(log, topic, n)
        if held:
            ideas.append((k, title, practice.key_text(held[1])))
    if not ideas:
        return
    ui.update_prefs(practice_made=today.isoformat())      # (once a day, even if it fails: never a loop of calls)
    system, messages = practice.make_request(ideas)
    with st.spinner("Writing new exercises for the ideas you need most…"):
        data, error = llm.ask_json(system, messages, max_tokens=tokens.QUIZ_MAX_TOKENS, salvage=quiz.salvage)
    made = practice.made(data, len(ideas)) if data else {}
    flat = [(k, q) for k, qs in made.items() for q in qs]
    if error or not flat:
        st.session_state.pr_problem = error or "New exercises couldn't be written just now. These are from your lessons."
        return
    system, messages = quiz.check_request([q for _, q in flat])
    with st.spinner("Checking every answer…"):
        verdict, error = llm.ask_json(system, messages)
    flagged = quiz.problems(verdict, len(flat)) if verdict else None
    if error or flagged is None:
        st.session_state.pr_problem = error or "New exercises couldn't be checked just now. These are from your lessons."
        return
    for j, (k, q) in enumerate(flat):
        if j in flagged:
            continue
        topic, n, _ = short[k - 1]
        held = mastery.holder(log, topic, n)
        if held is None:
            continue
        held[1]["bank"] = (held[1].get("bank") or []) + [q]
    for topic, n, _ in short:
        held = mastery.holder(log, topic, n)
        if held and held[1].get("bank"):
            ui.save_day(log, held[0], [n])


def start(avoid=()) -> None:
    """A new set for today (the ideas she needs most), saved before it's shown."""
    s = practice.build(log, today, avoid=avoid)
    if s["short"] and ui.prefs().get("practice_made") != today.isoformat():
        write_more(s["short"])
        s = practice.build(log, today, avoid=avoid)
    if not s["items"]:
        st.session_state.pr_problem = st.session_state.get("pr_problem") or "No exercises are ready for these ideas yet."
        return
    before = levels_now()
    st.session_state.pr_again = False
    ui.update_prefs(practice={"date": today.isoformat(), "items": s["items"], "answers": [None] * len(s["items"]),
                              "marks": [None] * len(s["items"]), "done": False, "seen": list(avoid),
                              "before": {idea_key(x["topic"], x["n"]): before.get(idea_key(x["topic"], x["n"]), "new")
                                         for x in s["items"]}})


def check(k: int, answer) -> None:
    """Mark exercise k (once), save the evidence for its idea, keep her place."""
    p = current()
    if p is None or p["marks"][k] is not None:
        return                      # (already marked: a second click, or another tab)
    item = p["items"][k]
    mark = quiz.mark(item["q"], answer)
    p["answers"][k], p["marks"][k] = answer, mark
    ui.learned_elsewhere(log, item["topic"], item["n"], "practice", mark,
                         source=f"{practice.qid(item['q'])}-{today.isoformat()}")
    if None not in p["marks"]:
        p["done"] = True
        ui.record("practice_done")
    ui.update_prefs(practice=p)


p = current()
problem = st.session_state.pop("pr_problem", "")
weak = mastery.needs_practice(log, today)

# ------------------------------------------------------------------ no set yet
if p is None or (p["done"] and st.session_state.get("pr_again")):
    if p is None and not mastery.weakest(log, today, limit=1):
        st.markdown("### Nothing to practise yet")
        st.caption("Practice opens once you've taken a lesson's quiz: it then picks the ideas you know least "
                   "and mixes short exercises on them.")
        if st.button("Back to Home", key="pr_back", type="tertiary"):
            st.switch_page("views/daily.py")
        st.stop()
    names = [f"{i['title']}" for _, _, i in (weak or mastery.weakest(log, today, limit=3))[:practice.IDEAS_PER_SET]]
    count = min(practice.SET_SIZE, practice.PER_IDEA * len(names))
    st.html('<p class="hb-eyebrow">Focus for today</p>'
            f'<p class="hb-text">{len(names)} {"idea" if len(names) == 1 else "ideas"} you know least: '
            + ", ".join(f"“{escape(x)}”" for x in names) + ". "
            f"{count} short exercises, mixed, about {count} minutes.</p>")
    if not weak:
        st.caption("Nothing is fading right now. A short set keeps what's solid on its way to mastered.")
    if problem:
        st.caption(problem)
    spot = st.empty()
    if spot.button("Start practice", type="primary", key="pr_start", width="stretch"):
        spot.button("Getting it ready…", disabled=True, key="pr_wait", width="stretch")
        start(avoid=tuple((p or {}).get("seen") or ()) + tuple(practice.qid(x["q"]) for x in (p or {}).get("items", [])))
        st.rerun()
    st.stop()

# ------------------------------------------------------------------ the summary
if p["done"] and st.session_state.get("pr_shown") is None:     # (after the last answer's feedback)
    now = levels_now()
    right = sum(1 for m in p["marks"] if m == 1)
    st.markdown("### Practice done")
    st.caption(f"{right} of {len(p['marks'])} right. Each answer went into your skill map.")
    seen = []
    rows = []
    for x in p["items"]:
        key = idea_key(x["topic"], x["n"])
        if key in seen:
            continue
        seen.append(key)
        held = mastery.holder(log, x["topic"], x["n"])
        title = held[1]["title"] if held else f"Lesson {x['n']}"
        was, is_ = p["before"].get(key, "new"), now.get(key, "new")
        change = (f"{mastery.LEVEL_NAMES[was]} → {mastery.LEVEL_NAMES[is_]}" if was != is_
                  else mastery.LEVEL_NAMES[is_])
        rows.append(f'<li><span>{escape(title)}</span><small>{escape(catalog.name(x["topic"]))} · '
                    f'{escape(change)}</small></li>')
    st.html('<ul class="wk-review pr-ideas">' + "".join(rows) + "</ul>")
    st.caption("An idea becomes solid when it holds on another day, and mastered when it keeps holding "
               "over a week or more. Coming back tomorrow does more than another set today.")
    done_ids = tuple(p.get("seen") or ()) + tuple(practice.qid(x["q"]) for x in p["items"])
    nxt = practice.build(log, today, avoid=done_ids)
    more = bool(nxt["items"]) or bool(nxt["short"] and ui.prefs().get("practice_made") != today.isoformat())
    if not more or problem:
        st.caption(problem or "That's all the practice ready for today. New exercises come tomorrow.")
    with st.container(horizontal=True, key="pr_end"):
        if st.button("Knowledge map", type="primary", key="pr_map"):
            st.switch_page("views/skills.py")
        if more and st.button("Another set", key="pr_more", type="tertiary"):
            st.session_state.pr_again = True
            st.rerun()
        if st.button("Back to Home", key="pr_today", type="tertiary"):
            st.switch_page("views/daily.py")
    st.stop()

# ------------------------------------------------------------------ one exercise
k = next(j for j, m in enumerate(p["marks"]) if m is None) if st.session_state.get("pr_shown") is None \
    else st.session_state.pr_shown
k = min(k, len(p["items"]) - 1)
item = p["items"][k]
done = sum(1 for m in p["marks"] if m is not None)
st.html(f'<div class="rv-pace"><div class="rv-line"><span style="width:{done / len(p["items"]) * 100:.0f}%"></span>'
        f'</div><p>{done} of {len(p["items"])} done</p></div>')
held = mastery.holder(log, item["topic"], item["n"])
st.caption(f"{catalog.name(item['topic'])} · Lesson {item['n']}" + (f": {held[1]['title']}" if held else ""))
key = f"pr_{p['date']}_{k}_{practice.qid(item['q'])}"
if p["marks"][k] is None:
    answer = exercise.field(item["q"], key)
    spot = st.empty()
    if spot.button("Check", type="primary", key=f"{key}_check", width="stretch",
                   disabled=not quiz.answered(item["q"], answer)):
        check(k, answer)
        st.session_state.pr_shown = k
        st.rerun()
else:
    q, mark = item["q"], p["marks"][k]
    st.markdown(f"### {q['question']}")
    st.markdown(f"**{exercise.sign(mark)} {exercise.verdict(mark)}**")
    exercise.result(q, p["answers"][k], mark, show_question=False)
    if st.button("Next" if None in p["marks"] else "See how it went", type="primary", key="pr_next", width="stretch"):
        st.session_state.pr_shown = None
        st.rerun()
st.caption("Practice never holds up your lessons. Stop any time; your place is kept for today.")
