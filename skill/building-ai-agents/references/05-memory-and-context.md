# 05 · Memory and context

> Snapshot verified 2026-10-27. Items tagged **[volatile]** change often — re-check them with the freshness protocol in SKILL.md before relying on them.

## Default
Manage the context window on the server and keep durable facts outside it. Use the provider's or harness's built-in compaction as the primary long-context mechanism (Anthropic on-demand compaction, OpenAI Responses `compact_threshold` **[volatile]**, or the compaction and context management built into the Claude Agent SDK, OpenAI Agents SDK, Google ADK, Microsoft Agent Framework and Deep Agents) instead of writing a summarizer, and add tool-result clearing for loops dominated by large, single-use tool output. Write anything that must survive summarization or a new session (decisions, user preferences, progress, checklists) to file-style memory (Anthropic memory tool, Managed Agents memory stores, ADK Memory Bank), scoped per user or project and read-only wherever writing is not needed. Push broad exploration into sub-agents with clean context windows that return condensed summaries of roughly 1,000–2,000 tokens. Treat memory as untrusted data: an injection that gets written to memory replays in every later session. Add a third-party memory layer only for needs the native options do not cover.

## Decide
- If a run can outgrow the window or quality drops as it lengthens → provider compaction; on Claude use on-demand compaction (beta header `compact-2026-09-04` **[volatile]**, top-level `compaction` **[volatile]** parameter) when you need to control timing, keep recent turns verbatim or compact in the background, and threshold compaction (`compact_20260112` **[volatile]** edit) only when the API should compact inside ordinary requests, because Anthropic recommends on-demand wherever it is available.
- If you are on the OpenAI Responses API → `context_management` **[volatile]** with a `compaction` entry and `compact_threshold` **[volatile]** (plus `store=false` **[volatile]** for ZDR), or the stateless `/responses/compact` **[volatile]** endpoint whose output you pass on unpruned, because the compaction item is opaque and carries prior state; with `previous_response_id` **[volatile]** chaining, never prune manually.
- If you build on a harness → turn on its built-in compaction or context management (the OpenAI Agents SDK runs automatic compaction, see its v0.24.0 **[volatile]** release notes; ADK and the Microsoft Agent Framework Harness Agent ship compaction; Deep Agents ships context management), because a hand-written summarizer duplicates it and drifts.
- If the loop is dominated by large tool results that are needed once → tool-result clearing (`clear_tool_uses_20250919` **[volatile]** under `context_management.edits` **[volatile]**, beta `context-management-2025-06-27` **[volatile]**) with `clear_at_least` **[volatile]** set and must-keep tools in `exclude_tools` **[volatile]**, because clearing is the lightest touch but each clear invalidates the cached prefix; on Claude you cannot send `compaction` and `context_management` on the same request.
- If a fact must survive summarization or a new session → write it to durable memory and run memory alongside compaction, because compaction keeps the window small while memory keeps what a summary may drop.
- If you run your own loop on Claude → memory tool (`memory_20250818` **[volatile]**, client-side, backed by your storage); on Managed Agents → memory stores (beta `agent-memory-2026-07-22` **[volatile]**) attached at session creation in `resources` **[volatile]**; on Google ADK → `VertexAiMemoryBankService` **[volatile]** with `preload_memory` (every turn) or `load_memory` (agent decides) **[volatile]**; on the OpenAI Agents SDK → Sessions; on Microsoft Agent Framework → context providers, because the native path already integrates with that vendor's compaction and audit.
- If the agent reads untrusted input (web pages, email, uploads, third-party tool output) → attach memory read-only, or route writes through a gate (schema, provenance tag, human or rule review), because a successful prompt injection written to memory is read back as trusted context in later sessions.
- If memory belongs to users or tenants → one store or directory per user, plus a separate read-only store for shared reference material, because a shared writable store lets one user's content steer another user's agent.
- If a subtask reads far more than the orchestrator needs to see → a sub-agent with its own context, an allow-list of tools, a small tier or `low` effort, and an explicit return format, because only its final message returns to the parent.
- If the model spawns sub-agents on its own → cap depth, concurrency and spend (Claude Agent SDK: `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` and `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS` **[volatile]** plus the query's spend-cap option), because one prompt can otherwise grow into a tree of agents.
- If you need memory portable across vendors, entity and relationship memory that changes over time, or one user profile shared across apps → evaluate mem0 (memory layer), Zep Graphiti (temporal knowledge graph) or Letta (stateful-agent platform; no release since 2026-05-14 **[volatile]**); otherwise stay native, because every major SDK now has a memory path and each extra store is one more place to poison, secure and audit.

## Build checklist
- [ ] Use one compaction mechanism per conversation; the Claude SDK tool runner refuses to compact while `context_management` **[volatile]** holds a compaction edit.
- [ ] Trigger compaction at a limit you choose below the window; estimate size from the last response's `input_tokens` + `cache_read_input_tokens` + `cache_creation_input_tokens` + `output_tokens` **[volatile]**, since `input_tokens` alone excludes cached tokens.
- [ ] Claude on-demand compaction: resolve pending tool calls first, send the same system prompt and tools, check `stop_reason` **[volatile]** equals `"compaction"` before swapping, keep the returned block exactly as returned (including its `signature` **[volatile]**), put it first, send exactly one block, and send the beta header on every later request:
  ```python
  summary = client.beta.messages.create(
      model=MODEL, max_tokens=4096, system=SYSTEM, tools=TOOLS,
      betas=["compact-2026-09-04"], messages=history,
      compaction={"type": "summarize", "instructions": KEEP_RULES},
  )
  if summary.stop_reason == "compaction":
      history = [{"role": "assistant", "content": summary.content}]
  ```
- [ ] Write compaction `instructions` **[volatile]** (≤ 16,384 chars) listing what the summary must keep (IDs, decisions, constraints, the open request) and telling the model not to call tools.
- [ ] After compaction, restate what the summary cannot carry: images, documents, fetched URLs, mid-conversation system instructions and per-message effort.
- [ ] OpenAI Responses server-side compaction shape:
  ```python
  client.responses.create(model=MODEL, input=items, store=False,
      context_management=[{"type": "compaction", "compact_threshold": THRESHOLD_TOKENS}])
  ```
- [ ] Add a recall eval: a long session crosses the compaction trigger, then the agent must still use a fact stated before it.
- [ ] Tool-result clearing: set `trigger`, `keep` and `clear_at_least` **[volatile]**; list memory, plan and other must-keep tools in `exclude_tools` **[volatile]**; enable the memory tool in the same request so Claude is warned to save before results are cleared.
- [ ] Memory tool handler: resolve every path to canonical form and reject anything outside `/memories` (`../`, `..\`, URL-encoded `%2e%2e%2f`); refuse delete or rename of the root; cap file size and view output; expire files nobody reads; strip secrets and personal data before writing.
- [ ] Map `/memories` to per-user or per-tenant storage, never one shared directory.
- [ ] Managed Agents memory stores: set `access` **[volatile]** to read-only for reference stores and read-write only for sessions that must add memories; stay within 8 stores per session, 100 kB per memory and 10,000 memories per store **[volatile]**; use the `content_sha256` **[volatile]** precondition for concurrent edits; export versions you must keep beyond the 30-day **[volatile]** retention.
- [ ] Record provenance on every memory write (session, source, time, trust level) and keep system instructions out of user-writable memory.
- [ ] Keep a rollback path (versioned or snapshotted memory) and a redaction procedure for deletion requests; Managed Agents provides memory versions and redact.
- [ ] Add a memory-poisoning red-team case: untrusted content tries to plant an instruction in memory, and a later session must not follow it (e.g. promptfoo's memory-poisoning plugin, mapped to OWASP agentic threat T1).
- [ ] Define each sub-agent with a description, its own prompt, an allow-list of tools, a model or effort, and a return format with a length limit; put every path, error and decision it needs in the delegation prompt, because it does not see the parent's history.
- [ ] For multi-session work, have the first session write a progress log and feature checklist to memory; every later session reads them first and updates them last; mark a feature done only after end-to-end verification.

## Avoid
- A hand-written summarizer or the SDK's client-side `compaction_control` **[volatile]** → server-side compaction (Anthropic deprecated the client helper and removed it from the Python SDK).
- Editing the compaction block or keeping the messages it summarized → send the block exactly as returned and drop those messages (an edited block or messages in front of it fail with 400; summarized messages left after it are silently sent again).
- Relying on compaction for must-keep facts → write them to memory (summaries drop details).
- Clearing tool results on every turn → set `clear_at_least` **[volatile]** so each clear is worth the cache invalidation (cache churn raises latency and token use).
- Changing top-level effort mid-conversation → per-message effort, see `01-model-and-harness.md` (top-level changes invalidate the cache).
- One writable memory store shared by all users → per-user stores plus a read-only shared store (cross-user poisoning and leakage).
- Following instructions found in memory → treat memory as data and keep instructions in the system prompt (poisoned memory persists across sessions and context resets).
- A memory handler without path validation → canonicalize and confine to the memory root (traversal reaches secrets outside it).
- Sub-agents that return full transcripts → condensed summaries in a fixed format (the point is a clean parent context).
- Unbounded model-spawned sub-agents → depth, concurrency and spend caps (token use and coherence degrade fast).
- Adding mem0, Letta or Graphiti by default → native memory first (another store to secure, audit and keep consistent).

## Additions (verified 2026-10-27)

- In compaction keep-rules, keep failed actions and their errors and the paths or IDs of anything dropped, so the summary stays restorable and the agent does not repeat mistakes.
- Keep the history append-only between compactions; compaction itself is the one sanctioned rewrite.

## Verify before relying
| Fact **[volatile]** | Snapshot (2026-10-27) | Where to check (URL) |
| --- | --- | --- |
| Claude on-demand compaction | Beta `compact-2026-09-04` (since 2026-09-14); `compaction: {type: "summarize", instructions}`; `stop_reason` `"compaction"`; block carries a `signature`; `instructions` ≤ 16,384 chars; not combinable with `context_management` |
| Claude usage fields | `input_tokens` excludes cached tokens; add `cache_read_input_tokens`, `cache_creation_input_tokens`, `output_tokens` | https://platform.claude.com/docs/en/build-with-claude/compaction-on-demand | https://platform.claude.com/docs/en/build-with-claude/compaction-on-demand |
| Claude threshold compaction | `compact_20260112` edit in `context_management`; beta | https://platform.claude.com/docs/en/build-with-claude/compaction |
| Claude context editing | Beta `context-management-2025-06-27`; `context_management.edits`; `clear_tool_uses_20250919` (default trigger 100,000 input tokens, keep 3 tool uses; `clear_at_least`, `exclude_tools`, `clear_tool_inputs`); `clear_thinking_20251015`; `compaction_control` deprecated, removed in Python SDK v1.0 | https://platform.claude.com/docs/en/build-with-claude/context-editing |
| Claude memory tool | `memory_20250818`, no beta header; view/create/str_replace/insert/delete/rename | https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool |
| Managed Agents memory stores | Beta `agent-memory-2026-07-22` on store calls; attach via session `resources` with `managed-agents-2026-04-01`; `access` `read_write` (default) or `read_only`; 8 stores/session; 100 kB/memory; 10,000 memories/store; versions kept 30 days; `content_sha256` precondition | https://platform.claude.com/docs/en/managed-agents/memory |
| OpenAI compaction | `context_management=[{"type": "compaction", "compact_threshold": N}]`; `store=false` for ZDR; `/responses/compact`; no manual pruning with `previous_response_id` | https://developers.openai.com/api/docs/guides/compaction |
| OpenAI Agents SDK | Automatic compaction (v0.24.0 release notes, 2026-10-15, defer it for pending approvals); sandbox memory consolidation turns (v0.23.0, 2026-10-01); Sessions | https://github.com/openai/openai-agents-python/releases |
| Google ADK memory | `InMemoryMemoryService`, `VertexAiMemoryBankService`, `VertexAiRagMemoryService`; `preload_memory`, `load_memory` | https://adk.dev/sessions/memory/ |
| Claude Agent SDK sub-agent caps | `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` default 3; `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS` default 20; TypeScript SDK v0.3.219 / Python v0.2.127 or later | https://code.claude.com/docs/en/agent-sdk/subagents |
| Third-party memory releases | mem0 v2.2.1 (2026-09-25); Letta 0.16.8 (2026-05-14); Graphiti v0.31.2 (2026-10-20) | https://github.com/mem0ai/mem0 ; https://github.com/letta-ai/letta ; https://github.com/getzep/graphiti |
| Memory-poisoning taxonomy | promptfoo maps its plugin to OWASP agentic threat "T1: Memory Poisoning"; OWASP Agent Memory Guard is an incubator project | https://www.promptfoo.dev/docs/red-team/plugins/memory-poisoning/ ; https://owasp.org/www-project-agent-memory-guard/ |

## Sources
- [Compaction overview](https://platform.claude.com/docs/en/build-with-claude/compaction) — Anthropic, no date shown, accessed 2026-10-27
- [Compaction on demand](https://platform.claude.com/docs/en/build-with-claude/compaction-on-demand) — Anthropic, no date shown, accessed 2026-10-27
- [Context editing](https://platform.claude.com/docs/en/build-with-claude/context-editing) — Anthropic, no date shown, accessed 2026-10-27
- [Memory tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool) — Anthropic, no date shown, accessed 2026-10-27
- [Using agent memory](https://platform.claude.com/docs/en/managed-agents/memory) — Anthropic, no date shown, accessed 2026-10-27
- [Claude Developer Platform release notes](https://platform.claude.com/docs/en/release-notes/overview) — Anthropic, entries through 2026-10-23
- [Subagents in the SDK](https://code.claude.com/docs/en/agent-sdk/subagents) — Anthropic, no date shown, accessed 2026-10-27
- [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) — Anthropic Engineering, 2025-09-29
- [Compaction guide](https://developers.openai.com/api/docs/guides/compaction) — OpenAI developer docs, no date shown, accessed 2026-10-27
- [openai-agents-python releases](https://github.com/openai/openai-agents-python/releases) — GitHub, queried 2026-10-27
- [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/) — OpenAI, no date shown, accessed 2026-10-27
- [ADK memory](https://adk.dev/sessions/memory/) — Google, no date shown, accessed 2026-10-27
- [Agent Framework overview](https://learn.microsoft.com/en-us/agent-framework/overview/) — Microsoft Learn, 2026-10-23
- [LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview) — LangChain, no date shown, accessed 2026-10-27
- [mem0](https://github.com/mem0ai/mem0), [letta](https://github.com/letta-ai/letta), [graphiti](https://github.com/getzep/graphiti) — GitHub, queried 2026-10-27
- [Memory poisoning plugin](https://www.promptfoo.dev/docs/red-team/plugins/memory-poisoning/) — Promptfoo, last updated 2026-10-26
- [OWASP Agent Memory Guard](https://owasp.org/www-project-agent-memory-guard/) — OWASP Foundation, no date shown, accessed 2026-10-27
