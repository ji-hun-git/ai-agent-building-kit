"""The HR assistant on the Claude Agent SDK, with the template's rules held by the SDK's own gates.

    deny rules        no built-in file, shell or web tools (tools=[]), no settings files or other MCP
                      servers, and HR tools the user can never call are removed (disallowed_tools)
    PreToolUse hook   on every call: a known HR tool, its arguments, the user's permissions, the egress
                      guard, then the trifecta rule, lockdown and approvals, which send the call to a
                      person; it never allows, because a hook's allow skips can_use_tool
    can_use_tool      decides again from the session as it is now, and asks the person
    inside each tool  Toolbox.execute: the idempotency ledger, the session's taint, errors as sentences,
                      and, if the gates above were bypassed, a refusal; then the data guard on the result
    around the query  the prompt guard before it, the output guard on the final text

The tools, documents, prompt, policy and guard are examples.hr's own; only the loop is the SDK's.
Every SDK name is written sdk.<name>. Option, hook and callback names change between releases:
this module is checked against the version pinned in requirements.txt.
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable

from examples.hr import build
from kit import Call, NeedsApproval, Pending, Result, Tool, User
from kit.context import dumps

try:
    import claude_agent_sdk as sdk
except ImportError:  # importable without it, so the stdlib-only test run can discover and skip its tests
    sdk = None

SERVER = "hr"
PREFIX = f"mcp__{SERVER}__"  # the CLI's name for a tool of an in-process server
DECLINED = "The user declined. Nothing was done."
TOO_LONG = "I stopped because this took too many steps. Please narrow the request."

Approve = Callable[[Pending], bool | Awaitable[bool]]  # the person: yes or no to one call


def decline(pending: Pending) -> bool:
    return False


def local(name: str) -> str:
    """The HR tool's own name, from the name the CLI gives it."""
    return name[len(PREFIX):] if name.startswith(PREFIX) else name


class Conversation:
    """One conversation with one user: the rules' state (taint, ledger, approvals) and the adapters
    that read it. Start a new one per conversation. To keep writes run-once across restarts, pass
    the conversation's id and a persistent mapping as the ledger, as with Agent.start."""

    def __init__(self, user: User, approve: Approve = decline, guarded: bool = True,
                 session_id: str | None = None, ledger=None):
        if sdk is None:
            raise ImportError("claude-agent-sdk is not installed: pip install -r integrations/claude_agent_sdk/requirements.txt")
        hr = build(guarded=guarded)  # examples.hr: tools, guarded index, policy, lockdown, prompt, guard
        self.user, self.approve = user, approve
        self.toolbox, self.guard, self.system = hr.toolbox, hr.guard, hr.system
        self.session = hr.start(user, session_id, ledger)  # id, taint and ledger, as in the template
        self.approved: set[str] = set()                     # ledger keys a person said yes to, used once

    def options(self, **settings) -> sdk.ClaudeAgentOptions:
        """SDK options for this conversation; `settings` adds or overrides fields (model, env, cwd)."""
        names = sorted(self.toolbox.tools)
        hidden = [n for n in names if not self.toolbox.policy.visible(self.user, n)]
        base = dict(
            system_prompt=self.system,
            tools=[],                    # no built-in tools at all
            mcp_servers={SERVER: sdk.create_sdk_mcp_server(SERVER, tools=self.sdk_tools())},
            strict_mcp_config=True,      # no MCP servers from anywhere else
            setting_sources=[],          # no settings files: their allow rules and hooks would apply too
            skills=[],
            allowed_tools=[],            # no allow rules: a whole-tool allow skips can_use_tool
            disallowed_tools=[PREFIX + n for n in hidden],
            permission_mode="default",   # "dontAsk" denies without asking; "bypassPermissions" skips the callback
            hooks={"PreToolUse": [sdk.HookMatcher(matcher=None, hooks=[self.pre_tool_use])]},
            can_use_tool=self.can_use_tool,
            verbatim_prompts=True,       # "@path" in a message must not make the CLI read a local file
            max_turns=8,
        )
        return sdk.ClaudeAgentOptions(**{**base, **settings})

    def sdk_tools(self) -> list[sdk.SdkMcpTool]:
        return [self._sdk_tool(t) for _, t in sorted(self.toolbox.tools.items())]

    def _sdk_tool(self, t: Tool) -> sdk.SdkMcpTool:
        hints = sdk.ToolAnnotations(readOnlyHint=t.kind == "read", destructiveHint=t.kind == "irreversible",
                                    openWorldHint=t.outbound)

        @sdk.tool(t.name, t.description, t.schema()["input_schema"], annotations=hints)
        async def handler(args: dict) -> dict:
            result = self.run(t.name, args)
            return {"content": [{"type": "text", "text": result.content}], "is_error": result.is_error}
        return handler

    def decide(self, name: str, args: dict) -> tuple[str, str]:
        """"allow", "ask" or "deny", and why: Toolbox.execute's checks in its order, without running
        anything, with the egress guard after the user's permissions."""
        tool = self.toolbox.tools.get(local(name))
        if tool is None:
            return "deny", f"Unknown tool '{name}'. Available: {', '.join(sorted(self.toolbox.tools))}."
        missing = [p for p in tool.required if p not in args]
        if missing:
            return "deny", f"Missing required argument(s) for {tool.name}: {', '.join(missing)}."
        ok, why = self.toolbox.policy.check(self.user, tool.name, args)
        if not ok:
            return "deny", f"Denied: {why}. Tell the user you cannot do this."
        if self.guard and tool.outbound and (out := self.guard.egress(dumps(args))).findings:
            rules = ", ".join(sorted({f.rule for f in out.findings}))
            return "deny", (f"Blocked: this message would carry {rules} out of the session. "
                            "Do not retry; tell the user what was blocked.")
        if tool.kind != "read" and self._key(tool.name, args) in self.session.ledger:
            return "allow", "already done in this session"
        taint = self.session.taint
        if taint.blocks(tool.outbound):
            return "ask", ("this session has read private data and untrusted content; "
                           "sending anything out needs a person to check it")
        if self.toolbox.lockdown and tool.kind != "read" and taint.untrusted:
            return "ask", "this session has read untrusted content, and in lockdown every action after that needs a person"
        if tool.needs_approval:
            return "ask", f"{tool.name} is {'an' if tool.kind[0] in 'aeiou' else 'a'} {tool.kind} action"
        return "allow", ""

    async def pre_tool_use(self, data: dict, tool_use_id: str | None, context: dict) -> dict:
        """The PreToolUse hook. Denies what the rules forbid and sends to a person what needs one."""
        decision, reason = self.decide(data["tool_name"], data["tool_input"])
        if decision == "allow":
            return {}
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": decision,
                                       "permissionDecisionReason": reason}}

    async def can_use_tool(self, name: str, args: dict, context: sdk.ToolPermissionContext) -> sdk.PermissionResult:
        """The permission callback: every call the hook passed on reaches it, since there are no allow rules."""
        decision, reason = self.decide(name, args)
        if decision == "deny":
            return sdk.PermissionResultDeny(message=reason)
        if decision == "ask":
            answer = self.approve(Pending(Call(context.tool_use_id or "", local(name), args), reason))
            if inspect.isawaitable(answer):
                answer = await answer
            if not answer:
                return sdk.PermissionResultDeny(message=DECLINED)
            self.approved.add(self._key(local(name), args))
        return sdk.PermissionResultAllow()

    def run(self, name: str, args: dict) -> Result:
        """Inside each tool, after the gates: the toolbox runs the call, and the data guard screens
        what comes back, error messages included."""
        call = Call("", name, args)
        key = self.toolbox.key(self.session, call)
        approved = key in self.approved
        self.approved.discard(key)
        try:
            result = self.toolbox.execute(call, self.user, self.session, approved=approved)
        except NeedsApproval as e:  # the gates were bypassed (an allow rule, bypassPermissions): fail closed
            result = Result(f"Not done: {e.reason}, and no person approved this call.", True)
        if self.guard:
            verdict = self.guard.data(result.content)
            result = Result("This result was withheld by the content guard." if verdict.blocked
                            else verdict.text, result.is_error)
        return result

    def _key(self, name: str, args: dict) -> str:
        return self.toolbox.key(self.session, Call("", name, args))

    async def turn(self, client, text: str) -> str:
        """One user message through a connected ClaudeSDKClient: the prompt guard before the query,
        the output guard on the final text. An approval from an earlier turn never carries over."""
        self.approved.clear()
        if self.guard:
            verdict = self.guard.prompt(text)
            if verdict.blocked:  # the model never sees a request the guard refused
                return self.guard.refusal
            text = verdict.text
        await client.query(text)
        final, failed = "", ""
        async for message in client.receive_response():  # read to the end, so the next turn starts clean
            if isinstance(message, sdk.AssistantMessage):
                failed = failed or (message.error or "")
                final = "".join(b.text for b in message.content if isinstance(b, sdk.TextBlock)) or final
            elif isinstance(message, sdk.ResultMessage):
                if message.subtype == "error_max_turns":
                    return TOO_LONG
                if message.is_error:
                    failed = "; ".join(message.errors or []) or message.result or failed or message.subtype
                final = message.result or final
        if failed:
            return f"(the model call failed: {failed})"
        if not final.strip():
            final = "The model returned an empty answer. Please ask again."
        if self.guard:  # the final answer, before the user sees it
            verdict = self.guard.output(final)
            final = self.guard.withheld if verdict.blocked else verdict.text
        return final
