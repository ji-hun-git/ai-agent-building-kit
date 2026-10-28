# 06 · Identity and authorization

> Snapshot verified 2026-10-27. Items tagged **[volatile]** change often — re-check them with the freshness protocol in SKILL.md before relying on them.

## Default

Give every agent its own workload identity, and let it act for a person only through short-lived, audience-bound delegated tokens that name both the user (`sub`) and the agent (`client_id`, or `act` after a token exchange). Remote MCP servers follow the current MCP authorization spec, revision 2026-07-28 **[volatile]**: OAuth 2.1 with PKCE, RFC 9728 protected resource metadata, the RFC 8707 `resource` parameter on every authorization and token request, audience checks on every call, RFC 9207 `iss` checks, and pre-registered or Client ID Metadata Document (CIMD) clients instead of Dynamic Client Registration (DCR). In a workforce deployment, use Enterprise-Managed Authorization so the corporate IdP issues ID-JAGs and IT policy, not per-server consent screens, decides which users and clients reach which servers. Credentials live in the harness or tool layer and never enter model context. Every retrieved document and every tool call is authorized by code outside the model against user permission ∩ agent grant ∩ task policy, and high-impact actions are approved through the authorization server (CIBA), not through a button the agent itself renders.

## Decide

- If the agent acts for a signed-in user (assistant, copilot, IDE agent) → authorization code + PKCE with the agent as `client_id` and the user as `sub`; use delegation, not impersonation, when exchanging tokens, because downstream policy and incident response must tell the agent's actions apart from the user's own (RFC 8693 `act`).
- If no user is present and the agent touches only shared or agent-owned resources → the agent's own identity (SPIFFE SVID, IdP agent identity, or the MCP OAuth Client Credentials extension) with rights granted directly to it and a named human sponsor, because borrowing a user's token makes every run an unaudited impersonation.
- If an MCP client and authorization server (AS) have a prior relationship → pre-register; if not → CIMD (an HTTPS URL as `client_id`); use DCR only for a legacy AS, because DCR is deprecated in MCP 2026-07-28 **[volatile]** and anonymous registration fed the confused-deputy attack.
- If the deployment is workforce users behind a corporate IdP → Enterprise-Managed Authorization: SSO, RFC 8693 token exchange at the IdP for an ID-JAG, then an RFC 7523 JWT-bearer grant at the MCP server's AS, because admins get one place to grant and revoke access. Confirm IdP and SDK support first **[volatile]**.
- If an MCP server or tool must call a downstream API → it obtains its own token for that API (token exchange or on-behalf-of with `audience`/`resource` narrowed to that API) and never forwards the token it received, because the spec forbids passthrough and forwarded tokens defeat audit, rate limits and audience binding.
- If a call chain spans several services inside one trust domain → propagate a Transaction Token (minutes-long, scope never wider than the original) instead of the access token **[volatile]**, because each hop then sees user and agent context without holding a reusable credential.
- If a request crosses into another organization's trust domain → identity and authorization chaining (JWT grant obtained by intra-domain token exchange) **[volatile]**, because the target domain should only accept tokens its own AS minted.
- If a client connects to many MCP servers or authorization servers (agent hub, IDE) → record the expected issuer per request, validate `iss` before redeeming a code, and key stored credentials by issuer, because mix-up attacks send one AS's code to another, and PKCE alone does not stop them.
- If answers draw on retrieved documents → authorize every candidate with the user's identity before it reaches the model: post-filter with OpenFGA `BatchCheck` (over-fetch about 2–3×) when users can see most of the corpus, pre-filter with `ListObjects` as a vector-store metadata filter when they can see little, because index-level ACLs drift and post-filtering can return fewer than k.
- If tool calls depend on identity, arguments or session history (amount caps, allowed recipients, "approval before transfer", call counts) → enforce them in a policy engine at the tool gateway (Cedar: default deny, `forbid` overrides `permit`), because a prompt can be argued out of a rule and a policy engine cannot.
- If an operation needs more than the current scopes → step-up: the server returns 403 `insufficient_scope` with every scope the operation needs; the client re-authorizes with the union of old and new scopes, with a retry cap, because up-front omnibus scopes widen the blast radius of a stolen token.
- If an action is irreversible, high-value or unusual for this user → the AS decides whether approval is needed and obtains it out of band (CIBA with a `binding_message` naming the action), because injected content can spoof or fatigue an in-app confirmation and local UI confirmation alone is not authorization.

## Who is calling?

| Caller | Typical case | Identity in the token | How it gets the token | High-impact approval | Never |
| --- | --- | --- | --- | --- | --- |
| End user, delegated | Chat assistant reading the user's mail, files or tickets | `sub` = user, `client_id` = agent (`act` = agent after exchange), `aud` = one resource, minimal scopes, minutes-long | Auth code + PKCE (or ID-JAG via the IdP); token exchange per downstream hop | CIBA or step-up to the user; policy engine decides when | Impersonation token that hides the agent; one token for many resources |
| Agent's own identity | Triage bot on a shared queue; agent reading its own config or a team-wide index | `sub` = agent workload ID (SPIFFE ID or IdP agent identity); sponsor recorded | Client credentials, JWT-SVID or IdP-issued agent token; credentials rotated automatically | Policy engine; sponsor or admin approves new grants | Static API key; rights copied from a human account |
| Background job | Scheduled or event-driven run with no user present | User data: agent identity plus a stored, scoped, revocable delegation exchanged for a narrow per-run token. No user data: agent identity only | Token vault in the harness holds the grant; run-time exchange per resource | CIBA push to the user who set it up; otherwise hold and queue | Long-lived user refresh token in the agent's config or memory |

## Build checklist

- [ ] Fill a caller row (table above), resource URI, minimal scopes and the elevation approver for every tool and data source in the agent spec.
- [ ] MCP Python SDK servers: run a patched version (≥ 2.2.0 or ≥ 1.30.0 **[volatile]**) and set `validate_token_resource=True` in `AuthSettings` with `resource_server_url` set to the audience your authorization server puts in tokens. The check is off unless you set it; without it the server accepts tokens issued for other resource servers ([GHSA-w4fh-qvv9-3v23](https://github.com/modelcontextprotocol/python-sdk/security/advisories/GHSA-w4fh-qvv9-3v23), verified 2026-10-27). Check the equivalent setting in any other MCP SDK you use.
- [ ] For each third-party MCP server, probe its live discovery documents (protected resource metadata, authorization server metadata) and record the registration methods it accepts and the scopes it advertises; then confirm from a real token request which scopes your SDK actually asks for, because client libraries may request every advertised scope when the server does not name one.
- [ ] Give each agent exactly one workload identifier (SPIFFE ID or IdP agent identity) with an owner team and a named human sponsor; delete the identity and its grants when the agent is retired.
- [ ] MCP server: serve RFC 9728 metadata at `/.well-known/oauth-protected-resource`; answer unauthenticated calls with 401 and `WWW-Authenticate: Bearer resource_metadata="…", scope="…"`.
- [ ] MCP server: validate signature, expiry, issuer and `aud` = its own canonical URI on every request; add a test that a token minted for another resource gets 401.
- [ ] MCP server: list only baseline scopes in `scopes_supported`; return all scopes an operation needs in one 403 `insufficient_scope` challenge; resolve scope hierarchies server-side; ship no `*`, `all` or `full-access` scope.
- [ ] MCP client: send `resource` (canonical server URI, no trailing slash) on authorization and token requests; use PKCE S256; store the expected issuer with the code verifier; reject a mismatched `iss` by exact string comparison before redeeming the code.
- [ ] MCP client: register in the order pre-registered → CIMD → DCR (legacy only); host the CIMD document over HTTPS at a URL with a path, with `client_id` equal to that URL; key persisted credentials by AS issuer and re-register when the AS changes.
- [ ] MCP client: on step-up, request the union of previous and challenged scopes, cap retries, and cache denied elevations.
- [ ] MCP client and CIMD-fetching AS: require HTTPS and block private, loopback and link-local ranges (including cloud metadata endpoints) when fetching OAuth URLs, or route those fetches through an egress proxy; open authorization URLs without a shell and accept only `https` (plus loopback `http` in development).
- [ ] Downstream calls: exchange the inbound token for one scoped to the downstream API; add a test asserting the inbound token never leaves the server.
- [ ] Keep access tokens minutes-long; keep refresh tokens and agent keys in a vault the harness reads; inject credentials in the tool layer; grep prompts, tool results, memory and traces for token patterns in CI.
- [ ] Log user, agent, tool, resource, decision and policy version for every authorization decision, in tamper-evident storage.
- [ ] Retrieval: run `BatchCheck` or `ListObjects` with the requesting user's identity on every query; test with a user who lacks access to a strongly matching document and assert it never reaches the context.
- [ ] Tool gateway: deny by default; principal = user + agent, action = tool, resource = target, context = arguments + session history; log every decision.
- [ ] Approvals: route irreversible or external actions through AS-mediated approval (CIBA) that shows the action, target and data on the user's own device; the agent cannot approve itself.
- [ ] Revocation: subscribe to IdP change events (OpenID Shared Signals: CAEP/RISC) or keep TTLs short enough that disabling a user or agent stops its access within minutes; test it.
- [ ] Stateful tools: bind every server-minted handle (cart ID, workflow ID) to the user from the verified token; possession of a handle is never authentication.
- [ ] Enterprise-Managed Authorization: token-exchange `audience` = the MCP server's AS issuer; issued access token audience-restricted to the MCP server named in the ID-JAG `resource` claim.

## Avoid

- Static API keys or shared service accounts for agents → per-agent workload identity with short-lived, auto-rotated credentials (keys leak, never expire, and make agents indistinguishable in logs).
- Token passthrough → token exchange for a new audience-bound token (forbidden by the MCP spec; it breaks audit, rate limits and audience binding, and creates a confused deputy).
- Impersonation tokens that hide the agent → delegation with the agent in `client_id`/`act` (responders must know an agent acted, and policy may treat agents differently).
- Credentials in system prompts, model-filled tool arguments or memory → the harness injects them at call time (anything in context can be exfiltrated by injected instructions).
- Telling the model "only use documents the user may see" → filter before the context window (a prompt is advice; a permission check is enforcement).
- One ACL snapshot at index build time → per-query checks against the live permission graph (permissions change after indexing).
- Requesting every scope up front → minimal baseline plus step-up (a broad token turns one leak into lateral access).
- DCR for new clients → CIMD or pre-registration with an AS trust policy (DCR is deprecated, and open registration enabled consent-skipping attacks).
- A chat-window "Approve" button as the authorization decision → AS-decided approval on a separate channel (injected content can mimic prompts, and people approve by habit).
- A user's long-lived refresh token stored with a background agent → a scoped, revocable delegation in a vault, exchanged per run.
- Accepting a token because its signature verifies → also check issuer, audience, expiry and scope (a valid token for another resource is still the wrong token).

## Additions (verified 2026-10-27)

- List every trigger (chat, Slack, email, webhook, cron) with the identity it runs as and whether its payload is untrusted; event-triggered runs without a user need their own scoped identity, never a borrowed user token.
- Payments: signed mandates or shared payment tokens (AP2, Agentic Commerce Protocol **[volatile]**); the agent never holds card credentials.

## Verify before relying

| Fact **[volatile]** | Snapshot (2026-10-27) | Where to check (URL) |
| --- | --- | --- |
| Current MCP spec revision and auth rules | 2026-07-28: CIMD SHOULD, DCR deprecated, client MUST validate a present `iss`, credentials keyed by issuer | https://modelcontextprotocol.io/specification/2026-07-28/changelog |
| AS inclusion of `iss` | SHOULD; spec says a future revision is expected to make it MUST | https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization |
| MCP auth extensions | Enterprise-Managed Authorization and OAuth Client Credentials, both Stable at 2026-07-28 | https://github.com/modelcontextprotocol/ext-auth |
| ID-JAG draft | draft-ietf-oauth-identity-assertion-authz-grant-04 (2026-05-21), active OAuth WG draft, not an RFC | https://datatracker.ietf.org/doc/draft-ietf-oauth-identity-assertion-authz-grant/ |
| Identity chaining draft | -17 (2026-07-19), submitted to IESG, no RFC number yet | https://datatracker.ietf.org/doc/draft-ietf-oauth-identity-chaining/ |
| Transaction Tokens draft | -11 (2026-07-30), WG consensus, waiting for write-up | https://datatracker.ietf.org/doc/draft-ietf-oauth-transaction-tokens/ |
| CIMD draft | -02 (2026-07-06); the MCP spec still cites -00 | https://datatracker.ietf.org/doc/draft-ietf-oauth-client-id-metadata-document/ |
| IETF agent identity guidance | draft-ietf-wimse-aims-00 (2026-09-15), Informational, WIMSE WG; replaces draft-klrc-aiagent-auth | https://datatracker.ietf.org/doc/draft-ietf-wimse-aims/ |
| ID-JAG vendor support | Okta Agent SSO GA 2026-08-24; Auth0 early access (Jul/Aug 2026); Descope 2026-09-01; Anthropic MCP connectors GA 2026-08-24 (Okta only); MCP TS/Python/C# SDKs yes, Java no (vendor-authored summary) | https://workos.com/blog/cross-app-access-converged-in-eight-days |
| Microsoft Entra Agent ID | Available to all Entra customers; Conditional Access and other Entra security features for agents require Microsoft Agent 365 | https://learn.microsoft.com/en-us/entra/agent-id/identity-platform/what-is-agent-id |
| AWS AgentCore Policy | Cedar and Dogwood policies at AgentCore Gateway, temporal (session-aware) rules; GA status not confirmed here | https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy.html |
| OpenFGA `ListObjects` defaults | 3 s deadline, 1000 results max; tune for large corpora | https://openfga.dev/docs/interacting/relationship-queries |
| NIST NCCoE agent identity project | Comment summary 2026-09-29; DevSecOps demo first; no standard yet | https://www.nist.gov/news-events/news/2026/09/comments-software-and-agentic-ai-identity-concept-paper |

## Sources

- [Authorization (MCP 2026-07-28)](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization) — Model Context Protocol, 2026-07-28
- [Client Registration (MCP 2026-07-28)](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization/client-registration) — Model Context Protocol, 2026-07-28
- [Key Changes (MCP 2026-07-28)](https://modelcontextprotocol.io/specification/2026-07-28/changelog) — Model Context Protocol, 2026-07-28
- [Security Best Practices](https://modelcontextprotocol.io/specification/2026-07-28/basic/security_best_practices) — Model Context Protocol, 2026-07-28
- [MCP Authorization Extensions (ext-auth)](https://github.com/modelcontextprotocol/ext-auth) — Model Context Protocol on GitHub, accessed 2026-10-27
- [Enterprise-Managed Authorization 2026-07-28](https://raw.githubusercontent.com/modelcontextprotocol/ext-auth/main/specification/stable/enterprise-managed-authorization/2026-07-28/enterprise-managed-authorization.mdx) — Model Context Protocol, 2026-07-28
- [RFC 8693: OAuth 2.0 Token Exchange](https://www.rfc-editor.org/rfc/rfc8693.html) — IETF, January 2020
- [Identity Assertion JWT Authorization Grant](https://datatracker.ietf.org/doc/draft-ietf-oauth-identity-assertion-authz-grant/) — IETF OAuth WG, 2026-05-21
- [OAuth Identity and Authorization Chaining Across Domains](https://datatracker.ietf.org/doc/draft-ietf-oauth-identity-chaining/) — IETF OAuth WG, 2026-07-19
- [Transaction Tokens](https://datatracker.ietf.org/doc/draft-ietf-oauth-transaction-tokens/) — IETF OAuth WG, 2026-07-30
- [OAuth Client ID Metadata Document](https://datatracker.ietf.org/doc/draft-ietf-oauth-client-id-metadata-document/) — IETF OAuth WG, 2026-07-06
- [AI Identity Management System (draft-ietf-wimse-aims-00)](https://datatracker.ietf.org/doc/html/draft-ietf-wimse-aims-00) — IETF WIMSE WG, 2026-09-15
- [OpenID Connect CIBA Core 1.0](https://openid.net/specs/openid-client-initiated-backchannel-authentication-core-1_0.html) — OpenID Foundation, 2021-09-01
- [SPIFFE Overview](https://spiffe.io/docs/latest/spiffe-about/overview/) — SPIFFE project, accessed 2026-10-27
- [What are agent identities?](https://learn.microsoft.com/en-us/entra/agent-id/identity-platform/what-is-agent-id) — Microsoft Learn, updated 2026-06-15
- [RAG Authorization](https://openfga.dev/docs/modeling/agents/rag-authorization) — OpenFGA, accessed 2026-10-27
- [Relationship Queries: Check, Read, Expand, ListObjects and ListUsers](https://openfga.dev/docs/interacting/relationship-queries) — OpenFGA, accessed 2026-10-27
- [Cedar authorization](https://docs.cedarpolicy.com/auth/authorization.html) — Cedar project, accessed 2026-10-27
- [Policy in Amazon Bedrock AgentCore](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy.html) — AWS, accessed 2026-10-27
- [Three identity vendors shipped the same agent access pattern in eight days](https://workos.com/blog/cross-app-access-converged-in-eight-days) — WorkOS (vendor), 2026-09-04
- [Comments on the Software and Agentic AI Identity concept paper](https://www.nist.gov/news-events/news/2026/09/comments-software-and-agentic-ai-identity-concept-paper) — NIST NCCoE, 2026-09-29
