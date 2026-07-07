from __future__ import annotations

import argparse
from datetime import datetime

from sqlalchemy import delete, select

from planner_core.database.models import ExternalActivityRaw
from planner_core.database.session import SessionLocal


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean expired desensitized external activity raw payloads.")
    parser.add_argument("--dry-run", action="store_true", help="Only print the number of rows that would be removed.")
    args = parser.parse_args()
    now = datetime.utcnow()
    with SessionLocal() as db:
        count = len(
            db.scalars(
                select(ExternalActivityRaw.id).where(
                    ExternalActivityRaw.expires_at.is_not(None),
                    ExternalActivityRaw.expires_at < now,
                )
            ).all()
        )
        if args.dry_run:
            print(f"Expired external_activity_raw rows: {count}")
            return
        db.execute(
            delete(ExternalActivityRaw).where(
                ExternalActivityRaw.expires_at.is_not(None),
                ExternalActivityRaw.expires_at < now,
            )
        )
        db.commit()
        print(f"Deleted expired external_activity_raw rows: {count}")


if __name__ == "__main__":
    main()
