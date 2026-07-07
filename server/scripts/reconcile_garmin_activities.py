from __future__ import annotations

import argparse
from datetime import date

from planner_core.database.session import SessionLocal
from server.schemas.garmin_sync import GarminActivityReconcileRequest
from server.services.garmin_sync_service import reconcile_activities


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reconcile Garmin activities into workout logs.")
    parser.add_argument("--user-id", type=int, required=True)
    parser.add_argument("--start-date", type=date.fromisoformat)
    parser.add_argument("--end-date", type=date.fromisoformat)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--activity-id", type=int, action="append", dest="activity_ids")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = GarminActivityReconcileRequest(
        start_date=args.start_date,
        end_date=args.end_date,
        dry_run=args.dry_run,
        activity_ids=args.activity_ids,
    )
    with SessionLocal() as db:
        result = reconcile_activities(db, args.user_id, payload)
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
