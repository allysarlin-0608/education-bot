"""The learner model's arithmetic (docs/LEARNING_DESIGN.md §2): how likely
she has learned an idea, and how likely she still remembers a card.

- Bayesian knowledge tracing (Corbett & Anderson 1995): the chance an idea
  is learned, P(L), updated by each piece of evidence. A right answer can
  be a guess (GUESS, by kind of evidence) and a wrong one a slip (SLIP);
  every practice is a chance to learn it (LEARN). Evidence is a score from
  0 to 1, so a part-right answer moves P(L) part of the way (soft evidence:
  the two posteriors mixed by the score). The parameters are the usual
  defaults in the literature, not fitted to our learners yet:
  tools/fit_models.py estimates them once there are attempts to fit.
- FSRS-4.5 (the open spaced-repetition scheduler Anki now uses): a card's
  stability S (days until recall falls to 90%) and difficulty D (1-10) move
  with each review's rating; the next review is set for when recall would
  fall to the target retention. Default weights.

Pure functions; no Streamlit, no AI call."""
import math

# --------------------------------------------------- knowledge tracing (BKT)
P_INIT = 0.1                # an idea she has never met
P_KNOWN = 0.85              # an idea the diagnostic says she knows already
LEARN = 0.2                 # chance of learning it from one day's practice
SLIP = 0.1
# a right answer by luck: a quiz is many questions (hard to pass by luck), a
# card or a quick check is one; a question that showed confusion is weak evidence
GUESS = {"quiz": 0.1, "recall": 0.25, "review": 0.2, "practice": 0.2, "explain": 0.1, "ask": 0.5,
         "check": 0.3, "diag": 0.25}
WEAK_SLIP = {"ask": 0.3}


def bkt(p: float, score: float, kind: str = "quiz", learn: bool = True) -> float:
    """P(L) after one piece of evidence scored 0..1."""
    guess = GUESS.get(kind, 0.2)
    slip = WEAK_SLIP.get(kind, SLIP)
    score = min(1.0, max(0.0, float(score)))
    right = p * (1 - slip) / (p * (1 - slip) + (1 - p) * guess)
    wrong = p * slip / (p * slip + (1 - p) * (1 - guess))
    post = score * right + (1 - score) * wrong
    if learn and kind != "ask":
        post += (1 - post) * LEARN
    return min(0.999, max(0.001, post))


# ------------------------------------------------------ memory (FSRS-4.5)
W = (0.4872, 1.4003, 3.7145, 13.8206, 5.1618, 1.2298, 0.8975, 0.031, 1.6474, 0.1367,
     1.0461, 2.1072, 0.0793, 0.3246, 1.587, 0.2272, 2.8755)
DECAY = -0.5
FACTOR = 19 / 81            # so that recall is 90% after S days
AGAIN, HARD, GOOD, EASY = 1, 2, 3, 4
TARGET = 0.9                # the retention reviews are scheduled for
MAX_INTERVAL = 365


def retrievability(elapsed: float, stability: float) -> float:
    """The chance of recalling it `elapsed` days after the last review."""
    return (1 + FACTOR * max(0.0, elapsed) / max(stability, 0.01)) ** DECAY


def interval(stability: float, target: float = TARGET) -> int:
    """Days until recall falls to `target` (at least 1, at most MAX_INTERVAL)."""
    days = stability / FACTOR * (target ** (1 / DECAY) - 1)
    return int(min(MAX_INTERVAL, max(1, round(days))))


def _d0(rating: int) -> float:
    return min(10.0, max(1.0, W[4] - (rating - 3) * W[5]))


def first(rating: int) -> tuple:
    """(stability, difficulty) after a card's first review."""
    return W[rating - 1], _d0(rating)


def review(stability: float, difficulty: float, elapsed: float, rating: int) -> tuple:
    """(stability, difficulty) after a review `elapsed` days after the last one."""
    r = retrievability(elapsed, stability)
    d = difficulty - W[6] * (rating - 3)
    d = min(10.0, max(1.0, W[7] * _d0(GOOD) + (1 - W[7]) * d))
    if rating == AGAIN:
        s = W[11] * difficulty ** -W[12] * ((stability + 1) ** W[13] - 1) * math.exp(W[14] * (1 - r))
        return max(0.1, min(s, stability)), d
    hard = W[15] if rating == HARD else 1.0
    easy = W[16] if rating == EASY else 1.0
    s = stability * (math.exp(W[8]) * (11 - difficulty) * stability ** -W[9]
                     * (math.exp(W[10] * (1 - r)) - 1) * hard * easy + 1)
    return min(s, 36500.0), d


def rating(right: bool, confidence=None) -> int:
    """A review's rating from whether it was right and how sure she was
    (1 guessed, 2 fairly sure, 3 sure; None: not asked)."""
    if not right:
        return AGAIN
    return {1: HARD, 2: GOOD, 3: EASY}.get(confidence, GOOD)


# ------------------------------------------------------- confidence ratings
CONFIDENCE = (1, 2, 3)      # guessed, fairly sure, sure (docs/LEARNING_DESIGN.md §3)


def confidence(value):
    """A saved confidence rating, checked (None if there isn't one)."""
    return value if isinstance(value, int) and not isinstance(value, bool) and value in CONFIDENCE else None


def overconfident(right: bool, conf) -> bool:
    """Sure, and wrong: the error worth bringing back first (hypercorrection)."""
    return not right and conf == 3
