# Practices register: adopt, adopt-when, watch, skip

> Snapshot verified 2026-10-27. Items tagged **[volatile]** change often — re-check them with the freshness protocol in SKILL.md before relying on them.

## Default

This register records techniques and practitioner workflows that were reviewed for this skill and how each was judged: **ADOPT** (a rule for every agent), **ADOPT-WHEN** (only under the stated condition), **WATCH** (promising, not ready) or **SKIP** (out of scope or not supported by evidence). The adopted rules are also written into the layer files named in the last column; this file keeps the reasoning and sources in one place so later reviews do not re-litigate them. When a WATCH item ships in a mainstream serving engine or SDK, re-review it.

## Context and KV cache (Manus lessons, self-hosting, Cache-to-Cache)

| Technique | Verdict | Condition or reason | Evidence | Applied in |
| --- | --- | --- | --- | --- |
| KV-cache-first context design: stable prefix, append-only history, deterministic serialization, hit rate as a key metric | ADOPT | Works on every hosted API | Real agent traces are 94–96% reusable prefix; Manus reports input:output near 100:1 ([Manus](https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus), 2025-07-18; [vLLM](https://vllm.ai/blog/2026-09-08-vllm-agentx), 2026-09-08) | 02, 08 |
| Mask or restrict tools through the API instead of editing the tool list | ADOPT | Claude `tool_removal` / `tool_addition` blocks **[volatile]**; OpenAI `allowed_tools` **[volatile]**; logit masking only when self-hosting | Opus 5.5 and Fable 5.1 return 400 for `tool_choice` any/tool **[volatile]** ([Claude docs](https://platform.claude.com/docs/en/build-with-claude/mid-conversation-system-messages)) | 04, 08 |
| Restorable compression; keep failed actions in context | ADOPT | Drop only what can be fetched again and keep its path or URL; errors teach the model what not to retry | Manus lessons | 02, 05 |
| Recitation (rewriting a todo list) and varied templates against few-shot ruts | ADOPT-WHEN | Long single loops (recitation); batches of similar items (variation). Recitation costs tokens | ~50 tool calls per task in Manus; overhead figure is secondary ([summary](https://philschmid.de/context-engineering-part-2)) | 02 |
| Prefix caching (vLLM) / RadixAttention (SGLang) with per-tenant `cache_salt` **[volatile]** | ADOPT-WHEN self-hosting | On by default; salt separates tenants | <1% overhead at 0% hit rate ([vLLM](https://docs.vllm.ai/en/latest/design/prefix_caching.html)) | 08 |
| KV offloading (vLLM connector, SGLang HiCache, LMCache) | ADOPT-WHEN self-hosting with multi-turn KV larger than GPU memory | Documented, Apache-2.0 | >2× throughput past 128 conversations; HiCache TTFT −56% on a coding agent ([vLLM](https://vllm.ai/blog/2026-09-10-tiered-kv-offloading); [LMSYS](https://lmsys.org/blog/2025-09-10-sglang-hicache)) | 08 |
| KV-aware / session-affinity routing (llm-d v1.0.0 **[volatile]**, Dynamo) | ADOPT-WHEN self-hosting ≥ 2 replicas | Production releases | p90 TTFT 0.54 s vs 92.6 s with random routing ([llm-d](https://llm-d.ai/blog/kvcache-wins-you-can-see)) | 08 |
| Mooncake distributed KV pool; Continuum KV-TTL; CacheBlend | WATCH | Release status unclear or quality must be re-evaluated | Vendor/research figures only | — |
| DroidSpeak; KVCOMM (KV reuse across agents) | WATCH | Same-architecture only, code not public or unlicensed, no serving-engine integration | NSDI'26 / arXiv 2510.12872 | — |
| **Cache-to-Cache (C2C)**: models communicate by projecting KV caches instead of text | WATCH for self-hosting researchers; SKIP for hosted-API builders | Needs white-box KV access to both models and a fuser trained per model pair; tested on 0.5–14B models and QA benchmarks; the latent channel cannot be audited or logged as text | ICLR'26: +6.4–14.2% vs single models, +3.1–5.4% vs text communication, ~2.5× faster ([arXiv 2510.03215](https://arxiv.org/abs/2510.03215), v2 2026-03-02) | — |
| LatentMAS; mixture-of-thought KV translation | WATCH | Same-architecture, little or no code | arXiv 2511.20639; 2607.28979 | — |

## Karpathy's workflow

| Idea | Verdict | Rule | Source | Applied in |
| --- | --- | --- | --- | --- |
| Make human checking fast | ADOPT | At every human checkpoint show the diff, the highlighted change or the source passage, not a wall of text | [Software 3.0 talk](https://www.youtube.com/watch?v=LCEmiRjPEtQ), Jun 2025 | agent-ux-design |
| Keep the AI on a leash | ADOPT | Make each agent increment no bigger than its reviewer can check in one pass; split anything larger | talk; [X post](https://x.com/karpathy/status/2015883857489522876) | architecture-patterns |
| Autonomy slider tied to scope | ADOPT | Define autonomy levels by how much they change (suggest → edit selection → edit artifact → multi-step run); start at the lowest that works; raise only on logged acceptance and reversion rates | talk; [Dwarkesh](https://www.dwarkesh.com/p/andrej-karpathy) | agent-ux-design |
| Give goals, not steps | ADOPT | Brief agents with success criteria and a runnable check (tests first); naive correct version before optimising | X post above | architecture-patterns, 02 |
| Context fails in both directions | ADOPT | Check each context item for too little or wrong form, and for too much or irrelevant | [X post](https://x.com/karpathy/status/1937902205765607626), Jun 2025 | 02 |
| March of nines | ADOPT | Set a reliability target in nines per task class; a demo is not evidence | Dwarkesh | 10 |
| Coding-agent failure modes | ADOPT | Eval cases where the right move is to ask, push back or flag an inconsistency; review diffs for unrequested edits, dead code, bloat | X post above | failure-modes, 10 |
| Evaluator the agent cannot change (autoresearch) | ADOPT-WHEN a cheap objective metric exists | Unattended loops only against a read-only evaluator, fixed budget per trial, git keep/discard per trial, append-only log, several metrics, in a sandbox | [autoresearch](https://github.com/karpathy/autoresearch) | architecture-patterns |
| Systems agents can operate without a GUI | ADOPT-WHEN you own the systems | Give every system an API, CLI or MCP path and Markdown docs with commands, not click-paths | [Sequoia Ascent 2026](https://karpathy.bearblog.dev/sequoia-ascent-2026/) | 04 |
| Less autonomy for novel code | ADOPT-WHEN work is off-distribution | Lower autonomy; verify against a reference implementation | [X post](https://x.com/karpathy/status/1977758204139331904) | architecture-patterns |
| Plausible-but-wrong joins | ADOPT-WHEN coding agents write the agent's code | Join identity and money on stable IDs, never on email | Sequoia Ascent 2026 | failure-modes |
| LLM Council (independent answers, anonymised peer ranking, chairman synthesis) | ADOPT-WHEN offline, high-value, no ground truth, every vendor approved for the data; SKIP on the live answer path | First beat a best-single-model self-consistency baseline; anonymise and shuffle; drop self-ranking; calibrate on human labels; ~2N+1 calls in 3 sequential rounds | [llm-council](https://github.com/karpathy/llm-council); Karpathy measured no quality gain; [Princeton](https://arxiv.org/abs/2502.00674): repeated best-model sampling often beats mixing models; [NeurIPS'25](https://arxiv.org/abs/2508.17536): voting explains most debate gains | architecture-patterns |
| llms.txt | WATCH | Publish for public docs if cheap; a proposal, not a control | [llmstxt.org](https://llmstxt.org) | — |
| LLM Wiki (compiled knowledge base) | WATCH | Only for a corpus with one permission scope; raw sources immutable and cited; writes reviewed | [gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) | — |
| Personal tool-split ratios; hiring test; framing metaphors | SKIP | Ratios flipped within months; out of scope | — | — |

## Other practitioner frameworks

| Practice | Verdict | Rule | Source | Applied in |
| --- | --- | --- | --- | --- |
| Durable-execution engine | ADOPT-WHEN a run must survive deploys or crashes, or wait hours to days for a person | Run the loop on Temporal, Restate, DBOS, Lambda durable functions or Agent Framework Durable Extension **[volatile]**, each model and tool call a checkpointed step; keep idempotency keys | [Temporal + OpenAI Agents SDK](https://temporal.io/blog/announcing-openai-agents-sdk-integration) (GA 2026-03-23); [Pydantic AI](https://pydantic.dev/docs/ai/integrations/durable_execution/overview/) | architecture-patterns |
| Session log as single source of truth; stateless harness | ADOPT-WHEN you host the loop | One append-only event log per session outside the harness; resume, fork, replay, render from it; sandboxes provisioned lazily with no credentials | [Anthropic Managed Agents](https://www.anthropic.com/engineering/managed-agents) (2026-04-08); 12-Factor factor 5 | architecture-patterns |
| Contact humans with a tool call | ADOPT-WHEN headless or event-driven | A structured `request_human_input` tool that saves state, ends the run and resumes on the reply event | [12-Factor Agents](https://github.com/humanlayer/12-factor-agents) factor 7 | architecture-patterns |
| Triggers and reply channels | ADOPT-WHEN non-chat triggers exist | List every trigger (Slack, email, webhook, cron) with its run-as identity, whether its payload is untrusted, and where replies go | 12-Factor factor 11 | templates/agent-spec, 07 |
| Eval task hygiene | ADOPT | Each task has a reference solution and a paired should-not-act case; 0% over k trials means a broken task; add harder tasks when a suite saturates | [Anthropic](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) (2026-01-09) | 10 |
| Error analysis first | ADOPT | Open-code real traces into a failure taxonomy before writing judges; one binary evaluator per frequent failure; record the first failing step | [Hamel Husain](https://hamel.dev/blog/posts/evals-faq/) (2026-09-18) | 10 |
| Infrastructure noise | ADOPT | Record sandbox CPU/RAM and kill limits in the bundle; count infra errors separately; treat gaps under ~3 points as noise | [Anthropic](https://www.anthropic.com/engineering/infrastructure-noise) (2026-02-05) | 10 |
| Eval awareness | ADOPT-WHEN eval agents can search the web | Block benchmark names and answer sources; flag transcripts that hunt for the answer key | [Anthropic](https://www.anthropic.com/engineering/eval-awareness-browsecomp) (2026-03-06) | 10 |
| Agent-shaped test output | ADOPT | A few summary lines, logs to files, grep-able error tags, a deterministic fast mode; a near-complete verifier | [Anthropic](https://www.anthropic.com/engineering/building-c-compiler) (2026-02-05) | architecture-patterns |
| Ralph reset loop | ADOPT-WHEN unattended, auto-verifiable and sandboxed | Same prompt, fresh context, one item per iteration, state in files and git, tests as backpressure, iteration cap | [ghuntley.com/ralph](https://ghuntley.com/ralph/) (2025-07-14) | architecture-patterns |
| AGENTS.md as a map | ADOPT | ~100 lines as a table of contents into a versioned docs/ tree; links and freshness checked in CI | [OpenAI harness engineering](https://openai.com/index/harness-engineering/) (2026-02-11) | 02 |
| CLI before MCP | ADOPT-WHEN a sandboxed shell already exists | Give the agent a mature CLI plus one usage example before building an MCP server | [Willison](https://simonwillison.net/2025/Sep/30/designing-agentic-loops/) | 04 |
| Spec Kit / Kiro specs | ADOPT-WHEN the team builds through one of them | Feed `agent-spec.md` and the eval plan in as the tool's spec instead of writing a second one | [Spec Kit](https://github.com/github/spec-kit) v1.2.3 **[volatile]**; [Kiro](https://kiro.dev/docs/specs/) | SKILL Step 1 |
| Agent Client Protocol | ADOPT-WHEN shipping a coding agent for editors | Expose it over ACP and list it in the ACP Registry | [Zed](https://zed.dev/blog/acp-registry) (2026-01-28) | 04 |
| AP2 / Agentic Commerce Protocol | ADOPT-WHEN the agent buys or pays | Signed mandates or shared payment tokens; the agent never holds card credentials | [ap2-protocol.org](https://ap2-protocol.org); [agenticcommerce.dev](https://agenticcommerce.dev) | 06, 04 |
| Parallel writer agents coordinating through lock files | WATCH | One experiment, regressions reported; conflicts with the single-writer rule | — | — |
| Research-plan-implement with a 40–60% context target | WATCH | Single-source practice | HumanLayer | — |
| 12-Factor "stateless reducer"; agentic-coding pattern guides | SKIP | Author calls the first mostly for fun; the second is about writing code with agents, not building them | — | — |

## Verify before relying

| Fact **[volatile]** | Snapshot (2026-10-27) | Where to check (URL) |
| --- | --- | --- |
| Claude tool restriction mechanism on Opus 5.5 / Fable 5.1 | `tool_removal` / `tool_addition` blocks; `tool_choice` any/tool returns 400 | https://platform.claude.com/docs/en/build-with-claude/mid-conversation-system-messages |
| Claude append-only enforcement | Replaying a thinking block after a prefix change returns 400 on accounts created on or after 2026-08-31 | https://platform.claude.com/docs/en/build-with-claude/mid-conversation-system-messages |
| C2C status | Research code; no serving-engine integration found | https://arxiv.org/abs/2510.03215 |
| llm-d release | v1.0.0 (2026-10-20) | https://llm-d.ai |
| Temporal × OpenAI Agents SDK | Python integration GA 2026-03-23 | https://temporal.io/blog/announcing-openai-agents-sdk-integration |
| Spec Kit version | v1.2.3 (2026-10-22) | https://github.com/github/spec-kit |

## Sources

Full research notes with publisher and access date for every source: the "Additions 2026-10-27" notes shipped with this skill's kit (`kv_cache_c2c.md`, `karpathy_workflow.md`, `other_practices.md`).
