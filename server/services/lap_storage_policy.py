"""Conservative lap replacement and private version evidence; no inference."""
from datetime import datetime, timedelta
import hashlib
import json
from decimal import Decimal
from math import isfinite

from sqlalchemy import select
from planner_core.config import get_settings
from planner_core.database.models import ExternalActivityRaw
from server.services.training_segment_facts import normalize_segments

LAP_FIELDS = ('lap_index', 'external_lap_id', 'start_time', 'start_offset_seconds',
    'distance_m', 'duration_seconds', 'timer_time_seconds', 'moving_time_seconds',
    'average_speed_mps', 'average_heart_rate_bpm', 'max_heart_rate_bpm',
    'average_cadence_spm', 'elevation_gain_m', 'lap_type', 'workout_step_type',
    'segment_role', 'classification_source', 'classification_confidence', 'data_quality')


def _payload(summary, rows):
    def canonical(value):
        if isinstance(value, dict): return {key: canonical(item) for key, item in value.items()}
        if isinstance(value, list): return [canonical(item) for item in value]
        if isinstance(value, (Decimal, float, int)) and not isinstance(value, bool):
            number = float(value)
            return (int(number) if number.is_integer() else number) if isfinite(number) else None
        return value.isoformat() if isinstance(value, datetime) else value
    return json.loads(json.dumps(canonical({'kind': 'lap_snapshot_v1',
        'summary': {name: getattr(summary, name, None) for name in ('distance_m', 'duration_seconds', 'timer_time_seconds')},
        'lap_count': len(rows), 'snapshot_truncated': len(rows) > 1000,
        'laps': [{name: getattr(row, name, None) for name in LAP_FIELDS} for row in rows[:1000]]}), default=str))


def _digest(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def _archive(db, activity, payload):
    digest = _digest(payload)
    existing = db.scalar(select(ExternalActivityRaw.id).where(ExternalActivityRaw.user_id == activity.user_id,
        ExternalActivityRaw.provider == activity.provider, ExternalActivityRaw.external_activity_id == activity.external_activity_id,
        ExternalActivityRaw.payload_hash == digest))
    if existing is None:
        now = datetime.utcnow()
        db.add(ExternalActivityRaw(user_id=activity.user_id, connection_id=activity.connection_id,
            sync_job_id=activity.sync_job_id, provider=activity.provider, external_activity_id=activity.external_activity_id,
            payload_hash=digest, raw_payload_json=payload, fetched_at=now,
            expires_at=now+timedelta(days=get_settings().garmin_raw_retention_days)))
    return digest


def profile(summary, rows):
    normalized, valid = normalize_segments(summary, rows, truncated=len(rows) > 1000)
    # Usable detail means a distinct row with positive recorded distance/time.
    usable = [row for row in normalized if row.distance_m is not None and row.distance_m > 0
        and row.duration_seconds is not None and row.duration_seconds > 0]
    return {'detail_count': len(usable), 'complete': valid['structure_complete'],
        'conflicted': valid['overlapping_segments'] or valid['conflicting_duplicate'],
        'boundary_count': sum(getattr(row, 'start_time', None) is not None or getattr(row, 'start_offset_seconds', None) is not None for row in usable),
        'heart_rate_count': sum(getattr(row, 'average_heart_rate_bpm', None) is not None for row in usable),
        'cadence_count': sum(getattr(row, 'average_cadence_spm', None) is not None for row in usable)}


def replacement_decision(previous_summary, previous, candidate_summary, candidate):
    old, new = profile(previous_summary, previous), profile(candidate_summary, candidate)
    if not candidate:
        return False, 'EMPTY_OR_UNAVAILABLE', old, new
    if not previous:
        return True, 'INITIAL_IMPORT', old, new
    if old['detail_count']:
        if not new['detail_count']:
            return False, 'COARSER_REPRESENTATION', old, new
        if new['conflicted'] or (old['complete'] and not new['complete']):
            return False, 'STRUCTURE_REGRESSION', old, new
        for field in ('detail_count', 'boundary_count', 'heart_rate_count', 'cadence_count'):
            if new[field] < old[field]:
                return False, 'DETAIL_COVERAGE_REGRESSION', old, new
    return True, 'ACCEPTED', old, new


def prepare_replacement(db, activity, previous_summary, previous, candidate_summary, candidate):
    accepted, reason, old, new = replacement_decision(previous_summary, previous, candidate_summary, candidate)
    current_digest = _archive(db, activity, _payload(previous_summary, previous)) if previous else None
    candidate_digest = _archive(db, activity, _payload(candidate_summary, candidate)) if candidate else None
    metadata = (activity.field_sources_json or {}).get('lap_sync') or {}
    version = metadata.get('version')
    version = version if type(version) is int and version >= 0 else int(bool(previous))
    changed = accepted and candidate_digest != current_digest
    activity.field_sources_json = {**(activity.field_sources_json or {}), 'lap_sync': {
        'version': version+int(changed), 'decision': 'ACCEPTED' if changed else 'UNCHANGED' if accepted else 'PRESERVED',
        'reason': reason, 'current_digest': candidate_digest if accepted else current_digest,
        'candidate_digest': candidate_digest, 'checked_at': datetime.utcnow().isoformat(),
        'current_detail_count': new['detail_count'] if accepted else old['detail_count'],
        'candidate_detail_count': new['detail_count'], 'requires_review': bool(previous and candidate and not accepted),
    }}
    return accepted and changed
