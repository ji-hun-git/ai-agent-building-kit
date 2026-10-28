"""kit: a small, dependency-free harness for building production AI agents.

    from kit import Agent, Toolbox, Tool, Policy, User, Index, Doc, search_tool, Guard

Read the modules in this order: policy, context, tools, guard, retrieval, agent,
trace, release, evals. Each one closes a specific way agents fail in production.
"""

from .agent import Agent, Anthropic, OpenAICompatible, OpenAIResponses, Pending, Reply, Scripted, model_from
from .context import Session, fingerprint, load_prompt
from .guard import Finding, Guard, GuardModel, OpenAIModeration, Verdict
from .net import APIError
from .policy import Policy, Taint, User, anyone, only_values, own_records, role
from .release import bundle
from .retrieval import Doc, Embeddings, Index, Reranker, search_tool
from .tools import Call, NeedsApproval, Result, Tool, Toolbox
from .trace import Tracer

__all__ = [
    "Agent", "Anthropic", "OpenAICompatible", "OpenAIResponses", "Pending", "Reply", "Scripted", "model_from",
    "Session", "fingerprint", "load_prompt",
    "APIError", "Finding", "Guard", "GuardModel", "OpenAIModeration", "Verdict",
    "Policy", "Taint", "User", "anyone", "only_values", "own_records", "role",
    "bundle", "Doc", "Embeddings", "Index", "Reranker", "search_tool",
    "Call", "NeedsApproval", "Result", "Tool", "Toolbox", "Tracer",
]
