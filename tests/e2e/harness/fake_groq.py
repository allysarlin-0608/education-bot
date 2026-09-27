"""A stand-in for the Groq client, for the end-to-end tests only.

The app's own llm.py runs unchanged on top of it (retries, error messages,
the daily allowance, JSON parsing); only the network call is replaced. What
the "model" does is read from a control file on every call, so a test can
make it fail, be slow, or return tricky content:

  {"mode": "ok" | "413" | "429" | "500" | "timeout" | "empty" | "invalid" | "broken_stream",
   "fail_times": 1,          # fail this many calls, then behave (default: always)
   "delay": 0.0,             # seconds before answering
   "inject": false,          # put HTML/script/markdown-link injection strings in every reply
   "quiz_flag_first": false} # the answer checker flags question 0 once (exercises rewrite)

Every call is appended to calls.jsonl (kind, time), so tests can count them.
"""
import json
import os
import threading
import time
import types
from pathlib import Path

import httpx

STATE = Path(os.environ.get("E2E_STATE_DIR", "/tmp/e2e_state"))
_lock = threading.Lock()

INJECT = ('<script>alert("xss")</script><img src=x onerror=alert(1)> '
          '[click me](javascript:alert(1)) **bold?** ## heading?')

LESSON = ("【Topic】 Earth's rotation\n\n【Key Idea】 Earth spins once a day, which gives day and night.\n\n"
          "【Deep Dive】 The spin is west to east, so the Sun appears to rise in the east.\n\n"
          "| Term | Meaning |\n|---|---|\n| Axis | The line Earth spins around |\n\n"
          "【Example】 Sunrise in Taipei comes before sunrise in Paris.\n\n【Today's Task】 Watch a sunset.\n\n"
          "【Vocabulary】 axis｜the line it spins around｜Earth spins on its axis.\n\n"
          "【Question to Explore】 Why do we not feel the spin?\n\n【Note】 Keep going.")


def control() -> dict:
    try:
        return json.loads((STATE / "llm.json").read_text())
    except (FileNotFoundError, ValueError):
        return {}


def _log(kind: str) -> int:
    with _lock:
        STATE.mkdir(parents=True, exist_ok=True)
        with open(STATE / "calls.jsonl", "a") as f:
            f.write(json.dumps({"kind": kind, "t": time.time()}) + "\n")
        n = sum(1 for _ in open(STATE / "calls.jsonl"))
    return n


def _kind(messages: list, stream: bool) -> str:
    system = messages[0]["content"] if messages else ""
    if "replacement questions" in system:
        return "quiz_rewrite"
    if system.startswith("You write a short quiz"):
        return "quiz"
    if system.startswith("You check a quiz"):
        return "quiz_check"
    if system.startswith("You mark a learner"):
        return "grade"
    if '"passed"' in system:
        return "reading_judge"
    if '"moves"' in system:
        return "reading_adjust"
    if "總結式肯定" in system:
        return "reading_final"
    if stream:
        return "followup" if len([m for m in messages if m["role"] == "user"]) > 1 else "lesson"
    return "json_other"


def _quiz(inject: bool) -> dict:
    extra = f" {INJECT}" if inject else ""
    qs = [{"type": "choice", "question": f"Why does Earth have day and night? ({k + 1}){extra}",
           "options": ["It spins on its axis", "It orbits the Sun", "The Moon blocks the light", "Solar flares"],
           "answer": 0, "why": "Earth's spin turns each place toward and away from the Sun."} for k in range(7)]
    qs.append({"type": "match", "question": "Match each term to its meaning.",
               "pairs": [["Axis", "The line Earth spins around"], ["Rotation", "One spin a day"],
                         ["Orbit", "One trip around the Sun"], ["Sunrise", "When the Sun comes into view"]],
               "why": "These are the lesson's terms."})
    qs += [{"type": "short", "question": q + extra, "answer": "Because Earth spins on its axis.", "why": "."}
           for q in ("Explain in your own words why we have day and night.",
                     "Why does the Sun seem to rise in the east?")]
    return {"questions": qs}


def _reply(kind: str, messages: list, ctl: dict) -> str:
    inject = ctl.get("inject")
    last = messages[-1]["content"] if messages else ""
    if kind == "quiz":
        return json.dumps(_quiz(inject))
    if kind == "quiz_rewrite":
        return json.dumps({"questions": [{"type": "choice", "question": "Which way does Earth spin?",
                                          "options": ["West to east", "East to west", "North to south", "It doesn't"],
                                          "answer": 0, "why": "That's why the Sun rises in the east."}]})
    if kind == "quiz_check":
        flag = ctl.get("quiz_flag_first") and not (STATE / "flagged_once").exists()
        if flag:
            (STATE / "flagged_once").write_text("1")
        return json.dumps({"problems": [{"id": 0, "issue": "Ambiguous."}] if flag else []})
    if kind == "grade":
        results = []
        for block in last.split("\n\n"):
            if block.startswith("id "):
                k = int(block.split("\n")[0].split()[1])
                ans = block.split("Her answer: ")[-1].lower()
                ok = "spin" in ans or "rotat" in ans
                results.append({"id": k, "correct": ok,
                                "feedback": ("Right: it's the spin." if ok else "It doesn't mention Earth's spin.")
                                + (f" {INJECT}" if inject else "")})
        return json.dumps({"results": results})
    if kind == "reading_judge":
        ok = len(last) > 20
        return json.dumps({"passed": ok, "reply": ("Nice summary — Day done." if ok else "Tell me a bit more.")
                           + (f" {INJECT}" if inject else "")})
    if kind == "reading_adjust":
        return json.dumps({"moves": [], "confirmed": "ok" in last.lower() or "good" in last.lower(),
                           "reply": "Sounds good." + (f" {INJECT}" if inject else "")})
    if kind == "lesson":
        return LESSON + (f"\n\n{INJECT}" if inject else "")
    if kind == "followup":
        return "Good question. Earth's spin is smooth and steady, so we don't feel it." + (f" {INJECT}" if inject else "")
    return "Thanks for sharing." + (f" {INJECT}" if inject else "")


def _status_error(status: int):
    import groq
    response = httpx.Response(status, request=httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions"))
    cls = {413: groq.APIStatusError, 429: groq.RateLimitError, 500: groq.InternalServerError}[status]
    return cls(f"Error code: {status} - fake", response=response, body={"error": {"message": "fake"}})


def _chunk(text, finish=None):
    return types.SimpleNamespace(choices=[types.SimpleNamespace(delta=types.SimpleNamespace(content=text),
                                                                finish_reason=finish)])


class FakeGroq:
    def __init__(self):
        self.chat = types.SimpleNamespace(completions=self)

    def create(self, **kwargs):
        import groq
        ctl = control()
        messages = kwargs.get("messages", [])
        stream = bool(kwargs.get("stream"))
        kind = _kind(messages, stream)
        n = _log(kind)
        if ctl.get("delay"):
            time.sleep(float(ctl["delay"]))
        mode = ctl.get("mode", "ok")
        fail_times = ctl.get("fail_times")
        failing = mode != "ok" and (fail_times is None or n <= int(fail_times))
        if failing and mode in ("413", "429", "500"):
            raise _status_error(int(mode))
        if failing and mode == "timeout":
            raise groq.APITimeoutError(request=httpx.Request("POST", "https://api.groq.com"))
        text = _reply(kind, messages, ctl)
        if failing and mode == "empty":
            text = ""
        if failing and mode == "invalid":
            text = "Sorry, here is some prose instead of JSON." if not stream else ""
        usage = types.SimpleNamespace(total_tokens=max(1, len(text) // 4))
        if stream:
            words = text.split(" ") if text else []
            broken = failing and mode == "broken_stream"

            def gen():
                for k, w in enumerate(words):
                    if broken and k == 5:
                        raise groq.APIConnectionError(request=httpx.Request("POST", "https://api.groq.com"))
                    yield _chunk(w + (" " if k < len(words) - 1 else ""))
                yield _chunk("", finish="stop")
            return gen()
        return types.SimpleNamespace(usage=usage, choices=[types.SimpleNamespace(
            message=types.SimpleNamespace(content=text), finish_reason="stop")])
