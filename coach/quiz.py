"""The quiz at the end of each lesson: ten multiple-choice questions on
that lesson. Nine or more right (90%) completes the lesson and opens the
next one; otherwise she can take a fresh set of questions as often as she
likes.

A lesson's quiz lives in its slot, slot["quiz"]:
{"id", "questions": [{"question", "options", "answer", "why"}],
 "answers": the last submitted choices (or None), "score": that score in %,
 "attempts": how many times she has submitted, "best": best score in %}."""
import random
import uuid

QUESTIONS = 10
OPTIONS = 4
PASS_MARK = 90          # percent

SYSTEM = f"""You write a short quiz that checks whether a learner really understood one lesson.

Write exactly {QUESTIONS} multiple-choice questions about the lesson you are given, in English.
- Cover the whole lesson: the key idea, the deep dive, the example and the vocabulary.
- Test understanding (why, how, what follows, which example fits), not trivia about wording.
- Each question has exactly {OPTIONS} short options and exactly one correct answer; the wrong
  options are plausible to someone who skimmed. No "all of the above" or "none of the above".
- Only ask about what the lesson actually says.
- "why" is one sentence explaining the correct answer, for when she gets it wrong.

Reply with JSON only, in this shape:
{{"questions": [{{"question": "...", "options": ["...", "...", "...", "..."], "answer": 0, "why": "..."}}]}}
where "answer" is the index (0-{OPTIONS - 1}) of the correct option."""


def request(slot: dict):
    """(system, messages) for generating this lesson's quiz."""
    lesson = f"Lesson {slot['n']}: {slot['title']}\n\n{slot['lesson']}"
    return SYSTEM, [{"role": "user", "content": lesson}]


def _question(item, rng):
    """One validated question with its options shuffled, or None."""
    if not isinstance(item, dict):
        return None
    question, options, answer = item.get("question"), item.get("options"), item.get("answer")
    if not isinstance(question, str) or not question.strip():
        return None
    if not isinstance(options, list) or len(options) != OPTIONS:
        return None
    options = [str(o).strip() for o in options]
    if not all(options) or len(set(options)) != OPTIONS:
        return None
    if not isinstance(answer, int) or isinstance(answer, bool) or not 0 <= answer < OPTIONS:
        return None
    correct = options[answer]
    rng.shuffle(options)          # models like to put the answer first
    return {"question": question.strip(), "options": options,
            "answer": options.index(correct), "why": str(item.get("why") or "").strip()}


def parse(data, rng=random) -> list:
    """The quiz's questions from the model's JSON, or None if there aren't
    {QUESTIONS} usable ones."""
    items = data.get("questions") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return None
    questions = [q for q in (_question(item, rng) for item in items) if q]
    return questions[:QUESTIONS] if len(questions) >= QUESTIONS else None


def new(questions: list, previous=None) -> dict:
    """A fresh quiz; attempts and the best score carry over from the last one."""
    previous = previous or {}
    return {"id": uuid.uuid4().hex[:8], "questions": questions, "answers": None, "score": None,
            "attempts": previous.get("attempts", 0), "best": previous.get("best")}


def grade(quiz: dict, answers: list) -> int:
    """Record a submission and return its score in percent."""
    right = sum(1 for q, a in zip(quiz["questions"], answers) if a == q["answer"])
    score = round(right / len(quiz["questions"]) * 100)
    quiz["answers"], quiz["score"] = list(answers), score
    quiz["attempts"] = quiz.get("attempts", 0) + 1
    quiz["best"] = max(score, quiz.get("best") or 0)
    return score


def passed(score) -> bool:
    return score is not None and score >= PASS_MARK


def parse_saved(data):
    """Validate a saved quiz (from the database or a backup), or None."""
    if not isinstance(data, dict) or not isinstance(data.get("questions"), list):
        return None
    questions = []
    for q in data["questions"]:
        if (isinstance(q, dict) and isinstance(q.get("question"), str)
                and isinstance(q.get("options"), list) and len(q["options"]) == OPTIONS
                and isinstance(q.get("answer"), int) and 0 <= q["answer"] < OPTIONS):
            questions.append({"question": q["question"], "options": [str(o) for o in q["options"]],
                              "answer": q["answer"], "why": str(q.get("why") or "")})
    if len(questions) != len(data["questions"]) or not questions:
        return None
    answers = data.get("answers")
    if not (isinstance(answers, list) and len(answers) == len(questions)):
        answers = None
    number = lambda v: v if isinstance(v, int) and not isinstance(v, bool) else None  # noqa: E731
    return {"id": str(data.get("id") or uuid.uuid4().hex[:8]), "questions": questions, "answers": answers,
            "score": number(data.get("score")) if answers else None,
            "attempts": number(data.get("attempts")) or 0, "best": number(data.get("best"))}
