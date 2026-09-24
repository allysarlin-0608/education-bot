"""The quiz at the end of each lesson: ten questions on that lesson, of
three kinds, so it checks understanding from different angles:

- "choice": multiple choice, four options, one right (1 point)
- "match":  pair four terms with their meanings (1 point, a quarter per pair)
- "short":  a one- or two-sentence answer in her own words, marked by the
            model against a model answer (1 point)

Every quiz is checked by a second model call before she sees it (is each
keyed answer factually right and the only defensible one?); questions that
fail are rewritten and checked again.

Eight points or more (80%) completes the lesson; otherwise she can take a
fresh set of questions as often as she likes.

A lesson's quiz lives in its slot, slot["quiz"]:
{"id", "questions", "answers": her last submitted answers (or None),
 "marks": points per question (None for a short answer not marked yet),
 "feedback": a line per question (short answers), "score": % once every
 question is marked, "attempts", "best", "draft": answers given so far,
 saved as she goes, until she submits}. Quizzes saved before question
kinds existed are all multiple choice."""
import random
import uuid

QUESTIONS = 10
OPTIONS = 4
PAIRS = 4
PASS_MARK = 80          # percent
MIX = {"choice": 7, "match": 1, "short": 2}
CHECK_ROUNDS = 2        # rewrite-and-recheck rounds before giving up

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

Correctness comes first:
- The keyed answer must be factually correct in the real world, not just in the lesson, and it
  must be the only correct option. If you are not completely sure a fact is right, don't ask
  about it; ask about something else. (For example: pure gold is soft; alloys are harder.)
- No two options may both be defensible. Every wrong option must be clearly wrong on reflection.
- If a question asks for the most common, main, best or usual thing, the true answer must be
  among the options.
- Matching pairs and model answers must be correct too.

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
not as wording she must match.
"feedback" is one or two short, kind sentences in English. If the answer is correct, say what she
got right. If it is not, say specifically why: what is wrong or what key point is missing.

Reply with JSON only: {"results": [{"id": 0, "correct": true, "feedback": "..."}]}, one entry per id."""

CHECKER = """You check a quiz before a learner sees it. For each question, decide whether it is sound:
- "choice": the keyed answer is factually correct in the real world and is the ONLY defensible
  option; no other option could also be argued to be right; if it asks for the most common, main,
  best or usual thing, the true answer is among the options.
- "match": every pair is factually correct and no term could reasonably match a different meaning.
- "short": the model answer is factually correct and answers the question.
Judge by real-world facts, not only by what a lesson might have said.

Reply with JSON only: {"problems": [{"id": 0, "issue": "one sentence"}]} listing only the questions
with a problem; {"problems": []} if every question is sound."""


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
    questions = parse_items(data, rng)
    if len(questions) < QUESTIONS:
        return None
    order = list(KINDS)
    return sorted(questions[:QUESTIONS], key=lambda q: order.index(q["type"]))


def _describe(k: int, q: dict) -> str:
    if q["type"] == "choice":
        opts = "\n".join(f"  {'*' if j == q['answer'] else '-'} {o}" for j, o in enumerate(q["options"]))
        return f"id {k} (choice): {q['question']}\n{opts}\n  (* = keyed answer)"
    if q["type"] == "match":
        pairs = "\n".join(f"  {left} = {q['right'][key]}" for left, key in zip(q["left"], q["key"]))
        return f"id {k} (match): {q['question']}\n{pairs}"
    return f"id {k} (short): {q['question']}\n  model answer: {q['answer']}"


def check_request(questions: list):
    """(system, messages) asking the model to vet every question."""
    return CHECKER, [{"role": "user", "content": "\n\n".join(_describe(k, q) for k, q in enumerate(questions))}]


def problems(data, n: int):
    """{id: issue} for the questions the checker flagged, or None if its
    reply can't be read."""
    items = data.get("problems") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return None
    out = {}
    for item in items:
        if isinstance(item, dict) and isinstance(item.get("id"), int) and 0 <= item["id"] < n:
            out[item["id"]] = _text(item.get("issue")) or "flagged"
    return out


def rewrite_request(slot: dict, questions: list, flagged: dict):
    """(system, messages) asking for replacements for the flagged questions,
    same kinds, different content."""
    kinds = [questions[k]["type"] for k in sorted(flagged)]
    wanted = ", ".join(f'{kinds.count(t)} "{t}"' for t in KINDS if t in kinds)
    avoid = "\n".join(f"- {questions[k]['question']} (problem: {issue})" for k, issue in sorted(flagged.items()))
    keep = "\n".join(f"- {q['question']}" for k, q in enumerate(questions) if k not in flagged)
    system = SYSTEM.split("Reply with JSON only")[0].replace(
        f"Write exactly {QUESTIONS} questions about the lesson you are given, in English, in this mix:",
        f"Write exactly {len(flagged)} replacement questions ({wanted}) about the lesson you are given, "
        "in English. The kinds are:")
    system += ("Reply with JSON only, in the same shape as before: "
               '{"questions": [{"type": "choice" | "match" | "short", ...}]}.')
    user = (f"Lesson {slot['n']}: {slot['title']}\n\n{slot['lesson']}\n\n"
            f"These questions had problems; write different ones:\n{avoid}\n\n"
            f"Don't repeat the questions already in the quiz:\n{keep}")
    return system, [{"role": "user", "content": user}]


def parse_items(data, rng=random) -> list:
    """Every usable question in the model's JSON, in the order given."""
    items = data.get("questions") if isinstance(data, dict) else None
    out = []
    for item in items if isinstance(items, list) else []:
        if isinstance(item, dict):
            kind = item.get("type", "choice")
            q = KINDS[kind](item, rng) if kind in KINDS else None
            if q:
                out.append(q)
    return out


def replace(questions: list, flagged: dict, fresh: list):
    """The quiz with each flagged question swapped for a fresh one of the
    same kind, or None if the fresh ones don't cover every kind needed."""
    fresh = list(fresh)
    out = list(questions)
    for k in sorted(flagged):
        match = next((f for f in fresh if f["type"] == questions[k]["type"]), None)
        if match is None:
            return None
        fresh.remove(match)
        out[k] = match
    return out


def new(questions: list, previous=None) -> dict:
    """A fresh quiz; attempts and the best score carry over from the last one."""
    previous = previous or {}
    return {"id": uuid.uuid4().hex[:8], "questions": questions, "answers": None, "marks": None,
            "feedback": None, "score": None, "attempts": previous.get("attempts", 0),
            "best": previous.get("best"), "draft": None}


def blank_draft(quiz: dict) -> list:
    """Unanswered: None for choice, a None per term for matching, "" for short."""
    return [[None] * len(q["left"]) if q["type"] == "match" else ("" if q["type"] == "short" else None)
            for q in quiz["questions"]]


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
    quiz["draft"] = None
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
    draft = data.get("draft")
    if not (answers is None and isinstance(draft, list) and len(draft) == n):
        draft = None
    return {"id": str(data.get("id") or uuid.uuid4().hex[:8]), "questions": questions, "answers": answers,
            "marks": marks, "feedback": feedback,
            "score": number(data.get("score")) if answers is not None else None,
            "attempts": number(data.get("attempts")) or 0, "best": number(data.get("best")), "draft": draft}
