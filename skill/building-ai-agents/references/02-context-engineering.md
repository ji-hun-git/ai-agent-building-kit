# 02 · Context engineering

> Snapshot verified 2026-10-27. Items tagged **[volatile]** change often — re-check them with the freshness protocol in SKILL.md before relying on them.

## Default
Treat context as a finite resource with diminishing returns and fill it in layers instead of one large prompt: a short, sectioned system prompt at the "right altitude" (concrete enough to steer, general enough to leave judgment to the model); task procedures as Agent Skills that load by progressive disclosure; repository conventions in AGENTS.md (CLAUDE.md for Claude tools); a small set of non-overlapping, token-efficient tools; and data fetched just in time through lightweight references such as paths, IDs and queries. Start minimal and add an instruction only when an eval fails, because recall degrades as context grows ("context rot") and every always-loaded token competes with the task. Keep prompts, skills, tool descriptions and agent configs as files in git, reviewed by pull request and gated by evals. Do not build on vendor-hosted prompt registries; they are being retired (OpenAI's `v1/prompts` **[volatile]** shuts down 2026-11-30 **[volatile]**).

## Decide
- If an instruction applies to every turn (role, scope, refusal and escalation rules, output contract, tool-use policy) → put it in the system prompt, because only that layer is always present.
- If knowledge is a procedure needed for some tasks only (a report format, a migration runbook, a domain workflow) → an Agent Skill, because only its name and description (about 100 tokens **[volatile]**) load at startup and the body loads on activation.
- If the agent works in a code repository used by several coding agents → AGENTS.md at the root plus nested files per package (the nearest file wins; explicit user prompts override), mirrored or referenced from CLAUDE.md for Claude tools, because AGENTS.md is read by Codex, Jules, Gemini CLI, Cursor, GitHub Copilot and many others.
- If you are writing long if-else rule lists → replace them with the principle plus a few diverse canonical examples, because hard-coded logic is brittle and examples convey expected behaviour better than edge-case rules.
- If your runtime loads Agent Skills natively (Claude API Skills via `/v1/skills` **[volatile]**, Claude Agent SDK, Managed Agents, Codex, ChatGPT, Google ADK) → package procedures as `SKILL.md` folders, because the format is an open standard and moves between products unchanged.
- If your runtime has no skill loader → emulate progressive disclosure: list each skill's name and description in the system prompt and expose a read-file tool scoped to the skills folder, because that reproduces the same load-on-demand behaviour.
- If a skill step is fragile or must run in an exact sequence → ship a script and tell the agent to run it (low freedom); if several approaches are valid → give heuristics (high freedom), because scripts are more reliable than generated code and cost only their output in context.
- If data is large, changes often or is needed only sometimes → just-in-time retrieval (references plus a fetch or search tool); if it is small, stable and needed every turn → load it up front, because the hybrid (key files up front, the rest explored with search tools) balances speed against context size.
- If two tools overlap or a person could not say which one to pick → merge them into one task-shaped tool and namespace by service and resource, because the agent will be just as confused (tool search for large catalogues: `04-tools-and-actions.md`).
- If a tool can return large output → paginate, filter and truncate by default, offer a concise/detailed response mode and return human-readable identifiers, because tool results are usually the largest context consumer (Claude Code caps a tool response at 25,000 tokens **[volatile]** by default).
- If a prompt needs variables or per-environment variants → typed function parameters, release tags and feature flags in your own code, because OpenAI now tells new work not to create hosted prompt objects.
- If you deploy on Managed Agents → use its server-side agent `version` **[volatile]** for rollout but keep git as the source of truth, because a server-side config is neither reviewed nor eval-gated by itself.

## Build checklist
- [ ] Split the system prompt into labelled sections (background, instructions, tool guidance, output format) with XML tags or Markdown headings.
- [ ] Start from the minimal prompt; add one instruction per failing eval case and cite the case ID in the commit message.
- [ ] Include a few diverse canonical examples; delete rules that only restate an example.
- [ ] Put stable content (system prompt, tool definitions) first and per-turn content last so the prefix can be cached (see `08-cost-and-latency.md`).
- [ ] Measure the always-loaded token footprint (system prompt + tool definitions + skill metadata + AGENTS.md) and record it in the stack lock; review any change that grows it.
- [ ] For each skill: folder name equals `name`; `name` ≤ 64 chars of lowercase letters, digits and single hyphens; `description` ≤ 1024 chars **[volatile]**, written in the third person, saying what the skill does and when to use it; on Claude, no "anthropic" or "claude" in `name`.
- [ ] Keep each `SKILL.md` body under 500 lines (the spec recommends < 5000 tokens) **[volatile]**, link reference files one level deep, and start any reference file over 100 lines with a table of contents.
- [ ] Validate each skill with `skills-ref validate ./my-skill` before shipping.
- [ ] Install skills where the runtime looks: Claude tools read `.claude/skills` (Managed Agents can load a GitHub repo's `.claude/skills` **[volatile]**); Codex reads `.agents/skills` from cwd up to the repo root, `$HOME/.agents/skills` and `/etc/codex/skills` **[volatile]**.
- [ ] Write AGENTS.md with build, test and lint commands, code style, PR rules and security notes; add nested files where a package differs.
- [ ] Write each tool description like onboarding a new teammate: purpose, when not to use it, parameter meanings and units, one example; give parameters unambiguous names.
- [ ] Make tool errors actionable (what went wrong, how to fix it) and truncation notices explicit (how to fetch the rest).
- [ ] Store prompts, skills, tool schemas and agent configs in git; review by PR; tag releases; run the eval suite as a required check on every change (see `10-evals-and-release.md`).
- [ ] Move any OpenAI reusable prompt objects into code before 2026-11-30 **[volatile]**.
- [ ] Test every prompt and skill on each model tier you will run; small tiers usually need more explicit guidance.
- [ ] Remove time-sensitive statements ("before August, use the old API") from prompts and skills, or move them to a dated legacy section.
- [ ] Review third-party skills like code before installing them, because a skill can bundle scripts the agent will run (see `07-security.md`).

## Avoid
- One monolithic prompt holding every procedure → short system prompt plus Skills (always-loaded tokens dilute attention).
- Hard-coded if-else logic written as prose → principles plus canonical examples (brittle and never complete).
- Vague guidance that assumes shared context ("be helpful, use good judgment") → concrete heuristics and examples (too high an altitude gives the model nothing to act on).
- Wrapping every API endpoint as its own tool → a few task-shaped tools (more tools rarely improve outcomes and each one costs context).
- Pasting whole documents or tables "just in case" → references plus a fetch or search tool (context rot).
- Editing prompts in a vendor console or hosted registry → files in git with an eval gate (OpenAI's `v1/prompts` **[volatile]** is shutting down, and unreviewed edits bypass the gate).
- Skill files that reference further files that reference more → links one level deep from `SKILL.md` (agents may only preview nested files and miss content).
- First-person or vague skill descriptions ("I can help with documents") → third person with concrete trigger words (the description is the only text used to select a skill).
- Shipping a prompt or tool-description change without running evals → required eval gate (small wording changes shift behaviour noticeably).

## Additions (verified 2026-10-27)

- Check every context item in both directions: too little or in the wrong form (the model guesses), and too much or irrelevant (the model drifts and the cache breaks).
- Keep the prefix stable and the history append-only; serialize tool results and JSON deterministically (fixed key order, no timestamps in early blocks), because any byte change before a cache breakpoint discards everything after it.
- Compress restorably: drop only content that can be fetched again (a file, a URL, a record) and keep its path or ID in context so the agent can reload it.
- Keep failed actions and their errors in the history; removing them hides the evidence the model needs not to retry the same mistake.
- In long single loops, let the agent re-write a short task list at the end of its context (recitation) to keep the goal in recent attention; it costs tokens, so use it only when runs exceed a few dozen steps.
- When processing many similar items, vary the template or ordering slightly, because a context full of identical examples pushes the model into repeating the pattern even when the item differs.
- Keep AGENTS.md short (around 100 lines) as a map into a versioned `docs/` tree, and check its links and freshness in CI, because a long AGENTS.md crowds the context and goes stale ([OpenAI harness engineering](https://openai.com/index/harness-engineering/)).
- Brief agents and sub-agents with the goal, success criteria and a runnable check, not step-by-step instructions.

## Verify before relying
| Fact **[volatile]** | Snapshot (2026-10-27) | Where to check (URL) |
| --- | --- | --- |
| Agent Skills format limits | `name` ≤ 64 chars, `description` ≤ 1024, `compatibility` ≤ 500; body < 500 lines and < 5000 tokens recommended; metadata about 100 tokens | https://agentskills.io/specification |
| Claude skill-name rules | No XML tags; reserved words "anthropic", "claude" | https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices |
| Skills on the Claude API | Agent Skills and `/v1/skills` out of beta 2026-08-19; `skills-2025-10-02` header no longer required | https://platform.claude.com/docs/en/release-notes/overview |
| Managed Agents skills and versions | Sessions load skills from a GitHub repo's `.claude/skills` (2026-08-07); optional agent `version` on updates (2026-07-22) | https://platform.claude.com/docs/en/release-notes/overview |
| Codex skill locations | `.agents/skills` (cwd up to repo root), `$HOME/.agents/skills`, `/etc/codex/skills`; initial skill list capped at 2% of the context window by default | https://learn.chatgpt.com/docs/build-skills |
| AGENTS.md | Stewarded by the Agentic AI Foundation (Linux Foundation); over 60k projects; nearest file wins | https://agents.md/ |
| OpenAI hosted prompts | Prompt creation de-emphasized from 2026-06-03; `v1/prompts` shuts down 2026-11-30 | https://developers.openai.com/api/docs/guides/prompting |
| Claude Code tool-response cap | 25,000 tokens by default | https://www.anthropic.com/engineering/writing-tools-for-agents |

## Sources
- [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) — Anthropic Engineering, 2025-09-29
- [Writing effective tools for agents — with agents](https://www.anthropic.com/engineering/writing-tools-for-agents) — Anthropic Engineering, 2025-09-11
- [Agent Skills overview](https://agentskills.io/) — agentskills.io, no date shown, accessed 2026-10-27
- [Agent Skills specification](https://agentskills.io/specification) — agentskills.io, no date shown, accessed 2026-10-27
- [Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) — Anthropic, no date shown, accessed 2026-10-27
- [Claude Developer Platform release notes](https://platform.claude.com/docs/en/release-notes/overview) — Anthropic, entries through 2026-10-23
- [Managed Agents overview](https://platform.claude.com/docs/en/managed-agents/overview) — Anthropic, no date shown, accessed 2026-10-27
- [Build skills](https://learn.chatgpt.com/docs/build-skills) — OpenAI, no date shown, accessed 2026-10-27
- [Prompting guide](https://developers.openai.com/api/docs/guides/prompting) — OpenAI developer docs, accessed 2026-10-27
- [AGENTS.md](https://agents.md/) — agents.md (LF Projects), no date shown, accessed 2026-10-27
- [Agent Development Kit docs (Skills for Agents)](https://adk.dev/) — Google, no date shown, accessed 2026-10-27
