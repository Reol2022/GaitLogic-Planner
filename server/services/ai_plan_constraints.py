"""Deterministic output contract. Never repairs a conflicting training decision."""
from collections import defaultdict
from datetime import date, timedelta
from math import isfinite
import re

from planner_core.utils.excel_parse import normalize_workout_main_type
from server.common.exceptions import BadRequestError
from server.schemas.ai_plan import AIPlanGenerateRequest, WEEKDAYS
from server.services.ai_plan_context_service import _seconds


def validate_plan_constraints(output: dict, request: AIPlanGenerateRequest, disabled_types=()) -> None:
    def reject(message):
        raise BadRequestError('计划未通过约束检查：' + message, error_code='AI_PLAN_CONSTRAINT_VIOLATION')
    start = request.plan_start_date
    end = start + timedelta(days=7 * request.plan_weeks - 1)
    if not isinstance(output.get('title'), str) or not output['title'].strip() or len(output['title']) > 128:
        reject('计划标题缺失或过长。')
    risks = output.get('risk_notes')
    if not isinstance(risks,list) or not risks or len(risks)>30 or any(not isinstance(item,str) or not item.strip() for item in risks):
        reject('风险提示必须为非空字符串列表。')
    if output.get('start_date') != start.isoformat() or output.get('end_date') != end.isoformat():
        reject('模型改变了计划起止日期。')
    if (output.get('target_race_date') or None) != (request.target_race_date.isoformat() if request.target_race_date else None):
        reject('模型改变了比赛日期。')
    target = output.get('target_result')
    if (target or None) != (request.target_result or None) and not (_seconds(target) and _seconds(target) == _seconds(request.target_result)):
        reject('模型改变了目标成绩。')
    if output.get('target_distance') != request.target_distance.value:
        reject('模型改变了目标距离。')
    disabled = {normalize_workout_main_type(value) for value in [*request.excluded_workout_types, *disabled_types]}
    by_day = defaultdict(list)
    high_dates = set()
    for week_index, week in enumerate(output['weeks']):
        if not week['workouts']:
            reject('不能返回空训练周。')
        training_days = set()
        total_km = 0.0
        for workout in week['workouts']:
            try:
                day = date.fromisoformat(workout['date'])
            except (TypeError, ValueError, KeyError):
                reject('训练日期缺失或无效。')
            if not start <= day <= end or (day-start).days // 7 != week_index:
                reject('训练日期不属于请求的计划周。')
            kind = workout['main_type']
            km = workout.get('planned_distance_km')
            if isinstance(km, bool) or not isinstance(km, (int, float)) or not isfinite(km) or not 0 <= km <= 100:
                reject('训练距离必须是合理的有限非负数。')
            total_km += km
            if kind == 'Rest':
                if km != 0:
                    reject('休息日不能安排跑量。')
            else:
                training_days.add(day)
                if WEEKDAYS[day.weekday()] in request.fixed_rest_days:
                    reject('训练与固定休息日冲突。')
                if normalize_workout_main_type(kind) in disabled:
                    reject('包含用户禁用的训练类型。')
                if not request.can_double_run and re.search(r'双跑|早晚各|上午.*下午|两次跑', workout['planned_content']):
                    reject('用户不允许双跑。')
                if kind in {'T1','T2','I','R','Mixed'}:
                    high_dates.add(day)
                budget = request.daily_available_minutes.get(WEEKDAYS[day.weekday()])
                duration = workout.get('planned_duration_minutes')
                if budget is not None and (isinstance(duration, bool) or not isinstance(duration, (int,float)) or not isfinite(duration) or duration <= 0):
                    reject('设置每日时间上限时，模型必须提供真实的计划时长字段。')
                if duration is not None and (isinstance(duration,bool) or not isinstance(duration,(int,float)) or not isfinite(duration) or not 0 < duration <= 600):
                    reject('计划时长不合理。')
            by_day[day].append(workout)
        if len(training_days) > request.available_training_days_per_week:
            reject('超过每周可训练天数。')
        summary = week.get('planned_distance_km')
        if isinstance(summary,bool) or not isinstance(summary,(int,float)) or not isfinite(summary) or abs(total_km-summary) > .1:
            reject('周跑量与每日明细不一致。')
    for day, items in by_day.items():
        if len(items) > (2 if request.can_double_run else 1) or (len(items)>1 and any(item['main_type']=='Rest' for item in items)):
            reject('同日课程数量与双跑约束冲突。')
        budget = request.daily_available_minutes.get(WEEKDAYS[day.weekday()])
        if budget is not None and sum(item.get('planned_duration_minutes',0) or 0 for item in items if item['main_type']!='Rest') > budget:
            reject('超过每日可用训练时间。')
    if any(day + timedelta(days=1) in high_dates for day in high_dates):
        reject('跨周也不得连续两天安排高强度。')
