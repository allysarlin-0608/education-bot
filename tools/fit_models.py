"""Fit the knowledge-tracing parameters (coach/learner.py) to real answers:

    python tools/fit_models.py answers.csv

The app starts with the usual defaults from the literature (guess, slip,
learn). With enough answers, this searches a grid for the values that make
the answers most likely (each idea's answers in order, per learner), by
kind of exercise context, and prints them beside the defaults. Changing
the app's values stays a decision for a person, made with the report in
hand; this only measures."""
import math
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from coach import learner  # noqa: E402
from learning_report import read_csv  # noqa: E402

GRID = [x / 20 for x in range(1, 10)]          # 0.05 ... 0.45


def likelihood(seqs, p0, learn, guess, slip) -> float:
    total = 0.0
    for answers in seqs:
        p = p0
        for right in answers:
            pr = p * (1 - slip) + (1 - p) * guess
            total += math.log(max(1e-9, pr if right else 1 - pr))
            p = p * (1 - slip) / pr if right else p * slip / (1 - pr)
            p = p + (1 - p) * learn
    return total


def fit(rows):
    seqs = defaultdict(list)
    for r in sorted(rows, key=lambda r: r["day"]):
        if r["score"] is not None and r["first"] and r["ctx"] not in ("jol", "step", "explain"):
            seqs[(r.get("learner", ""), r["topic"], r["n"])].append(r["score"] >= 0.999)
    seqs = [s for s in seqs.values() if len(s) >= 2]
    if len(seqs) < 30:
        return None, len(seqs)
    best = max(((learner.P_INIT, l, g, s) for l in GRID for g in GRID for s in GRID if g < 0.5 and s < 0.5),
               key=lambda x: likelihood(seqs, *x))
    return best, len(seqs)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    best, n = fit(read_csv(sys.argv[1]))
    if best is None:
        print(f"Only {n} ideas with two or more answers: not enough to fit (30 needed). Keep the defaults.")
    else:
        print(f"Fitted on {n} ideas: learn {best[1]}, guess {best[2]}, slip {best[3]} "
              f"(defaults: learn {learner.LEARN}, guess ~0.2, slip {learner.SLIP})")
