"""What the fourth round of testing found, held: the "Check it yourself"
links search what the lesson teaches (never a section heading or the goal's
name); ..."""
import pytest

from coach import lesson_view


# ---------------------------------------------------------------- 1. check it yourself
@pytest.mark.parametrize("title, query", [
    ("What is an investment and why it matters", "investment"),
    ("How compound interest works", "compound interest"),
    ("Why diversification matters", "diversification"),
    ("Introduction to the balance sheet", "balance sheet"),
    ("Reading financial statements for beginners", "Reading financial statements"),
    ("Lesson 3: What is risk?", "risk"),
    ("Aquinas's five ways", "Aquinas's five ways"),
    ("我想學吉他", "我想學吉他"),
])
def test_the_check_links_search_what_the_lesson_teaches(title, query):
    assert lesson_view.check_query(title) == query


@pytest.mark.parametrize("show", ["render", "render_tabs"])
def test_a_lesson_s_last_section_never_becomes_the_search(monkeypatch, show):
    searched = []
    monkeypatch.setattr(lesson_view, "check_links", searched.append)
    monkeypatch.setattr(lesson_view, "_body", lambda *a: None)
    monkeypatch.setattr(lesson_view.st, "html", lambda *a, **k: None)
    monkeypatch.setattr(lesson_view.st, "tabs", lambda names: [_Null() for _ in names])
    monkeypatch.setattr(lesson_view.st, "container", lambda **k: _Null())
    text = "【Topic】\nInvesting\n【Key Idea】\nMoney now for more later.\n【Note】\nNot advice."
    getattr(lesson_view, show)(text, "g-12345678", key="k", title="What is an investment and why it matters")
    assert searched == ["What is an investment and why it matters"]


class _Null:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


# ---------------------------------------------------------------- 2. the same goal twice, and removing one
from coach import catalog, paths, review, settings          # noqa: E402
from test_goal_pages import ai, all_of_it, first_purpose, has, stored, texts   # noqa: E402
from test_goals import a_path, design_reply                  # noqa: E402
from test_pages_smoke import app, loads                      # noqa: E402


@pytest.mark.parametrize("a, b, same", [
    ("Basics of Investing for Beginners", "Investing Basics for Beginners", True),
    ("Reading financial statements", "Read a company's financial statements", True),
    ("Economics: Behavioral economics", "Behavioral economics", True),
    ("我想學吉他", "學吉他", True),
    ("History of Japan", "History of Korea", False),
    ("Stoic philosophy", "Philosophy", False),
    ("Personal finance", "Behavioral economics", False),
])
def test_a_goal_in_other_words_is_the_same_goal(a, b, same):
    assert paths.similar(a, b) is same


def test_a_goal_she_has_is_offered_before_any_ai_call(monkeypatch, tmp_path):
    # covers: W-goal-goal_dup_go, W-goal-goal_dup_new
    goal = dict(a_path(), title="Investing Basics for Beginners", goal="Investing basics for beginners")
    calls = ai(monkeypatch, design_reply())
    at = app(monkeypatch, tmp_path, subjects=(goal["id"],), paths=[goal], history=False)
    loads(at, "views/goal.py")
    at.text_area(key="goal_text").input("Basics of Investing for Beginners").run()
    at.button(key="goal_design").click().run()
    assert not calls and "You already have a goal like this" in texts(at), "asked first: no AI call"
    at.button(key="goal_dup_new").click().run()                     # it's different: designed after all
    assert len(calls) == 1 and has(at, "goal_add")


def test_continuing_a_paused_goal_instead(monkeypatch, tmp_path):
    # covers: D-goal-save_settings-3
    goal = dict(a_path(), title="Investing Basics for Beginners", status="archived")
    other = a_path()
    ai(monkeypatch)
    at = app(monkeypatch, tmp_path, subjects=(other["id"],), paths=[goal, other], history=False)
    loads(at, "views/goal.py")
    at.text_area(key="goal_text").input("Basics of Investing for Beginners").run()
    at.button(key="goal_design").click().run()
    at.button(key="goal_dup_go").click().run()
    s, log = stored(tmp_path)
    assert goal["id"] in s["subjects"] and next(p for p in log["paths"] if p["id"] == goal["id"])["status"] == "active"
    assert len(log["paths"]) == 2, "no second goal made"


def test_removing_a_goal_keeps_its_lessons_stops_its_reviews_and_can_be_undone(monkeypatch, tmp_path):
    # covers: W-settings-setgone_back, W-settings-set_removed
    import seed_history
    from coach import ui
    goal, other = a_path(), a_path()
    catalog.use([goal, other])
    entries = seed_history.build(ui.today(), days=3, topics=(goal["id"],))
    at = app(monkeypatch, tmp_path, subjects=(goal["id"], other["id"]), paths=[goal, other], entries=entries)
    log0 = {"entries": entries}
    assert any(e["topic"] == goal["id"] for e, _, _ in review.due(log0, ui.today(), limit=99)), "(its cards were due)"
    loads(at, "views/settings.py")
    at.button(key=f"setgoal_remove_{goal['id']}").click().run()          # an active goal can be removed
    t = texts(at)
    assert "Nothing is deleted" in t and "stay in your" in t
    at.button(key=f"setgoal_remove_go_{goal['id']}").click().run()
    s, log = stored(tmp_path)
    assert goal["id"] not in s["subjects"] and len(log["entries"]) == len(entries), "her lessons are kept"
    catalog.use(log["paths"])
    assert catalog.removed(goal["id"]) and not any(e["topic"] == goal["id"] for e, _, _ in review.due(log, ui.today(), limit=99))
    at.button(key=f"setgone_back_{goal['id']}").click().run()           # brought back, paused
    _, log = stored(tmp_path)
    assert next(p for p in log["paths"] if p["id"] == goal["id"])["status"] == "archived"


def test_the_only_thing_she_learns_isnt_removed(monkeypatch, tmp_path):
    goal = a_path()
    at = app(monkeypatch, tmp_path, subjects=(goal["id"],), paths=[goal], history=False)
    loads(at, "views/settings.py")
    at.button(key=f"setgoal_remove_{goal['id']}").click().run()
    at.button(key=f"setgoal_remove_go_{goal['id']}").click().run()
    s, _ = stored(tmp_path)
    assert s["subjects"] == [goal["id"]] and "Add another goal first" in texts(at)


# ---------------------------------------------------------------- 3. the outline's counts follow every tick
def _meta(at):
    import html
    import re
    return html.unescape(re.findall(r'gm-meta[^>]*>([^<]*)<', texts(at))[0])


def test_the_outline_counts_and_time_follow_each_tick_in_the_setup(monkeypatch, tmp_path):
    from test_goal_pages import to_goal
    ai(monkeypatch, design_reply())
    at = app(monkeypatch, tmp_path, subjects=(), history=False, onboarded=False)
    to_goal(at)
    at.text_area(key="obg_text").input("Read a company's financial statements").run()
    at.button(key="obg_design").click().run()
    assert _meta(at).startswith("16 lessons in 4 parts") and "about 6 study days at 3 a day" in _meta(at)
    at.segmented_control(key="obs_scope").set_value("some").run()
    at.checkbox(key="obs_part_0").uncheck().run()
    assert _meta(at).startswith("You chose 12 of 16 lessons (3 of 4 parts)") and "about 4 study days" in _meta(at)
    at.checkbox(key="obs_part_1").uncheck().run()
    at.checkbox(key="obs_part_2").uncheck().run()
    assert "4 of 16 lessons (1 of 4 parts)" in _meta(at)
    assert at.checkbox(key="obs_part_3").disabled, "the last part can't be unticked"


def test_the_outline_counts_follow_each_tick_on_add_a_goal(monkeypatch, tmp_path):
    ai(monkeypatch, design_reply())
    at = app(monkeypatch, tmp_path, subjects=("philosophy",), history=False)
    loads(at, "views/goal.py")
    at.text_area(key="goal_text").input("Read a company's financial statements").run()
    at.button(key="goal_design").click().run()
    at.segmented_control(key="gs_scope").set_value("some").run()
    at.checkbox(key="gs_part_3").uncheck().run()
    assert _meta(at).startswith("You chose 12 of 16 lessons"), "before adding it"


# ---------------------------------------------------------------- 4. more than one goal, taking turns
def test_the_order_of_her_days_can_be_set_from_today():
    from datetime import timezone
    from coach import clock
    a, b, c = a_path(), a_path(), a_path()
    catalog.use([a, b, c])
    s = dict(settings.blank("u"), subjects=[a["id"], b["id"], c["id"]], onboarded_at="2026-09-01T01:00:00+00:00")
    day = clock.today()
    now = [t for _, t in settings.days_ahead(s, day, timezone.utc)]
    want = [now[2], now[0], now[1]]
    moved = settings.order_from(s, want)
    assert [t for _, t in settings.days_ahead(moved, day, timezone.utc)] == want
    assert settings.order_from(s, want[:2]) == s, "never a turn lost"


def test_a_second_goal_says_how_the_days_are_shared(monkeypatch, tmp_path):
    # covers: W-goal-goal_order, W-daily-today_order
    first = a_path(title="Japanese for travel", goal="Japanese for a trip")
    ai(monkeypatch, design_reply())
    at = app(monkeypatch, tmp_path, subjects=(first["id"],), paths=[first], history=False)
    loads(at, "views/goal.py")
    at.text_area(key="goal_text").input("Read a company's financial statements").run()
    at.button(key="goal_design").click().run()
    all_of_it(at, "gs_scope")
    first_purpose(at, "gp")
    at.button(key="goal_add").click().run()
    t = texts(at)
    assert "take turns, one a day" in t and "first turn is today" in t
    assert "Today" in t and "Tomorrow" in t and first["title"] in t, "the coming days, in turn"
    assert at.button(key="goal_today").label == "Start its first lesson"
    at.button(key="goal_today").click().run()                 # (the press reruns the page: it must still go)
    assert "Made for you" in texts(at), "her first lesson, at once"
    loads(at, "views/daily.py")
    t = texts(at)
    assert "Today: Reading financial statements · Tomorrow: " + first["title"] in t and has(at, "today_order")


def test_her_days_can_be_reordered_in_learning_plan(monkeypatch, tmp_path):
    # covers: W-settings-setday_up, W-settings-setday_down, D-settings-save_settings-3
    from coach import ui
    a, b, c = a_path(), a_path(), a_path()
    at = app(monkeypatch, tmp_path, subjects=(a["id"], b["id"], c["id"]), paths=[a, b, c], history=False)
    loads(at, "views/settings.py")
    s, _ = stored(tmp_path)
    catalog.use([a, b, c])
    before = [t for _, t in settings.days_ahead(s, ui.today(), ui.TIMEZONE)]
    at.button(key="setday_up_2").click().run()                       # the third day's goal, a day earlier
    s, _ = stored(tmp_path)
    after = [t for _, t in settings.days_ahead(s, ui.today(), ui.TIMEZONE)]
    assert after == [before[0], before[2], before[1]] and "Moved" in texts(at)
    at.button(key="setday_down_0").click().run()
    s, _ = stored(tmp_path)
    assert [t for _, t in settings.days_ahead(s, ui.today(), ui.TIMEZONE)][:2] == [before[2], before[0]]


# ---------------------------------------------------------------- 7. old quizzes and lessons
from coach import quiz as quiz_                              # noqa: E402


def test_a_quiz_carries_the_rules_it_was_written_under():
    q = quiz_.new([{"type": "short", "question": "Why?", "answer": "Because.", "why": ""}])
    assert q["id"].startswith(f"v{quiz_.VERSION}-") and quiz_.version(q) == quiz_.VERSION and not quiz_.outdated(q)
    assert quiz_.parse_saved(q)["id"] == q["id"], "every store keeps it (it is the quiz's id)"
    old = dict(q, id="1a2b3c4d")
    assert quiz_.version(old) == 1 and quiz_.outdated(old)
    assert not quiz_.outdated(dict(old, answers=["x"])), "one she answered is her record"
    assert quiz_.outdated(quiz_.retire(q)) and not quiz_.has_draft(q)
    assert quiz_.has_draft(dict(q, draft=[None, "an answer"]))


def _today_with_an_old_quiz(draft=None):
    import seed_history
    from datetime import timedelta
    from coach import ui
    entries = seed_history.build(ui.today() + timedelta(days=1), days=1, topics=("philosophy",), partial=())
    e = entries[0]
    e["completed"] = False
    for s in e["lessons"]:
        s["completed"] = False
        s.pop("quiz", None)
    old = seed_history._quiz("1a2b3c4d", 5)
    old.update(answers=None, marks=None, feedback=None, score=None, attempts=1, best=50, draft=draft)
    e["lessons"][0]["quiz"] = old
    return entries


def test_an_old_unanswered_quiz_is_written_again_when_she_starts(monkeypatch, tmp_path):
    from coach import quizgen
    fresh = quiz_.parse_saved(_today_with_an_old_quiz()[0]["lessons"][0]["quiz"])["questions"]
    made = []
    monkeypatch.setattr(quizgen, "make", lambda *a, **k: (made.append(1) or fresh, None))
    at = app(monkeypatch, tmp_path, subjects=("philosophy",), entries=_today_with_an_old_quiz())
    said = " ".join(c.value for c in at.caption)
    assert "rewritten with our latest checks" in said and "Your earlier attempts still count" in said
    next(b for b in at.button if b.label in ("Try a new set", "Start the check")).click().run()
    _, log = stored(tmp_path)
    q = log["entries"][0]["lessons"][0]["quiz"]
    assert made and q["id"].startswith(f"v{quiz_.VERSION}-") and q["attempts"] == 1 and q["best"] == 50


def test_answers_started_on_an_old_quiz_are_hers_to_keep(monkeypatch, tmp_path):
    # covers: W-daily-quiz_renew_go
    at = app(monkeypatch, tmp_path, subjects=("philosophy",), entries=_today_with_an_old_quiz(draft=[0] + [None] * 9))
    assert "A newer, checked version of this quiz is available" in texts(at) and has(at, "quiz_renew_go")


def test_an_earlier_lesson_not_passed_can_be_rewritten(monkeypatch, tmp_path):
    # covers: W-daily-rewrite, AI-daily-stream_reply-3, D-daily-save_day-4
    import seed_history
    from coach import llm, ui
    entries = seed_history.build(ui.today(), days=1, topics=("philosophy",), partial=())
    e = entries[0]                                       # yesterday: lesson 1 written, not passed
    e["completed"] = False
    s0 = e["lessons"][0]
    s0["completed"] = False
    s0["quiz"] = dict(seed_history._quiz("1a2b3c4d", 5), answers=None, marks=None, feedback=None, score=None)
    e["lessons"] = [s0]
    monkeypatch.setattr(llm, "stream_reply", lambda *a, **k: ("【Topic】 Rewritten\n\n【Key Idea】 A clearer idea.", None))
    at = app(monkeypatch, tmp_path, subjects=("philosophy",), entries=entries)
    rewrite = [b for b in at.button if (b.key or "").startswith("rewrite_")]
    assert rewrite, "offered on a lesson carried over from an earlier day"
    rewrite[0].click().run()
    _, log = stored(tmp_path)
    s = next(x for x in log["entries"] if x["date"] == e["date"])["lessons"][0]
    assert "A clearer idea." in s["lesson"] and quiz_.outdated(s["quiz"]) and not s["completed"]
    assert "Rewritten with our latest guidelines" in texts(at)


# ---------------------------------------------------------------- 8. the setup, run again on an account in use
def test_running_the_setup_again_keeps_everything_and_adds_the_new_goal():
    from datetime import timezone
    old_goal, new = a_path(title="Japanese for travel"), a_path()
    catalog.use([old_goal, new])
    s = dict(settings.blank("u"), subjects=["philosophy", old_goal["id"]], subject_levels={"philosophy": "Advanced"},
             units_per_day=1, reading_enabled=True, onboarded_at="2026-09-01T01:00:00+00:00")
    again = settings.rerun(s, "2026-10-11T00:00:00+00:00")
    assert again["onboarded_at"] is None and again["subjects"] == s["subjects"], "nothing taken away yet"
    d = settings.draft_of(again)
    assert d["keep"] == ["philosophy", old_goal["id"]] and d["units_per_day"] == 1 and d["reading_enabled"]
    done = settings.finish(again, dict(d, path=new, scope="all", purpose="x"), "2026-10-11T00:00:00+00:00")
    assert done["subjects"] == [new["id"], "philosophy", old_goal["id"]], "the new goal first, then what she had"
    assert done["subject_levels"]["philosophy"] == "Advanced" and done["units_per_day"] == 1 and not settings.errors(done)
    assert settings.topic_for(done, settings.start_day(done, timezone.utc), timezone.utc) == new["id"]


def test_run_the_setup_again_is_offered_on_the_public_site_only(monkeypatch, tmp_path):
    at = app(monkeypatch, tmp_path, subjects=("philosophy",))
    loads(at, "views/account.py")
    assert not has(at, "acct_rerun"), "never in the personal app"


def test_the_test_tools_flag_offers_it_to_everyone_on_the_public_site(monkeypatch):
    # covers: S-gnosis_test_tools
    from coach import auth
    monkeypatch.setattr(auth, "is_admin", lambda: False)
    monkeypatch.setattr(auth, "is_public", lambda: True)
    monkeypatch.delenv("GNOSIS_TEST_TOOLS", raising=False)
    assert not auth.test_tools()
    monkeypatch.setenv("GNOSIS_TEST_TOOLS", "1")
    assert auth.test_tools()
    monkeypatch.setattr(auth, "is_public", lambda: False)
    assert not auth.test_tools(), "never in the personal app"
