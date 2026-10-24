"""The top of every page at every size (fourth round): the whole Menu is
reachable (it scrolls inside itself when the screen is short), its names
say different things, and the avatar never touches the app's own ⋮ menu."""
import itertools
import time

import pytest

import flows
from conftest import covers

_n = itertools.count()
SIZES = [(360, 640), (390, 560), (390, 844), (768, 1024), (1180, 820), (1440, 900)]


def person(app, pages, width, height, scheme="light"):
    p = pages(width=width, height=height, scheme=scheme)
    flows.sign_in(p, app, email=f"hdr{next(_n)}-{int(time.time() * 1000)}@example.com")
    flows.onboard(p, subjects=("Philosophy", "Astronomy"))
    return p


@pytest.mark.parametrize("width,height", SIZES)
def test_the_whole_menu_is_reachable(public_app, pages, width, height):
    covers("W-topnav-site_menu")
    p = person(public_app, pages, width, height)
    flows.open_menu(p)
    t = p.page.locator(".st-key-site_menu_list").inner_text()
    for name in ("Courses", "Goals & Settings", "Learning Record", "Account"):
        assert name in t, name
    assert "Schedule" not in t and "Your week" not in t, "merged: each thing in one place"
    assert "Learning Path" not in t and "Subjects & Courses" not in t
    last = p.page.locator(".st-key-site_menu_list").get_by_role("link", name="Account").last
    last.scroll_into_view_if_needed()
    box = last.bounding_box()
    assert box and box["y"] >= 0 and box["y"] + box["height"] <= height, f"Account at {box}, screen {height}"
    last.click()
    flows.idle(p.page)
    assert "/account" in p.page.url


@pytest.mark.parametrize("width", [360, 390, 768])
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_the_avatar_keeps_clear_of_the_app_menu(public_app, pages, width, scheme):
    p = person(public_app, pages, width, 844, scheme)
    gap = p.page.evaluate("""() => {
      const a = document.querySelector('.st-key-account_menu button').getBoundingClientRect();
      const m = (document.querySelector('[data-testid="stMainMenu"]') || {getBoundingClientRect: () => ({left: innerWidth})})
                .getBoundingClientRect();
      const bg = getComputedStyle(document.querySelector('.st-key-account_menu button')).backgroundColor;
      return {gap: m.left - a.right, left: document.querySelector('.st-key-topnav').getBoundingClientRect().left, bg};
    }""")
    assert gap["gap"] >= 12, gap
    assert gap["left"] >= 8, gap
    assert gap["bg"] not in ("rgba(0, 0, 0, 0)", "rgb(255, 255, 255)"), "the avatar's circle shows"


@pytest.mark.parametrize("path", ["/settings", "/records"])
def test_no_stray_mark_for_a_page_the_phone_bar_leaves_out(public_app, pages, path):
    p = person(public_app, pages, 390, 844, "dark")
    flows.open_app(p, public_app, path)
    p.page.wait_for_timeout(800)
    shown = p.page.evaluate("""() => { const m = document.querySelector('.st-key-topnav_items > .cx-pill');
      return m ? getComputedStyle(m).opacity : '0'; }""")
    assert float(shown) == 0, "the travelling mark bows out (its page isn't in the phone's bar)"


def test_reading_plan_off_opens_its_switch(public_app, pages):
    """No reading plan yet: the Menu's Reading Plan item lands on the switch
    that turns it on (it once went to the top of Goals & Settings)."""
    p = person(public_app, pages, 390, 844)
    flows.open_menu(p)
    p.page.locator(".st-key-site_menu_list").get_by_role("link", name="Reading Plan · off, set it up").click()
    flows.idle(p.page)
    assert "/settings" in p.page.url and "open=" not in p.page.url
    p.page.wait_for_timeout(1200)
    switch = p.page.get_by_text("Add a 14-day reading plan")
    box = switch.bounding_box()
    assert box and 0 <= box["y"] <= 844, f"the switch is on screen: {box}"
    assert flows.wait_text(p.page, "split over 14 days")


@pytest.mark.parametrize("width", [820, 1024, 1180, 1440])
def test_the_bar_keeps_clear_of_the_sidebar_and_the_app_menu(public_app, pages, width):
    """Beside the open sidebar (a tablet held upright has little room), the bar
    sits over the content, its end clear of the app's ⋮ menu."""
    p = person(public_app, pages, width, 900, "light")
    flows.open_app(p, public_app, "/settings")
    p.page.wait_for_timeout(1200)
    r = p.page.evaluate("""() => {
      const a = document.querySelector('.st-key-account_menu button').getBoundingClientRect();
      const m = document.querySelector('[data-testid="stMainMenu"]').getBoundingClientRect();
      const bar = document.querySelector('.st-key-topnav').getBoundingClientRect();
      const side = document.querySelector('[data-testid="stSidebar"]');
      return {menu: m.left - a.right, side: bar.left - (side ? side.getBoundingClientRect().right : 0)};
    }""")
    assert r["menu"] >= 12 and r["side"] >= 12, r
