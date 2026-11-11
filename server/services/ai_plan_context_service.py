"""Private Plan Context: canonical local records only, never a Garmin network request."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import date, timedelta
from math import isfinite

from sqlalchemy import select
from sqlalchemy.orm import Session

from planner_core.database.models import AIPlanCoachPreference, ExternalSyncJob, PaceProfile
from server.schemas.ai_plan import AIPlanGenerateRequest, PlanContextRead, PlanContextIssue, WEEKDAYS
from server.services import training_cycle_lifecycle_service, training_load_service
from server.services.ai_coach_preference_service import preference_to_prompt_dict
from server.services.ai_plan_calendar import plan_calendar
from server.services.runner_state_service import RunnerStateService
from server.services.weekly_review_stats_service import APP_TIMEZONE, COMPLETED_STATUSES, local_today


def aggregate_plan_rows(rows, end: date, *, unresolved: int = 0) -> dict:
    """Aggregate complete 56-day rows, then bound examples, never the reverse."""
    start = end - timedelta(days=55)
    seen = set()
    sessions = []
    duplicates = 0
    updates = []
    for log, planned in rows:
        day = log.activity_date or (planned.workout_date if planned else None)
        if log.status_normalized not in COMPLETED_STATUSES or day is None or not start <= day <= end:
            continue
        key = log.activity_fingerprint or log.external_activity_id or f'log:{log.id}'
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        km = float(log.actual_distance_km) if log.actual_distance_km is not None else None
        if km is not None and (not isfinite(km) or km < 0):
            km = None
        if log.updated_at:
            updates.append(log.updated_at.isoformat())
        # A planned label is not proof of actual execution intensity.
        sessions.append({'record_ref': f'workout_log:{log.id}', 'date': day.isoformat(), 'distance_km': km,
                         'duration_seconds': log.actual_duration_seconds,
                         'source': training_load_service._safe_source(log.source_type),
                         'training_type': log.workout_type or None,
                         'classification_basis': 'ACTUAL_LOG' if log.workout_type else 'UNKNOWN'})
    sessions.sort(key=lambda item: (item['date'], item['record_ref']))
    weeks = []
    for index in range(8):
        week_end = end - timedelta(days=7 * index)
        week_start = week_end - timedelta(days=6)
        items = [item for item in sessions if week_start.isoformat() <= item['date'] <= week_end.isoformat()]
        known = bool(items) and all(item['distance_km'] is not None for item in items)
        weeks.append({'start_date': week_start.isoformat(), 'end_date': week_end.isoformat(), 'record_count': len(items),
                      'training_days': len({item['date'] for item in items}),
                      'recorded_distance_km': round(sum(item['distance_km'] for item in items), 2) if known else None})
    recent = [item for item in sessions if item['date'] >= (end - timedelta(days=27)).isoformat()]
    def average(window):
        return round(sum(week['recorded_distance_km'] for week in window) / 4, 2) if all(week['recorded_distance_km'] is not None for week in window) else None
    missing = sum(item['distance_km'] is None for item in sessions)
    distances = [item for item in sessions if item['distance_km'] is not None]
    return {'provenance': 'SERVER_DERIVED_FROM_GAITLOGIC_RECORDS', 'window_start': start.isoformat(), 'window_end': end.isoformat(),
            'weeks': weeks, 'record_count': len(sessions), 'recent_28d_record_count': len(recent),
            'recent_4w_avg_recorded_km': average(weeks[:4]), 'previous_4w_avg_recorded_km': average(weeks[4:]),
            'training_days_per_week_28d': round(len({item['date'] for item in recent}) / 4, 2) if all(week['record_count'] for week in weeks[:4]) else None,
            'longest_recorded_activity': max(distances, key=lambda item: item['distance_km']) if distances else None,
            'recent_key_training': [item for item in reversed(sessions) if str(item['training_type']).lower() in {'t1','t2','i','r','tempo','threshold','interval','interval_speed'}][:8],
            'source_counts': dict(Counter(item['source'] for item in sessions)),
            'last_training_date': sessions[-1]['date'] if sessions else None, 'last_record_updated_at': max(updates) if updates else None,
            'distance_missing_count': missing, 'duplicate_candidate_count': duplicates, 'unresolved_activity_count': unresolved,
            'complete_for_recorded_data': bool(sessions) and missing == 0 and duplicates == 0 and unresolved == 0,
            'sync_coverage_verified': False,
            'limitations': ['仅统计已完成日志；待关联设备活动不直接混入。最长距离为单条活动，不代表热身/主课/放松合并后的整堂训练。',
                            '没有记录的周标记未知，不当作零跑量；记录完整不等于Garmin同步完整。']}


def _seconds(value: str | None) -> int | None:
    try:
        parts = [int(part) for part in value.split(':')]
        if not 2 <= len(parts) <= 3 or any(item < 0 for item in parts) or any(item >= 60 for item in parts[1:]):
            return None
        return sum(item * 60 ** index for index, item in enumerate(reversed(parts))) or None
    except (AttributeError, ValueError):
        return None


def assess_feasibility(payload: AIPlanGenerateRequest, facts: dict) -> list[PlanContextIssue]:
    issues = []
    def issue(code, message, severity='warning'):
        issues.append(PlanContextIssue(code=code, message=message, severity=severity))
    available = [day for day in WEEKDAYS if day not in payload.fixed_rest_days and payload.daily_available_minutes.get(day, 1) > 0]
    if len(available) < payload.available_training_days_per_week:
        issue('TRAINING_DAYS_CONFLICT', '可训练天数与固定休息日或每日时间冲突，请修改约束。', 'error')
    calendar = plan_calendar(payload.plan_start_date, payload.plan_weeks, payload.target_race_date)
    if calendar.error:
        issue('RACE_BEFORE_PLAN' if payload.target_race_date < payload.plan_start_date else 'PLAN_WEEKS_EXCEED_RACE', calendar.error, 'error')
    if payload.target_race_date and 0 <= (payload.target_race_date - payload.plan_start_date).days < 28:
        issue('SHORT_PREPARATION', '距离比赛不足4周，适合有限准备与调整，不宜假设短期可大幅提升能力。')
    if payload.target_race_date and payload.target_race_date > calendar.end:
        issue('RACE_OUTSIDE_PLAN', '比赛在本计划结束后，本草稿不覆盖完整备赛周期。')
    if payload.long_run_preferred_day in payload.fixed_rest_days:
        issue('LONG_RUN_REST_CONFLICT', '长距离偏好日与固定休息日冲突：休息日优先，长距离需改日。')
    if len(payload.daily_available_minutes) == 7 and sum(payload.daily_available_minutes[day] for day in available) < 120:
        issue('LIMITED_WEEKLY_TIME', '每周可用训练时间不足120分钟，请确认目标与实际时间安排；这不是成绩保证或医学阈值。')
    basis = facts.get('training', {})
    if not basis.get('record_count'):
        issue('TRAINING_DATA_MISSING', '没有可用的近期已完成训练，使用用户填写的基础并保留不确定性。')
    elif not basis.get('complete_for_recorded_data') or basis.get('recent_4w_avg_recorded_km') is None:
        issue('TRAINING_DATA_PARTIAL', '训练统计存在未知周、距离缺失、重复候选或待关联活动，不视为完整训练基础。')
    recent = basis.get('recent_4w_avg_recorded_km')
    previous = basis.get('previous_4w_avg_recorded_km')
    if recent is not None and previous and abs(recent - previous) / previous > .35:
        issue('VOLUME_CHANGED', '近期与此前4周已记录跑量差异较大，应确认减量、漏同步或其他变化原因，不沿用历史高跑量。')
    if recent is not None and abs(payload.recent_4w_avg_mileage_km - recent) > max(10, recent * .25):
        issue('MANUAL_VOLUME_DIFFERS', '表单跑量与已记录统计不同：保留双方来源，不用用户自述覆盖已记录事实。')
    if facts.get('recovery', {}).get('freshness') in {None, 'UNAVAILABLE', 'STALE'}:
        issue('RECOVERY_LIMITED', '恢复数据缺失或过期，只作有限参考；缺少单项指标不阻止所有计划讨论。')
    if facts.get('last_sync_status') in {'failed','partially_succeeded','cancelled'}:
        issue('SYNC_INCOMPLETE', '最近同步未完整成功，已记录训练可能不是设备中的全部训练。')
    pb = _seconds(payload.recent_pb_result)
    target = _seconds(payload.target_result)
    if pb and target and payload.recent_pb_distance == payload.target_distance and target < pb * .9:
        issue('CHALLENGING_TARGET', '同距离目标较自述成绩提升超过10%，需确认专项能力与准备时间；不因此自动拒绝生成。')
    if not pb:
        issue('PERFORMANCE_UNKNOWN', '缺少可比较的参考成绩，不能给出确定的目标预测。')
    return issues


def build_plan_context(db: Session, user_id: int, payload: AIPlanGenerateRequest | None = None) -> PlanContextRead:
    end = local_today()
    facts = {}
    if payload is None or payload.use_training_context:
        recent = training_load_service.get_recent_training_read(db, user_id=user_id, days=56, limit=0, as_of_date=end)
        rows = training_load_service._query_logs(db, user_id, end - timedelta(days=55), end)
        facts['training'] = aggregate_plan_rows(rows, end, unresolved=recent.unresolved_activity_count)
        snapshot = RunnerStateService(db).get_current_for_user_id(user_id)
        facts['recovery'] = {'provenance':'GAITLOGIC_RECOVERY_RECORD', **snapshot.recovery.model_dump(mode='json')}
        facts['runner_state'] = {'provenance': 'SERVER_DERIVED', 'data_quality': snapshot.data_quality.data_quality_level.value,
                                 'risk_flags': [flag.model_dump(mode='json') for flag in snapshot.risk_flags]}
        lifecycle = training_cycle_lifecycle_service.get_lifecycle_snapshot(db, user_id, as_of_date=end)
        cycle = lifecycle.active_cycle or lifecycle.latest_completed_cycle
        facts['cycle'] = {'provenance': 'GAITLOGIC_RECORD', 'current': lifecycle.active_cycle is not None,
                          'id': cycle.id, 'start_date': cycle.start_date, 'end_date': cycle.end_date, 'status': cycle.status.value} if cycle else None
        profiles = list(db.scalars(select(PaceProfile).where(PaceProfile.user_id == user_id).order_by(PaceProfile.updated_at.desc()).limit(5)))
        facts['performances'] = [{'provenance': 'USER_REPORTED_SAVED_PROFILE', 'distance': item.race_distance.value,
                                  'result_seconds': item.race_result_seconds, 'updated_at': item.updated_at} for item in profiles]
        sync = db.scalar(select(ExternalSyncJob).where(ExternalSyncJob.user_id == user_id, ExternalSyncJob.provider == 'garmin', ExternalSyncJob.status.in_(['succeeded','partially_succeeded'])).order_by(ExternalSyncJob.finished_at.desc()).limit(1))
        facts['last_sync_at'] = sync.finished_at if sync else None
        latest = db.scalar(select(ExternalSyncJob).where(ExternalSyncJob.user_id == user_id, ExternalSyncJob.provider == 'garmin').order_by(ExternalSyncJob.created_at.desc(), ExternalSyncJob.id.desc()).limit(1))
        facts['last_sync_status'] = latest.status if latest else None
    preference = db.scalar(select(AIPlanCoachPreference).where(AIPlanCoachPreference.user_id == user_id))
    context = PlanContextRead(as_of_date=end, timezone=APP_TIMEZONE.key, runner_facts=facts, soft_preferences=preference_to_prompt_dict(preference))
    basis = facts.get('training', {})
    if basis.get('complete_for_recorded_data'):
        if basis['weeks'][0]['recorded_distance_km'] is not None:
            context.suggestions['current_weekly_mileage_km'] = basis['weeks'][0]['recorded_distance_km']
        if basis.get('recent_4w_avg_recorded_km') is not None:
            context.suggestions['recent_4w_avg_mileage_km'] = basis['recent_4w_avg_recorded_km']
    if payload:
        data = payload.model_dump(mode='json')
        context.hard_constraints = {key: data[key] for key in ['target_distance','target_result','target_race_date','plan_start_date','plan_weeks','available_training_days_per_week','fixed_rest_days','daily_available_minutes','can_double_run','excluded_workout_types']}
        calendar = plan_calendar(payload.plan_start_date, payload.plan_weeks, payload.target_race_date)
        context.hard_constraints.update(plan_end_date=calendar.end.isoformat(), week_date_ranges=calendar.week_ranges)
        context.hard_constraints['excluded_workout_types'] = sorted(set(payload.excluded_workout_types + (context.soft_preferences.get('disabled_workout_types') or [])))
        context.user_reported = {key: data[key] for key in ['runner_level','recent_pb_distance','recent_pb_result','current_weekly_mileage_km','recent_4w_avg_mileage_km','injury_notes']}
        pb, target = _seconds(payload.recent_pb_result), _seconds(payload.target_result)
        if pb and target and payload.recent_pb_distance == payload.target_distance:
            distance_km = {'1500m':1.5,'3000m':3,'5000m':5,'10000m':10,'half_marathon':21.0975,'marathon':42.195}[payload.target_distance.value]
            context.user_reported['goal_gap'] = {'provenance':'SERVER_DERIVED_FROM_USER_REPORT', 'pb_seconds':pb,
                'target_seconds':target,'improvement_seconds':pb-target,'improvement_percent':round((pb-target)/pb*100,2),
                'pace_difference_seconds_per_km':round((pb-target)/distance_km,2), 'not_a_success_probability':True}
        context.soft_preferences.update({'training_preferences': payload.training_preferences, 'long_run_preferred_day': payload.long_run_preferred_day, 'intensity_style': payload.intensity_style.value})
        context.feasibility = assess_feasibility(payload, facts)
    # Stable facts retain caching: no per-request wall-clock timestamp or random ID.
    context.fingerprint = hashlib.sha256(json.dumps(context.model_dump(mode='json', exclude={'fingerprint'}), ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return context
