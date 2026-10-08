# Architecture decision records

One file per decision: context, decision, consequences. Numbered, never
rewritten; a later record supersedes an earlier one. The overall plan is
`docs/ARCHITECTURE_ASSESSMENT.md`.

| # | Decision | Status |
|---|---|---|
| 0001 | Modular monolith backend in Python (FastAPI), reusing the domain package | accepted |
| 0002 | PostgreSQL we control, relational schema, Alembic migrations, SQLAlchemy Core | accepted |
| 0003 | Strangler migration off Supabase and Streamlit; no new vendor-specific code | accepted |
| 0004 | Own authentication and sessions; Google as an OIDC identity provider | accepted |
| 0005 | AI behind our own gateway and provider interface | accepted |
| 0006 | Rule for adding any external dependency | accepted |
| 0007 | Frontend: strict TypeScript, React + Vite, static, separate admin app | accepted |
