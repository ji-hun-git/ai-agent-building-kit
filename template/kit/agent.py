"""The agent loop: the model proposes, code disposes.

    user -> [guard] -> model -> tool calls -> Toolbox (permissions, trifecta, approval, ledger)
         -> [guard] results -> model -> ... -> [guard] answer

The model never executes anything itself. When a call needs a person, the loop
stops and returns a Pending action that states exactly what will happen; the
caller shows it, and resumes with the person's decision.

With a Guard, the prompt is screened before the model sees it, every tool result
before it enters the context, every outbound call before it runs, and the answer
before the user sees it (see guard.py).

Models are plain callables: model(system, messages, tools) -> Reply. Three are
included: a scripted stand-in for tests, and thin adapters for the Anthropic
Messages API and any OpenAI-compatible Chat Completions API (OpenAI, vLLM,
SGLang, Ollama). Model names are configuration, never code; check the current
ones with skill/building-ai-agents/scripts/check_freshness.py.
"""

import json
import os
from dataclasses import dataclass, field

from .context import Session, dumps
from .guard import Guard
from .net import post
from .policy import User
from .tools import Call, NeedsApproval, Result, Toolbox
from .trace import Tracer


@dataclass
class Reply:
    text: str = ""
    calls: list[Call] = field(default_factory=list)
    usage: dict = field(default_factory=dict)


@dataclass
class Pending:
    call: Call
    reason: str

    def __str__(self) -> str:
        return f"Approve {self.call.name}({dumps(self.call.args)})? Reason: {self.reason}."


class Agent:
    def __init__(self, model, system: str, toolbox: Toolbox, tracer: Tracer | None = None,
                 model_id: str = "unset", max_steps: int = 8, guard: Guard | None = None):
        self.model, self.system, self.toolbox = model, system, toolbox
        self.tracer = tracer or Tracer()
        self.model_id, self.max_steps, self.guard = model_id, max_steps, guard

    def start(self, user: User) -> Session:
        """Freeze the prompt and this user's tool list for the whole session."""
        return Session(system=self.system, tools=self.toolbox.schemas(user))

    def run(self, session: Session, user: User, text: str) -> str | Pending:
        verdict = self.guard.prompt(text) if self.guard else None
        text = verdict.text if verdict else text
        with self.tracer.span("invoke_agent", **{"session.id": session.id, "content.input": text}) as span:
            session.append({"role": "user", "content": text})
            if verdict:
                span["guard.prompt"] = verdict.labels
                if verdict.blocked:  # the model never sees a request the guard refused
                    session.append({"role": "assistant", "content": self.guard.refusal, "calls": []})
                    return self.guard.refusal
            return self._loop(session, user, queue=[])

    def resume(self, session: Session, user: User, approved: bool) -> str | Pending:
        assert session.pending, "nothing is waiting for approval"
        call, queue = session.pending["call"], session.pending["queue"]
        session.pending = None
        with self.tracer.span("invoke_agent", **{"session.id": session.id, "approval.granted": approved}):
            if approved:
                self._execute(session, user, call, approved=True)
            else:
                session.append(_tool_msg(call, "The user declined. Nothing was done.", is_error=True))
            return self._loop(session, user, queue)

    def _loop(self, session: Session, user: User, queue: list[Call]) -> str | Pending:
        for _ in range(self.max_steps):
            while queue:  # finish the calls of the previous reply first
                call = queue.pop(0)
                try:
                    self._execute(session, user, call)
                except NeedsApproval as e:
                    session.pending = {"call": call, "queue": queue}
                    return Pending(call, e.reason)
            with self.tracer.span("chat", **{"gen_ai.request.model": self.model_id}) as span:
                reply = self.model(session.system, session.messages, session.tools)
                span.update({f"gen_ai.usage.{k}": v for k, v in reply.usage.items()})
                span["content.output"] = reply.text
                text = reply.text
                if self.guard and not reply.calls:  # the final answer, before the user sees it
                    verdict = self.guard.output(text)
                    span["guard.output"] = verdict.labels
                    text = self.guard.withheld if verdict.blocked else verdict.text
            session.append({"role": "assistant", "content": text,
                            "calls": [c.__dict__ for c in reply.calls]})
            if not reply.calls:
                return text
            queue = list(reply.calls)
        return "I stopped because this took too many steps. Please narrow the request."

    def _execute(self, session: Session, user: User, call: Call, approved: bool = False) -> None:
        tool = self.toolbox.tools.get(call.name)
        with self.tracer.span("execute_tool", **{"gen_ai.tool.name": call.name,
                                                 "content.arguments": dumps(call.args)}) as span:
            if self.guard and tool and tool.outbound and (out := self.guard.egress(dumps(call.args))).findings:
                span["guard.egress"] = out.labels
                rules = ", ".join(sorted({f.rule for f in out.findings}))
                result = Result(f"Blocked: this message would carry {rules} out of the session. "
                                "Do not retry; tell the user what was blocked.", True)
            else:
                result = self.toolbox.execute(call, user, session, approved=approved)
                if self.guard and not result.is_error:
                    verdict = self.guard.data(result.content)
                    span["guard.data"] = verdict.labels
                    result = Result("This result was withheld by the content guard." if verdict.blocked
                                    else verdict.text)
            span["tool.is_error"] = result.is_error
        session.append(_tool_msg(call, result.content, result.is_error))


def _tool_msg(call: Call, content: str, is_error: bool = False) -> dict:
    return {"role": "tool", "id": call.id, "name": call.name, "args": call.args,
            "content": content, "is_error": is_error}


# ---------------------------------------------------------------- models

class Scripted:
    """Returns replies from a list; for tests and offline demos."""

    def __init__(self, replies: list[Reply]):
        self.replies = list(replies)

    def __call__(self, system, messages, tools) -> Reply:
        return self.replies.pop(0) if self.replies else Reply("(no more scripted replies)")


class Anthropic:
    """Anthropic Messages API. The system prompt is marked cacheable."""

    def __init__(self, model: str, max_tokens: int = 2048, api_key: str | None = None,
                 url: str = "https://api.anthropic.com/v1/messages", version: str = "2023-06-01"):
        self.model, self.max_tokens, self.url, self.version = model, max_tokens, url, version
        self.api_key = api_key or os.environ["ANTHROPIC_API_KEY"]

    def __call__(self, system, messages, tools) -> Reply:
        body = {
            "model": self.model, "max_tokens": self.max_tokens,
            "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            "tools": tools, "messages": _to_anthropic(messages),
        }
        out = post(self.url, {"x-api-key": self.api_key, "anthropic-version": self.version}, body)
        text = "".join(b["text"] for b in out["content"] if b["type"] == "text")
        calls = [Call(b["id"], b["name"], b["input"]) for b in out["content"] if b["type"] == "tool_use"]
        return Reply(text, calls, out.get("usage", {}))


def _to_anthropic(messages) -> list[dict]:
    out = []
    for m in messages:
        if m["role"] == "user":
            out.append({"role": "user", "content": m["content"]})
        elif m["role"] == "assistant":
            blocks = [{"type": "text", "text": m["content"]}] if m["content"] else []
            blocks += [{"type": "tool_use", "id": c["id"], "name": c["name"], "input": c["args"]} for c in m["calls"]]
            out.append({"role": "assistant", "content": blocks})
        else:  # tool results ride in a user turn; consecutive ones share it
            block = {"type": "tool_result", "tool_use_id": m["id"], "content": m["content"], "is_error": m["is_error"]}
            if out and out[-1]["role"] == "user" and isinstance(out[-1]["content"], list):
                out[-1]["content"].append(block)
            else:
                out.append({"role": "user", "content": [block]})
    return out


class OpenAICompatible:
    """Chat Completions API: OpenAI, or a self-hosted vLLM / SGLang / Ollama via base_url."""

    def __init__(self, model: str, base_url: str = "https://api.openai.com/v1", api_key: str | None = None):
        self.model, self.base_url = model, base_url.rstrip("/")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "none")

    def __call__(self, system, messages, tools) -> Reply:
        body = {"model": self.model, "messages": [{"role": "system", "content": system}] + _to_openai(messages),
                "tools": [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                                            "parameters": t["input_schema"]}} for t in tools]}
        out = post(f"{self.base_url}/chat/completions", {"authorization": f"Bearer {self.api_key}"}, body)
        msg = out["choices"][0]["message"]
        calls = [Call(c["id"], c["function"]["name"], json.loads(c["function"]["arguments"] or "{}"))
                 for c in msg.get("tool_calls") or []]
        return Reply(msg.get("content") or "", calls, out.get("usage", {}))


def _to_openai(messages) -> list[dict]:
    out = []
    for m in messages:
        if m["role"] == "user":
            out.append({"role": "user", "content": m["content"]})
        elif m["role"] == "assistant":
            msg = {"role": "assistant", "content": m["content"] or None}
            if m["calls"]:
                msg["tool_calls"] = [{"id": c["id"], "type": "function",
                                      "function": {"name": c["name"], "arguments": dumps(c["args"])}} for c in m["calls"]]
            out.append(msg)
        else:
            out.append({"role": "tool", "tool_call_id": m["id"], "content": m["content"]})
    return out
