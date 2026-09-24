"""The quiz at the end of each lesson: ten questions on that lesson, of
three kinds, so it checks understanding from different angles:

- "choice": multiple choice, four options, one right (1 point)
- "match":  pair four terms with their meanings (1 point, a quarter per pair)
- "short":  a one- or two-sentence answer in her own words, marked by the
            model against a model answer (1 point)

Nine points or more (90%) completes the lesson and opens the next one;
otherwise she can take a fresh set of questions as often as she likes.

A lesson's quiz lives in its slot, slot["quiz"]:
{"id", "questions", "answers": her last submitted answers (or None),
 "marks": points per question (None for a short answer not marked yet),
 "feedback": a line per question (short answers), "score": % once every
 question is marked, "attempts", "best"}. Quizzes saved before question
kinds existed are all multiple choice."""
import random
import uuid

QUESTIONS = 10
OPTIONS = 4
PAIRS = 4
PASS_MARK = 90          # percent
MIX = {"choice": 6, "match": 1, "short": 3}

SYSTEM = f"""You write a short quiz that checks whether a learner really understood one lesson.

Write exactly {QUESTIONS} questions about the lesson you are given, in English, in this mix:
- {MIX["choice"]} "choice" questions: exactly {OPTIONS} short options, exactly one correct; the wrong
  options are plausible to someone who skimmed. No "all of the above" / "none of the above".
- {MIX["match"]} "match" question: exactly {PAIRS} pairs linking a term, name or idea from the lesson
  to its meaning or example (each side a few words, all different).
- {MIX["short"]} "short" questions she answers in one or two sentences in her own words: ask her to
  explain why or how, apply an idea to a new case, or compare two things. Give a model answer.
Cover the whole lesson (key idea, deep dive, example, vocabulary) and test understanding, not
wording. Only ask about what the lesson actually says. "why" is one sentence explaining the answer.

Reply with JSON only, in this shape (questions in any order):
{{"questions": [
  {{"type": "choice", "question": "...", "options": ["...", "...", "...", "..."], "answer": 0, "why": "..."}},
  {{"type": "match", "question": "Match each term to its meaning.", "pairs": [["term", "meaning"], ...], "why": "..."}},
  {{"type": "short", "question": "...", "answer": "a model answer", "why": "..."}}
]}}
"answer" in a choice question is the index (0-{OPTIONS - 1}) of the correct option."""

GRADER = """You mark a learner's short answers to questions about a lesson she just studied.
For each answer decide whether it shows she understood the point the question asks about. Her own
words are fine and grammar or spelling mistakes don't matter, but the answer must be correct and
specific enough; vague, off-topic or empty answers are not correct. Use the model answer as a guide,
not as wording she must match. Give one short, kind sentence of feedback in English saying what was
right or what was missing.

Reply with JSON only: {"results": [{"id": 0, "correct": true, "feedback": "..."}]}, one entry per id."""


def request(slot: dict):
    """(system, messages) for writing this lesson's quiz."""
    lesson = f"Lesson {slot['n']}: {slot['title']}\n\n{slot['lesson']}"
    return SYSTEM, [{"role": "user", "content": lesson}]


def _text(value) -> str:
    return str(value).strip() if isinstance(value, (str, int, float)) and not isinstance(value, bool) else ""


def _choice(item, rng):
    question, options, answer = _text(item.get("question")), item.get("options"), item.get("answer")
    if not question or not isinstance(options, list) or len(options) != OPTIONS:
        return None
    options = [_text(o) for o in options]
    if not all(options) or len(set(options)) != OPTIONS:
        return None
    if not isinstance(answer, int) or isinstance(answer, bool) or not 0 <= answer < OPTIONS:
        return None
    correct = options[answer]
    rng.shuffle(options)          # models like to put the answer first
    return {"type": "choice", "question": question, "options": options,
            "answer": options.index(correct), "why": _text(item.get("why"))}


def _match(item, rng):
    pairs = item.get("pairs")
    if not isinstance(pairs, list) or len(pairs) != PAIRS:
        return None
    if not all(isinstance(p, list) and len(p) == 2 for p in pairs):
        return None
    left = [_text(p[0]) for p in pairs]
    right = [_text(p[1]) for p in pairs]
    if not all(left + right) or len(set(left)) != PAIRS or len(set(right)) != PAIRS:
        return None
    shuffled = right[:]
    rng.shuffle(shuffled)
    return {"type": "match", "question": _text(item.get("question")) or "Match each term to its meaning.",
            "left": left, "right": shuffled, "key": [shuffled.index(r) for r in right],
            "why": _text(item.get("why"))}


def _short(item, rng):
    question, answer = _text(item.get("question")), _text(item.get("answer"))
    if not question or not answer:
        return None
    return {"type": "short", "question": question, "answer": answer, "why": _text(item.get("why"))}


KINDS = {"choice": _choice, "match": _match, "short": _short}


def parse(data, rng=random) -> list:
    """The quiz's questions from the model's JSON, or None if there aren't
    QUESTIONS usable ones. Multiple choice comes first, then matching,
    then short answers."""
    items = data.get("questions") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return None
    questions = []
    for item in items:
        if isinstance(item, dict):
            kind = item.get("type", "choice")
            q = KINDS[kind](item, rng) if kind in KINDS else None
            if q:
                questions.append(q)
    if len(questions) < QUESTIONS:
        return None
    order = list(KINDS)
    return sorted(questions[:QUESTIONS], key=lambda q: order.index(q["type"]))


def new(questions: list, previous=None) -> dict:
    """A fresh quiz; attempts and the best score carry over from the last one."""
    previous = previous or {}
    return {"id": uuid.uuid4().hex[:8], "questions": questions, "answers": None, "marks": None,
            "feedback": None, "score": None, "attempts": previous.get("attempts", 0),
            "best": previous.get("best")}


def answered(question: dict, answer) -> bool:
    if question["type"] == "choice":
        return answer is not None
    if question["type"] == "match":
        return isinstance(answer, list) and None not in answer
    return bool(_text(answer))


def _mark(question: dict, answer):
    """Points for one answer; None for a short answer (the model marks those)."""
    if question["type"] == "choice":
        return 1.0 if answer == question["answer"] else 0.0
    if question["type"] == "match":
        return sum(1 for a, k in zip(answer or [], question["key"]) if a == k) / len(question["key"])
    return None


def submit(quiz: dict, answers: list) -> bool:
    """Record a submission and mark what can be marked here. Returns True
    if short answers still need the model."""
    quiz["answers"] = list(answers)
    quiz["marks"] = [_mark(q, a) for q, a in zip(quiz["questions"], answers)]
    quiz["feedback"] = [""] * len(answers)
    quiz["score"] = None
    return needs_grading(quiz)


def needs_grading(quiz: dict) -> bool:
    return quiz.get("answers") is not None and None in (quiz.get("marks") or [None])


def grading_request(quiz: dict):
    """(system, messages) asking the model to mark the short answers."""
    lines = []
    for k, (q, a) in enumerate(zip(quiz["questions"], quiz["answers"])):
        if q["type"] == "short":
            lines.append(f"id {k}\nQuestion: {q['question']}\nModel answer: {q['answer']}\nHer answer: {a}")
    return GRADER, [{"role": "user", "content": "\n\n".join(lines)}]


def apply_grading(quiz: dict, data) -> bool:
    """Take the model's marks for the short answers. False if any is missing."""
    results = data.get("results") if isinstance(data, dict) else None
    if not isinstance(results, list):
        return False
    by_id = {r.get("id"): r for r in results if isinstance(r, dict) and isinstance(r.get("id"), int)}
    marks, feedback = list(quiz["marks"]), list(quiz["feedback"])
    for k, q in enumerate(quiz["questions"]):
        if q["type"] != "short":
            continue
        r = by_id.get(k)
        if r is None or not isinstance(r.get("correct"), bool):
            return False
        marks[k], feedback[k] = (1.0 if r["correct"] else 0.0), _text(r.get("feedback"))
    quiz["marks"], quiz["feedback"] = marks, feedback
    return True


def finish(quiz: dict) -> int:
    """Once every question is marked: the score in percent (and attempts, best)."""
    score = round(sum(quiz["marks"]) / len(quiz["questions"]) * 100)
    quiz["score"] = score
    quiz["attempts"] = quiz.get("attempts", 0) + 1
    quiz["best"] = max(score, quiz.get("best") or 0)
    return score


def passed(score) -> bool:
    return score is not None and score >= PASS_MARK


def points(quiz: dict) -> str:
    """ "8.5 of 10" style."""
    return f"{sum(quiz['marks']):g} of {len(quiz['questions'])}"


def _saved_question(q):
    if not isinstance(q, dict) or not _text(q.get("question")):
        return None
    kind = q.get("type", "choice")
    base = {"type": kind, "question": _text(q["question"]), "why": _text(q.get("why"))}
    if kind == "choice":
        options, answer = q.get("options"), q.get("answer")
        if (isinstance(options, list) and len(options) == OPTIONS and isinstance(answer, int)
                and not isinstance(answer, bool) and 0 <= answer < OPTIONS):
            return {**base, "options": [str(o) for o in options], "answer": answer}
    elif kind == "match":
        left, right, key = q.get("left"), q.get("right"), q.get("key")
        if (isinstance(left, list) and isinstance(right, list) and isinstance(key, list)
                and len(left) == len(right) == len(key) > 0
                and sorted(k for k in key if isinstance(k, int)) == list(range(len(key)))):
            return {**base, "left": [str(x) for x in left], "right": [str(x) for x in right], "key": key}
    elif kind == "short" and _text(q.get("answer")):
        return {**base, "answer": _text(q["answer"])}
    return None


def parse_saved(data):
    """Validate a saved quiz (from the database or a backup), or None."""
    if not isinstance(data, dict) or not isinstance(data.get("questions"), list) or not data["questions"]:
        return None
    questions = [_saved_question(q) for q in data["questions"]]
    if None in questions:
        return None
    n = len(questions)
    answers = data.get("answers")
    if not (isinstance(answers, list) and len(answers) == n):
        answers = None
    marks = data.get("marks")
    if answers is None:
        marks = None
    elif not (isinstance(marks, list) and len(marks) == n):
        # saved before question kinds (all multiple choice): mark from the answers
        marks = [_mark(q, a) for q, a in zip(questions, answers)]
    feedback = data.get("feedback")
    if answers is None:
        feedback = None
    elif not (isinstance(feedback, list) and len(feedback) == n):
        feedback = [""] * n
    number = lambda v: v if isinstance(v, int) and not isinstance(v, bool) else None  # noqa: E731
    return {"id": str(data.get("id") or uuid.uuid4().hex[:8]), "questions": questions, "answers": answers,
            "marks": marks, "feedback": feedback,
            "score": number(data.get("score")) if answers is not None else None,
            "attempts": number(data.get("attempts")) or 0, "best": number(data.get("best"))}
