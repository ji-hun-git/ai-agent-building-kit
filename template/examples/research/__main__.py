"""Run the research team: python -m examples.research [--chat] [--model ...]. Options: examples/cli.py."""

from kit import User

from ..cli import main
from . import build

USERS = {"analyst": User("u-analyst", frozenset({"employee"}))}

TOUR = [
    ("analyst", "How many hours does the battery last and how long is the warranty?", True),
    ("analyst", "Where does Acme ship and does it come in red?"),
]

if __name__ == "__main__":
    main(build, USERS, TOUR, default_user="analyst")
