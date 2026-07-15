from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from planner_core.database.models import AIPlanDraft, PlanAdjustmentDraft, PlannedWorkout, TrainingCycle
from server.services.training_facts.common import base_facts, date_text, decimal_float, enum_value, is_high_intensity, workout_type_bucket


def _item_from_workout(workout: PlannedWorkout) -> dict[str, Any]:
    main_type = enum_value(workout.main_type_normalized) or workout.main_type_raw or "unknown"
    return {
        "id": workout.id,
        "date": date_text(workout.workout_date),
        "session_index": workout.session_index,
        "content": workout.planned_content,
        "distance_km": decimal_float(workout.planned_distance_km) or 0,
        "main_type": main_type,
        "bucket": workout_type_bucket(main_type),
        "high_intensity": is_high_intensity(main_type),
        "plan_version": workout.plan_version,
    }


def _item_from_ai_workout(workout: Any) -> dict[str, Any]:
    main_type = enum_value(getattr(workout, "main_type_normalized", None)) or getattr(workout, "main_type_raw", None) or "unknown"
    return {
        "id": getattr(workout, "id", None),
        "date": date_text(getattr(workout, "workout_date", None)),
        "session_index": 1,
        "content": getattr(workout, "planned_content", ""),
        "distance_km": decimal_float(getattr(workout, "planned_distance_km", None)) or 0,
        "main_type": main_type,
        "bucket": workout_type_bucket(main_type),
        "high_intensity": is_high_intensity(main_type),
        "plan_version": 1,
    }


def _analyze(items: list[dict[str, Any]]) -> dict[str, Any]:
    dated = [item for item in items if item.get("date")]
    dates = sorted(date.fromisoformat(item["date"]) for item in dated)
    if not dates:
        return {
            "has_plan": False,
            "total_days": 0,
            "total_distance_km": 0,
            "weekly_distance_km": {},
            "has_empty_week": True,
            "unknown_workout_type_count": len(items),
        }
    start, end = min(dates), max(dates)
    by_week: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in dated:
        week_start = date.fromisoformat(item["date"]) - timedelta(days=date.fromisoformat(item["date"]).weekday())
        by_week[week_start.isoformat()].append(item)
    weekly_distance = {
        week: round(sum(item["distance_km"] for item in rows), 2) for week, rows in sorted(by_week.items())
    }
    week_keys = sorted(weekly_distance)
    weekly_change_ratios = {}
    for previous, current in zip(week_keys, week_keys[1:]):
        prev_value = weekly_distance[previous]
        current_value = weekly_distance[current]
        weekly_change_ratios[current] = None if prev_value <= 0 else round((current_value - prev_value) / prev_value, 4)
    consecutive_training = _max_consecutive(dates)
    high_dates = sorted(date.fromisoformat(item["date"]) for item in dated if item["high_intensity"])
    key_dates = sorted(date.fromisoformat(item["date"]) for item in dated if item["bucket"] == "key")
    long_dates = sorted(date.fromisoformat(item["date"]) for item in dated if item["bucket"] == "long_run")
    rest_count_by_week = {week: sum(1 for item in rows if item["bucket"] == "rest") for week, rows in by_week.items()}
    return {
        "has_plan": True,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "total_days": (end - start).days + 1,
        "total_distance_km": round(sum(item["distance_km"] for item in dated), 2),
        "weekly_distance_km": weekly_distance,
        "weekly_distance_change_ratios": weekly_change_ratios,
        "weekly_training_days": {week: sum(1 for item in rows if item["bucket"] != "rest") for week, rows in by_week.items()},
        "weekly_rest_days": rest_count_by_week,
        "key_workout_count": sum(1 for item in dated if item["bucket"] == "key"),
        "high_intensity_count": sum(1 for item in dated if item["high_intensity"]),
        "long_run_count": sum(1 for item in dated if item["bucket"] == "long_run"),
        "max_consecutive_training_days": consecutive_training,
        "has_consecutive_high_intensity": _has_consecutive(high_dates),
        "has_consecutive_key_workouts": _has_consecutive(key_dates),
        "long_run_near_key_workout": _near_any(long_dates, key_dates, days=1),
        "longest_single_distance_km": max((item["distance_km"] for item in dated), default=0),
        "type_distribution": dict(sorted(_counts(item["bucket"] for item in dated).items())),
        "unknown_workout_type_count": sum(1 for item in dated if item["bucket"] == "unknown"),
        "has_empty_week": any(not rows for rows in by_week.values()) or not dated,
        "taper_volume_not_reduced": _taper_not_reduced(weekly_distance),
        "no_rest_day_weeks": sorted(week for week, count in rest_count_by_week.items() if count == 0),
        "max_weekly_distance_change_ratio": max((value for value in weekly_change_ratios.values() if value is not None), default=0),
        "has_missing_rest_day": any(count == 0 for count in rest_count_by_week.values()),
        "too_many_high_intensity_days": any(
            sum(1 for item in rows if item["high_intensity"]) >= 3 for rows in by_week.values()
        ),
        "weekly_volume_change_notice": any(
            value is not None and abs(value) >= 0.25 for value in weekly_change_ratios.values()
        ),
    }


def _counts(values: Iterable[str]) -> dict[str, int]:
    result: dict[str, int] = defaultdict(int)
    for value in values:
        result[value] += 1
    return result


def _has_consecutive(values: list[date]) -> bool:
    return any((current - previous).days <= 1 for previous, current in zip(values, values[1:]))


def _near_any(values: list[date], others: list[date], days: int) -> bool:
    return any(value != other and abs((value - other).days) <= days for value in values for other in others)


def _max_consecutive(values: list[date]) -> int:
    unique = sorted(set(values))
    if not unique:
        return 0
    best = current = 1
    for previous, item in zip(unique, unique[1:]):
        if (item - previous).days == 1:
            current += 1
        else:
            current = 1
        best = max(best, current)
    return best


def _taper_not_reduced(weekly_distance: dict[str, float]) -> bool:
    values = list(weekly_distance.values())
    return len(values) >= 2 and values[-1] >= values[-2]


def build_plan_facts_from_items(items: list[dict[str, Any]], *, source_type: str, source_id: int | None = None) -> dict[str, Any]:
    facts = base_facts()
    analysis = _analyze(items)
    facts["plan"] = {
        "source_type": source_type,
        "source_id": source_id,
        "items": items,
        "metrics": analysis,
    }
    facts["system"]["context_type"] = "plan_validation"
    return facts


def build_cycle_plan_facts(db: Session, user_id: int, cycle_id: int) -> dict[str, Any]:
    cycle = db.scalar(select(TrainingCycle).where(TrainingCycle.id == cycle_id, TrainingCycle.user_id == user_id))
    workouts = list(
        db.scalars(
            select(PlannedWorkout)
            .where(PlannedWorkout.user_id == user_id, PlannedWorkout.cycle_id == cycle_id)
            .order_by(PlannedWorkout.workout_date, PlannedWorkout.session_index, PlannedWorkout.id)
        )
    )
    facts = build_plan_facts_from_items([_item_from_workout(item) for item in workouts], source_type="cycle", source_id=cycle_id)
    facts["plan"]["cycle"] = {
        "id": cycle.id if cycle else cycle_id,
        "name": cycle.name if cycle else None,
        "status": enum_value(cycle.status) if cycle else None,
    }
    return facts


def build_ai_draft_plan_facts(db: Session, user_id: int, draft_id: int) -> dict[str, Any]:
    draft = db.scalar(select(AIPlanDraft).where(AIPlanDraft.id == draft_id, AIPlanDraft.user_id == user_id))
    if draft is None:
        return build_plan_facts_from_items([], source_type="ai_plan_draft", source_id=draft_id)
    facts = build_plan_facts_from_items([_item_from_ai_workout(item) for item in draft.workouts], source_type="ai_plan_draft", source_id=draft_id)
    facts["plan"]["draft"] = {"id": draft.id, "title": draft.title, "status": enum_value(draft.status)}
    return facts


def build_plan_import_facts(db: Session, user_id: int, import_id: int) -> dict[str, Any]:
    draft = db.scalar(select(PlanAdjustmentDraft).where(PlanAdjustmentDraft.id == import_id, PlanAdjustmentDraft.user_id == user_id))
    items: list[dict[str, Any]] = []
    if draft and draft.normalized_payload_json:
        for index, item in enumerate(draft.normalized_payload_json):
            main_type = item.get("workout_type") or "unknown"
            items.append(
                {
                    "id": index + 1,
                    "date": item.get("planned_date"),
                    "session_index": item.get("session_index") or 1,
                    "content": item.get("content") or "",
                    "distance_km": decimal_float(item.get("planned_distance_km")) or 0,
                    "main_type": main_type,
                    "bucket": workout_type_bucket(main_type),
                    "high_intensity": is_high_intensity(main_type),
                    "plan_version": 1,
                }
            )
    return build_plan_facts_from_items(items, source_type="plan_import_draft", source_id=import_id)
