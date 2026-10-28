"""The command line every example shares: a scripted tour, or a chat, against any model.

    python -m examples.<name>                                   # tour with the offline stand-in model
    python -m examples.<name> --chat [--user <who>]             # talk to it yourself
    python -m examples.<name> --model anthropic:<model-id>      # Messages API; needs ANTHROPIC_API_KEY
    python -m examples.<name> --model openai:<model-id>         # Responses API; needs OPENAI_API_KEY
    python -m examples.<name> --model openai:qwen3-vl:2b@http://127.0.0.1:11434/v1   # a local Ollama, free

--effort and --max-tokens tune the model, --trace trace.jsonl writes spans, --no-guard turns off the
guard and lockdown to show what they stop. In the tour every approval is declined, unless the
example's tour marks a turn to approve.
"""

import argparse

from kit import APIError, Pending, Tracer, model_from


def run_turn(agent, session, user, text, ask) -> None:
    try:
        out = agent.run(session, user, text)
        while isinstance(out, Pending):
            print(f"  approval needed: {out}")
            out = agent.resume(session, user, approved=ask())
    except APIError as e:  # say what the provider said, and keep the session usable
        out = f"(the model call failed: {e})"
    print(f"agent> {out}")


def main(build, users: dict, tour: list, default_user: str) -> None:
    """tour: (user key, text) or (user key, text, approve) tuples; each turn gets a fresh session."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", help="anthropic:<id>[@base_url] | openai:<id>[@base_url] | responses:<id>@base_url")
    ap.add_argument("--effort", help="reasoning effort, e.g. low, medium, high (model-dependent)")
    ap.add_argument("--max-tokens", type=int, help="cap on each answer, reasoning included")
    ap.add_argument("--chat", action="store_true")
    ap.add_argument("--user", default=default_user, choices=users)
    ap.add_argument("--trace")
    ap.add_argument("--no-guard", action="store_true", help="turn off the guard and lockdown")
    args = ap.parse_args()

    try:
        model = model_from(args.model, args.effort, args.max_tokens) if args.model else None
    except (ValueError, APIError) as e:
        raise SystemExit(f"error: {e}") from None
    model_id = args.model.split(":", 1)[1].split("@")[0] if args.model else "stand-in"
    agent = build(model, model_id, Tracer(args.trace) if args.trace else None, guarded=not args.no_guard)
    print(f"model: {model_id}   release: {agent.tracer.release}")

    if args.chat:
        user = users[args.user]
        session = agent.start(user)
        ask = lambda: input("  approve? [y/N] ").strip().lower() == "y"
        try:
            while (text := input(f"\n{user.id}> ").strip()) not in ("", "exit", "quit"):
                run_turn(agent, session, user, text, ask)
        except (EOFError, KeyboardInterrupt):
            print()
        return

    for who, text, *approve in tour:
        user, verdict = users[who], bool(approve and approve[0])
        print(f"\n{user.id}> {text}")
        run_turn(agent, agent.start(user), user, text,
                 ask=lambda v=verdict: (print(f"  (tour {'approves' if v else 'declines'})"), v)[1])
