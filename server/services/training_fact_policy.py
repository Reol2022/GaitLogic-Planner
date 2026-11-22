"""Shared factual conventions; no intensity inference or plan mutations."""
from math import isfinite


def recorded_date(log, plan):
    return log.activity_date or (plan.workout_date if plan is not None else None)


def recorded_distance(value):
    if value is None:
        return None
    number = float(value)
    return number if isfinite(number) and number >= 0 else None


def record_source(value):
    normalized = str(value or '').strip().lower()
    if normalized.startswith('garmin'):
        return 'GARMIN'
    if 'import' in normalized:
        return 'IMPORT'
    if normalized in {'manual', 'manual_edit', 'manual_entry'}:
        return 'MANUAL'
    return 'UNKNOWN'


def origin_source(log):
    # Field provenance is a declaration, NOT independent verification.
    fields = {'actual_distance_km', 'actual_duration_seconds', 'avg_pace_seconds_per_km',
              'avg_heart_rate', 'max_heart_rate', 'moving_time_seconds'}
    declared = {record_source(value) for key, value in (log.field_sources_json or {}).items() if key in fields}
    declared.discard('UNKNOWN')
    if len(declared) > 1:
        return 'MIXED'
    if declared:
        return declared.pop()
    return 'GARMIN' if record_source(log.source_type) == 'GARMIN' else 'UNKNOWN'


def actual_training_type(log):
    value = log.workout_type or None
    if value is not None and str(value).lower() == 'unknown':
        return None
    if log.source_type == 'garmin_sync' and (log.field_sources_json or {}).get('workout_type') not in {'manual', 'manual_edit', 'garmin_actual'}:
        return None
    if value == 'rest' and log.actual_distance_km is not None and log.actual_distance_km > 0:
        return None
    return value


def classification_evidence(log):
    value = actual_training_type(log)
    source = (log.field_sources_json or {}).get('workout_type')
    if not value or str(value).lower() == 'unknown':
        return {'source': 'UNKNOWN', 'confirmation_status': 'UNCONFIRMED'}
    if source in {'manual', 'manual_edit'}:
        return {'source': 'USER_REPORTED_FACT', 'confirmation_status': 'USER_CONFIRMED'}
    if source == 'garmin_actual':
        return {'source': 'PROVIDER_RECORDED', 'confirmation_status': 'PROVIDER_DECLARED'}
    return {'source': 'RECORDED_UNVERIFIED', 'confirmation_status': 'UNCONFIRMED'}


def classification_coverage(logs):
    rows = list(logs)
    known = sum(bool(actual_training_type(log)) and str(actual_training_type(log)).lower() != 'unknown' for log in rows)
    confirmed = sum(classification_evidence(log)['confirmation_status'] != 'UNCONFIRMED' for log in rows)
    return {'classified_sessions': known, 'unclassified_sessions': len(rows)-known,
        'classification_coverage': round(known/len(rows), 4) if rows else None,
        'key_session_count_status': 'COMPLETE' if rows and confirmed == len(rows) else 'PARTIAL' if known else 'UNKNOWN'}
