"""The day's lessons as steps on Today's progress bar. Every state comes
from the saved lessons (and which one she has open), never from fixed
values:

- completed: its quiz is passed; it can be opened to review
- current:   the first lesson not completed; there is none once all are done
- locked:    not completed and after the current one; opening it only
             says what unlocks it
- viewing:   the one open on the page (with completed or current)
"""
from coach.i18n import tr

COMPLETED, CURRENT, LOCKED = "completed", "current", "locked"


def current(plan):
    """Index of the first lesson not completed, or None when all are done."""
    return next((k for k, s in enumerate(plan) if not s["completed"]), None)


def states(plan, viewing):
    now = current(plan)
    return [
        {"state": COMPLETED if s["completed"] else CURRENT if k == now else LOCKED,
         "viewing": k == viewing}
        for k, s in enumerate(plan)
    ]


def done(plan):
    return sum(1 for s in plan if s["completed"])


def viewing(plan, chosen):
    """The lesson to show: her choice if it can be opened, otherwise the
    current one (None once all are done: the page shows the day's summary)."""
    now = current(plan)
    if chosen is not None and 0 <= chosen < len(plan) and (plan[chosen]["completed"] or chosen == now):
        return chosen
    return now


def label(plan):
    """The one line under the bar, e.g. "Lesson 2 of 5 · 1 done"."""
    now, total = current(plan), len(plan)
    if now is None:
        return tr("All {total} lessons done", total=total)
    return tr("Lesson {n} of {total} · {done} done", n=now + 1, total=total, done=done(plan))


def unlock_message(plan, k):
    """What a locked lesson says when she taps it."""
    return tr("Unlocks after you pass Lesson {n}'s quiz", n=plan[k - 1]['n'])


def just_completed(before, plan):
    """Lessons completed since `before` (the completed flags shown last
    time): the segments that fill from left to right this once."""
    if before is None or len(before) != len(plan):
        return set()
    return {k for k, (was, s) in enumerate(zip(before, plan)) if s["completed"] and not was}


def arrow(viewing, target):
    """Which way the lesson "Back to" goes: ↓ to a later lesson, ↑ to an
    earlier one or to the summary at the top."""
    return "down" if target is not None and viewing is not None and target > viewing else "up"
