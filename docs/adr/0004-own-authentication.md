# 0004 — Own authentication; Google as an identity provider

**Decision.** Our `users.id` is the identity. Sign-in methods are rows in
`identities` (provider, subject): Google via OpenID Connect (authorization
code + PKCE + nonce, ID token verified against Google's keys), and
email + password (argon2id; bcrypt hashes imported from Supabase verified
as they are and rehashed on the next sign-in). Sessions are server-side:
an opaque random id in an HttpOnly, Secure, SameSite=Lax cookie, stored
hashed, revocable, rotated on sign-in. Authorization is role-based with
permissions, checked on the server for every route.

**Consequences.** No one resets a password at the switch; adding another
provider is one adapter; an admin can suspend or sign out anyone at once.
