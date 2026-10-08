# 0002 — Our own PostgreSQL schema, migrations and data-access layer

**Context.** Today the data sits in Supabase Postgres, reached through
PostgREST. A day's lessons, quizzes, cards and evidence are a JSON array in
one column, so no constraint or index covers them, and only the latest quiz
attempt is kept.

**Decision.** PostgreSQL (16+) on infrastructure we choose. A relational
schema (users, identities, sessions, roles; subjects, goals, study days,
lesson progress and content, quiz attempts/questions/answers, review cards,
mastery evidence, practice items, explanations, messages; usage, signals,
audit log), evolved only through Alembic migrations. Access only through
repositories in `gnosis/data` (SQLAlchemy Core, parameterised SQL). JSON
columns only for content that is a document (a lesson's text, a question's
options, a goal's path, a reading plan, a setup draft).

**Consequences.** Constraints and indexes protect the data; analytics and
admin read tables, not blobs; the database host is replaceable with a
`pg_dump`. Repositories translate between the tables and the shapes the
domain functions take, so the domain keeps working unchanged.
