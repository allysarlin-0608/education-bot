"""Streamlit helpers shared by the app's pages."""
import hmac
import logging
import math
import threading
import time
from datetime import date
from urllib.parse import urlparse

import streamlit as st

from coach import appconfig, catalog, clock, core, curriculum, habit, prefs as prefs_, settings, storage

logger = logging.getLogger("coach.ui")


def _session_paths():
    """Her goals, from the session running now (None outside a session)."""
    from streamlit.runtime.scriptrunner import get_script_run_ctx
    if get_script_run_ctx(suppress_warning=True) is None or "coach_log" not in st.session_state:
        return None
    return st.session_state.coach_log.get("paths") or []


def _paths_unreadable() -> bool:
    store = st.session_state.get("coach_store")
    return bool(getattr(store, "paths_error", None))


catalog.bind(_session_paths, _paths_unreadable)     # every page and callback sees this session's goals (coach/catalog.py)
TIMEZONE = clock.TIMEZONE        # the learner's timezone (coach/clock.py: the one clock)


PASSWORD_MISSING = (
    "This app has no password set yet, so it stays closed to protect the records. "
    "In Streamlit, go to Settings → Secrets, add the line APP_PASSWORD = \"your password\", save and refresh."
)


# Wrong passwords (BUG-011): after MAX_TRIES in a row the gate closes for
# COOLDOWN_SECONDS, then opens again by itself. Counted for the whole server,
# not per session, since a new session costs nothing; a server restart
# clears it.
MAX_TRIES = 5
COOLDOWN_SECONDS = 15 * 60
_gate = {"failures": 0, "until": 0.0}
_gate_lock = threading.Lock()


def _clock() -> float:
    return time.time()


def _cooling_down() -> float:
    """Seconds left before passwords are checked again (0: open)."""
    with _gate_lock:
        return max(0.0, _gate["until"] - _clock())


def _check_password(entered: str, expected: str) -> bool:
    with _gate_lock:
        if _gate["until"] > _clock():
            return False
        if hmac.compare_digest(entered.encode(), expected.encode()):
            _gate["failures"] = 0
            return True
        _gate["failures"] += 1
        if _gate["failures"] >= MAX_TRIES:
            _gate["failures"], _gate["until"] = 0, _clock() + COOLDOWN_SECONDS
            logger.warning("password gate: %d wrong tries, closed for %d minutes", MAX_TRIES, COOLDOWN_SECONDS // 60)
        return False


def require_password():
    """Basic gate for a public URL: nothing is loaded until the password
    from secrets (APP_PASSWORD) is entered in this session."""
    if st.session_state.get("coach_authed"):
        return
    # the page she asked for (a refresh, a link): she is taken back to it once in
    url = st.context.url          # (None where there is no browser page: the page tests)
    if url:
        st.session_state.setdefault("coach_asked_path", urlparse(url).path.strip("/").split("/")[-1])
    expected = appconfig.get_setting("APP_PASSWORD")
    st.markdown("### GNOSIS")
    if not expected:
        st.error(PASSWORD_MISSING)
        st.stop()
    with st.form("login"):
        entered = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Enter", type="primary")
    if submitted and _check_password(entered, expected):
        st.session_state.coach_authed = True
        st.rerun()
    left = _cooling_down()
    if left:
        minutes = math.ceil(left / 60)
        st.error(f"Too many wrong tries. Try again in {minutes} {'minute' if minutes == 1 else 'minutes'}.")
    elif submitted:
        st.error("Wrong password. Try again.")
    st.stop()


# Bump whenever the store or the log's shape changes. Sessions opened
# before an update keep the old objects in st.session_state (e.g. a store
# without save_book, a log without "books"), so on a mismatch those are
# dropped and reloaded from storage, which is always up to date.
STATE_VERSION = 4


CACHED = ("coach_log", "coach_chats", "coach_settings", "coach_prefs")


def make_store():
    """The session's store (once per session). public: scoped to whoever is
    signed in, asked afresh on every call (auth.get_current_user_id)."""
    import coach
    from coach import auth
    # (new code loaded since this session began: its store and records are rebuilt by it too)
    version = (STATE_VERSION, coach.GENERATION)
    if st.session_state.get("coach_state_version") != version:
        for key in ("coach_store", *CACHED):
            st.session_state.pop(key, None)
        st.session_state.coach_state_version = version
    if "coach_store" not in st.session_state:
        public = auth.is_public()
        try:
            st.session_state.coach_store = storage.make_store(
                appconfig.get_setting("SUPABASE_URL"), appconfig.get_setting("SUPABASE_KEY"),
                scoped=public, current_user=auth.get_current_user_id,
                access_token=auth.access_token if public else None,
            )
        except storage.StorageError as e:
            st.error(f"The app isn't set up correctly: {e}.")
            st.stop()
    return st.session_state.coach_store


def init_state():
    make_store()
    # what this session holds is one person's: if someone else is signed in now
    # (a sign-out and a sign-in in the same browser), it is dropped and reloaded
    uid = user_id()
    if st.session_state.get("coach_uid") != uid:
        for key in CACHED:
            st.session_state.pop(key, None)
        st.session_state.coach_uid = uid
    if "api_key" not in st.session_state:
        st.session_state.api_key = appconfig.get_setting("GROQ_API_KEY")
    if "coach_log" not in st.session_state:
        try:
            st.session_state.coach_log = st.session_state.coach_store.load()
            st.session_state.coach_log_fresh = True     # (read this run: no second read on arrival)
        except storage.StorageError as e:
            # Don't cache the failure: the next rerun tries to load again.
            st.error(f"Couldn't load your records ({e}). Refresh the page in a moment to try again.")
            st.stop()
    if "coach_settings" not in st.session_state:
        load_settings()
    if "coach_chats" not in st.session_state:
        # "date|topic" -> that lesson's chat, so switching pages or topics
        # never loses it (restored from the saved entry when missing).
        st.session_state.coach_chats = {}


def personal_user_id() -> str:
    """The one user of a personal app (a fixed id, which can be set with
    COACH_USER_ID)."""
    return appconfig.get_setting("COACH_USER_ID") or settings.DEFAULT_USER_ID


def user_id():
    """Whose data this session shows (auth.get_current_user_id)."""
    from coach import auth
    return auth.get_current_user_id()


def load_settings():
    """This user's settings. Where the settings table doesn't exist yet the
    app keeps its old fixed setup, unchanged (settings.legacy)."""
    store, uid = st.session_state.coach_store, user_id()
    try:
        row = store.load_settings()
    except storage.StorageError as e:
        st.error(f"Couldn't load your settings ({e}). Refresh the page in a moment to try again.")
        st.stop()
    st.session_state.coach_settings = (settings.legacy(uid) if store.settings_missing
                                       else settings.normalize(row, uid))


def config() -> dict:
    return st.session_state.coach_settings


def save_settings(new: dict) -> bool:
    """Save her settings (the whole row, found by her user_id) and use
    them from now on. On failure nothing changes and the error is shown
    after the rerun."""
    if settings.is_legacy(new):
        return False
    try:
        st.session_state.coach_store.save_settings(new)
    except storage.StorageError as e:
        st.session_state.coach_save_error = f"Your settings weren't saved ({e}). Try again in a moment."
        return False
    st.session_state.coach_settings = new
    return True


# ------------------------------------------------------------ her habits
PREFS_MISSING = ("Reminders and light days need one more table in the database "
                 "(supabase/goals.sql). Everything else works as usual.")


def load_prefs() -> None:
    """Her habit preferences as stored now (coach/prefs.py). Where they can't
    be read the defaults are used (reminders off), and saving says why."""
    store = st.session_state.coach_store
    try:
        row = store.load_prefs()
        st.session_state.coach_prefs_error = None
    except storage.StorageError as e:
        logger.warning("couldn't read the habit preferences (%s); using the defaults", e)
        st.session_state.coach_prefs_error = PREFS_MISSING if e.status == 404 else str(e)
        row = (st.session_state.get("coach_prefs") or None)
    st.session_state.coach_prefs = prefs_.normalize(row)


def prefs() -> dict:
    if "coach_prefs" not in st.session_state:
        load_prefs()
    return st.session_state.coach_prefs


def update_prefs(**fields) -> bool:
    """Change some preferences, applied onto the row as stored now (another
    tab or device may have changed others). False, and the reason shown
    after the rerun, if it couldn't be saved."""
    load_prefs()
    if st.session_state.get("coach_prefs_error") == PREFS_MISSING:
        st.session_state.coach_save_error = PREFS_MISSING
        return False
    new = prefs_.normalize(dict(prefs(), **fields))
    try:
        st.session_state.coach_store.save_prefs(new)
    except storage.StorageError as e:
        st.session_state.coach_save_error = f"That wasn't saved ({e}). Try again in a moment."
        return False
    st.session_state.coach_prefs = new
    return True


def units_today() -> int:
    """Lessons in today's plan: her pace, or one on a light day. Every page
    that shows today's plan asks here, so they all agree."""
    return habit.lessons_today(prefs(), today(), settings.units(config()))


def review_due(log) -> list:
    """Today's review cards: a short catch-up on a light or returning day
    (coach/habit.py). Every page that counts them asks here."""
    from coach import review
    day = today()
    return review.due(log, day, limit=habit.review_limit(log, prefs(), day))


def refit_today(count: int) -> None:
    """Her pace changed: today's day, if started, takes the new number of
    lessons now and is saved (curriculum.fit keeps what she began), so
    Today, Progress and the calendar read the same day."""
    log, day = st.session_state.coach_log, today()
    topic = topic_for(day)
    refresh_entry(log, day, topic)
    entry = core.find_entry(log, day, topic)
    if not entry or not entry.get("lessons"):
        return
    fitted = curriculum.fit(log, topic, entry["lessons"], count)
    if [s["n"] for s in fitted] != [s["n"] for s in entry["lessons"]]:
        entry["lessons"] = fitted
        entry["completed"] = curriculum.day_complete(fitted)
        save_entry(log, entry)


def topic_for(day):
    """The subject for a day, from her settings (and, for a day already
    started, the subject she started)."""
    return settings.topic_for(config(), day, TIMEZONE, st.session_state.get("coach_log"))


WORLD_PAGE = "views/world.py"


def enter_world(topic: str):
    """Into a subject's world. The one subject it shows is kept in her
    session and named in the page's address (?subject=), so a refresh, the
    browser's Back or a link opens that same subject, never another."""
    st.session_state.world_topic = topic
    st.switch_page(WORLD_PAGE, query_params={"subject": topic})


COURSE_PAGE = "views/course.py"


def open_course(topic: str):
    """A subject's course map (views/course.py), named in the address."""
    st.switch_page(COURSE_PAGE, query_params={"subject": topic})


def next_study_day(topic: str):
    """The next day, from today, that the rotation gives to this subject."""
    from datetime import timedelta
    day = today()
    for k in range(0, 8):
        if topic_for(day + timedelta(days=k)) == topic:
            return day + timedelta(days=k)
    return None


def today():
    return clock.today()


def using_cloud() -> bool:
    return st.session_state.coach_store.name == "supabase"


def save_entry(log, entry):
    """Save one entry. Returns True on success; on failure the error is
    kept for show_pending_error() so it survives the st.rerun() that
    usually follows a save."""
    unsaved = st.session_state.setdefault("coach_unsaved", set())
    try:
        st.session_state.coach_store.save_entry(log, entry)
    except storage.StorageError as e:
        st.session_state.coach_save_error = f"This wasn't saved ({e}). Try again in a moment."
        unsaved.add((entry["date"], entry["topic"]))     # kept as it is until a save succeeds
        return False
    unsaved.discard((entry["date"], entry["topic"]))
    return True


def save_path(log, path) -> bool:
    """Save one of her goals (and keep it in this session's records); same
    error handling as save_entry."""
    try:
        st.session_state.coach_store.save_path(log, path)
    except storage.StorageError as e:
        st.session_state.coach_save_error = f"Your goal wasn't saved ({e}). Try again in a moment."
        return False
    log["paths"] = [p for p in log.get("paths", []) if p["id"] != path["id"]] + [path]
    return True


def record(event: str) -> None:
    """Count one usage event for today (coach/metrics.py). Counting never
    gets in the way: a failure is logged, not shown, and the learner carries on."""
    from coach import auth
    if not auth.is_public() or not hasattr(st.session_state.get("coach_store"), "add_event"):
        return                       # (the numbers are the public site's: signed-in learners only)
    try:
        st.session_state.coach_store.add_event(today().isoformat(), event)
    except storage.StorageError as e:
        logger.warning("couldn't count %s (%s)", event, e)


def learned(slot: dict, entry_date: str, kind: str, score: float, source: str = "") -> None:
    """Add a piece of evidence to a lesson's slot (coach/mastery.py) and count
    what it showed (missed, recovered, held, slipped, mastered). The caller
    saves the slot's day."""
    from coach import mastery
    for signal in mastery.add(slot, entry_date, kind, score, today(), source):
        record(signal)


def learned_elsewhere(log, topic: str, n: int, kind: str, score: float, source: str = "") -> bool:
    """Evidence for another lesson than the one on the page (an earlier idea
    asked again in a quiz, a practice exercise): its day re-read, the
    evidence added, the day saved. False if it couldn't be saved."""
    from coach import mastery
    held = mastery.holder(log, topic, n)
    if held is None:
        return False
    refresh_entry(log, date.fromisoformat(held[0]["date"]), topic)
    held = mastery.holder(log, topic, n)
    if held is None:
        return False
    entry, slot = held
    learned(slot, entry["date"], kind, score, source)
    return save_day(log, entry, [n])


def save_book(log, book):
    """Save one book's state; same error handling as save_entry."""
    try:
        st.session_state.coach_store.save_book(log, book)
    except storage.StorageError as e:
        st.session_state.coach_save_error = f"Your reading progress wasn't saved ({e}). Try again in a moment."
        return False
    return True


def show_pending_error():
    # The slot is always there, error or not: an element that appears on one
    # run and not the next shifts everything under it, and Streamlit then
    # redraws the panels below as new (closed) ones.
    slot = st.empty()
    error = st.session_state.pop("coach_save_error", None)
    if error:
        slot.error(error)


def replace_log(log):
    """Replace the whole stored log (backup import). Returns True on success."""
    try:
        st.session_state.coach_store.replace(log)
    except storage.StorageError as e:
        st.error(f"The import wasn't saved ({e}). Try again in a moment.")
        return False
    return True


def reset_chat():
    """Forget the on-screen chats so the lesson page reloads them from the log."""
    st.session_state.coach_chats = {}


def refresh_entry(log, day, topic):
    """Today's entry as stored now, in place of this session's copy: another
    tab or device may have moved on since this page was loaded, and every
    write (and every Start) must build on that, not on an old copy."""
    try:
        stored = st.session_state.coach_store.load_entry(day.isoformat(), topic)
    except storage.StorageError as e:
        logger.warning("couldn't refresh %s %s (%s); using this session's copy", day, topic, e)
        return
    mine = next((k for k, e in enumerate(log["entries"])
                 if e["date"] == day.isoformat() and e["topic"] == topic), None)
    if (day.isoformat(), topic) in st.session_state.get("coach_unsaved", ()):
        return          # this session's copy holds work a save failed on: the next save sends it (ISS-024)
    if stored is None and mine is not None and not curriculum.worked_on(log["entries"][mine]):
        # made by an action that then failed or was cut off (a lesson that
        # couldn't be written, a question with no reply): never saved, nothing
        # done, so not a day she studied (ISS-013)
        del log["entries"][mine]
        return
    if stored is None or (mine is not None and log["entries"][mine] == stored):
        return
    if mine is None:
        log["entries"].append(stored)
        log["entries"].sort(key=lambda e: (e["date"], e["topic"]))
    else:
        log["entries"][mine] = stored
    for key in [k for k in st.session_state.coach_chats if k.startswith(f"{day.isoformat()}|{topic}|")]:
        del st.session_state.coach_chats[key]          # rebuilt from the stored lessons


def refresh_log(log) -> None:
    """Her whole record as stored now, in place of this session's copy (another
    tab or device may have moved on since it was loaded): for pages that show
    or hand out all of it (Progress, its backup). Days a save failed on stay as
    this session holds them (ISS-024)."""
    try:
        stored = st.session_state.coach_store.load()
    except storage.StorageError as e:
        logger.warning("couldn't re-read the records (%s); using this session's copy", e)
        return
    unsaved = st.session_state.get("coach_unsaved", set())
    mine = {(e["date"], e["topic"]): e for e in log["entries"] if (e["date"], e["topic"]) in unsaved}
    entries = [e for e in stored["entries"] if (e["date"], e["topic"]) not in mine] + list(mine.values())
    log["entries"] = sorted(entries, key=lambda e: (e["date"], e["topic"]))
    if not getattr(st.session_state.coach_store, "books_error", None):
        log["books"] = stored["books"]      # (books that couldn't be read aren't "no books", ISS-031)
    if not getattr(st.session_state.coach_store, "paths_error", None):
        log["paths"] = stored.get("paths", [])     # (the same for her goals)
    st.session_state.coach_chats = {}          # rebuilt from the records as now stored


def save_day(log, entry, ns, keep=(), recount=False, page_day=None) -> bool:
    """Save a day this page changed, written into the day as stored now
    (curriculum.merge_day): this page's copy may be old (another tab or
    device, a fragment that didn't re-read it), and a whole-row save of it
    would undo what was saved since (ISS-021, ISS-025)."""
    try:
        stored = st.session_state.coach_store.load_entry(entry["date"], entry["topic"])
    except storage.StorageError as e:
        logger.warning("couldn't re-read %s %s (%s); saving this session's copy", entry["date"], entry["topic"], e)
        stored = None
    if stored is not None:
        unsaved = (entry["date"], entry["topic"]) in st.session_state.get("coach_unsaved", ())
        since = None if unsaved else (page_day or today())       # the day the page made its cards on
        curriculum.merge_day(entry, stored, ns, since, keep=keep, recount=recount)
    return save_entry(log, entry)


def refresh_books(log):
    """The books as stored now (another tab or device may have checked a day
    since this page was loaded), so a save never writes an old copy back."""
    try:
        log["books"] = st.session_state.coach_store.load_books()
    except storage.StorageError as e:
        logger.warning("couldn't refresh the books (%s); using this session's copy", e)


def refresh_settings():
    """Her settings as stored now, before a change is applied to them:
    another tab may have changed something else since this page loaded, and
    the change is saved as the whole row. (Quiet: this runs in callbacks.)"""
    store, uid = st.session_state.coach_store, user_id()
    try:
        row = store.load_settings()
    except storage.StorageError as e:
        logger.warning("couldn't refresh the settings (%s); using this session's copy", e)
        return
    if not store.settings_missing:
        st.session_state.coach_settings = settings.normalize(row, uid)
