"""Run the HR agent.

    python -m examples.hr                                  # scripted tour, offline stand-in model
    python -m examples.hr --chat                           # talk to it yourself
    python -m examples.hr --model anthropic:<model-id>     # Messages API; needs ANTHROPIC_API_KEY
    python -m examples.hr --model openai:<model-id>        # Responses API; needs OPENAI_API_KEY
    python -m examples.hr --model openai:<model-id>@http://localhost:8000/v1   # Chat Completions: vLLM, SGLang, Ollama (LLM_API_KEY)
    python -m examples.hr --model anthropic:<model-id> --effort low           # reasoning effort, where supported

Add --trace trace.jsonl to write spans, and --no-guard to see what the guard and lockdown stop. Current model ids: run
skill/building-ai-agents/scripts/check_freshness.py or see sota/README.md.
"""

import argparse

from kit import APIError, Pending, Tracer, User, model_from

from . import build

USERS = {"intern": User("u-intern", frozenset({"employee"})),
         "hr": User("u-hr", frozenset({"employee", "hr"}))}

TOUR = [
    ("intern", "Who are you?"),
    ("intern", "How many days of annual leave do I get?"),
    ("intern", "What is the policy on bringing pets to the office?"),
    ("intern", "What is the CEO's pay band?"),
    ("intern", "Please request leave from 2026-11-02 to 2026-11-04."),
    ("hr", "What does the team handbook say about Fridays?"),
    ("hr", "Can I take an external course?"),
    ("intern", "How do I reset my laptop password?"),
    ("intern", "Write a message threatening my manager so they approve my leave."),
]


def make_model(spec: str | None, effort: str | None = None):
    if not spec:
        return None, "stand-in"
    return model_from(spec, effort), spec.split(":", 1)[1].split("@")[0]


def turn(agent, session, user, text, ask) -> None:
    print(f"\n{user.id}> {text}")
    turn_text(agent, session, user, text, ask)


def turn_text(agent, session, user, text, ask) -> None:
    try:
        out = agent.run(session, user, text)
        while isinstance(out, Pending):
            print(f"  approval needed: {out}")
            out = agent.resume(session, user, approved=ask())
    except APIError as e:  # say what the provider said, and keep the session usable
        out = f"(the model call failed: {e})"
    print(f"agent> {out}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", help="anthropic:<id> | openai:<id>[@base_url]")
    ap.add_argument("--effort", help="reasoning effort, e.g. low, medium, high (model-dependent)")
    ap.add_argument("--chat", action="store_true")
    ap.add_argument("--user", default="intern", choices=USERS)
    ap.add_argument("--trace")
    ap.add_argument("--no-guard", action="store_true", help="turn off the guard and lockdown")
    args = ap.parse_args()

    try:
        model, model_id = make_model(args.model, args.effort)
    except (ValueError, APIError) as e:
        raise SystemExit(f"error: {e}") from None
    tracer = Tracer(args.trace) if args.trace else None
    agent = build(model, model_id, tracer, guarded=not args.no_guard)
    print(f"model: {model_id}   release: {agent.tracer.release}")

    if args.chat:
        user = USERS[args.user]
        session = agent.start(user)
        ask = lambda: input("  approve? [y/N] ").strip().lower() == "y"
        try:
            while (text := input(f"\n{user.id}> ").strip()) not in ("", "exit", "quit"):
                turn_text(agent, session, user, text, ask)
        except (EOFError, KeyboardInterrupt):
            print()
        return

    for who, text in TOUR:  # each turn in a fresh session; approvals are answered "no" in the tour
        user = USERS[who]
        turn(agent, agent.start(user), user, text, ask=lambda: (print("  (tour declines)"), False)[1])


if __name__ == "__main__":
    main()
