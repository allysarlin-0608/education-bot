"""What each plan includes. Prepared, not enforced: while ENFORCED is False
everyone has the app's own limits (settings.MAX_GOALS) and no page mentions
a plan or an upgrade. When paid plans start, a learner's plan is read from
her account and these numbers apply.

The plan names and numbers are a proposal (PRODUCT_PLAN.md §7): a free plan
with one goal of her own at a time and the built-in subjects; a paid plan
with several goals and certificates of completion."""
from coach import settings

ENFORCED = False

PLANS = {
    "free": {"active_goals": 1, "certificates": False},
    "plus": {"active_goals": settings.MAX_GOALS, "certificates": True},
}


def plan_of(config: dict) -> str:
    """Her plan (everyone is on "free" until plans are stored with accounts)."""
    return "free"


def active_goals_allowed(config: dict) -> int:
    """How many of her own goals may be active at once."""
    if not ENFORCED:
        return settings.MAX_GOALS
    return PLANS[plan_of(config)]["active_goals"]
