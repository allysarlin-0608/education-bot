"""Review: one card at a time, then the collection she can look through.

The cards (coach/review.py) are her missed quiz questions, the words of the
lessons she has passed and the points she saved. Answers are checked here,
without the model: a question against its stored answer, a word as "which
meaning?", a saved point by her own honest "I knew it" / "Not yet"."""
from datetime import date
from html import escape

import streamlit as st

from coach import catalog, exercise, quiz, review, ui
from coach import i18n
from coach.i18n import N_, tr, trn

log = st.session_state.coach_log
today = ui.today()
st.html('<div id="review-page"></div>')
st.markdown(tr("## Review"))
st.caption(tr("What you've learned comes back just before you'd forget it: a day later, then further apart "
           "each time you know it. A few minutes a day; your lessons never wait for it."))

VIEWS = [N_("Today"), N_("Collection")]
st.session_state.setdefault("rv_view", "Today")
view = st.segmented_control(tr("Show"), VIEWS, key="rv_view", required=True,
                            label_visibility="collapsed", format_func=tr) or "Today"


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


def answered(card_id, right, score=None):
    found = holder(card_id)
    if found is None:
        st.rerun()
    e, slot, card = found
    review.grade(card, right, today)
    # what she knows (the skill map): a review is evidence for its lesson's idea
    ui.learned(slot, e["date"], "review", float(right) if score is None else score,
               source=f"{card_id}-{card['reviews']}")
    if not ui.save_entry(log, e):
        ui.show_pending_error()
    st.session_state.rv_current = {"id": card_id, "right": right}
    st.rerun()


def when(iso):
    d = date.fromisoformat(iso)
    if d <= today:
        return tr("due today")
    if (d - today).days == 1:
        return tr("tomorrow")
    return tr("on {day}", day=i18n.day_short(d))


def source(card):
    subject = catalog.name(card.get("topic"), "")
    lesson = f"Lesson {card['n']}" if card.get("n") else ""
    return " · ".join(x for x in (tr(review.KIND_NAMES[card["kind"]]), subject, lesson) if x)


# ============================================================
# TODAY'S REVIEW: one card at a time
# ============================================================
def show_question(card, q):
    """A stored question (or a word asked as one), checked on the spot."""
    key = f"rv_{card['id']}_{card['reviews']}"
    if q["type"] in quiz.WRITTEN:
        recall(card, q["question"], tr("A good answer: {answer}", answer=q['answer']))
        return
    answer = exercise.field(q, key, tag=q["type"] not in ("choice", "match"))
    if st.button(tr("Check"), type="primary", key=f"{key}_check", disabled=not quiz.answered(q, answer), width="stretch"):
        mark = quiz.mark(q, answer)
        st.session_state.rv_answer = {"id": card["id"], "answer": answer}
        answered(card["id"], mark == 1, mark)


def recall(card, prompt, answer):
    """Recall it, look, and say honestly whether she knew it."""
    st.markdown(f"**{prompt}**")
    shown = st.session_state.get("rv_shown") == card["id"]
    if not shown:
        st.caption(tr("Say it to yourself first, then look."))
        if st.button(tr("Show the answer"), type="primary", key=f"rv_show_{card['id']}", width="stretch"):
            st.session_state.rv_shown = card["id"]
            st.rerun()
        return
    st.markdown(answer)
    with st.container(horizontal=True, key="rv_self"):
        if st.button(tr("I knew it"), type="primary", key=f"rv_yes_{card['id']}", width="stretch"):
            st.session_state.rv_shown = None
            answered(card["id"], True)
        if st.button(tr("Not yet"), key=f"rv_no_{card['id']}", width="stretch"):
            st.session_state.rv_shown = None
            answered(card["id"], False)


def feedback(card, right):
    """Just answered: right or not (said in words, not only colour), the answer, what's next."""
    st.markdown(f"**{'✓ ' + tr('Right.') if right else '✗ ' + tr('Not quite.')}** " +
                (tr("It comes back {when}.", when=when(card['due'])) if right else tr("It comes back tomorrow.")))
    mine = st.session_state.get("rv_answer") or {}
    if card["kind"] == "question" and mine.get("id") == card["id"] and card["question"]["type"] in quiz.LOCAL:
        item = card["question"]
        exercise.result(item, mine["answer"], quiz.mark(item, mine["answer"]), show_question=False)
    elif card["kind"] == "question":
        item = card["question"]
        st.caption(tr("Answer: {answer}.", answer=review._answer_text(item)) + (f" {item['why']}" if item.get("why") else ""))
    elif card["kind"] == "word":
        st.caption(f"{card['front']}: {card['back']}" + (f" — {card['example']}" if card.get("example") else ""))


def pace(left):
    """How far through today's cards: a hairline and a few words."""
    done = review.reviewed_today(log, today)
    share = done / (done + left) if done + left else 1
    st.html(tr('<div class="rv-pace"><div class="rv-line"><span style="width:{p0:.0f}%"></span></div><p>{done} done · {left} to go today</p></div>', p0=share * 100, done=done, left=left))


def today_view():
    current = st.session_state.get("rv_current")
    found = review.find(log, current["id"]) if current else None
    due = ui.review_due(log)
    if found is not None:
        card = found[2]
        pace(len(due))
        st.caption(source(card))
        st.markdown(f"### {review.front(card) if card['kind'] != 'question' else card['question']['question']}")
        feedback(card, current["right"])
        label = tr("Next card") if due else tr("Finish")
        if st.button(label, type="primary", key="rv_next", width="stretch"):
            st.session_state.rv_current = None
            st.rerun()
        return
    if not due:
        done = review.reviewed_today(log, today)
        if not review.cards(log):
            st.markdown(tr("### Nothing to review yet"))
            st.caption(tr("Questions you miss in a quiz, the words of each lesson you pass and the points you "
                       "save come back here a day later, then further apart each time you know them."))
        else:
            st.markdown(tr("### All reviewed for today") if done else tr("### Nothing due today"))
            nxt = review.next_due(log, today)
            parts = ([trn("You reviewed {n} card today.", "You reviewed {n} cards today.", done)] if done else []) + \
                ([tr("The next ones come back {when}.", when=when(nxt.isoformat()))] if nxt else [])
            waiting = [c for _, _, c in review.cards(log)
                       if not c["paused"] and c["due"] <= today.isoformat() and c.get("last") != today.isoformat()]
            if waiting:
                parts = [tr("That's today's {limit}. The other {n} wait for tomorrow.", limit=review.DAILY_LIMIT, n=len(waiting))]
            st.caption(" ".join(parts))
        if st.button(tr("Back to Home"), key="rv_back", type="tertiary"):
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
            recall(card, tr("What does “{word}” mean?", word=card['front']), card["back"] + (f" — {card['example']}" if card.get("example") else ""))
        else:
            show_question(card, q)
    else:
        recall(card, review.front(card), card["back"])
    st.caption(tr("Reviews don't hold up today's lessons, and you can stop any time."))


# ============================================================
# COLLECTION: everything she has, searchable; pause or delete
# ============================================================
FILTERS = {N_("All"): None, N_("Vocabulary"): "word", N_("Missed questions"): "question", N_("Saved points"): "point"}


def collection_view():
    everything = review.cards(log)
    if not everything:
        st.markdown(tr("### Your collection is empty"))
        st.caption(tr("It fills as you learn: missed quiz questions, the words of each lesson you pass, "
                   "and the key points you save with “Save for review” under a lesson."))
        return
    with st.container(key="rv_tools"):
        query = st.text_input(tr("Search your collection"), key="rv_query", placeholder=tr("A word, a question, a subject…"))
        counts = {name: sum(1 for _, _, c in everything if k is None or c["kind"] == k) for name, k in FILTERS.items()}
        kind = st.pills(tr("Kind"), list(FILTERS), key="rv_kind", default="All", label_visibility="collapsed",
                        format_func=lambda name: f"{tr(name)} {counts[name]}") or "All"
    found = review.search(log, query, FILTERS[kind])
    paused = sum(1 for _, _, c in everything if c["paused"])
    st.caption(tr("{found} of {n} cards", found=len(found), n=len(everything)) + (" · " + tr("{n} paused", n=paused) if paused else ""))
    if not found:
        st.caption(tr("Nothing matches. Try another word or kind."))
        return
    shown = st.session_state.get("rv_more", 30)
    for e, slot, c in found[:shown]:
        with st.container(key=f"rv_row_{c['id']}"):
            # one block of text, spaced by its own type (separate blocks stacked
            # tight and, on iPad Safari, ran into each other and the buttons)
            meta = f"{source(c)} · " + (tr("paused") if c["paused"] else tr("next review {when}", when=when(c['due'])))
            back = c["back"] if c["kind"] != "question" else tr("Answer: {answer}", answer=c['back'])
            st.html(f'<div class="rv-card"><p class="rv-front">{escape(review.front(c))}</p>'
                    f'<p class="rv-meta">{escape(meta)}</p><p class="rv-back">{escape(back)}</p></div>')
            confirm = st.session_state.get("rv_confirm") == c["id"]
            with st.container(horizontal=True, key=f"rv_acts_{c['id']}"):
                if confirm:
                    if st.button(tr("Delete it"), key=f"rv_del_yes_{c['id']}", type="primary"):
                        held = holder(c["id"])
                        if held:
                            review.remove(held[1], c["id"])
                            if not ui.save_entry(log, held[0]):
                                ui.show_pending_error()
                        st.session_state.rv_confirm = None
                        st.rerun()
                    if st.button(tr("Keep it"), key=f"rv_del_no_{c['id']}", type="tertiary"):
                        st.session_state.rv_confirm = None
                        st.rerun()
                else:
                    if st.button(tr("Resume") if c["paused"] else tr("Pause"), key=f"rv_pause_{c['id']}", type="tertiary"):
                        held = holder(c["id"])
                        if held:
                            held[2]["paused"] = not held[2]["paused"]
                            if not ui.save_entry(log, held[0]):
                                ui.show_pending_error()
                        st.rerun()
                    if st.button(tr("Delete"), key=f"rv_del_{c['id']}", type="tertiary"):
                        st.session_state.rv_confirm = c["id"]
                        st.rerun()
    if len(found) > shown and st.button(tr("Show more"), key="rv_show_more", type="tertiary"):
        st.session_state.rv_more = shown + 30
        st.rerun()


with st.container(key=f"rv_{view.lower()}"):
    if view == "Today":
        today_view()
    else:
        collection_view()
