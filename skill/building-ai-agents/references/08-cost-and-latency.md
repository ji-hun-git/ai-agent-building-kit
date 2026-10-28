# 08 · Cost and latency

> Snapshot verified 2026-10-27. Items tagged **[volatile]** change often — re-check them with the freshness protocol in SKILL.md before relying on them.

## Default
Let provider prompt caching do most of the work: render every request as a stable prefix (tool definitions → system prompt → static reference material) followed by volatile content (history, retrieved chunks, dates, user input), and keep that prefix byte-identical for the whole session. Treat model snapshot, effort, speed, thinking settings, tool set and router choice as session constants, because changing any of them at the top level is a cache miss; when one must change, use the providers' cache-preserving mid-conversation mechanisms. Do not put a semantic (embedding-similarity) response cache in front of an agent by default: it returns answers generated for another user and context, and its fuzzy keys can be collided on purpose. Pick effort per workload from a sweep on your own evals, send offline work through batch APIs, defer rarely used tools behind tool search, and let provider compaction keep long sessions small. Every lever in this file changes behavior, so every change ships through the eval gate in `10-evals-and-release.md`.

## Decide
- If the same prefix recurs across calls and is at least the model's minimum cacheable length (Anthropic 512–4,096 tokens depending on model; OpenAI 1,024 on GPT-5.6+; Gemini 4 Argon 4,096) **[volatile]** → rely on provider prefix caching (Anthropic: one top-level `cache_control` for automatic caching, or up to 4 explicit breakpoints; OpenAI and Gemini 2.5+: on by default) **[volatile]**, because it matches exact prefixes only and still generates a fresh answer, so it cannot serve a stale or foreign response.
- If calls in a session can be further apart than the default TTL (Anthropic 5 minutes, refreshed on use; OpenAI GPT-5.6+ 30 minutes) **[volatile]**, or the work runs in a batch → use the long TTL (Anthropic `"cache_control": {"type": "ephemeral", "ttl": "1h"}`; OpenAI `prompt_cache_options.ttl: "12h"`) **[volatile]**, because an expired prefix is rewritten in full on the next call.
- If the first reply's time-to-first-token matters and the prefix is large → pre-warm at session start (Anthropic `max_tokens: 0` with an explicit breakpoint and the same thinking and effort settings as the real calls; OpenAI `prompt_cache_options.prewarm: true`) **[volatile]**, because it moves the cache-miss penalty off the user's first turn; Anthropic rejects pre-warm inside Message Batches and with `stream: true`.
- If instructions, effort or tools must change mid-session → append the change instead of rewriting the prefix: Anthropic mid-conversation `role: "system"` messages, per-message `output_config.effort` (beta `mid-conversation-output-config-2026-07-01`), `tool_addition` blocks (beta `inline-tools-2026-09-15`); OpenAI `configuration_update` input items on supported GPT-6 models **[volatile]**, because a top-level change invalidates the cache from that level down.
- If someone proposes a semantic response cache → decline by default; allow it only for public, non-personalized content that needs no permission check, keyed by tenant + permission scope + release bundle ID, holding verified answers and purged on every release and rollback, because CacheAttack hijacked responses at an 86% hit rate, steered agent actions and transferred across embedding models, and cross-user leakage is the common everyday failure.
- If traffic mixes easy and hard requests → trial a learned router (a RouteLLM-style strong/weak router, or a managed one such as Azure Foundry model router in Balanced, Cost or Quality mode **[volatile]**) behind your full eval suite, pinned per session and logging the served model, because routing changes the model per request, breaks prefix reuse across turns, and Microsoft states managed routing does not remove the need for evaluation.
- If nobody is waiting on the answer (eval runs, backfills, enrichment, nightly reports) → use batch APIs (Anthropic Message Batches; OpenAI Batch, `24h` window only) or OpenAI `service_tier: "flex"` (beta) **[volatile]**, because they draw on separate capacity and trade latency for lower cost; match results by `custom_id` and retry `expired` items.
- If you are choosing an effort level → sweep effort per workload on your evals and take the lowest level that passes the gate (typical start: `low` for sub-agents, classification and chat; `medium` for well-specified agentic tasks; `high`/`xhigh` for long-horizon coding) **[volatile]**, because effort scales all output tokens including tool calls and thinking, lower effort makes fewer and terser tool calls, and defaults differ by model (Opus 5.5 and Haiku 5.5 default to `medium`, most others `high`).
- If long streamed outputs are the bottleneck → consider fast mode (`speed: "fast"`, up to 2.5x output tokens per second, GA on Opus 5.5) **[volatile]**; if time-to-first-token is the bottleneck → fix caching, pre-warm, prompt size or effort instead, because fast mode targets output speed, not TTFT, and is unavailable with Batch.
- If you need resilience to overload at peak → design retries with backoff, a fallback region or provider and graceful degradation; treat priority tiers as availability, not speed (Anthropic Priority Tier reduces "overloaded" errors and is no longer sold as new commitments) **[volatile]**, because prioritization does not make tokens generate faster.
- If the agent has 10+ tools or more than 10k tokens of definitions → defer all but the 3–5 most used behind tool search (Anthropic `tool_search_tool_regex_20251119` or `tool_search_tool_bm25_20251119` with `defer_loading: true`; OpenAI `{"type": "tool_search"}` on gpt-5.4+) **[volatile]**, because deferred definitions stay out of the cached prefix, a five-server MCP setup costs ~55k definition tokens up front, and selection accuracy degrades past 30–50 loaded tools.
- If sessions outgrow a comfortable window → use provider compaction (Anthropic on-demand compaction, beta `compact-2026-09-04`; OpenAI `context_management` with `compact_threshold`, or `/responses/compact`) plus tool-result clearing with a `clear_at_least` floor **[volatile]**, because response quality degrades as context grows and each clearing pass costs one cache rewrite.

## Build checklist
- [ ] Render requests in a fixed order — tools (stable sort, stable JSON key order) → system prompt → static reference → history → this turn's retrieval → user message — and unit-test that rendering the same session twice gives identical bytes.
- [ ] Keep dates, request IDs, user names, feature flags and experiment arms out of the system prompt; put them in the latest turn or a mid-conversation system message.
- [ ] Freeze per session, and store on the session record: model snapshot, effort, speed, thinking config, tool set, `tool_choice`, router mode. Restrict tools without removing definitions: on Claude Opus 5.5 and Fable 5.1 use `tool_removal` / `tool_addition` blocks, because forced `tool_choice` (any/tool) returns 400 there **[volatile]**; on OpenAI use `allowed_tools` **[volatile]**.
- [ ] Log cache usage on every call — Anthropic `cache_read_input_tokens`, `cache_creation_input_tokens`; OpenAI `usage.input_tokens_details.cached_tokens`, `cache_write_tokens`; Gemini `usage.total_cached_tokens` **[volatile]** — and emit a cache-hit ratio per release (see `09-observability.md`).
- [ ] Add a CI check that runs two consecutive turns and fails if the second shows zero cache reads; use Anthropic cache diagnostics to locate where a prefix diverged.
- [ ] Check cache isolation against tenancy: Anthropic isolates per workspace on the Claude API, Claude Platform on AWS and Microsoft Foundry, but only per organization on Bedrock and Google-managed Vertex; OpenAI per organization and regional boundary **[volatile]**.
- [ ] On OpenAI models before GPT-5.6, set a `prompt_cache_key` per prefix family and keep each key near or below ~15 requests/min, splitting hotter traffic across keys **[volatile]**.
- [ ] When fanning out parallel requests that share a prefix, send one first and wait until its response starts before sending the rest.
- [ ] Run an effort sweep per workload and record the chosen level in the release bundle; set `max_tokens` with room for thinking at `high` and above.
- [ ] For long Claude agent loops, consider `output_config.task_budget` (beta `task-budgets-2026-03-13`, advisory, minimum 20,000 tokens) **[volatile]** with `max_tokens` as the hard cap; set the budget once, because decrementing `remaining` per request breaks the cache.
- [ ] Route offline jobs to batch with the long cache TTL for shared context; match results by `custom_id`; resubmit `expired` items.
- [ ] If using fast mode, read `usage.speed` on every response and count fast→standard fallbacks, since each one is a cache miss.
- [ ] Turn on tool search with namespaced tool names (`github_`, `slack_`), 3–5 non-deferred tools and a system-prompt line naming the tool categories; never mark the search tool itself as deferred.
- [ ] Turn on provider compaction and tool-result clearing (Anthropic `clear_tool_uses_20250919`: default trigger 100,000 input tokens, keeps the last 3 tool uses) **[volatile]**; pair with a memory file for facts that must survive summarization.
- [ ] If a router is in place: log the served model on every call, enable session affinity where offered, and change one routing lever at a time with a full eval rerun.
- [ ] If any response cache exists: key it on tenant, permission-scope hash, release bundle ID and tool versions; short TTL; purge on release and rollback; restrict exact-match caching to deterministic tool results.

## Avoid
- Timestamps or per-user data in the system prompt → put them in the latest turn (one changed byte near the top invalidates everything after it).
- Adding or removing tools per turn to save tokens → defer behind tool search or restrict with `tool_removal`/`tool_addition` blocks (Claude) or `allowed_tools` (OpenAI) (changing tool definitions invalidates the whole Anthropic cache).
- Flipping top-level effort, speed or thinking mid-session → per-message mechanisms, or hold them constant (each flip is a full or partial cache miss).
- A semantic cache in front of an agent → exact-match caches of deterministic tool results (fuzzy keys are collidable and leak across users).
- A response cache that survives a rollback → version the cache key and purge on rollback (practitioners report bad answers served after rollback; anecdotal, but cheap to prevent).
- Trusting router or effort savings measured on someone else's benchmark → measure on your own suite and traffic (savings and quality loss are workload-specific).
- Using fast mode to fix slow first tokens → caching, pre-warm, smaller prompts (fast mode raises output tokens per second, not TTFT).
- Silent fast→standard fallback → log it and expect a cache miss (requests at different speeds do not share cached prefixes).
- Hand-written summarizer loops → provider compaction (Anthropic recommends server-side compaction; its SDK client-side compaction is deprecated).
- Clearing tool results every turn → set a `clear_at_least` floor (each clear rewrites the cache).
- Running eval suites on the interactive tier → batch or flex (no user is waiting).
- Floating model aliases → dated snapshots (an alias change is an unreviewed release and resets caches).

## KV-cache-first design and self-hosting (added 2026-10-27)

- Treat the cache hit rate as a service-level metric next to latency and task success: real agent traces are 94–96% reusable prefix and agents read far more than they write, so a broken prefix is the most expensive regression an agent can ship ([vLLM](https://vllm.ai/blog/2026-09-08-vllm-agentx); [Manus](https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus)).
- Keep history append-only: never edit or reorder earlier turns. On Claude Opus 5.5 and Fable 5.1 this is enforced: replaying a thinking block after the prefix changed returns 400 on accounts created on or after 2026-08-31 **[volatile]**.
- Self-hosting (vLLM, SGLang): keep prefix caching on and set a per-tenant `cache_salt` **[volatile]** so tenants never share cached prefixes; add KV offloading (vLLM connector, SGLang HiCache, LMCache) when multi-turn KV exceeds GPU memory; with two or more replicas route by session or KV affinity (llm-d, Dynamo), which cut p90 time-to-first-token from 92.6 s to 0.54 s in llm-d's test ([llm-d](https://llm-d.ai/blog/kvcache-wins-you-can-see)). Record engine and connector versions in the stack lock.
- Do not build on latent or KV-cache communication between agents (Cache-to-Cache, KVCOMM, DroidSpeak) yet: they need white-box access to both models, are research-stage, and the channel cannot be logged or audited. See `practices-register.md`.

## Verify before relying
| Fact **[volatile]** | Snapshot (2026-10-27) | Where to check (URL) |
| --- | --- | --- |
| Anthropic caching modes | Automatic via top-level `cache_control`, or ≤ 4 explicit breakpoints; prefix order tools → system → messages | https://platform.claude.com/docs/en/build-with-claude/prompt-caching |
| Anthropic TTL and minimums | 5 min default (refreshed on use), `ttl: "1h"` option; minimum 512 tokens on most 5.x models, 1,024 on Sonnet 5, up to 4,096 on older ones | https://platform.claude.com/docs/en/build-with-claude/prompt-caching |
| Anthropic invalidation table | Tool definitions → all levels; web search, citations or speed toggle → system + messages; `tool_choice`, images → messages; thinking and effort → messages (model-specific above) | https://platform.claude.com/docs/en/build-with-claude/prompt-caching |
| Anthropic pre-warm | `max_tokens: 0`; rejected with streaming, `thinking.type: "enabled"`, forced `tool_choice`, `output_config.format`, and inside batches | https://platform.claude.com/docs/en/build-with-claude/prompt-caching |
| Cache-preserving mid-session changes | `inline-tools-2026-09-15`; `mid-conversation-output-config-2026-07-01`; OpenAI `configuration_update` (GPT-6) | https://platform.claude.com/docs/en/build-with-claude/effort · https://developers.openai.com/api/docs/guides/prompt-caching |
| OpenAI caching (GPT-5.6+) | Automatic; min 1,024 tokens; `prompt_cache_options.mode` implicit/explicit, `ttl` `"30m"`/`"12h"`, `prewarm`; overflow above ~15 req/min per prefix | https://developers.openai.com/api/docs/guides/prompt-caching |
| Gemini caching | Implicit by default on 2.5+; Gemini 4 Argon min 4,096 and full multi-turn reuse only if ≥ 2,050 new tokens; no explicit caching on 4 Argon or the Interactions API | https://ai.google.dev/gemini-api/docs/caching |
| Effort levels and defaults | `output_config.effort` low/medium/high/xhigh/max, GA; Opus 5.5 and Haiku 5.5 default `medium` | https://platform.claude.com/docs/en/build-with-claude/effort |
| Task budgets | `output_config.task_budget`, beta `task-budgets-2026-03-13`, advisory, min 20,000 | https://platform.claude.com/docs/en/build-with-claude/task-budgets |
| Fast mode | `speed: "fast"`; GA Opus 5.5; preview on Opus 5/4.8 with `fast-mode-2026-02-01`; up to 2.5x OTPS; not with Batch or Priority Tier | https://platform.claude.com/docs/en/build-with-claude/fast-mode |
| Anthropic Priority Tier | Existing commitments only; `service_tier` `"auto"`/`"standard_only"`; tier reported in `usage.service_tier` | https://platform.claude.com/docs/en/api/service-tiers |
| OpenAI flex | `service_tier: "flex"`, beta; may return 429 "Resource Unavailable" | https://developers.openai.com/api/docs/guides/flex-processing |
| Batch limits | Anthropic ≤ 100,000 requests or 256 MB, expires at 24 h, results kept 29 days; OpenAI ≤ 50,000 requests or 200 MB, `24h` window, output deleted after 30 days | https://platform.claude.com/docs/en/build-with-claude/batch-processing · https://developers.openai.com/api/docs/guides/batch |
| Tool search | Anthropic regex/BM25 `_20251119` tools, ≤ 10,000 deferred tools per request; OpenAI `tool_search` on gpt-5.4+, < 10 functions per namespace | https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-search-tool · https://developers.openai.com/api/docs/guides/tools-tool-search |
| Compaction and clearing | Anthropic compaction beta `compact-2026-09-04`; context editing `context-management-2025-06-27`, `clear_tool_uses_20250919`; OpenAI `compact_threshold`, `/responses/compact` | https://platform.claude.com/docs/en/build-with-claude/compaction · https://platform.claude.com/docs/en/build-with-claude/context-editing · https://developers.openai.com/api/docs/guides/compaction |
| Azure model router | Trained router (not an LLM); Balanced default, Cost, Quality; session affinity preview, 30-minute expiry | https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/model-router-how-it-works |
| CacheAttack status | arXiv v2 2026-06-30; listed as accepted to ICML 2026 | https://arxiv.org/abs/2601.23088 |

## Sources
- [Prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching) — Anthropic, n.d. (accessed 2026-10-27)
- [Effort](https://platform.claude.com/docs/en/build-with-claude/effort) — Anthropic, n.d. (accessed 2026-10-27)
- [Task budgets](https://platform.claude.com/docs/en/build-with-claude/task-budgets) — Anthropic, n.d. (accessed 2026-10-27)
- [Fast mode](https://platform.claude.com/docs/en/build-with-claude/fast-mode) — Anthropic, n.d. (accessed 2026-10-27)
- [Service tiers](https://platform.claude.com/docs/en/api/service-tiers) — Anthropic, n.d. (accessed 2026-10-27)
- [Batch processing](https://platform.claude.com/docs/en/build-with-claude/batch-processing) — Anthropic, n.d. (accessed 2026-10-27)
- [Tool search tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-search-tool) — Anthropic, n.d. (accessed 2026-10-27)
- [Compaction overview](https://platform.claude.com/docs/en/build-with-claude/compaction) — Anthropic, n.d. (accessed 2026-10-27)
- [Context editing](https://platform.claude.com/docs/en/build-with-claude/context-editing) — Anthropic, n.d. (accessed 2026-10-27)
- [Prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching) — OpenAI, n.d. (accessed 2026-10-27)
- [Flex processing](https://developers.openai.com/api/docs/guides/flex-processing) — OpenAI, n.d. (accessed 2026-10-27)
- [Batch API](https://developers.openai.com/api/docs/guides/batch) — OpenAI, n.d. (accessed 2026-10-27)
- [Tool search](https://developers.openai.com/api/docs/guides/tools-tool-search) — OpenAI, n.d. (accessed 2026-10-27)
- [Compaction](https://developers.openai.com/api/docs/guides/compaction) — OpenAI, n.d. (accessed 2026-10-27)
- [Context caching](https://ai.google.dev/gemini-api/docs/caching) — Google, updated 2026-10-23
- [How model router works](https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/model-router-how-it-works) — Microsoft Learn, updated 2026-10-19
- [From Similarity to Vulnerability: Key Collision Attack on LLM Semantic Caching (CacheAttack)](https://arxiv.org/abs/2601.23088) — Zhang et al., arXiv, v1 2026-01-30, v2 2026-06-30
- [RouteLLM: Learning to Route LLMs with Preference Data](https://arxiv.org/abs/2406.18665) — Ong et al., arXiv, v4 2025-02-23
