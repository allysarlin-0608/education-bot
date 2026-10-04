import importlib.abc
import importlib.machinery
import logging
import os
import sys
import threading

# Details of failed AI / database calls go here (Streamlit Cloud: Manage
# app → logs), never onto the page. Each line carries the session it came
# from (a short tag of Streamlit's random session id: no name, email or
# user id), so one person's failing run can be followed through the log.
class _SessionTag(logging.Filter):
    def filter(self, record):
        record.sid = session_tag()
        return True


def session_tag() -> str:
    """The running session's tag ("-" outside one: the server, a route)."""
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        ctx = get_script_run_ctx(suppress_warning=True)
    except ImportError:
        return "-"
    return ctx.session_id[:8] if ctx is not None and ctx.session_id else "-"


_logger = logging.getLogger("coach")
if not _logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s [%(sid)s] %(message)s"))
    _handler.addFilter(_SessionTag())
    _logger.addHandler(_handler)
    _logger.setLevel(logging.INFO)
    _logger.propagate = False


# ---------------------------------------------------------------- new code
# Streamlit reads each page's file afresh on every run, but a module it
# imported (coach.ui, ...) stays the copy in memory. When an update lands
# while nobody has the site open (Streamlit Cloud pulls a push into the
# running server), the next visitor gets new pages on old modules: half old,
# half new code (a page calling ui.open_course on a ui without it). So each
# module notes its file's time when it is loaded, and freshen(), at the top
# of every run (gnosis.py), drops them all when any file is newer, so the
# run loads the new code whole. coach.routes is kept: the server holds its
# routes (and the sign-ins waiting in them) from when it started; a change
# there still needs a reboot.
SERVER_SIDE = {"coach.routes", "coach.errors"}     # (errors: one class across versions, coach/errors.py)
GENERATION = 0              # +1 each time the code is reloaded (ui.make_store starts sessions afresh)
_loaded = {}                # module name -> its file's modification time when it was loaded
_lock = threading.Lock()


class _Stamp(importlib.abc.MetaPathFinder):
    """Notes each coach module's file time as it is imported."""
    def find_spec(self, name, path, target=None):
        if not name.startswith("coach."):
            return None
        spec = importlib.machinery.PathFinder.find_spec(name, path)
        if spec is not None and spec.origin:
            try:
                _loaded[name] = os.path.getmtime(spec.origin)
            except OSError:
                pass
        return spec


if not any(isinstance(f, _Stamp) for f in sys.meta_path):
    sys.meta_path.insert(0, _Stamp())


def _changed() -> list:
    out = []
    for name, when in list(_loaded.items()):
        module = sys.modules.get(name)
        path = getattr(module, "__file__", None)
        try:
            if path and os.path.getmtime(path) != when:
                out.append(name)
        except OSError:
            pass
    return out


def freshen() -> bool:
    """If any coach file changed since it was loaded, forget every coach
    module (but the server's routes) so this run imports the new code whole.
    True when it did."""
    global GENERATION
    with _lock:
        changed = _changed()
        if not changed:
            return False
        package = sys.modules[__name__]
        for name in [n for n in list(sys.modules) if n.startswith("coach.") and n not in SERVER_SIDE]:
            del sys.modules[name]
            _loaded.pop(name, None)
            short = name.split(".", 1)[1]
            if "." not in short and hasattr(package, short):
                delattr(package, short)     # (or `from coach import ui` would hand back the old one)
        GENERATION += 1
        _logger.warning("new code on disk (%s): coach modules reloaded, generation %d%s", ", ".join(sorted(changed)),
                        GENERATION, f"; {', '.join(sorted(set(changed) & SERVER_SIDE))} changed too: reboot the app to load it"
                        if set(changed) & SERVER_SIDE else "")
        return True
