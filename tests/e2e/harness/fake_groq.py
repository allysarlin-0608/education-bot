"""A stand-in for the Groq client, for the end-to-end tests only.

The app's own llm.py runs unchanged on top of it (retries, error messages,
the daily allowance, JSON parsing); only the network call is replaced. What
the "model" does is read from a control file on every call, so a test can
make it fail, be slow, or return tricky content:

  {"mode": "ok" | "413" | "429" | "500" | "timeout" | "empty" | "invalid" | "broken_stream"
           | "malformed_quiz"        # one question has 3 options
           | "truncated_quiz",       # the reply stops at the limit, two thirds of the way through
   "fail_times": 1,          # fail this many calls, then behave (default: always)
   "delay": 0.0,             # seconds before answering
   "chunk_delay": 0.0,       # seconds between streamed pieces (a slow stream)
   "fail_kinds": ["reading_final"],   # fail only these kinds of call (default: any)
   "inject": false,          # put HTML/script/markdown-link injection strings in every reply
   "quiz_flag_first": false, # the answer checker flags question 0 once (exercises rewrite)
   "old_quiz": false}        # the quiz mix from before Phase 3 (7 choice, 1 match, 2 short)

Every call is appended to calls.jsonl (kind, time), so tests can count them.
"""
import json
import os
import re
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
          "【Quick Check】\nQ: What gives us day and night?\nA) Earth orbiting the Sun — ✗ the orbit gives the year\n"
          "B) Earth spinning on its axis ✓\nC) The Moon blocking the Sun — ✗ that's an eclipse\n"
          "Hint: Think of what happens once every 24 hours.\nWhy: One spin turns each place toward, then away from, the Sun.\n\n"
          "【Deep Dive】 The spin is west to east, so the Sun appears to rise in the east.\n\n"
          "| Term | Meaning |\n|---|---|\n| Axis | The line Earth spins around |\n\n"
          "【Quick Check】\nQ: Which way does Earth spin?\nA) East to west — ✗ then the Sun would rise in the west\n"
          "B) North to south — ✗ the axis runs north to south\nC) West to east ✓\n"
          "Hint: Where does the Sun rise?\nWhy: Spinning west to east makes the Sun appear in the east.\n\n"
          "【Example】 1. Taipei turns to face the Sun first. 2. Paris turns to face it hours later. "
          "3. So sunrise in Taipei comes before sunrise in Paris.\n\n【Today's Task】 Watch a sunset.\n\n"
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
    if system.startswith("You design short, structured learning paths"):
        return "design"
    if "replacement questions" in system:
        return "quiz_rewrite"
    if system.startswith(("You write a short quiz", "You write the practice and the mastery check")):
        return "quiz"
    if system.startswith("You write short practice exercises"):
        return "practice_make"
    if "A learner has just explained" in system:
        return "explain"
    if "You asked a learner a follow-up" in system:
        return "explain_follow"
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
    if "她在聊這本書" in system:
        return "reading_chat"
    if stream:
        return "followup" if len([m for m in messages if m["role"] == "user"]) > 1 else "lesson"
    return "json_other"


RIGHT, WRONG = "It spins on its axis", "Solar flares"
OPTIONS = [RIGHT, "It orbits the Sun", "The Moon blocks the light", WRONG]
NOTES = ["", "Orbiting gives the year, not the day", "The Moon only blocks light in an eclipse", "Flares don't cause night"]
PAIRS = [["Axis", "The line Earth spins around"], ["Rotation", "One spin a day"],
         ["Orbit", "One trip around the Sun"], ["Sunrise", "When the Sun comes into view"]]
STEPS = ["Taipei turns toward the Sun", "The Sun rises in Taipei", "Taipei turns away: night falls"]


# different questions, as a real quiz has (the app leaves out plain repeats: quiz.alike)
CHOICES = ("Why does Earth have day and night?", "What makes the Sun seem to rise each morning?",
           "Why is one side of the planet dark while the other is light?", "What would stop sunsets from happening?",
           "Which motion gives a place its daytime hours?", "What turns your city away from sunlight at dusk?",
           "Why do sunrise times move around the world from east to west?")
SCENARIOS = ("Mia in Taipei watches the sky darken in the evening.", "Leo in London sees the Sun come up over the river.")


def _quiz(inject: bool, old: bool = False, recall: bool = False) -> dict:
    extra = f" {INJECT}" if inject else ""
    if old:
        qs = [{"type": "choice", "question": f"{CHOICES[k]}{extra}",
               "options": OPTIONS, "answer": 0, "why": "Earth's spin turns each place toward and away from the Sun."}
              for k in range(7)]
        qs.append({"type": "match", "question": "Match each term to its meaning.", "pairs": PAIRS,
                   "why": "These are the lesson's terms."})
        qs += [{"type": "short", "question": q + extra, "answer": "Because Earth spins on its axis.", "why": "."}
               for q in ("Explain in your own words why we have day and night.",
                         "Why does the Sun seem to rise in the east?")]
        return {"questions": qs}
    qs = [{"role": "check", "type": "choice", "question": f"{CHOICES[k]}{extra}", "options": OPTIONS,
           "answer": 0, "notes": NOTES, "why": "Earth's spin turns each place toward and away from the Sun.",
           "diff": 1, "hint": "Think of one whole day."} for k in range(1)]
    qs += [{"role": "check", "type": "scenario", "scenario": f"{SCENARIOS[k]}{extra}",
            "question": "What causes what they see?", "options": OPTIONS, "answer": 0, "notes": NOTES,
            "why": "Their side of Earth is turning toward or away from the Sun.", "diff": 2} for k in range(1)]
    qs.append({"role": "check", "type": "blank", "question": f"Earth spins on its ____ once a day.{extra}", "answer": "axis",
               "accept": ["own axis"], "why": "The axis is the line it spins around.", "diff": 1})
    qs.append({"role": "check", "type": "order", "question": f"Put a day in Taipei in order.{extra}", "steps": STEPS,
               "why": "The spin carries Taipei toward the Sun, then away.", "diff": 2})
    qs.append({"role": "check", "type": "match", "question": "Match each term to its meaning.", "pairs": PAIRS,
               "why": "These are the lesson's terms.", "diff": 1})
    qs.append({"role": "check", "type": "spot", "question": f"Which line has the mistake?{extra}",
               "lines": ["Earth spins once a day.", "So the Sun rises in the west.", "Night falls as we turn away."],
               "answer": 1, "fix": "So the Sun rises in the east.", "why": "Spinning west to east brings the Sun up in the east.",
               "diff": 3})
    qs.append({"role": "practice", "type": "steps", "question": f"It is noon in Taipei. Is it day or night in Paris?{extra}",
               "steps": ["Taipei faces the Sun at noon.", "Paris is about 7 hours of spin behind, so it still faces ____.",
                         "So in Paris it is early morning, before sunrise."], "answers": ["away"],
               "accept": [["away from the Sun", "away from it"]], "why": "Paris hasn't turned to face the Sun yet.",
               "hint": "Which way has Paris not turned yet?", "diff": 2})
    qs.append({"role": "practice", "type": "problem", "question": f"Why does the Moon look like it rises in the east?{extra}",
               "options": OPTIONS, "answer": 0, "notes": NOTES, "why": "Earth's spin carries us past the Moon too.",
               "hint": "What moves once a day?", "diff": 3})
    if recall:
        qs.append({"type": "choice", "recall": True, "question": "From before: what makes a day?",
                   "options": OPTIONS, "answer": 0, "notes": NOTES, "why": "One spin is one day."})
    return {"questions": qs}


def _design(last: str, inject: bool) -> dict:
    """A path for her goal, or the answer for one that can't be planned yet:
    "doctor" is too big, "hack" or "stocks to buy" isn't taught, "business
    stuff" is too vague (until she answers the question)."""
    goal = re.search(r"Goal: (.*)", last).group(1).lower()
    extra = "INJECT " + INJECT if inject else ""
    if "doctor" in goal:
        return {"status": "narrow", "message": "Becoming a doctor takes years. Here are first steps that fit a few weeks.",
                "suggestions": ["Understand how the heart and blood work", "Learn basic first aid",
                                "Know how medical school works"]}
    if "hack" in goal or "stocks to buy" in goal:
        return {"status": "decline", "message": "We can't help with that here, but here is what we can teach.",
                "suggestions": ["Understand how investing works", "Learn how to read a company report",
                                "Know the risks of investing"]}
    if "business stuff" in goal and "More about my goal" not in last:
        return {"status": "clarify", "message": "Business is a wide field. What would you like to be able to do?",
                "questions": ["Are you starting something of your own, or working in a company?"],
                "suggestions": ["Plan and price a small side business", "Read a company's financial statements",
                                "Run better meetings"]}
    units = [{"name": name, "lessons": [{"title": f"{name}: idea {k + 1}" + (f" {extra}" if extra and k == 0 else ""),
                                         "objective": f"Use {name.lower()} idea {k + 1} on a real example"}
                                        for k in range(4)]}
             for name in ("Foundations", "Core skills", "Putting it together", "Next steps")]
    return {"status": "ok", "title": ("Reading financial statements" if "financ" in goal else "Your path") + extra,
            "outcome": "By the end you will be able to read the three main statements and explain what they say.",
            "level": "Beginner", "units": units}


def _reply(kind: str, messages: list, ctl: dict) -> str:
    inject = ctl.get("inject")
    last = messages[-1]["content"] if messages else ""
    if kind == "design":
        return json.dumps(_design(last, inject))
    if kind == "quiz":
        return json.dumps(_quiz(inject, ctl.get("old_quiz"), '"recall": true' in last))
    if kind == "quiz_rewrite":           # as many of each kind as asked for
        system = messages[0]["content"]
        wanted = {k: int(n) for n, k in re.findall(r'(\d+) "(\w+)"', system.split("The kinds are")[0])}
        full = _quiz(inject)["questions"]
        out = []
        for kind_, n in wanted.items():
            same = [q for q in full if q["type"] == kind_] or [q for q in full if q["type"] == "choice"]
            made = [dict(same[j % len(same)], question=f"Again ({j + 1}): {same[j % len(same)]['question']}")
                    for j in range(n)]
            if kind_ == "scenario":           # a new situation, as a real model writes (not a copy: quiz.alike)
                made = [dict(q, scenario=f"Sam in Sydney waits before dawn for first light, morning {j + 1}.")
                        for j, q in enumerate(made)]
            if kind_ == "choice" and made:
                made[0] = {"type": "choice", "question": "Which way does Earth spin?",
                           "options": ["West to east", "East to west", "North to south", "It doesn't"],
                           "answer": 0, "why": "That's why the Sun rises in the east."}
            out += made
        return json.dumps({"questions": out})
    if kind == "practice_make":
        ideas = [int(k) for k in re.findall(r"^Idea (\d+):", last, re.M)]
        out = []
        for k in ideas:
            out.append({"idea": k, "type": "choice", "question": f"New practice {k}: what makes a day?",
                        "options": OPTIONS, "answer": 0, "notes": NOTES, "why": "One spin is one day."})
            out.append({"idea": k, "type": "blank", "question": f"New practice {k}: Earth spins on its ____.",
                        "answer": "axis", "why": "The line it spins around."})
        return json.dumps({"questions": out})
    if kind == "explain":
        mine = last.split("Her explanation:")[-1].lower()
        if "spin" in mine or "rotat" in mine:
            return json.dumps({"right": "You named the cause: Earth's spin." + (f" {INJECT}" if inject else ""),
                               "rubric": {"idea": True, "why": True, "accurate": True},
                               "missing": "", "verdict": "right", "question": "Why don't we feel the spin?"})
        if "sun" in mine or "day" in mine:
            return json.dumps({"right": "You linked day and night to the Sun.", "verdict": "partly",
                               "rubric": {"idea": True, "why": False, "accurate": True},
                               "missing": "What makes the Sun appear and disappear: Earth's spin.", "question": ""})
        return json.dumps({"right": "Nothing yet that explains it.", "verdict": "wrong",
                           "missing": "Say what causes day and night: Earth spinning on its axis.", "question": ""})
    if kind == "explain_follow":
        mine = last.split("Her answer:")[-1].lower()
        ok = "steady" in mine or "smooth" in mine or "same speed" in mine
        return json.dumps({"feedback": "Yes: the spin is smooth and steady." if ok else
                           "Think about how a smooth ride feels.", "verdict": "right" if ok else "partly"})
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
                partly = not ok and ("sun" in ans or "day" in ans)
                results.append({"id": k, "verdict": "right" if ok else ("partly" if partly else "wrong"),
                                "feedback": ("Right: it's the spin." if ok else
                                             "On the right track; name what causes it." if partly else
                                             "It doesn't mention Earth's spin.")
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
        asked = last.lower()
        if "pizza" in asked:            # off topic: back to the subject, gently
            return ("That's outside today's subject; here we stick to Earth and the sky. You could ask why "
                    "the Sun rises in the east.\n\nBased on: beyond this lesson\nConfused: no")
        if "exact" in asked and "speed" in asked:
            return ("I'm not sure of the exact figure to quote here, so I won't guess. The lesson's point is "
                    "that the spin is steady.\n\nBased on: not sure\nConfused: no")
        confused = "orbit" in asked and "day" in asked          # mixing up the spin and the orbit
        return ("Good question. Earth's spin is smooth and steady, so we don't feel it."
                + (" One small fix: a day comes from the spin, not the orbit." if confused else "")
                + (f" {INJECT}" if inject else "")
                + f"\n\nBased on: Key Idea\nConfused: {'yes' if confused else 'no'}")
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
        failing = (mode != "ok" and (fail_times is None or n <= int(fail_times))
                   and (not ctl.get("fail_kinds") or kind in ctl["fail_kinds"]))
        if failing and mode in ("413", "429", "500"):
            raise _status_error(int(mode))
        if failing and mode == "timeout":
            raise groq.APITimeoutError(request=httpx.Request("POST", "https://api.groq.com"))
        text = _reply(kind, messages, ctl)
        if failing and mode == "empty":
            text = ""
        if failing and mode == "invalid":
            text = "Sorry, here is some prose instead of JSON." if not stream else ""
        if failing and mode == "malformed_quiz" and kind == "quiz":
            q = json.loads(text)                     # valid JSON, but one question has 3 options
            q["questions"][0]["options"] = q["questions"][0]["options"][:3]
            text = json.dumps(q)
        if failing and mode == "truncated_quiz" and kind == "quiz":
            text = text[:len(text) * 2 // 3]
        usage = types.SimpleNamespace(total_tokens=max(1, len(text) // 4))
        if stream:
            words = text.split(" ") if text else []
            broken = failing and mode == "broken_stream"

            def gen():
                for k, w in enumerate(words):
                    if broken and k == 5:
                        raise groq.APIConnectionError(request=httpx.Request("POST", "https://api.groq.com"))
                    if ctl.get("chunk_delay"):
                        time.sleep(float(ctl["chunk_delay"]))
                    yield _chunk(w + (" " if k < len(words) - 1 else ""))
                yield _chunk("", finish="stop")
            return gen()
        cut = failing and mode == "truncated_quiz" and kind == "quiz"
        return types.SimpleNamespace(usage=usage, choices=[types.SimpleNamespace(
            message=types.SimpleNamespace(content=text), finish_reason="length" if cut else "stop")])
