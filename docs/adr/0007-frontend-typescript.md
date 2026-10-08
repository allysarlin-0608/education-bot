# 0007 — Frontend: strict TypeScript, React + Vite, static; separate admin

**Decision.** The learner app (`web/`) and the admin app (`admin/`) are
static TypeScript (strict) builds with React + Vite, served by our own web
server, calling the API through a client generated from its OpenAPI
contract. No business rule lives only in the frontend. The admin app has
its own origin (`admin.` subdomain), cookie scope and security policy.

**Consequences.** No hosting platform is required; the UI is replaced
page by page in step M5 while Streamlit keeps serving until cut-over.
