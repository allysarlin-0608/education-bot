"""Supabase Auth (GoTrue) over its REST API, for APP_MODE=public.

Every call is made from the server with the project's publishable (anon)
key; passwords go straight to Supabase and are never logged, stored or
echoed. Failures become AuthError with a short code the UI turns into a
plain message (raw backend text stays in the server log)."""
import base64
import hashlib
import logging
import secrets as pysecrets

import requests

from coach import ui

logger = logging.getLogger("coach.supa_auth")
TIMEOUT = 15


class AuthError(Exception):
    """code: invalid_credentials | email_not_confirmed | weak_password |
    invalid_email | rate_limited | not_invited | exists | link_invalid |
    session_expired | network | failed"""

    def __init__(self, code: str, status: int | None = None):
        super().__init__(code)
        self.code = code
        self.status = status


def _base() -> str:
    return ui.get_setting("SUPABASE_URL").rstrip("/") + "/auth/v1"


def _headers(access_token: str | None = None) -> dict:
    key = ui.get_setting("SUPABASE_KEY")
    h = {"apikey": key, "Content-Type": "application/json"}
    if access_token:
        h["Authorization"] = f"Bearer {access_token}"
    return h


session = requests.Session()


_BY_CODE = {
    "invalid_credentials": "invalid_credentials",
    "email_not_confirmed": "email_not_confirmed",
    "weak_password": "weak_password",
    "email_address_invalid": "invalid_email",
    "validation_failed": "invalid_email",
    "over_email_send_rate_limit": "rate_limited",
    "over_request_rate_limit": "rate_limited",
    "otp_expired": "link_invalid",
    "flow_state_expired": "link_invalid",
    "flow_state_not_found": "link_invalid",
    "bad_code_verifier": "link_invalid",
    "bad_jwt": "session_expired",
    "session_not_found": "session_expired",
    "session_expired": "session_expired",
    "refresh_token_not_found": "session_expired",
    "refresh_token_already_used": "session_expired",
    "user_already_exists": "exists",
    "email_exists": "exists",
}


def _code_for(status: int, body: dict) -> str:
    text = " ".join(str(body.get(k) or "") for k in ("msg", "message", "error", "error_description")).lower()
    if "not_invited" in text:                  # our before-user-created hook
        return "not_invited"
    code = str(body.get("error_code") or "")
    if code in _BY_CODE:
        return _BY_CODE[code]
    if status == 429:
        return "rate_limited"
    if "invalid login" in text:
        return "invalid_credentials"
    if "refresh token" in text:
        return "session_expired"
    if "expired" in text or "invalid" in text:
        return "link_invalid"
    return "failed"


def _call(method: str, path: str, *, json=None, params=None, access_token=None, ok=(200, 201, 204)):
    try:
        resp = session.request(method, _base() + path, json=json, params=params,
                               headers=_headers(access_token), timeout=TIMEOUT)
    except requests.RequestException as e:
        logger.error("supabase auth %s %s unreachable: %s", method, path, e)
        raise AuthError("network") from e
    if resp.status_code not in ok:
        try:
            body = resp.json()
        except ValueError:
            body = {"msg": resp.text[:200]}
        code = _code_for(resp.status_code, body if isinstance(body, dict) else {})
        logger.warning("supabase auth %s %s -> %s (%s)", method, path, resp.status_code, code)
        raise AuthError(code, resp.status_code)
    if resp.status_code == 204 or not resp.content:
        return {}
    return resp.json()


# ---- PKCE ----
def pkce_pair() -> tuple:
    verifier = pysecrets.token_urlsafe(64)[:96]
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def google_authorize_url(redirect_to: str, challenge: str) -> str:
    from urllib.parse import urlencode
    q = urlencode({"provider": "google", "redirect_to": redirect_to,
                   "code_challenge": challenge, "code_challenge_method": "s256"})
    return f"{_base()}/authorize?{q}"


def exchange_code(auth_code: str, verifier: str) -> dict:
    return _call("POST", "/token", params={"grant_type": "pkce"},
                 json={"auth_code": auth_code, "code_verifier": verifier})


# ---- email + password ----
def sign_up(email: str, password: str, redirect_to: str) -> None:
    """Always ends the same way for the caller (no hint whether the email
    was already registered); raises only for problems the person can fix."""
    _call("POST", "/signup", params={"redirect_to": redirect_to},
          json={"email": email, "password": password})


def sign_in(email: str, password: str) -> dict:
    return _call("POST", "/token", params={"grant_type": "password"},
                 json={"email": email, "password": password})


def resend_confirmation(email: str, redirect_to: str) -> None:
    _call("POST", "/resend", params={"redirect_to": redirect_to}, json={"type": "signup", "email": email})


def request_reset(email: str, redirect_to: str) -> None:
    _call("POST", "/recover", params={"redirect_to": redirect_to}, json={"email": email})


def verify_link(token_hash: str, kind: str) -> dict:
    """An emailed link (sign-up confirmation or password reset): its
    token_hash, checked by Supabase, gives a session."""
    if kind not in ("email", "signup", "recovery"):
        raise AuthError("link_invalid")
    return _call("POST", "/verify", json={"type": kind, "token_hash": token_hash})


def set_password(access_token: str, password: str) -> None:
    _call("PUT", "/user", access_token=access_token, json={"password": password})


# ---- session ----
def refresh(refresh_token: str) -> dict:
    return _call("POST", "/token", params={"grant_type": "refresh_token"}, json={"refresh_token": refresh_token})


def get_user(access_token: str) -> dict:
    return _call("GET", "/user", access_token=access_token)


def sign_out(access_token: str) -> None:
    """Revokes this session's refresh token at Supabase."""
    try:
        _call("POST", "/logout", params={"scope": "local"}, access_token=access_token)
    except AuthError:
        pass                            # already gone: signing out locally is what matters


def profile(user: dict) -> dict:
    """The fields the app shows: id, email, name, picture, provider."""
    meta = user.get("user_metadata") or {}
    email = str(user.get("email") or "").strip().lower()
    return {
        "sub": str(user["id"]),
        "email": email,
        "name": str(meta.get("full_name") or meta.get("name") or email.split("@")[0]),
        "picture": str(meta.get("avatar_url") or meta.get("picture") or ""),
        "provider": str((user.get("app_metadata") or {}).get("provider") or "email"),
    }
