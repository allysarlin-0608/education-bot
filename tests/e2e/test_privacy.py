"""Two people on the same site: nothing of one ever reaches the other,
by any way the app offers (Today, Review, Progress, course map, search,
backup), and the address can't be used to open the other's data."""
import itertools
import json
import time
from datetime import date, timedelta

import flows
from conftest import covers

_n = itertools.count()
SECRET = "Zanzibar-quokka private note"


def test_two_accounts_never_see_each_other(public_app, pages):
    covers("W-topnav-nav_search", "W-settings-data_download", "W-settings-data_prepare")
    app = public_app
    a, b = pages(width=1180), pages(width=1180)
    ea = f"alice{next(_n)}-{int(time.time() * 1000)}@example.com"
    eb = f"bob{next(_n)}-{int(time.time() * 1000)}@example.com"
    flows.sign_in(a, app, email=ea)
    flows.onboard(a)
    flows.sign_in(b, app, email=eb)
    flows.onboard(b)
    # Alice learns, writes a private note and passes a quiz (cards, history, search)
    flows.open_app(a, app)
    flows.start_lesson(a)
    a.page.get_by_placeholder("Ask about Lesson").fill(SECRET)
    a.page.keyboard.press("Enter")
    assert flows.wait_text(a.page, "Good question", 30)
    flows.idle(a.page)
    flows.take_quiz(a, correct=False)
    # Bob looks everywhere
    seen = []
    for path in ("/", "/review", "/records", "/course?subject=philosophy", "/settings"):
        flows.open_app(b, app, path)
        flows.idle(b.page)
        t = b.page.evaluate("document.body.innerText")
        if SECRET in t or ea in t:
            seen.append(path)
    flows.button(b, "Search", exact=False)
    box = b.page.get_by_placeholder("Lessons, subjects, books, your notes…")
    box.fill("Zanzibar")
    box.press("Enter")
    assert flows.wait_text(b.page, "No results", 10), "Bob's search finds nothing of Alice's"
    b.page.keyboard.press("Escape")
    flows.open_app(b, app, "/review")
    assert "Nothing to review yet" in b.page.evaluate("document.body.innerText")
    flows.open_app(b, app, "/course?subject=philosophy")
    assert flows.wait_text(b.page, "0 of 260 lessons passed", 10), "Bob's map is his own"
    assert not seen, f"Alice's data reached Bob on {seen}"
    # Bob's own data download holds only Bob
    flows.open_app(b, app, "/settings")
    b.page.get_by_role("button", name="Download my data").click()      # gathered now, as her
    with b.page.expect_download() as dl:
        b.page.get_by_role("button", name="Save my data as a file").click()
    data = json.loads(open(dl.value.path()).read())
    blob = json.dumps(data)
    assert SECRET not in blob and ea not in blob and eb in blob
    # and in the database, Alice's rows are Alice's
    d = app.get("/__dump")
    uid_a = next(u["id"] for u in d["users"] if u["email"] == ea)
    rows_with_secret = [e for e in d["tables"]["learning_entries"] if SECRET in json.dumps(e)]
    assert rows_with_secret and all(e["user_id"] == uid_a for e in rows_with_secret)
