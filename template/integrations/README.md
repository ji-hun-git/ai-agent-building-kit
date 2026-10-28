# integrations

The HR assistant from [`examples/hr`](../examples/hr) rebuilt on two vendor agent SDKs. Each port reuses the example's own tools, documents, prompt, policy and guard, so a rule you change there changes here too; only the agent loop is the SDK's. Each folder pins its own requirements, and its tests run offline and skip when the SDK is not installed.

| Port | SDK | Offline | With a local model (Ollama) |
| --- | --- | --- | --- |
| [`openai_agents`](openai_agents) | [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) | the tour with a stand-in model, and the tests | `python -m integrations.openai_agents --model qwen3-vl:2b@http://127.0.0.1:11434/v1` |
| [`claude_agent_sdk`](claude_agent_sdk) | [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk-python) | the tests; the tour needs a model, because the SDK drives the Claude Code CLI | `python -m integrations.claude_agent_sdk --model qwen3-vl:2b --base-url http://127.0.0.1:11434 --max-tokens 4096` |

Where each rule goes:

| Rule | OpenAI Agents SDK | Claude Agent SDK |
| --- | --- | --- |
| The user's own permissions | a check at the top of every tool; `is_enabled` hides tools the user can never call | a `PreToolUse` hook on every call; deny rules for tools the user can never call |
| Trifecta rule and lockdown | `needs_approval`, decided from the run's taint, and checked again when the tool runs | the same hook answers `ask` from the session's taint |
| Approvals | `result.interruptions`, then `approve` or `reject` on the `RunState` | `can_use_tool` asks the person |
| Guard | input and output guardrails, `Guard.data` inside every tool, `Guard.egress` before anything goes out | the prompt guard before the query, `Guard.data` inside every tool, `Guard.egress` in the hook, the output guard on the final text |
| Run-once writes | the ledger in the run context, carried through `RunState.to_json` | `Toolbox.execute` inside each tool, with the ledger keyed by `Toolbox.key` |
| If a gate is bypassed | the tool refuses a call that needed a person | the tool refuses a call that needed a person |

Each SDK needed one rule held somewhere it did not offer. The OpenAI SDK decides approvals for every call in a reply before it runs any of them, so a send planned before a private read would pass; the tool checks again when it runs. The Claude SDK skips the permission callback when a hook allows a call, so the hook never allows; it only denies or asks.

Hook and option names change between releases. Both ports are checked against the versions in their `requirements.txt`; check them again when you upgrade. [Moving to a framework](../README.md#moving-to-a-framework) maps the same rules onto any other framework.
