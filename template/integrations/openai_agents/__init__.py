"""The HR assistant from examples/hr on the OpenAI Agents SDK, with the template's rules in the SDK's own hooks.

    rule in the template                 where it lives here
    the user's permissions (Policy)      a check at the top of every tool, with the user from the run context;
                                         is_enabled hides tools the user can never call
    trifecta and lockdown (Toolbox)      needs_approval, decided from the taint the run has accumulated, and
                                         checked again when the tool runs, because the SDK decides approvals
                                         for every call of a reply before it runs any of them
    approvals (Pending, resume)          result.interruptions, RunState.approve / reject, Runner.run(agent, state)
    guard (Guard)                        an input guardrail refuses blocked prompts, Guard.data runs inside every
                                         tool, Guard.egress before anything goes out, and an output guardrail
                                         withholds blocked answers; a guardrail can stop a run but not edit it,
                                         so the guard's rules redact the prompt before the run and the answer after
    run-once writes (the ledger)         Toolbox.execute inside every tool, with the run context as its session,
                                         so the ledger is keyed by Toolbox.key; Context.dump and Context.load
                                         carry it through RunState.to_json and RunState.from_json
    traces                               the SDK's exporter to OpenAI removed and tracing off

The tools, documents, prompt, policy and guard are examples.hr's own, taken from its build(), so the
port cannot drift from the original. SDK names are written as agents.X, so each hook is easy to find.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

import examples.hr
from kit import Call, Guard, NeedsApproval, Taint, Tool, Toolbox, User
from kit.agent import _args
from kit.context import dumps
from kit.net import key_for

try:
    import agents
except ImportError:  # importable without it, so the stdlib-only test run can discover and skip its tests
    agents = None

DECLINED = "The user declined. Nothing was done."
# How a tool says it did not do the work. The SDK hands tool output to the model as text with no error
# flag; a real model reads the sentence, and the stand-in tells errors apart by these openings.
ERRORS = ("Missing required", "Denied:", "Blocked:", "Not done:", DECLINED, "This result was withheld")


@dataclass
class Context:
    """The run context: who is asking, and what this conversation has read and written.

    The SDK passes it to every tool, needs_approval callable and guardrail, and never to the model.
    Keep one per conversation: like a kit Session, taint and the ledger outlive a single run. To keep
    writes run-once across restarts, restore the id and pass a persistent mapping as the ledger."""
    user: User
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    taint: Taint = field(default_factory=Taint)
    ledger: dict = field(default_factory=dict)   # Toolbox.key -> result of a write
    history: list = field(default_factory=list)  # input items of the finished turns

    def dump(self) -> dict:
        """For RunState.to_json(context_serializer=Context.dump)."""
        return {"user": {"id": self.user.id, "roles": sorted(self.user.roles)}, "id": self.id,
                "taint": {"private": self.taint.private, "untrusted": self.taint.untrusted},
                "ledger": dict(self.ledger), "history": list(self.history)}

    @classmethod
    def load(cls, data, ledger=None) -> Context:
        """For RunState.from_json(agent, data, context_deserializer=Context.load). With a persistent
        ledger, pass it (functools.partial(Context.load, ledger=store)): a saved run resumed twice then
        finds its write already done, instead of a copy of the ledger from when it was saved."""
        return cls(User(data["user"]["id"], frozenset(data["user"]["roles"])), data["id"],
                   Taint(**data["taint"]), dict(data["ledger"]) if ledger is None else ledger,
                   list(data["history"]))


# ---------------------------------------------------------------- tools

def needs_person(tool: Tool, taint: Taint, lockdown: bool) -> str:
    """Why a call of this tool needs a person now, or "" if it does not: the rules of Toolbox.execute."""
    if taint.blocks(tool.outbound):
        return ("this session has read private data and untrusted content; "
                "sending anything out needs a person to check it")
    if lockdown and tool.kind != "read" and taint.untrusted:
        return "this session has read untrusted content, and in lockdown every action after that needs a person"
    if tool.needs_approval:
        return f"{tool.name} is {'an' if tool.kind[0] in 'aeiou' else 'a'} {tool.kind} action"
    return ""


def port(tool: Tool, toolbox: Toolbox, guard: Guard) -> agents.FunctionTool:
    """A kit Tool as an SDK FunctionTool, with the toolbox's checks moved into the SDK's hooks."""
    if toolbox.tools.get(tool.name) is not tool:  # the toolbox runs it, so it must be the toolbox's own
        raise ValueError(f"{tool.name}: add the tool to the toolbox before porting it")

    def refusal(user: User, args: dict) -> str:
        """Why this call must not run whoever approves it, or "" if it may."""
        missing = [p for p in tool.required if p not in args]
        if missing:
            return f"Missing required argument(s) for {tool.name}: {', '.join(missing)}."
        ok, why = toolbox.policy.check(user, tool.name, args)
        if not ok:
            return f"Denied: {why}. Tell the user you cannot do this."
        if tool.outbound:
            found = guard.egress(dumps(args)).findings
            if found:
                rules = ", ".join(sorted({f.rule for f in found}))
                return (f"Blocked: this message would carry {rules} out of the session. "
                        "Do not retry; tell the user what was blocked.")
        return ""

    async def needs_approval(ctx: agents.RunContextWrapper, args: dict, call_id: str) -> bool:
        """The SDK asks this before the call runs. A call that will be refused, or that already ran in
        this conversation, never asks a person."""
        run = ctx.context
        if refusal(run.user, args) or toolbox.key(run, Call(call_id, tool.name, args)) in run.ledger:
            return False
        return bool(needs_person(tool, run.taint, toolbox.lockdown))

    def execute(ctx: agents.tool_context.ToolContext, args: dict) -> str:
        run = ctx.context
        refused = refusal(run.user, args)  # the user's own permissions on every call, and the egress guard
        if refused:
            return refused
        # The kit's own order from here: ledger, trifecta, lockdown, approval, then the function, once.
        # The run context is the session: it has the id, the taint and the ledger.
        approved = bool(ctx.is_tool_approved(tool.name, ctx.tool_call_id))
        try:
            return toolbox.execute(Call(ctx.tool_call_id, tool.name, args), run.user, run, approved=approved).content
        except NeedsApproval as e:  # needs_approval ran before an earlier call of the same reply tainted the run
            return f"Not done: {e.reason}. Call {tool.name} again so the user is asked."

    async def invoke(ctx: agents.tool_context.ToolContext, arguments: str) -> str:
        """Every result, errors included, passes Guard.data before the model reads it."""
        verdict = guard.data(execute(ctx, _args(arguments)))
        return "This result was withheld by the content guard." if verdict.blocked else verdict.text

    return agents.FunctionTool(
        name=tool.name, description=tool.description, params_json_schema=tool.schema()["input_schema"],
        on_invoke_tool=invoke,
        strict_json_schema=False,  # kit schemas leave optional arguments out of "required"
        is_enabled=lambda ctx, agent: toolbox.policy.visible(ctx.context.user, tool.name),
        # A plain read never needs a person; anything that writes or sends is decided per call.
        needs_approval=needs_approval if tool.kind != "read" or tool.outbound else False,
    )


# ---------------------------------------------------------------- guardrails

def text_of(content) -> str:
    """Message or tool-output content as plain text: a string, or the text parts of a list."""
    if isinstance(content, str):
        return content
    return "".join(p.get("text", "") for p in content or [] if isinstance(p, dict))


def guardrails(guard: Guard) -> tuple[agents.InputGuardrail, agents.OutputGuardrail]:
    @agents.input_guardrail(name="guard_prompt", run_in_parallel=False)  # before the model starts
    def screen_prompt(ctx: agents.RunContextWrapper, agent: agents.Agent, input) -> agents.GuardrailFunctionOutput:
        """Refuse the newest user message if the prompt guard blocks it. Assistant.ask redacts it first,
        so a message the rules would still change was not screened, and is refused too."""
        items = [{"role": "user", "content": input}] if isinstance(input, str) else input
        texts = [text_of(i.get("content")) for i in items if isinstance(i, dict) and i.get("role") == "user"][-1:]
        verdicts = [guard.prompt(t) for t in texts]
        tripped = any(v.blocked or v.text != t for v, t in zip(verdicts, texts, strict=True))
        return agents.GuardrailFunctionOutput(output_info=sorted({x for v in verdicts for x in v.labels}),
                                              tripwire_triggered=tripped)

    @agents.output_guardrail(name="guard_output")
    def screen_answer(ctx: agents.RunContextWrapper, agent: agents.Agent, output) -> agents.GuardrailFunctionOutput:
        """Withhold an answer the output guard blocks. Links and identifiers come out after the run."""
        verdict = guard.output(str(output or ""))
        return agents.GuardrailFunctionOutput(output_info=verdict.labels, tripwire_triggered=verdict.blocked)

    return screen_prompt, screen_answer


# ---------------------------------------------------------------- the agent

@dataclass
class Assistant:
    """What build() returns: the SDK agent and run settings, and the adapters, so tests can call them."""
    agent: agents.Agent
    run_config: agents.RunConfig
    toolbox: Toolbox  # the template's tools, policy and lockdown setting, which the adapters read
    guard: Guard
    rules: Guard      # the same rules without the classifier: they edit text, the guardrails refuse
    screen_prompt: agents.InputGuardrail
    screen_answer: agents.OutputGuardrail
    max_turns: int = 8

    @property
    def tools(self) -> dict:
        return {t.name: t for t in self.agent.tools}

    def start(self, user: User, **saved) -> Context:
        return Context(user, **saved)

    def question(self, context: Context, item: agents.ToolApprovalItem) -> str:
        """What the person is asked, worded like the template's Pending."""
        tool = self.toolbox.tools.get(item.name)
        why = (tool and needs_person(tool, context.taint, self.toolbox.lockdown)) or "its arguments could not be checked"
        return f"Approve {item.name}({dumps(_args(item.arguments))})? Reason: {why}."

    async def ask(self, context: Context, text: str, approve=None) -> str:
        """One user turn. approve(question) -> bool answers each approval; the default declines."""
        approve = approve or (lambda question: False)
        text = self.rules.prompt(text).text  # a guardrail cannot edit the input, so redaction happens here
        try:
            result = await agents.Runner.run(self.agent, [*context.history, {"role": "user", "content": text}],
                                             context=context, run_config=self.run_config, max_turns=self.max_turns)
            while result.interruptions:
                state = result.to_state()
                for item in result.interruptions:
                    if approve(self.question(context, item)):
                        state.approve(item)
                    else:
                        state.reject(item, rejection_message=DECLINED)
                result = await agents.Runner.run(self.agent, state, run_config=self.run_config,
                                                 max_turns=self.max_turns)
        except agents.InputGuardrailTripwireTriggered:  # the model never sees a refused request, now or later
            return self._remember(context, "[a request the content guard refused]", self.guard.refusal)
        except agents.OutputGuardrailTripwireTriggered:
            return self._remember(context, text, self.guard.withheld)
        except agents.MaxTurnsExceeded:
            return self._remember(context, text, "I stopped because this took too many steps. Please narrow the request.")
        context.history = result.to_input_list()
        answer = str(result.final_output or "").strip() or "The model returned an empty answer. Please ask again."
        return self.rules.output(answer).text

    @staticmethod
    def _remember(context: Context, text: str, reply: str) -> str:
        context.history = [*context.history, {"role": "user", "content": text},
                           {"role": "assistant", "content": reply}]
        return reply


def model_from(spec: str, api_key: str | None = None):
    """`<id>` for OpenAI's Responses API, which its current models need for tools; `<id>@<base_url>`
    for a Chat Completions server (Ollama, vLLM, SGLang, Meta's Model API); `responses:<id>@<base_url>`
    for another Responses server."""
    from openai import AsyncOpenAI

    if spec.startswith("responses:") or "@" not in spec:
        model_id, _, base = spec.removeprefix("responses:").partition("@")
        base = (base or "https://api.openai.com/v1").rstrip("/")
        if not model_id:
            raise ValueError(f"use <id>, <id>@<base_url> or responses:<id>@<base_url>, not {spec!r}")
        client = AsyncOpenAI(base_url=base, api_key=key_for(base, "api.openai.com", "OPENAI_API_KEY", api_key))
        return agents.OpenAIResponsesModel(model_id, client)
    return chat_model(spec, api_key)


def chat_model(spec: str, api_key: str | None = None) -> agents.OpenAIChatCompletionsModel:
    """`<id>@<base_url>` on a Chat Completions server (Ollama, vLLM, SGLang). The client always gets an
    explicit key, so the SDK never reads OPENAI_API_KEY itself; kit.net.key_for sends that key only to
    api.openai.com and gives every other server LLM_API_KEY, or "none"."""
    from openai import AsyncOpenAI

    model_id, _, base = spec.partition("@")
    if not model_id or not base:
        raise ValueError(f"use <id>@<base_url>, e.g. qwen3-vl:2b@http://127.0.0.1:11434/v1, not {spec!r}")
    base = base.rstrip("/")
    client = AsyncOpenAI(base_url=base, api_key=key_for(base, "api.openai.com", "OPENAI_API_KEY", api_key))
    return agents.OpenAIChatCompletionsModel(model_id, client)


def build(model=None, max_turns: int = 8) -> Assistant:
    """The HR agent on the SDK. model is any agents.Model (chat_model() for a local server); None runs the
    template's gullible stand-in, offline.

    Tracing is process-wide in the SDK: this removes its default exporter, which sends traces to OpenAI,
    and turns tracing off. To trace, add_trace_processor() your own pipeline and set_tracing_disabled(False)."""
    if agents is None:
        raise ImportError("the OpenAI Agents SDK is missing: pip install -r integrations/openai_agents/requirements.txt")
    agents.set_trace_processors([])
    agents.set_tracing_disabled(True)
    if model is None:
        from .stand_in import StandInModel
        model = StandInModel()
    template = examples.hr.build()  # its prompt, its toolbox (tools, policy, lockdown) and its guard
    guard, toolbox = template.guard, template.toolbox
    screen_prompt, screen_answer = guardrails(guard)
    # Like the template's adapter: nothing stored at the provider, reasoning replayed from the response.
    settings = (agents.ModelSettings(store=False, response_include=["reasoning.encrypted_content"])
                if isinstance(model, agents.OpenAIResponsesModel) else agents.ModelSettings())
    agent = agents.Agent(
        name="hr", instructions=template.system, model=model, model_settings=settings,
        tools=[port(t, toolbox, guard) for t in sorted(toolbox.tools.values(), key=lambda t: t.name)],
        input_guardrails=[screen_prompt], output_guardrails=[screen_answer])
    run_config = agents.RunConfig(
        tracing_disabled=True, trace_include_sensitive_data=False, workflow_name="hr",
        # One call at a time, in the order the model wrote them, so a read taints the run before the
        # next call of the same reply runs.
        tool_execution=agents.ToolExecutionConfig(max_function_tool_concurrency=1),
        tool_not_found_behavior="return_error_to_model")  # an unknown or hidden tool gets a sentence
    return Assistant(agent, run_config, toolbox, guard, Guard(pii=tuple(guard.pii), hosts=guard.hosts),
                     screen_prompt, screen_answer, max_turns)
