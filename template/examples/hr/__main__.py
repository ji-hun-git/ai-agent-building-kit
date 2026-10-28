"""Run the HR agent: python -m examples.hr [--chat] [--model ...]. Options: examples/cli.py."""

from kit import User

from ..cli import main
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

if __name__ == "__main__":
    main(build, USERS, TOUR, default_user="intern")
