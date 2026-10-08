# 0005 — AI behind our own gateway

**Decision.** All model calls go through `gnosis/ai`: use cases (lesson,
quiz write/check/grade, explain, tutor, path design, reading, practice)
→ context builder (versioned prompts, user context from our data, retrieved
knowledge, allowed tools) → model router (configuration) → provider adapter
(Groq now; any OpenAI-compatible endpoint, including self-hosted, next) →
output validation → interaction log. Nothing else imports a provider SDK.

**Consequences.** Changing provider or model is configuration; usage,
cost and quality are measured per use case; self-hosted models fit later
without touching services.
