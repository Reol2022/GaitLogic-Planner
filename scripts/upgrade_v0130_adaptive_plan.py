from __future__ import annotations

import argparse
from pathlib import Path
import sys

from sqlalchemy.engine import Connection

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from planner_core.database.models import (
    AdaptivePlanVersionRecord,
    AdaptiveWorkflowCheckpointRecord,
    AdaptiveWorkflowCheckpointWriteRecord,
)
from planner_core.database.session import engine


TABLES = (
    AdaptivePlanVersionRecord.__table__,
    AdaptiveWorkflowCheckpointRecord.__table__,
    AdaptiveWorkflowCheckpointWriteRecord.__table__,
)


def upgrade(connection: Connection) -> None:
    for table in TABLES:
        table.create(bind=connection, checkfirst=False)


def downgrade(connection: Connection) -> None:
    for table in reversed(TABLES):
        table.drop(bind=connection, checkfirst=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate v0.13 adaptive plan audit and workflow checkpoint tables.")
    parser.add_argument("action", choices=("upgrade", "downgrade"), nargs="?", default="upgrade")
    args = parser.parse_args()
    with engine.begin() as connection:
        (upgrade if args.action == "upgrade" else downgrade)(connection)
    print(f"v0.13 adaptive plan migration {args.action} completed")


if __name__ == "__main__":
    main()
