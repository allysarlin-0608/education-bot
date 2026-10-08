# GNOSIS — architecture assessment and migration architecture

Status: **proposal, no code changed**. Written 2026-10-08 on branch `dev`
after Phases 1–3. It answers: what exists, what depends on third parties,
what stays, what is refactored, what is redesigned, what the target is, and
the order in which to get there without a rewrite.

Companion documents: `ARCHITECTURE.md` (the system as it is),
`docs/ENGINEERING_REVIEW.md` (the October hardening pass).

---

## 1. Summary

GNOSIS today is a **Python monolith rendered by Streamlit**, with
**Supabase** as database, REST layer, row-level security and identity
provider, and **Groq** as the only model provider. Hosting is Streamlit
Community Cloud.

The most valuable part of the codebase is already independent: about
**30 pure domain modules** (`coach/*`: curriculum, quiz, review, mastery,
streaks, habit, practice, paths, metrics…) with no UI, no database and no
network code, covered by ~685 tests and enforced by `tests/test_layers.py`.
They are the core that the new backend is built around: **reused, not
rewritten**.

What is not ours:

| Concern | Today | Owned? |
|---|---|---|
| Frontend | Streamlit server-rendered widgets + 2,200 lines of CSS that override Streamlit's internals | No (framework-bound, not portable, no TypeScript, no API) |
| API | None: pages call domain functions in-process | Missing |
| Backend runtime | Streamlit script reruns; Starlette routes added to Streamlit's server for sign-in | Partly |
| Database | Supabase Postgres, reached through PostgREST with the user's JWT | Data yes (Postgres, exportable); access path no |
| Authorization | Postgres row-level security + `security definer` functions in Supabase | Logic in SQL, coupled to Supabase's `auth.uid()` |
| Identity | Supabase Auth (GoTrue): email/password, Google OAuth, tokens, mail links | No |
| AI | `coach/llm.py` wraps Groq; prompts, orchestration and pacing spread over 5 modules and 2 pages | Partly |
| Knowledge | Syllabus text files + one large system prompt; lessons generated, not retrieved | Minimal |
| Hosting / domain | Streamlit Cloud, `*.streamlit.app` | No |

**Recommendation.** Migrate to a **modular monolith** we own:

- a Python backend (FastAPI) that imports the existing domain modules;
- our own PostgreSQL schema with migrations;
- our own sessions and auth, with Google as an OIDC provider;
- an AI service with a provider interface;
- a TypeScript frontend and a separate admin app;
- Docker images behind a reverse proxy on any host, under our own domain.

Do it as a **strangler migration**: the backend comes first, behind the
existing app (Streamlit talks to it through the storage interface it
already has), then auth, then AI, then the new frontend page by page. At
no point is there a big-bang rewrite or a frozen product.

Not now: microservices, Kubernetes, self-hosted models, GPU, a
knowledge graph. Phase 4–5 items stay on paper, with boundaries drawn
so they can be added later.

---

## 2. What exists (inventory)

### 2.1 Code (≈15,900 lines of app code)

| Layer | Modules | Notes | Verdict |
|---|---|---|---|
| Domain (pure) | `core` (partly), `catalog`, `curriculum`, `course`, `quiz`, `review`, `mastery`, `practice`, `streaks`, `habit`, `steps`, `history`, `search`, `books`, `reading` (partly), `paths`, `plans`, `placement`, `settings`, `prefs`, `metrics`, `clock`, `tokens` | Pure functions over a "log" dict; tested; layering enforced by tests | **Keep**: becomes `gnosis/domain` |
| AI | `llm` (Groq client, retries, pacing, JSON parsing), `quizgen`, `quota`, `prompts/`, `system_prompt.md`, prompt text inside `quiz`, `practice`, `paths`, `reading`, `core` | One client module (good), but prompts, model limits and orchestration are spread over the codebase; two pages orchestrate calls themselves (`views/daily.py`, `views/practice.py`) | **Refactor** into an AI service |
| Data | `storage.py`: `FileStore` and `SupabaseStore` implement the same ~25 operations | A real seam already exists; the operations are shaped around whole "entries" with JSON blobs | **Refactor**: same contract, new implementation (`ApiStore`, then repositories) |
| Auth | `supa_auth.py` (GoTrue HTTP client), `auth.py` (pages + gate), `session_cookie.py`, `routes.py` (Starlette routes on Streamlit's server) | Well tested, but entirely built on Supabase tokens | **Redesign** |
| UI | `views/*` (13 pages), `ui.py`, `style.py`, `motion.py`, `glass.py`, `place.py`, `topnav.py`, `sidebar.py`, `lesson_view.py`, `exercise.py`, `goalmaker.py`… | Pages still hold flow logic (start lesson, run quiz, grade, explain); CSS depends on Streamlit's DOM (`st-key-*`, `data-testid`) | **Replace** in time (TypeScript); the flow logic moves to backend services first |
| Schema | `supabase/*.sql` (15 files, applied by hand) | Tables + RLS + RPCs; no migration tool, no version table | **Redesign** as migrations |
| Tests | ~685 unit/page tests, ~235 Playwright tests with fake Supabase and fake Groq, inventory check | Strong safety net; the fakes document the contracts we depend on | **Keep**; domain tests move as-is |

### 2.2 Data model today

- `learning_entries`: one row per (user, date, subject). `lessons` is a
  **JSON array** of slots, and each slot holds:
  - the generated lesson text and the chat
  - the latest quiz (questions, answers, marks)
  - review cards
  - mastery evidence (`ev`), the practice bank, and the explanation.
- `user_settings`, `learning_paths` (goal as JSON), `reading_books` (JSON),
  `learner_prefs` (JSON), `usage_events` and `learning_signals` (counts),
  `ai_usage`, `users`, `allowed_users`, `app_admins`.

Problems with this model:
- **Learning data lives inside JSON blobs.** No index, constraint or
  foreign key covers a single quiz answer, review or piece of evidence.
  Analytics, admin views and retrieval would all have to unpack blobs.
- **History is overwritten.** Only the latest quiz attempt is kept, so the
  record of what happened is partly lost.
- **Identity is Supabase's.** `user_id` is Supabase's `auth.users.id`.

On the plus side, everything is Postgres and is already exported as JSON by
"Download my data", so there is no data trapped anywhere.

---

## 3. Third-party dependencies, assessed (Section 19 questions)

| Dependency | Why used | Essential? | Replaceable? | Migration difficulty | Owns our data? | Lock-in | Export | Alternative | Decision |
|---|---|---|---|---|---|---|---|---|---|
| **Supabase Postgres** | Database | The *Postgres* is; the vendor isn't | Yes | Low: standard `pg_dump` | Hosts it | Low | Full | Any Postgres (managed or self-hosted) | **Replace the host** (move data to our Postgres) |
| **Supabase PostgREST + RLS** | DB access from the app with the user's token | No | Yes | Medium: rules live in SQL policies | No | **High**: authorization lives in vendor-specific policies (`auth.uid()`) | n/a | Our API + service-layer authorization | **Replace** |
| **Supabase Auth (GoTrue)** | Sign-up, passwords, Google, mail links, tokens | No | Yes | Medium: password hashes are bcrypt in `auth.users` and can be exported and verified by us, so **no forced password resets** | Holds identities | **High** | Yes, via SQL | Own auth service + Google OIDC | **Replace** |
| **Streamlit** (framework) | UI + server | No | Yes | High: the UI must be rebuilt | No | Medium: CSS hacks on its internals; no API | n/a | TypeScript SPA + our API | **Replace gradually** |
| **Streamlit Community Cloud** | Hosting | No | Yes | Low | Holds secrets | Medium: domain `*.streamlit.app` | n/a | Docker on any VM | **Replace** |
| **Groq** | Model inference (`gpt-oss-120b`) | A model is essential, this provider isn't | Yes | Low once behind an interface (the API is OpenAI-compatible) | Sees prompts | Low–medium: rate limits are tuned into `tokens.py` | n/a | Any OpenAI-compatible endpoint, incl. self-hosted vLLM/Ollama | **Keep for now, behind the AI provider interface** |
| `requests`, `starlette`, `tzdata` | HTTP, routes, time zones | Yes | Yes | Trivial | No | None | n/a | — | Keep |
| Google Fonts (CSS) | Typefaces | No | Yes | Trivial (self-host the files) | No | None | n/a | Self-hosted fonts | Self-host in the new frontend |
| GitHub + Actions | Code, CI | Yes for now | Yes | Low (git) | Holds code | Low | Full (git) | Any git host / CI | Keep |

**Rule for new dependencies** (to add to `ARCHITECTURE.md`): a new external
service is allowed only:
- behind one of our interfaces;
- with a written note answering the eight questions;
- with an export path for any data it holds.

Convenience alone is not a reason.

---

## 4. Keep, refactor, redesign

**Keep (move, don't rewrite)**
- The domain modules and their tests (`curriculum`, `quiz`, `review`,
  `mastery`, `practice`, `streaks`, `habit`, `paths`, `metrics`…), and the
  learning rules they encode: spacing, mastery, streaks, rest days.
- The prompt content and the quiz verification pipeline (write → check →
  rewrite), as AI "use cases".
- The test fakes' scenarios, which become API contract tests.
- PostgreSQL as the database engine.

**Refactor**
- `storage.py` contract → a data-access layer of **repositories** (one per
  aggregate: users, lessons, attempts, cards, evidence, goals…), and an
  `ApiStore` so the current app can run against our backend unchanged during
  the migration.
- Flow logic in `views/daily.py` and `views/practice.py` (start lesson,
  write quiz, grade, explain, practice check) → **application services**
  in the backend. Pages then call one endpoint per action.
- `llm.py`, `quizgen.py`, `quota.py`, `tokens.py` and the prompts →
  **AI service**:
  - provider interface;
  - prompt registry, with versions;
  - per-use-case orchestrators;
  - limits per provider rather than global constants.

**Redesign**
- Database schema: relational, not blobs (section 6).
- Authentication and sessions (section 7) and authorization (section 8).
- Frontend: TypeScript learner app + separate admin app (section 5).
- Infrastructure, environments, domain, CI/CD (section 11).

---

## 5. Target architecture

```
                  yourdomain.com      admin.yourdomain.com     api.yourdomain.com
                        │                     │                        │
                  ┌─────┴─────────────────────┴────────────────────────┴─────┐
                  │  Reverse proxy (Caddy): TLS, HTTP→HTTPS, headers, routing │
                  └─────┬─────────────────────┬────────────────────────┬─────┘
             web (static TS app)     admin (static TS app)      api (FastAPI)
                                                                       │
     ┌───────────────────────── backend: modular monolith ─────────────┴────────┐
     │ api/        HTTP routes, request/response schemas (OpenAPI), CSRF,       │
     │             rate limits                                                  │
     │ auth/       identities (Google OIDC, email+password), sessions, mail     │
     │             links                                                        │
     │ authz/      roles, permissions, policy checks (server-side, every        │
     │             action)                                                      │
     │ services/   application services: lessons, quizzes, review, practice,    │
     │             goals, reading, admin                                        │
     │ domain/     today's pure modules (curriculum, quiz, mastery, …):         │
     │             unchanged rules                                              │
     │ data/       repositories over PostgreSQL (SQLAlchemy Core),              │
     │             transactions, Alembic                                        │
     │ ai/         gateway → orchestrators → context builder → providers        │
     │             (adapters)                                                   │
     │             memory · knowledge · retrieval · tools · AI interaction log  │
     │ jobs/       background worker (reminder mail, embeddings, exports,       │
     │             cleanups)                                                    │
     │ infra/      config, secrets, logging, metrics, health, mail, object      │
     │             storage                                                      │
     └──────────────────────────────────────────────────────────────────────────┘
                     │                         │                         │
                PostgreSQL               model providers           object storage
       (+ pgvector, full-text)    (Groq now; any OpenAI-compatible;  (backups, exports;
                                   self-hosted later)                 S3-compatible)
```

Choices and why:

| Choice | Why | Lock-in check |
|---|---|---|
| **Python + FastAPI** for the backend | Reuses all domain code and tests as-is; typed (Pydantic); generates OpenAPI for the frontends | Open source; runs anywhere |
| **Modular monolith**, not microservices | One deployable, clear internal boundaries (import rules enforced by tests, as today); split a module out only when scale demands it | — |
| **PostgreSQL 16** + **SQLAlchemy Core** + **Alembic** | Mature; the data is already Postgres; plain SQL-level access keeps the database replaceable | Any Postgres host |
| **pgvector + Postgres full-text** for retrieval at first | Hybrid search without a new vendor; behind a `VectorIndex`/`KeywordIndex` interface so a dedicated engine can replace it | None |
| **TypeScript (strict) + React + Vite** for web and admin, TanStack Router/Query, a typed API client generated from OpenAPI | Static files we own, deployable on any web server, no server runtime or vendor platform required | Open source; no hosting tie |
| **Caddy** reverse proxy | Automatic HTTPS for any domain, simple config, host-agnostic | Swappable for nginx |
| **Docker images + Compose** per environment | Same images in dev, staging, production; any VM or later Kubernetes | Portable |
| Background jobs: a small worker with a **Postgres-backed queue** (e.g. `procrastinate`) | No Redis/broker to run at first; same database | Swappable |
| Mail behind a `Mailer` interface (SMTP) | Any provider or our own server | Swappable |

---

## 6. Data model (target)

Relational core. JSON is kept only where content truly is a document, such
as the text of a generated lesson or a question's options.

- **Identity and access:**
  - `users` (internal UUID, status, created/deleted at)
  - `user_profiles`
  - `identities` (provider, subject, user_id; unique per provider+subject)
  - `credentials` (password hash; argon2 for new, bcrypt accepted for imported)
  - `sessions` (opaque id hash, user, device, expiry, revoked)
  - `roles`, `permissions`, `role_permissions`, `user_roles`
  - `invites`
- **Catalog / content:**
  - `subjects` (built-in and goal-based)
  - `units`, `lessons_catalog` (syllabus positions)
  - `goals` (her path, versioned)
  - `lesson_contents` (generated lesson text, model, prompt version, created at)
  - `knowledge_documents`, `knowledge_chunks` (+ embedding, metadata)
- **Learning activity:**
  - `study_days`, `lesson_progress` (per user × lesson: started, passed, carried)
  - `quiz_attempts`, `quiz_questions`, `quiz_answers` (every attempt kept, not only the last)
  - `review_cards`, `card_reviews`
  - `mastery_evidence` (today's `ev`)
  - `explanations`, `practice_items`, `practice_sets`
  - `reading_books`, `reading_days`
  - `preferences`
- **AI:**
  - `ai_interactions` (use case, prompt version, provider, model, tokens, latency, outcome, linked object)
  - `conversations`, `messages` (tutor chat)
  - `user_memories` (curated long-term facts, with source and expiry)
- **Operations:**
  - `audit_log` (who, what, target, when, from where; append-only)
  - `usage_counters`, `learning_signals`
  - `jobs`
  - `schema_version` (Alembic)

Rules:
- every table has a primary key, `created_at`, and foreign keys with
  explicit `ON DELETE`;
- indexes are added for every lookup the services make;
- each state change happens in one transaction;
- no business rule lives in triggers;
- **retention**: AI interaction text kept N days (configurable), counts kept
  indefinitely; account deletion removes personal data in one transaction
  and leaves anonymous counts;
- **backups**: nightly full dump, continuous WAL archiving to S3-compatible
  storage, 30-day retention, and a restore rehearsed every quarter.

**Migration of existing data:** a one-off importer reads the Supabase
tables, unpacks each JSON slot into the relational tables, and checks the
counts and totals both ways (lessons passed, cards, evidence). The domain
functions already parse every historical shape (`parse_slots`, `parse_saved`,
`legacy`), which the importer reuses. A dry run against a copy is required
before cut-over.

---

## 7. Authentication (target)

```
Browser → api.yourdomain.com/auth/google/start  (state + PKCE + nonce)
       → Google (OIDC)
       → /auth/google/callback: verify id_token (iss, aud, exp, nonce, signature via Google's JWKS)
       → find or create our user via identities(provider='google', subject=sub)
       → create our session: random 256-bit id, stored hashed, HttpOnly + Secure + SameSite=Lax cookie
       → app
```

- Our `users.id` is the identity. A provider is just a row in `identities`,
  so Apple, Microsoft or SSO are each one more adapter, with no redesign.
- **Email + password stays** for current users. Their bcrypt hashes are
  imported from Supabase's `auth.users.encrypted_password` and verified as
  is, then rehashed to argon2 at the next sign-in. Nobody has to reset a
  password.
- Sessions:
  - server-side and revocable (sign out everywhere, admin suspend);
  - sliding expiry;
  - the id is rotated at sign-in and when privilege changes.
- Brute force: per-account and per-IP limits, a delay after failures, and
  lock-out notices.
- Mail links (confirm, reset) are single-use tokens, stored hashed with a
  short expiry.
- CSRF:
  - SameSite cookies, plus a double-submit token on state-changing requests;
  - CORS limited to our own origins;
  - the admin site uses a separate cookie scope.

## 8. Authorization (target)

- **Role-based**, with permissions as the unit of checking. Roles are
  User, Staff, Editor, Moderator, Admin, Super Admin and custom roles; they
  are only bundles of permissions such as `users.read`, `users.suspend`,
  `content.edit`, `ai.config.edit` or `audit.read`.
- **Ownership checks** for learner data live in the service layer: every
  query is scoped to the session's user, and repositories require a user
  id.
- Enforced on the server for every endpoint through one dependency, so no
  endpoint is open by default; a test fails if a route has no declared
  permission.
- Every admin action and security event is written to `audit_log`.
- Super-admin actions require a recent re-authentication.

## 9. Admin system (target)

- A separate app on `admin.yourdomain.com`: separate build, cookie scope
  and content-security policy. It talks to the same API with permission
  checks.
- First version, built from what exists today:
  - users (search, profile, status, roles, sessions, usage);
  - invites (today's `allowed_users`);
  - learning overview (today's Insights);
  - audit log.
- Later: content (courses, lessons, knowledge documents), AI configuration
  (prompts, models, limits per use case), system configuration and data
  exports.

---

## 10. AI system (target)

```
service (e.g. lessons) → ai.gateway.run(use_case, inputs, user)
  → policy: quota, permissions, safety rules
  → context builder: system instructions (prompt registry, versioned)
                     + user context (memory layer)
                     + knowledge (retrieval layer)
                     + tools allowed for this use case
  → model router: picks provider + model per use case (config, not code)
  → provider adapter: groq | openai_compatible (vLLM, Ollama, …) | others
  → output validation (schemas; the existing quiz checker becomes a validator step)
  → ai_interactions log (prompt version, model, tokens, latency, verdict)
```

- **Model interface:** `generate(messages, params) -> Completion`,
  `stream(...)`, `generate_json(schema, ...)`, plus `capabilities()`
  (context size, tools, JSON mode) and `limits()` (rate limits per
  provider). Groq's 8,000 tokens a minute moves from `tokens.py` into the
  Groq adapter's limits.
- **Use cases**, written as code and owned by us: `lesson`, `quiz_write`,
  `quiz_check`, `quiz_grade`, `explain_feedback`, `tutor_answer`,
  `path_design`, `reading_judge`, `practice_write`. Each declares its
  prompt version, output schema, allowed tools and default model.
- **Memory** has layers and is retrieved deliberately, never as a whole
  history dump:
  1. the turns of the current conversation (bounded);
  2. the learning state, computed from the database: mastery, weak ideas,
     recent lessons (already exists as `mastery` and `practice`);
  3. preferences;
  4. curated long-term memories (`user_memories`), written by explicit rules
     or tools and reviewable by the user and admins.
- **Knowledge and retrieval:**
  - documents → chunks → embeddings, with metadata (subject, lesson,
    source, licence);
  - hybrid search: Postgres full-text + pgvector, then reranking;
  - every part sits behind an interface: `Embedder`, `VectorIndex`,
    `KeywordIndex`, `Reranker`.
  - The first sources are the syllabus, our own lessons once checked, and
    curated documents. The schema keeps entity and relation tables open
    for a knowledge graph later.
- **Tools:** a registry of typed functions, each with:
  - a permission scope;
  - read-only or write;
  - rate limits;
  - audit logging.

  The first tools are read-only (search knowledge, the learner's history,
  her progress, recommend a lesson). The model never gets SQL, files or a
  shell.
- **Model independence path:** Groq → any OpenAI-compatible endpoint →
  a self-hosted open model (vLLM) on rented GPUs → a fine-tuned model
  trained on our own `ai_interactions` and quiz data (with consent) →
  our own infrastructure. Only adapters and configuration change, never
  the services.

---

## 11. Infrastructure, environments, domain

- **Environments**:
  - `dev` runs locally with Docker Compose and a seeded database.
  - `staging` (`staging.yourdomain.com`, `api.staging…`) and `production`
    (`yourdomain.com`, `admin.`, `api.`) run the same images with
    different configuration.
- **Domain:**
  - registered at any registrar; DNS records point to the reverse proxy;
  - TLS is issued automatically by Caddy (Let's Encrypt), so nothing ties
    the domain to a hosting provider;
  - the app reads its public URLs from configuration, never from
    hard-coded hosts.
- **Hosting:** start with one or two plain VMs from any provider (app and
  database), or managed Postgres if we'd rather not run it, since the data
  stays standard Postgres. Moving providers means pointing DNS elsewhere
  and restoring a backup.
- **Secrets:**
  - kept as environment variables, injected from the CI secret store or a
    file outside the repo;
  - never sent to the frontend, never logged;
  - rotation documented.
- **CI/CD** (GitHub Actions; the workflow file is portable):
  1. lint, type-check and test;
  2. build images;
  3. run migrations on staging and deploy;
  4. smoke tests, then manual promotion to production.
- **Observability:**
  - structured JSON logs with request and session ids (we already tag
    sessions);
  - `/health` and `/ready` endpoints;
  - OpenTelemetry metrics and traces, sent to Prometheus + Grafana, which
    we can self-host;
  - error tracking with GlitchTip (self-hosted, Sentry-compatible);
  - AI usage dashboards built from `ai_interactions`.
- **Disaster recovery:**
  - target data loss at most 15 minutes, restore in at most 4 hours;
  - the restore is rehearsed;
  - the runbook lives in `docs/ops/`.

---

## 12. Security checklist (target)

| Area | How |
|---|---|
| Sessions/cookies | Opaque ids, hashed at rest, HttpOnly, Secure, SameSite, rotation, revocation |
| CSRF | SameSite + double-submit token; origin checks |
| XSS | React escaping by default; no raw HTML from the model; Markdown rendered with a sanitiser; strict content-security policy |
| SQL injection | Parameterised queries only (SQLAlchemy Core); no string SQL |
| Rate limiting | Per IP, per user and per route; AI quota per user per day (exists today) |
| Brute force | Throttling and lock-out on sign-in and on mail links |
| Authorization bypass | Deny by default; permission declared on every route; tests that try every route as every role |
| Secrets | Server-only, from the environment; automated secret scanning in CI |
| Data exposure | Response schemas whitelist fields; admin APIs separate; personal data minimised in logs |
| Admin | Separate origin, recent re-authentication for dangerous actions, everything audited |
| AI | Prompt-injection rules in prompts (started in Phase 3); tools scoped; outputs validated against schemas |

---

## 13. Migration plan (strangler, each step shippable)

The learner app keeps working at every step. Each step ends with tests
green and a rollback path.

| Step | What | Result | Rollback |
|---|---|---|---|
| **M0** (days) | Architecture decisions recorded (`docs/adr/`). Rule: no new Supabase-specific code. Repository restructured as a monorepo: `backend/`, `web/`, `admin/`, `infra/`; current app kept in place | Direction fixed | n/a |
| **M1** (2–3 weeks) | Backend skeleton:<br>• FastAPI, config, logging, health<br>• PostgreSQL schema + Alembic<br>• repositories<br>• domain modules imported<br>• Docker Compose<br>• CI<br><br>Data importer (Supabase → our schema) with verification | Our database, filled with a copy of real data | Nothing switched yet |
| **M2** (2–3 weeks) | Learner API (lessons, quiz, review, practice, goals, prefs, reading, export/delete): the flow logic moves from the pages into services. `ApiStore` + action endpoints, so the **current Streamlit app uses our backend** on staging | Supabase no longer in the data path on staging | Switch the store back |
| **M3** (2 weeks) | Own auth:<br>• Google OIDC<br>• email+password with imported hashes<br>• sessions, roles<br>• audit log, rate limits<br><br>Cut-over of production data and sign-in on one planned evening | Supabase removed from production; Streamlit app runs on our backend | Keep the Supabase project read-only for 30 days |
| **M4** (2 weeks) | AI service:<br>• provider interface (Groq adapter + OpenAI-compatible adapter)<br>• prompt registry<br>• use cases<br>• `ai_interactions` log<br>• model routing by configuration | One place for all model calls; provider swappable | Configuration |
| **M5** (6–10 weeks) | TypeScript web app, page by page (Today, quiz, review, practice, skill map, progress, settings), then cut-over at `yourdomain.com`. Admin app, first version. Streamlit retired | Frontend and admin owned | Old app kept on a subdomain until confident |
| **M6** (later) | Knowledge base + hybrid retrieval, memory layers, read-only tools | AI grounded in our knowledge | Feature flags |
| **M7** (when justified) | Self-hosted open model behind the same adapter; evaluation set built from logged, checked interactions | Model independence | Route back to the API provider |

The timings assume one full-time engineer working with an AI coding
assistant; they are estimates, not commitments.

---

## 14. Decisions needed (with recommendations)

1. **Backend language: Python (FastAPI).** Recommended: it reuses ~30
   tested domain modules. The alternative, TypeScript end to end, means
   rewriting the domain.
2. **Frontend: React + TypeScript + Vite (static).** Recommended: it is
   the most portable and has the widest hiring pool. Next.js is fine too,
   if run on our own Node server and not tied to a hosting platform.
3. **Hosting for staging/production:** a plain VM provider of your choice
   (EU or Asia region), with standard Postgres on it or a managed Postgres.
   This is needed by M1 for staging.
4. **Domain name** to register, needed by M3 for Google sign-in, since
   Google's OAuth redirect must be our domain.
5. **Order:** M1→M3 first (data and identity ownership), before new product
   features? Recommended **yes**: every feature built on Supabase now is
   work to move later.
6. **Personal app:** keep it as is on Streamlit + files until M5, then move
   it to its own account on the new platform? Recommended yes.

---

## 15. What not to do now

- No microservices, Kubernetes, service mesh or event bus. One backend,
  one worker.
- No vector database product, no knowledge graph engine, no GPU servers.
- No self-trained models. Collect clean, consented interaction data and
  evaluation sets first; that is the asset that makes Phase 4–5 possible.
- No rewrite of working learning rules. Move them, keep their tests.
