from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from planner_core.database.models import (
    PlannedWorkout,
    RunnerStateSnapshotRecord,
    TrainingBlock,
    TrainingCycle,
    WorkoutLog,
)
from planner_core.enums import PlannedWorkoutLifecycleStatus
from planner_core.utils.excel_parse import normalize_workout_main_type
from planner_core.weekly_review.aggregation import build_weekly_facts
from planner_core.weekly_review.schemas import (
    PlannedSessionFact,
    RunnerStateSampleFact,
    WeeklyFacts,
    WeeklyFactsRequest,
    WeeklyPeriod,
    WorkoutSessionFact,
)
from server.common.exceptions import NotFoundError


def _number(value: Decimal | int | float | None) -> float | None:
    return None if value is None else float(value)


def _enum(value: object | None, default: str = "unknown") -> str:
    if value is None:
        return default
    return str(getattr(value, "value", value))


class WeeklyFactsService:
    """Read-only adapter from existing ORM facts into the deterministic domain."""

    def build_weekly_facts(
        self,
        db: Session,
        request: WeeklyFactsRequest,
        *,
        as_of_date: date | None = None,
    ) -> WeeklyFacts:
        cycle = self._cycle(db, request)
        plans = self._plans(db, request)
        logs = self._logs(db, request)
        samples = self._runner_state_samples(db, request)
        phase = self._phase(db, request, cycle.id if cycle else None)
        effective_today = as_of_date or datetime.now(
            ZoneInfo(request.timezone)
        ).date()
        return build_weekly_facts(
            period=WeeklyPeriod(
                week_start=request.week_start,
                week_end=request.week_end,
                timezone=request.timezone,
                cycle_id=cycle.id if cycle else None,
                cycle_name=cycle.name if cycle else None,
                training_phase=phase,
            ),
            plans=[
                PlannedSessionFact(
                    plan_id=item.id,
                    session_date=item.workout_date,
                    main_type=_enum(item.main_type_normalized),
                    distance_km=_number(item.planned_distance_km),
                    duration_minutes=None,
                    is_cancelled=(
                        item.lifecycle_status
                        != PlannedWorkoutLifecycleStatus.planned
                    ),
                )
                for item in plans
                if item.workout_date is not None
            ],
            logs=[
                WorkoutSessionFact(
                    log_id=item.id,
                    activity_date=(
                        item.activity_date
                        or (
                            item.planned_workout.workout_date
                            if item.planned_workout
                            else None
                        )
                    ),
                    planned_workout_id=item.planned_workout_id,
                    main_type=(
                        _enum(item.planned_workout.main_type_normalized)
                        if item.planned_workout
                        else normalize_workout_main_type(item.workout_type).value
                    ),
                    distance_km=_number(item.actual_distance_km),
                    duration_minutes=(
                        round(
                            (
                                item.moving_time_seconds
                                or item.actual_duration_seconds
                            )
                            / 60,
                            2,
                        )
                        if (
                            item.moving_time_seconds is not None
                            or item.actual_duration_seconds is not None
                        )
                        else None
                    ),
                    status=_enum(item.status_normalized),
                    sport_type=item.sport_type,
                    activity_fingerprint=item.activity_fingerprint,
                )
                for item in logs
                if (
                    item.activity_date is not None
                    or (
                        item.planned_workout is not None
                        and item.planned_workout.workout_date is not None
                    )
                )
            ],
            runner_state_samples=samples,
            as_of_date=effective_today,
        )

    @staticmethod
    def _cycle(
        db: Session, request: WeeklyFactsRequest
    ) -> TrainingCycle | None:
        if request.cycle_id is not None:
            cycle = db.scalar(
                select(TrainingCycle).where(
                    TrainingCycle.id == request.cycle_id,
                    TrainingCycle.user_id == request.user_id,
                )
            )
            if cycle is None:
                raise NotFoundError("Training cycle not found.")
            return cycle
        return db.scalar(
            select(TrainingCycle)
            .where(
                TrainingCycle.user_id == request.user_id,
                or_(
                    TrainingCycle.start_date.is_(None),
                    TrainingCycle.start_date <= request.week_end,
                ),
                or_(
                    TrainingCycle.end_date.is_(None),
                    TrainingCycle.end_date >= request.week_start,
                ),
            )
            .order_by(TrainingCycle.start_date.desc(), TrainingCycle.id.desc())
        )

    @staticmethod
    def _plans(
        db: Session, request: WeeklyFactsRequest
    ) -> list[PlannedWorkout]:
        filters = [
            PlannedWorkout.user_id == request.user_id,
            PlannedWorkout.workout_date >= request.week_start,
            PlannedWorkout.workout_date <= request.week_end,
        ]
        if request.cycle_id is not None:
            filters.append(PlannedWorkout.cycle_id == request.cycle_id)
        return list(
            db.scalars(
                select(PlannedWorkout)
                .where(*filters)
                .order_by(
                    PlannedWorkout.workout_date,
                    PlannedWorkout.session_index,
                    PlannedWorkout.id,
                )
            )
        )

    @staticmethod
    def _logs(db: Session, request: WeeklyFactsRequest) -> list[WorkoutLog]:
        filters = [
            WorkoutLog.user_id == request.user_id,
            or_(
                WorkoutLog.activity_date.between(
                    request.week_start,
                    request.week_end,
                ),
                PlannedWorkout.workout_date.between(
                    request.week_start,
                    request.week_end,
                ),
            ),
        ]
        if request.cycle_id is not None:
            filters.append(
                or_(
                    WorkoutLog.cycle_id == request.cycle_id,
                    WorkoutLog.cycle_id.is_(None),
                )
            )
        return list(
            db.scalars(
                select(WorkoutLog)
                .outerjoin(
                    PlannedWorkout,
                    WorkoutLog.planned_workout_id == PlannedWorkout.id,
                )
                .options(selectinload(WorkoutLog.planned_workout))
                .where(*filters)
                .order_by(
                    WorkoutLog.activity_date,
                    WorkoutLog.session_index,
                    WorkoutLog.id,
                )
            ).unique()
        )

    @staticmethod
    def _runner_state_samples(
        db: Session, request: WeeklyFactsRequest
    ) -> list[RunnerStateSampleFact]:
        rows = list(
            db.scalars(
                select(RunnerStateSnapshotRecord)
                .where(
                    RunnerStateSnapshotRecord.user_id == request.user_id,
                    RunnerStateSnapshotRecord.data_cutoff_date
                    >= request.week_start,
                    RunnerStateSnapshotRecord.data_cutoff_date <= request.week_end,
                )
                .order_by(
                    RunnerStateSnapshotRecord.data_cutoff_date,
                    RunnerStateSnapshotRecord.created_at,
                )
            )
        )
        return [
            RunnerStateSampleFact(
                sample_date=item.data_cutoff_date,
                fatigue_state=item.fatigue_state or "UNKNOWN",
                load_trend=item.volume_trend or "UNKNOWN",
                recovery_state="UNKNOWN",
                risk_flag_count=item.risk_flag_count,
            )
            for item in rows
        ]

    @staticmethod
    def _phase(
        db: Session,
        request: WeeklyFactsRequest,
        cycle_id: int | None,
    ) -> str | None:
        filters = [
            TrainingBlock.user_id == request.user_id,
            or_(
                TrainingBlock.start_date.is_(None),
                TrainingBlock.start_date <= request.week_end,
            ),
            or_(
                TrainingBlock.end_date.is_(None),
                TrainingBlock.end_date >= request.week_start,
            ),
        ]
        if cycle_id is not None:
            filters.append(TrainingBlock.cycle_id == cycle_id)
        block = db.scalar(
            select(TrainingBlock)
            .where(*filters)
            .order_by(TrainingBlock.sort_order, TrainingBlock.id)
        )
        return block.phase_name if block else None
