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
import json
import random
import re
import uuid

QUESTIONS = 10
OPTIONS = 4
PAIRS = 4
STEPS = (3, 5)          # an ordering question has 3 to 5 steps
PASS_MARK = 80          # percent
# The mix she gets (ten questions). An ordering question only when the lesson
# has a real sequence; otherwise another scenario takes its place.
MIX = {"choice": 3, "scenario": 2, "blank": 1, "order": 1, "match": 1, "short": 1, "apply": 1}
LOCAL = ("choice", "scenario", "blank", "order", "match")     # marked here, at once
WRITTEN = ("short", "apply")                                  # marked by the model
KIND_NAMES = {"choice": "Multiple choice", "scenario": "Scenario", "blank": "Fill in the blank",
              "order": "Put in order", "match": "Matching", "short": "In your own words",
              "apply": "Apply it to your life"}
CHECK_ROUNDS = 2        # rewrite-and-recheck rounds before giving up
RECOVERIES = 2          # extra calls when the questions come back incomplete (views/daily.py)
FILL_AT_MOST = 4        # up to this many missing: ask for just those; more: the whole quiz again
BLANK = re.compile(r"_{3,}")

SYSTEM = f"""You write a short quiz that checks whether a learner really understood one lesson.

Write exactly {QUESTIONS} questions about the lesson you are given, in English, in this mix:
- {MIX["choice"]} "choice" questions: exactly {OPTIONS} short options, exactly one correct; the wrong
  options are plausible to someone who skimmed. No "all of the above" / "none of the above".
  "notes" gives, for each option in the same order, a few words on why it is wrong ("" for the
  right one): the mistake a learner who picked it made.
- {MIX["scenario"]} "scenario" questions: a short, concrete situation (2-3 sentences) where the idea
  applies, then a question with {OPTIONS} options and "notes", as for "choice". Test using the idea,
  not remembering words.
- {MIX["blank"]} "blank" question: one sentence from the idea with one key word or short phrase
  replaced by "____". Only one word or phrase can fit; list close variants that are also right
  (plural, synonym, spelling) in "accept".
- {MIX["order"]} "order" question, ONLY if the lesson has a real sequence (steps of a method, stages,
  events in time): 3-5 short steps listed in the correct order, with exactly one defensible order.
  If the lesson has no real sequence, write one more "scenario" question instead.
- {MIX["match"]} "match" question: exactly {PAIRS} pairs linking a term, name or idea from the lesson
  to its meaning or example (each side a few words, all different).
- {MIX["short"]} "short" question she answers in one or two sentences in her own words: explain why or
  how, or compare two things. Give a model answer.
- {MIX["apply"]} "apply" question: she applies the idea to her own life, work or goal (see "Her goal" if
  given). Ask for one concrete example; in "answer", say what a good answer must show (the criteria).
Cover the whole lesson (key idea, deep dive, example, vocabulary) and test understanding, not
wording. Only ask about what the lesson actually says. "why" is one sentence explaining the answer.

Correctness comes first:
- The keyed answer must be factually correct in the real world, not just in the lesson, and it
  must be the only correct option. If you are not completely sure a fact is right, don't ask
  about it; ask about something else. (For example: pure gold is soft; alloys are harder.)
- No two options may both be defensible. Every wrong option must be clearly wrong on reflection.
- If a question asks for the most common, main, best or usual thing, the true answer must be
  among the options.
- Matching pairs, the order of steps, blanks and model answers must be correct too.

Reply with JSON only, in this shape (questions in any order):
{{"questions": [
  {{"type": "choice", "question": "...", "options": ["...", "...", "...", "..."], "answer": 0, "notes": ["", "...", "...", "..."], "why": "..."}},
  {{"type": "scenario", "scenario": "...", "question": "...", "options": ["...", "...", "...", "..."], "answer": 2, "notes": ["...", "...", "", "..."], "why": "..."}},
  {{"type": "blank", "question": "A sentence with ____ in it.", "answer": "word", "accept": ["words"], "why": "..."}},
  {{"type": "order", "question": "Put these steps in order.", "steps": ["first", "second", "third"], "why": "..."}},
  {{"type": "match", "question": "Match each term to its meaning.", "pairs": [["term", "meaning"], ...], "why": "..."}},
  {{"type": "short", "question": "...", "answer": "a model answer", "why": "..."}},
  {{"type": "apply", "question": "...", "answer": "what a good answer must show", "why": "..."}}
]}}
"answer" in a choice or scenario question is the index (0-{OPTIONS - 1}) of the correct option."""

RECALL = """Also write ONE extra question, with "recall": true, of type "choice", about the earlier
lesson below, which she found hard. It checks the earlier lesson's key idea, not today's lesson,
and follows the same rules (one correct option, "notes" for each option)."""

GRADER = """You mark a learner's written answers to questions about a lesson she just studied.
For each answer decide how well it shows she understood the point the question asks about:
- "right": correct and specific enough;
- "partly": on the right track but missing a key part, or partly wrong;
- "wrong": wrong, vague, off-topic, empty or nonsense.
Her own words are fine and grammar or spelling mistakes don't matter. Use the model answer (or, for
an "apply" question, the criteria) as a guide, not as wording she must match. For an "apply"
question any example from her own life is fine if it really uses the idea.
"feedback" is one or two short, kind sentences in English. If it is right, say what she got right.
If not, say specifically what is wrong or what key point is missing.

Reply with JSON only: {"results": [{"id": 0, "verdict": "right", "feedback": "..."}]}, one entry per id."""

CHECKER = """You check a quiz before a learner sees it. For each question, decide whether it is sound:
- "choice" and "scenario": the keyed answer is factually correct in the real world and is the ONLY
  defensible option; no other option could also be argued to be right; if it asks for the most
  common, main, best or usual thing, the true answer is among the options.
- "blank": exactly one word or phrase (or the listed variants) fits the blank, and it is correct.
- "order": the steps are correct and there is exactly one defensible order (the one given).
- "match": every pair is factually correct and no term could reasonably match a different meaning.
- "short": the model answer is factually correct and answers the question.
- "apply": the question can be answered from her own life, and the criteria are fair and correct.
Judge by real-world facts, not only by what a lesson might have said.

Reply with JSON only: {"problems": [{"id": 0, "issue": "one sentence"}]} listing only the questions
with a problem; {"problems": []} if every question is sound."""


def _context(context: dict) -> str:
    """Her goal (for the "apply" question) and an earlier idea to recall."""
    context = context or {}
    parts = []
    if context.get("goal"):
        parts.append(f"Her goal: {context['goal']}")
    r = context.get("recall")
    if r:
        parts.append(f"{RECALL}\nEarlier lesson {r['n']}: {r['title']}\nIts key idea: {r['key']}")
    return ("\n\n" + "\n\n".join(parts)) if parts else ""


def request(slot: dict, context: dict = None):
    """(system, messages) for writing this lesson's quiz; `context` may give
    her goal and an earlier idea she found hard (coach/mastery.py)."""
    extra = _context(context)
    lesson = _fit(SYSTEM, f"Lesson {slot['n']}: {slot['title']}\n\n{slot['lesson']}", extra)
    return SYSTEM, [{"role": "user", "content": lesson + extra}]


def _fit(system: str, lesson: str, extra: str) -> str:
    """A very long lesson cut at the end so the request fits the budget
    (the start holds its key idea and deep dive)."""
    from coach import tokens
    while lesson and tokens.estimate_request(system, [{"content": lesson + extra}],
                                             tokens.QUIZ_MAX_TOKENS) > tokens.REQUEST_BUDGET:
        lesson = lesson[:int(len(lesson) * 0.9)]
    return lesson


def _text(value) -> str:
    return str(value).strip() if isinstance(value, (str, int, float)) and not isinstance(value, bool) else ""


_LABEL = re.compile(r"^\(?([A-Da-d1-4])[).:]\s+")


def _answer_index(answer, options):
    """The keyed answer as an index into options: an index, a numeric
    string, an option letter ("B"), or the option's own text."""
    if isinstance(answer, bool):
        return None
    if isinstance(answer, int):
        return answer if 0 <= answer < len(options) else None
    text = _text(answer)
    if text.isdigit():
        return int(text) if int(text) < len(options) else None
    if len(text) == 1 and text.upper() in "ABCD"[:len(options)]:
        return "ABCD".index(text.upper())
    folded = [o.casefold() for o in options]
    text = _LABEL.sub("", text).casefold()
    return folded.index(text) if text and folded.count(text) == 1 else None


def _choice(item, rng):
    """A multiple-choice question, or None. Small slips are repaired here
    rather than costing a new quiz: "A) " labels on every option, the answer
    given as a letter or as the option's text, a repeated option, or more
    than four options (the extra wrong ones are dropped). Each option's note
    (why it's wrong) travels with it."""
    question, options = _text(item.get("question")), item.get("options")
    if not question or not isinstance(options, list) or len(options) < OPTIONS:
        return None
    options = [_text(o) for o in options]
    if not all(options):
        return None
    if all(_LABEL.match(o) for o in options):
        options = [_LABEL.sub("", o) for o in options]
    answer = _answer_index(item.get("answer"), options)
    if answer is None:
        return None
    raw = item.get("notes")
    notes = [_text(x) for x in raw] if isinstance(raw, list) and len(raw) == len(options) else [""] * len(options)
    correct = options[answer]
    if sum(o.casefold() == correct.casefold() for o in options) > 1:
        return None
    wrong = []
    for o, note in zip(options, notes):
        if o.casefold() != correct.casefold() and o.casefold() not in {w[0].casefold() for w in wrong}:
            wrong.append((o, note))
    if len(wrong) < OPTIONS - 1:
        return None
    pairs = [(correct, "")] + wrong[:OPTIONS - 1]
    rng.shuffle(pairs)          # models like to put the answer first
    options = [o for o, _ in pairs]
    out = {"type": "choice", "question": question, "options": options,
           "answer": options.index(correct), "why": _text(item.get("why"))}
    if any(n for _, n in pairs):
        out["notes"] = [n for _, n in pairs]
    return out


def _scenario(item, rng):
    """A situation, then a choice about it (without one: a plain choice)."""
    q = _choice(item, rng)
    scenario = _text(item.get("scenario"))
    return {**q, "type": "scenario", "scenario": scenario} if q and scenario else q


def _blank(item, rng):
    """A sentence with one gap; the word (and close variants) that fit."""
    question, answer = _text(item.get("question")), _text(item.get("answer"))
    if not question or len(BLANK.findall(question)) != 1 or not answer or len(answer.split()) > 5:
        return None
    if _fold(answer) and _fold(answer) in _fold(BLANK.sub(" ", question)).split(" ") and len(answer.split()) == 1:
        return None                                  # the answer is given away in the sentence
    accept = [_text(a) for a in item.get("accept") or [] if _text(a)] if isinstance(item.get("accept"), list) else []
    return {"type": "blank", "question": BLANK.sub("____", question), "answer": answer,
            "accept": [a for a in accept if _fold(a) != _fold(answer)][:5], "why": _text(item.get("why"))}


def _order(item, rng):
    """Steps in the right order; shown shuffled (never already in order)."""
    steps = item.get("steps")
    if not isinstance(steps, list) or not STEPS[0] <= len(steps) <= STEPS[1]:
        return None
    steps = [_text(x) for x in steps]
    if not all(steps) or len({x.casefold() for x in steps}) != len(steps):
        return None
    items = steps[:]
    while items == steps:
        rng.shuffle(items)
    return {"type": "order", "question": _text(item.get("question")) or "Put these in the right order.",
            "items": items, "key": [items.index(x) for x in steps], "why": _text(item.get("why"))}


def _pair(p):
    if isinstance(p, (list, tuple)) and len(p) == 2:
        return list(p)
    if isinstance(p, dict) and len(p) == 2:
        return list(p.values())
    return None


def _match(item, rng):
    """A matching question, or None. Pairs may come as [term, meaning],
    {"term": .., "meaning": ..} or one {term: meaning} object; more than
    four pairs are cut to the first four."""
    pairs = item.get("pairs")
    if isinstance(pairs, dict):
        pairs = [[k, v] for k, v in pairs.items()]
    if not isinstance(pairs, list):
        return None
    pairs = [_pair(p) for p in pairs]
    if None in pairs or len(pairs) < PAIRS:
        return None
    pairs = pairs[:PAIRS]
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
    question = _text(item.get("question"))
    answer = _text(item.get("answer")) or _text(item.get("model_answer")) or _text(item.get("criteria"))
    if not question or not answer:
        return None
    kind = "apply" if item.get("type") == "apply" else "short"
    return {"type": kind, "question": question, "answer": answer, "why": _text(item.get("why"))}


KINDS = {"choice": _choice, "scenario": _scenario, "blank": _blank, "order": _order, "match": _match,
         "short": _short, "apply": _short}


def parse(data, rng=random) -> list:
    """The quiz's questions from the model's JSON, or None if there aren't
    QUESTIONS usable ones. Multiple choice comes first, then matching,
    then short answers."""
    return assemble(parse_items(data, rng))


def assemble(questions: list):
    """QUESTIONS of the usable questions, in the MIX where they allow it
    (then any kind she can answer: never more than two written answers to
    mark), repeats left out; None if there aren't enough. A question about
    an earlier lesson ("recall") is never one of them (recall_of())."""
    seen, unique = set(), []
    for q in questions:
        if q["question"].casefold() not in seen and not q.get("recall"):
            seen.add(q["question"].casefold())
            unique.append(q)
    picked = []
    for kind, n in MIX.items():
        picked += [q for q in unique if q["type"] == kind][:n]
    written = sum(1 for q in picked if q["type"] in WRITTEN)
    for q in unique:
        if len(picked) >= QUESTIONS:
            break
        if q in picked or (q["type"] in WRITTEN and written >= len(WRITTEN)):
            continue
        picked.append(q)
        written += q["type"] in WRITTEN
    if len(picked) < QUESTIONS:
        return None
    order = list(KINDS)
    return sorted(picked[:QUESTIONS], key=lambda q: order.index(q["type"]))


def recall_of(questions: list):
    """The question about an earlier lesson, if the model wrote one."""
    return next((q for q in questions if q.get("recall")), None)


def missing(questions: list) -> list:
    """The kinds still needed to make a full quiz of these questions (the
    MIX's gaps: written answers, matching, a blank and a scenario first; an
    ordering question is never asked for on its own), e.g. ["short", "choice"]."""
    have = {q["question"].casefold(): q["type"] for q in questions if not q.get("recall")}
    need = QUESTIONS - len(have)
    gaps = []
    for kind in ("apply", "short", "match", "blank", "scenario", "choice"):
        gaps += [kind] * max(0, MIX[kind] - sum(1 for t in have.values() if t == kind))
    gaps += ["choice"] * need
    return gaps[:max(0, need)]


def _describe(k: int, q: dict) -> str:
    if q["type"] in ("choice", "scenario"):
        opts = "\n".join(f"  {'*' if j == q['answer'] else '-'} {o}" for j, o in enumerate(q["options"]))
        lead = f"  situation: {q['scenario']}\n" if q["type"] == "scenario" else ""
        return f"id {k} ({q['type']}): {q['question']}\n{lead}{opts}\n  (* = keyed answer)"
    if q["type"] == "match":
        pairs = "\n".join(f"  {left} = {q['right'][key]}" for left, key in zip(q["left"], q["key"]))
        return f"id {k} (match): {q['question']}\n{pairs}"
    if q["type"] == "blank":
        also = f" (also accepted: {', '.join(q['accept'])})" if q.get("accept") else ""
        return f"id {k} (blank): {q['question']}\n  answer: {q['answer']}{also}"
    if q["type"] == "order":
        steps = "\n".join(f"  {j + 1}. {q['items'][i]}" for j, i in enumerate(q["key"]))
        return f"id {k} (order): {q['question']}\n  correct order:\n{steps}"
    label = "criteria for a good answer" if q["type"] == "apply" else "model answer"
    return f"id {k} ({q['type']}): {q['question']}\n  {label}: {q['answer']}"


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


def _more_request(slot: dict, kinds: list, notes: str):
    wanted = ", ".join(f'{kinds.count(t)} "{t}"' for t in KINDS if t in kinds)
    system = SYSTEM.split("Reply with JSON only")[0].replace(
        f"Write exactly {QUESTIONS} questions about the lesson you are given, in English, in this mix:",
        f"Write exactly {len(kinds)} replacement questions ({wanted}) about the lesson you are given, "
        "in English. The kinds are:")
    system += ("Reply with JSON only, in the same shape as before: "
               '{"questions": [{"type": "choice" | "scenario" | "blank" | "order" | "match" | "short" | "apply", ...}]}.')
    return system, [{"role": "user", "content": f"Lesson {slot['n']}: {slot['title']}\n\n{slot['lesson']}\n\n{notes}"}]


def rewrite_request(slot: dict, questions: list, flagged: dict, context: dict = None):
    """(system, messages) asking for replacements for the flagged questions,
    same kinds, different content."""
    avoid = "\n".join(f"- {questions[k]['question']} (problem: {issue})" for k, issue in sorted(flagged.items()))
    keep = "\n".join(f"- {q['question']}" for k, q in enumerate(questions) if k not in flagged)
    return _more_request(slot, [questions[k]["type"] for k in sorted(flagged)],
                         f"These questions had problems; write different ones:\n{avoid}\n\n"
                         f"Don't repeat the questions already in the quiz:\n{keep}"
                         + _context({"goal": (context or {}).get("goal")}))


def fill_request(slot: dict, questions: list, context: dict = None):
    """(system, messages) asking only for the questions a quiz still lacks
    (missing()), when some of the model's questions couldn't be used."""
    keep = "\n".join(f"- {q['question']}" for q in questions) or "- (none yet)"
    return _more_request(slot, missing(questions),
                         f"Don't repeat the questions already in the quiz:\n{keep}"
                         + _context({"goal": (context or {}).get("goal")}))


def salvage(text: str):
    """The complete questions in a reply that was cut off before its JSON
    closed (the reply limit), as {"questions": [...]}, or None."""
    start = (text or "").find("[", (text or "").find('"questions"'))
    if '"questions"' not in (text or "") or start < 0:
        return None
    items, depth, begin, in_str, escape = [], 0, None, False, False
    for k in range(start + 1, len(text)):
        c = text[k]
        if in_str:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == "{":
            begin = k if depth == 0 else begin
            depth += 1
        elif c == "}" and depth:
            depth -= 1
            if depth == 0:
                try:
                    items.append(json.loads(text[begin:k + 1]))
                except ValueError:
                    pass
        elif c == "]" and depth == 0:
            break
    return {"questions": items} if items else None


def _kind(item) -> str:
    """The question's kind: its "type", or what its fields show when the
    type is missing or unknown ("multiple_choice", "matching"…)."""
    kind = item.get("type")
    if kind in KINDS:
        return kind
    if "pairs" in item:
        return "match"
    if "steps" in item:
        return "order"
    if "scenario" in item and "options" in item:
        return "scenario"
    if "options" in item or kind is None:
        return "choice"
    return "short"


def parse_items(data, rng=random) -> list:
    """Every usable question in the model's JSON, in the order given (a
    question about an earlier lesson keeps "recall": True)."""
    items = data.get("questions") if isinstance(data, dict) else None
    out = []
    for item in items if isinstance(items, list) else []:
        if isinstance(item, dict):
            q = KINDS[_kind(item)](item, rng)
            if q:
                if item.get("recall") is True and q["type"] in ("choice", "scenario"):
                    q["recall"] = True
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
    """Unanswered: None for choice, a None per term (or step) for matching
    and ordering, "" for written answers and blanks."""
    out = []
    for q in quiz["questions"]:
        if q["type"] == "match":
            out.append([None] * len(q["left"]))
        elif q["type"] == "order":
            out.append([None] * len(q["items"]))
        elif q["type"] in WRITTEN + ("blank",):
            out.append("")
        else:
            out.append(None)
    return out


def answered(question: dict, answer) -> bool:
    if question["type"] in ("choice", "scenario"):
        return answer is not None
    if question["type"] in ("match", "order"):
        return isinstance(answer, list) and None not in answer and len(set(answer)) == len(answer)
    return bool(_text(answer))


_PUNCT = re.compile(r"[^\w\s]")
_ARTICLES = re.compile(r"^(?:the|a|an)\s+")


def _fold(text) -> str:
    """For comparing a typed word: case, punctuation, spaces and a leading
    article don't matter."""
    t = " ".join(_PUNCT.sub(" ", str(text or "")).casefold().split())
    return _ARTICLES.sub("", t)


def _distance(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def blank_result(question: dict, answer) -> str:
    """ "right", "typo" (right, misspelt by a letter or two) or "wrong"."""
    mine = _fold(answer)
    targets = [_fold(question["answer"])] + [_fold(a) for a in question.get("accept") or []]
    if not mine:
        return "wrong"
    if mine in targets:
        return "right"
    allowed = lambda t: 2 if len(t) >= 9 else (1 if len(t) >= 5 else 0)   # noqa: E731
    if any(_distance(mine, t) <= allowed(t) for t in targets if t):
        return "typo"
    return "wrong"


def _mark(question: dict, answer):
    """Points for one answer; None for a written answer (the model marks those)."""
    kind = question["type"]
    if kind in ("choice", "scenario"):
        return 1.0 if answer == question["answer"] else 0.0
    if kind in ("match", "order"):
        return sum(1 for a, k in zip(answer or [], question["key"]) if a == k) / len(question["key"])
    if kind == "blank":
        return 0.0 if blank_result(question, answer) == "wrong" else 1.0
    return None


def mark(question: dict, answer):
    """Public: points for one answer marked here (None for a written one)."""
    return _mark(question, answer)


def mistake(question: dict, answer) -> str:
    """What she got wrong, specifically (for an answer marked here): the
    option she chose and why it isn't right, the pairs or steps out of
    place, the word that fits. "" when it's right."""
    kind = question["type"]
    if kind in ("choice", "scenario"):
        if answer == question["answer"] or answer is None:
            return ""
        note = (question.get("notes") or [""] * len(question["options"]))[answer]
        return (f"You chose “{question['options'][answer]}”" + (f": {note.rstrip('.')}." if note else ".")
                + f" The answer is “{question['options'][question['answer']]}”.")
    if kind == "match":
        wrong = [f"“{left}” goes with “{question['right'][k]}”"
                 for left, a, k in zip(question["left"], answer or [], question["key"]) if a != k]
        return ("Not quite: " + "; ".join(wrong) + ".") if wrong else ""
    if kind == "order":
        right = [question["items"][i] for i in question["key"]]
        off = [j + 1 for j, (a, k) in enumerate(zip(answer or [], question["key"])) if a != k]
        if not off:
            return ""
        where = ", ".join(map(str, off))
        return (f"Step{'s' if len(off) > 1 else ''} {where} {'were' if len(off) > 1 else 'was'} out of place. "
                "The order is: " + " → ".join(right) + ".")
    if kind == "blank":
        result = blank_result(question, answer)
        if result == "typo":
            return f"Right (it's spelled “{question['answer']}”)."
        if result == "wrong":
            return f"You wrote “{_text(answer)}”; the word that fits is “{question['answer']}”."
    return ""


def submit(quiz: dict, answers: list) -> bool:
    """Record a submission and mark what can be marked here. Returns True
    if written answers still need the model."""
    quiz["answers"] = list(answers)
    quiz["draft"] = None
    quiz["marks"] = [_mark(q, a) for q, a in zip(quiz["questions"], answers)]
    quiz["feedback"] = [""] * len(answers)
    quiz["score"] = None
    return needs_grading(quiz)


def needs_grading(quiz: dict) -> bool:
    return quiz.get("answers") is not None and None in (quiz.get("marks") or [None])


def grading_request(quiz: dict):
    """(system, messages) asking the model to mark the written answers."""
    lines = []
    for k, (q, a) in enumerate(zip(quiz["questions"], quiz["answers"])):
        if q["type"] in WRITTEN:
            guide = "Criteria for a good answer" if q["type"] == "apply" else "Model answer"
            lines.append(f"id {k} ({q['type']})\nQuestion: {q['question']}\n{guide}: {q['answer']}\nHer answer: {a}")
    return GRADER, [{"role": "user", "content": "\n\n".join(lines)}]


VERDICTS = {"right": 1.0, "partly": 0.5, "wrong": 0.0}


def verdict_mark(r: dict):
    """A result's mark: "verdict" right/partly/wrong (or the older "correct")."""
    v = r.get("verdict")
    if isinstance(v, str) and v.strip().lower() in VERDICTS:
        return VERDICTS[v.strip().lower()]
    if isinstance(r.get("correct"), bool):
        return 1.0 if r["correct"] else 0.0
    return None


def apply_grading(quiz: dict, data) -> bool:
    """Take the model's marks for the written answers. False if any is missing."""
    results = data.get("results") if isinstance(data, dict) else None
    if not isinstance(results, list):
        return False
    by_id = {r.get("id"): r for r in results if isinstance(r, dict) and isinstance(r.get("id"), int)}
    marks, feedback = list(quiz["marks"]), list(quiz["feedback"])
    for k, q in enumerate(quiz["questions"]):
        if q["type"] not in WRITTEN:
            continue
        r = by_id.get(k)
        if r is None or verdict_mark(r) is None:
            return False
        marks[k], feedback[k] = verdict_mark(r), _text(r.get("feedback"))
    quiz["marks"], quiz["feedback"] = marks, feedback
    return True


def counted(quiz: dict) -> list:
    """The indexes of the questions that make the score (not the one about
    an earlier lesson, which only feeds what she knows)."""
    return [k for k, q in enumerate(quiz["questions"]) if not q.get("from")]


def finish(quiz: dict) -> int:
    """Once every question is marked: the score in percent (and attempts, best)."""
    ks = counted(quiz)
    score = round(sum(quiz["marks"][k] for k in ks) / len(ks) * 100)
    quiz["score"] = score
    quiz["attempts"] = quiz.get("attempts", 0) + 1
    quiz["best"] = max(score, quiz.get("best") or 0)
    return score


def passed(score) -> bool:
    return score is not None and score >= PASS_MARK


def points(quiz: dict) -> str:
    """ "8.5 of 10" style."""
    ks = counted(quiz)
    return f"{sum(quiz['marks'][k] for k in ks):g} of {len(ks)}"


def _saved_question(q):
    if not isinstance(q, dict) or not _text(q.get("question")):
        return None
    kind = q.get("type", "choice")
    base = {"type": kind, "question": _text(q["question"]), "why": _text(q.get("why"))}
    if isinstance(q.get("from"), int) and not isinstance(q.get("from"), bool):
        base["from"] = q["from"]              # about an earlier lesson (doesn't count toward the score)
    if kind in ("choice", "scenario"):
        options, answer = q.get("options"), q.get("answer")
        if (isinstance(options, list) and len(options) == OPTIONS and isinstance(answer, int)
                and not isinstance(answer, bool) and 0 <= answer < OPTIONS):
            out = {**base, "options": [str(o) for o in options], "answer": answer}
            notes = q.get("notes")
            if isinstance(notes, list) and len(notes) == OPTIONS:
                out["notes"] = [_text(x) for x in notes]
            if kind == "scenario":
                if not _text(q.get("scenario")):
                    return None
                out["scenario"] = _text(q["scenario"])
            return out
    elif kind in ("match", "order"):
        left = q.get("left") if kind == "match" else q.get("items")
        right, key = (q.get("right") if kind == "match" else left), q.get("key")
        if (isinstance(left, list) and isinstance(right, list) and isinstance(key, list)
                and len(left) == len(right) == len(key) > 0
                and sorted(k for k in key if isinstance(k, int)) == list(range(len(key)))):
            if kind == "order":
                return {**base, "items": [str(x) for x in left], "key": key}
            return {**base, "left": [str(x) for x in left], "right": [str(x) for x in right], "key": key}
    elif kind == "blank" and _text(q.get("answer")) and BLANK.search(_text(q["question"])):
        accept = q.get("accept") if isinstance(q.get("accept"), list) else []
        return {**base, "answer": _text(q["answer"]), "accept": [_text(a) for a in accept if _text(a)]}
    elif kind in WRITTEN and _text(q.get("answer")):
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


def why_unusable(data) -> str:
    """For the log: what the model's quiz JSON held, when it can't be used."""
    items = data.get("questions") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return f"no questions list (keys: {sorted(data)[:5] if isinstance(data, dict) else type(data).__name__})"
    usable = parse_items(data, random.Random(0))
    kinds = {k: sum(1 for q in usable if q["type"] == k) for k in KINDS}
    given = {k: sum(1 for i in items if isinstance(i, dict) and _kind(i) == k) for k in KINDS}
    return f"{len(usable)} usable of {len(items)} given (usable {kinds}, given {given}; {QUESTIONS} needed)"
