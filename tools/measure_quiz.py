"""Issue A acceptance on the real model: write quizzes with the app's own
code (coach/quizgen.py, coach/llm.py) against Groq and report how many came
on the first click and how long each took (p50 / p95).

    GROQ_API_KEY_TEST=… python tools/measure_quiz.py --runs 20 --lessons 10

- Reads the key only from the environment variable GROQ_API_KEY_TEST (a key
  made for this test, revoked afterwards). Never prints, logs or saves it.
- Groq's free tier allows 200k tokens a day for the whole organization (both
  apps included), so the run stops before --budget tokens (default 150k),
  and at once if Groq says the day's tokens are used up.
- Real lessons first (one per lesson, different subjects), then each quiz
  as a person would take it: after reading, i.e. with the minute's token
  allowance free again (the app's pacing, llm.py, is left on).
- Touches no database; writes its report to docs/audit/quiz_measure_<date>.json.
"""
import argparse
import json
import logging
import math
import os
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import groq  # noqa: E402

from coach import core, curriculum, llm, quiz, quizgen, quota  # noqa: E402

KEY_NAME = "GROQ_API_KEY_TEST"
LESSONS = [("philosophy", 1), ("cosmos", 1), ("investing", 1), ("business", 1), ("fashion", 1),
           ("jewelry", 1), ("philosophy", 7), ("cosmos", 12), ("business", 20), ("jewelry", 9)]


class Spent(Exception):
    pass


class Counting:
    """The Groq client, counting every call's tokens; stops at the budget."""
    def __init__(self, key, budget):
        self.inner = groq.Groq(api_key=key, max_retries=0, timeout=llm.REQUEST_TIMEOUT)
        self.chat = self
        self.completions = self
        self.budget, self.used, self.calls = budget, 0, []

    def create(self, **kwargs):
        if self.used + kwargs.get("max_completion_tokens", 0) > self.budget:
            raise Spent(f"budget: {self.used} tokens used, next call could pass {self.budget}")
        t0 = time.monotonic()
        try:
            resp = self.inner.chat.completions.create(**kwargs)
        except groq.RateLimitError as e:
            if "per day" in str(e) or "TPD" in str(e):
                raise Spent("Groq: the day's tokens are used up") from None
            self.calls.append({"status": 429, "seconds": round(time.monotonic() - t0, 1)})
            raise
        if kwargs.get("stream"):
            self.used += kwargs.get("max_completion_tokens", 0)    # counted high until the stream ends
            self.calls.append({"stream": True, "seconds": round(time.monotonic() - t0, 1)})
            return resp
        usage = getattr(resp, "usage", None)
        self.used += getattr(usage, "total_tokens", 0) or 0
        self.calls.append({"tokens": getattr(usage, "total_tokens", None), "seconds": round(time.monotonic() - t0, 1),
                           "finish": resp.choices[0].finish_reason})
        return resp


def lesson_slot(topic, n, today):
    slot = curriculum.new_slot(topic, n)
    log = {"entries": [], "books": []}
    system = core.build_system_prompt(log, topic, today, slot=slot, start_level="Beginner")
    kickoff = core.build_kickoff_message(topic, today, slot=slot)
    text = "".join(llm.stream_text(system, [{"role": "user", "content": kickoff}], llm.tokens.LESSON_MAX_TOKENS))
    slot["kickoff"], slot["lesson"] = kickoff, core.finalize_reply(text, lesson=True, topic=topic)
    return slot


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=20)
    ap.add_argument("--lessons", type=int, default=10)
    ap.add_argument("--budget", type=int, default=150_000)
    ap.add_argument("--rest", type=float, default=60.0, help="seconds between quizzes (her reading time)")
    args = ap.parse_args()
    key = os.environ.get(KEY_NAME, "")
    if not key:
        sys.exit(f"Set {KEY_NAME} in the environment first (never paste it into a chat).")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s",
                        handlers=[logging.StreamHandler(sys.stdout)])
    client = Counting(key, args.budget)
    llm.get_client = lambda: client
    quota.over_limit = lambda: False            # no signed-in person here
    quota.record = lambda *a, **k: None
    today = datetime.now(ZoneInfo("Asia/Taipei")).date()
    report = {"date": str(today), "model": llm.MODEL_NAME, "runs": [], "stopped": None}
    out = ROOT / "docs" / "audit" / f"quiz_measure_{today}.json"
    try:
        slots = []
        for topic, n in LESSONS[:args.lessons]:
            t0 = time.monotonic()
            slots.append((topic, lesson_slot(topic, n, today)))
            print(f"lesson {topic} {n} written in {time.monotonic() - t0:.1f}s ({client.used} tokens so far)", flush=True)
        for k in range(args.runs):
            time.sleep(args.rest)
            topic, slot = slots[k % len(slots)]
            before, t0 = len(client.calls), time.monotonic()
            questions, error = quizgen.make(slot, f"{topic} lesson {slot['n']}")
            seconds = time.monotonic() - t0
            calls = client.calls[before:]
            report["runs"].append({"lesson": f"{topic} {slot['n']}", "ok": questions is not None, "error": error,
                                   "seconds": round(seconds, 1), "calls": calls,
                                   "kinds": [q["type"] for q in questions] if questions else None})
            print(f"quiz {k + 1}: {'ok' if questions else 'FAILED ' + str(error)} in {seconds:.1f}s, "
                  f"{len(calls)} calls, {client.used} tokens so far", flush=True)
            out.write_text(json.dumps(report, indent=1))
    except Spent as e:
        report["stopped"] = str(e)
        print(f"stopped: {e}")
    runs = report["runs"]
    if runs:
        times = sorted(r["seconds"] for r in runs)
        report["summary"] = {
            "quizzes": len(runs), "first_click": sum(r["ok"] for r in runs),
            "p50_seconds": statistics.median(times),
            "p95_seconds": times[math.ceil(0.95 * len(times)) - 1],        # nearest rank
            "extra_calls": sum(len(r["calls"]) - 2 for r in runs if r["ok"]),
            "tokens_used": client.used, "quiz_size": quiz.QUESTIONS,
        }
        print(json.dumps(report["summary"], indent=1))
    out.write_text(json.dumps(report, indent=1))
    print(f"report: {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
