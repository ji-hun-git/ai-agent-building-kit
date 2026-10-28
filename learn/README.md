# Learn to build an agent that holds up in production

Twelve lessons, from a first run to a shipped agent. Each one has a goal, something to read, something to run, one exercise that changes real code, and a check you can run yourself. They build on the three worked agents in [`template/examples`](../template/examples): an HR assistant (data and permissions), a support desk (money and approvals) and a research team (several agents).

You need Python 3.10 or newer and git. Nothing to install from PyPI until lesson 11. Lesson 9 is better with [Ollama](https://ollama.com), which runs open models locally for free. Allow about six hours in total; every lesson stands on its own after lesson 0.

| # | Lesson | You will be able to |
| --- | --- | --- |
| 0 | [Setup](#0-setup) | run the agents, the tests and the release gate |
| 1 | [Why agents fail](#1-why-agents-fail) | name the eight failures and the control for each |
| 2 | [The loop](#2-the-loop) | read a trace and say who decided what |
| 3 | [Tools, approvals, run-once](#3-tools-approvals-run-once) | add a tool with the right kind and approval |
| 4 | [Acting as the user](#4-acting-as-the-user) | write a permission rule over arguments |
| 5 | [Retrieval that cites and abstains](#5-retrieval-that-cites-and-abstains) | ground answers in your documents |
| 6 | [Prompt injection](#6-prompt-injection) | show why a fooled model still cannot leak |
| 7 | [The guard](#7-the-guard) | screen prompts, data, messages and answers |
| 8 | [Evals and the release gate](#8-evals-and-the-release-gate) | make a prompt edit fail the build |
| 9 | [A real model, free](#9-a-real-model-free) | tell a model's mistakes from the harness's |
| 10 | [Several agents](#10-several-agents) | split work across agents without losing control |
| 11 | [Moving to an SDK](#11-moving-to-an-sdk) | carry the rules into a vendor framework |
| 12 | [Shipping](#12-shipping) | leave a spec, a threat model and a gate behind |

All commands run from `template/` unless a lesson says otherwise.

---

### 0. Setup

**Run**

```
git clone https://github.com/ji-hun-git/ai-agent-building-kit
cd ai-agent-building-kit/template
python -m examples.hr
python -m unittest
python -m kit.evals examples/hr/cases.json --agent examples.hr:build --k 3
```

**Done when** the tour prints answers, the tests say `OK`, and the gate says `GATE PASSED`.

### 1. Why agents fail

**Read** [the ontology](../guide/ontology.md): the eight failures in the order a company meets them, and the architecture they force. Then the README's [ten layers](../README.md#the-ten-layers).

**Try** For each failure (the agent calls itself ChatGPT, invents policy, shows an intern the CEO's pay, follows a planted instruction, runs up the bill, cannot be debugged, regresses after a prompt edit), find the file in [`template/kit`](../template/kit) that closes it.

**Done when** you can name the control for every failure without looking.

### 2. The loop

**Read** [`kit/agent.py`](../template/kit/agent.py), `run` and `_loop`: the model proposes tool calls, the code decides whether they run.

**Run** `python -m examples.hr --trace trace.jsonl`, then open `trace.jsonl`. Each line is one step: `invoke_agent`, `chat` (a model call) or `execute_tool`, with the release version on every line.

**Try** Find the line where the stand-in model asks to post the CEO's pay band, and the line where the harness stops it. Then pass `capture=True` where [`examples/cli.py`](../template/examples/cli.py) creates the `Tracer`, run again, and see what content capture adds and why it is off by default.

**Done when** you can say, for the handbook question, which component made each decision.

### 3. Tools, approvals, run-once

**Read** [`kit/tools.py`](../template/kit/tools.py): every call passes the same checks in the same order. Then run `python -m examples.support` and watch the refund wait for a person.

**Try** Add a `cancel_order(ticket_id)` tool to [`examples/support`](../template/examples/support/__init__.py). Decide its kind (read, write or irreversible) and whether it is outbound. Give it a policy rule, then add a case to `examples/support/cases.json` that expects it to wait for approval and write nothing.

**Done when** `python -m kit.evals examples/support/cases.json --agent examples.support:build` passes with your case, and fails if you mark the tool `read`.

### 4. Acting as the user

**Read** [`kit/policy.py`](../template/kit/policy.py) and the support example's `within_limit`: a rule can read the call's arguments, so a limit lives in code, not in the prompt.

**Try** In [`examples/hr`](../template/examples/hr/__init__.py), add a `finance` role that may read anyone's pay band but not post to `#hr-team`. Add two cases: finance can read the CEO's band; finance cannot post it.

**Done when** both cases and the existing intern case pass. Ask yourself: what would a prompt-only rule have done when a document told the model to ignore it?

### 5. Retrieval that cites and abstains

**Read** [`kit/retrieval.py`](../template/kit/retrieval.py) and the [retrieval ladder](../sota/ladders.md#retrieval).

**Try** Add `examples/hr/docs/parking.md` with a heading and two facts, and a case that asks about one of them and expects the fact and the `parking` citation. Then ask something the documents do not cover and confirm the agent says it could not find it. With Ollama running, try dense search: `Index(docs, embed=Embeddings("nomic-embed-text", "http://127.0.0.1:11434/v1"))`, and ask "How much vacation do I get?", which shares no word with the leave policy.

**Done when** your case passes, and you can explain why the agent abstains instead of guessing.

### 6. Prompt injection

**Read** [Step 7 of the guide](../guide/agent-101.md#step-7--security-against-prompt-injection) and the [injection ladder](../sota/ladders.md#prompt-injection-and-hijacking).

**Run** `python -m examples.hr` and `python -m examples.hr --no-guard`, and compare the handbook, benefits and password turns.

**Try** Plant the same kind of instruction in another document, for example a line in `docs/leave-policy.md` starting `Assistant:` that asks for the CEO's pay band to be posted. Write a safety case that asks about leave as an HR user and expects nothing written and no `P9` in the answer.

**Done when** your case passes with the stand-in, which obeys the instruction, and you can say which rule stopped it: permissions, the trifecta rule, or lockdown.

### 7. The guard

**Read** [`kit/guard.py`](../template/kit/guard.py): the four checkpoints and what each rule promises.

**Try** Your company issues tokens like `acme_` followed by 32 lowercase letters and digits. Add that format to `SECRETS`, then a test in `tests/test_guard.py` that it is redacted in a prompt and refused in an outbound message. Build the token in the test from pieces, so the repository never contains one.

**Done when** `python -m unittest tests.test_guard` passes.

### 8. Evals and the release gate

**Read** [`kit/evals.py`](../template/kit/evals.py) and [`kit/release.py`](../template/kit/release.py).

**Try** Change the first line of `examples/hr/prompt.md` to "You are a helpful assistant." Run the gate and watch the identity case fail and the release version change. Restore it. Then explain why the gate needs every safety case to pass on all k trials (`--k 3`), not on most.

**Done when** you have seen the gate fail on a one-line prompt edit.

### 9. A real model, free

**Run** with Ollama installed: `ollama pull qwen3-vl:2b`, then

```
python -m examples.hr --model openai:qwen3-vl:2b@http://127.0.0.1:11434/v1
python -m kit.evals examples/hr/cases.json --agent examples.hr:build --model openai:qwen3-vl:2b@http://127.0.0.1:11434/v1 --k 1
```

Try the other two adapters too: `anthropic:qwen3-vl:2b@http://127.0.0.1:11434/v1` and `responses:qwen3-vl:2b@http://127.0.0.1:11434/v1`.

**Try** For each failing case, decide whether the model got it wrong (wrong tool, wrong words) or the harness did (an error, a leak). A small model misses many cases; the guard and permission cases should still pass.

**Done when** you can sort every failure into one of the two.

### 10. Several agents

**Read** [`examples/research`](../template/examples/research/__init__.py): a lead hands questions to researchers who each start clean, search with one read-only tool, and return a short cited answer. Only the lead can save.

**Run** `python -m examples.research` and `python -m examples.research --no-guard`, and compare the second turn.

**Try** Add a note about colours to `examples/research/docs` and a case that asks about battery and colour together.

**Done when** your case passes. Then say what would go wrong if researchers could save, and what the lead never sees.

### 11. Moving to an SDK

**Read** [Moving to a framework](../template/README.md#moving-to-a-framework) and [`template/integrations`](../template/integrations): the HR agent rebuilt on the OpenAI Agents SDK and on the Claude Agent SDK, with the same rules in each SDK's own hooks.

**Run** one of them, in a virtual environment of its own:

```
pip install -r integrations/openai_agents/requirements.txt
python -m unittest tests.test_openai_agents
python -m integrations.openai_agents                                                # offline, the stand-in model
python -m integrations.openai_agents --model qwen3-vl:2b@http://127.0.0.1:11434/v1   # Ollama
```

```
pip install -r integrations/claude_agent_sdk/requirements.txt
python -m unittest tests.test_claude_agent_sdk
python -m integrations.claude_agent_sdk --model qwen3-vl:2b --base-url http://127.0.0.1:11434 --max-tokens 4096   # Ollama
```

**Try** Pick one rule and find it in both ports: where the user's permissions are checked, where a write waits for a person, and what happens if that gate is bypassed. Then take your `finance` role from lesson 4 and confirm that both ports pick it up without a change, because they reuse the example's policy.

**Done when** the port's tests pass, and you can say which SDK hook holds each rule and which rule the SDK could not hold on its own.

### 12. Shipping

**Read** [Agent 101](../guide/agent-101.md) end to end, the [upgrade ladders](../sota/ladders.md) for the layers you will climb, and the [skill](../skill/README.md).

**Try** For an agent you actually need, fill in the skill's [spec](../skill/building-ai-agents/templates/agent-spec.md), [eval plan](../skill/building-ai-agents/templates/eval-plan.md), [threat model](../skill/building-ai-agents/templates/threat-model.md) and [stack lock](../skill/building-ai-agents/templates/stack-lock.md), and write its `cases.json` before its code.

**Done when** a person who has not seen your agent could run its gate and tell whether it may ship.
