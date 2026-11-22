"""Read-only stored-activity acceptance; no Provider requests, sync or exports.

Targets are explicit CLI arguments. Public tests use synthetic records only.
"""
import argparse
from datetime import date
import json


def verify(db, *, user_id, activity_id, expected_date, minimum_laps=2):
    from planner_core.database.models import ExternalActivity
    from server.mcp.facts_v2 import read_training_detail
    activity = db.get(ExternalActivity, activity_id)
    if activity is None or activity.user_id != user_id or activity.activity_date != expected_date:
        raise ValueError('Target identity/date mismatch')
    result = read_training_detail(db, user_id, f'external_activity:{activity_id}')
    validation = result.segment_validation
    return {'status': 'PASS' if len(result.normalized_segments) >= minimum_laps
        and validation.get('structure_complete') is True else 'PARTIAL',
        'raw_rows_returned': len(result.segments), 'normalized_rows': len(result.normalized_segments),
        'approximately_kilometre_rows': sum(row.distance_m is not None and 980 <= row.distance_m <= 1020
            for row in result.normalized_segments),
        'distance_consistent': validation.get('distance_consistent'),
        'time_consistent': validation.get('time_consistent'),
        'structure_complete': validation.get('structure_complete'),
        'issue_codes': [issue.code for issue in result.fact_issues],
        'classification': result.activity_classification.get('primary_type', 'UNKNOWN'),
        'database_writes': False, 'provider_calls': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--user-id', type=int, required=True)
    parser.add_argument('--activity-id', type=int, required=True)
    parser.add_argument('--expected-date', type=date.fromisoformat, required=True)
    parser.add_argument('--minimum-laps', type=int, default=2)
    args = parser.parse_args()
    if min(args.user_id, args.activity_id, args.minimum_laps) <= 0 or args.minimum_laps > 100:
        parser.error('Invalid target or lap bound')
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from planner_core.config import get_settings
    engine = create_engine(get_settings().database_url, hide_parameters=True)
    try:
        with Session(engine) as db:
            db.connection().exec_driver_sql('SET TRANSACTION READ ONLY')
            report = verify(db, user_id=args.user_id, activity_id=args.activity_id,
                expected_date=args.expected_date, minimum_laps=args.minimum_laps)
            db.rollback()
        print(json.dumps(report))
        return 0 if report['status'] == 'PASS' else 1
    finally:
        engine.dispose()


if __name__ == '__main__':
    raise SystemExit(main())
