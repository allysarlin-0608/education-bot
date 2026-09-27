"""HTTP routes served beside the Streamlit app (st.App, streamlit_app.py).

Sign-in has steps a Streamlit script can't do: set an HttpOnly cookie, read
a link's query before the page loads. Those happen here, on the server."""
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route

PROBE_COOKIE = "gn_probe"


async def _probe_set(request: Request):
    resp = PlainTextResponse("GNOSIS routes OK (1/2). Now open /auth/probe-check")
    resp.set_cookie(PROBE_COOKIE, "1", max_age=600, httponly=True, secure=True, samesite="lax", path="/")
    return resp


async def _probe_check(request: Request):
    got = request.cookies.get(PROBE_COOKIE) == "1"
    return PlainTextResponse(f"GNOSIS routes OK (2/2). HttpOnly cookie came back: {'YES' if got else 'NO'}")


def all_routes() -> list:
    return [Route("/auth/probe", _probe_set), Route("/auth/probe-check", _probe_check)]
