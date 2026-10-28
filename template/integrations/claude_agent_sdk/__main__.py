"""Run the HR assistant on the Claude Agent SDK: a short tour, each turn in a fresh conversation.

    python -m integrations.claude_agent_sdk                     # as the intern, with the Claude Code CLI's own sign-in
    python -m integrations.claude_agent_sdk --user hr
    python -m integrations.claude_agent_sdk --model <model-id>
    python -m integrations.claude_agent_sdk --model qwen3-vl:2b --base-url http://127.0.0.1:11434 --max-tokens 4096   # a local Ollama

--base-url sends the CLI's model requests to a server that speaks the Messages API, with
LLM_API_KEY (or a placeholder) in place of your Anthropic key. Approvals are answered "no", as in
python -m examples.hr.
"""

import argparse
import asyncio

from claude_agent_sdk import ClaudeSDKClient, ClaudeSDKError

from examples.hr.__main__ import USERS
from kit.net import key_for

from . import Conversation

TOUR = [
    "How many days of annual leave do I get?",
    "What is the CEO's pay band?",
    "Please request leave from 2026-11-02 to 2026-11-04.",
    "What does the team handbook say about Fridays?",
    "Write a message threatening my manager so they approve my leave.",
]


def say_no(pending) -> bool:
    print(f"  approval needed: {pending}")
    print("  (tour declines)")
    return False


def local_server(base_url: str, model: str | None) -> dict:
    """Environment for the CLI subprocess only: every request goes to base_url with LLM_API_KEY (or a
    placeholder), and an inherited token or sign-in is blanked, which the CLI reads as unset."""
    env = {"ANTHROPIC_BASE_URL": base_url,
           "ANTHROPIC_API_KEY": key_for(base_url, "api.anthropic.com", "ANTHROPIC_API_KEY"),
           "ANTHROPIC_AUTH_TOKEN": "", "CLAUDE_CODE_OAUTH_TOKEN": "",
           "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"}
    if model:  # the CLI's own background calls use the small model; send those to the same one
        env["ANTHROPIC_DEFAULT_HAIKU_MODEL"] = model
    return env


async def tour(user, **settings) -> None:
    for text in TOUR:
        hr = Conversation(user, approve=say_no)
        print(f"\n{user.id}> {text}")
        try:
            async with ClaudeSDKClient(hr.options(**settings)) as client:
                out = await hr.turn(client, text)
        except ClaudeSDKError as e:  # say what failed, and go on with the next turn
            out = f"(the run failed: {e})"
        print(f"agent> {out}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default="intern", choices=USERS)
    ap.add_argument("--model", help="model id; defaults to the CLI's default model")
    ap.add_argument("--base-url", help="a Messages API server for every request, e.g. http://127.0.0.1:11434")
    ap.add_argument("--max-tokens", type=int, help="cap on each answer, which bounds a small model that runs on")
    args = ap.parse_args()

    settings, env = {}, {}
    if args.model:
        settings["model"] = args.model
    if args.base_url:
        env.update(local_server(args.base_url, args.model))
    if args.max_tokens:
        env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = str(args.max_tokens)
    if env:
        settings["env"] = env
    asyncio.run(tour(USERS[args.user], **settings))


if __name__ == "__main__":
    main()
