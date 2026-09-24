"""Conservative token estimates and the per-request budget.

Groq's free tier allows 8000 tokens per minute for openai/gpt-oss-120b,
and it counts a request's prompt *plus its max_tokens* against that. So
every request is kept under REQUEST_BUDGET before it is sent.

Calibration: the request that failed with 413 ("Requested 9439") was
9,969 characters (9,419 CJK) with max_tokens=2048, i.e. about 7,391
prompt tokens, 0.74 per character. Counting 1.0 per CJK character and
0.3 per other character gives 9,584 for that text, about 30% high, so
these estimates err on the safe side."""
import math
import re

# One request stays well under the 8000/minute limit; two in the same
# minute (a lesson, then a quick follow-up) may hit a 429, which llm.py
# waits out and retries.
REQUEST_BUDGET = 5500        # system + history + max_tokens, estimated (~30% high)
MESSAGE_OVERHEAD = 4         # role markers etc. per message
REQUEST_OVERHEAD = 3

# Completion budgets. Groq counts these toward the limit even if unused,
# so they are sized to the reply, with reasoning_effort="low" on the call.
LESSON_MAX_TOKENS = 2400     # seven-block lesson, ~600–1000 characters plus reasoning
CHAT_MAX_TOKENS = 900        # follow-ups and book chat
JSON_MAX_TOKENS = 900        # verdicts / plan adjustments

CJK = re.compile(r"[⺀-鿿豈-﫿＀-￯　-〿]")


def estimate(text: str) -> int:
    cjk = len(CJK.findall(text))
    return math.ceil(cjk * 1.0 + (len(text) - cjk) * 0.3)


def estimate_request(system: str, messages: list, max_tokens: int) -> int:
    body = estimate(system) + sum(estimate(m["content"]) for m in messages)
    overhead = MESSAGE_OVERHEAD * (len(messages) + 1) + REQUEST_OVERHEAD
    return body + overhead + max_tokens


def fit_messages(system: str, messages: list, max_tokens: int, budget: int = REQUEST_BUDGET):
    """Drop the oldest messages until the request fits. If the newest
    message alone still doesn't fit, shorten it from the start (keeping
    its end, which is usually the actual question). Returns (messages,
    dropped_count). Raises ValueError if even the system prompt alone
    doesn't fit, which would be a bug in how the prompt was built."""
    if estimate_request(system, [], max_tokens) > budget:
        raise ValueError("system prompt exceeds the request budget")
    kept = list(messages)
    dropped = 0
    while len(kept) > 1 and estimate_request(system, kept, max_tokens) > budget:
        kept.pop(0)
        dropped += 1
    if kept and estimate_request(system, kept, max_tokens) > budget:
        room = budget - estimate_request(system, [{"content": ""}], max_tokens)
        content = kept[0]["content"]
        while content and estimate(content) > room:
            content = content[max(1, len(content) // 10):]
        kept[0] = {**kept[0], "content": content}
    return kept, dropped
