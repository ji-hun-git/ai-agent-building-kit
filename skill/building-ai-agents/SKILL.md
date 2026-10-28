---
name: building-ai-agents
description: Design, build, review or upgrade AI agents and LLM applications on a verified, current reference stack — model and SDK choice, context engineering, retrieval (RAG), MCP tools and A2A, memory, user-delegated authorization, prompt-injection security, agent UX, cost, observability, evals and release gates. Use this skill whenever the user wants to build, architect, plan, review, harden or modernize an AI agent, assistant, copilot, chatbot with tools, RAG system, MCP server, multi-agent system or agent eval pipeline, or asks which model, SDK or method is current — even if they never say "agent" (also for requests in Korean such as "AI 에이전트 만들어줘", "챗봇 설계", "RAG 구축"). It starts with a live freshness check, so model names, SDK versions and spec versions are verified on the web instead of trusted from memory.
---

# Building AI agents

A reference stack for enterprise-grade agents, snapshot verified **2026-10-27**, plus a workflow that keeps it current. The agent ecosystem changes monthly: in 2026 alone MCP went stateless, every major vendor shipped a new model family, and prompt injection was shown to beat every published detector. Your training data and this snapshot are both aging the moment you read them. So the first job is always to check what is current, and the second is to build in an order where each layer closes a known failure.

## How to use this skill

Match the request to a path, then follow it. Read reference files only when the step needs them; each is self-contained.

| Request | Path |
| --- | --- |
| Build or design a new agent | Steps 0 → 7 below |
| Review or harden an existing agent | Step 0, then the audit in `references/failure-modes.md` |
| "Which model / SDK / method should I use?" | Step 0, then the relevant layer file |
| Add one capability (RAG, tools, evals, auth…) | Step 0, then that layer file + its row in the non-negotiables |

**Size the output to the ask.** The full workflow (spec, eval plan, threat model, stack lock) is for design and build requests. A quick question gets a quick answer: the recommendation, the two or three reasons that decide it, the check date with source links, and the one risk to watch, in about 300 words unless the user asks for more. Run the freshness check either way, but put its results in a line ("verified 2026-10-27: …") rather than a separate file. For design documents, lead with the decisions and put long tables, eval cases and threat analysis in their own files, so the reader can see the design in one sitting.

## Step 0 · Freshness check (always first)

Facts tagged **[volatile]** anywhere in this skill — model names, SDK versions, spec revisions, API parameter names, beta flags, benchmark figures — are hypotheses until you confirm them today.

1. **Run the version check.** From this skill's folder: `python scripts/check_freshness.py` (add `--no-models` if the user has not agreed to you using their API keys). It reports the latest release of each agent SDK and protocol package, the current MCP, A2A and OTel GenAI spec releases, and the model IDs each vendor serves when `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` or `GEMINI_API_KEY` is set. It diffs everything against `references/snapshot.json`. Anything marked `changed` needs its changelog read before you rely on this skill's default for it.
2. **Search the web for what a script cannot see.** At minimum:
   - each candidate vendor's current model lineup and recommended default (vendor models pages and release notes);
   - the vendor's deprecation and retirement pages for every model the project uses or would fall back to (models are shut down on fixed dates, and the obvious fallback is often retiring too);
   - "<SDK name> changelog" for every SDK the script flagged as changed;
   - known advisories for every pinned or proposed version: `python scripts/check_freshness.py --no-models --audit mcp==2.3.0 npm:@openai/agents@0.21.0 …` queries the OSV database. OSV misses advisories filed only on a project's own GitHub repository, so also open the Security → Advisories page of the MCP SDK and agent SDK repositories you pin. Cite an advisory ID only from that output or an advisory page you opened, because invented or mistyped IDs are easy to produce and hard for readers to catch;
   - new methods for the layers this project touches, e.g. "RAG retrieval state of the art <current year>", "prompt injection defense <current year>", "agent evaluation <current year>", "MCP specification changelog".
   Open the pages you rely on; a search snippet is not a source. Prefer vendor docs, changelogs, specs and papers over blog summaries.
3. **Record it.** Copy `templates/stack-lock.md` into the project (e.g. `docs/agent-stack-lock.md`) and fill it: date, versions, model IDs, sources, and every place where today's finding overrides this skill. Later steps cite the lock, not your memory.
4. **When a newer method replaces a default here**, follow the newer one and say so to the user with the source. If the user maintains this skill, offer to update the affected reference file and its verified date.
5. **No web access?** Say so plainly, use the snapshot, and mark the lock file "unverified" so nobody mistakes it for a checked stack.

## Step 1 · Frame the job

Fill `templates/agent-spec.md` with the user before writing code. The sections that change the design most:

- **Jobs and examples.** Five real tasks with real inputs. Vague jobs produce vague agents and unmeasurable evals.
- **Data.** Each source, its owner, sensitivity, and how access is decided today. This decides retrieval and authorization.
- **Actions.** Every system the agent may change, classified read / reversible write / irreversible. This decides approvals, idempotency and the threat model.
- **Risk tier.** Low (internal, read-only), medium (writes to internal systems), high (money, personal data, external communication, irreversible actions).

- **Build or buy.** Search whether the system's own vendor or the user's platform already ships an agent, connector or MCP server for this job (HR, ITSM, CRM and office suites increasingly do). Read the vendor's newsroom and release notes for the last few months, not only product pages, because these offerings change surface and availability quickly. Building is justified when it covers jobs, data or controls the bought option does not; say which.

- **Spec tools.** If the team builds through a spec-driven tool (GitHub Spec Kit, Kiro), feed this spec and the eval plan in as its spec rather than writing a second one.

Ask the user only for what you cannot infer from the repo or the request; propose defaults for the rest.

## Step 2 · Choose the simplest architecture that will pass the evals

Climb the ladder only when the rung below fails a measured requirement: single LLM call → fixed workflow (chain, route, parallelize) → one agent with tools in a loop → orchestrator with sub-agents. Multi-agent pays for parallel breadth and context isolation; it costs tokens and coherence. Keep each agent increment small enough for its reviewer to check in one pass. Details, the five-question decision flow, durable execution, reset loops and council voting: `references/architecture-patterns.md`. Techniques reviewed and judged (including Cache-to-Cache, Karpathy's workflow, 12-Factor Agents, Manus's KV-cache lessons) are in `references/practices-register.md`; check it before proposing something that sounds new.

## Step 3 · Write the eval plan before the code

Fill `templates/eval-plan.md`. Seed the regression suite from the failure catalogue in `references/failure-modes.md` (identity, grounding, authority, injection, write safety, cost) plus the jobs from Step 1. Evals written first define "done"; evals written last only describe what was built. Details: `references/10-evals-and-release.md`.

## Step 4 · Build in layer order

Each layer closes a failure that the previous layers leave open. Read the file when you reach the layer.

| # | Layer | Read | Snapshot default (one line; **[volatile]** names re-checked in Step 0) |
| --- | --- | --- | --- |
| 1 | Model and harness | `references/01-model-and-harness.md` | Vendor general model + small tier, named effort levels, schema-enforced outputs; build on a vendor harness (Claude Agent SDK, OpenAI Agents SDK, Google ADK, Microsoft Agent Framework) or LangGraph; pin versions |
| 2 | Context engineering | `references/02-context-engineering.md` | Short sectioned system prompt; procedures as Agent Skills; AGENTS.md for repos; prompts versioned in git |
| 3 | Retrieval | `references/03-retrieval.md` | Layout parsing → contextual chunks → hybrid dense+BM25 → wide retrieve, rerank → ACL filter with the user's token → exposed as a search tool; graph RAG, keyword-only agentic search or long context when the decision rules say so |
| 4 | Tools and actions | `references/04-tools-and-actions.md` | MCP servers to the current spec; task-shaped tools; tool search when tools exceed a few dozen; A2A only for other teams' agents; approvals + idempotency on writes |
| 5 | Memory and context | `references/05-memory-and-context.md` | Provider compaction, tool-result clearing, file-style durable memory, sub-agents for exploration |
| 6 | Identity and authorization | `references/06-identity-and-authz.md` | Agent workload identity; delegated tokens naming user and agent; enterprise-managed MCP auth; permission checks outside the model |
| 7 | Security | `references/07-security.md`, `references/guards-and-moderation.md` | No session holds private data + untrusted input + an outbound channel; injection-resistant patterns; sandbox + egress allow-list; rules at the prompt, data, egress and output checkpoints; classifiers as one layer only |
| 8 | Cost and latency | `references/08-cost-and-latency.md` | Provider prompt caching with stable prefix; learned routing under evals; batch for offline work; effort per workload |
| 9 | Observability | `references/09-observability.md` | OpenTelemetry GenAI spans across model, tool and MCP calls; redacting Collector; release version on every span |
| 10 | Evals and release | `references/10-evals-and-release.md` | Versioned bundle; required CI eval gate with pass^k; shadow → canary → ramp; online evals; rollback triggers |

For the human-facing side (identity and limits, progress, confirmations, citations, undo, handoff), apply `references/agent-ux-design.md` while building layers 2, 3, 4 and 10.

## Step 5 · Threat-model before first deploy

Fill `templates/threat-model.md`: list every place untrusted content enters, check each session or flow against the lethal trifecta, map controls to the OWASP agentic top 10, and turn the residual risks into red-team eval cases. Details: `references/07-security.md`.

## Step 6 · Release through the gate

Ship the versioned bundle (prompt, dated model snapshot, tool schemas, effort, router mode, index version) through the required eval check, then shadow → canary → ramp with rollback triggers set in advance. A gate that a person can skip is not a gate: the classic failure is an agent that, after months of hardening, answers "Who are you?" with "I'm ChatGPT" because someone pushed a system-prompt change and skipped the evals.

## Step 7 · Hand off

Leave the project with: the filled spec, eval plan, threat model and stack lock; a short decisions log (decision, alternatives, reason, date); and the command that runs the eval suite. Tell the user which **[volatile]** choices to re-check on their next upgrade.

## Non-negotiables

These hold at every risk tier. Each one exists because its absence produced a real failure.

1. **Authorization lives outside the model.** Retrieval and tools enforce the user's own permissions with a delegated token, checked by code or a policy engine. A prompt can be argued out of a rule; a policy engine cannot.
2. **Untrusted content never chooses actions.** Retrieved documents, tool output, web pages, email, images and memory are data. If one session would combine private data, untrusted input and an outbound channel, break the combination or put a deterministic gate or a human in the path.
3. **Every side-effecting tool is classified, gated by its class, idempotent and audited.** Approval does not guarantee exactly-once execution; idempotency keys do.
4. **No secrets in prompts or model-visible context.** Credentials are short-lived and held by the harness, not the model.
5. **Every behavior change is a versioned release through a required eval gate.** Prompt text, model snapshot, tools, effort, router mode, index and guard settings all count. No skip path.
6. **Everything is traced; content capture is opt-in and redacted.** A failure you cannot replay is a failure you cannot fix.
7. **Pin model snapshots and SDK versions; re-run evals on every upgrade.** Defaults shift between releases.
8. **Grounded answers cite their sources and abstain when retrieval finds nothing.** An unsupported answer in a confident voice is the most expensive failure an assistant can make.
9. **Prefer the simplest architecture that passes the evals.** Every extra agent, tool or layer is a new failure surface.
10. **Verify volatile facts before using them.** This file is a snapshot; Step 0 is how it stays true.

## Reviewing an existing agent

Run Step 0, then walk the audit in `references/failure-modes.md`: for each failure mode, find the control in the code or config, test it with its eval case, and report findings as a table (failure mode · evidence · severity · fix · layer file). Lead with authorization, injection and release-gate findings; they are the ones that turn a bug into an incident.

## Files

| File | Read when |
| --- | --- |
| `scripts/check_freshness.py` | Step 0, every time |
| `references/snapshot.json` | Baseline the script diffs against; refresh with `--write-snapshot` only when updating this skill |
| `references/architecture-patterns.md` | Choosing between workflow, single agent and multi-agent; long-running agents |
| `references/01` … `10-*.md` | Building or reviewing that layer |
| `references/agent-ux-design.md` | Designing what the user sees and approves |
| `references/guards-and-moderation.md` | Screening prompts, documents, tool results, outbound messages and answers: invisible characters, credentials, identifiers, exfiltration URLs, guard models and moderation APIs |
| `references/failure-modes.md` | Seeding evals; auditing an existing agent |
| `references/practices-register.md` | Before adopting or rejecting a technique: verdicts (adopt / adopt-when / watch / skip) with sources |
| `templates/agent-spec.md` | Step 1 |
| `templates/eval-plan.md` | Step 3 |
| `templates/threat-model.md` | Step 5 |
| `templates/stack-lock.md` | Step 0 record |

Guide documents produced with this skill leave out prices and currency figures; describe cost mechanisms instead, because prices change faster than anything else here.
