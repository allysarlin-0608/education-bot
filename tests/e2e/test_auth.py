"""Accounts (public mode): create an account, confirm, sign in, forget and
reset the password, resend the confirmation, Google, the account menu, and
sign out. Everything against the fake Supabase Auth (tests/fake_supabase.py)."""
import time

import pytest

import flows
from conftest import PASSWORD, covers

NEUTRAL = "If an account can be created with this email, we've sent you a link."


def new_email(tag):
    return f"{tag}-{int(time.time() * 1000)}@example.com"


def invite(app, email):
    app.post("/__seed", {"allowed_users": [{"email": email, "note": ""}]})


def mail_for(app, email, kind=None):
    mails = [m for m in app.get("/__outbox") if m["to"] == email and (kind is None or m["type"] == kind)]
    return mails


def fill(p, label, value, nth=0):
    p.page.get_by_label(label, exact=True).nth(nth).fill(value)


def to_view(p, name):
    flows.button(p, name)


def text(p):
    return p.page.evaluate("document.body.innerText")


@pytest.mark.parametrize("width", [1440, 390])
def test_create_an_account_confirm_and_arrive(public_app, pages, width):
    covers("W-auth-key", "W-auth-su_form", "W-auth-su_email", "W-auth-su_password", "W-auth-su_confirm",
           "W-auth-creating_your_account_if_busy_else_creat", "D-auth-touch_user")
    app = public_app
    email = new_email("signup")
    invite(app, email)
    p = pages(width=width)
    flows.open_app(p, app)
    to_view(p, "Create an account")
    # the rules are checked before anything is sent
    fill(p, "Email", email)
    fill(p, "Password", "short1")
    fill(p, "Confirm password", "short1")
    flows.button(p, "Create account")
    assert flows.wait_text(p.page, "at least 7 characters"), "a too-short password is explained"
    fill(p, "Password", "longenough")
    fill(p, "Confirm password", "longenough")
    flows.button(p, "Create account")
    assert flows.wait_text(p.page, "at least one letter and one number"), "a password without digits is explained"
    fill(p, "Password", PASSWORD)
    fill(p, "Confirm password", PASSWORD + "x")
    flows.button(p, "Create account")
    assert flows.wait_text(p.page, "don't match"), "mismatched passwords are explained"
    assert not mail_for(app, email), "nothing is sent until the form is right"
    fill(p, "Password", PASSWORD)
    fill(p, "Confirm password", PASSWORD)
    flows.button(p, "Create account")
    assert flows.wait_text(p.page, NEUTRAL)
    assert PASSWORD not in p.page.content(), "the password stays out of the page"
    mails = mail_for(app, email, "email")
    assert len(mails) == 1
    p.page.goto(mails[0]["link"])                 # Supabase's default template link
    flows.idle(p.page, 40)
    assert flows.wait_text(p.page, "Get started", 20), "the confirmed person arrives in the app"


def test_sign_up_is_neutral_for_someone_not_invited(public_app, pages):
    covers("W-auth-creating_your_account_if_busy_else_creat")
    app = public_app
    email = new_email("stranger")
    p = pages(width=1440)
    flows.open_app(p, app)
    to_view(p, "Create an account")
    fill(p, "Email", email)
    fill(p, "Password", PASSWORD)
    fill(p, "Confirm password", PASSWORD)
    flows.button(p, "Create account")
    t = text(p)
    assert NEUTRAL in t or "invite-only" in t
    assert not mail_for(app, email)


def test_wrong_password_and_unknown_email_read_the_same(public_app, pages):
    covers("W-auth-si_form", "W-auth-si_email", "W-auth-si_password", "W-auth-signing_in_if_busy_else_sign_in")
    app = public_app
    email = new_email("known")
    app.post("/__user", {"email": email, "password": PASSWORD})
    p = pages(width=1440)
    flows.open_app(p, app)
    msgs = []
    for who, pw in ((email, "wrong password 1"), (new_email("nobody"), "wrong password 1")):
        fill(p, "Email", who)
        fill(p, "Password", pw)
        flows.button(p, "Sign in")
        assert flows.wait_text(p.page, "don't match")
        msgs.append([line for line in text(p).splitlines() if "match" in line])
    assert msgs[0] == msgs[1], "the message must not reveal whether the account exists"


def test_forgot_password_then_sign_in_with_the_new_one(public_app, pages):
    covers("W-auth-fp_form_if_forgot_else_rs_form", "W-auth-fp_email_if_forgot_else_rs_email",
           "W-auth-sending_if_busy_else_label", "W-auth-rp_form", "W-auth-rp_password", "W-auth-rp_confirm",
           "W-auth-saving_if_busy_else_save_new_password")
    app = public_app
    email = new_email("forgot")
    app.post("/__user", {"email": email, "password": PASSWORD})
    p = pages(width=1440)
    flows.open_app(p, app)
    to_view(p, "Forgot password?")
    fill(p, "Email", email)
    flows.button(p, "Send reset link")
    assert flows.wait_text(p.page, NEUTRAL)
    link = mail_for(app, email, "recovery")[-1]["link"]
    p.page.goto(link)
    flows.idle(p.page, 40)
    assert flows.wait_text(p.page, "Set a new password", 20)
    fill(p, "New password", "abcdefg")
    fill(p, "Confirm new password", "abcdefg")
    flows.button(p, "Save new password")
    assert flows.wait_text(p.page, "at least one letter and one number")
    new = "a new pass 9"
    fill(p, "New password", new)
    fill(p, "Confirm new password", new)
    flows.button(p, "Save new password")
    flows.idle(p.page, 40)
    assert flows.wait_text(p.page, "Get started", 20), "after the reset the person is in the app"
    # sign out, then the new password works and the old one doesn't
    p.page.context.clear_cookies()
    flows.open_app(p, app)
    fill(p, "Email", email)
    fill(p, "Password", PASSWORD)
    flows.button(p, "Sign in")
    assert flows.wait_text(p.page, "don't match")
    fill(p, "Email", email)
    fill(p, "Password", new)
    flows.button(p, "Sign in")
    assert flows.wait_text(p.page, "Get started", 20)


def test_an_unconfirmed_account_can_resend_the_link(public_app, pages):
    covers("W-auth-key", "W-auth-fp_form_if_forgot_else_rs_form", "W-auth-fp_email_if_forgot_else_rs_email",
           "W-auth-sending_if_busy_else_label")
    app = public_app
    email = new_email("resend")
    invite(app, email)
    p = pages(width=1440)
    flows.open_app(p, app)
    to_view(p, "Create an account")
    fill(p, "Email", email)
    fill(p, "Password", PASSWORD)
    fill(p, "Confirm password", PASSWORD)
    flows.button(p, "Create account")
    assert flows.wait_text(p.page, NEUTRAL)
    to_view(p, "Back to sign in")
    fill(p, "Email", email)
    fill(p, "Password", PASSWORD)
    flows.button(p, "Sign in")
    assert flows.wait_text(p.page, "confirm your email first")
    to_view(p, "Resend confirmation email")
    assert p.page.get_by_label("Email", exact=True).input_value() == email, "the email is carried over"
    flows.button(p, "Resend confirmation email")
    assert flows.wait_text(p.page, NEUTRAL)
    assert len(mail_for(app, email)) == 2


def test_an_expired_link_says_so_and_offers_a_new_one(public_app, pages):
    covers("W-auth-key")
    app = public_app
    email = new_email("expired")
    invite(app, email)
    p = pages(width=1440)
    flows.open_app(p, app)
    to_view(p, "Create an account")
    fill(p, "Email", email)
    fill(p, "Password", PASSWORD)
    fill(p, "Confirm password", PASSWORD)
    flows.button(p, "Create account")
    assert flows.wait_text(p.page, NEUTRAL)
    app.post("/__expire_link", {})
    p.page.goto(mail_for(app, email)[-1]["link"])
    flows.idle(p.page, 40)
    assert flows.wait_text(p.page, "expired or has already been used", 20)
    assert "Resend confirmation email" in text(p)


def test_google_invited_and_not_invited(public_app, pages):
    covers("W-auth-key")
    app = public_app
    for invited in (True, False):
        email = new_email("google")
        if invited:
            invite(app, email)
        p = pages(width=1440)
        flows.open_app(p, app)
        # followed by the browser itself into the whole window (a script can't, inside Cloud's frame)
        assert p.page.locator("a.si-google").get_attribute("target") == "_top"
        p.page.get_by_text("Continue with Google").click()
        p.page.wait_for_selector("#gemail", timeout=20000)
        p.page.fill("#gemail", email)
        p.page.click("#gcontinue")
        flows.idle(p.page, 40)
        if invited:
            assert flows.wait_text(p.page, "Get started", 20)
        else:
            assert flows.wait_text(p.page, "invite-only", 20)
            assert "Get started" not in text(p)
        p.close()


def test_google_cancel_comes_back_quietly(public_app, pages):
    covers("W-auth-key")
    app = public_app
    p = pages(width=1440)
    flows.open_app(p, app)
    p.page.get_by_text("Continue with Google").click()
    p.page.wait_for_selector("#gcancel", timeout=20000)
    p.page.click("#gcancel")
    flows.idle(p.page, 40)
    assert flows.wait_text(p.page, "Sign in", 20)
    assert "Traceback" not in text(p)


@pytest.mark.parametrize("width", [1440, 390])
def test_account_menu_settings_and_sign_out(public_app, pages, width):
    covers("W-auth-account_menu", "W-auth-views_settings_py", "W-auth-views_account_py")
    app = public_app
    email = new_email("menu")
    p = pages(width=width)
    flows.sign_in(p, app, email=email)
    flows.onboard(p)
    flows.open_app(p, app)
    menu = p.page.locator(".st-key-account_menu button").first
    flows.tap(p, menu)
    assert flows.wait_text(p.page, email, 10), "the menu shows who is signed in"
    flows.tap(p, p.page.get_by_role("link", name="Account").last)
    flows.idle(p.page)
    assert "/account" in p.page.url and flows.wait_text(p.page, email, 10), "her profile"
    flows.tap(p, p.page.locator(".st-key-account_menu button").first)
    flows.tap(p, p.page.get_by_role("link", name="Learning Plan").last)
    flows.idle(p.page)
    assert "/settings" in p.page.url
    assert p.page.get_by_text("Sign out", exact=True).count() == 0, "the menu stays open over the new page"
    flows.tap(p, p.page.locator(".st-key-account_menu button").first)
    flows.tap(p, p.page.get_by_text("Sign out", exact=True).last)
    flows.idle(p.page, 40)
    assert flows.wait_text(p.page, "You've signed out", 20)
    p.page.goto(app.url + "/settings")                  # nothing behind the sign-in once signed out
    flows.idle(p.page, 40)
    assert "Continue with Google" in text(p) and email not in text(p)
