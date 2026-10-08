# 0003 — Strangler migration; no new vendor-specific code

**Decision.** Move off Supabase and Streamlit in shippable steps (M1–M5 in
the assessment): our database and importer; the current app on our API
through its existing storage interface; our auth; the AI gateway; the
TypeScript frontends. From now on no new code may call Supabase-specific
features (PostgREST queries, RLS policies, `auth.uid()`, RPCs) except to
keep the current app running until its step replaces them.

**Consequences.** The product never stops; every step has a rollback (the
old path stays available until the new one has run in production).
