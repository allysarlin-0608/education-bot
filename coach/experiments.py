"""Comparing variants instead of guessing (docs/LEARNING_DESIGN.md §7c).

Each experiment has two arms. Which arm someone is in is worked out from a
hash of who they are (and, for a within-learner design, of the day or the
idea), so it needs no storage and never changes; every answer recorded
(coach/attempts.py) carries the arms that were in force, and the learning
dashboard (coach/learnmetrics.py) compares them.

The test site has few learners, so the first experiments randomise within
each learner where that is possible (a day, an idea), which needs far fewer
people than one arm per person:
- "interleave": a day's mixed practice in mixed order (ideas taken in turn)
  or blocked (one idea's items together). Unit: the day. Read on delayed
  retention (reviews a week or more later).
- "fading": a new idea's practice as a worked example that fades into
  problems, or problem first (the worked steps only after a miss). Unit:
  the idea. Read on first-attempt accuracy and days to mastery.
- "retention": reviews scheduled for 90% or 85% recall (coach/review.py).
  Unit: the learner (a schedule has to be one person's). Read on retention
  and how many reviews a day it costs.

Experiments run only on the public (test) site and can be switched off
with the setting GNOSIS_EXPERIMENTS=off; switched off, everyone gets the
first arm. Pure: the caller says whether they're on."""
import hashlib

EXPERIMENTS = {
    "interleave": {"arms": ("mixed", "blocked"), "unit": "day"},
    "fading": {"arms": ("faded", "problem_first"), "unit": "idea"},
    "retention": {"arms": ("r90", "r85"), "unit": "learner"},
}
TARGETS = {"r90": 0.9, "r85": 0.85}


def enabled(setting: str, public: bool) -> bool:
    return public and (setting or "").strip().lower() not in ("off", "0", "false", "no")


def arm(name: str, learner: str, *unit, on: bool = True) -> str:
    """The arm of experiment `name` for this learner (and day or idea)."""
    arms = EXPERIMENTS[name]["arms"]
    if not on or not learner:
        return arms[0]
    digest = hashlib.sha256("|".join([name, str(learner), *map(str, unit)]).encode()).digest()
    return arms[digest[0] % len(arms)]


def tag(name: str, which: str) -> str:
    """How an arm is written on a recorded answer: "fading:faded"."""
    return f"{name}:{which}"


def target(learner: str, on: bool = True) -> float:
    return TARGETS[arm("retention", learner, on=on)]
