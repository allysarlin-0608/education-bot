"""Writing a lesson's quiz: the model calls behind "Take the quiz", kept
apart from the page so the measurement script (tools/measure_quiz.py) runs
exactly what the app runs.

1. The quiz is asked for (quiz.request). A reply that leaves some questions
   unusable (a slip in one, or cut off at the reply limit) doesn't fail it:
   the good questions are kept and only the missing ones are asked for
   (quiz.fill_request); if that doesn't make a full quiz either, the whole
   quiz is asked for again. At most quiz.RECOVERIES extra calls; a busy
   model (already retried in llm.py), the daily limit or a missing key end
   it at once.
2. A second call checks every keyed answer (quiz.check_request); flagged
   questions are rewritten and checked again, quiz.CHECK_ROUNDS times.

`context` (coach/practice.quiz_context) gives her goal, for the question that
applies the idea to her life, and an earlier idea she found hard: the model
adds one question on it in the same call (no extra call). It is checked with
the others; if the check flags it, it is simply left out (never rewritten),
and it never counts toward the score (quiz.counted)."""
import contextlib
import time

from coach import llm, quiz, tokens

GAVE_UP = "I couldn't write a quiz whose answers I'm sure of this time. Try again."


def _quietly(label):
    return contextlib.nullcontext()


def write_questions(slot, where, started, step=_quietly, context=None):
    """(questions, recall question or None, None) or (None, None, friendly error)."""
    system, messages = quiz.request(slot, context)
    with step("Writing your quiz…"):
        data, error = llm.ask_json(system, messages, max_tokens=tokens.QUIZ_MAX_TOKENS, salvage=quiz.salvage)
    usable = quiz.parse_items(data) if data else []
    last = "quiz"
    for recovery in range(quiz.RECOVERIES + 1):
        questions = quiz.assemble(usable)
        if questions is not None:
            recall = quiz.recall_of(usable)
            if recall is not None and (context or {}).get("recall"):
                recall = {k: v for k, v in recall.items() if k != "recall"}
                recall["from"] = context["recall"]["n"]
            else:
                recall = None
            return questions, recall, None
        why = error or f"unusable quiz: {quiz.why_unusable(data)}"
        if error in (llm.LIMIT, llm.NO_KEY, llm.BUSY) or recovery == quiz.RECOVERIES:
            llm.logger.warning("quiz for %s failed after %.1fs and %d extra calls: %s", where,
                               time.monotonic() - started, recovery, why)
            return None, None, error or llm.FAILED
        gaps = quiz.missing(usable)
        if usable and len(gaps) <= quiz.FILL_AT_MOST and last != "fill":
            last = "fill"
            system, messages = quiz.fill_request(slot, usable, context)
            label = f"Writing {len(gaps)} more {'question' if len(gaps) == 1 else 'questions'}…"
        else:
            last = "quiz"
            system, messages = quiz.request(slot, context)
            label = "Writing your quiz again…"
        llm.logger.info("quiz for %s incomplete after %.1fs (%s); asking for %s", where,
                        time.monotonic() - started, why, "the whole quiz again" if last == "quiz" else gaps)
        with step(label):
            data, error = llm.ask_json(system, messages, max_tokens=tokens.QUIZ_MAX_TOKENS, salvage=quiz.salvage)
        usable += quiz.parse_items(data) if data else []


def make(slot, where, step=_quietly, context=None):
    """A checked quiz's questions for this lesson: (questions, None) or
    (None, friendly error). `where` names the lesson in the log; `step(label)`
    is a context manager shown around each call (the page's spinner). A
    question on an earlier idea, if any, comes last (its "from": the lesson)."""
    started = time.monotonic()
    questions, recall, error = write_questions(slot, where, started, step, context)
    if questions is None:
        return None, error
    if recall is not None:
        questions = questions + [recall]
    for attempt in range(quiz.CHECK_ROUNDS + 1):
        system, messages = quiz.check_request(questions, slot.get("lesson", "") if isinstance(slot, dict) else "")
        with step("Checking every answer…"):
            data, error = llm.ask_json(system, messages)
        flagged = quiz.problems(data, len(questions)) if data else None
        if error or flagged is None:
            llm.logger.warning("quiz check for %s failed after %.1fs: %s", where,
                               time.monotonic() - started, error or f"unreadable verdict: {str(data)[:200]}")
            return None, error or llm.FAILED
        # the rejection rate of every check, flagged or not (criterion 1.5)
        llm.logger.info("quiz check round %d: %d of %d questions rejected%s", attempt + 1, len(flagged),
                        len(questions), f" {flagged}" if flagged else "")
        if recall is not None and len(questions) - 1 in flagged:        # the earlier idea's question: left out
            flagged.pop(len(questions) - 1)
            questions, recall = questions[:-1], None
        if not flagged:
            break
        if attempt == quiz.CHECK_ROUNDS:
            llm.logger.warning("quiz for %s gave up: still %d flagged after %d rewrites",
                               where, len(flagged), quiz.CHECK_ROUNDS)
            return None, GAVE_UP
        system, messages = quiz.rewrite_request(slot, questions, flagged, context)
        with step(f"Rewriting {len(flagged)} {'question' if len(flagged) == 1 else 'questions'}…"):
            data, error = llm.ask_json(system, messages, max_tokens=tokens.QUIZ_MAX_TOKENS, salvage=quiz.salvage)
        fresh = quiz.replace(questions, flagged, quiz.parse_items(data)) if data else None
        if error or fresh is None:
            llm.logger.warning("quiz rewrite for %s failed: %s", where,
                               error or f"replacements don't fit: {quiz.why_unusable(data)}")
            return None, error or llm.FAILED
        questions = fresh
    llm.logger.info("quiz for %s ready in %.1fs", where, time.monotonic() - started)
    return questions, None
