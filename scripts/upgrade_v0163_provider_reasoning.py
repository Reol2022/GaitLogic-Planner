from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from planner_core.database.models import ProviderReasoningRecord
from planner_core.database.session import engine


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the internal Provider reasoning table.")
    parser.add_argument("action", choices=("upgrade", "downgrade"), nargs="?", default="upgrade")
    args = parser.parse_args()
    with engine.begin() as connection:
        if args.action == "upgrade":
            ProviderReasoningRecord.__table__.create(bind=connection, checkfirst=True)
        else:
            ProviderReasoningRecord.__table__.drop(bind=connection, checkfirst=True)
    print(f"provider reasoning migration {args.action} completed")


if __name__ == "__main__":
    main()
