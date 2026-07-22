from __future__ import annotations

import argparse
from pathlib import Path
import sys

from sqlalchemy.engine import Connection

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from planner_core.database.models import RunnerStateSnapshotTriggerReceipt
from planner_core.database.session import engine


def upgrade(connection: Connection) -> None:
    """Create only the runner-state automatic-trigger receipt table."""
    RunnerStateSnapshotTriggerReceipt.__table__.create(bind=connection, checkfirst=False)


def downgrade(connection: Connection) -> None:
    """Drop only the runner-state automatic-trigger receipt table."""
    RunnerStateSnapshotTriggerReceipt.__table__.drop(bind=connection, checkfirst=False)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate runner-state automatic snapshot trigger receipts."
    )
    parser.add_argument("action", choices=("upgrade", "downgrade"), nargs="?", default="upgrade")
    args = parser.parse_args()
    with engine.begin() as connection:
        if args.action == "upgrade":
            upgrade(connection)
        else:
            downgrade(connection)
    print(f"runner-state snapshot receipt migration {args.action} completed")


if __name__ == "__main__":
    main()
