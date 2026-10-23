"""The unit check in a real browser, at a phone and a desktop width: Home
points to the unit just finished, a set answered wrong is not passed, a
fresh set answered right is, and the course map then says so. No AI call
is made for it (the fake Groq counts every call)."""
import itertools
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import pytest

import flows
from conftest import covers

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import seed_history  # noqa: E402

_n = itertools.count()
D = date(2026, 11, 12)


def text(p):
    return p.page.evaluate("document.body.innerText")


def answer_all(p, right: bool):
    """Every question of the set (seeded: choice questions, "Right" is right)."""
    for group in p.page.get_by_role("radiogroup").all():
        group.get_by_text("Right" if right else "Wrong", exact=True).first.click()
        p.page.wait_for_timeout(60)
    flows.idle(p.page)


@pytest.mark.parametrize("width", [390, 1440])
def test_a_unit_check_from_home_failed_then_passed(public_app, pages, width):
    covers("W-daily-today_unit", "W-unit-uc_check", "W-unit-uc_again", "W-unit-uc_back", "W-course-cm_uc_go")
    app = public_app
    app.set_clock(D, "02:00:00")
    p = pages(width=width)
    email = f"unit{next(_n)}-{int(time.time() * 1000)}@example.com"
    flows.sign_in(p, app, email=email)
    flows.onboard(p, subjects=("Philosophy",), pace="Light")
    app.seed_entries(email, seed_history.build(D, days=6, topics=("philosophy",), gaps=(), partial=()))
    calls = len(app.calls())
    flows.open_app(p, app)
    flows.button(p, "Unit check", exact=False)
    assert flows.wait_text(p.page, "80% passes it")
    answer_all(p, right=False)
    flows.button(p, "Check my answers")
    assert flows.wait_text(p.page, "Not yet") and "You need 80%" in text(p)
    flows.button(p, "Try a new set")
    answer_all(p, right=True)
    flows.button(p, "Check my answers")
    assert flows.wait_text(p.page, "100% · Passed")
    flows.button(p, "Back to the learning map")
    assert flows.wait_text(p.page, "unit check passed · best 100%")
    flows.open_app(p, app)
    assert "Unit check ·" not in text(p), "taken: Home no longer points to it"
    assert len(app.calls()) == calls, "no AI call for a unit check"
    assert "Traceback" not in text(p)
    app.set_clock(None)
