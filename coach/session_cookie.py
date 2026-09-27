"""The signed-in session, kept in the browser as Streamlit's own auth cookies.

Streamlit Community Cloud only lets a few cookie names through to the app:
its XSRF cookie and the two it uses for st.login (_streamlit_user,
_streamlit_user_tokens). So the Supabase session travels in exactly those,
written the way Streamlit writes them: HttpOnly, SameSite=Lax, signed with
[auth].cookie_secret (so they can't be forged or edited in the browser).
Streamlit then shows the person as st.user and the access token as
st.user.tokens["access"] ([auth] expose_tokens = "access"); the refresh
token stays in the cookie, read only here on the server.

This leans on Streamlit's internal cookie helpers; streamlit is pinned in
requirements.txt and tests/test_session_cookie.py checks the round trip."""
import json
from urllib.parse import urlparse

from starlette.requests import Request
from starlette.responses import Response
from streamlit.web.server.starlette import starlette_app_utils as _su
from streamlit.web.server.starlette import starlette_auth_routes as _sa
from streamlit.web.server.starlette.starlette_server_config import (
    TOKENS_COOKIE_NAME,
    USER_COOKIE_NAME,
    XSRF_COOKIE_NAME,
)

from coach import ui


# Written into every session this app makes. A cookie without it (e.g. one
# left by Streamlit's own st.login, which uses the same cookie names) is not
# one of ours and counts as no one signed in.
MARK = "gnosis_session"
MARK_VERSION = 1


def app_url() -> str:
    """The app's public address, e.g. https://x.streamlit.app (APP_URL)."""
    return ui.get_setting("APP_URL").rstrip("/")


def origin() -> str:
    p = urlparse(app_url())
    return f"{p.scheme}://{p.netloc}"


def routes_base() -> str:
    """Where this server's own routes are reached from a browser. On
    Streamlit Community Cloud the app itself is served under /~/+/."""
    base = app_url()
    return base + "/~/+" if urlparse(base).netloc.endswith(".streamlit.app") else base


async def write(response: Response, person: dict, session: dict, **flags) -> None:
    """Signed-in: person (supa_auth.profile) and the Supabase session."""
    payload = dict(person, origin=origin(), is_logged_in=True, **{MARK: MARK_VERSION},
                   exp=int(session.get("expires_at") or 0), **flags)
    tokens = {"access_token": session["access_token"], "refresh_token": session["refresh_token"]}
    await _sa._set_auth_cookie(response, payload, tokens)


def clear(response: Response, request: Request) -> None:
    _sa._clear_auth_cookie(response, request)


def read(request: Request):
    """(person, tokens) from a request's cookies, or (None, None)."""
    try:
        raw_user = _sa._get_cookie_value_from_request(request, USER_COOKIE_NAME)
        raw_tokens = _sa._get_cookie_value_from_request(request, TOKENS_COOKIE_NAME)
        if not raw_user or not raw_tokens:
            return None, None
        person, tokens = json.loads(raw_user), json.loads(raw_tokens)
    except (ValueError, UnicodeDecodeError):
        return None, None
    if (not person.get("is_logged_in") or person.get(MARK) != MARK_VERSION or person.get("origin") != origin()
            or not tokens.get("refresh_token")):
        return None, None
    return person, tokens


def read_exp(request: Request) -> int:
    person, _ = read(request)
    return int((person or {}).get("exp") or 0)


def browser_key(cookies) -> bytes | None:
    """This browser's XSRF secret (the same across page loads), used to
    tie a sign-in started here to the browser that finishes it."""
    raw = cookies.get(XSRF_COOKIE_NAME)
    token, _ = _su.decode_xsrf_token_string(raw) if raw else (None, None)
    return token
