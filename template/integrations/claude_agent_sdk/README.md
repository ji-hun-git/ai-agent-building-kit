# Claude Agent SDK

The HR assistant from [`examples/hr`](../../examples/hr) on the [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk-python), which runs Claude Code's agent loop in your process. The tools, documents, prompt, policy and guard are the example's own; this folder moves each of the template's rules into the SDK's own mechanism, as the table in [Moving to a framework](../../README.md#moving-to-a-framework) says.

| Rule | Here |
| --- | --- |
| HR tools only | each `kit.Tool` becomes an in-process tool (`@tool`, `create_sdk_mcp_server`); `tools=[]` loads no built-in file, shell or web tools; `setting_sources=[]` and `strict_mcp_config=True` keep settings files and other MCP servers out |
| The user's own permissions | deny rules (`disallowed_tools`) for tools the user can never call, and a `PreToolUse` hook that runs `policy().check` on every call and denies with the reason |
| Trifecta rule and lockdown | the same hook reads the session's taint and answers `ask`, which sends the call to the permission callback |
| Approvals | `can_use_tool` decides again and asks the person; with no allow rules, every call reaches it |
| Guard | `Guard.prompt` before the query, `Guard.data` inside each tool, `Guard.egress` in the hook, `Guard.output` on the final text |
| Run-once writes | `Toolbox.execute` inside each tool, with the ledger keyed by `Toolbox.key` |

The hook never answers `allow`, because an allow from a hook skips `can_use_tool`. If the gates are bypassed anyway (an allow rule, `bypassPermissions`), the tool itself refuses a call that needed a person, so a misconfiguration fails closed.

## Run it

```
pip install -r integrations/claude_agent_sdk/requirements.txt
python -m integrations.claude_agent_sdk                       # the tour, as the intern
python -m integrations.claude_agent_sdk --user hr
python -m integrations.claude_agent_sdk --model <model-id>
python -m integrations.claude_agent_sdk --model qwen3-vl:2b --base-url http://127.0.0.1:11434 --max-tokens 4096   # a local Ollama, free
python -m unittest tests.test_claude_agent_sdk                # offline: hook, callback and tools called directly
```

Run these from `template/`. The SDK drives the Claude Code CLI bundled in its wheel, with the CLI's own sign-in or `ANTHROPIC_API_KEY`. `--base-url` sends the CLI's model requests to that server instead, with `LLM_API_KEY` or a placeholder as the key, blanks any inherited Anthropic token, and turns off the CLI's nonessential traffic. The tour asks five questions, each in a fresh conversation: a grounded answer, the CEO's pay band, a leave request (declined at the approval), the handbook's planted instruction, and a threat the prompt guard refuses before the CLI sees it. The tests skip when the SDK is not installed.

```python
from claude_agent_sdk import ClaudeSDKClient
from integrations.claude_agent_sdk import Conversation

hr = Conversation(user, approve=lambda pending: input(f"{pending} [y/N] ") == "y")
async with ClaudeSDKClient(hr.options(model="<model-id>")) as client:
    print(await hr.turn(client, "Please request leave from 2026-11-02 to 2026-11-04."))
```

## What it does not cover

- Traces: use the SDK's OpenTelemetry export, and add spans for the guard and approvals.
- Approvals that arrive later: `can_use_tool` waits for an answer within the run. To pause for hours, store the session, deny the call, and resume it with the SDK's `resume` option once someone decides.
- A persistent ledger: pass `session_id` and a database-backed mapping as `ledger`, as with `Agent.start`.
- The release gate: `kit.evals` still runs against `examples.hr:build`, not against this loop.
- Option and hook names are checked against `claude-agent-sdk==0.2.174`; check them again when you upgrade.
