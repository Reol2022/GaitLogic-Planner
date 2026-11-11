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
    if log.source_type == 'garmin_sync' and (log.field_sources_json or {}).get('workout_type') not in {'manual', 'garmin_actual'}:
        return None
    if value == 'rest' and log.actual_distance_km is not None and log.actual_distance_km > 0:
        return None
    return value
