"""What each plan includes. Prepared, not enforced: while ENFORCED is False
everyone has the app's own limits (settings.MAX_GOALS, the reading plan)
whatever plan she chose, and nothing is charged.

The setup (views/setup.py) lets her choose a plan and shows what it
includes. The choice is kept with her preferences (prefs "plan_choice") as
what she asked for; her plan stays "free" (plan_of) until plans are stored
with accounts and paid through a real payment service.

The plan names and what each includes are a proposal (PRODUCT_PLAN.md §3);
the reading plan as a paid feature follows the site-structure brief. Prices
are not decided (PRODUCT_PLAN.md §6, decision 3): the paid price stays None
until they are, and the pages say so instead of showing a number.

Pure functions, no Streamlit."""
from coach import settings

ENFORCED = False
DEFAULT = "free"

PLANS = {
    "free": {"active_goals": 1, "subjects": settings.MAX_SUBJECTS, "reading_plan": False, "certificates": False},
    "plus": {"active_goals": settings.MAX_GOALS, "subjects": settings.MAX_SUBJECTS, "reading_plan": True,
             "certificates": True},
}
NAMES = {"free": "Free", "plus": "Plus"}
BLURBS = {"free": "Learn every day at no cost: our subjects, a goal of your own, review and practice.",
          "plus": "More goals of your own at once, a reading plan, and certificates once they open."}

# a month, in CURRENCY; None: not decided yet (no number is shown before then)
PRICES = {"free": 0, "plus": None}
CURRENCY = "USD"

# what a plan includes, line by line: (feature, label)
FEATURES = (("subjects", "Our subjects"), ("active_goals", "Goals of your own at a time"),
            ("reading_plan", "Reading plan (a book over 14 days)"), ("certificates", "Certificates"))
# what every plan has (never paywalled: PRODUCT_PLAN.md §3)
EVERY_PLAN = ("Daily lessons, each with a quiz", "Spaced review", "Practice and the knowledge map",
              "Streaks, rest days and your weekly summary")
# features a plan names that the site doesn't have yet
NOT_BUILT = {"certificates"}


def known(plan) -> bool:
    return plan in PLANS


def plan_of(config: dict) -> str:
    """Her plan (everyone is on "free" until plans are stored with accounts)."""
    return DEFAULT


def active_goals_allowed(config: dict) -> int:
    """How many of her own goals may be active at once."""
    if not ENFORCED:
        return settings.MAX_GOALS
    return PLANS[plan_of(config)]["active_goals"]


def includes(plan: str, feature: str):
    """What a plan includes of a feature (a number, or True/False)."""
    return PLANS[plan if known(plan) else DEFAULT][feature]


def value_line(plan: str, feature: str) -> str:
    v = includes(plan, feature)
    if isinstance(v, bool):
        line = "Included" if v else "Not included"
    else:
        line = f"Up to {v}"
    return line + (" · not available yet" if v is True and feature in NOT_BUILT else "")


def price_line(plan: str) -> str:
    p = PRICES.get(plan)
    if p == 0:
        return "Free"
    return "Price not set yet" if p is None else f"{CURRENCY} {p:.2f} a month"


def due_today(plan: str) -> int:
    """What she pays when she starts: nothing (there is no payment yet)."""
    return 0
