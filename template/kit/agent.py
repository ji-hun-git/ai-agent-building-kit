"""The agent loop: the model proposes, code disposes.

    user -> [guard] -> model -> tool calls -> Toolbox (permissions, trifecta, approval, ledger)
         -> [guard] results -> model -> ... -> [guard] answer

The model never executes anything itself. When a call needs a person, the loop
stops and returns a Pending action that states exactly what will happen; the
caller shows it, and resumes with the person's decision.

With a Guard, the prompt is screened before the model sees it, every tool result
before it enters the context, every outbound call before it runs, and the answer
before the user sees it (see guard.py).

Models are plain callables: model(system, messages, tools) -> Reply. Four are
included: a scripted stand-in for tests, and thin adapters for the Anthropic
Messages API, the OpenAI Responses API, and any Chat Completions server (vLLM,
SGLang, Ollama, Gemini's OpenAI-compatible endpoint). Adapters keep the
provider's own output on each assistant turn (thinking blocks, reasoning items)
and send it back unchanged, because current reasoning models reject or lose a
history whose reasoning was dropped or edited. Model names are configuration,
never code; check the current ones with
skill/building-ai-agents/scripts/check_freshness.py.
"""

import json
from dataclasses import dataclass, field

from .context import Session, dumps
from .guard import Guard
from .net import key_for, post
from .policy import User
from .tools import Call, NeedsApproval, Result, Toolbox
from .trace import Tracer


@dataclass
class Reply:
    text: str = ""
    calls: list[Call] = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    raw: list = field(default_factory=list)  # the provider's own output, sent back unchanged
    via: str = ""                            # the adapter that produced `raw`
    cut: bool = False                        # the answer stopped at the token limit


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

    def start(self, user: User, session_id: str | None = None, ledger=None) -> Session:
        """Freeze the prompt and this user's tool list for the whole session.

        Writes run once per session. To keep that across restarts, pass the session's id when you
        resume it and a persistent mapping as the ledger (a database table, or shelve.open(path))."""
        extra = {"id": session_id} if session_id else {}
        if ledger is not None:
            extra["ledger"] = ledger
        return Session(system=self.system, tools=self.toolbox.schemas(user), **extra)

    def run(self, session: Session, user: User, text: str) -> str | Pending:
        if session.pending:  # the user moved on: a call waiting for approval never runs later
            pending, session.pending = session.pending, None
            for call in [pending["call"], *pending["queue"]]:
                session.append(_tool_msg(call, "Not done: the user moved on without approving it.", is_error=True))
        session.steps = 0
        verdict = self.guard.prompt(text) if self.guard else None
        text = verdict.text if verdict else text
        with self.tracer.span("invoke_agent", **{"session.id": session.id, "content.input": text}) as span:
            if verdict:
                span["guard.prompt"] = verdict.labels
                if verdict.blocked:  # the model never sees a request the guard refused, now or later
                    session.append({"role": "user", "content": "[a request the content guard refused]"})
                    session.append({"role": "assistant", "content": self.guard.refusal, "calls": []})
                    return self.guard.refusal
            session.append({"role": "user", "content": text})
            return self._loop(session, user, queue=[])

    def resume(self, session: Session, user: User, approved: bool) -> str | Pending:
        if not session.pending:
            raise RuntimeError("nothing is waiting for approval")
        call, queue = session.pending["call"], session.pending["queue"]
        session.pending = None
        with self.tracer.span("invoke_agent", **{"session.id": session.id, "approval.granted": approved}):
            if approved:
                self._execute(session, user, call, approved=True)
            else:
                session.append(_tool_msg(call, "The user declined. Nothing was done.", is_error=True))
            return self._loop(session, user, queue)

    def _loop(self, session: Session, user: User, queue: list[Call]) -> str | Pending:
        while True:
            while queue:  # finish the calls of the previous reply first
                call = queue.pop(0)
                try:
                    self._execute(session, user, call)
                except NeedsApproval as e:
                    session.pending = {"call": call, "queue": queue}
                    return Pending(call, e.reason)
            if session.steps >= self.max_steps:  # counted across approvals, so resuming cannot loop
                text = "I stopped because this took too many steps. Please narrow the request."
                session.append({"role": "assistant", "content": text, "calls": []})
                return text
            session.steps += 1
            with self.tracer.span("chat", **{"gen_ai.request.model": self.model_id}) as span:
                reply = self.model(session.system, session.messages, session.tools)
                span.update({f"gen_ai.usage.{k}": v for k, v in reply.usage.items()})
                span["content.output"] = reply.text
                text = reply.text
                if not reply.calls and reply.cut:  # say so, rather than pass a cut answer off as whole
                    text = (f"{text} [cut off at the token limit]" if text.strip() else
                            "The answer hit its token limit before any text; raise max_tokens and ask again.")
                elif not reply.calls and not text.strip():
                    text = "The model returned an empty answer. Please ask again."
                if self.guard and not reply.calls:  # the final answer, before the user sees it
                    verdict = self.guard.output(text)
                    span["guard.output"] = verdict.labels
                    text = self.guard.withheld if verdict.blocked else verdict.text
            message = {"role": "assistant", "content": text, "calls": [c.__dict__ for c in reply.calls]}
            if reply.raw:  # the model's own output, which it already has; the guard decides what the user sees
                message.update(raw=reply.raw, via=reply.via)
            session.append(message)
            if not reply.calls:
                return text
            queue = list(reply.calls)

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
                if self.guard:  # error messages too: a failing tool can echo what it read
                    verdict = self.guard.data(result.content)
                    span["guard.data"] = verdict.labels
                    result = Result("This result was withheld by the content guard." if verdict.blocked
                                    else verdict.text, result.is_error)
            span["tool.is_error"] = result.is_error
        session.append(_tool_msg(call, result.content, result.is_error))


def _tool_msg(call: Call, content: str, is_error: bool = False) -> dict:
    return {"role": "tool", "id": call.id, "name": call.name, "args": call.args,
            "content": content, "is_error": is_error}


# ---------------------------------------------------------------- models

SPECS = """anthropic:<id>[@<base_url>]   Messages API (Anthropic, or a server that speaks it)
openai:<id>                     Responses API at OpenAI
openai:<id>@<base_url>          Chat Completions (vLLM, SGLang, Ollama, Gemini's endpoint)
responses:<id>@<base_url>       Responses API at another server"""


def model_from(spec: str, effort: str | None = None, max_tokens: int | None = None):
    """A model adapter from a spec; see SPECS. base_url is the API root, e.g. http://127.0.0.1:11434/v1.
    max_tokens caps each answer, reasoning included, which bounds both time and cost."""
    provider, _, rest = spec.partition(":")
    model_id, _, base = rest.partition("@")
    base = base.rstrip("/")
    if not model_id:
        raise ValueError(f"no model id in {spec!r}; use one of:\n{SPECS}")
    if provider == "anthropic":
        url = f"{base}/messages" if base else "https://api.anthropic.com/v1/messages"
        return Anthropic(model_id, max_tokens=max_tokens or 16000, effort=effort, url=url)
    if provider == "openai" and base:
        return OpenAICompatible(model_id, base, max_tokens=max_tokens)
    if provider == "openai" or (provider == "responses" and base):
        url = f"{base}/responses" if base else "https://api.openai.com/v1/responses"
        return OpenAIResponses(model_id, effort=effort, max_tokens=max_tokens, url=url)
    raise ValueError(f"unknown model spec {spec!r}; use one of:\n{SPECS}")


def _args(text: str | None) -> dict:
    """Tool arguments from JSON. Malformed or non-object JSON becomes no arguments, so the toolbox
    answers with a missing-argument sentence instead of the loop crashing."""
    try:
        value = json.loads(text or "{}")
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}


class Scripted:
    """Returns replies from a list; for tests and offline demos."""

    def __init__(self, replies: list[Reply]):
        self.replies = list(replies)

    def __call__(self, system, messages, tools) -> Reply:
        return self.replies.pop(0) if self.replies else Reply("(no more scripted replies)")


class Anthropic:
    """Anthropic Messages API. The system prompt is marked cacheable, and each assistant turn goes
    back exactly as it came, thinking blocks included: current models tie those blocks to the
    conversation and reject or lose a history that drops or edits them."""

    def __init__(self, model: str, max_tokens: int = 16000, effort: str | None = None, api_key: str | None = None,
                 url: str = "https://api.anthropic.com/v1/messages", version: str = "2026-10-21"):
        self.model, self.max_tokens, self.effort, self.url, self.version = model, max_tokens, effort, url, version
        self.api_key = key_for(url, "api.anthropic.com", "ANTHROPIC_API_KEY", api_key)

    def __call__(self, system, messages, tools) -> Reply:
        body = {
            "model": self.model, "max_tokens": self.max_tokens,
            "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            "messages": _to_anthropic(messages),
        }
        if tools:
            body["tools"] = tools
        if self.effort:
            body["output_config"] = {"effort": self.effort}
        out = post(self.url, {"x-api-key": self.api_key, "anthropic-version": self.version}, body)
        blocks = out.get("content", [])
        text = "".join(b["text"] for b in blocks if b["type"] == "text")
        if out.get("stop_reason") == "refusal" and not text:
            text = "I can't help with that request."
        calls = [Call(b["id"], b["name"], b["input"]) for b in blocks if b["type"] == "tool_use"]
        return Reply(text, calls, out.get("usage", {}), raw=blocks, via="anthropic",
                     cut=out.get("stop_reason") == "max_tokens")


def _to_anthropic(messages) -> list[dict]:
    out = []
    for m in messages:
        if m["role"] == "user":
            out.append({"role": "user", "content": m["content"]})
        elif m["role"] == "assistant":
            if m.get("via") == "anthropic":  # the model's own blocks, unchanged
                out.append({"role": "assistant", "content": m["raw"]})
                continue
            blocks = [{"type": "text", "text": m["content"]}] if m["content"] else []
            blocks += [{"type": "tool_use", "id": c["id"], "name": c["name"], "input": c["args"]} for c in m["calls"]]
            if blocks:  # an empty assistant turn is rejected; leaving it out keeps the history valid
                out.append({"role": "assistant", "content": blocks})
        else:  # tool results ride in a user turn; consecutive ones share it
            block = {"type": "tool_result", "tool_use_id": m["id"], "content": m["content"], "is_error": m["is_error"]}
            if out and out[-1]["role"] == "user" and isinstance(out[-1]["content"], list):
                out[-1]["content"].append(block)
            else:
                out.append({"role": "user", "content": [block]})
    return out


class OpenAIResponses:
    """OpenAI Responses API, OpenAI's recommended interface (GPT-6 Astra calls tools only here).
    Stateless (store=false): reasoning comes back encrypted and goes back with the turn it belongs to."""

    def __init__(self, model: str, effort: str | None = None, api_key: str | None = None,
                 url: str = "https://api.openai.com/v1/responses", max_tokens: int | None = None):
        self.model, self.effort, self.url, self.max_tokens = model, effort, url, max_tokens
        self.api_key = key_for(url, "api.openai.com", "OPENAI_API_KEY", api_key)

    def __call__(self, system, messages, tools) -> Reply:
        body = {"model": self.model, "instructions": system, "input": _to_responses(messages),
                "store": False, "include": ["reasoning.encrypted_content"]}
        if tools:
            body["tools"] = [{"type": "function", "name": t["name"], "description": t["description"],
                              "parameters": t["input_schema"], "strict": False} for t in tools]
        if self.effort:
            body["reasoning"] = {"effort": self.effort}
        if self.max_tokens:
            body["max_output_tokens"] = self.max_tokens
        out = post(self.url, {"authorization": f"Bearer {self.api_key}"}, body)
        items = out.get("output", [])
        text = "".join(part.get("text", "") for item in items if item["type"] == "message"
                       for part in item.get("content", []) if part.get("type") == "output_text")
        calls = [Call(i["call_id"], i["name"], _args(i.get("arguments"))) for i in items if i["type"] == "function_call"]
        cut = (out.get("incomplete_details") or {}).get("reason") == "max_output_tokens"
        return Reply(text, calls, out.get("usage", {}), raw=items, via="openai-responses", cut=cut)


def _to_responses(messages) -> list[dict]:
    out = []
    for m in messages:
        if m["role"] == "user":
            out.append({"role": "user", "content": m["content"]})
        elif m["role"] == "assistant":
            if m.get("via") == "openai-responses":  # reasoning, calls and text, in the order they came
                out.extend(m["raw"])
                continue
            if m["content"]:
                out.append({"role": "assistant", "content": m["content"]})
            out += [{"type": "function_call", "call_id": c["id"], "name": c["name"], "arguments": dumps(c["args"])}
                    for c in m["calls"]]
        else:
            out.append({"type": "function_call_output", "call_id": m["id"], "output": m["content"]})
    return out


class OpenAICompatible:
    """Chat Completions: self-hosted vLLM, SGLang or Ollama, Gemini's OpenAI-compatible endpoint, and
    any other server that speaks it. For OpenAI's own current models use OpenAIResponses: from
    GPT-5.4 on, Chat Completions calls tools only at reasoning effort none.

    OPENAI_API_KEY goes only to OpenAI's own API; any other server gets LLM_API_KEY (see net.key_for)."""

    def __init__(self, model: str, base_url: str = "https://api.openai.com/v1", api_key: str | None = None,
                 max_tokens: int | None = None):
        self.model, self.base_url, self.max_tokens = model, base_url.rstrip("/"), max_tokens
        self.api_key = key_for(self.base_url, "api.openai.com", "OPENAI_API_KEY", api_key)

    def __call__(self, system, messages, tools) -> Reply:
        body = {"model": self.model, "messages": [{"role": "system", "content": system}] + _to_openai(messages)}
        if self.max_tokens:
            body["max_tokens"] = self.max_tokens
        if tools:
            body["tools"] = [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                                               "parameters": t["input_schema"]}} for t in tools]
        out = post(f"{self.base_url}/chat/completions", {"authorization": f"Bearer {self.api_key}"}, body)
        choice = out["choices"][0]
        msg = choice["message"]
        calls = [Call(c["id"], c["function"]["name"], _args(c["function"]["arguments"])) for c in msg.get("tool_calls") or []]
        return Reply(msg.get("content") or "", calls, out.get("usage", {}), cut=choice.get("finish_reason") == "length")


def _to_openai(messages) -> list[dict]:
    out = []
    for m in messages:
        if m["role"] == "user":
            out.append({"role": "user", "content": m["content"]})
        elif m["role"] == "assistant":
            msg = {"role": "assistant", "content": m["content"] or ""}  # null content is rejected by some servers
            if m["calls"]:
                msg["tool_calls"] = [{"id": c["id"], "type": "function",
                                      "function": {"name": c["name"], "arguments": dumps(c["args"])}} for c in m["calls"]]
            out.append(msg)
        else:
            out.append({"role": "tool", "tool_call_id": m["id"], "content": m["content"]})
    return out
