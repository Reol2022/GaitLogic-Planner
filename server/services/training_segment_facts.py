"""Conservative structural facts. No inferred intensity, repetitions or risk."""
from math import isfinite


def number(value):
    if value is None or isinstance(value, bool):
        return None
    value = float(value)
    return value if isfinite(value) and value >= 0 else None


def normalize_segments(activity, laps, *, truncated=False):
    retained, seen, intervals = [], {}, []
    summaries = duplicates = 0
    overlap = False
    conflict = False
    for lap in laps:
        kind = str(getattr(lap, 'lap_type', None) or '').upper()
        source = getattr(lap, 'classification_source', None)
        start = getattr(lap, 'start_offset_seconds', None)
        stamp = getattr(lap, 'start_time', None)
        # Historical splitSummaries were stored as laps without a source flag.
        aggregate = (source == 'garmin_summary_rollup' or getattr(lap, 'segment_role', None) == 'summary'
            or kind.startswith('RWD_') or (kind.startswith('INTERVAL_') and source != 'garmin_lap_dto' and start is None and stamp is None))
        if aggregate:
            summaries += 1
            continue
        boundary = ('offset', start) if start is not None else ('time', stamp) if stamp is not None else None
        identity = getattr(lap, 'external_lap_id', None)
        key = ('id', identity) if identity else (boundary, getattr(lap, 'duration_seconds', None), getattr(lap, 'distance_m', None)) if boundary is not None else None
        if key is not None and key in seen:
            signature = (getattr(lap, 'distance_m', None), getattr(lap, 'duration_seconds', None), boundary)
            if seen[key] != signature:
                conflict = True
            duplicates += 1
            continue
        if key is not None:
            seen[key] = (getattr(lap, 'distance_m', None), getattr(lap, 'duration_seconds', None), boundary)
        retained.append(lap)
        duration = number(getattr(lap, 'duration_seconds', None))
        if boundary and duration is not None:
            begin = float(start) if start is not None else stamp.timestamp()
            intervals.append((boundary[0], begin, begin + duration))
    for kind in ('offset', 'time'):
        periods = sorted((start, end) for mode, start, end in intervals if mode == kind)
        furthest = None
        for start, end in periods:
            if furthest is not None and start < furthest - 1:
                overlap = True
            furthest = max(furthest, end) if furthest is not None else end
    distances = [number(getattr(lap, 'distance_m', None)) for lap in retained]
    target = number(getattr(activity, 'distance_m', None))
    distance_ok = abs(sum(distances) - target) <= 20 if retained and not truncated and target is not None and all(v is not None for v in distances) else None
    timer = number(getattr(activity, 'timer_time_seconds', None))
    times = [number(getattr(lap, 'timer_time_seconds', None)) for lap in retained]
    if timer is None or not times or any(t is None for t in times):
        timer = number(getattr(activity, 'duration_seconds', None))
        times = [number(getattr(lap, 'duration_seconds', None)) for lap in retained]
    time_ok = abs(sum(times) - timer) <= max(2, len(times) * .5) if retained and not truncated and timer is not None and all(t is not None for t in times) else None
    complete = bool(retained) and not truncated and not overlap and not conflict and distance_ok is True and time_ok is True
    validation = {'distance_consistent': distance_ok, 'time_consistent': time_ok,
        'overlapping_segments': overlap, 'structure_complete': complete,
        'confidence': 'VALIDATED_STRUCTURE' if complete else 'INCOMPLETE',
        'excluded_summary_count': summaries, 'deduplicated_count': duplicates,
        'raw_laps_truncated': truncated, 'conflicting_duplicate': conflict}
    # Do not make an arbitrary winner selection among overlapping representations.
    return ([] if overlap or conflict else retained), validation


def classify_segments(laps, validation):
    unknown = {'primary_type': 'UNKNOWN', 'components': [], 'confidence': 'INSUFFICIENT',
        'evidence_source': 'STORED_GARMIN_LAPS', 'requires_confirmation': True}
    if not validation['structure_complete']:
        return unknown
    work = [lap for lap in laps if str(getattr(lap, 'workout_step_type', '') or '').upper() in {'ACTIVE', 'INTERVAL_ACTIVE'}]
    if len(work) < 2:
        return unknown
    # Count only individually stored work laps, never divide an aggregate by a
    # reported repetition distance or label physiological zones from pace alone.
    return {'primary_type': 'interval_speed', 'components': [
        {'type': 'work_interval', 'lap_index': lap.lap_index, 'distance_m': float(lap.distance_m),
         'duration_seconds': lap.duration_seconds} for lap in work],
        'confidence': 'STRUCTURE_ONLY', 'evidence_source': 'STORED_GARMIN_LAPS',
        'requires_confirmation': False}
