"""First-time setup: short steps, one decision each, in this order:
Welcome; Plans (Free or Plus, what each includes); Courses & subjects (ours,
and a goal of her own: coach/goalmaker.py, the path the AI designs for it);
Reading plan (only on a plan that includes it, and optional); Your
selection (what she chose, each part changeable); Price summary (what it
costs: nothing is charged, there is no payment yet); Customize learning
(time each day, how often, the order of her turns, where each subject
starts); Your path (the order of her days and where each course goes first;
her goal's path to adjust); Final review; and Start learning, which saves
it all and opens her first day. route() gives the steps her answers call for.

Her answers are kept in her settings row as she goes (settings "onboarding"),
so a refresh, Back or a change from the review never loses them. She counts
as set up only once she presses Start learning: then the settings are
checked, saved with onboarded_at, and her first day opens."""
from html import escape

import streamlit as st

from coach import catalog, choices, goalmaker, pathview, plans, settings, stage, ui, visuals

STEP_NAMES = {"welcome": "Welcome", "plans": "Plans", "subjects": "Courses & subjects", "goal": "Your goal",
              "reading": "Reading plan", "selection": "Your selection", "price": "Price summary",
              "customize": "Customize learning", "path": "Your path", "review": "Final review"}
CHANGE = {"plans": "Change plan", "subjects": "Change subjects", "goal": "Change your goal",
          "reading": "Change reading plan", "customize": "Change time, order or level", "path": "Change your path"}


def draft() -> dict:
    return settings.draft_of(ui.config())


def put(d: dict) -> None:
    """Keep her answers so far (not yet a finished setup: onboarded_at stays empty).
    Once the setup is finished (Start learning, here or in another tab), a
    click left on a setup page saves nothing: a draft written onto a
    finished setup mixed old answers into her account (and the New goal page
    then opened the setup's path as if it were new)."""
    ui.refresh_settings()       # onto the row as stored now (another tab may have changed it; ISS-044)
    if settings.onboarded(ui.config()):
        return                  # (the next run opens the app as it now is)
    ui.save_settings(dict(ui.config(), onboarding=d))


def plan(d: dict) -> str:
    """Her plan for the setup: the one she chose while plans are shown
    (plans.SHOWN); else nobody chooses one, and everyone has every feature."""
    return d["plan"] if plans.SHOWN else plans.DEFAULT


def reading_offered(d: dict) -> bool:
    """The reading plan is offered on a plan that includes it (to everyone
    while plans aren't shown: no feature is held back then)."""
    if not plans.SHOWN:
        return True
    return plans.known(d["plan"]) and bool(plans.includes(d["plan"], "reading_plan"))


def route(d: dict) -> list:
    """The steps her answers call for: Your goal once she asked for a goal
    of her own (or has one), Reading plan only on a plan that includes it."""
    out = ["welcome"] + (["plans"] if plans.SHOWN else []) + ["subjects"]
    out += ["goal"] if d["want_goal"] or d["path"] else []
    out += ["reading"] if reading_offered(d) else []
    return out + ["selection"] + (["price"] if plans.SHOWN else []) + ["customize", "path", "review"]


def reachable(d: dict) -> str:
    """The step to show: hers, or the furthest her answers allow (a stale
    draft can't skip ahead, and a step her answers no longer call for
    gives way to the one before it)."""
    steps = route(d)
    name = settings.STEPS[d["step"]]
    while name not in steps:
        name = settings.STEPS[settings.STEPS.index(name) - 1]
    at = steps.index(name)
    if plans.SHOWN and not plans.known(d["plan"]):
        at = min(at, steps.index("plans"))
    if not d["subjects"] and not d["path"]:
        at = min(at, steps.index("goal") if "goal" in steps else steps.index("subjects"))
    if any(v is None for v in settings.draft_levels(d).values()):
        at = min(at, steps.index("customize"))
    return steps[at]


def go(name: str, back_to=None) -> None:
    """To a step of her route (as far as her answers allow). back_to: the
    step a change was asked from (the final review), offered again on the
    way ("Back to final review"), so a change never means walking every step."""
    d = draft()
    now = reachable(d)
    steps = route(d)
    if name not in steps:
        return
    st.session_state.ob_way = "fwd" if steps.index(name) > steps.index(now) else "back"
    st.session_state.ob_from = steps.index(now)
    d["step"] = settings.STEPS.index(name)
    d["step"] = settings.STEPS.index(reachable(d))
    d["back_to"] = None if settings.STEPS[d["step"]] == "review" else back_to or d.get("back_to")
    put(d)


def can_return(d: dict) -> bool:
    """Back to the final review is offered once her answers allow it again."""
    if d.get("back_to") != "review":
        return False
    return reachable(dict(d, step=settings.STEPS.index("review"))) == "review"


def step_by(k: int):
    """The step k away from this one on her route."""
    steps = route(d)
    return steps[max(0, min(steps.index(step) + k, len(steps) - 1))]


# ---------------------------------------------------------------- her answers
def pick_plan(name: str) -> None:
    d = draft()
    d["plan"] = name
    if not reading_offered(d):
        d["reading_enabled"] = False       # (a plan without it: no reading plan is set up)
    put(d)


def pick_subject(topic: str) -> None:
    st.session_state.ob_focus = topic           # the lens goes to the row she touched
    d = draft()
    d["subjects"] = settings.toggle_subject(d["subjects"], topic)
    put(d)


def want_goal() -> None:
    put(dict(draft(), want_goal=True))
    go("goal")


def skip_goal() -> None:
    """No goal of her own (for now): its path goes (her words stay), and on
    to the step after the subjects (back to them if none is chosen)."""
    goalmaker.again(draft, put)
    d = dict(draft(), want_goal=False)
    put(d)
    steps = route(d)
    go(steps[steps.index("subjects") + (1 if d["subjects"] else 0)])


def pick_pace(n: int) -> None:
    put(dict(draft(), units_per_day=n))


def move(item: str, k: int) -> None:
    put(settings.move_turn(draft(), item, k))


def set_level(topic: str, change) -> None:
    d = draft()
    d["levels"][topic] = change(settings.level_choice(d, topic))
    put(d)


def set_way(topic: str) -> None:
    way = st.session_state[f"lvl_{topic}"] or choices.BASICS
    set_level(topic, lambda c: dict(c, way=way))


def set_reading() -> None:
    d = draft()
    put(dict(d, reading_enabled=bool(st.session_state.ob_reading) and reading_offered(d)))


def start() -> None:
    """Start learning: check everything, save it as her settings (her goal's
    path first), and her first day opens."""
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
    # the plan she chose, as asked for (nothing is charged; her plan is plans.plan_of). A
    # preference that can't be kept (its table missing) doesn't hold up her start.
    if plans.SHOWN:
        ui.update_prefs(plan_choice=d["plan"])
    st.session_state.pop("coach_save_error", None)
    ui.record("setup_done")
    if d["path"]:
        ui.record("goal_created")
    st.session_state.pop("ob_way", None)
    first = done["subjects"][0]
    if visuals.known(first):
        st.session_state.enter_world = first     # into the first day's subject (a goal: Today)


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
        if can_return(d) and step != "review" and not on:
            st.button("Back to final review", key="ob_to_review", type="tertiary", disabled=not ready,
                      on_click=go, args=("review",))
        st.button(label, key="ob_next", type="primary", disabled=not ready,
                  on_click=on or go, args=() if on else (step_by(1),))


def lead(title: str, lede: str) -> None:
    st.markdown(f"## {title}")
    st.html(f'<p class="ob-lede">{escape(lede)}</p>')


def changes(*names) -> None:
    """Ways back to an earlier step (what she chose elsewhere is kept; from
    the final review, the way back to it is offered on every step after)."""
    with st.container(key="ob_changes", horizontal=True):
        for name in names:
            st.button(CHANGE[name], key=f"ob_change_{name}", type="tertiary", on_click=go,
                      args=(name, step if step == "review" else None))


def turn_names(d: dict) -> list:
    return [d["path"]["title"] if t == settings.GOAL else catalog.name(t) for t in settings.rotation(d)]


def row(term: str, value_html: str, small: str = "") -> str:
    return (f"<div><dt>{escape(term)}</dt><dd>{value_html}"
            + (f"<small>{escape(small)}</small>" if small else "") + "</dd></div>")


def level_line(d: dict, t: str) -> str:
    c = settings.level_choice(d, t)
    lv = settings.draft_levels(d)[t]
    how = f"{c['score']} of 5 right" if c["way"] == choices.PLACEMENT else "from the basics"
    return (f'<span class="ob-pair"><span>{escape(catalog.name(t))}</span>'
            f'<span>{escape(lv or "")} <small>· {how}</small></span></span>')


def chosen_rows(d: dict) -> str:
    """What she chose: the plan, subjects, goal, reading plan."""
    plan_ = plan(d)
    out = row("Plan", escape(plans.NAMES[plan_]), plans.price_line(plan_)) if plans.SHOWN else ""
    if d["subjects"]:
        objs = "".join(visuals.object_html(t, "ob-obj", list(settings.SUBJECTS).index(t) + 1) for t in d["subjects"])
        out += row("Subjects", f'<span class="ob-objs">{objs}</span>'
                   + escape(", ".join(catalog.name(t) for t in d["subjects"])),
                   f"{len(d['subjects'])} of {plans.includes(plan_, 'subjects')}"
                   + (" on your plan" if plans.SHOWN else ""))
    if d["path"]:
        out += row("Your goal", escape(d["path"]["title"]), "A path designed for it")
    if reading_offered(d):
        out += row("Reading plan", "On" if d["reading_enabled"] else "Off",
                   "A book over 14 days" if d["reading_enabled"] else "You can add one later")
    else:
        out += row("Reading plan", "Not on your plan", "Included in Plus")
    return out


def learning_rows(d: dict) -> str:
    """How she will learn: time, how often, the order, starting levels."""
    name, minutes = settings.PACES[d["units_per_day"]]
    n = d["units_per_day"]
    names = turn_names(d)
    out = row("Time each day", escape(name), f"{n} {'lesson' if n == 1 else 'lessons'} a day · {minutes}")
    out += row("Order of your days", escape(" → ".join(names)),
               "Every day" if len(names) == 1 else "One a day, taking turns")
    if d["subjects"]:
        out += row("Starting level", "".join(level_line(d, t) for t in d["subjects"]))
    return out


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
            st.html('<p class="ob-lede">GNOSIS teaches the subjects you choose, or a goal of your own, in short '
                    "daily lessons. Each lesson has a quiz to check it stayed, review brings back what you "
                    "might forget, and your record shows what you know.</p>"
                    f'<p class="ob-note">Next: {"choose a plan, then " if plans.SHOWN else ""}what to learn. '
                    "You can go back at any step; nothing is final until you press Start learning.</p>")
            with st.container(key="ob_nav", horizontal=True, horizontal_alignment="left"):
                st.button("Get started", key="ob_next", type="primary", on_click=go, args=(steps[1],))

    elif step == "plans":
        with st.container(key="ob_grid"):
            with st.container(key="ob_lead"):
                lead("Choose a plan", "Both plans teach every subject the same way. You can change your plan later.")
            with st.container(key="ob_body"):
                choices.rows("plan", [(k, plans.NAMES[k], plans.price_line(k) + " · " + plans.BLURBS[k])
                                      for k in plans.PLANS], [d["plan"]] if d["plan"] else [], pick_plan)
                head = "".join(f"<th scope='col'>{escape(plans.NAMES[k])}</th>" for k in plans.PLANS)
                body = "".join(f"<tr><th scope='row'>{escape(label)}</th>"
                               + "".join(f"<td>{escape(plans.value_line(k, f))}</td>" for k in plans.PLANS) + "</tr>"
                               for f, label in plans.FEATURES)
                body += "".join(f"<tr><th scope='row'>{escape(x)}</th>" + "<td>Included</td>" * len(plans.PLANS)
                                + "</tr>" for x in plans.EVERY_PLAN)
                st.html(f'<table class="ob-plans"><thead><tr><th><span class="sr-only">Feature</span></th>{head}'
                        f'</tr></thead><tbody>{body}</tbody></table>'
                        '<p class="ob-note">Paid plans aren\'t open yet: there is no payment, and nothing will be '
                        "charged. While plans are being prepared, everyone can use every feature that exists.</p>")
                nav(ready=plans.known(d["plan"]), note="" if plans.known(d["plan"]) else "Choose a plan to continue.")

    elif step == "subjects":
        limit, goals = plans.includes(plan(d), "subjects"), plans.includes(plan(d), "active_goals")
        with st.container(key="ob_grid_subjects"):
            with st.container(key="ob_lead"):
                lead("What would you like to learn?",
                     f"Choose up to {limit} of our subjects, a goal of your own, or both. They take turns, one a day.")
            # one subject in focus, for the stage and the lens alike
            focus = stage.focus_of(st.session_state.get("ob_focus"), d["subjects"])
            with st.container(key="ob_stage"):
                st.html(stage.html(focus, "subj"))
            with st.container(key="ob_body"):
                full = len(d["subjects"]) >= limit
                choices.rows("subj", stage.rows(),
                             d["subjects"], pick_subject, multi=True, full=full, focus=focus, style="index")
                with st.container(key="ob_goal_way", horizontal=True, vertical_alignment="center"):
                    if d["path"]:
                        st.html(f'<p class="ob-note">Your goal: <b>{escape(d["path"]["title"])}</b></p>')
                        st.button("Change your goal", key="ob_to_goal", type="tertiary", on_click=go, args=("goal",))
                    elif not d["want_goal"]:
                        st.button("Or set a goal of your own", key="ob_to_goal", type="tertiary", on_click=want_goal)
                n = len(d["subjects"])
                counted = (f"{n} of {limit} chosen" + (" · the most you can choose" if full else "") if n
                           else "" if d["path"] or d["want_goal"] else "Choose at least one subject to continue.")
                plan_note = (f"{plans.NAMES[plan(d)]} plan: up to {limit} subjects and "
                             f"{goals} {'goal' if goals == 1 else 'goals'} of your own at a time." if plans.SHOWN else "")
                nav(ready=n >= settings.MIN_SUBJECTS or bool(d["path"]) or d["want_goal"],
                    note=" · ".join(x for x in (counted, plan_note) if x))

    elif step == "goal":
        with st.container(key="ob_grid"):
            with st.container(key="ob_lead"):
                lead("A goal of your own", "Say what you want to learn in your own words, or start from an idea. "
                                           "We'll design a path for it; you can adjust it at Your path.")
            with st.container(key="ob_body"):
                if d["path"]:
                    st.html(goalmaker.summary_html(d["path"], d["units_per_day"], eyebrow="Your goal"))
                    with st.container(key="ob_goal_acts", horizontal=True):
                        st.button("Start over with a different goal", key="ob_again", type="tertiary",
                                  on_click=lambda: goalmaker.again(draft, put))
                        st.button("Remove this goal", key="ob_no_goal", type="tertiary", on_click=skip_goal)
                    nav()
                else:
                    goalmaker.form("obg", draft, put, pace=d["units_per_day"],
                                   skip=("Continue without a goal", skip_goal))
                    with st.container(key="ob_goal_back", horizontal=True):
                        st.button("Back", key="ob_back", type="tertiary", on_click=go, args=(step_by(-1),))

    elif step == "reading":
        with st.container(key="ob_grid"):
            with st.container(key="ob_lead"):
                lead("Reading plan", (f"Included in {plans.NAMES[plan(d)]}, and optional. " if plans.SHOWN else "Optional. ")
                     + "Choose a book and it is split into 14 days: read your part each day, then talk it through.")
            with st.container(key="ob_body"):
                with st.container(key="ob_toggle"):
                    st.toggle("Add a 14-day reading plan", value=d["reading_enabled"], key="ob_reading",
                              on_change=set_reading)
                nav(label="Continue" if d["reading_enabled"] else "Skip for now")

    elif step == "selection":
        with st.container(key="ob_grid"):
            with st.container(key="ob_lead"):
                lead("Your selection", "What you chose so far. Change anything before you go on.")
            with st.container(key="ob_body"):
                st.html(f'<dl class="ob-summary">{chosen_rows(d)}</dl>')
                changes(*(["plans"] if plans.SHOWN else []), "subjects", *(["goal"] if d["path"] else []),
                        *(["reading"] if reading_offered(d) else []))
                nav()

    elif step == "price":
        plan = d["plan"]
        with st.container(key="ob_grid"):
            with st.container(key="ob_lead"):
                lead("Price summary", "What your plan costs and what it includes. No hidden charges.")
            with st.container(key="ob_body"):
                included = "".join(f"<span class='ob-pair'><span>{escape(label)}</span>"
                                   f"<span>{escape(plans.value_line(plan, f))}</span></span>"
                                   for f, label in plans.FEATURES)
                st.html('<dl class="ob-summary">'
                        + row("Plan", escape(plans.NAMES[plan]), plans.price_line(plan))
                        + row("Included", included, "Daily lessons, review, practice and your record are on every plan")
                        + row("Extra costs", "None", "Nothing is added for subjects, lessons or review")
                        + row("Due today", f"{plans.CURRENCY} {plans.due_today(plan):.2f}",
                              "Nothing is charged: payment isn't available yet")
                        + "</dl>"
                        + ('<p class="ob-note" role="note">The Plus price hasn\'t been set yet. Paid plans will open '
                           "later; you'll see the price and be asked before anything is ever charged. Until then you "
                           "use GNOSIS at no cost.</p>" if plans.PRICES.get(plan) is None else ""))
                nav()

    elif step == "customize":
        turns = settings.rotation(d)
        with st.container(key="ob_grid"):
            with st.container(key="ob_lead"):
                lead("Customize your learning", "How much each day, the order of your days, and where each "
                                                "subject starts. You can change these later in Learning Plan.")
            with st.container(key="ob_body"):
                st.html('<p class="ob-subject">Time each day</p>')
                choices.rows("pace", [(n, name, settings.pace_line(n), {"bars": n})
                                      for n, (name, _) in settings.PACES.items()],
                             [d["units_per_day"]], pick_pace, style="pace")
                st.html('<p class="ob-subject">How often</p>'
                        '<p class="ob-note">Every day, one subject or goal a day. Other rhythms (weekdays only, '
                        "say) aren't available yet; you can take a rest day from Today.</p>")
                if len(turns) > 1:
                    st.html('<p class="ob-subject">Order and priority</p>'
                            '<p class="ob-note">The first comes on your first day; then they take turns.</p>')
                    names = turn_names(d)
                    for i, item in enumerate(turns):
                        with st.container(key=f"ob_turn_{i}", horizontal=True, vertical_alignment="center"):
                            st.html(f'<p class="ob-turn"><span>Day {i + 1}</span> {escape(names[i])}</p>')
                            st.button("Earlier", key=f"ob_up_{i}", type="tertiary", disabled=i == 0,
                                      on_click=move, args=(item, -1))
                            st.button("Later", key=f"ob_down_{i}", type="tertiary", disabled=i == len(turns) - 1,
                                      on_click=move, args=(item, 1))
                levels = settings.draft_levels(d)
                if d["subjects"]:
                    st.html('<p class="ob-subject">Depth: where each subject starts</p>'
                            '<p class="ob-note">Start from the basics, or answer five quick questions to find '
                            "your level.</p>")
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
                if d["path"]:
                    st.html('<p class="ob-note">Your goal\'s depth is set on its path, next.</p>')
                waiting = [catalog.name(t) for t, lv in levels.items() if lv is None]
                nav(ready=not waiting, note=f"Finish the questions for {', '.join(waiting)} to continue." if waiting else "")

    elif step == "path":
        levels = settings.draft_levels(d)
        with st.container(key="ob_grid"):
            with st.container(key="ob_lead"):
                lead("Your path", "The order of your days, and where each course goes first. "
                                  "Lessons come one after another; each is written when you reach it.")
            with st.container(key="ob_body"):
                st.html(pathview.turns_html(turn_names(d), d["units_per_day"]))
                for t in settings.rotation(d):
                    if t == settings.GOAL:
                        with st.container(key="ob_goal_path"):
                            st.html('<p class="ob-subject">Your goal</p>'
                                    '<p class="ob-note">Make it yours: change the depth, skip what you know, '
                                    "move parts around.</p>")
                            goalmaker.review("obp", draft, put, d["units_per_day"])
                    else:
                        st.html(pathview.subject_outline(t, levels.get(t) or ""))
                changes("customize")
                nav()

    else:
        with st.container(key="ob_grid"):
            with st.container(key="ob_lead"):
                lead("Final review", "Everything you chose. Go back to change any part: your other answers are kept.")
            with st.container(key="ob_body"):
                turns = settings.rotation(d)
                enter = turns[0] if turns and turns[0] != settings.GOAL else ""
                st.html((f'<div hidden data-enter="{enter}"></div>' if enter else "")
                        + f'<dl class="ob-summary">{chosen_rows(d)}{learning_rows(d)}'
                        + (row("Due today", f"{plans.CURRENCY} {plans.due_today(plan(d)):.2f}", "Nothing is charged")
                           if plans.SHOWN else "")
                        + "</dl>")
                changes(*(["plans"] if plans.SHOWN else []), "subjects", *(["goal"] if d["path"] else []),
                        *(["reading"] if reading_offered(d) else []), "customize", "path")
                problem = st.session_state.pop("ob_problem", "")
                levels = settings.draft_levels(d)
                nav(label="Start learning", ready=bool(turns) and not any(v is None for v in levels.values()),
                    note=problem, on=start)
