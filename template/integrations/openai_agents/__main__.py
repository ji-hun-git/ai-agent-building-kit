"""Run the HR agent on the OpenAI Agents SDK.

    python -m integrations.openai_agents                                                # offline stand-in
    python -m integrations.openai_agents --model qwen3-vl:2b@http://127.0.0.1:11434/v1   # any Chat Completions server
    python -m integrations.openai_agents --user hr                                      # every turn as one user

The tour declines every approval, like the template's.
"""

import argparse
import asyncio

from agents import AgentsException, __version__
from openai import OpenAIError

from examples.hr.__main__ import USERS

from . import build, chat_model

TOUR = [
    ("intern", "How many days of annual leave do I get?"),
    ("intern", "What is the CEO's pay band?"),
    ("intern", "Please request leave from 2026-11-02 to 2026-11-04."),
    ("hr", "What does the team handbook say about Fridays?"),
]


def decline(question: str) -> bool:
    print(f"  approval needed: {question}")
    print("  (tour declines)")
    return False


async def tour(assistant, who: str | None) -> None:
    for name, text in TOUR:  # each turn in a fresh conversation
        user = USERS[who or name]
        print(f"\n{user.id}> {text}")
        try:
            out = await assistant.ask(assistant.start(user), text, approve=decline)
        except (OpenAIError, AgentsException) as e:  # say what failed, and go on with the tour
            out = f"(the model call failed: {type(e).__name__}: {e})"
        print(f"agent> {out}")


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m integrations.openai_agents")
    ap.add_argument("--model", help="<id>@<base_url> of a Chat Completions server; omit for the offline stand-in")
    ap.add_argument("--user", choices=USERS, help="run every turn as this user")
    args = ap.parse_args()
    try:
        model = chat_model(args.model) if args.model else None
    except ValueError as e:
        raise SystemExit(f"error: {e}") from None
    print(f"model: {args.model.split('@')[0] if args.model else 'stand-in'}   openai-agents {__version__}")
    asyncio.run(tour(build(model), args.user))


if __name__ == "__main__":
    main()
