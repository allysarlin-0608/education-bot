"""Phase 3's pages without a browser (part of the check before every push):
the skill map (empty, several subjects, nothing shaky), a whole practice set
and the next one, the ways in from Today, Progress and the week, explaining
it back offered after a lesson is passed, the course map's levels."""
from datetime import timedelta

from coach import mastery, ui
from test_habit_pages import has, history_until
from test_habit_pages import texts as _texts
from test_pages_smoke import app, loads


def texts(at):
    """Everything on the page, captions too."""
    return _texts(at) + " " + " ".join(c.value for c in at.caption)


def test_the_skill_map_before_any_lesson(monkeypatch, tmp_path):
    # covers: W-skills-sk_back
    at = app(monkeypatch, tmp_path, history=False)
    loads(at, "views/skills.py")
    assert "Your map starts with your first lesson" in texts(at)
    at.button(key="sk_back").click().run()
    assert not at.exception


def test_the_skill_map_with_two_subjects(monkeypatch, tmp_path):
    # covers: W-skills-sk_pick, W-skills-sk_practice, W-skills-sk_course, W-skills-sk_today
    at = app(monkeypatch, tmp_path, entries=history_until(ui.today() - timedelta(days=1)))
    loads(at, "views/skills.py")
    t = texts(at)
    assert "Knowledge Map" in t and "learning" in t and "Learning" in t and "ideas met" in t
    assert has(at, "sk_practice") and "shakiest" in str(at.button(key="sk_practice").proto.label)
    other = [x for x in at.segmented_control[0].options if x != at.segmented_control[0].value][0]
    at.segmented_control[0].set_value(other).run()
    assert not at.exception and at.session_state["sk_topic"] != "" and "ideas met" in texts(at)
    at.button(key="sk_course").click().run()
    assert not at.exception
    loads(at, "views/skills.py")
    at.button(key="sk_today").click().run()
    assert not at.exception


def solid_history():
    """Every lesson of the seeded history known on two days: nothing shaky."""
    entries = history_until(ui.today() - timedelta(days=1), days=4, topics=("philosophy",))
    for e in entries:
        for s in e["lessons"]:
            s["ev"] = [mastery.event("quiz", 1.0, ui.today() - timedelta(days=2), "a"),
                       mastery.event("review", 1.0, ui.today() - timedelta(days=1), "b")]
    return entries


def test_nothing_shaky_the_map_still_offers_practice_and_today_doesnt_push_it(monkeypatch, tmp_path):
    # covers: W-skills-sk_practice_any
    at = app(monkeypatch, tmp_path, entries=solid_history(), subjects=("philosophy",))
    loads(at, "views/skills.py")
    assert not has(at, "sk_practice") and has(at, "sk_practice_any") and "Solid" in texts(at)
    at.button(key="sk_practice_any").click().run()
    assert not at.exception
    loads(at, "views/daily.py")
    assert not has(at, "today_practice"), "nothing shaky: Today doesn't push practice"


def answer_right(at):
    """Answer the exercise on screen (the seeded quizzes: "Right" is right)."""
    radio = at.radio[0]
    radio.set_value(radio.options.index("Right")).run()


def test_a_whole_practice_set_then_the_next_one(monkeypatch, tmp_path):
    # covers: W-practice-pr_start, W-practice-check, W-practice-pr_next, W-practice-pr_more, W-practice-pr_map,
    # covers: W-practice-pr_today, W-daily-today_practice, D-practice-save_day
    at = app(monkeypatch, tmp_path, entries=history_until(ui.today() - timedelta(days=1), topics=("philosophy",)),
             subjects=("philosophy",))
    loads(at, "views/daily.py")
    assert has(at, "today_practice") and "ideas to strengthen" in str(at.button(key="today_practice").proto.label)
    at.button(key="today_practice").click().run()
    loads(at, "views/practice.py")
    assert "Focus for today" in texts(at) and "6 short exercises" in texts(at)
    at.button(key="pr_start").click().run()
    for k in range(6):
        assert f"{k} of 6 done" in texts(at), k
        answer_right(at)
        check = next(b for b in at.button if str(b.key).endswith("_check"))
        check.click().run()
        assert "Right." in texts(at)
        at.button(key="pr_next").click().run()
    t = texts(at)
    assert "Practice done" in t and "6 of 6 right" in t
    p = at.session_state["coach_prefs"]
    assert p["practice"]["done"] and None not in p["practice"]["marks"]
    log = at.session_state["coach_log"]
    practised = [e for x in log["entries"] for s in x["lessons"] for e in s.get("ev") or [] if e["k"] == "practice"]
    assert len(practised) == 6, "each answer is evidence for its idea, saved"
    assert has(at, "pr_more"), "more shaky ideas wait: another set is offered"
    at.button(key="pr_more").click().run()
    at.button(key="pr_start").click().run()
    assert "0 of 6 done" in texts(at)
    first = at.session_state["coach_prefs"]["practice"]["items"][0]
    assert (first["topic"], first["n"]) not in {(e["topic"], s["n"]) for e in log["entries"] for s in e["lessons"]
                                                if sum(1 for v in s.get("ev") or [] if v["k"] == "practice") >= 2}
    for _ in range(6):                                        # this set too, then its end
        answer_right(at)
        next(b for b in at.button if str(b.key).endswith("_check")).click().run()
        at.button(key="pr_next").click().run()
    assert "Practice done" in texts(at)
    at.button(key="pr_map").click().run()
    assert not at.exception
    loads(at, "views/practice.py")
    at.button(key="pr_today").click().run()
    assert not at.exception


def test_the_ways_in_from_progress_and_the_week(monkeypatch, tmp_path):
    # covers: W-records-prog_skills_open, W-week-wk_skills, W-daily-today_skills
    at = app(monkeypatch, tmp_path, entries=history_until(ui.today() - timedelta(days=1)))
    loads(at, "views/records.py")
    t = texts(at)
    assert "Ideas mastered" in t and "What you know:" in t and "still being learned" in t
    at.button(key="prog_skills_open").click().run()
    assert not at.exception
    loads(at, "views/week.py")
    assert "What you know" in texts(at)
    at.button(key="wk_skills").click().run()
    assert not at.exception
    loads(at, "views/daily.py")
    at.button(key="today_skills").click().run()
    assert not at.exception


def test_the_course_map_shows_each_ideas_level(monkeypatch, tmp_path):
    # covers: W-course-cm_skills
    at = app(monkeypatch, tmp_path, entries=solid_history(), subjects=("philosophy",))
    loads(at, "views/course.py", subject="philosophy")
    t = texts(at)
    assert "sk-chip sk-solid" in t and "solid or mastered" in t
    at.button(key="cm_skills").click().run()
    assert not at.exception and at.session_state["sk_topic"] == "philosophy"


def test_practice_before_any_quiz(monkeypatch, tmp_path):
    # covers: W-practice-pr_back
    at = app(monkeypatch, tmp_path, history=False)
    loads(at, "views/practice.py")
    assert "Nothing to practise yet" in texts(at)
    at.button(key="pr_back").click().run()
    assert not at.exception


def test_explain_it_back_is_offered_once_a_lesson_is_passed(monkeypatch, tmp_path):
    import seed_history
    from coach import settings
    at = app(monkeypatch, tmp_path, entries=history_until(ui.today() - timedelta(days=1), topics=("philosophy",)),
             subjects=("philosophy",), pace=1)
    log = at.session_state["coach_log"]
    today = ui.today().isoformat()
    topic = settings.topic_for(at.session_state["coach_settings"], ui.today(), ui.TIMEZONE)
    done = seed_history.build(ui.today() + timedelta(days=1), days=1, topics=(topic,), per_day=1)
    for e in done:
        e["date"] = today
    log["entries"] = [e for e in log["entries"] if e["date"] != today] + done
    at.session_state[f"lesson_{today}_{topic}"] = 0          # the passed lesson, open
    loads(at, "views/daily.py")
    t = texts(at)
    assert "Explain it back" in t and "This idea:" in t and has(at, "explain_send")
    at.text_area(key=f"explain_{ui.today()}_{done[0]['lessons'][0]['n']}").input("Too short.").run()
    at.button(key="explain_send").click().run()
    assert not at.exception and any("A little more" in w.value for w in at.warning), "no call for too little"
