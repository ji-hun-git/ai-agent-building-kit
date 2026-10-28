# OpenAI Agents SDK

The HR assistant from [`examples/hr`](../../examples/hr) on the [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/). The tools, documents, prompt, policy and guard are the example's own; this folder moves each of the template's rules into the SDK's own mechanism, as the table in [Moving to a framework](../../README.md#moving-to-a-framework) says.

| Rule | Here |
| --- | --- |
| The user's own permissions | each `kit.Tool` becomes a `FunctionTool` whose first step is `policy().check`, with the user from the run context (`RunContextWrapper.context`); `is_enabled` hides tools the user can never call |
| Trifecta rule and lockdown | a `needs_approval` callable on every write and outbound tool, decided from the taint the run has accumulated |
| Approvals | `result.interruptions`, then `RunState.approve` or `reject(rejection_message=...)`, then `Runner.run(agent, state)` |
| Guard | an input guardrail (`run_in_parallel=False`) refuses a blocked prompt before the model starts, `Guard.data` runs inside each tool, `Guard.egress` before an outbound call is even offered for approval, and an output guardrail withholds a blocked answer |
| Run-once writes | `Toolbox.execute` inside each tool, with the run context as its session, so the ledger is keyed by `Toolbox.key`; `Context.dump` and `Context.load` carry it through `RunState.to_json()` and `from_json()` |
| Traces | the SDK's default exporter, which sends traces to OpenAI, is removed and tracing is off |

Two gaps in the SDK's hooks are closed in code. A guardrail can stop a run but not edit it, so the guard's rules (without the classifier) redact the prompt before the run and strip links and identifiers from the answer after it. And the SDK decides approvals for every call of a reply before it runs any of them, so a send planned in the same reply as the read that tainted the run would slip past `needs_approval`; the tool runs `Toolbox.execute` with the SDK's approval status, which refuses that call and tells the model to call again, and the next call asks the person.

## Run it

```
pip install -r integrations/openai_agents/requirements.txt
python -m integrations.openai_agents                                                # the tour, offline
python -m integrations.openai_agents --user hr
python -m integrations.openai_agents --model qwen3-vl:2b@http://127.0.0.1:11434/v1   # a local Ollama, free
python -m unittest tests.test_openai_agents                                         # offline
```

Run these from `template/`. Without `--model` the tour runs the template's gullible stand-in behind the SDK's `Model` interface, so you can watch the handbook's planted instruction stopped at the trifecta. `--model <id>@<base_url>` uses `OpenAIChatCompletionsModel` on any Chat Completions server (Ollama, vLLM, SGLang) with `LLM_API_KEY` or a placeholder as the key; the SDK never falls back to `OPENAI_API_KEY`. The tour asks four questions, each in a fresh conversation, and declines every approval: a grounded answer, the intern asking for the CEO's pay band, a leave request, and the handbook's planted instruction. The tests skip when the SDK is not installed.

Ollama sizes the context window by available memory, and on a small GPU it is 4,096 tokens. A 2B thinking model can fill that with reasoning alone, and the SDK sends the reasoning back with each turn, so the run then ends with `finish_reason='length'`. Start the server with `OLLAMA_CONTEXT_LENGTH=16384 ollama serve` to give it room.

```python
from integrations.openai_agents import build, chat_model

hr = build(chat_model("qwen3-vl:2b@http://127.0.0.1:11434/v1"))
conversation = hr.start(user)
print(await hr.ask(conversation, "Please request leave from 2026-11-02 to 2026-11-04.",
                   approve=lambda question: input(f"{question} [y/N] ") == "y"))
```

## What it does not cover

- Traces: register your own pipeline with `add_trace_processor()` and `set_tracing_disabled(False)`, and add spans for the guard and approvals.
- Streaming (`Runner.run_streamed`), the SDK's sessions, handoffs, hosted tools and MCP servers.
- Approvals that arrive later: `ask` waits for an answer within the turn. To pause for hours, store `result.to_state().to_json(context_serializer=Context.dump)` and resume with `RunState.from_json(..., context_deserializer=Context.load)` once someone decides; the tests show the round trip.
- A persistent ledger: pass the conversation's `id` and a database-backed mapping as `ledger` to `start`.
- The release gate: `kit.evals` still runs against `examples.hr:build`, not against this loop.
- Class and hook names are checked against `openai-agents==0.24.0`; check them again when you upgrade.
