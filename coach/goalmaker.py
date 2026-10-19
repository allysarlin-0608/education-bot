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
from coach.i18n import tr

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
        _use(key, tr(idea), get, put)           # her goal in her words: the idea as she read it


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
    with st.spinner(tr("Designing your path…")):
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
def form(key: str, get, put, *, pace: int = settings.DEFAULT_PACE, skip=None, on_path=None,
         ideas: str = None) -> None:
    """What she wants to learn. get() -> the draft; put(d) keeps it. `pace`:
    the lessons a day the path is sized for. skip: (label, callback) for the
    other way in. on_path(): called once a path is designed (the page moves
    on to it). `ideas`: the group of ideas shown first (from who she is).
    What it's for is asked after the path (purpose())."""
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

    st.text_area(tr("In your own words"), key=_k(key, "text"), max_chars=paths.GOAL_MAX_CHARS, height=96,
                 placeholder=tr("e.g. Understand how investing works before I put money in"),
                 on_change=_keep, args=(key, get, put))
    # the answer to the goal she wrote, just under it
    reply = d.get("design") or {}
    if reply.get("status") in ("clarify", "narrow", "decline", "error") and reply.get("text") == d["goal"]["text"].strip():
        with st.container(key=_k(key, f"reply_{reply['status']}")):
            st.html(f'<p class="gm-reply" role="status">{escape(reply["message"])}</p>'
                    + ("".join(f'<p class="gm-q">{escape(q)}</p>' for q in reply["questions"])))
            if reply["status"] == "clarify" and reply.get("calls", 0) < paths.DESIGN_ATTEMPTS:
                st.text_input(tr("Your answer"), key=_k(key, "answers"), max_chars=paths.TEXT_LIMIT,
                              placeholder=tr("A few words are enough"), on_change=_keep, args=(key, get, put))
            if reply["suggestions"]:
                with st.container(key=_k(key, "suggested"), horizontal=True):
                    for k, idea in enumerate(reply["suggestions"]):
                        st.button(idea, key=_k(key, f"sugg_{k}"), on_click=_use, args=(key, idea, get, put))

    with st.container(key=_k(key, "ideas")):
        # one kind of learner's ideas at a time (work, curiosity, study), so the list stays short
        group = st.segmented_control(tr("Or start from an idea"), list(paths.SUGGESTIONS), key=_k(key, "idea_group"),
                                     default=ideas if ideas in paths.SUGGESTIONS else next(iter(paths.SUGGESTIONS)),
                                     required=True, format_func=tr)
        with st.container(key=_k(key, "idea_list")):
            st.pills(tr(group), paths.SUGGESTIONS[group], key=_k(key, f"idea_{group}"), label_visibility="collapsed",
                     format_func=tr,
                     on_change=_use_idea, args=(key, group, get, put))
    with st.container(key=_k(key, "start_sw")):
        st.segmented_control(tr("Where are you now?"), list(paths.STARTS), format_func=lambda s: tr(paths.STARTS[s][0]),
                             key=_k(key, "start"), required=True, width="stretch",
                             on_change=_keep, args=(key, get, put))
    note = st.session_state.pop(_k(key, "note"), "")
    if note:
        st.html(f'<p class="ob-note gm-note" role="status">{escape(note)}</p>')
    with st.container(key="ob_nav", horizontal=True, vertical_alignment="center"):
        st.button(tr("Design my path"), key=_k(key, "design"), type="primary", on_click=_ask, args=(key,))
        if skip:
            st.button(skip[0], key=_k(key, "skip"), type="tertiary", on_click=skip[1])
    st.html(tr('<p class="ob-note">One short lesson at a time, written when you reach it. '
            "Lessons teach well-established knowledge, each with links to check it yourself.</p>"))


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


# ------------------------------------------------- all of it, or some parts
def _set_scope(key: str, get, put) -> None:
    d = get()
    picked = st.session_state.get(_k(key, "scope"))
    if picked not in settings.SCOPES:       # (a tap on the one already chosen, or a control coming back
        return                              # without its value: her answer stays as it is)
    d["scope"] = picked
    if d["scope"] == "all" and d.get("path_original"):
        d["path"] = d["path_original"]               # (all of it: every part, as designed)
    put(d)


def _tick(key: str, get, put) -> None:
    d = get()
    orig = d.get("path_original")
    if orig:
        names = [u["name"] for i, u in enumerate(orig["units"]) if st.session_state.get(_k(key, f"part_{i}"))]
        d["path"] = paths.keep_units(orig, names)
        put(d)


def scope_line(orig: dict, p: dict, some: bool, pace: int) -> str:
    """How much she has chosen, and how long it takes at her pace."""
    n, n_all = paths.lesson_count(p), paths.lesson_count(orig)
    days = math.ceil(n / max(pace, 1))
    when = f"about {days} study {'day' if days == 1 else 'days'} at {pace} a day"
    if not some or n == n_all:
        return f"{n_all} lessons in {len(orig['units'])} parts · {orig['level']} · {when}"
    return (f"You chose {n} of {n_all} lessons ({len(p['units'])} of {len(orig['units'])} parts) · "
            f"{orig['level']} · {when}")


def scope(key: str, get, put, pace: int = settings.DEFAULT_PACE) -> None:
    """The outline of what she asked for, how many lessons it is, and her
    choice: all of it, or only the parts she ticks (any part can be ticked
    again: nothing is lost). The count and the time it takes follow every
    tick at once, at the top where she reads it."""
    d = get()
    orig, p = d.get("path_original") or d["path"], d["path"]
    some = d.get("scope") == "some"
    st.html(tr('<div class="gm-path"><p class="gm-eyebrow">The outline</p><h3>{p0}</h3><p class="gm-outcome">{p1}</p><p class="gm-meta" role="status" aria-live="polite">{p2}</p></div>', p0=escape(orig["title"]), p1=escape(orig["outcome"]), p2=escape(scope_line(orig, p, some, pace))))
    st.session_state[_k(key, "scope")] = d.get("scope") or None      # (always her answer as kept)
    with st.container(key=_k(key, "scope_sw")):
        st.segmented_control(tr('Do you want to learn all of {p0}?', p0=orig['title']), ["all", "some"],
                             format_func=lambda v: tr("Yes, all of it") if v == "all" else tr("No, only some parts"),
                             key=_k(key, "scope"), width="stretch", on_change=_set_scope, args=(key, get, put))
    kept = {u["name"] for u in p["units"]}
    with st.container(key=_k(key, "outline")):
        for i, u in enumerate(orig["units"]):
            with st.container(key=_k(key, f"unit_{i}")):
                if some:
                    st.session_state[_k(key, f"part_{i}")] = u["name"] in kept      # (always as kept)
                    last = u["name"] in kept and len(kept) == 1          # (one part at least: the last can't go)
                    st.checkbox(tr('Part {p0}: {p1} · {p2} lessons', p0=i + 1, p1=u['name'], p2=len(u['lessons'])), key=_k(key, f"part_{i}"),
                                on_change=_tick, args=(key, get, put), disabled=last,
                                help=tr("Keep at least one part.") if last else None)
                else:
                    st.html(tr('<p class="gm-u"><span>Part {p0}</span>{p1}</p>', p0=i + 1, p1=escape(u["name"])))
                st.html('<ol class="gm-lessons">' + "".join(f"<li>{escape(t)}</li>" for t in u["lessons"]) + "</ol>")


# ------------------------------------------------------ what it's for
def _purpose(key: str, get, put, value=None) -> None:
    d = get()
    if value is not None:
        d["purpose"] = value
        st.session_state[_k(key, "own")] = ""        # (her own words give way to the one she picked)
    else:
        own = str(st.session_state.get(_k(key, "own")) or "").strip()
        d["purpose"] = own[:paths.TEXT_LIMIT]
    put(d)


def _all_of_it(key: str, get, put) -> None:
    from coach import directions
    d = get()
    d["purpose"] = directions.ALL_OF_IT if st.session_state.get(_k(key, "all")) else ""
    put(d)


def purpose(key: str, get, put, identity: str = "") -> None:
    """What it's for: the goals that fit who she is, or her own words. To
    skip it she says so (no particular goal: all of it)."""
    from coach import directions
    d = get()
    chosen = d.get("purpose") or ""
    options = list(directions.purposes(identity))
    with st.container(key=_k(key, "purposes"), gap=None):
        for i, o in enumerate(options):
            on = chosen == o
            st.button(tr("{name}, selected", name=tr(o)) if on else tr(o), key=_k(key, f"pp_{i}"), type="primary" if on else "secondary",
                      on_click=_purpose, args=(key, get, put, o))
    own = chosen if chosen and chosen not in options and chosen != directions.ALL_OF_IT else ""
    st.session_state[_k(key, "own")] = own          # (always her answer as kept)
    st.text_input(tr("Or in your own words"), key=_k(key, "own"), max_chars=paths.TEXT_LIMIT,
                  placeholder=tr("e.g. Understand the news about the economy"), on_change=_purpose, args=(key, get, put))
    st.session_state[_k(key, "all")] = chosen == directions.ALL_OF_IT
    st.checkbox(tr("No particular goal: I want to learn all of it"), key=_k(key, "all"), on_change=_all_of_it,
                args=(key, get, put))
