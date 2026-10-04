"""What can be learned, behind one set of questions every page asks.

Two kinds of subject:
- the built-in subjects (core.TOPICS), each with a written syllabus in
  coach/curriculum/<topic>.txt, shared by everyone;
- the learner's own goals (coach/paths.py), each a path the AI designed for
  her, stored with her records. A goal's key is "g-" and eight hex digits.

Both are "topics" to the rest of the app: entries, review cards, the course
map, Progress, search and backups key everything by topic, so a goal works
everywhere a subject does.

The goals are one person's, so they are never held in the module: a
Streamlit server runs many people's sessions at once. In the app they are
read from the session running now (bind(), set once by coach/ui.py: her
records in st.session_state), so a button's callback, which runs before the
page, sees them too. Without a session (tests, tools) use() gives them for
the thread."""
import re
import threading

GOAL_ID = re.compile(r"^g-[0-9a-f]{8}$")
_local = threading.local()
_source = None


def bind(source) -> None:
    """source(): the paths of the session running now, or None outside one."""
    global _source
    _source = source


def use(paths) -> None:
    """Her goals for this thread, where there is no app session (tests, tools)."""
    _local.paths = _index(paths)


def _index(paths) -> dict:
    return {p["id"]: p for p in paths or [] if isinstance(p, dict) and is_goal(p.get("id"))}


def _paths() -> dict:
    found = _source() if _source is not None else None
    if found is not None:
        return _index(found)
    return getattr(_local, "paths", {})


def is_goal(topic) -> bool:
    return isinstance(topic, str) and bool(GOAL_ID.match(topic))


def builtin(topic) -> bool:
    from coach import core
    return topic in core.TOPICS


def valid(topic) -> bool:
    """A topic a record may carry (its shape only: goals are checked against
    her paths where they are used, not when records are read)."""
    return builtin(topic) or is_goal(topic)


def known(topic) -> bool:
    """A subject that exists for her now: built in, or one of her goals."""
    return builtin(topic) or topic in _paths()


def path(topic):
    """Her goal's path, or None."""
    return _paths().get(topic)


def goals(active_only: bool = True) -> list:
    """Her goals, oldest first."""
    out = sorted(_paths().values(), key=lambda p: p.get("created_at") or "")
    return [p for p in out if p.get("status") == "active"] if active_only else out


def name(topic, default: str = None) -> str:
    """The name to show: a subject's, or her goal's title."""
    from coach import core
    if topic in core.TOPICS:
        return core.TOPICS[topic]
    p = path(topic)
    if p:
        return p["title"]
    return default if default is not None else ("Your goal" if is_goal(topic) else str(topic))


def goal_lessons(topic) -> tuple:
    """A goal's syllabus as (unit, title) pairs, in order."""
    p = path(topic)
    if not p:
        return ()
    return tuple((u["name"], title) for u in p["units"] for title in u["lessons"])


def level(topic):
    """The level a goal is taught at (its path's), or None for a subject."""
    p = path(topic)
    return p.get("level") if p else None
