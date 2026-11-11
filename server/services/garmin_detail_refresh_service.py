"""Explicit, bounded stored-activity refresh; dry-run by default, no new logs."""
from datetime import date, datetime
from sqlalchemy import select, or_
from planner_core.database.models import ExternalActivity, WorkoutLog, WorkoutLogExternalActivity
from server.common.exceptions import BadRequestError
from server.integrations.activity_provider.base import ProviderError
from server.services.weekly_review_stats_service import local_today


def refresh_details(db, *, user_id: int, start: date, end: date,
                    activity_ids: list[int] | None = None, limit: int = 30, apply: bool = False):
    from server.services import garmin_sync_service as sync
    from server.services.token_encryption_service import decrypt_token_payload
    if start > end or (end-start).days > 27 or end > local_today() or not 1 <= limit <= 30:
        raise BadRequestError("详情刷新范围必须是截至今天的最多28天，每批最多30条。")
    if activity_ids is not None and (not activity_ids or len(activity_ids) > 30):
        raise BadRequestError("请明确选择1至30条活动。")
    query = select(ExternalActivity).where(ExternalActivity.user_id == user_id,
        ExternalActivity.provider == "garmin", ExternalActivity.activity_date.between(start,end))
    if activity_ids is not None:
        query = query.where(ExternalActivity.id.in_(activity_ids))
    rows = list(db.scalars(query.order_by(ExternalActivity.activity_date.desc(), ExternalActivity.id.desc()).limit(limit+1)))
    if activity_ids is not None and {r.id for r in rows} != set(activity_ids):
        raise BadRequestError("活动不在当前用户的授权日期范围内。")
    report = {"dry_run": not apply, "activity_refs": [f"external_activity:{r.id}" for r in rows[:limit]],
        "has_more": len(rows)>limit, "updated":0, "failed":0, "error_codes":[], "failures":[]}
    if not apply:
        return report
    providers = {}
    for row in rows[:limit]:
        try:
            with db.begin_nested():
                if row.connection_id not in providers:
                    connection = sync._require_connection(db, user_id)
                    if connection.id != row.connection_id:
                        raise ProviderError("CONNECTION_MISMATCH", "活动来自不同的设备连接。")
                    provider = sync._provider_for_connection(connection)
                    provider.restore_session(decrypt_token_payload(connection.encrypted_token_payload))
                    providers[row.connection_id] = provider
                detail = providers[row.connection_id].fetch_activity_summary(row.external_activity_id)
                if detail.external_activity_id != row.external_activity_id:
                    raise ProviderError("ACTIVITY_DETAIL_MISMATCH", "活动详情引用不一致。")
                # Refresh sparse detail metrics without wiping previous valid metrics.
                from dataclasses import fields
                for f in fields(detail):
                    if getattr(detail,f.name) is None and hasattr(row,f.name):
                        setattr(detail,f.name,getattr(row,f.name))
                sync._copy_activity_metrics(row, detail)
                row.fetched_at = datetime.utcnow()
                sync._replace_laps(db, row, detail)
                linked = select(WorkoutLogExternalActivity.workout_log_id).where(
                    WorkoutLogExternalActivity.user_id == user_id, WorkoutLogExternalActivity.external_activity_id == row.id)
                logs = list(db.scalars(select(WorkoutLog).where(WorkoutLog.user_id == user_id,
                    or_(WorkoutLog.id.in_(linked), WorkoutLog.id == row.workout_log_id))))
                for log in logs:
                    sync._recalculate_log_from_linked_activities(db, log)
            report["updated"] += 1
        except ProviderError as exc:
            report["failed"] += 1
            report["failures"].append({"activity_ref":f"external_activity:{row.id}","code":exc.code})
            if exc.code not in report["error_codes"]:
                report["error_codes"].append(exc.code)
    # Caller owns commit/rollback. No sync cursor, formal plan, or cycle activation changes.
    return report
