# 10 · Evals and release

> Snapshot verified 2026-10-27. Items tagged **[volatile]** change often — re-check them with the freshness protocol in SKILL.md before relying on them.

## Default
Write the eval suite before the agent and make it a required CI check on a versioned release bundle: prompt version, dated model snapshot, tool schemas, effort and speed, router mode and model subset, retrieval index version. Grade final environment state with deterministic code first, add trace graders for tool-use and policy checks, and use LLM judges only for what code cannot check — calibrated against human labels with chance-corrected agreement, and treated as a regression floor, not a replacement for reading transcripts. Run every task k times and gate user-facing tasks on pass^k; keep a regression suite (near 100%, seeded from 20–50 real failures) separate from a capability suite (hard, low pass rate) whose reliably passing tasks graduate into regression. Use public benchmarks only to shortlist models. Release through shadow → canary → ramp with session-pinned cohorts, online evaluators on sampled traces, rollback triggers declared before launch, and a config kill switch that restores the previous bundle in under a minute.

## Decide
- If the outcome shows up in environment state (a database row, file, ticket, or message in a sandbox outbox) → grade it with a deterministic final-state check, because code graders are fast, reproducible and indifferent to the path, and Anthropic recommends deterministic graders wherever possible.
- If the path itself matters (forbidden tool, write without approval, wrong handoff, data sent to the wrong tool) → add trace graders that assert on tool spans and arguments, but never require an exact step sequence, because outcome checks pass unsafe runs that happen to end well and rigid sequences fail valid alternatives.
- If quality can only be judged (tone, faithfulness of a summary, helpfulness) → use one LLM judge per dimension with a structured rubric and an "Unknown" option, pin the judge model, and calibrate it on human-labeled traces with Cohen's kappa and per-defect recall, because exact-match agreement overstated judge validity by 33–41 points on MT-Bench and judge rankings shifted up to 14 places across benchmarks.
- If the agent is multi-turn and stateful (carts, confirmations, referents, escalations) → add rubric categories for state tracking, guardrails and recovery, and keep sampled human transcript review in the loop, because one production judge caught 2 of 9 systematic patterns and its gate flagged 0 of 100 rounds that held 23 human-confirmed defects.
- If users rely on the task succeeding every time, or it takes irreversible actions → gate on pass^k (k ≥ 3), not pass@1, because 75% per trial is only ~42% pass^3; report pass@k only when exploring capability.
- If you are choosing a model → shortlist on public benchmarks that match your agent's shape — τ-bench for tool-agent-user service flows, MCPMark for MCP CRUD tasks, Terminal-Bench for terminal and coding agents, SWE-bench Pro for repository coding — then decide on your own suite **[volatile]**, because SWE-bench Verified was dropped over contamination and broken tasks, benchmark versions are not comparable (τ-bench 2.0 vs 1.x), and none of them exercises your tools or data.
- If you need sandboxed agent tasks, external agents (Claude Code, Codex CLI, Gemini CLI) or ready-made benchmarks → Inspect; if you want declarative test cases and scheduled red-team scans in CI → promptfoo (acquisition by OpenAI announced 2026-03-09; open source continues) **[volatile]**; if traces already live in a platform → its online evaluators (OpenAI trace grading, LangSmith, Langfuse, Braintrust), because the gate needs reproducible sandboxes and the online loop needs trace access.
- If any element of the release bundle changes → rerun the full regression suite and change one element at a time, because each element shifts behavior and most also reset prompt caches; Microsoft gives the same rule for router mode and model subset.
- If the change touches irreversible actions, money movement or personal data → shadow first (mirrored traffic, side effects stubbed), then canary at 0.1%; otherwise canary at 1% → 5 → 20 → 50 → 100% with session-sticky cohorts, because per-request assignment mixes two behaviors inside one conversation (the percentages are a practitioner pattern, not a standard).
- If a rollback trigger fires or an online score crosses its threshold → flip the kill switch to the previous bundle by config (for example, move the `production` prompt label back), purge response caches keyed to the bad bundle and freeze the ramp, because a rollback that needs a code deploy is too slow and a surviving cache keeps serving the bad version.
- If you place a general-purpose AI model on the EU market, or substantially fine-tune one → check EU AI Act GPAI duties (applicable since 2025-08-02, enforceable by the AI Office since 2026-08-02; systemic-risk models need model evaluation and adversarial testing) **[volatile]**, because a substantial fine-tuner can be treated as a provider.

## Build checklist
- [ ] Write a bundle manifest listing prompt version/hash, dated model snapshot ID (never an alias), tool schema hashes and MCP server versions, effort/speed/thinking, router mode and model subset, retrieval index and embedding model version, guard and classifier versions, SDK lockfile hash and judge model snapshot; derive a bundle ID and stamp it on every span (`09-observability.md`).
- [ ] Seed the regression suite with 20–50 tasks from real failures plus the catalogue in `failure-modes.md`; give each task a fixture initial state, an input, a deterministic final-state check, trace assertions and, only where needed, a judge rubric.
- [ ] Keep a separate capability suite and graduate tasks into regression once they pass reliably.
- [ ] Reset a sandbox per trial (container or VM) with writes going to fakes or test tenants, never production.
- [ ] Run k trials per task (k ≥ 3 for regression, more for flaky tasks) and report pass@1, pass^k and an interval; run them on batch or flex capacity (`08-cost-and-latency.md`).
- [ ] Calibrate each judge on a human-labeled set: report kappa and recall per defect class, add position-swap checks for pairwise judges, and recalibrate whenever the judge model or rubric changes.
- [ ] Make the eval job a required status check under branch protection with no admin bypass, triggered by any change to bundle paths (prompts, tool schemas, bundle manifest, index lock, SDK lockfiles).
- [ ] Store each released bundle's results as the baseline the next change is compared against.
- [ ] Schedule a daily red-team run (promptfoo `redteam run` or Inspect tasks) that plants injection payloads in retrieved documents, tool outputs and memory; turn every new finding into a regression case.
- [ ] Shadow: mirror real traffic to the candidate bundle with side-effecting tools stubbed; compare judge scores, tool-call counts, tokens per task and latency.
- [ ] Canary with session-sticky cohorts; hold the first step 24–48 hours before ramping.
- [ ] Run online evaluators on sampled production traces with filters (negative feedback, specific tool calls, low scores), thread-level evaluators for multi-turn sessions and a per-evaluator spend cap; write scores back to the traces.
- [ ] Declare rollback triggers in the bundle before launch, each relative to the previous bundle: online eval score drop, p99 latency rise, refusal-rate jump, tokens-per-task or turns-per-task rise, tool error rate rise, guardrail-trip spike.
- [ ] Rehearse the kill switch every release: restore the previous bundle by config in under a minute and confirm prompt labels and response caches follow.
- [ ] Read a weekly sample of production transcripts; turn each new failure into a regression case within the week.
- [ ] On a provider snapshot deprecation or upgrade, rerun the full suite and the effort sweep before switching.

Example eval case (harness-neutral; map the fields onto Inspect, promptfoo or your runner):
```yaml
id: refund-duplicate-charge-017
source: incident INC-2291             # real failure: agent refunded twice
suite: regression
trials: 5                             # gate on pass^5
setup: {fixture: fixtures/orders/duplicate_charge.sql, user: cust_4410}
input: "I was charged twice for order 8812. Please fix it."
graders:
  - type: state                       # deterministic final environment state
    sql: SELECT count(*) FROM refunds WHERE order_id = 8812
    expect: 1
  - type: trace                       # policy on spans, not exact step order
    require_before: {tool: payments_refund, approval: granted}
    forbid_tools: [admin_sql, email_send_external]
    max_tool_calls: 8
  - type: judge                       # only what code cannot check
    rubric: rubrics/explains_refund_and_timeline.md
    allow_unknown: true
```

Example CI gate step (required check `agent-evals`; thresholds are examples — set yours from baseline noise):
1. On any PR touching a bundle path, build the bundle and compute its ID.
2. Run the regression suite in sandboxes with k = 5 plus the red-team smoke set (e.g. `inspect eval …`, or `npx promptfoo@latest eval -c evals/promptfooconfig.yaml -o results.junit.xml -o results.json`).
3. Load the stored results of the current production bundle as the baseline.
4. Fail if any task tagged `critical` misses pass^5 = 1.0; suite pass^5 falls below baseline beyond its interval; any critical red-team case succeeds; or median tokens per task or p95 latency exceed 1.2× baseline. promptfoo's `--fail-on-error` fails on any failed test but has no pass-rate flag, so compute rates from `results.json` in the step **[volatile]**.
5. Publish the JUnit report and link traces tagged with the bundle ID in the PR.

## Avoid
- Grading exact step sequences → grade outcomes and forbid unsafe paths (rigid sequences fail valid alternatives).
- One trial per task → k trials and pass^k (a single run hides the flakiness users will see).
- Raw agreement as judge validation → kappa plus per-defect recall against human labels (agreement is inflated by chance).
- An LLM judge as the only gate for a multi-turn agent → judge as a floor plus sampled transcript review (judges miss cross-turn state defects).
- SWE-bench Verified scores for model choice → SWE-bench Pro and your own suite (an audit found 59.4% of consistently failed tasks broken, and models reproduced fixes from task IDs).
- Comparing τ-bench 2.0 numbers with the 1.x leaderboard → compare within one version.
- Floating model aliases → dated snapshots (an alias update is an unreviewed release).
- A "just a prompt tweak" skip path → required check with no bypass (see the identity failure in SKILL.md Step 6).
- Per-request canary assignment → session-sticky cohorts.
- Shadow runs with live side effects → stubbed writes.
- Changing prompt, model and effort in one release → one lever per release (otherwise no change is attributable).
- Online judges on all traffic with no cap → sampling plus a spend cap.
- A rollback that leaves caches and labels on the bad bundle → purge and reassign inside the switch.

## Additions (verified 2026-10-27)

- **Error analysis before judges.** Read and open-code real traces into a failure taxonomy first; then write one binary pass/fail evaluator per frequent failure, recording the first failing step ([evals FAQ](https://hamel.dev/blog/posts/evals-faq/)).
- **Task hygiene.** Give every task a reference solution and a paired should-not-act case; a task at 0% over k trials is usually broken, not hard; add harder tasks when a suite saturates ([Anthropic](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)).
- **Reliability in nines.** Set a target per task class (e.g. 99% or 99.9% of runs) and measure it with pass^k; a working demo is not evidence.
- **Ask-or-push-back cases.** Include cases where the correct behaviour is to ask a question, refuse, or flag an inconsistency; for coding agents also review diffs for unrequested edits, dead code and bloat.
- **Infrastructure noise.** Record sandbox CPU, memory and kill limits in the release bundle; count infrastructure errors separately; treat score gaps under about 3 points as noise ([Anthropic](https://www.anthropic.com/engineering/infrastructure-noise)).
- **Eval awareness.** When eval agents can browse, block benchmark names and answer sources and flag transcripts that hunt for the answer key ([Anthropic](https://www.anthropic.com/engineering/eval-awareness-browsecomp)).

## Verify before relying
| Fact **[volatile]** | Snapshot (2026-10-27) | Where to check (URL) |
| --- | --- | --- |
| Anthropic eval guidance | Deterministic graders first; pass^k; capability vs regression; start with 20–50 real-failure tasks (2026-01-09) | https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents |
| τ-bench version | τ-bench 2.0 current (`v2.0.0` tagged 2026-10-20 per freshness snapshot); not comparable with 1.x; domains airline, retail, telecom, banking_knowledge, intake; text and voice | https://github.com/sierra-research/tau2-bench · https://taubench.com |
| SWE-bench status | OpenAI stopped reporting Verified (Feb 2026), recommends SWE-bench Pro; >70% Verified models scored ~23% on the Pro public split | https://decrypt.co/359012/openai-benchmark-measure-ai-coding-supremacy-contaminated |
| MCPMark | ICLR 2026; 127 tasks with programmatic verification; best reported 52.56% pass@1, 33.86% pass^4 | https://proceedings.iclr.cc/paper_files/paper/2026/hash/8138d211ce8790fdfbeeeb9781838a37-Abstract-Conference.html |
| Terminal-Bench version | 4.0; resolution rate with 95% CIs | https://www.tbench.ai/ |
| Inspect | UK AISI + Meridian Labs; 200+ prebuilt evals; agent bridge; Docker/K8s/Modal sandboxes | https://inspect.aisi.org.uk/ |
| promptfoo ownership and CI flags | Acquisition by OpenAI announced 2026-03-09; open source continues; `--fail-on-error`, no pass-rate flag; daily `redteam run` example | https://www.promptfoo.dev/docs/integrations/ci-cd/ · https://gigazine.net/gsc_news/en/20260310-openai-to-acquire-promptfoo |
| LangSmith online evaluators | Sampling rate, filters, thread evaluators, per-evaluator weekly spend limit | https://docs.langchain.com/langsmith/online-evaluations |
| Langfuse prompt labels | `production` served by default; `latest` automatic; rollback by moving the label; protected labels on paid tiers | https://langfuse.com/docs/prompt-management/features/prompt-version-control |
| Judge-reliability findings | Preprints (June 2026), not yet peer-reviewed | https://arxiv.org/abs/2606.10315 · https://arxiv.org/abs/2606.19544 |
| Managed-router re-evaluation rule | Re-evaluate after any routing-mode or subset change; one lever at a time (doc updated 2026-10-19) | https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/model-router-how-it-works |
| Rollout percentages and triggers | Practitioner pattern (2026-04-09), not a standard | https://tianpan.co/blog/2026-04-09-llm-gradual-rollout-shadow-canary-ab-testing |
| EU AI Act GPAI dates | Obligations 2025-08-02; AI Office enforcement 2026-08-02; Annex III high-risk deadline moved to 2027-12-02, GPAI unchanged | https://labs.cloudsecurityalliance.org/research/csa-research-note-eu-ai-act-gpai-enforcement-20260803-csa-st/ |

## Sources
- [Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) — Anthropic Engineering, 2026-01-09
- [Evaluate agent workflows](https://developers.openai.com/api/docs/guides/agent-evals) — OpenAI, n.d. (accessed 2026-10-27)
- [tau2-bench](https://github.com/sierra-research/tau2-bench) — Sierra Research, GitHub, accessed 2026-10-27
- [OpenAI Says Benchmark Used to Measure AI Coding Skill Is 'Contaminated'—Here's Why](https://decrypt.co/359012/openai-benchmark-measure-ai-coding-supremacy-contaminated) — Decrypt, 2026-02-24
- [MCPMark: A Benchmark for Stress-Testing Realistic and Comprehensive MCP Use](https://proceedings.iclr.cc/paper_files/paper/2026/hash/8138d211ce8790fdfbeeeb9781838a37-Abstract-Conference.html) — ICLR 2026
- [Terminal-Bench](https://www.tbench.ai/) — Stanford, Laude Institute, Harbor, accessed 2026-10-27
- [Inspect](https://inspect.aisi.org.uk/) — UK AI Security Institute and Meridian Labs, accessed 2026-10-27
- [CI/CD integration](https://www.promptfoo.dev/docs/integrations/ci-cd/) — promptfoo, updated 2026-10-26
- [OpenAI acquires AI security startup Promptfoo](https://gigazine.net/gsc_news/en/20260310-openai-to-acquire-promptfoo) — GIGAZINE, 2026-03-10
- [Online evaluations](https://docs.langchain.com/langsmith/online-evaluations) — LangChain, n.d. (accessed 2026-10-27)
- [Prompt version control](https://langfuse.com/docs/prompt-management/features/prompt-version-control) — Langfuse, n.d. (accessed 2026-10-27)
- [Catching One in Five: LLM-as-Judge Blind Spots in Production Multi-Turn Transaction Agents](https://arxiv.org/abs/2606.10315) — Zhang, Wang, Lei, arXiv, 2026-06-09
- [Reliability without Validity: A Systematic, Large-Scale Evaluation of LLM-as-a-Judge Models](https://arxiv.org/abs/2606.19544) — arXiv, 2026-06-17
- [How model router works](https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/model-router-how-it-works) — Microsoft Learn, updated 2026-10-19
- [Releasing AI Features Without Breaking Production: Shadow Mode, Canary Deployments, and A/B Testing for LLMs](https://tianpan.co/blog/2026-04-09-llm-gradual-rollout-shadow-canary-ab-testing) — Tian Pan, 2026-04-09
- [EU AI Act GPAI Enforcement Goes Live](https://labs.cloudsecurityalliance.org/research/csa-research-note-eu-ai-act-gpai-enforcement-20260803-csa-st/) — Cloud Security Alliance, 2026-08-03
