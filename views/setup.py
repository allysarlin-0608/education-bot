"""First-time setup: a few short steps, one decision each.

1. Who you are (asked once: later questions can be fewer). Skipped only by
   saying she knows exactly what she wants.
2. What you want to learn: in her own words (coach/goalmaker.py); or, if she
   doesn't know yet, broad directions to narrow down (Explore), whose last
   choice becomes her words. Either way GNOSIS designs an outline for it.
3. All of it, or some parts: the outline and its number of lessons; she
   keeps all of it, or ticks the parts she wants.
4. What it's for: goals that fit who she is, or her own words. Skipped only
   by saying she wants all of it.
5. Confirm: one sentence of everything, each part changeable; Start learning
   saves it and opens her first day.

The built-in subjects aren't offered here (they stay for anyone already
learning them). Her answers are kept in her settings row as she goes
(settings "onboarding"), so a refresh, Back or a change never loses them.
She counts as set up only once she presses Start learning."""
from html import escape

import streamlit as st

from coach import choices, directions, goalmaker, paths, settings, ui

STEP_NAMES = {"identity": "About you", "want": "What to learn", "explore": "Find a topic",
              "scope": "All of it, or some parts", "purpose": "What it's for", "confirm": "Confirm"}
CHANGE = {"identity": "Change who you are", "want": "Change what you learn", "scope": "Change the parts",
          "purpose": "Change what it's for"}
# who she is, as the start of a sentence
YOU_ARE = {"Student": "You're a student", "Working adult": "You're a working adult",
           "Changing careers": "You're changing careers", "Retired": "You're retired",
           "Learning for the love of it": "You're learning for the love of it"}


def draft() -> dict:
    return settings.draft_of(ui.config())


def put(d: dict) -> None:
    """Keep her answers so far (not yet a finished setup: onboarded_at stays empty).
    Once the setup is finished (Start learning, here or in another tab), a
    click left on a setup page saves nothing: a draft written onto a
    finished setup mixed old answers into her account (ISS-063)."""
    ui.refresh_settings()       # onto the row as stored now (another tab may have changed it; ISS-044)
    if settings.onboarded(ui.config()):
        return                  # (the next run opens the app as it now is)
    ui.save_settings(dict(ui.config(), onboarding=d))


def route(d: dict) -> list:
    """The steps her answers call for: Explore only while she is finding a
    topic; the outline's steps once there is an outline."""
    out = ["identity", "want"] + (["explore"] if d["exploring"] else [])
    out += ["scope", "purpose"] if d["path"] else []
    return out + ["confirm"]


def reachable(d: dict) -> str:
    """The step to show: hers, or the furthest her answers allow (a stale
    draft can't skip ahead, and a step her answers no longer call for
    gives way to the one before it)."""
    steps = route(d)
    name = settings.STEPS[d["step"]]
    while name not in steps:
        name = settings.STEPS[settings.STEPS.index(name) - 1]
    at = steps.index(name)
    if not (d["identity"] or d["knows"]):
        at = min(at, steps.index("identity"))
    if not d["path"]:
        at = min(at, steps.index("explore") if "explore" in steps else steps.index("want"))
    elif not d["scope"]:
        at = min(at, steps.index("scope"))
    elif not d["purpose"]:
        at = min(at, steps.index("purpose"))
    return steps[at]


def go(name: str, back_to=None) -> None:
    """To a step of her route (as far as her answers allow). back_to: the
    step a change was asked from (Confirm), offered again on the way."""
    d = draft()
    now = reachable(d)
    steps = route(d)
    if name not in steps:
        return
    st.session_state.ob_way = "fwd" if steps.index(name) > steps.index(now) else "back"
    st.session_state.ob_from = steps.index(now)
    d["step"] = settings.STEPS.index(name)
    d["step"] = settings.STEPS.index(reachable(d))
    d["back_to"] = None if settings.STEPS[d["step"]] == "confirm" else back_to or d.get("back_to")
    put(d)


def can_return(d: dict) -> bool:
    """Back to Confirm is offered once her answers allow it again."""
    if d.get("back_to") != "confirm":
        return False
    return reachable(dict(d, step=settings.STEPS.index("confirm"))) == "confirm"


def step_by(k: int):
    """The step k away from this one on her route."""
    steps = route(d)
    return steps[max(0, min(steps.index(step) + k, len(steps) - 1))]


# ---------------------------------------------------------------- her answers
def pick_identity(name: str) -> None:
    put(dict(draft(), identity=name, knows=False))


def set_own_identity() -> None:
    own = str(st.session_state.get("ob_identity_own") or "").strip()[:60]
    if own:
        put(dict(draft(), identity=own, knows=False))


def set_knows() -> None:
    d = draft()
    put(dict(d, knows=bool(st.session_state.ob_knows)))


def start_explore() -> None:
    """She doesn't know yet: the broad directions, from the top."""
    put(dict(draft(), exploring=True, explore=[]))
    go("explore")


def pick_direction(choice: str) -> None:
    """One level narrower; when there is nothing narrower, her topic becomes
    her words and its outline is designed at once (as if she had typed it)."""
    d = draft()
    path = list(d["explore"]) + [choice]
    if directions.narrower(path):
        put(dict(d, explore=path))
        return
    topic = directions.topic_of(path)
    goalmaker._use("obg", topic, draft, put)        # her words: the topic (and the box shows it)
    put(dict(draft(), explore=path, exploring=False))
    st.session_state["obg_go"] = True               # designed on the next run, with its spinner
    go("want")


def explore_back() -> None:
    d = draft()
    if d["explore"]:
        put(dict(d, explore=d["explore"][:-1]))
    else:
        put(dict(d, exploring=False))
        go("want")


def other_goal() -> None:
    """A different goal: the outline goes (her words stay), and so do her
    answers about it."""
    goalmaker.again(draft, put)
    put(dict(draft(), scope=None))
    for k in [k for k in st.session_state if k.startswith(("obs_", "obp_"))]:
        del st.session_state[k]


def start() -> None:
    """Start learning: check everything, save it (her goal's outline, with
    what it's for), and her first day opens."""
    ui.refresh_settings()          # finished onto the row as stored now (as every settings save is)
    d = draft()
    if not d["path"]:
        st.session_state.ob_problem = "Choose what you want to learn first."
        return
    try:
        done = settings.finish(ui.config(), d, settings.now_iso())
    except ValueError as e:
        st.session_state.ob_problem = str(e)
        return
    path = dict(d["path"], why="" if d["purpose"] == directions.ALL_OF_IT else d["purpose"])
    if not ui.save_path(st.session_state.coach_log, path):
        st.session_state.ob_problem = "Your goal wasn't saved. Try again in a moment."
        return
    if not ui.save_settings(done):
        # said beside the button she pressed (the page's own error line is at the top, out of sight: ISS-061)
        st.session_state.ob_problem = st.session_state.pop("coach_save_error", "") or \
            "Your plan wasn't saved. Try again in a moment."
        return
    # who she is: kept for later (fewer questions next time). A preference that
    # can't be kept (its table missing) doesn't hold up her start.
    ui.update_prefs(identity=d["identity"])
    st.session_state.pop("coach_save_error", None)
    ui.record("setup_done")
    ui.record("goal_created")
    st.session_state.pop("ob_way", None)


# ---------------------------------------------------------------- drawing
def nav(back: bool = True, label: str = "Continue", ready: bool = True, note: str = "", on=None) -> None:
    """Back and Continue, at the foot of the step (a note on what's missing just above)."""
    if note:
        st.html(f'<p class="ob-note" role="status">{escape(note)}</p>')
    with st.container(key="ob_nav", horizontal=True, horizontal_alignment="distribute", vertical_alignment="center"):
        if back:
            st.button("Back", key="ob_back", type="tertiary", on_click=go, args=(step_by(-1),))
        else:
            st.html('<span class="pq-gap"></span>')
        if can_return(d) and step != "confirm" and not on:
            st.button("Back to confirm", key="ob_to_review", type="tertiary", disabled=not ready,
                      on_click=go, args=("confirm",))
        st.button(label, key="ob_next", type="primary", disabled=not ready,
                  on_click=on or go, args=() if on else (step_by(1),))


def lead(title: str, lede: str) -> None:
    st.markdown(f"## {title}")
    st.html(f'<p class="ob-lede">{escape(lede)}</p>')


def row(term: str, value_html: str, small: str = "") -> str:
    return (f"<div><dt>{escape(term)}</dt><dd>{value_html}"
            + (f"<small>{escape(small)}</small>" if small else "") + "</dd></div>")


def sentence(d: dict) -> str:
    """Everything she chose, in one sentence."""
    p, orig = d["path"], d.get("path_original") or d["path"]
    who = YOU_ARE.get(d["identity"], f"You're: {d['identity']}" if d["identity"] else "")
    n = paths.lesson_count(p)
    what = (f"learning all of {p['title']}" if d["scope"] == "all" or paths.lesson_count(orig) == n
            else f"learning {', '.join(u['name'] for u in p['units'])} from {p['title']}")
    why = ("" if d["purpose"] == directions.ALL_OF_IT or not d["purpose"]
           else f", {d['purpose'][0].lower()}{d['purpose'][1:]}")
    head = f"{who}, {what[0].lower()}{what[1:]}" if who else f"{what[0].upper()}{what[1:]}"
    return f"{head}: {n} lessons{why}."


d = draft()
step = reachable(d)
steps = route(d)
at, total = steps.index(step), len(steps)
came = st.session_state.pop("ob_way", "none")
was = min(st.session_state.pop("ob_from", at), total - 1)

st.html('<div id="setup-page" hidden></div>')     # a narrower, quieter page (style.py)
# where she is: a hairline that fills step by step, and the step's name
st.html(f'<div class="ob-progress" role="progressbar" aria-label="Setup" aria-valuemin="1" aria-valuemax="{total}" '
        f'aria-valuenow="{at + 1}" aria-valuetext="Step {at + 1} of {total}, {STEP_NAMES[step]}">'
        f'<div class="ob-track"><i style="--from:{(was + 1) / total:.4f};--to:{(at + 1) / total:.4f}"></i></div>'
        f'<div class="ob-where"><span>{STEP_NAMES[step]}</span><span>{at + 1} of {total}</span></div></div>')

# each step is its own block, so it comes in from the side she is heading to;
# inside it one editorial grid: the question on the left, the decision on the
# right (on a narrow page, one above the other)
with st.container(key=f"ob_step_{settings.STEPS.index(step)}_{came}"):
    if step == "identity":
        with st.container(key="ob_grid"):
            with st.container(key="ob_lead"):
                lead("Welcome to GNOSIS. Who are you?",
                     "Learn anything you want, a little every day. Tell us who you are once, "
                     "and we'll ask fewer questions from here on.")
            with st.container(key="ob_body"):
                own = d["identity"] if d["identity"] and d["identity"] not in directions.IDENTITIES else ""
                choices.rows("ident", [(x, x, "") for x in directions.IDENTITIES],
                             [d["identity"]] if d["identity"] in directions.IDENTITIES else [], pick_identity)
                st.session_state.setdefault("ob_identity_own", own)
                st.text_input("Something else", key="ob_identity_own", max_chars=60,
                              placeholder="In a few words", on_change=set_own_identity)
                with st.container(key="ob_toggle"):
                    st.checkbox("I know exactly what I want to learn: skip this", value=d["knows"], key="ob_knows",
                                on_change=set_knows)
                ready = bool(d["identity"] or d["knows"])
                nav(back=False, label="Get started", ready=ready,
                    note="" if ready else "Choose who you are, or tick that you know what you want.")

    elif step == "want":
        with st.container(key="ob_grid"):
            with st.container(key="ob_lead"):
                lead("What do you want to learn?",
                     "Anything at all: a subject, a skill, a question you're curious about. "
                     "A word is enough; we'll show you what it covers.")
            with st.container(key="ob_body"):
                if d["path"]:
                    st.html(goalmaker.summary_html(d["path_original"] or d["path"], d["units_per_day"],
                                                   eyebrow="What you want to learn"))
                    with st.container(key="ob_goal_acts", horizontal=True):
                        st.button("Something else", key="ob_again", type="tertiary", on_click=other_goal)
                    nav()
                else:
                    goalmaker.form("obg", draft, put, pace=d["units_per_day"], ideas=directions.IDEAS.get(d["identity"]),
                                   skip=("I don't know yet", start_explore), on_path=lambda: go("scope"))
                    with st.container(key="ob_goal_back", horizontal=True):
                        st.button("Back", key="ob_back", type="tertiary", on_click=go, args=("identity",))

    elif step == "explore":
        picked = d["explore"]
        options = directions.narrower(picked)
        with st.container(key="ob_grid"):
            with st.container(key="ob_lead"):
                lead("Where would you like to start?" if not picked else " › ".join(picked),
                     "Pick a direction, then narrow it down. You'll see what it covers before anything starts."
                     if not picked else "Narrow it down a little more.")
            with st.container(key="ob_body"):
                choices.rows(f"dir{len(picked)}", [(o, o, "") for o in options], [], pick_direction)
                with st.container(key="ob_nav", horizontal=True):
                    st.button("Back", key="ob_back", type="tertiary", on_click=explore_back)
                    st.button("I'll write it myself", key="ob_write", type="tertiary",
                              on_click=lambda: (put(dict(draft(), exploring=False)), go("want")))

    elif step == "scope":
        with st.container(key="ob_grid"):
            with st.container(key="ob_lead"):
                lead("All of it, or some parts?", "Here's what it covers. Keep all of it, or tick only the parts "
                                                  "you want; you can change this before you start.")
            with st.container(key="ob_body"):
                goalmaker.scope("obs", draft, put, pace=d["units_per_day"])
                nav(ready=bool(d["scope"]), note="" if d["scope"] else "Choose all of it, or some parts.")

    elif step == "purpose":
        with st.container(key="ob_grid"):
            with st.container(key="ob_lead"):
                lead("What's it for?", "So the examples and tasks fit you.")
            with st.container(key="ob_body"):
                goalmaker.purpose("obp", draft, put, d["identity"])
                nav(ready=bool(d["purpose"]),
                    note="" if d["purpose"] else "Choose one, write your own, or tick that you want all of it.")

    else:
        name, minutes = settings.PACES[d["units_per_day"]]
        with st.container(key="ob_grid"):
            with st.container(key="ob_lead"):
                lead("Is this right?", "Change any part: your other answers are kept.")
            with st.container(key="ob_body"):
                st.html(f'<p class="ob-sentence">{escape(sentence(d))}</p>'
                        '<dl class="ob-summary">'
                        + (row("You", escape(d["identity"])) if d["identity"] else "")
                        + row("Learning", escape(d["path"]["title"]),
                              f"{paths.lesson_count(d['path'])} lessons in {len(d['path']['units'])} parts")
                        + row("For", escape(d["purpose"]))
                        + row("Each day", escape(name), f"{d['units_per_day']} lessons · {minutes} · change it any time "
                                                        "in Goals & Settings")
                        + "</dl>")
                with st.container(key="ob_changes", horizontal=True):
                    for n_ in ("identity", "want", "scope", "purpose"):
                        st.button(CHANGE[n_], key=f"ob_change_{n_}", type="tertiary", on_click=go,
                                  args=(n_, "confirm"))
                problem = st.session_state.pop("ob_problem", "")
                nav(label="Start learning", ready=bool(d["path"]), note=problem, on=start)
