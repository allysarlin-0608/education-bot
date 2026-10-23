"""The learning dashboard (admins only; docs/LEARNING_DESIGN.md §7): is
GNOSIS making people learn? From the answer rows (coach/attempts.py, table
learning_attempts), as coach/learnmetrics.py defines each number, with a
plain line on what it means. Who answered is never shown."""
from datetime import timedelta
from html import escape

import streamlit as st

from coach import auth, learnmetrics, storage, ui
from coach.i18n import N_, tr

st.html('<div id="learning-page" hidden></div>')
st.html('<p class="cm-eyebrow">' + tr("Admins") + "</p>")
st.markdown(tr("## Learning dashboard"))
if not auth.is_admin():
    st.caption(tr("Only admins can see this page."))
    st.stop()
st.caption(tr("Whether people are learning, not only using it. Who answered is never shown; small numbers say "
              "little, and below {n} answers an experiment's arms aren't compared.", n=learnmetrics.MIN_N))
since = st.date_input(tr("Answers since"), value=ui.today() - timedelta(days=30), max_value=ui.today(), key="ld_since")
try:
    rows = st.session_state.coach_store.attempts_since(since)
except (storage.StorageError, AttributeError) as e:
    st.html('<p class="ob-note">' + tr("Couldn't load the answers ({e}). If they aren't set up yet, run "
                                       "supabase/learning_v2.sql in the test database first.", e=escape(str(e))) + "</p>")
    st.stop()
m = learnmetrics.summarize(rows)
if rows:                     # the rows themselves, for analysis elsewhere (no one named: tools/learning_report.py)
    import csv
    import io
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=sorted({k for r in rows for k in r}))
    w.writeheader()
    w.writerows(rows)
    st.download_button(tr("Download the answers (CSV)"), buf.getvalue(), file_name=f"gnosis-answers-{since}.csv",
                       mime="text/csv", key="ld_csv", type="tertiary")


def pct(x) -> str:
    return "—" if x is None else f"{x * 100:.0f}%"


def ci(r) -> str:
    return "" if not r or not r.get("ci") else tr("95% CI {lo}–{hi}", lo=pct(r["ci"][0]), hi=pct(r["ci"][1]))


def table(rows_, note: str = "") -> None:
    st.html('<dl class="ins-list">' + "".join(
        f'<div><dt>{escape(a)}{f"<small>{escape(d)}</small>" if d else ""}</dt><dd>{escape(b)}<small>{escape(c)}</small></dd></div>'
        for a, b, c, d in rows_) + "</dl>" + (f'<p class="ob-note">{escape(note)}</p>' if note else ""))


CTX = {"warmup": N_("Warm-up"), "check": N_("Quick checks in lessons"), "guided": N_("Guided practice"),
       "quiz": N_("The check"), "mixed": N_("Mixed practice"), "practice": N_("Practice page"),
       "review": N_("Review cards"), "unit": N_("Unit checks"), "diag": N_("Where to start")}
STEPS = {"warmup": N_("Warm-up"), "learn": N_("Read the lesson"), "practice": N_("Practise"), "quiz": N_("The check"),
         "passed": N_("Passed"), "mixed": N_("Mixed practice"), "explain": N_("Explain it back"), "reflect": N_("Reflect")}

st.markdown(tr("#### First try"))
f = m["first"]
table([(tr("All first tries"), pct(f["all"]["share"]), f'n={f["all"]["n"]} · {ci(f["all"])}',
        tr("70–85% is hard enough to teach and easy enough to keep at."))]
      + [(tr(CTX[k]), pct(v["share"]), f'n={v["n"]}', "") for k, v in f["by_ctx"].items()]
      + [(tr("Difficulty {d}", d=d), pct(v["share"]), f'n={v["n"]}', "") for d, v in f["by_diff"].items()])

st.markdown(tr("#### Remembered later"))
r = m["retention"]
table([(tr("{d}+ days after the last practice", d=d), pct(v["share"]), f'n={v["n"]} · {ci(v)}', "")
       for d, v in r.items()], tr("Reviews and warm-up items: the share she still knew."))
t = m["remembered"]
table([(tr("Ideas known a week later"), f'{t["remembered"]} / {t["ideas"]}',
        tr("median {d} days from first answer", d=t["median_days"]) if t["median_days"] is not None else "",
        tr("Right a week or more after the answer before it."))])

st.markdown(tr("#### Knowing what you know"))
c = m["calibration"]
names = {1: tr("Guessing"), 2: tr("Fairly sure"), 3: tr("Sure")}
table([(names[k], pct(v["share"]), f'n={v["n"]}', "") for k, v in c["by_conf"].items()]
      + [(tr("Sure, but wrong"), pct(c["sure_but_wrong"]), f'n={c["sure_n"]}', tr("These cards come back first.")),
         (tr("Brier score"), "—" if c["brier"] is None else f'{c["brier"]:.3f}', "", tr("Lower is better; 0.25 is chance."))]
      + [(tr("“Will you remember?” {a} → next answer", a=tr(x)), pct(c["jol"][k]["share"]), f'n={c["jol"][k]["n"]}', "")
         for k, x in ((1, "Not yet"), (2, "Mostly"), (3, "Yes, clearly"))])

st.markdown(tr("#### Where sessions stop"))
table([(tr(STEPS.get(step, step)), str(n), pct(share) + tr(" of the step before") if share is not None else "", "")
       for step, n, share in m["funnel"]], tr("Sessions (a learner on a day) that reached each step."))

st.markdown(tr("#### Experiments"))
for name, e in m["experiments"].items():
    a_, b_ = list(e["arms"].items())
    d = e["difference"]
    said = (tr("difference {d} (95% CI {lo} to {hi})", d=f'{d["diff"] * 100:+.0f} pts', lo=f'{d["ci"][0] * 100:+.0f}',
               hi=f'{d["ci"][1] * 100:+.0f}') if d else tr("not enough data yet: don't draw a conclusion"))
    table([(f"{name} · {a_[0]}", pct(a_[1]["share"]), f'n={a_[1]["n"]}', e["measure"]),
           (f"{name} · {b_[0]}", pct(b_[1]["share"]), f'n={b_[1]["n"]}', ""),
           (tr("Difference"), "", said, "")])

st.markdown(tr("#### Activity (not learning)"))
g = m["engagement"]
table([(tr("Learners"), str(g["learners"]), "", ""), (tr("Sessions"), str(g["sessions"]), "", ""),
       (tr("Answers"), str(g["answers"]), "", tr("Activity says people came, not that they learned."))])
