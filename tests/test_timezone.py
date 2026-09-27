"""COACH_TIMEZONE decides the learner's date everywhere (not the server's)."""
import importlib
from datetime import datetime
from zoneinfo import ZoneInfo

from coach import books, ui


def test_the_learners_date_follows_coach_timezone(monkeypatch):
    # covers: S-coach_timezone
    for zone in ("Pacific/Kiritimati", "Pacific/Pago_Pago"):     # UTC+14 and UTC-11: always different dates
        monkeypatch.setenv("COACH_TIMEZONE", zone)
        importlib.reload(ui)
        expected = datetime.now(ZoneInfo(zone)).date()
        assert ui.TIMEZONE.key == zone
        assert books._local_today() == expected
    monkeypatch.delenv("COACH_TIMEZONE")
    importlib.reload(ui)
    assert ui.TIMEZONE.key == "Asia/Taipei"
