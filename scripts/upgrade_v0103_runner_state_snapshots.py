from __future__ import annotations

import argparse
from pathlib import Path
import sys

from sqlalchemy.engine import Connection

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from planner_core.database.models import RunnerStateSnapshotRecord
from planner_core.database.session import engine


def upgrade(connection: Connection) -> None:
    """Create only the runner-state snapshot table.

    checkfirst=False is intentional: running the same migration twice must fail
    instead of disguising a deployment error as a successful upgrade.
    """
    RunnerStateSnapshotRecord.__table__.create(bind=connection, checkfirst=False)


def downgrade(connection: Connection) -> None:
    RunnerStateSnapshotRecord.__table__.drop(bind=connection, checkfirst=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate runner-state snapshot storage.")
    parser.add_argument(
        "action",
        choices=("upgrade", "downgrade"),
        nargs="?",
        default="upgrade",
    )
    args = parser.parse_args()
    with engine.begin() as connection:
        if args.action == "upgrade":
            upgrade(connection)
        else:
            downgrade(connection)
    print(f"runner-state snapshot migration {args.action} completed")


if __name__ == "__main__":
    main()
