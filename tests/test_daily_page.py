"""Page-level guards for views/daily.py."""
import re
from pathlib import Path

DAILY = Path(__file__).resolve().parent.parent / "views" / "daily.py"


def test_each_kind_of_retry_is_shown_in_one_place_only():
    # Two Retry buttons with one key on the same run crash the page
    # (StreamlitDuplicateElementKey), so every failure kind has one home.
    source = DAILY.read_text(encoding="utf-8")
    calls = re.findall(r"show_retry\(slot, \(([^)]*)\)\)", source)
    kinds = [k.strip().strip('"') for call in calls for k in call.split(",") if k.strip()]
    assert sorted(kinds) == ["followup", "grade", "kickoff", "quiz"]
    assert 'key=f"coach_retry_{retry[\'kind\']}"' in source
