"""Preview by default. Use explicit IDs and reviewed DB config before --apply."""
import argparse
import json
import logging
import sys
from datetime import date
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--user-id',type=int,required=True)
    parser.add_argument('--start',type=date.fromisoformat,required=True)
    parser.add_argument('--end',type=date.fromisoformat,required=True)
    parser.add_argument('--activity-id',type=int,action='append')
    parser.add_argument('--limit',type=int,default=30)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--confirm',default='')
    args=parser.parse_args()
    if args.apply and (args.confirm!='REFRESH_GARMIN_DETAILS' or not args.activity_id):
        parser.error('--apply requires explicit --activity-id selections and --confirm REFRESH_GARMIN_DETAILS')
    logging.disable(logging.CRITICAL)
    from planner_core.config import get_settings
    from urllib.parse import urlsplit
    # Print only non-secret target metadata; never print a connection string.
    settings=get_settings()
    url=urlsplit(settings.database_url)
    print(json.dumps({'database_host':url.hostname,'database_port':url.port,'database':url.path.lstrip('/'),'apply':args.apply}),flush=True)
    from planner_core.database.session import SessionLocal
    from server.services.garmin_detail_refresh_service import refresh_details
    with SessionLocal() as db:
        try:
            if not args.apply:
                db.connection().exec_driver_sql('START TRANSACTION READ ONLY')
            result=refresh_details(db,user_id=args.user_id,start=args.start,end=args.end,
                activity_ids=args.activity_id,limit=args.limit,apply=args.apply)
            if args.apply:db.commit()
            else:db.rollback()
            print(json.dumps(result))
        except Exception as exc:
            db.rollback()
            print(json.dumps({'status':'FAILED','exception_type':type(exc).__name__}))
            return 1
    return 0


if __name__=='__main__':
    raise SystemExit(main())
