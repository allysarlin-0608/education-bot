"""New code on disk while the server runs (a push Streamlit Cloud pulls in
while nobody is on the site): the next run loads every coach module anew,
not new pages on old modules (the course map's ui.open_course crash).
Run in a separate Python, so this suite's own modules stay as they are."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SCRIPT = r'''
import sys
import coach
from coach import routes            # the server's routes, imported at start (they bring coach.ui)
from coach import ui
old_ui, old_routes = ui, routes
assert coach.freshen() is False, "nothing changed yet"
coach._loaded["coach.ui"] -= 5      # as if ui.py were replaced on disk after it was loaded
assert coach.freshen() is True and coach.GENERATION == 1
assert "coach.ui" not in sys.modules and not hasattr(coach, "ui")
from coach import ui                 # this run gets the file as it is now
assert ui is not old_ui and hasattr(ui, "open_course")
assert sys.modules["coach.routes"] is old_routes, "the server's routes are kept"
assert coach.freshen() is False, "once is enough"
print("ok")
'''


def test_new_code_on_disk_is_loaded_whole():
    r = subprocess.run([sys.executable, "-c", SCRIPT], cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0 and r.stdout.strip().endswith("ok"), r.stdout + r.stderr
