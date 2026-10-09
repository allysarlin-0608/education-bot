"""Making a goal of her own: she says what she wants to learn (and why, where
she is, how much time she has), the AI designs a path for it (one call,
coach/paths.py), and she adjusts the path before she starts.

Used by the setup (views/setup.py) and the New goal page (views/goal.py).
Both keep the goal being made in her settings' draft (settings.onboarding,
settings.goal_draft_of), saved as she goes, so a refresh, another tab or a
slow network never loses what she wrote or the path she got.

The AI is asked only when she presses Design my path, and never twice for
the same answers (a second click, a refresh, a click while it runs): the
answers it designed for are kept with its reply ("for"). A goal it couldn't
plan yet may be asked again once with her answer (paths.DESIGN_ATTEMPTS);
past that she picks a suggested goal or writes another. Every call counts
toward her daily allowance (coach/quota.py)."""
import hashlib
import json
import math
from html import escape

import streamlit as st

from coach import llm, paths, settings, tokens

RETRY = "We couldn't design a path just now. Your goal is kept: try again in a moment."
ENOUGH = ("We couldn't turn this into a path yet. Pick one of the goals below, "
          "or write your goal differently: what would you like to be able to do?")


def _k(key: str, name: str) -> str:
    return f"{key}_{name}"


def signature(goal: dict, pace: int) -> str:
    """The answers a path is designed for (the same answers: the same path)."""
    raw = json.dumps([goal["text"].strip(), goal["why"].strip(), goal["start"], goal["answers"].strip(), pace])
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _answers(key: str, d: dict) -> dict:
    """What the boxes say now (else what was saved)."""
    g = d["goal"]
    return {"text": str(st.session_state.get(_k(key, "text"), g["text"])),
            "why": str(st.session_state.get(_k(key, "why"), g["why"])),
            "start": st.session_state.get(_k(key, "start")) or g["start"],
            "answers": str(st.session_state.get(_k(key, "answers"), g["answers"]))}


def _keep(key: str, get, put) -> None:
    """A box changed: keep it in the draft (a refresh brings it back)."""
    d = get()
    d["goal"] = _answers(key, d)
    put(d)


def _use_idea(key: str, group: str, get, put) -> None:
    """A suggested goal picked: it becomes her goal's words."""
    idea = st.session_state.get(_k(key, f"idea_{group}"))
    st.session_state[_k(key, f"idea_{group}")] = None
    if idea:
        _use(key, idea, get, put)


def _use(key: str, text: str, get, put) -> None:
    st.session_state[_k(key, "text")] = text
    st.session_state[_k(key, "answers")] = ""
    d = get()
    d["goal"] = dict(_answers(key, d), text=text, answers="")
    put(d)


def _ask(key: str) -> None:
    st.session_state[_k(key, "go")] = True


def design(key: str, d: dict, put, pace: int) -> bool:
    """Design a path for her answers (the one AI call), unless it was already
    designed for exactly these answers. The reply is saved the moment it
    comes back, before anything is drawn: a click that interrupts this run
    can't lose it, and the next run finds it instead of asking again.
    True when there is a path for these answers."""
    goal = _answers(key, d)
    d["goal"] = goal
    note = paths.precheck(goal["text"])
    if note:
        st.session_state[_k(key, "note")] = note
        put(d)
        return False
    sig = signature(goal, pace)
    prev = d["design"] or {}
    if prev.get("for") == sig and prev.get("status") != "error" and (prev.get("status") != "ok" or d["path"]):
        return bool(d["path"])          # (a path she has since let go of is designed again)
    calls = prev.get("calls", 0) if prev.get("text") == goal["text"].strip() else 0
    if calls >= paths.DESIGN_ATTEMPTS:
        st.session_state[_k(key, "note")] = ENOUGH
        return False
    with st.spinner("Designing your path…"):
        system, messages = paths.design_messages(goal, pace)
        data, error = llm.ask_json(system, messages, max_tokens=tokens.PATH_MAX_TOKENS)
        result = {"status": "error", "message": error} if error else paths.read_design(data, goal)
        if result["status"] == "error":
            result["message"] = result.get("message") or RETRY
        d["design"] = {"status": result["status"], "message": result.get("message", ""),
                       "questions": result.get("questions", []), "suggestions": result.get("suggestions", []),
                       "for": sig, "text": goal["text"].strip(),
                       "calls": calls if result["status"] == "error" else calls + 1}   # (a failed call isn't her try)
        if result["status"] == "ok":
            d["path"] = d["path_original"] = result["path"]
        elif result["status"] != "error":           # another goal, not planned yet: the old path is not its
            d["path"] = d["path_original"] = None
        put(d)
    return result["status"] == "ok"


# ------------------------------------------------------------------- the form
def form(key: str, get, put, *, pace: int = settings.DEFAULT_PACE, skip=None, on_path=None) -> None:
    """What she wants to learn. get() -> the draft; put(d) keeps it. `pace`:
    the lessons a day the path is sized for (the setup's draft, or her
    settings; the setup asks it at Customize). skip: (label, callback) for the other way in.
    on_path(): called once a path is designed (the page moves on to it)."""
    unreadable = getattr(st.session_state.get("coach_store"), "paths_error", None)
    if unreadable:                 # goals can't be kept now: no path is designed for nothing
        st.html(f'<p class="ob-note" role="status">{escape(unreadable)}</p>')
        if skip:
            with st.container(key="ob_nav", horizontal=True):
                st.button(skip[0], key=_k(key, "skip"), type="tertiary", on_click=skip[1])
        return
    d = get()
    if st.session_state.pop(_k(key, "go"), False):
        if design(key, d, put, pace):
            if on_path:
                on_path()
            st.rerun()
    for name in ("text", "why", "answers"):               # her words so far, once per visit
        st.session_state.setdefault(_k(key, name), d["goal"][name])
    st.session_state.setdefault(_k(key, "start"), d["goal"]["start"])

    st.text_area("In your own words", key=_k(key, "text"), max_chars=paths.GOAL_MAX_CHARS, height=96,
                 placeholder="e.g. Understand how investing works before I put money in",
                 on_change=_keep, args=(key, get, put))
    # the answer to the goal she wrote, just under it
    reply = d.get("design") or {}
    if reply.get("status") in ("clarify", "narrow", "decline", "error") and reply.get("text") == d["goal"]["text"].strip():
        with st.container(key=_k(key, f"reply_{reply['status']}")):
            st.html(f'<p class="gm-reply" role="status">{escape(reply["message"])}</p>'
                    + ("".join(f'<p class="gm-q">{escape(q)}</p>' for q in reply["questions"])))
            if reply["status"] == "clarify" and reply.get("calls", 0) < paths.DESIGN_ATTEMPTS:
                st.text_input("Your answer", key=_k(key, "answers"), max_chars=paths.TEXT_LIMIT,
                              placeholder="A few words are enough", on_change=_keep, args=(key, get, put))
            if reply["suggestions"]:
                with st.container(key=_k(key, "suggested"), horizontal=True):
                    for k, idea in enumerate(reply["suggestions"]):
                        st.button(idea, key=_k(key, f"sugg_{k}"), on_click=_use, args=(key, idea, get, put))

    with st.container(key=_k(key, "ideas")):
        # one kind of learner's ideas at a time (work, curiosity, study), so the list stays short
        group = st.segmented_control("Or start from an idea", list(paths.SUGGESTIONS), key=_k(key, "idea_group"),
                                     default=next(iter(paths.SUGGESTIONS)), required=True)
        with st.container(key=_k(key, "idea_list")):
            st.pills(group, paths.SUGGESTIONS[group], key=_k(key, f"idea_{group}"), label_visibility="collapsed",
                     on_change=_use_idea, args=(key, group, get, put))
    st.text_input("Why does it matter to you? (optional)", key=_k(key, "why"), max_chars=paths.TEXT_LIMIT,
                  placeholder="e.g. I want to start investing this year", on_change=_keep, args=(key, get, put))
    with st.container(key=_k(key, "start_sw")):
        st.segmented_control("Where are you now?", list(paths.STARTS), format_func=lambda s: paths.STARTS[s][0],
                             key=_k(key, "start"), required=True, width="stretch",
                             on_change=_keep, args=(key, get, put))
    note = st.session_state.pop(_k(key, "note"), "")
    if note:
        st.html(f'<p class="ob-note gm-note" role="status">{escape(note)}</p>')
    with st.container(key="ob_nav", horizontal=True, vertical_alignment="center"):
        st.button("Design my path", key=_k(key, "design"), type="primary", on_click=_ask, args=(key,))
        if skip:
            st.button(skip[0], key=_k(key, "skip"), type="tertiary", on_click=skip[1])
    st.html('<p class="ob-note">One short lesson at a time, written when you reach it. '
            "Lessons teach well-established knowledge, with sources for the important facts.</p>")


# ---------------------------------------------------------- the path, adjusted
def _change(get, put, how) -> None:
    d = get()
    if d.get("path"):
        d["path"] = how(d["path"])
        put(d)


def _level(key: str, get, put) -> None:
    level = st.session_state.get(_k(key, "level"))
    _change(get, put, lambda p: paths.with_level(p, level))


def _undo(get, put) -> None:
    d = get()
    d["path"] = d["path_original"]
    put(d)


def again(get, put) -> None:
    """A different goal: the path goes, her words stay."""
    d = get()
    d["path"] = d["path_original"] = None
    d["design"] = None
    put(d)


def summary_html(p: dict, pace: int, eyebrow: str = "Made for you", title: bool = True) -> str:
    n = paths.lesson_count(p)
    days = math.ceil(n / pace)
    why = f'<p class="gm-why">Because: “{escape(p["why"])}”</p>' if p.get("why") else ""
    return (f'<div class="gm-path"><p class="gm-eyebrow">{escape(eyebrow)}</p>'
            + (f'<h3>{escape(p["title"])}</h3>' if title else "") +
            f'<p class="gm-outcome">{escape(p["outcome"])}</p>{why}'
            f'<p class="gm-meta">{n} lessons in {len(p["units"])} parts · {p["level"]} · '
            f'about {days} study {"day" if days == 1 else "days"} at {pace} a day</p></div>')


def review(key: str, get, put, pace: int) -> None:
    """The path she got, to adjust before she starts: deeper or gentler,
    shorter, parts moved or skipped, lessons taken out (no AI call)."""
    d = get()
    p = d["path"]
    st.html(summary_html(p, pace))
    st.session_state[_k(key, "level")] = p["level"]
    with st.container(key=_k(key, "adjust"), horizontal=True, vertical_alignment="bottom"):
        st.segmented_control("Depth", list(paths.LEVELS), key=_k(key, "level"), required=True,
                             on_change=_level, args=(key, get, put))
        shorter = paths.lighter(p)
        st.button("Make it shorter", key=_k(key, "lighter"), type="tertiary",
                  disabled=paths.lesson_count(shorter) == paths.lesson_count(p),
                  on_click=_change, args=(get, put, paths.lighter))
        if p["units"] != (d.get("path_original") or {}).get("units") or p["level"] != (d.get("path_original") or {}).get("level"):
            st.button("Undo my changes", key=_k(key, "undo"), type="tertiary", on_click=_undo, args=(get, put))
    first = 1
    with st.container(key=_k(key, "units")):
        for i, u in enumerate(p["units"]):
            with st.container(key=_k(key, f"unit_{i}")):
                st.html(f'<div class="gm-unit"><p class="gm-u"><span>Part {i + 1}</span>{escape(u["name"])}</p>'
                        f'<ol start="{first}">' + "".join(f"<li>{escape(t)}</li>" for t in u["lessons"]) + "</ol></div>")
                first += len(u["lessons"])
                with st.container(key=_k(key, f"unit_act_{i}"), horizontal=True):
                    if i > 0:
                        st.button("Move up", key=_k(key, f"up_{i}"), type="tertiary",
                                  on_click=_change, args=(get, put, lambda p, i=i: paths.move_unit(p, i, -1)))
                    if i < len(p["units"]) - 1:
                        st.button("Move down", key=_k(key, f"down_{i}"), type="tertiary",
                                  on_click=_change, args=(get, put, lambda p, i=i: paths.move_unit(p, i, 1)))
                    if len(p["units"]) > 1:
                        st.button("I know this: skip it", key=_k(key, f"skip_{i}"), type="tertiary",
                                  on_click=_change, args=(get, put, lambda p, i=i: paths.remove_unit(p, i)))
                    if paths.lesson_count(p) > 1:
                        with st.popover("Remove a lesson", type="tertiary", key=_k(key, f"rmpop_{i}")):
                            for k, t in enumerate(u["lessons"]):
                                st.button(t, key=_k(key, f"rm_{i}_{k}"), type="tertiary",
                                          on_click=_change, args=(get, put, lambda p, i=i, k=k: paths.remove_lesson(p, i, k)))
