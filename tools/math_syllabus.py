"""Writes coach/curriculum/math.txt from the math curriculum file
(data/math_curriculum_zh-Hant.json): a unit per curriculum unit, headed
"<id> <English title>", a lesson per learning outcome (its English text),
every unit after the units it needs (file order otherwise).

    python tools/math_syllabus.py          # write it
    python tools/math_syllabus.py --check  # fail if it is out of date"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from coach import mathcourse  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "coach" / "curriculum" / "math.txt"
CJK = re.compile(r"[　-鿿＀-￯]")


def ordered(data: dict) -> list:
    every = mathcourse.units(data)
    done, out = set(), []

    def place(uid):
        if uid in done:
            return
        done.add(uid)
        for p in every[uid].get("prerequisites", []):
            if p in every:
                place(p)
        out.append(every[uid])
    for uid in every:
        place(uid)
    return out


def text(data: dict) -> str:
    lines = []
    for u in ordered(data):
        title, outcomes = u["title_en"].strip(), [o.strip() for o in u["learning_outcomes_en"]]
        assert not CJK.search(title + "".join(outcomes)), f"{u['id']}: Chinese in its English text"
        lines.append(f"# {u['id']} {title}")
        lines += [o[0].upper() + o[1:] for o in outcomes]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    want = text(mathcourse.load())
    if "--check" in sys.argv:
        sys.exit(0 if OUT.read_text(encoding="utf-8") == want else "coach/curriculum/math.txt is out of date: run python tools/math_syllabus.py")
    OUT.write_text(want, encoding="utf-8")
    print(f"{want.count(chr(10) + '# ') + 1} units, {sum(1 for l in want.splitlines() if not l.startswith('# '))} lessons")
