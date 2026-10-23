"""The learning numbers as text, from answer rows (docs/LEARNING_DESIGN.md §7):

    python tools/learning_report.py answers.csv        # the dashboard's download
    python tools/learning_report.py --local            # this machine's local store (learning_attempts.json)

The same arithmetic as the learning dashboard (coach/learnmetrics.py)."""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from coach import attempts, learnmetrics, storage  # noqa: E402


def read_csv(path):
    out = []
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            row = attempts.parse({**r, "n": int(r["n"]), "first": r.get("first") == "True",
                                  **{k: (float(r[k]) if k == "score" else int(r[k])) if r.get(k) not in ("", None) else None
                                     for k in ("score", "conf", "secs", "gap", "diff")}})
            if row:
                out.append(dict(row, learner=r.get("learner", "")))
    return out


def pct(x):
    return "—" if x is None else f"{x * 100:.0f}%"


def report(rows) -> str:
    m = learnmetrics.summarize(rows)
    lines = [f"Answers: {m['engagement']['answers']} from {m['engagement']['learners']} learners "
             f"in {m['engagement']['sessions']} sessions", ""]
    f = m["first"]["all"]
    lines.append(f"First try right: {pct(f['share'])} (n={f['n']})")
    for k, v in m["first"]["by_ctx"].items():
        lines.append(f"  {k:9} {pct(v['share']):>5} (n={v['n']})")
    lines.append("Remembered later:")
    for d, v in m["retention"].items():
        lines.append(f"  {d:>2}+ days  {pct(v['share']):>5} (n={v['n']})")
    t = m["remembered"]
    lines.append(f"Ideas known a week later: {t['remembered']} of {t['ideas']}, median {t['median_days']} days")
    c = m["calibration"]
    lines.append("Calibration: " + ", ".join(f"conf {k} → {pct(v['share'])} (n={v['n']})" for k, v in c["by_conf"].items())
                 + f"; sure but wrong {pct(c['sure_but_wrong'])}; Brier {c['brier'] if c['brier'] is None else round(c['brier'], 3)}")
    lines.append("Where sessions stop: " + " → ".join(f"{s} {n}" for s, n, _ in m["funnel"]))
    for name, e in m["experiments"].items():
        (a, ra), (b, rb) = e["arms"].items()
        d = e["difference"]
        lines.append(f"Experiment {name} ({e['measure']}): {a} {pct(ra['share'])} (n={ra['n']}) vs "
                     f"{b} {pct(rb['share'])} (n={rb['n']}) · "
                     + (f"difference {d['diff'] * 100:+.0f} pts, 95% CI {d['ci'][0] * 100:+.0f} to {d['ci'][1] * 100:+.0f}"
                        if d else "not enough data"))
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--local":
        store = storage.FileStore()
        rows = [storage.pseudonymous(r) for r in store._rows(storage.ATTEMPTS_TABLE)]
    elif len(sys.argv) > 1:
        rows = read_csv(sys.argv[1]) if sys.argv[1].endswith(".csv") else json.loads(Path(sys.argv[1]).read_text())
    else:
        sys.exit(__doc__)
    print(report(rows))
