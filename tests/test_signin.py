"""Sign-in plumbing: the session cookie (Streamlit's own auth cookies, read
back by Streamlit's own websocket code), the one-time handoff, and the
mapping of Supabase errors to plain messages."""
import asyncio
import json
import time

import pytest
from starlette.requests import Request
from starlette.responses import Response
from streamlit import config
from streamlit.web.server.starlette import starlette_websocket as ws
from streamlit.web.server.starlette.starlette_server_config import TOKENS_COOKIE_NAME, USER_COOKIE_NAME

from coach import auth, routes, session_cookie, supa_auth

APP = "https://gnosis-test.streamlit.app"
PERSON = {"sub": "0b9c-uuid", "email": "a@example.com", "name": "Ann", "picture": "", "provider": "email"}
SESSION = {"access_token": "access-jwt", "refresh_token": "r1", "expires_at": 2_000_000_000}


@pytest.fixture(autouse=True)
def setup(monkeypatch):
    monkeypatch.setenv("APP_URL", APP)
    monkeypatch.setenv("APP_MODE", "public")
    config.set_option("server.cookieSecret", "test-secret-" + "x" * 32)


def _cookies(resp: Response) -> dict:
    out = {}
    for k, v in resp.raw_headers:
        if k == b"set-cookie":
            name, _, rest = v.decode("latin-1").partition("=")
            out[name] = rest.split(";")[0]
    return out


def _request(cookies: dict, path="/", query=b"") -> Request:
    header = "; ".join(f"{k}={v}" for k, v in cookies.items()).encode("latin-1")
    return Request({"type": "http", "method": "GET", "path": path, "query_string": query,
                    "headers": [(b"cookie", header), (b"accept", b"text/html")]})


def test_the_cookie_is_what_streamlit_itself_reads_as_st_user():
    resp = Response()
    asyncio.run(session_cookie.write(resp, PERSON, SESSION))
    cookies = _cookies(resp)
    assert set(cookies) == {USER_COOKIE_NAME, TOKENS_COOKIE_NAME}
    raw = [v.decode() for k, v in resp.raw_headers if k == b"set-cookie"]
    assert all("HttpOnly" in c and "SameSite=lax" in c for c in raw)
    assert "access-jwt" not in "".join(raw) or all("." in c for c in raw)      # signed, not plain
    # Streamlit's websocket code turns it into st.user, with the access token exposed
    user = ws._parse_decoded_user_cookie(ws._get_signed_cookie_with_chunks(cookies, USER_COOKIE_NAME), APP)
    assert user["is_logged_in"] is True and user["sub"] == "0b9c-uuid" and user["email"] == "a@example.com"
    tokens = json.loads(ws._get_signed_cookie_with_chunks(cookies, TOKENS_COOKIE_NAME))
    assert tokens == {"access_token": "access-jwt", "refresh_token": "r1"}
    # and the server reads it back
    person, toks = session_cookie.read(_request(cookies))
    assert person["sub"] == "0b9c-uuid" and toks["refresh_token"] == "r1"


def test_an_edited_cookie_is_not_accepted():
    resp = Response()
    asyncio.run(session_cookie.write(resp, PERSON, SESSION))
    cookies = _cookies(resp)
    cookies[USER_COOKIE_NAME] = cookies[USER_COOKIE_NAME].replace("a", "b", 1)
    assert session_cookie.read(_request(cookies)) == (None, None)
    assert ws._get_signed_cookie_with_chunks(cookies, USER_COOKIE_NAME) is None


def test_a_cookie_for_another_site_is_not_accepted(monkeypatch):
    resp = Response()
    asyncio.run(session_cookie.write(resp, PERSON, SESSION))
    monkeypatch.setenv("APP_URL", "https://other.streamlit.app")
    assert session_cookie.read(_request(_cookies(resp))) == (None, None)


def test_routes_live_under_the_cloud_prefix():
    assert session_cookie.routes_base() == APP + "/~/+"


def test_handoff_is_single_use_and_bound_to_the_browser(monkeypatch):
    monkeypatch.setattr(session_cookie, "browser_key", lambda cookies: cookies.get("_streamlit_xsrf", "").encode() or None)
    url = routes.handoff(PERSON, SESSION, b"browser-1")
    key = url.split("h=")[1]
    assert "access-jwt" not in url and "r1" not in url             # no token in the address
    # opened in a different browser: refused
    resp = asyncio.run(routes._session(_request({"_streamlit_xsrf": "browser-2"}, query=f"h={key}".encode())))
    assert "auth_error=expired" in resp.headers["location"] and USER_COOKIE_NAME not in _cookies(resp)
    # the key was spent by that attempt too
    url = routes.handoff(PERSON, SESSION, b"browser-1")
    key = url.split("h=")[1]
    ok = asyncio.run(routes._session(_request({"_streamlit_xsrf": "browser-1"}, query=f"h={key}".encode())))
    assert ok.headers["location"] == APP + "/" and USER_COOKIE_NAME in _cookies(ok)
    again = asyncio.run(routes._session(_request({"_streamlit_xsrf": "browser-1"}, query=f"h={key}".encode())))
    assert "auth_error=expired" in again.headers["location"]


def test_handoff_expires(monkeypatch):
    monkeypatch.setattr(session_cookie, "browser_key", lambda cookies: b"b")
    url = routes.handoff(PERSON, SESSION, b"b")
    real = time.time
    monkeypatch.setattr(time, "time", lambda: real() + routes.HANDOFF_SECONDS + 5)
    resp = asyncio.run(routes._session(_request({}, query=f"h={url.split('h=')[1]}".encode())))
    assert "auth_error=expired" in resp.headers["location"]


def test_google_callback_errors_become_notes():
    cancel = asyncio.run(routes._callback(_request({}, query=b"error=access_denied&flow=x")))
    assert cancel.headers["location"].endswith("?auth_error=google")
    refused = asyncio.run(routes._callback(_request({}, query=b"error=server_error&error_description=not_invited")))
    assert refused.headers["location"].endswith("?auth=invite")
    unknown = asyncio.run(routes._callback(_request({}, query=b"code=abc&flow=nope")))
    assert unknown.headers["location"].endswith("?auth_error=google")


def test_signout_clears_the_cookie(monkeypatch):
    revoked = []
    monkeypatch.setattr(supa_auth, "sign_out", revoked.append)
    resp = Response()
    asyncio.run(session_cookie.write(resp, PERSON, SESSION))
    out = asyncio.run(routes._signout(_request(_cookies(resp))))
    assert revoked == ["access-jwt"]
    cleared = [v.decode() for k, v in out.raw_headers if k == b"set-cookie"]
    assert any(c.startswith(USER_COOKIE_NAME + "=") and "Max-Age=0" in c for c in cleared)


def test_refresh_on_page_load_rotates_the_cookie(monkeypatch):
    monkeypatch.setattr(supa_auth, "refresh", lambda rt: {**SESSION, "refresh_token": "r2",
                                                          "expires_at": int(time.time()) + 3600,
                                                          "user": {"id": "0b9c-uuid", "email": "a@example.com"}})
    resp = Response()
    asyncio.run(session_cookie.write(resp, PERSON, dict(SESSION, expires_at=int(time.time()) + 60)))
    extra = asyncio.run(routes.RefreshSession(None)._renewed(_request(_cookies(resp))))
    new = {}
    for _, v in extra:
        name, _, rest = v.decode().partition("=")
        new[name] = rest.split(";")[0]
    assert json.loads(ws._get_signed_cookie_with_chunks(new, TOKENS_COOKIE_NAME))["refresh_token"] == "r2"


def test_no_refresh_when_plenty_of_time_is_left(monkeypatch):
    monkeypatch.setattr(supa_auth, "refresh", lambda rt: pytest.fail("renewed too early"))
    resp = Response()
    asyncio.run(session_cookie.write(resp, PERSON, dict(SESSION, expires_at=int(time.time()) + 3000)))
    assert asyncio.run(routes.RefreshSession(None)._renewed(_request(_cookies(resp)))) == []


def test_routes_do_nothing_in_personal_mode(monkeypatch):
    monkeypatch.setenv("APP_MODE", "personal")
    resp = asyncio.run(routes._public_only(routes._google)(_request({})))
    assert resp.status_code == 404


@pytest.mark.parametrize("status,body,code", [
    (400, {"error_code": "invalid_credentials", "msg": "Invalid login credentials"}, "invalid_credentials"),
    (400, {"error_code": "email_not_confirmed"}, "email_not_confirmed"),
    (422, {"error_code": "weak_password"}, "weak_password"),
    (429, {"error_code": "over_email_send_rate_limit"}, "rate_limited"),
    (403, {"error_code": "otp_expired"}, "link_invalid"),
    (400, {"error_code": "refresh_token_already_used"}, "session_expired"),
    (403, {"error_code": "hook_error", "msg": "not_invited"}, "not_invited"),
    (500, {"msg": "database error: relation x"}, "failed"),
])
def test_supabase_errors_become_short_codes(status, body, code):
    assert supa_auth._code_for(status, body) == code


def test_messages_never_include_backend_text():
    for text in auth.ERRORS.values():
        assert "supabase" not in text.lower() and "error" not in text.lower()


@pytest.mark.parametrize("pw,good", [("abc1234", True), ("correct horse 1", True), ("abcdefgh", False),
                                     ("12345678", False), ("ab12", False), ("", False)])
def test_password_rule_matches_supabase_settings(pw, good):
    assert auth.password_ok(pw) is good
    assert "letters and numbers" in auth.PASSWORD_RULE
