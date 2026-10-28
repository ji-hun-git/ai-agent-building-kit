"""Run the HR agent.

    python -m examples.hr                                  # scripted tour, offline stand-in model
    python -m examples.hr --chat                           # talk to it yourself
    python -m examples.hr --model anthropic:<model-id>     # needs ANTHROPIC_API_KEY
    python -m examples.hr --model openai:<model-id>        # needs OPENAI_API_KEY
    python -m examples.hr --model openai:<model-id>@http://localhost:8000/v1   # self-hosted (vLLM, SGLang, Ollama)

Add --trace trace.jsonl to write spans. Current model ids: run
skill/building-ai-agents/scripts/check_freshness.py or see sota/README.md.
"""

import argparse

from kit import Anthropic, OpenAICompatible, Pending, Tracer, User

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
]


def make_model(spec: str | None):
    if not spec:
        return None, "stand-in"
    provider, _, rest = spec.partition(":")
    model_id, _, base = rest.partition("@")
    if provider == "anthropic":
        return Anthropic(model_id), model_id
    if provider == "openai":
        return (OpenAICompatible(model_id, base) if base else OpenAICompatible(model_id)), model_id
    raise SystemExit(f"unknown provider {provider!r}; use anthropic: or openai:")


def turn(agent, session, user, text, ask) -> None:
    print(f"\n{user.id}> {text}")
    out = agent.run(session, user, text)
    while isinstance(out, Pending):
        print(f"  approval needed: {out}")
        out = agent.resume(session, user, approved=ask())
    print(f"agent> {out}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", help="anthropic:<id> | openai:<id>[@base_url]")
    ap.add_argument("--chat", action="store_true")
    ap.add_argument("--user", default="intern", choices=USERS)
    ap.add_argument("--trace")
    args = ap.parse_args()

    model, model_id = make_model(args.model)
    tracer = Tracer(args.trace) if args.trace else None
    agent = build(model, model_id, tracer)
    print(f"model: {model_id}   release: {agent.tracer.release}")

    if args.chat:
        user = USERS[args.user]
        session = agent.start(user)
        ask = lambda: input("  approve? [y/N] ").strip().lower() == "y"
        while (text := input(f"\n{user.id}> ").strip()) not in ("", "exit", "quit"):
            out = agent.run(session, user, text)
            while isinstance(out, Pending):
                print(f"  approval needed: {out}")
                out = agent.resume(session, user, approved=ask())
            print(f"agent> {out}")
        return

    for who, text in TOUR:  # each turn in a fresh session; approvals are answered "no" in the tour
        user = USERS[who]
        turn(agent, agent.start(user), user, text, ask=lambda: (print("  (tour declines)"), False)[1])


if __name__ == "__main__":
    main()
