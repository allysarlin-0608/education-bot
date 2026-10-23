"""The learning numbers (coach/learnmetrics.py) from answer rows, and the
report and fitting tools that read the dashboard's download."""
import csv
from datetime import date, timedelta

from coach import attempts, learnmetrics

D = date(2026, 11, 2)


def row(day, n, ctx, kind="choice", score=1.0, first=True, conf=None, gap=None, diff=None, variant="", who="a"):
    r = attempts.row(D + timedelta(days=day), "math", n, ctx, kind, score=score, first=first, conf=conf, gap=gap,
                     diff=diff, variants=(variant,) if variant else ())
    return dict(r, learner=who)


def test_first_tries_retention_and_known_a_week_later():
    rows = [row(0, 1, "check", score=1, diff=1), row(0, 1, "quiz", score=0, diff=3), row(0, 2, "quiz", score=1),
            row(8, 1, "review", score=1, gap=8), row(8, 2, "review", score=0, gap=8), row(2, 2, "warmup", gap=2)]
    m = learnmetrics.summarize(rows)
    assert m["first"]["all"]["n"] == 6 and m["first"]["by_ctx"]["quiz"]["share"] == 0.5
    assert m["first"]["by_diff"][3]["share"] == 0
    assert m["retention"][7]["n"] == 2 and m["retention"][7]["share"] == 0.5 and m["retention"][1]["n"] == 3
    assert m["remembered"] == {"ideas": 2, "remembered": 1, "median_days": 8}


def test_calibration_says_how_often_sure_was_wrong_and_judges_the_judgment():
    rows = [row(0, 1, "quiz", score=1, conf=3), row(0, 2, "quiz", score=0, conf=3), row(0, 3, "quiz", score=1, conf=1),
            row(0, 1, "jol", kind="jol", score=None, conf=3), row(3, 1, "review", score=1, gap=3)]
    c = learnmetrics.summarize(rows)["calibration"]
    assert c["sure_but_wrong"] == 0.5 and c["sure_n"] == 2 and c["by_conf"][1]["share"] == 1
    assert c["jol"][3]["n"] == 1 and c["jol"][3]["share"] == 1
    assert 0 < c["brier"] < 1


def test_where_sessions_stop():
    rows = [row(0, 1, "step", kind="warmup", score=None), row(0, 1, "step", kind="learn", score=None),
            row(0, 1, "step", kind="learn", score=None, who="b")]
    f = dict((s, (n, share)) for s, n, share in learnmetrics.summarize(rows)["funnel"])
    assert f["warmup"] == (1, None) and f["learn"][0] == 2 and f["practice"][0] == 0


def test_experiments_compare_arms_only_with_enough_answers():
    rows = []
    for k in range(40):                       # blocked ideas: remembered a week later half the time
        rows += [row(0, k, "mixed", variant="interleave:blocked", who=f"b{k}"),
                 row(9, k, "review", score=float(k % 2), gap=9, who=f"b{k}")]
    for k in range(40):                       # mixed: mostly remembered
        rows += [row(0, 100 + k, "mixed", variant="interleave:mixed", who=f"m{k}"),
                 row(9, 100 + k, "review", score=float(k % 5 != 0), gap=9, who=f"m{k}")]
    e = learnmetrics.summarize(rows)["experiments"]
    il = e["interleave"]
    assert il["enough"] and il["arms"]["mixed"]["share"] == 0.8 and il["arms"]["blocked"]["share"] == 0.5
    assert il["difference"]["diff"] < 0 and il["difference"]["ci"][1] < 0, "mixed is better here, beyond chance"
    assert not e["fading"]["enough"] and e["fading"]["difference"] is None
    lo, hi = learnmetrics.wilson(8, 10)
    assert lo < 0.8 < hi and learnmetrics.wilson(0, 0) is None


def test_the_report_reads_the_dashboards_download(tmp_path):
    import sys
    sys.path.insert(0, "tools")
    import learning_report
    rows = [row(0, 1, "quiz", score=1, conf=2), row(8, 1, "review", score=1, gap=8)]
    path = tmp_path / "answers.csv"
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=sorted(rows[0]))
        w.writeheader()
        w.writerows(rows)
    back = learning_report.read_csv(path)
    assert [r["ctx"] for r in back] == ["quiz", "review"] and back[1]["gap"] == 8
    text = learning_report.report(back)
    assert "First try right: 100%" in text and "Experiment interleave" in text
    import fit_models
    assert fit_models.fit(back)[0] is None, "too few answers: the defaults stay"
