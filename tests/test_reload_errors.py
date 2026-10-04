"""New code loaded while a session is mid-run (coach.freshen): an error
raised by the store the run began with is still caught by the page's
`except storage.StorageError` on the new code."""
import sys

import coach
from coach import storage


def test_a_storage_error_is_caught_across_a_reload(monkeypatch, tmp_path):
    old_storage = storage
    raised = old_storage.StorageError("the database isn't responding right now")
    monkeypatch.setattr(coach, "_changed", lambda: ["coach.storage"])
    saved = {k: v for k, v in sys.modules.items() if k.startswith("coach.")}
    try:
        assert coach.freshen()
        from coach import storage as new_storage
        assert new_storage is not old_storage, "the module itself was reloaded"
        try:
            raise raised
        except new_storage.StorageError:
            pass
    finally:                                   # the rest of the tests keep the modules they imported
        sys.modules.update(saved)
        for name, module in saved.items():
            setattr(coach, name.split(".", 1)[1], module)
