"""Review: one card at a time, then the collection she can look through.

The cards (coach/review.py) are her missed quiz questions, the words of the
lessons she has passed and the points she saved. Answers are checked here,
without the model: a question against its stored answer, a word as "which
meaning?", a saved point by her own honest "I knew it" / "Not yet"."""
from datetime import date
from html import escape

import streamlit as st

from coach import core, review, ui

log = st.session_state.coach_log
today = ui.today()
st.html('<div id="review-page"></div>')
st.markdown("## Review")
st.caption("What you've learned comes back just before you'd forget it: a day later, then further apart "
           "each time you know it. A few minutes a day; your lessons never wait for it.")

VIEWS = ["Today", "Collection"]
st.session_state.setdefault("rv_view", "Today")
view = st.segmented_control("Show", VIEWS, key="rv_view", required=True,
                            label_visibility="collapsed") or "Today"


def holder(card_id):
    """(entry, slot, card) as stored now (another tab may have reviewed it)."""
    found = review.find(log, card_id)
    if found is not None:
        ui.refresh_entry(log, date.fromisoformat(found[0]["date"]), found[0]["topic"])
        found = review.find(log, card_id)
    if found is not None and "cards" not in found[1]:     # from before review: keep that lesson's cards now
        review.keep(log, found[1])
        found = review.find(log, card_id)
    return found


def answered(card_id, right):
    found = holder(card_id)
    if found is None:
        st.rerun()
    e, _, card = found
    review.grade(card, right, today)
    if not ui.save_entry(log, e):
        ui.show_pending_error()
    st.session_state.rv_current = {"id": card_id, "right": right}
    st.rerun()


def when(iso):
    d = date.fromisoformat(iso)
    if d <= today:
        return "due today"
    if (d - today).days == 1:
        return "tomorrow"
    return f"{d:%a}, {d:%b} {d.day}"


def source(card):
    subject = core.TOPICS.get(card.get("topic"), "")
    lesson = f"Lesson {card['n']}" if card.get("n") else ""
    return " · ".join(x for x in (review.KIND_NAMES[card["kind"]], subject, lesson) if x)


# ============================================================
# TODAY'S REVIEW: one card at a time
# ============================================================
def show_question(card, q):
    """A stored question (or a word asked as one), checked on the spot."""
    key = f"rv_{card['id']}_{card['reviews']}"
    if q["type"] == "choice":
        pick = st.radio(q["question"], range(len(q["options"])), index=None, key=key,
                        format_func=lambda o: q["options"][o])
        if st.button("Check", type="primary", key=f"{key}_check", disabled=pick is None, width="stretch"):
            answered(card["id"], pick == q["answer"])
    elif q["type"] == "match":
        st.markdown(q["question"])
        picks = []
        for j, left in enumerate(q["left"]):
            picks.append(st.selectbox(left, range(len(q["right"])), index=None, key=f"{key}_{j}",
                                      placeholder="Choose its match", format_func=lambda o: q["right"][o]))
        if st.button("Check", type="primary", key=f"{key}_check", disabled=None in picks, width="stretch"):
            answered(card["id"], picks == q["key"])
    else:
        recall(card, q["question"], f"A good answer: {q['answer']}")


def recall(card, prompt, answer):
    """Recall it, look, and say honestly whether she knew it."""
    st.markdown(f"**{prompt}**")
    shown = st.session_state.get("rv_shown") == card["id"]
    if not shown:
        st.caption("Say it to yourself first, then look.")
        if st.button("Show the answer", type="primary", key=f"rv_show_{card['id']}", width="stretch"):
            st.session_state.rv_shown = card["id"]
            st.rerun()
        return
    st.markdown(answer)
    with st.container(horizontal=True, key="rv_self"):
        if st.button("I knew it", type="primary", key=f"rv_yes_{card['id']}", width="stretch"):
            st.session_state.rv_shown = None
            answered(card["id"], True)
        if st.button("Not yet", key=f"rv_no_{card['id']}", width="stretch"):
            st.session_state.rv_shown = None
            answered(card["id"], False)


def feedback(card, right):
    """Just answered: right or not (said in words, not only colour), the answer, what's next."""
    st.markdown(f"**{'✓ Right.' if right else '✗ Not quite.'}** " +
                (f"It comes back {when(card['due'])}." if right else "It comes back tomorrow."))
    if card["kind"] == "question":
        item = card["question"]
        st.caption(f"Answer: {review._answer_text(item)}" + (f". {item['why']}" if item.get("why") else ""))
    elif card["kind"] == "word":
        st.caption(f"{card['front']}: {card['back']}" + (f" — {card['example']}" if card.get("example") else ""))


def pace(left):
    """How far through today's cards: a hairline and a few words."""
    done = review.reviewed_today(log, today)
    share = done / (done + left) if done + left else 1
    st.html(f'<div class="rv-pace"><div class="rv-line"><span style="width:{share * 100:.0f}%"></span></div>'
            f'<p>{done} done · {left} to go today</p></div>')


def today_view():
    current = st.session_state.get("rv_current")
    found = review.find(log, current["id"]) if current else None
    due = review.due(log, today)
    if found is not None:
        card = found[2]
        pace(len(due))
        st.caption(source(card))
        st.markdown(f"### {card['front'] if card['kind'] != 'question' else card['question']['question']}")
        feedback(card, current["right"])
        label = "Next card" if due else "Finish"
        if st.button(label, type="primary", key="rv_next", width="stretch"):
            st.session_state.rv_current = None
            st.rerun()
        return
    if not due:
        done = review.reviewed_today(log, today)
        if not review.cards(log):
            st.markdown("### Nothing to review yet")
            st.caption("Questions you miss in a quiz, the words of each lesson you pass and the points you "
                       "save come back here a day later, then further apart each time you know them.")
        else:
            st.markdown("### All reviewed for today" if done else "### Nothing due today")
            nxt = review.next_due(log, today)
            parts = ([f"You reviewed {done} {'card' if done == 1 else 'cards'} today."] if done else []) + \
                ([f"The next ones come back {when(nxt.isoformat())}."] if nxt else [])
            waiting = [c for _, _, c in review.cards(log)
                       if not c["paused"] and c["due"] <= today.isoformat() and c.get("last") != today.isoformat()]
            if waiting:
                parts = [f"That's today's {review.DAILY_LIMIT}. The other {len(waiting)} wait for tomorrow."]
            st.caption(" ".join(parts))
        if st.button("Back to Today", key="rv_back", type="tertiary"):
            st.switch_page("views/daily.py")
        return
    _, _, card = due[0]
    pace(len(due))
    st.caption(source(card))
    if card["kind"] == "question":
        show_question(card, card["question"])
    elif card["kind"] == "word":
        q = review.word_question(log, card)
        if q is None:
            recall(card, f"What does “{card['front']}” mean?", card["back"] + (f" — {card['example']}" if card.get("example") else ""))
        else:
            show_question(card, q)
    else:
        recall(card, card["front"], card["back"])
    st.caption("Reviews don't hold up today's lessons, and you can stop any time.")


# ============================================================
# COLLECTION: everything she has, searchable; pause or delete
# ============================================================
FILTERS = {"All": None, "Vocabulary": "word", "Missed questions": "question", "Saved points": "point"}


def collection_view():
    everything = review.cards(log)
    if not everything:
        st.markdown("### Your collection is empty")
        st.caption("It fills as you learn: missed quiz questions, the words of each lesson you pass, "
                   "and the key points you save with “Save for review” under a lesson.")
        return
    with st.container(key="rv_tools"):
        query = st.text_input("Search your collection", key="rv_query", placeholder="A word, a question, a subject…")
        counts = {name: sum(1 for _, _, c in everything if k is None or c["kind"] == k) for name, k in FILTERS.items()}
        kind = st.pills("Kind", list(FILTERS), key="rv_kind", default="All", label_visibility="collapsed",
                        format_func=lambda name: f"{name} {counts[name]}") or "All"
    found = review.search(log, query, FILTERS[kind])
    paused = sum(1 for _, _, c in everything if c["paused"])
    st.caption(f"{len(found)} of {len(everything)} cards" + (f" · {paused} paused" if paused else ""))
    if not found:
        st.caption("Nothing matches. Try another word or kind.")
        return
    shown = st.session_state.get("rv_more", 30)
    for e, slot, c in found[:shown]:
        with st.container(key=f"rv_row_{c['id']}"):
            # one block of text, spaced by its own type (separate blocks stacked
            # tight and, on iPad Safari, ran into each other and the buttons)
            meta = f"{source(c)} · " + ("paused" if c["paused"] else f"next review {when(c['due'])}")
            back = c["back"] if c["kind"] != "question" else f"Answer: {c['back']}"
            st.html(f'<div class="rv-card"><p class="rv-front">{escape(c["front"])}</p>'
                    f'<p class="rv-meta">{escape(meta)}</p><p class="rv-back">{escape(back)}</p></div>')
            confirm = st.session_state.get("rv_confirm") == c["id"]
            with st.container(horizontal=True, key=f"rv_acts_{c['id']}"):
                if confirm:
                    if st.button("Delete it", key=f"rv_del_yes_{c['id']}", type="primary"):
                        held = holder(c["id"])
                        if held:
                            review.remove(held[1], c["id"])
                            if not ui.save_entry(log, held[0]):
                                ui.show_pending_error()
                        st.session_state.rv_confirm = None
                        st.rerun()
                    if st.button("Keep it", key=f"rv_del_no_{c['id']}", type="tertiary"):
                        st.session_state.rv_confirm = None
                        st.rerun()
                else:
                    if st.button("Resume" if c["paused"] else "Pause", key=f"rv_pause_{c['id']}", type="tertiary"):
                        held = holder(c["id"])
                        if held:
                            held[2]["paused"] = not held[2]["paused"]
                            if not ui.save_entry(log, held[0]):
                                ui.show_pending_error()
                        st.rerun()
                    if st.button("Delete", key=f"rv_del_{c['id']}", type="tertiary"):
                        st.session_state.rv_confirm = c["id"]
                        st.rerun()
    if len(found) > shown and st.button("Show more", key="rv_show_more", type="tertiary"):
        st.session_state.rv_more = shown + 30
        st.rerun()


with st.container(key=f"rv_{view.lower()}"):
    if view == "Today":
        today_view()
    else:
        collection_view()
