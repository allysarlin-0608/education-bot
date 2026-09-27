"""Quick smoke test: `pytest tests/e2e -m smoke`."""
import pytest

import flows
from conftest import covers

pytestmark = pytest.mark.smoke


@pytest.mark.parametrize("mode", ["public", "personal"])
def test_new_person_learns_one_lesson(mode, pages, request):
    covers("W-setup-get_started", "W-daily-start_this_lesson", "W-daily-take_the_quiz", "AI-daily-stream_reply",
           "AI-daily-ask_json", "AI-daily-ask_json-2", "D-setup-save_settings-2", "D-daily-save_entry")
    app = request.getfixturevalue(f"{mode}_app")
    p = pages(width=1440)
    flows.sign_in(p, app, email=f"smoke-{mode}@example.com")
    assert flows.wait_text(p.page, "Get started"), "a new person starts with the setup"
    flows.onboard(p)
    flows.open_app(p, app)
    flows.pass_lesson(p)
    assert flows.wait_text(p.page, "Next lesson"), "passing offers the next lesson"
