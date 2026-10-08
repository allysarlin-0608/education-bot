"""First-time setup: short steps, one decision each. Welcome, then Your
goal: what she wants to learn, in her words (coach/goalmaker.py), and Your
path, the one the AI designed for it, to adjust; or, instead or as well,
our subjects (Subjects, Daily pace, Level); then Reading and Summary.
route() gives the steps her answers call for.

Her answers are kept in her settings row as she goes (settings "onboarding"),
so a refresh brings her back to the same step with everything she chose.
She counts as set up only once she presses Start learning: then the
settings are checked, saved with onboarded_at, and Today opens."""
from html import escape

import streamlit as st

from coach import catalog, choices, goalmaker, settings, stage, ui, visuals

STEP_NAMES = {"welcome": "Welcome", "goal": "Your goal", "path": "Your path", "subjects": "Subjects",
              "pace": "Daily pace", "level": "Level", "reading": "Reading", "summary": "Summary"}


def draft() -> dict:
    return settings.draft_of(ui.config())


def put(d: dict) -> None:
    """Keep her answers so far (not yet a finished setup: onboarded_at stays empty)."""
    ui.refresh_settings()       # onto the row as stored now (another tab may have changed it; ISS-044)
    ui.save_settings(dict(ui.config(), onboarding=d))


def route(d: dict) -> list:
    """The steps her answers call for: Your path once a goal has one (and
    then the time she has was asked with the goal), Level only for subjects."""
    out = ["welcome", "goal"]
    out += ["path"] if d["path"] else []
    out += ["subjects"]
    out += [] if d["path"] else ["pace"]
    out += ["level"] if d["subjects"] else []
    return out + ["reading", "summary"]


def reachable(d: dict) -> str:
    """The step to show: hers, or the furthest her answers allow (a stale
    draft can't skip ahead, and a step her answers no longer call for
    gives way to the one before it)."""
    steps = route(d)
    name = settings.STEPS[d["step"]]
    while name not in steps:
        name = settings.STEPS[settings.STEPS.index(name) - 1]
    at = steps.index(name)
    if not d["subjects"] and not d["path"]:
        at = min(at, steps.index("subjects"))
    if any(v is None for v in settings.draft_levels(d).values()):
        at = min(at, steps.index("level"))
    return steps[at]


def go(name: str) -> None:
    d = draft()
    now = reachable(d)
    steps = route(d)
    st.session_state.ob_way = "fwd" if steps.index(name) > steps.index(now) else "back"
    st.session_state.ob_from = steps.index(now)
    d["step"] = settings.STEPS.index(name)
    d["step"] = settings.STEPS.index(reachable(d))
    put(d)


def step_by(k: int):
    """The step k away from this one on her route."""
    steps = route(d)
    return steps[max(0, min(steps.index(step) + k, len(steps) - 1))]


def pick_subject(topic: str) -> None:
    st.session_state.ob_focus = topic           # the lens goes to the row she touched
    d = draft()
    d["subjects"] = settings.toggle_subject(d["subjects"], topic)
    put(d)


def pick_pace(n: int) -> None:
    put(dict(draft(), units_per_day=n))


def set_level(topic: str, change) -> None:
    d = draft()
    d["levels"][topic] = change(settings.level_choice(d, topic))
    put(d)


def set_way(topic: str) -> None:
    way = st.session_state[f"lvl_{topic}"] or choices.BASICS
    set_level(topic, lambda c: dict(c, way=way))


def set_reading() -> None:
    put(dict(draft(), reading_enabled=bool(st.session_state.ob_reading)))


def start() -> None:
    """Start learning: check everything, save it as her settings (her goal's
    path first), and Today opens."""
    ui.refresh_settings()          # finished onto the row as stored now (as every settings save is)
    d = draft()
    try:
        done = settings.finish(ui.config(), d, settings.now_iso())
    except ValueError as e:
        st.session_state.ob_problem = str(e)
        return
    if d["path"] and not ui.save_path(st.session_state.coach_log, d["path"]):
        st.session_state.ob_problem = "Your goal wasn't saved. Try again in a moment."
        return
    if not ui.save_settings(done):
        # said beside the button she pressed (the page's own error line is at the top, out of sight: ISS-061)
        st.session_state.ob_problem = st.session_state.pop("coach_save_error", "") or \
            "Your plan wasn't saved. Try again in a moment."
        return
    ui.record("setup_done")
    if d["path"]:
        ui.record("goal_created")
    st.session_state.pop("ob_way", None)
    if visuals.known(done["subjects"][0]):
        st.session_state.enter_world = done["subjects"][0]     # into the first day's subject (a goal: Today)


def skip_goal() -> None:
    go("subjects")


def nav(back: bool = True, label: str = "Continue", ready: bool = True, note: str = "", on=None) -> None:
    """Back and Continue, at the foot of the step (a note on what's missing just above)."""
    if note:
        st.html(f'<p class="ob-note">{escape(note)}</p>')
    with st.container(key="ob_nav", horizontal=True, horizontal_alignment="distribute", vertical_alignment="center"):
        if back:
            st.button("Back", key="ob_back", type="tertiary", on_click=go, args=(step_by(-1),))
        else:
            st.html('<span class="pq-gap"></span>')
        st.button(label, key="ob_next", type="primary", disabled=not ready,
                  on_click=on or go, args=() if on else (step_by(1),))


def lead(title: str, lede: str) -> None:
    st.markdown(f"## {title}")
    st.html(f'<p class="ob-lede">{escape(lede)}</p>')


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
    if step == "welcome":
        with st.container(key="ob_hero"):
            st.markdown("# Learn what you want, a little every day")
            st.html('<p class="ob-lede">Tell us what you want to learn and why. GNOSIS designs a short path '
                    "for it and teaches it in a few minutes a day, each lesson with a quiz to check it stayed.</p>")
            with st.container(key="ob_nav", horizontal=True, horizontal_alignment="left"):
                st.button("Get started", key="ob_next", type="primary", on_click=go, args=("goal",))

    elif step == "goal":
        with st.container(key="ob_grid"):
            with st.container(key="ob_lead"):
                lead("What do you want to learn?",
                     "Say it in your own words, or start from an idea. We'll design a path for it.")
            with st.container(key="ob_body"):
                goalmaker.form("obg", draft, put, skip=("Choose from our subjects instead", skip_goal),
                               on_path=lambda: go("path"))
                if d["path"]:
                    st.button("Back to your path", key="ob_to_path", type="tertiary", on_click=go, args=("path",))

    elif step == "path":
        with st.container(key="ob_grid"):
            with st.container(key="ob_lead"):
                lead("Your path", "Designed for your goal. Make it yours: change the depth, "
                                  "skip what you know, move parts around.")
            with st.container(key="ob_body"):
                goalmaker.review("obp", draft, put, d["units_per_day"])
                st.button("Start over with a different goal", key="ob_again", type="tertiary",
                          on_click=lambda: (goalmaker.again(draft, put), go("goal")))
                nav()

    elif step == "subjects":
        with st.container(key="ob_grid_subjects"):
            with st.container(key="ob_lead"):
                if d["path"]:
                    lead("Add a subject?", "Optional. Our subjects can take turns with your goal, one a day. "
                                           "Choose up to three, or continue without.")
                else:
                    lead("What would you like to learn?",
                         "Choose up to three. They take turns, one a day, in the order you choose them.")
            # one subject in focus, for the stage and the lens alike
            focus = stage.focus_of(st.session_state.get("ob_focus"), d["subjects"])
            with st.container(key="ob_stage"):
                st.html(stage.html(focus, "subj"))
            with st.container(key="ob_body"):
                full = len(d["subjects"]) >= settings.MAX_SUBJECTS
                choices.rows("subj", stage.rows(),
                             d["subjects"], pick_subject, multi=True, full=full, focus=focus, style="index")
                n = len(d["subjects"])
                nav(ready=n >= settings.MIN_SUBJECTS or bool(d["path"]),
                    note=(f"{n} of {settings.MAX_SUBJECTS} chosen" + (" · the most you can choose" if full else "")
                          if n else "" if d["path"] else "Choose at least one subject to continue."))

    elif step == "pace":
        with st.container(key="ob_grid"):
            with st.container(key="ob_lead"):
                lead("How much each day?", "One subject a day, in short lessons. You can change this later in Settings.")
            with st.container(key="ob_body"):
                choices.rows("pace", [(n, name, settings.pace_line(n), {"bars": n})
                                      for n, (name, _) in settings.PACES.items()],
                             [d["units_per_day"]], pick_pace, style="pace")
                nav()

    elif step == "level":
        with st.container(key="ob_grid"):
            with st.container(key="ob_lead"):
                lead("Where should each subject start?",
                     "Start from the basics, or answer five quick questions to find your level.")
            with st.container(key="ob_body"):
                levels = settings.draft_levels(d)
                for t in d["subjects"]:
                    c = settings.level_choice(d, t)
                    with st.container(key=f"ob_subject_{t}"):
                        st.html(f'<p class="ob-subject">{escape(catalog.name(t))}</p>')
                        choices.way_switch(f"lvl_{t}", c["way"], set_way, args=(t,))
                        if c["way"] == choices.PLACEMENT:
                            choices.placement(
                                t, t, c,
                                on_answer=lambda i, t=t: set_level(t, lambda c: choices.answer(c, i)),
                                on_move=lambda k, t=t: set_level(t, lambda c: choices.move(c, t, k)),
                                on_again=lambda t=t: set_level(t, lambda c: dict(c, **choices.fresh())))
                waiting = [catalog.name(t) for t, lv in levels.items() if lv is None]
                nav(ready=not waiting, note=f"Finish the questions for {', '.join(waiting)} to continue." if waiting else "")

    elif step == "reading":
        with st.container(key="ob_grid"):
            with st.container(key="ob_lead"):
                lead("Reading", "Choose a book and it is split into 14 days: read your part each day, "
                                "then come back and talk it through.")
            with st.container(key="ob_body"):
                with st.container(key="ob_toggle"):
                    st.toggle("Add a 14-day reading plan", value=d["reading_enabled"], key="ob_reading",
                              on_change=set_reading)
                nav()

    else:
        levels = settings.draft_levels(d)
        name, minutes = settings.PACES[d["units_per_day"]]
        n = d["units_per_day"]
        order = ([d["path"]["title"]] if d["path"] else []) + [catalog.name(t) for t in d["subjects"]]

        def level_line(t):
            c = settings.level_choice(d, t)
            how = f"{c['score']} of 5 right" if c["way"] == choices.PLACEMENT else "from the basics"
            return (f'<span class="ob-pair"><span>{escape(catalog.name(t))}</span>'
                    f'<span>{escape(levels[t] or "")} <small>· {how}</small></span></span>')

        with st.container(key="ob_grid"):
            with st.container(key="ob_lead"):
                lead("Your plan", "Everything can be changed later in Settings.")
            with st.container(key="ob_body"):
                if d["path"]:
                    st.html(goalmaker.summary_html(d["path"], n, eyebrow="Your goal · your first lesson is today"))
                objs = "".join(visuals.object_html(t, "ob-obj", list(settings.SUBJECTS).index(t) + 1) for t in d["subjects"])
                first = d["subjects"][0] if d["subjects"] and not d["path"] else ""
                st.html((f'<div hidden data-enter="{first}"></div>' if first else "") + '<dl class="ob-summary">'
                        + (f'<div><dt>Subjects</dt><dd><span class="ob-objs">{objs}</span>'
                           f'{escape(" → ".join(catalog.name(t) for t in d["subjects"]))}</dd></div>'
                           if d["subjects"] else "")
                        + f'<div><dt>Your days</dt><dd>{escape(" → ".join(order))}'
                        f'<small>{"Every day" if len(order) == 1 else "One a day, taking turns"}</small></dd></div>'
                        f'<div><dt>Daily pace</dt><dd>{name}<small>{n} {"lesson" if n == 1 else "lessons"} a day · {minutes}</small></dd></div>'
                        + (f'<div><dt>Starting level</dt><dd>{"".join(level_line(t) for t in d["subjects"])}</dd></div>'
                           if d["subjects"] else "")
                        + f'<div><dt>Reading plan</dt><dd>{"On" if d["reading_enabled"] else "Off"}'
                        f'<small>{"A book over 14 days" if d["reading_enabled"] else "You can add one later"}</small></dd></div>'
                        "</dl>")
                problem = st.session_state.pop("ob_problem", "")
                nav(label="Start learning", ready=bool(order) and not any(v is None for v in levels.values()),
                    note=problem, on=start)
