# Architecture patterns

> Snapshot verified 2026-10-27. Items tagged **[volatile]** change often — re-check them with the freshness protocol in SKILL.md before relying on them.

## Default
Build the lowest rung of the ladder that passes the eval set, and climb only when a measured requirement fails: one LLM call with retrieval and examples, then a code-orchestrated workflow (chain, route, parallelize, evaluate), then one agent with tools in a loop, then an orchestrator with sub-agents. Keep control flow, permissions, validation, arithmetic and state in deterministic code, and spend model calls on judgment over unstructured input and on planning when the steps cannot be known in advance. Use several agents only for read-heavy breadth that parallelizes or to keep noisy intermediate context out of the lead agent, and keep every write to a shared artifact in one thread. For work that outlives one context window or session, externalize state (progress file, machine-readable task list, git or a durable session log), resume from checkpoints, verify with a separate evaluator against concrete criteria, and put humans at the plan and at irreversible actions. Re-run the evals on every model upgrade and delete harness parts that are no longer load-bearing.

## Decide
- If one call with retrieval and in-context examples passes the evals → ship it, because Anthropic finds this "usually enough" and every rung above adds latency, tokens and a new failure surface.
- If the steps are fixed and known in advance → prompt chaining with programmatic checks ("gates") between calls, because each call gets an easier job and a failing gate stops drift before it compounds.
- If inputs fall into distinct categories that a classifier separates reliably → route each category to its own prompt, tools or a smaller model, because one prompt tuned for every category degrades on some of them.
- If you can write checkable acceptance criteria and a second pass measurably helps → evaluator-optimizer with the evaluator in its own context and hard pass thresholds, because agents "reliably skew positive when grading their own work" (Anthropic, Mar 2026).
- If the number of steps cannot be predicted and the environment returns ground truth at each step (test results, tool output, API status) → one agent with tools in a loop, with explicit exit conditions, a sandbox and approval gates, because that is where autonomy earns its cost.
- If a single agent picks wrong tools or ignores branches of its prompt → first rename, describe and de-duplicate the tools, defer-load them behind tool search and template the prompt; split into agents only if that fails, because OpenAI reports agents coping with more than 15 distinct tools while others fail with fewer than 10 overlapping ones **[volatile]**.
- If the work splits into independent, read-heavy subtasks whose intermediate output is large and mostly irrelevant to the final answer (over about 1,000 tokens each **[volatile]**) → orchestrator plus sub-agents that return condensed findings (about 1,000–2,000 tokens) or file references, because context isolation and parallel breadth are the measured gains.
- If subtasks share state, are tightly coupled, or are sequential phases of one piece of work (plan → implement → test → review) → keep one agent, because every handoff loses context and Anthropic saw role-split sub-agents spend "more tokens on coordination than on actual work" **[volatile]**.
- If several agents would write to the same code base, document or record → keep writes single-threaded and give the other agents read-only research, review or second-opinion roles, because parallel writers make conflicting implicit decisions (Cognition, Jun 2025 and Apr 2026).
- If one agent should own the user conversation and synthesize the result → manager pattern (specialist agents exposed as tools); if a specialist should take over the conversation outright (support triage) → handoff pattern, because the choice fixes who holds context and who talks to the user.
- If output must be verified → a black-box verifier that gets the artifact, the success criteria and its own tools but not the build history, run after deterministic checks, because verification needs little context and rule-based feedback is more robust than model grading.
- If the task runs for hours or across sessions → the long-running harness below, or a managed harness with durable sessions such as Claude Managed Agents (beta) **[volatile]** or OpenAI Agents SDK sandbox agents with resumable sessions and snapshots **[volatile]**, because a context window is not a database.

## Patterns

### The ladder
1. **Single LLM call.** One prompt with retrieved context, examples and a schema-enforced output. Use it for classification, extraction, summarization, drafting and Q&A over a bounded corpus. It is the baseline every higher rung must beat on the same eval set; Google's architecture guide likewise recommends a non-agentic solution when a workload is predictable or a single call can handle it.
2. **Workflow patterns (code decides the path).** Prompt chaining for fixed sequences; routing for separable input types; parallelization as sectioning (independent parts at once) or voting (same task several times for confidence); orchestrator-workers when a model must choose the subtasks at run time (for example, which files a change touches); evaluator-optimizer when criteria are clear and iteration helps. Fan-out, merging, retries and exit conditions live in code, so runs are cheaper, reproducible and debuggable. Choose this rung when you can draw the flowchart before the run.
3. **Single agent with tools in a loop.** The model picks the next action from tool results until an exit condition fires: a final-output tool or structured result, an error, or a turn, time or token budget. Loop shape: gather context → act → verify → repeat. Grow capability by adding well-designed tools before adding agents, because one agent is easier to evaluate and maintain. Choose it when steps are open-ended and each step returns feedback the agent can check.
4. **Multi-agent (orchestrator + sub-agents).** A lead agent plans, spawns workers with their own context windows and a clear brief (objective, output format, tool guidance, boundaries), then synthesizes. It wins on breadth-first research and on keeping noisy exploration out of the lead's context: Anthropic's research system beat single-agent Opus 4 by 90.2% on an internal eval, and token usage explained 80% of the variance on BrowseComp **[volatile]**. It costs about 15× the tokens of a chat (a single agent about 4×) and typically 3–10× a single-agent solution to the same task **[volatile]**, usually more wall-clock time, plus routing and prompt maintenance. Have workers write outputs to files or a store and return references, so results are not retold lossily through the lead.

### Multi-agent: what works in 2026
- **Works:** read-only search and research sub-agents; a reviewer or verifier with clean context (Cognition: "clean context leads to a notable improvement" in generator-verifier loops); a model escalating hard sub-problems to a stronger model through a tool call; a manager splitting a large task into child agents that each own disjoint work ("map-reduce-and-manage") **[volatile]**.
- **Fails:** parallel-writer swarms; splitting by role instead of by context; managers that assume children share their state; briefs that pass instructions without the decisions behind them. Cognition's rule: "writes stay single-threaded and the additional agents contribute intelligence rather than actions."
- **Decompose by context, not by job title:** "an agent handling a feature should also handle its tests." Good boundaries: independent research paths, components with clean interfaces, black-box verification. Poor boundaries: sequential phases of one piece of work, tightly coupled components, shared mutable state.

### Long-running agents
- **Initializer + worker sessions.** The first session writes a setup script (`init.sh`), a progress log, a JSON feature list with every item `"passes": false`, and an initial git commit. Every later session confirms its working directory, reads the git log and progress file, starts the app and runs a smoke end-to-end test, picks the highest-priority failing item, implements only that item, tests it as a user would (browser automation), commits, updates the progress log and leaves a clean state. Keep the list in JSON and allow edits only to the status field; Anthropic found the model "less likely to inappropriately change or overwrite JSON files" than Markdown **[volatile]**.
- **Design against these failure modes:** one-shotting (context runs out mid-feature), declaring victory early, leaving broken or undocumented state, and marking items done without an end-to-end test.
- **Compaction or reset.** Compaction summarizes history in place and keeps continuity; a reset starts a fresh agent from a structured handoff file, giving a clean slate but only if the handoff is complete. Choose per model and re-test: resets were essential for Sonnet 4.5 and unnecessary for Opus 4.5 **[volatile]**. Note files suit milestone work; sub-agents suit parallel exploration (details: `05-memory-and-context.md`).
- **Planner / generator / evaluator.** For multi-hour builds, a planner expands a short prompt into a spec, the generator works in increments, and an evaluator exercises the running app against criteria both sides agreed before each increment (a "sprint contract"), failing the increment if any criterion fails. In Anthropic's comparison a 20-minute solo run produced a broken app and the 6-hour harness a working one, and with Opus 4.6 the sprint structure could be dropped **[volatile]**. Treat each part as a hypothesis: "every component in a harness encodes an assumption about what the model can't do on its own."
- **Durable, resumable state.** Resume from the last checkpoint instead of restarting. Persist run state outside the process (OpenAI Agents SDK `RunState.to_json()` **[volatile]**, the Claude Managed Agents server-side session event log **[volatile]**, sandbox snapshots), store a version marker with it, and make side-effecting tools idempotent, because a resume can repeat an action. Deploy so in-flight runs finish on the version they started on (Anthropic uses rainbow deployments).

### Human-in-the-loop placement
- Put people where their judgment adds information: approving the plan before a long run, approving each irreversible or external action (payment, deletion, outbound message, permission change), and taking over after a failure threshold such as N failed attempts at one step. Exceeded failure thresholds and high-risk actions are OpenAI's two intervention triggers; plan review is the third.
- Do not make per-command prompts your safety layer: Claude Code users approved 93–97% of permission prompts but rejected 39% of plans, and in a controlled study reviewers caught 13.6% of injected dangerous commands, falling to about 5% after 50 or more prompts **[volatile]**. Contain at the environment layer first (sandbox, egress allow-list, policy engine), then steer the model.
- Make approvals durable: pause, serialize state, notify, and resume on the same session hours later. Approval does not guarantee exactly-once execution; idempotency keys do. Approval wording and UI: `agent-ux-design.md`.

### Code vs model judgment
- **Code:** any control flow you can draw, routing on structured fields, authorization, schema validation, arithmetic, dates and units, retries and backoff, rate limits, budgets, loop caps, persistence, fan-out and merge, and every check a test, linter or type checker can make. **Model:** reading unstructured input, choosing actions when the steps are unknown, drafting, and judging fuzzy criteria against a rubric.
- **Feedback order:** rules first ("The best form of feedback is providing clearly defined rules for an output"), visual checks such as screenshots second, LLM-as-judge last ("generally not a very robust method") (Anthropic, Sep 2025).
- **Let the agent write code** for calculation and file generation, since code is "precise, composable, and infinitely reusable". Many production agents are "mostly deterministic code, with LLM steps sprinkled in" (12-Factor Agents).

### Five-question decision flow
1. **Does one call with retrieval and examples pass the eval set?** Yes → stop at rung 1. No → question 2.
2. **Can you draw the flowchart before the run?** Yes → a workflow pattern orchestrated by code (chain, route, parallelize, evaluator-optimizer). No → question 3.
3. **Does each step return feedback the agent can verify (tests, tool results, API status)?** Yes → one agent with tools in a loop, sandboxed, with exit conditions. No → add a verifier or human checkpoints, or narrow the scope until it does.
4. **Does the work split into independent, read-heavy pieces whose intermediate output would swamp one context, and is the task worth several times the tokens?** Yes → orchestrator with read-only sub-agents and a single writer. No → stay with one agent and add compaction or note files.
5. **Will it outlive one context window or session, or take irreversible actions?** Yes → add the long-running harness (progress file, JSON task list, checkpoints, durable run state, idempotent tools) and human gates at the plan and at irreversible actions. No → ship through the eval gate.

## Build checklist
- [ ] Record the chosen rung and the eval result that ruled out the rung below it in the decisions log.
- [ ] Run the eval set against a single-call or workflow baseline before building any agent loop.
- [ ] Give every loop explicit exit conditions (final-output tool, max turns, max tokens or time, error) and test that each one fires.
- [ ] Implement validation, permissions, structured routing, arithmetic and retries in code, with unit tests.
- [ ] Give every sub-agent brief an objective, output format, tool guidance and boundaries, and cap its return at a condensed summary or a file reference.
- [ ] Ensure exactly one agent writes to any shared artifact; all parallel workers are read-only.
- [ ] Measure tokens and latency per task for single-agent and multi-agent versions on the same evals; keep multi-agent only where the quality gain justifies the multiple.
- [ ] Run deterministic checks (tests, linters, schemas) before any LLM judge, and calibrate any judge against human labels.
- [ ] Run the verifier in a separate context with the artifact and criteria only, and require it to run the full test suite before passing.
- [ ] For long runs, keep a progress file, a JSON task list and a git commit per unit of work, and prove a fresh session can resume from them alone by killing a run midway.
- [ ] Serialize run state with a version marker, test resume after a process restart, and give every side-effecting tool an idempotency key.
- [ ] Implement escalation after a failure threshold, approval for irreversible actions and plan approval for long tasks, and test each path.
- [ ] Trace every model call, tool call and sub-agent spawn with parent IDs so a run can be replayed.
- [ ] On each model upgrade, ablate harness components (resets, sprints, evaluators, sub-agents) and keep only those that still move the evals.
- [ ] Deploy so in-flight long runs complete on the version they started on.

## Avoid
- Starting with a multi-agent framework → start from the API or one agent and add structure when an eval fails (teams have spent months on multi-agent designs that a better single-agent prompt matched).
- Splitting agents by role (planner, coder, tester, reviewer) → split by context, so one agent owns a feature and its tests (each handoff is a game of telephone).
- Parallel agents writing the same artifact → one writer plus read-only helpers (implicit style and design choices collide).
- Briefs that carry only an instruction → pass the relevant decisions, constraints and file references (sub-agents act on unstated assumptions otherwise).
- The generator grading its own work → a separate evaluator with concrete, hard thresholds (self-evaluation skews lenient).
- An LLM judge where a test, linter or schema check exists → the deterministic check (cheaper, repeatable, harder to fool).
- One giant session for a large build → one feature per session with a commit and a progress update (one-shotting runs out of context and leaves half-built state).
- Markdown checklists the agent may rewrite → a JSON list where only the status field may change (models overwrite prose lists more readily).
- Restarting a failed long run from scratch → resume from the last checkpoint (errors compound and restarts waste the work done).
- Keeping scaffolding forever → re-test each component on model upgrades (a part that compensated for an old weakness becomes pure cost).
- Loops without caps → turn, time and token budgets plus an escalation path (runaway loops burn budget and hang).
- A permission prompt on every action → sandbox and policy for routine steps, human approval for plans and irreversible actions (people approve nearly everything they are shown).

## Additions (verified 2026-10-27)

- **Keep the agent on a leash.** Size each agent increment so its reviewer can check it in one pass; split larger work. Lower autonomy further for novel, off-distribution work and verify it against a reference implementation (Karpathy).
- **Durable execution** when a run must survive deploys or crashes, or wait hours to days for a person: run the loop on a durable engine (Temporal, Restate, DBOS, Lambda durable functions, Agent Framework Durable Extension **[volatile]**), each model and tool call a checkpointed step, idempotency keys kept. Do not add one only for save and resume.
- **Session log as the source of truth** when you host the loop: one append-only event log per session, outside the harness; resume, fork, replay and render from it; provision sandboxes lazily with no credentials inside ([Anthropic Managed Agents](https://www.anthropic.com/engineering/managed-agents)).
- **Contact humans through a tool** in headless or event-driven agents: a structured `request_human_input` tool saves state, ends the run and resumes on the reply event ([12-Factor Agents](https://github.com/humanlayer/12-factor-agents)).
- **Agent-shaped test output** for long-running agents: a few summary lines, full logs to files, grep-able error tags, a deterministic fast mode, and a verifier that covers nearly all behaviour.
- **Reset loops (Ralph)** only when work is unattended, automatically verifiable and sandboxed: same prompt, fresh context, one item per iteration, state in files and git, tests as backpressure, an iteration cap.
- **Unattended optimisation loops** only against an evaluator the agent cannot modify: fixed budget per trial, keep or discard each trial in git, append-only log, several metrics, inside a sandbox (Karpathy's autoresearch pattern).
- **Multi-model councils** (independent answers, anonymised peer ranking, synthesis) only offline, for high-value questions without ground truth, with every vendor approved for the data. First beat repeated sampling of the best single model; evidence shows voting explains most of the gain from debate-style setups. Keep councils off the live answer path.
- **Latent or KV-cache communication between agents** (Cache-to-Cache and similar): watch, do not build; see `practices-register.md`.

## Verify before relying
| Fact **[volatile]** | Snapshot (2026-10-27) | Where to check (URL) |
| --- | --- | --- |
| Multi-agent research results and token multiples | +90.2% vs single agent on internal eval; agents ~4×, multi-agent ~15× chat tokens; tokens explain 80% of BrowseComp variance (Jun 2025) | https://www.anthropic.com/engineering/multi-agent-research-system |
| Multi-agent vs single-agent cost and isolation threshold | 3–10× tokens for equivalent tasks; isolate subtasks producing >1,000 mostly irrelevant tokens; 15–20+ tools signals specialization (Jan 2026) | https://www.claude.com/blog/building-multi-agent-systems-when-and-how-to-use-them |
| Cognition position on multi-agent | Writes single-threaded; reviewer, smart-friend, manager/child and read-only sub-agents work; parallel-writer swarms do not (Apr 2026) | https://cognition.com/blog/multi-agents-working |
| Harness components needed per model | Resets needed for Sonnet 4.5, not Opus 4.5; sprint structure removable with Opus 4.6 (Mar 2026) | https://www.anthropic.com/engineering/harness-design-long-running-apps |
| JSON feature list and initializer pattern | Initializer + coding-agent sessions; JSON less often overwritten than Markdown (Nov 2025) | https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents |
| Claude Managed Agents status | Beta, header `managed-agents-2026-04-01`; multiagent orchestration and outcomes public beta; dreaming and MCP tunnels research preview | https://platform.claude.com/docs/en/managed-agents/overview |
| OpenAI Agents SDK durable approvals and sandboxes | `needs_approval`, `RunState.to_json()/from_json()`, sandbox agents with manifest, resumable sessions and snapshots | https://openai.github.io/openai-agents-python/human_in_the_loop/ |
| OpenAI tool-overload heuristic | >15 distinct tools can work; <10 overlapping tools can fail (2025 guide) | https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf |
| Human approval behaviour in Claude Code | 93% (May 2026) to 97% (Aug 2026) of prompts approved; 39% of plans rejected; reviewers caught 13.6% of dangerous commands | https://claude.com/blog/auto-mode-default-in-claude-code |
| Google Cloud agent pattern catalog | 12 patterns incl. sequential, parallel, loop, coordinator, swarm, human-in-the-loop (updated 2026-05-28) | https://docs.cloud.google.com/architecture/choose-design-pattern-agentic-ai-system |

## Sources
- [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents) — Anthropic, 2024-12-19
- [How we built our multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system) — Anthropic, 2025-06-13
- [A practical guide to building agents](https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf) — OpenAI, 2025 (PDF carries no date)
- [Don't Build Multi-Agents](https://cognition.com/blog/dont-build-multi-agents) — Cognition (Walden Yan), 2025-06-12
- [Multi-Agents: What's Actually Working](https://cognition.com/blog/multi-agents-working) — Cognition (Walden Yan), 2026-04-22
- [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) — Anthropic, 2025-09-29
- [Building agents with the Claude Agent SDK](https://claude.com/blog/building-agents-with-the-claude-agent-sdk) — Anthropic, 2025-09-29
- [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) — Anthropic, 2025-11-26
- [Building multi-agent systems: when and how to use them](https://www.claude.com/blog/building-multi-agent-systems-when-and-how-to-use-them) — Anthropic, 2026-01-23
- [Harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps) — Anthropic, 2026-03-24
- [How we contain Claude across products](https://www.anthropic.com/engineering/how-we-contain-claude) — Anthropic, 2026-05-25
- [Auto mode is now the default in Claude Code](https://claude.com/blog/auto-mode-default-in-claude-code) — Anthropic, 2026-08-07 (updated 2026-10-22)
- [Claude Managed Agents overview](https://platform.claude.com/docs/en/managed-agents/overview) — Anthropic docs, accessed 2026-10-27
- [New in Claude Managed Agents: dreaming, outcomes, and multiagent orchestration](https://claude.com/blog/new-in-claude-managed-agents) — Anthropic, 2026-05-19
- [Human-in-the-loop](https://openai.github.io/openai-agents-python/human_in_the_loop/) and [Sandbox agents](https://openai.github.io/openai-agents-python/sandbox_agents/) — OpenAI Agents SDK docs, accessed 2026-10-27
- [Choose a design pattern for your agentic AI system](https://docs.cloud.google.com/architecture/choose-design-pattern-agentic-ai-system) — Google Cloud, updated 2026-05-28
- [12-Factor Agents](https://github.com/humanlayer/12-factor-agents) — HumanLayer, accessed 2026-10-27
