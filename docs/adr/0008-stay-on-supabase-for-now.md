# 0008 — Stay on Supabase for now; pause the move to our own backend

**Context.** ADR 0003 planned a step-by-step move off Supabase. Step M1 (our
backend, schema and importer) and part of M2 (ApiStore) were built. The app
now keeps three stores in step: the local file store, Supabase, and
ApiStore. Every change to what is stored touches all three, while the app
still has few learners and Supabase meets its needs. (Audit, P2-5.)

**Decision.** The app stays on Supabase. The move to our own backend is
paused, not dropped: `backend/` and ApiStore stay as they are and keep
passing their tests, but get no new features. New stored data (a new table
or column) goes to the file store and Supabase only; ApiStore answers that
it isn't available there yet (as it does for `content_reports`).

**Consequences.** A change to stored data touches two stores, not three.
ADR 0003's rule still holds for new code (keep Supabase-specific features
inside `storage.py` and `supabase/*.sql`), so the move can resume later.
Revisit when one of these is true: Supabase's limits or price no longer fit,
the app needs our own sign-in (ADR 0004), or many more learners are invited.
