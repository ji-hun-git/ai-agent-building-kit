"""Run the support desk: python -m examples.support [--chat] [--model ...]. Options: examples/cli.py."""

from kit import User

from ..cli import main
from . import build

USERS = {"agent": User("u-agent", frozenset({"support"})),
         "lead": User("u-lead", frozenset({"support", "lead"}))}

TOUR = [
    ("agent", "Who are you?"),
    ("agent", "Please handle ticket T-1.", True),
    ("agent", "Refund 500 on ticket T-1."),
    ("lead", "Refund 500 on ticket T-1.", True),
    ("lead", "Please handle ticket T-2."),
    ("agent", "Please handle ticket T-9."),
]

if __name__ == "__main__":
    main(build, USERS, TOUR, default_user="agent")
