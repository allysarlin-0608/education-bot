"""HTTP routes served beside the Streamlit app (st.App, streamlit_app.py).

Sign-in has steps a Streamlit script can't do (write an HttpOnly cookie, read
a link before the page loads), so they happen here, on the server:

  /auth/google    start Google sign-in (PKCE: the verifier never leaves the server)
  /auth/callback  Supabase sends the browser back here with a one-time code
  /auth/confirm   links in our emails (sign-up confirmation, password reset)
  /auth/session   a sign-in done on the page (email + password) becomes the cookie
  /auth/signout   revoke the session at Supabase, clear the cookie

Every route ends by redirecting to the app with a clean address: tokens are
never put in a URL. A small note (?auth=… or ?auth_error=…) says what
happened; the page reads it and removes it at once.

RefreshSession (middleware) renews the session on page loads, the only time
the cookie can be rewritten (see session_cookie.py)."""
import logging
import secrets
import threading
import time
from urllib.parse import quote

from starlette.concurrency import run_in_threadpool
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from starlette.routing import Route

from coach import session_cookie, supa_auth

logger = logging.getLogger("coach.routes")

FLOW_SECONDS = 600        # to finish Google sign-in
EMAIL_SECONDS = 3600      # an emailed link (Supabase's link expiry is an hour)
HANDOFF_SECONDS = 60      # from a sign-in on the page to its cookie
REFRESH_BEFORE = 600      # renew when less than 10 minutes are left

_lock = threading.Lock()
_flows: dict = {}         # Google sign-ins under way: id -> (verifier, browser, expires)
_handoffs: dict = {}      # page sign-ins waiting for their cookie: id -> (…, expires)
_email_flows: dict = {}   # emailed links on their way: id -> (verifier, kind, expires)


def _put(store: dict, value: tuple, seconds: int) -> str:
    key = secrets.token_urlsafe(24)
    now = time.time()
    with _lock:
        for k in [k for k, v in store.items() if v[-1] < now]:
            del store[k]
        store[key] = (*value, now + seconds)
    return key


def _take(store: dict, key):
    """The entry, once only, if it hasn't expired."""
    with _lock:
        entry = store.pop(key or "", None)
    return entry if entry and entry[-1] >= time.time() else None


def _to_app(note: str = "") -> RedirectResponse:
    resp = RedirectResponse(session_cookie.app_url() + "/" + (f"?{note}" if note else ""), status_code=303)
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["Referrer-Policy"] = "no-referrer"
    return resp


def _error_note(e: supa_auth.AuthError, default: str) -> str:
    if e.code == "not_invited":
        return "auth=invite"
    if e.code == "network":
        return "auth_error=network"
    return f"auth_error={default}"


# ---- the page's side: a sign-in done in the script becomes a cookie ----
def handoff(person, session, browser, **flags) -> str:
    """Called by the page after an email+password sign-in (or a password
    change, with person and session None: keep the session, change flags):
    the address to send the browser to. It carries only a random
    one-time key, good for a minute, and only for this browser."""
    key = _put(_handoffs, (person, session, flags, browser), HANDOFF_SECONDS)
    return f"{session_cookie.routes_base()}/auth/session?h={quote(key)}"


async def _session(request: Request):
    entry = _take(_handoffs, request.query_params.get("h"))
    if not entry:
        return _to_app("auth_error=expired")
    person, session, flags, browser, _ = entry
    if browser is None or browser != session_cookie.browser_key(request.cookies):
        logger.warning("sign-in handoff opened in a different browser; refused")
        return _to_app("auth_error=expired")
    if session is None:                  # same session, new flags (e.g. password just changed)
        person, tokens = session_cookie.read(request)
        if not person:
            return _to_app("auth_error=expired")
        person = {k: person[k] for k in ("sub", "email", "name", "picture", "provider") if k in person}
        session = dict(tokens, expires_at=session_cookie.read_exp(request))
    flags = dict(flags)
    note = flags.pop("note", "")
    resp = _to_app(note)
    await session_cookie.write(resp, person, session, **flags)
    return resp


# ---- Google ----
async def _google(request: Request):
    browser = session_cookie.browser_key(request.cookies)
    if browser is None:                   # the page was never loaded in this browser
        return _to_app()
    verifier, challenge = supa_auth.pkce_pair()
    flow = _put(_flows, (verifier, browser), FLOW_SECONDS)
    back = f"{session_cookie.routes_base()}/auth/callback?flow={quote(flow)}"
    resp = RedirectResponse(supa_auth.google_authorize_url(back, challenge), status_code=303)
    resp.headers["Cache-Control"] = "no-store"
    return resp


async def _callback(request: Request):
    q = request.query_params
    entry = _take(_flows, q.get("flow"))
    if q.get("error"):
        why = f"{q.get('error')} {q.get('error_description', '')}".lower()
        logger.warning("google sign-in came back with an error: %s", why[:200])
        return _to_app("auth=invite" if "not_invited" in why else "auth_error=google")
    if not entry or not q.get("code"):
        return _to_app("auth_error=google")
    verifier, browser, _ = entry
    if browser != session_cookie.browser_key(request.cookies):
        logger.warning("google sign-in finished in a different browser; refused")
        return _to_app("auth_error=google")
    try:
        session = await run_in_threadpool(supa_auth.exchange_code, q["code"], verifier)
    except supa_auth.AuthError as e:
        return _to_app(_error_note(e, "google"))
    resp = _to_app()
    await session_cookie.write(resp, supa_auth.profile(session["user"]), session)
    return resp


# ---- links in our emails ----
def email_flow(kind: str) -> tuple:
    """For an email about to be sent (kind "signup" or "recovery"): where its
    link should come back to, and the PKCE challenge to send with it. The
    verifier stays here; the link may be opened on another device (a phone),
    so it isn't tied to this browser — the link itself is the secret."""
    verifier, challenge = supa_auth.pkce_pair()
    key = _put(_email_flows, (verifier, kind), EMAIL_SECONDS)
    return f"{session_cookie.routes_base()}/auth/confirm?flow={quote(key)}", challenge


async def _confirm(request: Request):
    """An emailed link lands here, in one of two forms:
    - Supabase's default email: after Supabase checks it, ?flow=…&code=…
      (PKCE), exchanged here with the verifier kept by email_flow();
    - our own template (needs custom SMTP): ?token_hash=…&type=…, verified here."""
    q = request.query_params
    if q.get("code"):
        entry = _take(_email_flows, q.get("flow"))
        if not entry:              # older than an hour, or the app restarted since it was sent
            return _to_app("auth_error=link_unknown")
        verifier, kind, _ = entry
        try:
            session = await run_in_threadpool(supa_auth.exchange_code, q["code"], verifier)
        except supa_auth.AuthError as e:
            return _to_app(_error_note(e, "link"))
    elif q.get("token_hash"):
        kind = q.get("type", "")
        if kind not in ("email", "signup", "recovery"):
            return _to_app("auth_error=link")
        try:
            session = await run_in_threadpool(supa_auth.verify_link, q["token_hash"], kind)
        except supa_auth.AuthError as e:
            return _to_app(_error_note(e, "link"))
    else:                          # Supabase refused the link (expired, used) — or sent no code
        _take(_email_flows, q.get("flow"))
        return _to_app("auth_error=link")
    if not session.get("access_token"):
        return _to_app("auth_error=link")
    recovery = kind == "recovery"
    resp = _to_app("auth=reset" if recovery else "auth=confirmed")
    await session_cookie.write(resp, supa_auth.profile(session["user"]), session, recovery=recovery)
    return resp


# ---- sign out ----
async def _signout(request: Request):
    person, tokens = session_cookie.read(request)
    if tokens:
        await run_in_threadpool(supa_auth.sign_out, tokens["access_token"])
    why = request.query_params.get("why")
    resp = _to_app("auth=deleted" if why == "deleted" else "auth=signed_out")
    session_cookie.clear(resp, request)
    return resp


def _public_only(handler):
    """A personal app (APP_MODE unset or "personal") has no such pages."""
    async def route(request: Request):
        from coach import auth
        if not auth.is_public() or not session_cookie.app_url():
            return Response("Not found", status_code=404)
        return await handler(request)
    return route


def all_routes() -> list:
    return [
        Route("/auth/google", _public_only(_google)),
        Route("/auth/callback", _public_only(_callback)),
        Route("/auth/confirm", _public_only(_confirm)),
        Route("/auth/session", _public_only(_session)),
        Route("/auth/signout", _public_only(_signout)),
    ]


# ---- keeping the session fresh ----
_NOT_PAGES = ("/_stcore", "/static", "/auth/", "/component", "/media", "/app/static", "/-/")


class RefreshSession:
    """On a page load (the HTML, not its scripts or the websocket), renew the
    session when it is close to expiring and write the new cookie into the
    response. Supabase issues a new refresh token each time, so this is the
    one place renewal happens; the page itself never renews."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] != "GET" or scope["path"].startswith(_NOT_PAGES):
            return await self.app(scope, receive, send)
        request = Request(scope)
        if "text/html" not in request.headers.get("accept", ""):
            return await self.app(scope, receive, send)
        extra = await self._renewed(request)
        if not extra:
            return await self.app(scope, receive, send)

        async def send_with_cookies(message):
            if message["type"] == "http.response.start":
                message = dict(message, headers=list(message.get("headers", [])) + extra)
            await send(message)

        return await self.app(scope, receive, send_with_cookies)

    async def _renewed(self, request: Request) -> list:
        from coach import auth
        if not auth.is_public():
            return []
        person, tokens = session_cookie.read(request)
        if not person or person.get("exp", 0) - time.time() > REFRESH_BEFORE:
            return []
        holder = Response()
        try:
            session = await run_in_threadpool(supa_auth.refresh, tokens["refresh_token"])
        except supa_auth.AuthError as e:
            if e.code == "network":
                return []                          # try again on the next load
            session_cookie.clear(holder, request)   # ended at Supabase: signed out here too
            return [(k, v) for k, v in holder.raw_headers if k == b"set-cookie"]
        flags = {k: person[k] for k in ("recovery",) if person.get(k)}
        await session_cookie.write(holder, supa_auth.profile(session["user"]), session, **flags)
        return [(k, v) for k, v in holder.raw_headers if k == b"set-cookie"]


def middleware() -> list:
    return [Middleware(RefreshSession)]
