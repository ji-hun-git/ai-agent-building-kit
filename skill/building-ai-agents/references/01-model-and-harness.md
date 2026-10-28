# 01 · Model and harness

> Snapshot verified 2026-10-27. Items tagged **[volatile]** change often — re-check them with the freshness protocol in SKILL.md before relying on them.

## Default
Start on your primary vendor's recommended general model, set reasoning effort explicitly, and route high-volume or sub-agent steps to the same vendor's small tier at low effort; move a step to the top tier only when evals at higher effort on the general model still fail. At this snapshot the general models are Claude Opus 5.5 **[volatile]**, GPT-6 Astra **[volatile]** and Gemini 4 Argon **[volatile]** (or Gemini 3.8 Flash **[volatile]** for speed), and the small tiers are Claude Haiku 5.5 **[volatile]**, GPT-6 Luna **[volatile]** and Gemini 3.5 Flash-Lite **[volatile]**. Every vendor now steers reasoning with a named effort level instead of a thinking-token budget, and defaults are recalibrated between model versions, so sweep effort on your own evals after every model change. Constrain every machine-consumed output with JSON-schema structured outputs and strict tool schemas, and still validate it, because refusals and truncation escape the constraint. Build on your primary vendor's agent harness (or LangGraph when you need provider-neutral durable graphs) instead of a hand-rolled loop, and pin model IDs and SDK versions exactly.

## Decide
- If you have no eval data yet → start on the vendor's stated default (Anthropic recommends Claude Opus 5.5 **[volatile]** for most workloads; OpenAI points new projects to GPT-6 Astra **[volatile]**), because vendor docs, default effort and examples are tuned around that model.
- If a step is classification, extraction, routing, short summarization or a scoped sub-agent task → the small tier (Claude Haiku 5.5 **[volatile]**, GPT-6 Luna **[volatile]**, Gemini 3.5 Flash-Lite **[volatile]**) at `low` effort, because Anthropic names `low` as the level for sub-agents and both Anthropic and OpenAI position their small tier for high-volume, clearly defined work.
- If the general model still fails your evals at its highest useful effort on long-horizon or hard reasoning → Claude Fable 5.1 **[volatile]**, or GPT-6 Astra **[volatile]** at `xhigh`/`max`, because Anthropic positions Fable 5.1 for exactly that case and the top tier is slower.
- If you call Claude directly → set `output_config.effort` **[volatile]** on every request and agent config, because defaults differ per model (`medium` on Opus 5.5 and Haiku 5.5, `high` on Fable 5.1 and Sonnet 5.5 **[volatile]**) and effort also changes how many tool calls the model makes.
- If you need less thinking on Claude → lower effort first; Opus 5.5 thinking cannot be disabled, and on Sonnet 5.5 send `thinking: {"type": "between_tools"}` **[volatile]** instead of `"disabled"`, because `"disabled"` returns 400 on those models.
- If effort must change mid-conversation and you rely on prompt caching → per-message effort (beta header `mid-conversation-output-config-2026-07-01` **[volatile]**), because changing top-level effort between requests invalidates the cached prefix.
- If code parses the output → schema-constrained output (Claude `output_config.format` **[volatile]** with `type: "json_schema"`; OpenAI Responses `text.format` **[volatile]** with `strict: true` **[volatile]**; Gemini `response_format` **[volatile]** with a `schema`) plus strict tool definitions, because JSON mode and prompt-only formatting do not enforce the schema.
- If the schema needs recursion, numeric or length constraints, or many unions → simplify it and validate the rest in code, because Claude rejects unsupported schema keywords with 400 and Gemini silently ignores some (e.g. `minLength`/`maxLength`).
- If residency, licensing or offline operation requires self-hosting → shortlist open-weight models from a current leaderboard (snapshot leaders include MiMo-V2.6-Pro, Qwen3.8 Max, GLM-5.3, DeepSeek V4.1 Flash **[volatile]**), then check each license and run your own evals, because ranks are noisy, partly estimated and say nothing about license or hosting fit.
- If Claude is the primary model → Claude Agent SDK to embed Claude Code's loop (tools, hooks, sub-agents, MCP, permissions, sessions, skills) in a process you run; Claude Managed Agents (beta header `managed-agents-2026-04-01` **[volatile]**) for an Anthropic-hosted loop and sandbox; the client SDK's tool runner only to write your own loop, because each step down means rebuilding compaction, sub-agents and permissions yourself.
- If the agent is customer- or employee-facing and needs none of the Claude Agent SDK's built-in file, shell or web tools → either use the Agent SDK with an explicit allow-list that removes them (`allowedTools` **[volatile]**) or use the client SDK tool runner; choose by whether you need the SDK's compaction, sub-agents, hooks and permissions, and write the choice in the decisions log, because shipping unused shell and file tools enlarges the attack surface for no gain.
- If another vendor or several vendors → OpenAI Agents SDK (handoffs, guardrails, sandbox agents, sessions, tracing) for OpenAI-first stacks; Google ADK 2.x **[volatile]** for Google Cloud or Go/Java/Kotlin teams; Microsoft Agent Framework for .NET/Azure shops (its Harness Agent bundles planning, compaction, file access and memory); LangGraph 1.x **[volatile]** with Deep Agents as the harness for provider-neutral durable execution and explicit graphs, because each ships the harness pieces natively for that ecosystem.
- If the flow is a fixed one- or two-call path with tight latency → call the client SDK directly (a workflow, not an agent), because a harness adds loop overhead and abstractions that hide the prompts you need to debug.

## Build checklist
- [ ] Record model IDs, effort per step, thinking mode, SDK versions and API version in the project's stack lock (`templates/stack-lock.md`).
- [ ] Use exact model IDs; Claude IDs from the 4.6 generation on are dateless pinned snapshots **[volatile]**, but confirm each vendor's alias-versus-snapshot rules before calling an ID "pinned".
- [ ] Pin the API version your client sends (`anthropic-version` **[volatile]** for Claude); Anthropic's release notes say new SDKs default to `2026-10-21` **[volatile]**.
- [ ] Pin SDK versions exactly (no `^`, `~` or `latest`); the Claude Agent SDK (Python 0.2.x, TypeScript 0.3.x **[volatile]**) and OpenAI Agents SDK (Python 0.24, JS 0.21 **[volatile]**) are pre-1.0 with near-daily releases.
- [ ] Run an effort sweep (`low` → `max`) on the eval suite for each model and step; keep the lowest level that meets the bar and store the result next to the model ID.
- [ ] At `high` effort and above set a large `max_tokens` **[volatile]**, since it caps thinking plus reply; Anthropic suggests `xhigh` for agentic or coding runs over about 30 minutes.
- [ ] Remove `thinking.type: "enabled"` + `budget_tokens` **[volatile]** from Claude requests; models after the 4.6 generation reject them.
- [ ] Gemini: resend thought signatures verbatim in stateless mode (also when switching models), or use stateful mode (`store: true` + `previous_interaction_id` **[volatile]**).
- [ ] Define a JSON Schema for every machine-consumed output and enable strict tools; on Claude set `additionalProperties: false` on every object. Shape:
  ```json
  {"output_config": {"format": {"type": "json_schema", "schema": {"type": "object",
     "properties": {"name": {"type": "string"}}, "required": ["name"], "additionalProperties": false}}},
   "tools": [{"name": "search_flights", "strict": true, "input_schema": {"...": "..."}}]}
  ```
- [ ] Test the refusal (`stop_reason: "refusal"` **[volatile]**), `max_tokens` truncation and enum-casing paths; output can break the schema in all three.
- [ ] Keep Claude strict requests within limits (20 strict tools, 24 optional params, 16 union-typed params per request **[volatile]**).
- [ ] Put the model call behind a thin adapter keyed by step, so moving a step to another tier or vendor is a config change plus an eval run.
- [ ] Write the harness choice, the rejected alternative and the reason into the decisions log; check ZDR/HIPAA eligibility of any hosted harness first (Managed Agents is not currently eligible).
- [ ] Start the harness with the minimum tool set and a permission mode that asks before writes; widen only with evals (see `04-tools-and-actions.md`, `07-security.md`).
- [ ] For open-weight models, record license, weights revision and serving-stack version in the lock.
- [ ] Add a CI check that fails when a model ID, effort level or SDK version changes without a passing eval run (see `10-evals-and-release.md`).

## Avoid
- Carrying effort settings over from an earlier model → re-sweep on the new one (levels are recalibrated; Claude Opus 5.5 **[volatile]** defaults one level lower than Claude Opus 5 **[volatile]**).
- Thinking-token budgets → named effort levels (Claude rejects `budget_tokens` **[volatile]** on newer models; Google documents only `thinking_level` **[volatile]**).
- JSON mode or "reply in JSON" instructions → schema-constrained outputs (only constrained decoding guarantees the shape).
- Treating constrained output as always valid → validate and handle refusal and truncation (the guarantee excludes them).
- The top tier for every step → general model plus small-tier routing (use the top tier only where evals prove a gain; latency and token use rise sharply).
- A hand-rolled `while` loop for a general-purpose agent → a vendor harness (you would rebuild compaction, sub-agents, permissions and sessions).
- A framework whose calls you have not read → inspect the prompts and requests it sends (abstraction layers hide the cause of failures).
- Picking an open-weight model by leaderboard rank → shortlist, license check, own evals (adjacent ranks are not separable).
- Floating versions → exact pins and upgrade PRs gated by evals (0.x SDKs change behaviour between minor releases).
- Committing to a hosted harness before checking data-retention terms → check eligibility first (late rework costs most).

## Verify before relying
| Fact **[volatile]** | Snapshot (2026-10-27) | Where to check (URL) |
| --- | --- | --- |
| Claude lineup and IDs | Fable 5.1 `claude-fable-5-1`, Opus 5.5 `claude-opus-5-5`, Sonnet 5.5 `claude-sonnet-5-5`, Haiku 5.5 `claude-haiku-5-5`; 1M context, 128K max output; dateless IDs are pinned snapshots | https://platform.claude.com/docs/en/about-claude/models/overview |
| Tool calling on OpenAI's current models | Through the Responses API: GPT-6 Astra calls tools only there; from GPT-5.4 on, Chat Completions calls tools only at reasoning effort `none` (checked 2026-10-28) | https://developers.openai.com/api/docs/guides/migrate-to-responses |
| Reasoning replay | Send each assistant turn back unchanged: Claude thinking blocks (bound to the conversation; edited history is rejected on accounts created from 2026-08-31) and OpenAI reasoning items (with `include: ["reasoning.encrypted_content"]` when `store=false`) (checked 2026-10-28) | https://platform.claude.com/docs/en/api/migration-2026-10-21 |
| Claude default-model guidance | Opus 5.5 for most work; Fable 5.1 when Opus 5.5 at higher effort falls short; Haiku 5.5 for classification, extraction, routing | https://platform.claude.com/docs/en/about-claude/models/overview |
| Claude release dates | Fable 5.1 2026-09-01; Opus 5.5 2026-09-22; Sonnet 5.5 2026-09-28; Haiku 5.5 2026-10-07 | https://platform.claude.com/docs/en/release-notes/overview |
| `output_config.effort` | GA; `low`/`medium`/`high`/`xhigh`/`max`; default `medium` on Opus 5.5 and Haiku 5.5, `high` on Fable 5.1, Sonnet 5.5 and Opus 5; `low` for sub-agents; `xhigh` for runs over 30 min; large `max_tokens` at `high` and above | https://platform.claude.com/docs/en/build-with-claude/effort |
| Claude thinking controls | Opus 5.5 thinking always on; Sonnet 5.5 `thinking: {"type": "between_tools"}`; `budget_tokens` not accepted after the 4.6 generation | https://platform.claude.com/docs/en/build-with-claude/effort |
| Per-message effort | Beta header `mid-conversation-output-config-2026-07-01`; preserves prompt cache | https://platform.claude.com/docs/en/build-with-claude/effort |
| Claude structured outputs | GA, no beta header; `output_config.format` + `json_schema`; `strict: true` tools; 20 / 24 / 16 limits; `stop_reason: "refusal"` and `max_tokens` truncation can break the schema | https://platform.claude.com/docs/en/build-with-claude/structured-outputs |
| Claude API version | `anthropic-version`; new SDKs default to `2026-10-21` | https://platform.claude.com/docs/en/release-notes/overview |
| OpenAI lineup | `gpt-6-astra`, `gpt-6.1-sol`, `gpt-6.1-terra`, `gpt-6-luna`; Astra/Sol effort `low`…`max`, Terra/Luna add `none` | https://developers.openai.com/api/docs/models |
| OpenAI release dates | GPT-6 Astra 2026-09-03; GPT-6 Sol and Luna 2026-09-22 (6.1 dates unconfirmed) | https://techcrunch.com/2026/09/22/openai-launches-gpt-6-sol-and-luna/ |
| OpenAI structured outputs | Responses `text.format` `{type: "json_schema", strict: true}`; JSON mode not schema-enforcing | https://developers.openai.com/api/docs/guides/structured-outputs |
| Gemini lineup | `gemini-4-argon`, `gemini-3.8-flash`, `gemini-3.5-flash-lite` stable; `gemini-3.1-pro-preview` | https://ai.google.dev/gemini-api/docs/models |
| Gemini thinking | `thinking_level`; defaults Argon `medium`, 3.8 Flash `medium`, Flash-Lite `minimal`; thought signatures; `store: true` + `previous_interaction_id` | https://ai.google.dev/gemini-api/docs/thinking |
| Gemini structured output | `response_format` with `mime_type: "application/json"` and `schema`; some keywords ignored | https://ai.google.dev/gemini-api/docs/structured-output |
| Open-weight leaders | MiMo-V2.6-Pro, Qwen3.8 Max, Step 5 Preview, GLM-5.3, Ling 3.1 Flash, DeepSeek V4.1 Flash 1017 (several scores estimated) | https://benchlm.ai/best/open-source |
| SDK versions | claude-agent-sdk Py 0.2.174 / TS 0.3.311; openai-agents 0.24.0 / @openai/agents 0.21.0; google-adk 2.13.0; agent-framework Py 1.23.0 / .NET 1.26.0; langgraph 1.2.18 | `scripts/check_freshness.py`; GitHub release pages in Sources |
| Managed Agents | Beta header `managed-agents-2026-04-01`; not ZDR- or HIPAA-BAA-eligible | https://platform.claude.com/docs/en/managed-agents/overview |
| ADK and MAF status | ADK 2.x graph workflows, TypeScript 2.0 GA; MAF Harness Agent, Go preview, .NET quickstart still `--prerelease` | https://adk.dev/ ; https://learn.microsoft.com/en-us/agent-framework/overview/ |
| LangGraph | 1.x; Deep Agents harness on top | https://docs.langchain.com/oss/python/langgraph/overview |

## Sources
- [Models overview](https://platform.claude.com/docs/en/about-claude/models/overview) — Anthropic, no date shown, accessed 2026-10-27
- [Effort](https://platform.claude.com/docs/en/build-with-claude/effort) — Anthropic, no date shown, accessed 2026-10-27
- [Structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) — Anthropic, no date shown, accessed 2026-10-27
- [Claude Developer Platform release notes](https://platform.claude.com/docs/en/release-notes/overview) — Anthropic, entries through 2026-10-23
- [Agent SDK overview](https://code.claude.com/docs/en/agent-sdk/overview) — Anthropic, no date shown, accessed 2026-10-27
- [Managed Agents overview](https://platform.claude.com/docs/en/managed-agents/overview) — Anthropic, no date shown, accessed 2026-10-27
- [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents) — Anthropic Engineering, 2024-12-19
- [Models](https://developers.openai.com/api/docs/models) — OpenAI developer docs, no date shown, accessed 2026-10-27
- [Structured Outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs) — OpenAI developer docs, accessed 2026-10-27
- [OpenAI launches GPT-6 Sol and Luna](https://techcrunch.com/2026/09/22/openai-launches-gpt-6-sol-and-luna/) — TechCrunch, 2026-09-22
- [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/) — OpenAI, no date shown, accessed 2026-10-27
- [Gemini models](https://ai.google.dev/gemini-api/docs/models) — Google AI for Developers, updated 2026-10-22
- [Thinking](https://ai.google.dev/gemini-api/docs/thinking) — Google AI for Developers, updated 2026-10-14
- [Structured output](https://ai.google.dev/gemini-api/docs/structured-output) — Google AI for Developers, updated 2026-10-21
- [Agent Development Kit docs](https://adk.dev/) — Google, no date shown, accessed 2026-10-27
- [Agent Framework overview](https://learn.microsoft.com/en-us/agent-framework/overview/) — Microsoft Learn, 2026-10-23
- [LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview) — LangChain, no date shown, accessed 2026-10-27
- [Open-source LLM leaderboard](https://benchlm.ai/best/open-source) — BenchLM, updated 2026-10-26
- GitHub release pages, queried 2026-10-27: [claude-agent-sdk-python](https://github.com/anthropics/claude-agent-sdk-python/releases), [claude-agent-sdk-typescript](https://github.com/anthropics/claude-agent-sdk-typescript/releases), [openai-agents-python](https://github.com/openai/openai-agents-python/releases), [openai-agents-js](https://github.com/openai/openai-agents-js/releases), [adk-python](https://github.com/google/adk-python/releases), [langgraph](https://github.com/langchain-ai/langgraph/releases), [agent-framework](https://github.com/microsoft/agent-framework/releases) — GitHub
