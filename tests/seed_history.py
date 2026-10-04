"""A learner's history, built with the app's own code (so it has exactly the
shape the app writes): used by the E2E tests (fake database / local file)
and by tools/seed_test_db.py (the TEST Supabase project only).

    entries = build(today, days=35, topics=["philosophy", "psychology"])
"""
from datetime import date, timedelta

from coach import core, curriculum

LESSON = ("【Topic】 A seeded lesson\n\n【Key Idea】 Seeded key idea.\n\n【Deep Dive】 Seeded detail.\n\n"
          "【Example】 Seeded example.\n\n【Today's Task】 Seeded task.\n\n"
          "【Vocabulary】 seed｜a start｜A seed grows.\n\n【Question to Explore】 What grows from a seed?\n\n"
          "【Note】 Keep going.")


def _quiz(qid, right, total=10):
    """A marked quiz as the app saves it: `right` of `total` choice questions."""
    questions = [{"type": "choice", "question": f"Seeded question {k + 1}?",
                  "options": ["Right", "Wrong", "Also wrong", "No"], "answer": 0, "why": "Seeded."}
                 for k in range(total)]
    answers = [0 if k < right else 1 for k in range(total)]
    score = round(100 * right / total)
    return {"id": qid, "questions": questions, "answers": answers,
            "marks": [1 if a == 0 else 0 for a in answers], "feedback": [""] * total,
            "score": score, "attempts": 1, "best": score, "draft": None}


def build(today: date, days: int = 35, topics=("philosophy",), per_day: int = 3,
          gaps=(3, 4, 17), partial=(9, 22)) -> list:
    """`days` days before today, one subject a day in turn. Days `gaps` (days
    ago) have no entry; days `partial` passed one lesson of the day only;
    every other day is complete (scores 80-100)."""
    log = {"entries": []}
    for ago in range(days, 0, -1):
        if ago in gaps:
            continue
        day = today - timedelta(days=ago)
        topic = topics[ago % len(topics)]
        entry = core.start_entry(log, day, topic)
        slots = curriculum.day_plan(log, topic, None, per_day)
        passed = 1 if ago in partial else len(slots)
        for k, s in enumerate(slots):
            s["kickoff"] = f"Lesson {s['n']}"
            s["lesson"] = LESSON.replace("A seeded lesson", s["title"])
            if k < passed:
                right = 8 + (ago + k) % 3                      # 8, 9 or 10 of 10: 80-100%
                s["completed"] = True
                s["quiz"] = _quiz(f"s{ago}{k}", right)
        for s in slots:
            s.pop("cards", None)     # history as earlier versions saved it (before review cards existed)
        entry["lessons"] = slots
        entry["completed"] = curriculum.day_complete(slots)
        entry["title"] = f"Lessons {slots[0]['n']}–{slots[-1]['n']}"
        entry["followup_question"] = "What grows from a seed?"
    return log["entries"]


def expected(entries, today: date) -> dict:
    """The figures Progress should show for these entries (from the app's
    own definitions)."""
    log = {"entries": entries}
    return {
        "current_streak": core.current_streak(log, today),
        "longest_streak": core.longest_streak(log),
        "days_completed": len(core.completed_dates(log)),
        "days_studied": len({e["date"] for e in entries}),
        "lessons_passed": sum(sum(1 for s in e["lessons"] if s["completed"]) for e in entries),
    }
