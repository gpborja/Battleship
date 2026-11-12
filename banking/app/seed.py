"""Populate the database with demo accounts and sample transactions.

Usage (from the banking/ directory):
    python -m app.seed           # seed only if the database is empty
    python -m app.seed --reset   # drop all data and reseed
"""

import argparse
from datetime import timedelta

from sqlalchemy import func, select

from app import services
from app.database import DEFAULT_DATABASE_URL, Base, init_db, make_engine, make_session_factory
from app.models import Account, utcnow

DEMO_ACCOUNTS = [
    ("Frida Kahlo", 5_000_00),
    ("Diego Rivera", 3_200_00),
    ("Octavio Paz", 12_750_00),
    ("Sor Juana Inés de la Cruz", 850_00),
]

# (days_ago, operation, args) — account numbers refer to positions in DEMO_ACCOUNTS (1-based).
DEMO_ACTIVITY = [
    (28, "deposit", (1, 1_250_00)),
    (26, "withdraw", (2, 180_50)),
    (24, "transfer", (3, 4, 600_00)),
    (21, "deposit", (2, 900_00)),
    (19, "withdraw", (1, 320_75)),
    (17, "transfer", (1, 2, 450_00)),
    (14, "deposit", (4, 275_00)),
    (12, "transfer", (2, 3, 1_000_00)),
    (10, "withdraw", (3, 2_150_00)),
    (8, "deposit", (3, 3_400_00)),
    (6, "transfer", (4, 1, 125_25)),
    (4, "withdraw", (4, 60_00)),
    (2, "transfer", (3, 1, 2_000_00)),
    (1, "deposit", (1, 99_99)),
]


def seed(database_url: str = DEFAULT_DATABASE_URL, reset: bool = False) -> bool:
    engine = make_engine(database_url)
    if reset:
        Base.metadata.drop_all(engine)
    init_db(engine)
    session_factory = make_session_factory(engine)

    with session_factory() as db:
        if db.scalar(select(func.count()).select_from(Account)):
            return False

        now = utcnow()
        opened = now - timedelta(days=30)
        ids = [services.create_account(db, name, cents, at=opened).id for name, cents in DEMO_ACCOUNTS]

        for days_ago, op, args in DEMO_ACTIVITY:
            at = now - timedelta(days=days_ago)
            if op == "transfer":
                src, dst, cents = args
                services.transfer(db, ids[src - 1], ids[dst - 1], cents, at=at)
            else:
                acct, cents = args
                getattr(services, op)(db, ids[acct - 1], cents, at=at)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reset", action="store_true", help="drop existing data before seeding")
    parser.add_argument("--database-url", default=DEFAULT_DATABASE_URL)
    args = parser.parse_args()
    if seed(args.database_url, reset=args.reset):
        print(f"Seeded {len(DEMO_ACCOUNTS)} accounts and {len(DEMO_ACTIVITY)} transactions into {args.database_url}")
    else:
        print("Database already has accounts; nothing to do (use --reset to reseed).")


if __name__ == "__main__":
    main()
