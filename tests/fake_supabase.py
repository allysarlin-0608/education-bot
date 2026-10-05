"""A stand-in for a Supabase project, for tests only: its database as
PostgREST serves it (FakeDB, with the row level security of
supabase/accounts.sql) and, run as a server (python tests/fake_supabase.py),
its Auth API too, with a pretend Google and an outbox instead of email.

Not a security boundary of anything real: it only lets the app be driven end
to end without a real project."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from coach import storage  # noqa: E402

URL = "https://abc.supabase.co"
KEY = "sb_publishable_test"

# table -> its primary key, after multiuser.sql + accounts.sql
SCHEMA = {
    storage.TABLE: ("user_id", "date", "topic"),
    storage.BOOKS_TABLE: ("user_id", "id"),
    storage.SETTINGS_TABLE: ("user_id",),
    storage.USERS_TABLE: ("user_id",),
    storage.INVITES_TABLE: ("email",),
    storage.USAGE_TABLE: ("user_id", "date"),
    storage.ADMINS_TABLE: ("email",),
    storage.PATHS_TABLE: ("user_id", "id"),            # goals.sql
    storage.EVENTS_TABLE: ("user_id", "day", "event"),
    storage.SIGNALS_TABLE: ("user_id", "day", "event"),
    storage.PREFS_TABLE: ("user_id",),                 # goals.sql (habits)
}
USER_TABLES = [t for t in SCHEMA if t not in (storage.INVITES_TABLE, storage.ADMINS_TABLE)]
OWN_ROWS = [storage.TABLE, storage.BOOKS_TABLE, storage.SETTINGS_TABLE, storage.USERS_TABLE, storage.PATHS_TABLE,
            storage.PREFS_TABLE]


class Resp:
    def __init__(self, status_code=200, data=None):
        self.status_code, self._data = status_code, data
        self.text = "" if data is None else str(data)

    def json(self):
        return self._data


def _match(row, params):
    for col, cond in (params or {}).items():
        if col in ("select", "order", "limit", "on_conflict"):
            continue
        op, _, val = cond.partition(".")
        have = "" if row.get(col) is None else str(row.get(col))
        if op == "eq" and have != val:
            return False
        if op == "neq" and have == val:
            return False
        if op == "gte" and not have >= val:
            return False
    return True


RLS_DENIED = Resp(403, {"code": "42501", "message": "new row violates row-level security policy"})


class FakeDB:
    """In-memory tables plus the functions, as PostgREST serves them. The
    caller is whoever the bearer token says ("tok|<user id>|<email>")."""

    def __init__(self, rls=True):
        self.rls = rls
        self.tables = {t: {} for t in SCHEMA}
        self.auth_users = set()
        self.fail_delete_at = None           # to show delete_my_account is all-or-nothing

    @staticmethod
    def _caller(headers):
        token = headers.get("Authorization", "").removeprefix("Bearer ")
        if not token.startswith("tok|"):
            return None, ""
        _, uid, email = token.split("|")[:3]
        return uid, email.lower()

    def _admin(self, email):
        return (email,) in self.tables[storage.ADMINS_TABLE]

    def _visible(self, name, row, uid, email):
        if not self.rls:
            return True
        if name in USER_TABLES:
            return row.get("user_id") == uid
        if name == storage.INVITES_TABLE:
            return row["email"] == email or self._admin(email)
        return row["email"] == email          # app_admins: your own row

    def request(self, method, url, params=None, json=None, headers=None, timeout=None):
        assert headers["apikey"] == KEY and timeout
        uid, email = self._caller(headers)
        if self.rls and uid is None:
            return Resp(401, {"message": "JWT required"})
        name = url.removeprefix(f"{URL}/rest/v1/")
        if name.startswith("rpc/"):
            return self.rpc(name[4:], json, uid, email)
        table, pk = self.tables[name], SCHEMA[name]
        if method == "GET":
            rows = [r for r in table.values() if _match(r, params) and self._visible(name, r, uid, email)]
            cols = params.get("select", "*")
            if cols != "*":
                rows = [{c: r.get(c) for c in cols.split(",")} for r in rows]
            return Resp(200, rows)
        if method == "POST":
            if tuple(params["on_conflict"].split(",")) != pk:
                return Resp(400, {"code": "42P10", "message": "no unique constraint matching the ON CONFLICT"})
            for row in json:
                if any(row.get(c) in (None, "") for c in pk):
                    return Resp(400, {"code": "23502", "message": f"null value in {pk} of {name}"})
                if self.rls and (
                        (name in OWN_ROWS and row["user_id"] != uid)
                        or name in (storage.USAGE_TABLE, storage.EVENTS_TABLE)   # only their functions write
                        or name == storage.ADMINS_TABLE
                        or (name == storage.INVITES_TABLE and not self._admin(email))):
                    return RLS_DENIED
            for row in json:
                key = tuple(str(row[c]) for c in pk)
                table[key] = {**table.get(key, {}), **row}
            return Resp(201)
        if method == "DELETE":
            if not any(k not in ("select", "order") for k in params or {}):
                return Resp(400, {"message": "DELETE requires a WHERE clause"})
            for key in [k for k, r in table.items() if _match(r, params)]:
                row = table[key]
                if self.rls and not (
                        (name in OWN_ROWS and row["user_id"] == uid)
                        or (name == storage.INVITES_TABLE and self._admin(email))):
                    continue                  # RLS: rows you may not delete are simply not matched
                del table[key]
            return Resp(204)
        raise AssertionError(method)

    def rpc(self, fn, args, uid, email=""):
        if uid is None:
            return Resp(400, {"message": "not signed in"})
        if fn == "add_ai_usage":
            assert set(args) == {"p_date", "p_requests", "p_tokens"}   # no user id: the function uses auth.uid()
            key = (uid, args["p_date"])
            row = self.tables[storage.USAGE_TABLE].setdefault(
                key, {"user_id": uid, "date": args["p_date"], "request_count": 0, "token_count": 0})
            row["request_count"] += max(args["p_requests"], 0)
            row["token_count"] += max(args["p_tokens"], 0)
            return Resp(204)
        if fn == "add_usage_event":
            assert set(args) == {"p_event"}             # the function uses auth.uid() and the server's date
            from datetime import datetime
            from coach import metrics
            day = datetime.now(metrics.TZ).date().isoformat()
            key = (uid, day, args["p_event"])
            row = self.tables[storage.EVENTS_TABLE].setdefault(
                key, {"user_id": uid, "day": day, "event": args["p_event"], "count": 0})
            row["count"] = 1 if args["p_event"] == "visit" else row["count"] + 1
            return Resp(204)
        if fn == "add_learning_signal":
            assert set(args) == {"p_event"}
            from datetime import datetime
            from coach import metrics
            assert args["p_event"] in metrics.SIGNALS
            day = datetime.now(metrics.TZ).date().isoformat()
            key = (uid, day, args["p_event"])
            row = self.tables[storage.SIGNALS_TABLE].setdefault(
                key, {"user_id": uid, "day": day, "event": args["p_event"], "count": 0})
            row["count"] += 1
            return Resp(204)
        if fn == "gnosis_metrics":
            if not self._admin(email):
                return Resp(400, {"message": "admins only"})
            from datetime import date, datetime
            from coach import metrics
            today = datetime.now(metrics.TZ).date()
            return Resp(200, metrics.summarize(list(self.tables[storage.USERS_TABLE].values()),
                                               list(self.tables[storage.EVENTS_TABLE].values())
                                               + list(self.tables[storage.SIGNALS_TABLE].values()),
                                               date.fromisoformat(args["p_since"]), today))
        if fn == "delete_my_account":
            assert args == {}
            snapshot = {t: dict(rows) for t, rows in self.tables.items()}
            for t in USER_TABLES:
                if t == self.fail_delete_at:
                    self.tables = snapshot                    # rolled back
                    return Resp(500, {"message": "boom"})
                for key in [k for k, r in self.tables[t].items() if r.get("user_id") == uid]:
                    del self.tables[t][key]
            self.auth_users.discard(uid)
            return Resp(204)
        raise AssertionError(fn)




# ============================================================================
# The Auth API (GoTrue) and PostgREST over HTTP: python tests/fake_supabase.py
# ============================================================================
import base64  # noqa: E402
import hashlib  # noqa: E402
import os  # noqa: E402
import secrets  # noqa: E402
import time  # noqa: E402
import uuid  # noqa: E402
from urllib.parse import urlencode  # noqa: E402

MIN_PASSWORD = 7


def _strong(p):
    """As the test project is set up: at least 7, letters and digits."""
    return len(p) >= MIN_PASSWORD and any(c.isalpha() for c in p) and any(c.isdigit() for c in p)


class FakeAuth:
    def __init__(self, db: FakeDB, access_ttl: int):
        self.db = db
        self.ttl = access_ttl
        self.users = {}          # email -> {id, email, password_hash|None, confirmed, providers, meta}
        self.refresh = {}        # refresh token -> (user id, used?)
        self.access = {}         # access token -> (user id, expires)
        self.links = {}          # token_hash -> (email, kind, expires)
        self.codes = {}          # PKCE auth code -> (user id, challenge)
        self.outbox = []         # the emails "sent"
        self.password_log = []   # nothing may ever put a password here (checked by tests)

    # ---- helpers
    @staticmethod
    def _hash(p):
        return hashlib.sha256(("salt" + p).encode()).hexdigest()

    def _invited(self, email):
        return ((email,) in self.db.tables[storage.INVITES_TABLE]) or ((email,) in self.db.tables[storage.ADMINS_TABLE])

    def _user_json(self, u):
        return {"id": u["id"], "email": u["email"], "user_metadata": u["meta"],
                "app_metadata": {"provider": u["providers"][0] if u["providers"] else "email",
                                 "providers": u["providers"]},
                "identities": [{"provider": p} for p in u["providers"]]}

    def _session(self, u):
        access = f"tok|{u['id']}|{u['email']}|{secrets.token_hex(6)}"
        refresh = secrets.token_urlsafe(9)
        exp = int(time.time()) + self.ttl
        self.access[access] = (u["id"], exp)
        self.refresh[refresh] = (u["id"], False)
        self.db.auth_users.add(u["id"])
        return {"access_token": access, "refresh_token": refresh, "expires_in": self.ttl, "expires_at": exp,
                "token_type": "bearer", "user": self._user_json(u)}

    def _by_id(self, uid):
        return next((u for u in self.users.values() if u["id"] == uid), None)

    def _mail(self, email, kind, redirect_to, challenge="", base=""):
        """Supabase's default template: a link to its own /verify, which
        checks the token and sends the browser on to redirect_to (with
        ?code=… when the request carried a PKCE challenge). custom_link is
        what our own template would send instead (token_hash)."""
        th = secrets.token_hex(16)
        self.links[th] = (email, kind, time.time() + 3600, challenge, redirect_to)
        sep = "&" if "?" in redirect_to else "?"
        self.outbox.append({"to": email, "type": kind,
                            "link": f"{base}/auth/v1/verify?" + urlencode({"token": th, "type": kind,
                                                                          "redirect_to": redirect_to}),
                            "custom_link": f"{redirect_to}{sep}token_hash={th}&type={kind}"})

    def user_for(self, access):
        entry = self.access.get(access)
        if not entry or entry[1] < time.time() or self._by_id(entry[0]) is None:
            return None
        return self._by_id(entry[0])

    def new_user(self, email, password=None, provider="email", meta=None):
        u = {"id": str(uuid.uuid4()), "email": email, "password": self._hash(password) if password else None,
             "confirmed": provider != "email", "providers": [provider], "meta": meta or {}}
        self.users[email] = u
        return u


def _err(status, code, msg=""):
    from starlette.responses import JSONResponse
    return JSONResponse({"code": status, "error_code": code, "msg": msg or code}, status_code=status)


def build_app(access_ttl=3600):
    from starlette.applications import Starlette
    from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
    from starlette.routing import Route

    db = FakeDB(rls=True)
    auth = FakeAuth(db, access_ttl)

    def key_ok(request):
        return request.headers.get("apikey") == KEY

    def base(request):
        return str(request.base_url).rstrip("/")

    async def verify_get(request):
        """The default email link: check it, then on to redirect_to."""
        q = request.query_params
        entry = auth.links.pop(q.get("token", ""), None)
        back = q.get("redirect_to", "")
        sep = "&" if "?" in back else "?"
        if not entry or entry[2] < time.time():
            return RedirectResponse(back + sep + urlencode({"error": "access_denied", "error_code": "otp_expired",
                                                            "error_description": "Email link is invalid or has expired"}), 303)
        email, kind, _, challenge, _ = entry
        u = auth.users.get(email)
        if not u:
            return RedirectResponse(back + sep + "error=access_denied", 303)
        u["confirmed"] = True
        if not challenge:            # implicit flow: tokens after '#', which a server never sees
            s = auth._session(u)
            return RedirectResponse(back + "#" + urlencode({"access_token": s["access_token"],
                                                            "refresh_token": s["refresh_token"]}), 303)
        code = secrets.token_hex(12)
        auth.codes[code] = (u["id"], challenge)
        return RedirectResponse(back + sep + urlencode({"code": code}), 303)

    async def signup(request):
        if not key_ok(request):
            return _err(401, "no_api_key")
        body = await request.json()
        email = str(body.get("email", "")).strip().lower()
        password = str(body.get("password", ""))
        if "@" not in email:
            return _err(400, "email_address_invalid")
        if not _strong(password):
            return _err(422, "weak_password", "Password should contain letters and digits.")
        u = auth.users.get(email)
        if u:                                     # already registered: same answer, no user made
            if not u["confirmed"]:
                auth._mail(email, "email", request.query_params.get("redirect_to", ""),
                           body.get("code_challenge", ""), base(request))
            return JSONResponse({"id": str(uuid.uuid4()), "email": email, "identities": []})
        if not auth._invited(email):              # the before-user-created hook
            return _err(403, "hook_error", "not_invited")
        u = auth.new_user(email, password)
        auth._mail(email, "email", request.query_params.get("redirect_to", ""), body.get("code_challenge", ""),
                   base(request))
        return JSONResponse(auth._user_json(u))

    async def token(request):
        if not key_ok(request):
            return _err(401, "no_api_key")
        grant = request.query_params.get("grant_type")
        body = await request.json()
        if grant == "password":
            u = auth.users.get(str(body.get("email", "")).lower())
            if not u or not u["password"] or u["password"] != auth._hash(str(body.get("password", ""))):
                return _err(400, "invalid_credentials", "Invalid login credentials")
            if not u["confirmed"]:
                return _err(400, "email_not_confirmed", "Email not confirmed")
            return JSONResponse(auth._session(u))
        if grant == "refresh_token":
            entry = auth.refresh.get(body.get("refresh_token", ""))
            if not entry:
                return _err(400, "refresh_token_not_found", "Invalid Refresh Token: Refresh Token Not Found")
            if entry[1]:
                return _err(400, "refresh_token_already_used", "Invalid Refresh Token: Already Used")
            auth.refresh[body["refresh_token"]] = (entry[0], True)
            u = auth._by_id(entry[0])
            if u is None:
                return _err(400, "session_not_found")
            return JSONResponse(auth._session(u))
        if grant == "pkce":
            entry = auth.codes.pop(body.get("auth_code", ""), None)
            if not entry:
                return _err(400, "flow_state_not_found")
            uid, challenge = entry
            got = base64.urlsafe_b64encode(hashlib.sha256(str(body.get("code_verifier", "")).encode()).digest()
                                           ).rstrip(b"=").decode()
            if got != challenge:
                return _err(400, "bad_code_verifier")
            return JSONResponse(auth._session(auth._by_id(uid)))
        return _err(400, "unsupported_grant_type")

    async def verify(request):
        body = await request.json()
        entry = auth.links.pop(body.get("token_hash", ""), None)
        if not entry or entry[1] != body.get("type") and not (entry[1] == "email" and body.get("type") == "signup"):
            return _err(403, "otp_expired", "Email link is invalid or has expired")
        email, kind, expires = entry[:3]
        if expires < time.time():
            return _err(403, "otp_expired", "Email link is invalid or has expired")
        u = auth.users.get(email)
        if not u:
            return _err(403, "otp_expired")
        u["confirmed"] = True
        return JSONResponse(auth._session(u))

    async def recover(request):
        body = await request.json()
        email = str(body.get("email", "")).lower()
        if email in auth.users:
            auth._mail(email, "recovery", request.query_params.get("redirect_to", ""),
                       body.get("code_challenge", ""), base(request))
        return JSONResponse({})

    async def resend(request):
        body = await request.json()
        email = str(body.get("email", "")).lower()
        u = auth.users.get(email)
        if u and not u["confirmed"]:
            auth._mail(email, "email", request.query_params.get("redirect_to", ""),
                       body.get("code_challenge", ""), base(request))
        return JSONResponse({})

    async def user(request):
        u = auth.user_for(request.headers.get("Authorization", "").removeprefix("Bearer "))
        if not u:
            return _err(401, "bad_jwt", "invalid JWT")
        if request.method == "PUT":
            body = await request.json()
            if "password" in body:
                if not _strong(str(body["password"])):
                    return _err(422, "weak_password")
                u["password"] = auth._hash(str(body["password"]))
                if "email" not in u["providers"]:
                    u["providers"].append("email")
        return JSONResponse(auth._user_json(u))

    async def logout(request):
        access = request.headers.get("Authorization", "").removeprefix("Bearer ")
        entry = auth.access.pop(access, None)
        if entry:
            for r, (uid, _) in list(auth.refresh.items()):
                if uid == entry[0]:
                    del auth.refresh[r]
        return Response(status_code=204)

    async def authorize(request):
        q = request.query_params
        if q.get("provider") != "google" or q.get("code_challenge_method") != "s256":
            return _err(400, "bad_request")
        page = f"""<!doctype html><title>Sign in – Google (fake)</title>
        <h1>Fake Google</h1><form method="post" action="/__google">
        <input type="hidden" name="redirect_to" value="{q['redirect_to']}">
        <input type="hidden" name="challenge" value="{q['code_challenge']}">
        <label>Google account email <input name="email" id="gemail"></label>
        <label>Name <input name="name" id="gname" value="Test Person"></label>
        <button name="go" value="continue" id="gcontinue">Continue</button>
        <button name="go" value="cancel" id="gcancel">Cancel</button></form>"""
        return HTMLResponse(page)

    async def google(request):
        form = await request.form()
        back = form["redirect_to"]
        sep = "&" if "?" in back else "?"
        if form.get("go") != "continue":
            return RedirectResponse(back + sep + urlencode({"error": "access_denied",
                                                            "error_description": "The user cancelled"}), 303)
        email = str(form["email"]).strip().lower()
        u = auth.users.get(email)
        if u is None:
            if not auth._invited(email):
                return RedirectResponse(back + sep + urlencode({"error": "server_error",
                                                                "error_description": "not_invited"}), 303)
            u = auth.new_user(email, provider="google", meta={"full_name": form.get("name") or "",
                                                              "avatar_url": ""})
        else:                                   # same verified email: link to the existing user
            if not u["confirmed"]:              # an unconfirmed password identity is removed first
                u["password"] = None
                u["providers"] = [p for p in u["providers"] if p != "email"]
                u["confirmed"] = True
            if "google" not in u["providers"]:
                u["providers"].append("google")
            u["meta"].setdefault("full_name", form.get("name") or "")
        code = secrets.token_hex(12)
        auth.codes[code] = (u["id"], form["challenge"])
        return RedirectResponse(back + sep + urlencode({"code": code}), 303)

    async def rest(request):
        # failure injection (tests): fail the next matching request(s) with a 500
        name = request.path_params["name"]
        for rule in list(app.state.fail):
            if rule["method"] == request.method and rule["table"] == name:
                rule["skip"] = rule.get("skip", 0)
                if rule["skip"] > 0:
                    rule["skip"] -= 1
                    break
                rule["times"] -= 1
                if rule["times"] <= 0:
                    app.state.fail.remove(rule)
                return JSONResponse({"message": "injected failure"}, status_code=500)
        body = None
        if request.method in ("POST", "PATCH"):
            raw = await request.body()
            import json as _json
            body = _json.loads(raw) if raw else {}
        access = request.headers.get("Authorization", "").removeprefix("Bearer ")
        if access.startswith("tok|") and auth.user_for(access) is None:
            return _err(401, "bad_jwt", "JWT expired")
        name = request.path_params["name"]
        resp = db.request(request.method, f"{URL}/rest/v1/{name}", params=dict(request.query_params),
                          json=body, headers={k.title() if k != "apikey" else k: v for k, v in request.headers.items()},
                          timeout=5)
        if name == "rpc/delete_my_account" and resp.status_code < 300:
            uid = access.split("|")[1]
            for email, u in list(auth.users.items()):
                if u["id"] == uid:
                    del auth.users[email]
        data = resp.json()
        return JSONResponse(data, status_code=resp.status_code) if data is not None else Response(status_code=resp.status_code)

    async def fail(request):
        """Test setup: {"method": "POST", "table": "learning_entries", "times": 1, "skip": 0};
        {"clear": true} removes every rule not used up yet."""
        body = await request.json()
        if body.get("clear"):
            app.state.fail.clear()
        else:
            app.state.fail.append(body)
        return JSONResponse({"ok": True})

    async def outbox(request):
        return JSONResponse(auth.outbox)

    async def seed(request):
        body = await request.json()
        for table, rows in body.items():
            pk = SCHEMA[table]
            for row in rows:
                db.tables[table][tuple(str(row[c]) for c in pk)] = row
        return JSONResponse({"ok": True})

    async def wipe(request):
        """Test setup: what supabase/reset_my_progress.sql does to one person."""
        body = await request.json()
        for t in (storage.ENTRIES_TABLE if hasattr(storage, "ENTRIES_TABLE") else "learning_entries",
                  storage.BOOKS_TABLE, storage.PATHS_TABLE, storage.SETTINGS_TABLE, storage.PREFS_TABLE):
            for key in [k for k, r in db.tables[t].items() if r.get("user_id") == body["user_id"]]:
                del db.tables[t][key]
        return JSONResponse({"ok": True})

    async def expire_link(request):
        """Make the newest mailed link expired (to test that case)."""
        th = auth.outbox[-1]["custom_link"].split("token_hash=")[1].split("&")[0]
        e = auth.links[th]
        auth.links[th] = (e[0], e[1], time.time() - 1, *e[3:])
        return JSONResponse({"ok": True})

    async def make_user(request):
        """Test setup: a confirmed email+password account (and its invitation)."""
        body = await request.json()
        email = body["email"].lower()
        db.tables[storage.INVITES_TABLE][(email,)] = {"email": email, "note": ""}
        if email not in auth.users:
            u = auth.new_user(email, body["password"])
            u["confirmed"] = True
        return JSONResponse({"id": auth.users[email]["id"]})

    async def dump(request):
        return JSONResponse({"tables": {t: list(r.values()) for t, r in db.tables.items()},
                             "users": [{k: v for k, v in u.items() if k != "password"} | {"has_password": bool(u["password"])}
                                       for u in auth.users.values()]})

    routes = [
        Route("/auth/v1/signup", signup, methods=["POST"]),
        Route("/auth/v1/token", token, methods=["POST"]),
        Route("/auth/v1/verify", verify, methods=["POST"]),
        Route("/auth/v1/verify", verify_get, methods=["GET"]),
        Route("/auth/v1/recover", recover, methods=["POST"]),
        Route("/auth/v1/resend", resend, methods=["POST"]),
        Route("/auth/v1/user", user, methods=["GET", "PUT"]),
        Route("/auth/v1/logout", logout, methods=["POST"]),
        Route("/auth/v1/authorize", authorize),
        Route("/__google", google, methods=["POST"]),
        Route("/rest/v1/{name:path}", rest, methods=["GET", "POST", "DELETE", "PATCH"]),
        Route("/__outbox", outbox),
        Route("/__seed", seed, methods=["POST"]),
        Route("/__wipe", wipe, methods=["POST"]),
        Route("/__expire_link", expire_link, methods=["POST"]),
        Route("/__dump", dump),
        Route("/__user", make_user, methods=["POST"]),
        Route("/__fail", fail, methods=["POST"]),
    ]
    app = Starlette(routes=routes)
    app.state.auth = auth
    app.state.fail = []
    return app


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(build_app(int(os.environ.get("FAKE_ACCESS_TTL", "3600"))), host="127.0.0.1",
                port=int(os.environ.get("FAKE_SUPABASE_PORT", "9999")), log_level="warning")
