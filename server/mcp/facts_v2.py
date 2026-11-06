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
from sqlalchemy import select
from sqlalchemy.orm import Session

from planner_core.database.models import DailyRecoveryCheckin, ExternalActivity, ExternalActivityLap, PlannedWorkout, WorkoutLog, WorkoutLogExternalActivity
from server.mcp.errors import McpErrorCode, McpSafeError
from server.mcp.schemas import McpContractModel, McpRecentTrainingItem, McpRecentTraining, McpRecentTrainingSummary, McpTrainingFactIssue, McpDataQuality, _McpToolResult
from server.services.auth_service import signing_key
from server.services.training_load_service import _query_logs, _safe_source
from server.services.weekly_review_stats_service import COMPLETED_STATUSES, local_today
from server.domain.review_thresholds import KEY_WORKOUT_TYPES


def _value(value):
    return getattr(value, 'value', value)


def training_item(log: WorkoutLog, plan: PlannedWorkout | None) -> McpRecentTrainingItem:
    planned = str(_value(plan.main_type_normalized)) if plan else None
    actual = log.workout_type or None
    # A recorded type of rest is not a valid classification of a nonzero run.
    if actual == 'rest' and log.actual_distance_km is not None and log.actual_distance_km > 0:
        actual = None
    return McpRecentTrainingItem(
        record_ref=f'workout_log:{log.id}', date=log.activity_date or plan.workout_date,
        training_type=actual or 'unknown', planned_training_type=planned,
        actual_training_type=actual, classification_basis='ACTUAL_LOG' if actual else 'UNKNOWN',
        planned_or_unplanned='UNPLANNED' if log.is_unplanned or plan is None else 'PLANNED',
        completion_status=str(_value(log.status_normalized)),
        distance_km=float(log.actual_distance_km) if log.actual_distance_km is not None else None,
        duration_seconds=log.actual_duration_seconds, average_pace_seconds_per_km=log.avg_pace_seconds_per_km,
        average_heart_rate=log.avg_heart_rate, rpe=log.rpe if log.rpe is not None and 0 <= log.rpe <= 10 else None,
        source=_safe_source(log.source_type), origin_source='UNKNOWN',
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


class McpTrainingDetail(McpContractModel):
    record: McpRecentTrainingItem
    segments_available: bool
    segments_complete: bool
    segments: list[McpSegment] = Field(default_factory=list, max_length=100)
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


def read_training_detail(db: Session, user_id: int, record_ref: str) -> McpTrainingDetail:
    import re
    if not re.fullmatch(r'workout_log:[1-9][0-9]{0,17}', record_ref): raise McpSafeError(McpErrorCode.INVALID_ARGUMENT)
    log = db.scalar(select(WorkoutLog).where(WorkoutLog.id == int(record_ref.split(':')[1]), WorkoutLog.user_id == user_id))
    if log is None: raise McpSafeError(McpErrorCode.RESOURCE_NOT_FOUND)
    plan = db.scalar(select(PlannedWorkout).where(PlannedWorkout.id == log.planned_workout_id, PlannedWorkout.user_id == user_id)) if log.planned_workout_id else None
    if log.activity_date is None and (plan is None or plan.workout_date is None): raise McpSafeError(McpErrorCode.DATA_UNAVAILABLE)
    activity_ids = select(WorkoutLogExternalActivity.external_activity_id).where(WorkoutLogExternalActivity.user_id == user_id, WorkoutLogExternalActivity.workout_log_id == log.id)
    # Validate both link and activity ownership; never expose an unrelated lap.
    ids = list(db.scalars(select(ExternalActivity.id).where(ExternalActivity.user_id == user_id, ExternalActivity.id.in_(activity_ids))).all())
    if not ids and log.external_activity_id:
        ids = list(db.scalars(select(ExternalActivity.id).where(ExternalActivity.user_id == user_id, ExternalActivity.external_activity_id == log.external_activity_id)).all())
    laps = list(db.scalars(select(ExternalActivityLap).where(ExternalActivityLap.external_activity_id.in_(ids)).order_by(ExternalActivityLap.external_activity_id, ExternalActivityLap.lap_index).limit(101)).all()) if ids else []
    return McpTrainingDetail(record=training_item(log, plan), segments_available=bool(laps), segments_complete=len(laps) <= 100,
        segments=[McpSegment(index=index+1, role=lap.segment_role, distance_m=float(lap.distance_m) if lap.distance_m is not None else None,
            duration_seconds=lap.duration_seconds, average_pace_seconds_per_km=lap.average_pace_seconds_per_km, quality=lap.data_quality) for index, lap in enumerate(laps[:100])],
        limitations=['Only persisted laps are returned; roles and intensity are not inferred.', 'Heart-rate reliability is unknown; no device-quality diagnosis is inferred.'] + ([] if laps else ['No structured segments are stored.']))


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


class McpRecoveryTrend(McpContractModel):
    data_status: Literal['PARTIAL', 'AVAILABLE', 'EMPTY']
    as_of: date
    range_start: date
    timezone: Literal['Asia/Shanghai'] = 'Asia/Shanghai'
    daily_records: list[McpRecoveryDay] = Field(max_length=28)
    missing_dates: list[date] = Field(max_length=28)
    baseline: None = None
    limitations: list[str]


class McpRecoveryTrendResult(_FactResult):
    data: McpRecoveryTrend | None = None


def read_recovery(db: Session, user_id: int, days: int = 7) -> McpRecoveryTrend:
    if type(days) is not int or not 1 <= days <= 28: raise McpSafeError(McpErrorCode.INVALID_ARGUMENT)
    end = local_today(); start = end-timedelta(days=days-1)
    rows = list(db.scalars(select(DailyRecoveryCheckin).where(DailyRecoveryCheckin.user_id == user_id, DailyRecoveryCheckin.checkin_date >= start, DailyRecoveryCheckin.checkin_date <= end).order_by(DailyRecoveryCheckin.checkin_date)).all())
    records = []
    fields = ('hrv_value', 'sleep_duration_minutes', 'resting_heart_rate_bpm', 'sleep_score', 'body_battery_end', 'subjective_fatigue')
    for row in rows:
        values = {field:getattr(row, field) for field in fields}
        if values['hrv_value'] is not None: values['hrv_value'] = float(values['hrv_value'])
        def safe_source(value):
            source = str(_value(value) or 'unknown').lower()
            return source if source in {'garmin','manual','mixed','unknown'} else 'unknown'
        # Historical hrv_metric can be a measurement kind, not a unit.
        unit = 'MS' if (row.hrv_metric or '').strip().lower() in {'ms', 'millisecond', 'milliseconds'} else None
        records.append(McpRecoveryDay(date=row.checkin_date, source=safe_source(row.source), hrv_unit=unit, hrv_metric=row.hrv_metric,
            age_days=(end-row.checkin_date).days,
            field_sources={'hrv_value':safe_source(row.hrv_source), 'sleep_duration_minutes':safe_source(row.sleep_source), 'resting_heart_rate_bpm':safe_source(row.resting_heart_rate_source), 'sleep_score':safe_source(row.device_provider), 'body_battery_end':safe_source(row.device_provider), 'subjective_fatigue':'manual' if row.subjective_fatigue is not None else 'unknown'},
            synced_at=row.device_synced_at.isoformat() if row.device_synced_at else None,
            updated_at=row.updated_at.isoformat() if row.updated_at else None,
            missing_fields=[field for field, value in values.items() if value is None], **values))
    dates = {row.date for row in records}
    missing_dates = [start+timedelta(days=n) for n in range(days) if start+timedelta(days=n) not in dates]
    return McpRecoveryTrend(data_status='EMPTY' if not records else 'PARTIAL' if missing_dates or any(row.missing_fields for row in records) else 'AVAILABLE', as_of=end, range_start=start,
        daily_records=records, missing_dates=missing_dates, limitations=['Calendar-day recovery facts are not exact measurement timestamps.', 'No validated personal HRV baseline is stored in this projection; baseline is unavailable.', 'Subjective fatigue is distinct from session RPE; missing values are not zero.'])
