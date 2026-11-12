"""Bounded read-only projections. No provider calls, inference or persistence."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from datetime import date, timedelta
from typing import Literal

from pydantic import Field, model_validator
from sqlalchemy import select, or_, func
from sqlalchemy.orm import Session

from planner_core.database.models import DailyRecoveryCheckin, ExternalAccountConnection, ExternalActivity, ExternalActivityLap, PlannedWorkout, WorkoutLog, WorkoutLogExternalActivity
from server.mcp.errors import McpErrorCode, McpSafeError
from server.mcp.schemas import McpContractModel, McpRecentTrainingItem, McpRecentTraining, McpRecentTrainingSummary, McpTrainingFactIssue, McpDataQuality, _McpToolResult
from server.mcp.schemas import McpVersionedData
from server.services.auth_service import signing_key
from server.services.training_segment_facts import normalize_segments, classify_segments
from server.integrations.activity_provider.self_evaluation import effective_log_rpe
from server.services.training_load_service import _query_logs, _safe_source
from server.services.weekly_review_stats_service import COMPLETED_STATUSES, local_today
from server.domain.review_thresholds import KEY_WORKOUT_TYPES
from server.services.training_fact_policy import origin_source, recorded_distance
from server.integrations.activity_provider.self_evaluation import activity_rpe, log_rpe_metadata


def _value(value):
    return getattr(value, 'value', value)


def training_item(log: WorkoutLog, plan: PlannedWorkout | None) -> McpRecentTrainingItem:
    planned = str(_value(plan.main_type_normalized)) if plan else None
    actual = log.workout_type or None
    if log.source_type == 'garmin_sync' and (log.field_sources_json or {}).get('workout_type') not in {'manual', 'garmin_actual'}:
        actual = None
    # A recorded type of rest is not a valid classification of a nonzero run.
    if actual == 'rest' and log.actual_distance_km is not None and log.actual_distance_km > 0:
        actual = None
    return McpRecentTrainingItem(
        record_ref=f'workout_log:{log.id}', date=log.activity_date or plan.workout_date,
        training_type=actual or 'unknown', planned_training_type=planned,
        actual_training_type=actual, classification_basis='ACTUAL_LOG' if actual else 'UNKNOWN',
        planned_or_unplanned='UNPLANNED' if log.is_unplanned or plan is None else 'PLANNED',
        completion_status=str(_value(log.status_normalized)),
        distance_km=recorded_distance(log.actual_distance_km),
        duration_seconds=log.actual_duration_seconds, average_pace_seconds_per_km=log.avg_pace_seconds_per_km,
        average_heart_rate=log.avg_heart_rate, rpe=effective_log_rpe(log) if effective_log_rpe(log) is not None and 0 <= effective_log_rpe(log) <= 10 else None,
        rpe_metadata=log_rpe_metadata(log),
        source=_safe_source(log.source_type), origin_source=origin_source(log),
    )


def encode_cursor(payload: dict) -> str:
    body = base64.urlsafe_b64encode(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).decode().rstrip('=')
    signature = hmac.new(signing_key(), body.encode(), hashlib.sha256).hexdigest()
    return body + '.' + signature


def decode_cursor(cursor: str) -> dict:
    try:
        if len(cursor) > 2048: raise ValueError()
        body, signature = cursor.split('.')
        expected = hmac.new(signing_key(), body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected): raise ValueError()
        result = json.loads(base64.urlsafe_b64decode(body + '=' * (-len(body) % 4)))
        if not isinstance(result, dict) or set(result) != {'binding','days','start','end','offset','snapshot','expires'}: raise ValueError()
        if type(result['expires']) is not int or result['expires'] < time.time(): raise ValueError()
        date.fromisoformat(result['start']); date.fromisoformat(result['end'])
        return result
    except (KeyError, TypeError, ValueError):
        raise McpSafeError(McpErrorCode.INVALID_ARGUMENT) from None


def read_training(db: Session, user_id: int, *, days: int = 7, limit: int = 20, cursor: str | None = None, start_date: date | None = None, end_date: date | None = None) -> McpRecentTraining:
    if isinstance(days, bool) or isinstance(limit, bool) or not 1 <= days <= 90 or not 1 <= limit <= 20 or bool(start_date) != bool(end_date):
        raise McpSafeError(McpErrorCode.INVALID_ARGUMENT)
    previous = decode_cursor(cursor) if cursor else None
    end = end_date or (date.fromisoformat(previous['end']) if previous else local_today())
    start = start_date or (end - timedelta(days=days-1))
    if start > end or end > local_today() or (end-start).days >= 90:
        raise McpSafeError(McpErrorCode.INVALID_ARGUMENT)
    binding = hmac.new(signing_key(), f'{user_id}:{start}:{end}:{limit}'.encode(), hashlib.sha256).hexdigest()
    if previous and (previous.get('binding') != binding or previous.get('days') != days):
        raise McpSafeError(McpErrorCode.INVALID_ARGUMENT)
    rows = [(log, plan) for log, plan in _query_logs(db, user_id, start, end) if log.status_normalized in COMPLETED_STATUSES]
    if len(rows) > 5000: raise McpSafeError(McpErrorCode.DATA_UNAVAILABLE)
    # Stable canonical order independent of query execution order.
    rows.sort(key=lambda row: (row[0].activity_date or row[1].workout_date, row[0].id), reverse=True)
    items = [training_item(log, plan) for log, plan in rows]
    issues = []
    if any(log.workout_type == 'rest' and log.actual_distance_km is not None and log.actual_distance_km > 0 for log, _ in rows):
        issues.append(McpTrainingFactIssue(code='RECORDED_TYPE_DISTANCE_CONFLICT', message='A recorded rest type has positive running distance; its actual training type is withheld, not inferred.', affected_metrics=['actual_training_type', 'completed_key_sessions']))
    planned_rest = set(db.scalars(select(PlannedWorkout.workout_date).where(PlannedWorkout.user_id == user_id, PlannedWorkout.workout_date >= start, PlannedWorkout.workout_date <= end, PlannedWorkout.main_type_normalized == 'rest')).all())
    digest = hashlib.sha256(json.dumps({'items':[item.model_dump(mode='json') for item in items], 'planned_rest':sorted(str(day) for day in planned_rest)}, sort_keys=True).encode()).hexdigest()
    if previous and previous.get('snapshot') != digest: raise McpSafeError(McpErrorCode.CURSOR_STALE)
    offset = previous.get('offset', 0) if previous else 0
    if type(offset) is not int or not 0 <= offset <= len(items): raise McpSafeError(McpErrorCode.INVALID_ARGUMENT)
    next_offset = offset + limit
    next_cursor = encode_cursor({'binding':binding, 'days':days, 'start':str(start), 'end':str(end), 'offset':next_offset, 'snapshot':digest, 'expires':previous['expires'] if previous else int(time.time())+900}) if next_offset < len(items) else None
    distances = [item.distance_km for item in items if item.distance_km is not None]
    actual_dates = {item.date for item in items if item.distance_km is not None and item.distance_km > 0}
    core = ('distance_km', 'duration_seconds', 'rpe', 'actual_training_type')
    missing = [field for field in core if any(getattr(item, field) is None for item in items)]
    completeness = sum(getattr(item, field) is not None for item in items for field in core) / (len(items)*len(core)) if items else 0
    return McpRecentTraining(data_status='PARTIAL' if missing or not items or issues else 'AVAILABLE', as_of=end, range_start=start, range_end=end, fact_issues=issues,
        items=items[offset:next_offset], next_cursor=next_cursor, details_complete=offset == 0 and next_cursor is None,
        summary=McpRecentTrainingSummary(total_sessions=len(items), total_distance_km=round(sum(distances), 2) if distances else None,
            completed_key_sessions=sum(item.actual_training_type in KEY_WORKOUT_TYPES for item in items), rest_days=len(planned_rest-actual_dates)),
        planned_rest_days=len(planned_rest), data_quality=McpDataQuality(level='PARTIAL' if missing else 'UNKNOWN', completeness=completeness, missing_fields=missing),
        missing_reasons=['Record type is not an inferred intensity classification; origin is unknown unless independently linked.', 'rest_days counts planned rest days without a recorded positive-distance run, not confirmed physiological rest.'])


class McpSegment(McpContractModel):
    index: int
    role: str = Field(max_length=32)
    distance_m: float | None
    duration_seconds: int | None
    average_pace_seconds_per_km: int | None
    quality: str = Field(max_length=32)
    activity_ref: str | None = None
    start_time: str | None = None
    start_offset_seconds: int | None = None
    timer_time_seconds: int | None = None
    moving_time_seconds: int | None = None
    average_heart_rate_bpm: int | None = None
    max_heart_rate_bpm: int | None = None
    average_cadence_spm: int | None = None
    elevation_gain_m: float | None = None
    lap_type: str | None = Field(default=None, max_length=64)


class McpActivitySummary(McpContractModel):
    activity_ref: str
    date: date
    source: str
    start_time_local: str
    timezone: str
    distance_km: float | None
    duration_seconds: int | None
    average_pace_seconds_per_km: int | None
    average_heart_rate_bpm: int | None
    verification_status: Literal['PROVIDER_RECORDED_NOT_INDEPENDENTLY_VERIFIED'] = 'PROVIDER_RECORDED_NOT_INDEPENDENTLY_VERIFIED'


class McpActivityDetail(McpActivitySummary):
    rpe: int | None = Field(default=None, ge=1, le=10)
    rpe_evidence: dict[str, str | int | float | None] = Field(default_factory=dict)
    average_speed_mps: float | None = None
    max_speed_mps: float | None = None
    pause_total_seconds: int | None = None
    pause_basis: str = 'ELAPSED_MINUS_TIMER_WHEN_AVAILABLE_NOT_PAUSE_TIMELINE'
    actual_training_type: str = 'UNKNOWN'
    start_time_utc: str | None = None
    timer_time_seconds: int | None = None
    moving_time_seconds: int | None = None
    elapsed_time_seconds: int | None = None
    max_heart_rate_bpm: int | None = None
    average_cadence_spm: int | None = None
    max_cadence_spm: int | None = None
    elevation_gain_m: float | None = None
    elevation_loss_m: float | None = None
    calories_kcal: int | None = None
    average_stride_length_m: float | None = None
    average_vertical_ratio_percent: float | None = None
    average_vertical_oscillation_cm: float | None = None
    average_ground_contact_time_ms: float | None = None
    ground_contact_balance_percent: float | None = None
    average_running_power_w: int | None = None
    max_running_power_w: int | None = None
    data_quality: str
    fetched_at: str | None = None
    field_sources: dict[str, str] = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)


def _activity_summary(row):
    distance = recorded_distance(row.distance_m)
    return McpActivitySummary(activity_ref=f'external_activity:{row.id}', date=row.activity_date,
        source=_safe_source(row.provider), start_time_local=row.start_time_local.isoformat(), timezone=row.timezone,
        distance_km=round(distance / 1000, 5) if distance is not None else None,
        duration_seconds=row.duration_seconds, average_pace_seconds_per_km=row.average_pace_seconds_per_km,
        average_heart_rate_bpm=row.average_heart_rate_bpm)


_ACTIVITY_METRICS = ('timer_time_seconds', 'moving_time_seconds', 'elapsed_time_seconds',
    'max_heart_rate_bpm', 'average_cadence_spm', 'max_cadence_spm', 'elevation_gain_m', 'elevation_loss_m',
    'calories_kcal', 'average_stride_length_m', 'average_vertical_ratio_percent', 'average_vertical_oscillation_cm',
    'average_ground_contact_time_ms', 'ground_contact_balance_percent', 'average_running_power_w', 'max_running_power_w')


def _activity_detail(row):
    from datetime import timezone
    metrics = {field: getattr(row, field) for field in _ACTIVITY_METRICS}
    allowed = set(_ACTIVITY_METRICS) | {'distance_m', 'duration_seconds', 'average_heart_rate_bpm', 'average_pace_seconds_per_km'}
    return McpActivityDetail(**_activity_summary(row).model_dump(), **metrics,
        rpe=activity_rpe(row).get('value'), rpe_evidence=activity_rpe(row),
        average_speed_mps=row.average_speed_mps, max_speed_mps=row.max_speed_mps,
        pause_total_seconds=(row.elapsed_time_seconds-row.timer_time_seconds
            if row.elapsed_time_seconds is not None and row.timer_time_seconds is not None
            and row.elapsed_time_seconds >= row.timer_time_seconds else None),
        start_time_utc=row.start_time_utc.replace(tzinfo=timezone.utc).isoformat() if row.start_time_utc else None,
        data_quality=row.data_quality, fetched_at=row.fetched_at.isoformat() if row.fetched_at else None,
        field_sources={key:_safe_source(value) for key,value in (row.field_sources_json or {}).items() if key in allowed},
        missing_fields=[field for field in sorted(allowed) if getattr(row,field) is None])


class McpTrainingDetail(McpVersionedData):
    record: McpRecentTrainingItem | None
    detail_scope: Literal['WORKOUT_LOG_SUMMARY', 'SELECTED_ACTIVITY'] = 'WORKOUT_LOG_SUMMARY'
    linked_activity_count: int = 0
    activities: list[McpActivitySummary] = Field(default_factory=list, max_length=20)
    activities_complete: bool = True
    selection_required: bool = False
    selected_activity: McpActivityDetail | None = None
    fact_issues: list[McpTrainingFactIssue] = Field(default_factory=list, max_length=20)
    segments_available: bool
    segments_complete: bool
    segments: list[McpSegment] = Field(default_factory=list, max_length=100)
    normalized_segments: list[McpSegment] = Field(default_factory=list, max_length=100)
    segment_validation: dict = Field(default_factory=dict)
    activity_classification: dict = Field(default_factory=dict)
    segments_scope: Literal['STORED_LAPS_FOR_SELECTED_ACTIVITY'] = 'STORED_LAPS_FOR_SELECTED_ACTIVITY'
    segment_distance_consistent: bool | None = None
    heart_rate_quality: Literal['UNKNOWN'] = 'UNKNOWN'
    limitations: list[str] = Field(default_factory=list, max_length=10)


class _FactResult(_McpToolResult):
    @model_validator(mode='after')
    def validate_fact_data(self):
        if (self.status == 'SUCCEEDED') != (self.data is not None):
            raise ValueError('Fact result data must match status')
        return self


class McpTrainingDetailResult(_FactResult):
    data: McpTrainingDetail | None = None


def read_training_detail(db: Session, user_id: int, record_ref: str, activity_ref: str | None = None) -> McpTrainingDetail:
    import re
    pattern = r'(workout_log|external_activity):[1-9][0-9]{0,17}'
    if not re.fullmatch(pattern, record_ref) or (activity_ref is not None and not re.fullmatch(r'external_activity:[1-9][0-9]{0,17}',activity_ref)):
        raise McpSafeError(McpErrorCode.INVALID_ARGUMENT)
    log = plan = selected = None
    if record_ref.startswith('workout_log:'):
        log = db.scalar(select(WorkoutLog).where(WorkoutLog.id == int(record_ref.split(':')[1]), WorkoutLog.user_id == user_id))
        if log is None: raise McpSafeError(McpErrorCode.RESOURCE_NOT_FOUND)
        plan = db.scalar(select(PlannedWorkout).where(PlannedWorkout.id == log.planned_workout_id, PlannedWorkout.user_id == user_id)) if log.planned_workout_id else None
        if log.activity_date is None and (plan is None or plan.workout_date is None): raise McpSafeError(McpErrorCode.DATA_UNAVAILABLE)
        links = select(WorkoutLogExternalActivity.external_activity_id).where(WorkoutLogExternalActivity.user_id == user_id, WorkoutLogExternalActivity.workout_log_id == log.id)
        conditions = [ExternalActivity.id.in_(links), ExternalActivity.workout_log_id == log.id]
        if log.external_activity_id:
            conditions.append(ExternalActivity.external_activity_id == log.external_activity_id)
        where = (ExternalActivity.user_id == user_id, or_(*conditions))
    else:
        if activity_ref is not None and activity_ref != record_ref: raise McpSafeError(McpErrorCode.INVALID_ARGUMENT)
        where = (ExternalActivity.user_id == user_id, ExternalActivity.id == int(record_ref.split(':')[1]))
    count = db.scalar(select(func.count()).select_from(ExternalActivity).where(*where))
    activities = list(db.scalars(select(ExternalActivity).where(*where).order_by(ExternalActivity.start_time_local,ExternalActivity.id).limit(20)).all())
    if activity_ref:
        selected = db.scalar(select(ExternalActivity).where(*where, ExternalActivity.id == int(activity_ref.split(':')[1])))
        if selected is None: raise McpSafeError(McpErrorCode.RESOURCE_NOT_FOUND)
    elif count == 1:
        selected = activities[0]
    if log is None and not activities: raise McpSafeError(McpErrorCode.RESOURCE_NOT_FOUND)
    # Never concatenate laps from warm-up, race and cooldown into one activity.
    laps = list(db.scalars(select(ExternalActivityLap).where(ExternalActivityLap.external_activity_id == selected.id).order_by(ExternalActivityLap.lap_index).limit(101)).all()) if selected else []
    issues = []
    if log is not None and count and count <= 20 and log.actual_distance_km is not None and all(a.distance_m is not None for a in activities):
        if abs(float(log.actual_distance_km)-sum(float(a.distance_m) for a in activities)/1000) > 0.02:
            issues.append(McpTrainingFactIssue(code='LOG_ACTIVITY_DISTANCE_MISMATCH',message='Recorded log distance differs from linked activity distances; neither source is overwritten.',affected_metrics=['distance_km']))
    segment_distance_consistent = None
    if selected and selected.distance_m is not None and laps and len(laps) <= 100 and all(lap.distance_m is not None for lap in laps):
        segment_distance_consistent = abs(float(selected.distance_m)-sum(float(lap.distance_m) for lap in laps)) <= 20
        if not segment_distance_consistent:
            issues.append(McpTrainingFactIssue(code='LAP_ACTIVITY_DISTANCE_MISMATCH',message='Stored lap distances do not match the selected activity distance; do not treat these laps as a complete race trace.',affected_metrics=['segments','distance_km']))
    normalized, validation = normalize_segments(selected, laps[:100], truncated=len(laps) > 100) if selected else ([], {})
    classification = classify_segments(normalized, validation) if selected else {}
    selected_detail = _activity_detail(selected) if selected else None
    if selected_detail is not None and classification.get('primary_type') != 'UNKNOWN':
        selected_detail = selected_detail.model_copy(update={'actual_training_type': classification['primary_type']})
    record = training_item(log, plan) if log else None
    if record is not None:
        record = record.model_copy(update={'rpe': effective_log_rpe(log, linked_activity_count=count),
            'rpe_metadata': log_rpe_metadata(log, linked_activity_count=count)})
        if record.rpe is None and log.rpe is not None:
            issues.append(McpTrainingFactIssue(code='ACTIVITY_RPE_NOT_SESSION_RPE',
                message='An activity rating cannot rate a multi-activity session; enter an independent session rating.', affected_metrics=['rpe']))
    def segment(lap):
        return McpSegment(index=lap.lap_index, role=lap.segment_role,
            distance_m=float(lap.distance_m) if lap.distance_m is not None else None,
            duration_seconds=lap.duration_seconds, average_pace_seconds_per_km=lap.average_pace_seconds_per_km,
            quality=lap.data_quality, activity_ref=f'external_activity:{selected.id}',
            start_time=lap.start_time.isoformat() if lap.start_time else None,
            start_offset_seconds=lap.start_offset_seconds, timer_time_seconds=lap.timer_time_seconds,
            moving_time_seconds=lap.moving_time_seconds, average_heart_rate_bpm=lap.average_heart_rate_bpm,
            max_heart_rate_bpm=lap.max_heart_rate_bpm, average_cadence_spm=lap.average_cadence_spm,
            elevation_gain_m=lap.elevation_gain_m, lap_type=lap.lap_type)
    return McpTrainingDetail(record=record,
        detail_scope='SELECTED_ACTIVITY' if selected else 'WORKOUT_LOG_SUMMARY', linked_activity_count=count,
        activities=[_activity_summary(a) for a in activities], activities_complete=count <= 20,
        selection_required=count > 1 and selected is None, selected_activity=selected_detail,
        fact_issues=issues, segment_distance_consistent=segment_distance_consistent,
        normalized_segments=[segment(lap) for lap in normalized], segment_validation=validation,
        activity_classification=classification,
        segments_available=bool(laps), segments_complete=bool(laps) and len(laps) <= 100,
        segments=[McpSegment(index=lap.lap_index, role=lap.segment_role, distance_m=float(lap.distance_m) if lap.distance_m is not None else None,
            duration_seconds=lap.duration_seconds, average_pace_seconds_per_km=lap.average_pace_seconds_per_km, quality=lap.data_quality,
            activity_ref=f'external_activity:{selected.id}', start_time=lap.start_time.isoformat() if lap.start_time else None,
            start_offset_seconds=lap.start_offset_seconds, timer_time_seconds=lap.timer_time_seconds, moving_time_seconds=lap.moving_time_seconds,
            average_heart_rate_bpm=lap.average_heart_rate_bpm,max_heart_rate_bpm=lap.max_heart_rate_bpm,
            average_cadence_spm=lap.average_cadence_spm,elevation_gain_m=lap.elevation_gain_m,lap_type=lap.lap_type) for lap in laps[:100]],
        limitations=['Log totals are not individual race results. Select an activity when multiple are linked.',
            'Stored laps are not necessarily kilometre splits. No GPS, raw payload, text notes or time-series are exported.',
            'segments_complete only describes returned stored laps, not upstream sync completeness or full race coverage.',
            'Legacy segments are raw stored rows, possibly category rollups; use normalized_segments and segment_validation for structure.',
            'Activity classification describes structure only, not physiological intensity or recovery readiness.',
            'Provider measurements are not independently verified; no causal diagnosis is inferred.'] + ([] if laps else ['No selected activity with stored laps is available.']))


class McpRecoveryDay(McpContractModel):
    date: date
    source: str = Field(max_length=32)
    hrv_value: float | None
    hrv_unit: str | None = Field(max_length=32)
    hrv_metric: str | None = Field(default=None, max_length=32)
    sleep_duration_minutes: int | None
    resting_heart_rate_bpm: int | None
    sleep_score: int | None
    body_battery_end: int | None
    subjective_fatigue: int | None
    synced_at: str | None
    updated_at: str | None
    measured_at: None = None
    missing_fields: list[str]
    field_sources: dict[str, str] = Field(default_factory=dict)
    age_days: int = Field(ge=0)
    sleep_quality: int | None = None
    average_stress: int | None = None
    max_stress: int | None = None
    muscle_soreness: int | None = None
    leg_feeling: int | None = None
    body_battery_start: int | None = None
    body_battery_high: int | None = None
    body_battery_low: int | None = None
    device_data_status: str = 'UNKNOWN'
    provider_updated_at: str | None = None
    missing_reasons: dict[str, Literal['NOT_RECORDED_OR_NOT_SYNCED', 'SYNC_FAILED', 'DEVICE_UNSUPPORTED']] = Field(default_factory=dict)


class McpRecoveryTrend(McpVersionedData):
    data_status: Literal['PARTIAL', 'AVAILABLE', 'EMPTY']
    as_of: date
    range_start: date
    range_end: date
    timezone: Literal['Asia/Shanghai'] = 'Asia/Shanghai'
    daily_records: list[McpRecoveryDay] = Field(max_length=28)
    missing_dates: list[date] = Field(max_length=28)
    baseline: None = None
    sync_status: Literal['NEVER_SYNCED','SYNCED','FAILED','UNKNOWN'] = 'UNKNOWN'
    last_sync_attempt_at: str | None = None
    last_successful_sync_at: str | None = None
    limitations: list[str]


class McpRecoveryTrendResult(_FactResult):
    data: McpRecoveryTrend | None = None


def read_recovery(db: Session, user_id: int, days: int = 7, *, start_date: date | None = None, end_date: date | None = None) -> McpRecoveryTrend:
    if type(days) is not int or not 1 <= days <= 28: raise McpSafeError(McpErrorCode.INVALID_ARGUMENT)
    if (start_date is None) != (end_date is None): raise McpSafeError(McpErrorCode.INVALID_ARGUMENT)
    end = end_date or local_today(); start = start_date or end-timedelta(days=days-1)
    if start > end or end > local_today() or (end-start).days >= 28: raise McpSafeError(McpErrorCode.INVALID_ARGUMENT)
    days = (end-start).days+1
    rows = list(db.scalars(select(DailyRecoveryCheckin).where(DailyRecoveryCheckin.user_id == user_id, DailyRecoveryCheckin.checkin_date >= start, DailyRecoveryCheckin.checkin_date <= end).order_by(DailyRecoveryCheckin.checkin_date)).all())
    sync = db.execute(select(ExternalAccountConnection.recovery_last_attempt_at,ExternalAccountConnection.recovery_last_successful_sync_at,
        ExternalAccountConnection.recovery_last_error_code).where(ExternalAccountConnection.user_id==user_id,
            ExternalAccountConnection.provider=='garmin',ExternalAccountConnection.status=='connected').order_by(ExternalAccountConnection.id.desc()).limit(1)).first()
    attempted,successful,error = sync if sync is not None else (None,None,None)
    pending_attempt = attempted is not None and (successful is None or attempted > successful)
    sync_status = 'FAILED' if pending_attempt and error else 'UNKNOWN' if pending_attempt else 'SYNCED' if successful else 'NEVER_SYNCED'
    records = []
    fields = ('hrv_value', 'sleep_duration_minutes', 'resting_heart_rate_bpm', 'sleep_score', 'body_battery_end', 'subjective_fatigue',
        'sleep_quality', 'average_stress', 'max_stress', 'muscle_soreness', 'leg_feeling', 'body_battery_start', 'body_battery_high', 'body_battery_low')
    for row in rows:
        values = {field:getattr(row, field, None) for field in fields}
        if values['hrv_value'] is not None: values['hrv_value'] = float(values['hrv_value'])
        def safe_source(value):
            source = str(_value(value) or 'unknown').lower()
            return source if source in {'garmin','manual','mixed','unknown'} else 'unknown'
        # Historical hrv_metric can be a measurement kind, not a unit.
        unit = 'MS' if (row.hrv_metric or '').strip().lower() in {'ms', 'millisecond', 'milliseconds'} else None
        status = str(getattr(row,'device_data_status',None) or 'UNKNOWN').upper()
        if status not in {'AVAILABLE','PARTIAL','FAILED','SYNC_FAILED','UNSUPPORTED','UNAVAILABLE','EMPTY','SYNCED','UNKNOWN'}: status = 'UNKNOWN'
        missing = [field for field,value in values.items() if value is None]
        records.append(McpRecoveryDay(date=row.checkin_date, source=safe_source(row.source), hrv_unit=unit, hrv_metric=row.hrv_metric,
            age_days=(local_today()-row.checkin_date).days, device_data_status=status,
            provider_updated_at=row.provider_updated_at.isoformat() if getattr(row,'provider_updated_at',None) else None,
            # Today's connection error cannot establish why an older day is missing.
            missing_reasons={field:('SYNC_FAILED' if status in {'FAILED','SYNC_FAILED'} else 'DEVICE_UNSUPPORTED' if status=='UNSUPPORTED' else 'NOT_RECORDED_OR_NOT_SYNCED')
                if field not in {'subjective_fatigue','muscle_soreness','leg_feeling','sleep_quality'} else 'NOT_RECORDED_OR_NOT_SYNCED' for field in missing},
            field_sources={field:('manual' if values[field] is not None else 'unknown') if field in {'subjective_fatigue','muscle_soreness','leg_feeling','sleep_quality'} else
                safe_source(row.hrv_source) if field=='hrv_value' else safe_source(row.sleep_source) if field=='sleep_duration_minutes' else
                safe_source(row.resting_heart_rate_source) if field=='resting_heart_rate_bpm' else safe_source(row.device_provider) for field in fields},
            synced_at=row.device_synced_at.isoformat() if row.device_synced_at else None,
            updated_at=row.updated_at.isoformat() if row.updated_at else None,
            missing_fields=missing, **values))
    dates = {row.date for row in records}
    missing_dates = [start+timedelta(days=n) for n in range(days) if start+timedelta(days=n) not in dates]
    return McpRecoveryTrend(data_status='EMPTY' if not records else 'PARTIAL' if missing_dates or any(row.missing_fields for row in records) else 'AVAILABLE', as_of=end, range_start=start, range_end=end,
        sync_status=sync_status,last_sync_attempt_at=attempted.isoformat() if attempted else None,last_successful_sync_at=successful.isoformat() if successful else None,
        daily_records=records, missing_dates=missing_dates, limitations=['Calendar-day recovery facts are not exact measurement timestamps.', 'No validated personal HRV baseline is stored in this projection; baseline is unavailable.', 'Subjective fatigue is distinct from session RPE; missing values are not zero.'])
