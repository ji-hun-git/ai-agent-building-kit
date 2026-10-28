# 04 · Tools and actions

> Snapshot verified 2026-10-27. Items tagged **[volatile]** change often — re-check them with the freshness protocol in SKILL.md before relying on them.

## Default
Expose the agent's capabilities as a small set of task-shaped tools on MCP servers built to revision 2026-07-28 **[volatile]** (stateless, `server/discover`, Multi Round-Trip Requests (MRTR) for mid-call input, OpenTelemetry trace context in `_meta`), registered in a private allow-listed catalog behind a gateway. Design every tool for the model, not the API: namespaced names, unambiguous parameters, concise paginated responses, actionable errors, strict schemas and explicit annotations. Past about 10 tools or 10k tokens of definitions, defer-load tools behind tool search with the 3–5 most-used kept loaded, and route fan-out or bulk-data steps through programmatic tool calling while side-effecting calls stay direct. Classify every tool as read, reversible write or irreversible write and enforce the class in the harness with approvals, idempotency keys, dry runs and audit spans, because annotations and prompt instructions are hints, not controls. Use A2A only to delegate to another party's autonomous agent, and computer or browser use only when no API or MCP server exists.

## Decide
- If you are building a new MCP server or client → target 2026-07-28 **[volatile]**: no `initialize` or `Mcp-Session-Id`, version and capabilities read from each request's `_meta`, and `server/discover` implemented (a MUST for servers), because any replica behind a plain round-robin load balancer can then serve any request and gateways can route on the required `Mcp-Method`/`Mcp-Name` headers without parsing bodies.
- If existing code depends on sessions, `initialize`, server-initiated `elicitation/create`/`sampling/createMessage`/`roots/list` or SSE resumability → migrate those first (revision table below) and stop adding Roots, Sampling, Logging, HTTP+SSE or Dynamic Client Registration, because 2026-07-28 removed the former outright while the latter are deprecated with a window of at least 12 months **[volatile]**.
- If a tool needs state across calls (cart, browser context, transaction) → return an opaque server-minted handle from a create tool, take it as an argument, authorize the caller against it on every call and state its lifetime in the description, because the protocol has no session to hold state.
- If a tool must ask the user for input or a confirmation before acting → return an MRTR `input_required` result with an elicitation request and an integrity-protected `requestState`, because MRTR is the only server-to-client request path in 2026-07-28 and `requestState` comes back through the client as attacker-controlled input.
- If an operation outlives a single request (bulk HR update, ticket migration) → use the Tasks extension `io.modelcontextprotocol/tasks` **[volatile]** (`tasks/get` polling, `tasks/update` for mid-flight input), because a broken response stream now loses the in-flight request and SSE resumability is gone.
- If the enterprise IdP must decide which MCP servers each employee's agent may reach → require the Enterprise-Managed Authorization extension **[volatile]** (the client trades an IdP-issued ID-JAG for an MCP access token) and register clients with Client ID Metadata Documents instead of DCR, because policy and revocation then live in one admin console and DCR is deprecated (details: `06-identity-and-authz.md`).
- If a server works machine-to-machine with no user → use the OAuth Client Credentials extension, and if a result reads better as UI (chart, form) → use MCP Apps with a meaningful text fallback, because extensions are off by default and must degrade gracefully.
- If you are choosing which MCP servers agents may use → allow-list them in a private catalog or gateway, use the official registry only as an upstream metadata feed and prefer servers run by the service's own vendor, because the registry is still preview with its API frozen at v0.1 and no GA date **[volatile]**, and a malicious or silently changed server can exfiltrate context.
- If you have 10+ tools, more than 10k tokens of definitions or several aggregated MCP servers → enable tool search and set `defer_loading` **[volatile]** on all but the 3–5 most-used tools, because Anthropic reports that selection accuracy degrades past 30–50 loaded tools. In the Claude Agent SDK, MCP tool search is on by default, so mark the hot tools to stay loaded (`alwaysLoad` **[volatile]**) instead of deferring the rest by hand.
- If a step fans out over many items or pulls large data the model only aggregates → use programmatic tool calling or code execution with MCP in a sandbox, keeping sequential, judgement-per-result and side-effecting calls direct, because intermediate results then stay out of context while strictly sequential flows gain nothing (scores unchanged on τ²-bench).
- If the counterpart is an autonomous agent that plans for itself and belongs to another team, vendor or organization → use A2A v1.0 **[volatile]** and verify its signed Agent Card before trusting it (otherwise expose MCP tools), because A2A's task lifecycle and identity layer are overhead a plain tool call does not need.
- If the target system has no API and no MCP server → use the browser toolset for web-only UIs and full desktop computer use only for desktop-only apps, in a VM with confirmation per consequential action, because every screenshot and page is untrusted input and each UI step is slower and less reliable than an API call.
- If you are assigning gates by class → auto-allow reads, gate reversible writes by policy with an idempotency key and an audit span, and require a dry-run preview plus per-call human approval showing the exact arguments for irreversible or external actions (money, deletion, outbound messages, permission changes), because approval lets a call run but does not guarantee exactly-once execution.
- If the agent runs headless → deny by default and allow-list explicitly (Claude Agent SDK `allowedTools` with `permissionMode: "dontAsk"` **[volatile]**), and where approvals arrive later pause with OpenAI Agents SDK `needs_approval` and a server-held `RunState` **[volatile]**, because a prompt nobody can answer is not a gate. `dontAsk` denies anything not pre-allowed, so when a human must approve writes, run in `default` mode and route the writes through `canUseTool` **[volatile]**.

**MCP revision history.** Use this when migrating older servers or clients.

| Revision | What changed for builders |
| --- | --- |
| 2025-03-26 | OAuth 2.1 authorization. Streamable HTTP replaces HTTP+SSE. Tool annotations (read-only, destructive). JSON-RPC batching (removed in the next revision). |
| 2025-06-18 | Structured tool output and `outputSchema`. Elicitation. Resource links. Servers become OAuth resource servers, and clients must send RFC 8707 resource indicators. `MCP-Protocol-Version` header. |
| 2025-11-25 | OIDC discovery. Icons. Incremental scope consent. Tool-name guidance. URL-mode elicitation. Tools inside sampling. CIMD recommended. Experimental tasks. JSON Schema 2020-12 by default. Formal governance and SDK tiers. |
| 2026-07-28 **[volatile]** | Stateless: no sessions, no `initialize`, `server/discover` required. MRTR replaces server-initiated requests. `subscriptions/listen`. Tasks moved to an extension. Required `resultType`. `Mcp-Method`/`Mcp-Name` headers. OTel `traceparent`/`tracestate`/`baggage` in `_meta`. Deterministic `tools/list` with `ttlMs`/`cacheScope`. RFC 9207 `iss` check. Deprecated: Roots, Sampling, Logging, HTTP+SSE, DCR. |

## Tool design rules
1. **Build tools around tasks, not endpoints.** For example, one `schedule_event` replaces list-availability plus create, and one `get_customer_context` replaces three lookups. Why: fewer calls means fewer wrong chains and less context spent.
2. **Give each tool one distinct purpose, and merge or delete overlaps.** Why: overlapping tools make the agent pick the wrong one or call both.
3. **Namespace names by service, then resource** (`jira_issues_search`, `slack_messages_send`). Stay within MCP's 1–128 characters from `A-Z a-z 0-9 _ - .`, and test prefix against suffix naming in your evals. Why: one search query matches the whole group, and names don't collide when servers are aggregated.
4. **Name parameters unambiguously** (`user_id`, not `user`), and describe each one as you would to a new hire, with formats, units and how it relates to other parameters. Why: invalid-parameter errors in evals usually trace back to vague names.
5. **Return high-signal fields and readable identifiers.** Resolve UUIDs to names, but keep the ID that the next call needs. Why: cryptic IDs lead to hallucinated follow-up calls.
6. **Offer a `response_format` enum** (`concise` by default, `detailed` on request). Why: in Anthropic's Slack example, concise responses used about a third of the tokens.
7. **Paginate, filter and truncate by default.** When you truncate, say so and tell the agent how to narrow the query (for example "20 of 340 shown; add status or a date range"). Why: unbounded results crowd out reasoning, and Claude Code caps a tool response at 25,000 tokens by default **[volatile]**.
8. **Report failures as tool execution errors** (`isError: true`) that state the specific fix and show a correct example. Reserve protocol errors for unknown tools and malformed requests. Why: models self-correct from execution errors and rarely from protocol errors or stack traces.
9. **Make schemas strict:** `additionalProperties: false`, required fields, enums and formats. Turn on strict tool use where the API offers it (`strict: true` **[volatile]**), and add an `outputSchema` for structured results. Why: the model's arguments are constrained to the schema, and the client can validate results.
10. **Add 1–5 realistic `input_examples` to complex tools** **[volatile]** (nested objects, many optional parameters, domain conventions), and skip them for simple tools. Why: in Anthropic's tests they raised accuracy on complex parameters from 72% to 90%, but every example costs tokens.
11. **Set all four MCP annotations explicitly:** `readOnlyHint`, `destructiveHint`, `idempotentHint` and `openWorldHint`. Why: the defaults are pessimistic (not read-only, destructive, not idempotent, open-world), and clients may use them to decide when to ask for confirmation. Still, never enforce policy from annotations, because they are untrusted hints.
12. **Keep reads and writes in separate tools.** A `get`/`search` tool never mutates anything. Why: approval rules, tool search and audits all key on the tool name.
13. **Say in the description what changes, who is affected, how to undo it, and that a dry run exists.** Why: both the model and the human approver read the description.
14. **Keep `tools/list` order and descriptions byte-stable between releases.** Why: prompt-cache hits need a stable prefix, and tool definitions are part of the versioned release.
15. **Evaluate tools on realistic multi-step tasks and read the transcripts.** Track calls, tokens, errors and runtime per task, and let an agent propose description fixes that you then check on held-out tasks. Why: small description edits move results a lot.

A write tool that follows these rules, in MCP shape:
```json
{
  "name": "hr_leave_request_create",
  "description": "File one leave request for one employee. Reversible: hr_leave_request_cancel undoes it until the start date. Call with dry_run=true first and show the preview to the user; reuse the same idempotency_key on retries.",
  "inputSchema": {"type": "object", "additionalProperties": false, "required": ["employee_id", "start_date", "end_date", "idempotency_key"],
    "properties": {"employee_id": {"type": "string", "description": "HR worker ID such as W-104233, not a name or email"},
      "start_date": {"type": "string", "format": "date"}, "end_date": {"type": "string", "format": "date"},
      "idempotency_key": {"type": "string", "format": "uuid"}, "dry_run": {"type": "boolean", "default": true}}},
  "annotations": {"readOnlyHint": false, "destructiveHint": false, "idempotentHint": true, "openWorldHint": false}
}
```

## Build checklist
- [ ] List every action in the agent spec with its class (read / reversible write / irreversible write), the owning system, the undo path and the approver role.
- [ ] Make the MCP server stateless. It implements `server/discover`, reads version and capabilities from each request's `_meta`, returns `serverInfo` in each result's `_meta`, and keeps no per-connection state. Test: two replicas behind round-robin serve one interleaved conversation.
- [ ] Return `tools/list` in deterministic order with `ttlMs` and `cacheScope`, using `private` when the list is filtered by the caller's scopes.
- [ ] Require the `Mcp-Method`/`Mcp-Name` headers at the gateway, and authorize per tool there.
- [ ] Propagate OTel `traceparent`/`tracestate`/`baggage` in `_meta` from client through gateway to server. Emit one span per tool call with tool name, class, decision, approver, idempotency key and outcome, and hash or redact the arguments (`09-observability.md`).
- [ ] Collect confirmations and missing input over MRTR. Protect `requestState` with HMAC or AEAD, binding it to the principal, a short TTL and a digest of the original request. Enforce single use on the server for one-time actions.
- [ ] Give every mutating tool a required `idempotency_key`. The server dedupes on (principal, tool, key) and returns the original result on replay. Test: replaying a call creates one record.
- [ ] After a crash or timeout between the action and the state save, look up the idempotency key in the target system before any retry.
- [ ] Give every irreversible tool a `dry_run` mode (or a paired `*_preview` tool) that returns the exact change the approval UI will show.
- [ ] Wire the Claude Agent SDK gates **[volatile]**:
  - deny rules for forbidden calls;
  - a `PreToolUse` hook for checks that must run on every call;
  - `canUseTool` for human prompts;
  - `_meta["anthropic/requiresUserInteraction"]` on MCP tools that always need a person.
- [ ] Test the bypass paths. A bare tool name in `allowedTools`, `acceptEdits` and `bypassPermissions` all skip `canUseTool`, so move any check that must always run into a hook.
- [ ] Wire the OpenAI gates **[volatile]**:
  - `needs_approval` (a bool or an async policy) on Agents SDK tools;
  - `require_approval` on MCP servers, which is on by default in the Responses API and covers one call per approval response;
  - `RunState` stored on the server, with each reviewer authenticated and each decision consumed atomically.
- [ ] Configure tool search. Add the tool search tool, set `defer_loading: true` on all tools except 3–5 hot ones, and add a one-line list of tool categories to the system prompt. Write one eval per job that checks the right tool is found.
- [ ] Opt only read and aggregate tools into programmatic calling (`allowed_callers` **[volatile]**). Run the code in a sandbox with no outbound network access by default. Still handle direct calls, because `allowed_callers` is not a security boundary.
- [ ] Record each approved MCP server in the private catalog with owner, pinned version, scopes and data classification. Re-review whenever its tool definitions change.
- [ ] Register clients with CIMD. Validate `iss` (RFC 9207), key stored credentials by issuer, send RFC 8707 resource indicators, and request least-privilege scopes for each tool.
- [ ] For A2A:
  - Serve `/.well-known/agent-card.json` and sign it (JWS over the card canonicalized with JCS).
  - Before trusting a remote card, verify at least one signature with an unexpired key fetched over HTTPS.
- [ ] For computer or browser use:
  - Run in a dedicated VM or container with a fresh profile that holds no credentials.
  - Enforce the domain allow-list at the network layer and re-check it after redirects.
  - Leave `javascript_exec` and `file_upload` off.
  - Confirm before any batch that contains a purchase, a message, a data transmission, a deletion or acceptance of terms.
  - Verify the outcome in the target system.
- [ ] Add eval cases for every tool:
  - the right tool is selected;
  - the agent recovers from its own error message;
  - pagination is used;
  - the approval-required path works;
  - a replay stays idempotent;
  - injected text in tool output never triggers a write.

## Avoid
- One tool per REST endpoint → task-shaped tools (agents chain endpoints badly and spend context on intermediate results).
- Loading every MCP tool into the prompt → tool search with `defer_loading` (five common servers take about 55k tokens of definitions, and accuracy falls past 30–50 tools).
- Skipping approval because a third-party server says `readOnlyHint: true` → classify the tool in your own policy (annotations from untrusted servers are only hints).
- Approval without idempotency → idempotency keys plus a reconcile step before any retry (a crash after the action but before the state save repeats the action on resume).
- Client-side or unauthenticated approval state → a server-held `RunState`, authenticated reviewers and decisions consumed atomically (the SDK does not authenticate snapshots, so approvals can be replayed).
- Sticky "always approve" on shell, file-edit or irreversible tools → per-call approval with the arguments shown (sticky shell and file-edit decisions match only tool type and name, so they also cover other agents' calls).
- Session-keyed state or sticky load balancing → explicit handles passed as arguments (2026-07-28 has no sessions).
- Unsigned or unbound `requestState` → HMAC or AEAD bound to principal, TTL and originating request (it passes through the client and can be tampered with or replayed).
- New code on Sampling, Roots, MCP Logging, HTTP+SSE or DCR → direct LLM APIs, tool parameters or resource URIs, OTel or stderr, Streamable HTTP, CIMD (all deprecated and scheduled for removal).
- Secrets or PII marked with `x-mcp-header` → keep them in the request body (header values are visible to every intermediary).
- Computer use against a system that has an API → the API or an MCP wrapper (UI automation adds injection surface and flakiness).
- A2A to call a deterministic service → an MCP tool (a function call needs no task lifecycle or agent identity).
- Stack traces or bare error codes as tool output → the specific fix plus a valid example (the model can act on that, not on a trace).

## Additions (verified 2026-10-27)

- If the agent already has a sandboxed shell, try a mature CLI plus one usage example before building an MCP server for the same system ([Willison](https://simonwillison.net/2025/Sep/30/designing-agentic-loops/)).
- For systems you own, give every action an API, CLI or MCP path and document it in Markdown with commands, not click-paths, so agents never need a GUI.
- Restrict tools mid-session through the API (`tool_removal` / `tool_addition` on Claude, `allowed_tools` on OpenAI **[volatile]**), not by editing the tool list, which breaks the cache.
- Shipping a coding agent for editors: expose it over the Agent Client Protocol and list it in the ACP Registry ([Zed](https://zed.dev/blog/acp-registry)).
- Agents that buy or pay: use signed mandates or shared payment tokens (AP2, Agentic Commerce Protocol **[volatile]**) so the agent never holds card credentials; classify every payment as irreversible.

## Verify before relying
| Fact **[volatile]** | Snapshot (2026-10-27) | Where to check (URL) |
| --- | --- | --- |
| Current MCP spec revision | 2026-07-28; no next revision announced | https://modelcontextprotocol.io/specification/2026-07-28/changelog |
| MCP deprecations and window | Roots, Sampling, Logging, HTTP+SSE and DCR deprecated; window of at least 12 months | https://modelcontextprotocol.io/specification/2026-07-28/changelog |
| SDK support for 2026-07-28 | TypeScript, Python, Go and C# on release day; Rust in beta | https://blog.modelcontextprotocol.io/posts/2026-07-28/ |
| Official MCP extensions | Tasks, MCP Apps, Enterprise-Managed Authorization, OAuth Client Credentials, Skills over MCP; client support varies | https://modelcontextprotocol.io/docs/extensions/overview |
| MCP annotation names and defaults | `readOnlyHint` false, `destructiveHint` true, `idempotentHint` false, `openWorldHint` true | https://modelcontextprotocol.io/specification/2026-07-28/schema |
| Official MCP Registry status | Preview; API frozen at v0.1 since 2025-10-24; GA undated | https://github.com/modelcontextprotocol/registry |
| Governance and adoption | MCP in the Linux Foundation's AAIF since 2025-12-09 ("more than 10,000 published MCP servers"); A2A moved into AAIF 2026-08-17 | https://www.linuxfoundation.org/press/linux-foundation-announces-the-formation-of-the-agentic-ai-foundation |
| Anthropic tool search | `tool_search_tool_regex_20251119` and `tool_search_tool_bm25_20251119`; at most 10,000 deferred tools per request; `defer_loading` composes with strict mode | https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-search-tool |
| Anthropic programmatic tool calling | GA; needs `code_execution_20260120` or later; `allowed_callers`; excludes `strict: true` tools, MCP-connector tools and the computer and browser toolsets | https://platform.claude.com/docs/en/agents-and-tools/tool-use/programmatic-tool-calling |
| Anthropic computer and browser use | `computer_toolset_20260801` (17 members) and `browser_toolset_20260801` (31 members) GA on the Claude API; `computer_20251124` beta for older models and Bedrock | https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool |
| Tool use examples, Claude Code response cap | `input_examples` (beta header `advanced-tool-use-2025-11-20` at launch); 25,000-token cap | https://www.anthropic.com/engineering/advanced-tool-use |
| OpenAI tool search | `{"type":"tool_search"}` plus `defer_loading`; `gpt-5.4` and later; fewer than 10 functions per namespace | https://developers.openai.com/api/docs/guides/tools-tool-search |
| OpenAI remote MCP | `type: "mcp"`, `server_url`/`tunnel_id`, `allowed_tools`, `require_approval` on by default; `connector_id` deprecated for models released after 2026-09-01 | https://developers.openai.com/api/docs/guides/tools-connectors-mcp |
| OpenAI computer use | `computer` tool; `computer_call` with an ordered `actions` array; status not stated on the page | https://developers.openai.com/api/docs/guides/tools-computer-use |
| Gemini computer use | Preview; `computer_use` tool; `safety_decision` → `require_confirmation` → `safety_acknowledgement`; injection detection is opt-in | https://ai.google.dev/gemini-api/docs/computer-use |
| Claude Agent SDK permissions | Modes `default`, `dontAsk`, `acceptEdits`, `bypassPermissions`, `plan`, `auto`; evaluation order hooks → deny → ask → mode → allow → `canUseTool` | https://code.claude.com/docs/en/agent-sdk/permissions |
| OpenAI Agents SDK approvals | `needs_approval`, `interruptions`, `state.approve`/`reject`, `RunState` to and from JSON | https://openai.github.io/openai-agents-python/human_in_the_loop/ |
| A2A version and signing | v1.0.1 (2026-05-28) is the latest release; spec site lists 1.0.0; JWS-signed Agent Cards | https://github.com/a2aproject/A2A/releases |
| A2A adoption | 150+ organizations; in Azure AI Foundry, Copilot Studio and Bedrock AgentCore (2026-04-09) | https://www.linuxfoundation.org/press/a2a-protocol-surpasses-150-organizations-lands-in-major-cloud-platforms-and-sees-enterprise-production-use-in-first-year |

## Sources
- [Writing effective tools for agents — with agents](https://www.anthropic.com/engineering/writing-tools-for-agents) — Anthropic Engineering, 2025-09-11
- [Introducing advanced tool use on the Claude Developer Platform](https://www.anthropic.com/engineering/advanced-tool-use) — Anthropic Engineering, 2025-11-24
- [Code execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp) — Anthropic Engineering, 2025-11-04
- [MCP Key Changes, 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/changelog) — Model Context Protocol, 2026-07-28
- [MCP Key Changes, 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25/changelog) — Model Context Protocol, 2025-11-25
- [MCP Key Changes, 2025-06-18](https://modelcontextprotocol.io/specification/2025-06-18/changelog) — Model Context Protocol, 2025-06-18
- [MCP Key Changes, 2025-03-26](https://modelcontextprotocol.io/specification/2025-03-26/changelog) — Model Context Protocol, 2025-03-26
- [MCP Tools (2026-07-28)](https://modelcontextprotocol.io/specification/2026-07-28/server/tools) — Model Context Protocol, 2026-07-28
- [MCP Multi Round-Trip Requests](https://modelcontextprotocol.io/specification/2026-07-28/basic/patterns/mrtr) — Model Context Protocol, 2026-07-28
- [MCP Schema reference (ToolAnnotations)](https://modelcontextprotocol.io/specification/2026-07-28/schema) — Model Context Protocol, 2026-07-28
- [MCP Extensions overview](https://modelcontextprotocol.io/docs/extensions/overview) — Model Context Protocol, accessed 2026-10-27
- [Enterprise-Managed Authorization](https://modelcontextprotocol.io/extensions/auth/enterprise-managed-authorization) — Model Context Protocol, accessed 2026-10-27
- [The 2026-07-28 Specification](https://blog.modelcontextprotocol.io/posts/2026-07-28/) — MCP Blog, 2026-07-28
- [modelcontextprotocol/registry README](https://github.com/modelcontextprotocol/registry) — GitHub, accessed 2026-10-27
- [Linux Foundation announces the Agentic AI Foundation](https://www.linuxfoundation.org/press/linux-foundation-announces-the-formation-of-the-agentic-ai-foundation) — Linux Foundation, 2025-12-09
- [A2A protocol surpasses 150 organizations](https://www.linuxfoundation.org/press/a2a-protocol-surpasses-150-organizations-lands-in-major-cloud-platforms-and-sees-enterprise-production-use-in-first-year) — Linux Foundation, 2026-04-09
- [Google transfers A2A to the Agentic AI Foundation](https://www.techzine.eu/news/devops/143659/google-transfers-a2a-to-the-agentic-ai-foundation/) — Techzine, 2026-08-17
- [a2aproject/A2A releases](https://github.com/a2aproject/A2A/releases) — GitHub, accessed 2026-10-27
- [A2A Protocol Specification](https://a2a-protocol.org/latest/specification/) — A2A Project, accessed 2026-10-27
- [Tool search tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-search-tool) — Anthropic docs, accessed 2026-10-27
- [Programmatic tool calling](https://platform.claude.com/docs/en/agents-and-tools/tool-use/programmatic-tool-calling) — Anthropic docs, accessed 2026-10-27
- [Computer use tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool) — Anthropic docs, accessed 2026-10-27
- [Browser use tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/browser-use-tool) — Anthropic docs, accessed 2026-10-27
- [Agent SDK: Configure permissions](https://code.claude.com/docs/en/agent-sdk/permissions) — Anthropic docs, accessed 2026-10-27
- [Human-in-the-loop](https://openai.github.io/openai-agents-python/human_in_the_loop/) — OpenAI Agents SDK docs, accessed 2026-10-27
- [MCP and Connectors](https://developers.openai.com/api/docs/guides/tools-connectors-mcp) — OpenAI docs, accessed 2026-10-27
- [Tool search](https://developers.openai.com/api/docs/guides/tools-tool-search) — OpenAI docs, accessed 2026-10-27
- [Computer use](https://developers.openai.com/api/docs/guides/tools-computer-use) — OpenAI docs, accessed 2026-10-27
- [Computer Use](https://ai.google.dev/gemini-api/docs/computer-use) — Google AI for Developers, updated 2026-10-22
