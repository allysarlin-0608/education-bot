#!/usr/bin/env bash
# The check that runs before anything is pushed (.githooks/pre-push) and on
# GitHub for every push (.github/workflows/check.yml): about 15 seconds.
#   - every unit test, including:
#     tests/test_references.py   every name the app takes from its own modules exists
#     tests/test_pages_smoke.py  every page loads, and every way into the course map works
#     tests/test_freshen.py      new code on disk is loaded whole (no half-old app after a deploy)
#   - the feature inventory: every control the code has is named by a test
# The full browser suite (pytest tests/e2e) is longer and runs before a release.
set -euo pipefail
cd "$(dirname "$0")/.."
python -m pytest -q tests -p no:cacheprovider
python tools/inventory.py --check
