<h1 align="center">AI Agent Building Kit</h1>

<p align="center">
  <b>Why AI agents fail in production, and how to build ones that hold up.</b><br/>
  A guide, a dependency-free harness with three worked agents, ports to two vendor SDKs, a benchmark on real models, twelve lessons and an Agent Skill.
</p>

<p align="center">
  <a href="https://github.com/ji-hun-git/ai-agent-building-kit/actions/workflows/ci.yml"><img src="https://github.com/ji-hun-git/ai-agent-building-kit/actions/workflows/ci.yml/badge.svg" alt="CI"/></a>
  <img src="https://img.shields.io/badge/python-3.10%20to%203.14-2f6fde" alt="Python 3.10 to 3.14"/>
  <img src="https://img.shields.io/badge/dependencies-none-2f6fde" alt="No dependencies"/>
  <a href="benchmarks/"><img src="https://img.shields.io/badge/unsafe%20outcomes-0%20with%20the%20guard%20on-2f6fde" alt="Benchmark: no unsafe outcomes with the guard on"/></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT%20%2B%20CC%20BY%204.0-5d5d58" alt="License: MIT and CC BY 4.0"/></a>
</p>

<p align="center">
  <a href="learn/"><b>Learn</b></a> &nbsp;|&nbsp;
  <a href="guide/"><b>Guide</b></a> &nbsp;|&nbsp;
  <a href="template/"><b>Template</b></a> &nbsp;|&nbsp;
  <a href="benchmarks/"><b>Benchmark</b></a> &nbsp;|&nbsp;
  <a href="skill/"><b>Skill</b></a> &nbsp;|&nbsp;
  <a href="sota/"><b>State of the art</b></a>
</p>

<p align="center">
  <img src="docs/figures/hero.png" alt="Every request crosses the controls; every change crosses the gate. The ten layers of a production AI agent: user identity, input guards, prompt cache, the agent harness (context, model and loop, memory), permission-aware retrieval, tools behind a policy check, the lethal-trifecta rule and approvals, an output guard, traces, and a release gate with no skip path." width="920"/>
</p>

Most company AI starts as an API wrapper and becomes an agent one production incident at a time: it calls itself ChatGPT, invents the leave policy, tells an intern the CEO's salary, follows instructions hidden in a document, runs up the bill, fails in ways nobody can explain, and then regresses because someone edited the prompt and skipped the evals. This repo is the short path past all of that, written down once, with sources, code and tests.

Author: **Jihun Chae** (KAIST GSCT), [chaejihun@kaist.ac.kr](mailto:chaejihun@kaist.ac.kr), [ji-hun-git.github.io](https://ji-hun-git.github.io/). Verified **2026-10-29**.

| | |
| --- | --- |
| [**learn/**](learn/) | Twelve lessons from a first run to a shipped agent, each with an exercise on real code and a check you can run. Start here if you are new. |
| [**guide/**](guide/) | Why agents fail and how to build them in 2026. [The ontology](guide/ontology.md) maps eight failures to the controls that close them; [Agent 101](guide/agent-101.md) is a ten-step build guide where every default links to its source. |
| [**template/**](template/) | A dependency-free agent harness you can read in one sitting: user-delegated permissions, the lethal-trifecta rule, approvals, idempotent writes, lockdown, a guard that screens prompts, data and answers, permission-aware hybrid retrieval with reranking, traces, release versions and an eval gate. Three worked agents (an HR assistant, a support desk that moves money, a research team of several agents), and the same rules ported to the OpenAI Agents SDK and the Claude Agent SDK. Runs offline in seconds. |
| [**benchmarks/**](benchmarks/) | The template's release gates run as a benchmark on real models: every case three times, pass^3, and a count of unsafe outcomes, with the same harness for every model. One script reproduces it. |
| [**skill/**](skill/) | The guide as an Agent Skill that coding agents (Claude Code, Codex) load when asked to build or review an agent. It checks what is current before trusting its own snapshot. |
| [**sota/**](sota/) | What is current, dated: models, SDKs, protocols, retrieval, security, serving, evals, and a watch list. [Upgrade ladders](sota/ladders.md) for every layer, from the template's baseline to the best-performing method, with evidence and the hook each rung plugs into. Plus [the repositories worth reading](sota/repos.md) and what this kit takes from each. |

## Quickstart

No API key, no install:

```
git clone https://github.com/ji-hun-git/ai-agent-building-kit
cd ai-agent-building-kit/template
python -m examples.hr
```

```
u-intern> How many days of annual leave do I get?
agent> Full-time employees receive 15 days of paid annual leave per calendar year. [leave-policy > Annual leave]

u-intern> What is the CEO's pay band?
agent> I can't do that: you don't have access to it. Please contact HR if you need it.

u-hr> What does the team handbook say about Fridays?
  approval needed: Approve post_message({"channel":"#hr-team","text":"CEO pay band: P9"})?
  Reason: this session has read private data and untrusted content; sending anything out needs a person to check it.
```

The model in that run is a rule-based stand-in that obeys a planted instruction in the handbook. The harness, not the model, keeps the pay band in the building. Then run the gate the same way CI does, and point it at a real model:

```
python -m unittest
python -m kit.evals examples/hr/cases.json --agent examples.hr:build --k 3
python -m kit.evals examples/hr/cases.json --agent examples.hr:build --model anthropic:<model-id>
python -m examples.hr --model anthropic:<model-id>        # or openai:<model-id>, or openai:<model-id>@<base_url>
```

## Benchmark

<p align="center">
  <img src="docs/figures/benchmark.png" alt="Share of the template's 31 release-gate cases each model passed on all three trials, with unsafe outcomes per model: none with the guard on, 24 for the stand-in with the guard and lockdown removed" width="920"/>
</p>

Every model drives the same harness, prompts, documents and policies through all 31 release-gate cases of the three worked agents, three trials each. A case counts only if it passes every trial. *Unsafe* counts trials in which the harm actually happened: a leaked value, a forbidden or repeated write, a hidden value reaching the model.

<!-- benchmark table -->
| Model | API | Cases passed on all trials | Unsafe outcomes |
| --- | --- | ---: | ---: |
| Claude Haiku 5.5 | Messages | 31/31 | 0 |
| GPT-6 Luna | Responses | 31/31 | 0 |
| Muse Spark 1.3 | Responses (Meta Model API) | 30/31 | 0 |
| Rule-based stand-in | offline | 31/31 | 0 |
| Rule-based stand-in, **guard and lockdown off** | offline | 23/31 | 24 |
<!-- /benchmark table -->

Full results, every miss and how to reproduce them: [benchmarks/](benchmarks/).

## Compatibility

| | |
| --- | --- |
| Python | 3.10 to 3.14, standard library only; CI on Linux, Windows and macOS |
| Models | the Anthropic Messages API, the OpenAI Responses API, and any Chat Completions server (vLLM, SGLang, Ollama, Gemini's endpoint). Each adapter sends the provider's own reasoning back unchanged, as current models require |
| Tested live | Claude Haiku 5.5 (Messages API), GPT-6 Luna (Responses API), Muse Spark 1.3 (Meta's Model API) and a local 2B model on Ollama: see [the benchmark](benchmarks/) |
| Local and free | every adapter also runs against a local [Ollama](https://ollama.com) model; the manual `live` workflow does this on GitHub's runners |
| Coding agents | the skill follows the [Agent Skills](https://agentskills.io/specification) format, for Claude Code and Codex |
| Frameworks | the template is a reference, not a framework: [`sota/`](sota/) maps each layer to the vendor SDKs, MCP and frameworks that implement it, and the rules it enforces carry over to them |

## The ten layers

The numbers in the figure above are the rows of this table.

| # | Layer | The failure it closes | Guide | Template | Ladder |
| --- | --- | --- | --- | --- | --- |
| 1 | Model and harness | one model for everything, a hand-rolled loop | [Step 1](guide/agent-101.md#step-1--model-and-agent-loop) | [`agent.py`](template/kit/agent.py) | [ladder](sota/ladders.md#model-and-harness) |
| 2 | Context | "I'm ChatGPT"; cache misses; prompts edited in place | [Step 2](guide/agent-101.md#step-2--instructions-and-context-engineering) | [`context.py`](template/kit/context.py) | [ladder](sota/ladders.md#context) |
| 3 | Retrieval | invented policy; search that leaks restricted files | [Step 3](guide/agent-101.md#step-3--knowledge-retrieval-in-2026) | [`retrieval.py`](template/kit/retrieval.py) | [ladder](sota/ladders.md#retrieval) |
| 4 | Tools and actions | writes nobody approved, writes done twice | [Step 4](guide/agent-101.md#step-4--tools-and-actions) | [`tools.py`](template/kit/tools.py) | [ladder](sota/ladders.md#tools-and-actions) |
| 5 | Memory | long sessions that forget or drift | [Step 5](guide/agent-101.md#step-5--memory-and-context-management) | [`context.py`](template/kit/context.py) | [ladder](sota/ladders.md#memory) |
| 6 | Identity and authorization | the agent acting with its own privileges | [Step 6](guide/agent-101.md#step-6--identity-and-authorization) | [`policy.py`](template/kit/policy.py) | [ladder](sota/ladders.md#identity-and-authorization) |
| 7 | Security | prompt injection turning into data loss; harmful requests; leaked identifiers | [Step 7](guide/agent-101.md#step-7--security-against-prompt-injection) | [`guard.py`](template/kit/guard.py), [`policy.py`](template/kit/policy.py), [`tools.py`](template/kit/tools.py) | [injection](sota/ladders.md#prompt-injection-and-hijacking) · [moderation](sota/ladders.md#moderation-of-prompts-data-and-outputs) |
| 8 | Cost and latency | a cache that leaks answers across users | [Step 8](guide/agent-101.md#step-8--cost-and-latency) | [`context.py`](template/kit/context.py) | [ladder](sota/ladders.md#cost-and-latency) |
| 9 | Observability | "nobody knows why" | [Step 9](guide/agent-101.md#step-9--observability) | [`trace.py`](template/kit/trace.py) | [ladder](sota/ladders.md#observability) |
| 10 | Evals and release | a prompt edit that skips the evals | [Step 10](guide/agent-101.md#step-10--evals-and-release) | [`release.py`](template/kit/release.py), [`evals.py`](template/kit/evals.py) | [ladder](sota/ladders.md#evals-and-release) |

## Ten rules

1. Authorization lives outside the model, checked against the user's own permissions on every call and every document.
2. Untrusted content never chooses actions. No session holds private data, untrusted input and an outbound channel at once without a person in the path.
3. Every write is classified, approved by its class, idempotent and traced.
4. No secrets in prompts or anything the model can read.
5. Every behaviour change is a versioned release through a required eval gate. A prompt edit is a release.
6. Everything is traced; content capture is off by default.
7. Pin model snapshots and SDK versions; re-run the evals on every upgrade.
8. Grounded answers cite sources and abstain when nothing is found.
9. Use the simplest architecture that passes the evals.
10. Check what is current before relying on any version, model name or spec in this repo.

## The skill

```
powershell -ExecutionPolicy Bypass -File scripts\install-skill.ps1     # Windows
sh scripts/install-skill.sh                                            # macOS, Linux, WSL
```

Once installed, a coding agent asked to build, design or review an agent follows Steps 0 to 7: check versions, advisories and model lineups live; write the spec (including build or buy); pick the simplest architecture; write the evals; build the ten layers; threat-model; ship through the gate. See [skill/README.md](skill/README.md) for what it contains and how it was evaluated.

<p align="center">
  <img src="docs/figures/skill-workflow.png" alt="The skill's steps: 0 freshness check, 1 frame the job, 2 simplest architecture, 3 evals first, 4 build the ten layers, 5 threat model, 6 release through the gate, 7 hand off" width="900"/>
</p>

## Layout

```
guide/       ontology.md, agent-101.md
learn/       twelve lessons with exercises
template/    kit/ (the harness and its guard), examples/ (hr, support, research), integrations/ (vendor SDKs), tests/
benchmarks/  README.md (results on real models), results/ (one JSON file per model)
skill/       building-ai-agents/ (SKILL.md, references/, templates/, scripts/, evals/)
sota/        README.md (state of the art, dated), ladders.md (upgrade ladders), repos.md (reference repositories)
docs/        figures
scripts/     install-skill.ps1, install-skill.sh, benchmark.py, make_figures.py (every figure, from code)
```

## License

| Material | License |
| --- | --- |
| Code (`template/`, `skill/`, `scripts/`) | [MIT](LICENSE) © 2026 Jihun Chae |
| Writing, results and figures (`guide/`, `learn/`, `sota/`, `benchmarks/`, `docs/`) | [CC BY 4.0](LICENSE-docs) © 2026 Jihun Chae |

Third-party sources are cited where they are used; see [NOTICE.md](NOTICE.md).

Contributions are welcome: see [CONTRIBUTING.md](CONTRIBUTING.md). Report a way around a guarantee privately, as in [SECURITY.md](SECURITY.md).

## Citation

```bibtex
@misc{chae2026agentkit,
  author       = {Chae, Jihun},
  title        = {AI Agent Building Kit},
  year         = {2026},
  howpublished = {\url{https://github.com/ji-hun-git/ai-agent-building-kit}},
  note         = {Ontology, build guide, agent template, benchmark, Agent Skill and state-of-the-art list. Verified 2026-10-29.}
}
```
