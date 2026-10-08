# GNOSIS backend

The platform's own backend (docs/ARCHITECTURE_ASSESSMENT.md, docs/adr/). It
is being built step by step while the current app keeps running:

| Step | State |
|---|---|
| M1: skeleton, our PostgreSQL schema, migrations, repositories, importer from Supabase | **done** |
| M2: learner API; the current app runs on it | next |
| M3: our own sign-in, sessions, roles; Supabase removed | |
| M4: AI gateway | |
| M5: TypeScript web + admin apps | |

## Layout

```
gnosis/
  app.py                 FastAPI app: routers, request id, timing, safe errors
  api/                   routes (health now; the learner API in M2)
  data/schema.py         every table (changes only through a migration)
  data/repositories/     the only code that touches the database
    learning.py          her learning record <-> tables, exactly
    accounts.py          users, identities, credentials, roles, settings, prefs, counts, audit
  migrate/supabase.py    the move out of Supabase, checked person by person
  infra/                 configuration (environment only), JSON logging
migrations/              Alembic: 0001 = the initial schema + built-in roles
tests/                   against a real PostgreSQL (never a mock)
```

The learning rules are the shared package `coach/` at the repository root
(pure modules only; `tests/test_layers.py` enforces it).

## Run it

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt pytest httpx requests
export GNOSIS_DATABASE_URL=postgresql+psycopg://user:pass@host:5432/gnosis
PYTHONPATH=.:.. .venv/bin/alembic upgrade head          # the schema
PYTHONPATH=.:.. .venv/bin/uvicorn gnosis.app:app        # the API (/health, /ready, /docs outside production)
```

Or everything in containers: `docker compose -f infra/compose.yaml up --build`
(copy `infra/env.example` to `infra/.env` first).

Tests: `GNOSIS_TEST_DATABASE_ADMIN_URL=postgresql+psycopg://user@host:5432/postgres .venv/bin/python -m pytest`
(the tests create and drop their own database).

## Moving the data out of Supabase

```bash
# check everything, keep nothing:
PYTHONPATH=.:.. .venv/bin/python -m gnosis.migrate.supabase --source "$SUPABASE_DB_URL" --dry-run
# then for real (safe to run again: it replaces what an earlier run wrote):
PYTHONPATH=.:.. .venv/bin/python -m gnosis.migrate.supabase --source "$SUPABASE_DB_URL"
```

`SUPABASE_DB_URL` is the connection string in Supabase → Project Settings →
Database. The source is only read. Each person is copied in their own
transaction, read back and compared with the source; a mismatch rolls that
person back and is reported. Password hashes and Google identities come
across, so nobody resets a password at the switch.
