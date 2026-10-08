# 0001 — Modular monolith backend in Python (FastAPI)

**Context.** About 30 domain modules (`coach/`: curriculum, quiz, review,
mastery, practice, streaks, habit, paths, metrics…) are pure Python with
~685 tests. The app has no API: Streamlit pages call them in-process.

**Decision.** One backend service in `backend/` (package `gnosis`), built
on FastAPI, importing the domain package unchanged. Internal layers:
`api` → `services` → `domain` / `data` / `ai` → `infra`, with import rules
enforced by tests (as `tests/test_layers.py` does today). A background
worker runs from the same codebase. No microservices until a module has a
measured reason to be split.

**Consequences.** The learning rules are moved, not rewritten. One
deployable keeps operations simple; boundaries keep a later split
possible. Python's typing (Pydantic, type hints) gives the API contract
(OpenAPI) the frontends are generated from.
