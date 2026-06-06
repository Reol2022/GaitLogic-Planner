from collections import Counter
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from planner_core.database.models import PlannedWorkout, TrainingBlock
from planner_core.enums import WorkoutStatusNormalized
from server.common.exceptions import NotFoundError
from server.schemas.dashboard import BlockStats, DashboardSummary


ZERO = Decimal("0")


def decimal_or_zero(value: object) -> Decimal:
    if value is None:
        return ZERO
    return Decimal(str(value))


def completion_rate(planned: Decimal, actual: Decimal) -> Decimal:
    if planned == ZERO:
        return ZERO
    return (actual / planned * Decimal("100")).quantize(Decimal("0.01"))


def average_decimal(values: list[object]) -> Decimal | None:
    usable = [decimal_or_zero(value) for value in values if value is not None]
    if not usable:
        return None
    return (sum(usable, ZERO) / Decimal(len(usable))).quantize(Decimal("0.01"))


def get_dashboard_summary(
    db: Session,
    user_id: int,
    cycle_id: int | None = None,
) -> DashboardSummary:
    stmt = (
        select(PlannedWorkout)
        .options(selectinload(PlannedWorkout.workout_log))
        .where(PlannedWorkout.user_id == user_id)
    )
    if cycle_id is not None:
        stmt = stmt.where(PlannedWorkout.cycle_id == cycle_id)
    workouts = list(db.scalars(stmt))

    planned_distance = sum(
        (decimal_or_zero(workout.planned_distance_km) for workout in workouts),
        ZERO,
    )
    logs = [workout.workout_log for workout in workouts if workout.workout_log is not None]
    actual_distance = sum((decimal_or_zero(log.actual_distance_km) for log in logs), ZERO)
    completed_statuses = {
        WorkoutStatusNormalized.completed_high,
        WorkoutStatusNormalized.completed_normal,
        WorkoutStatusNormalized.completed_adjusted,
    }
    completed_count = sum(1 for log in logs if log.status_normalized in completed_statuses)
    missed_count = sum(1 for log in logs if log.status_normalized == WorkoutStatusNormalized.missed)
    pain_levels = [log.pain_level for log in logs if log.pain_level is not None]
    distribution = Counter(str(workout.main_type_normalized.value) for workout in workouts)

    return DashboardSummary(
        planned_distance_km=planned_distance,
        actual_distance_km=actual_distance,
        completion_rate=completion_rate(planned_distance, actual_distance),
        workout_count=len(workouts),
        completed_count=completed_count,
        missed_count=missed_count,
        avg_rpe=average_decimal([log.rpe for log in logs]),
        max_pain_level=max(pain_levels) if pain_levels else None,
        main_type_distribution=dict(distribution),
    )


def get_block_stats(db: Session, block_id: int, user_id: int) -> BlockStats:
    block = db.scalar(
        select(TrainingBlock).where(
            TrainingBlock.id == block_id,
            TrainingBlock.user_id == user_id,
        )
    )
    if block is None:
        raise NotFoundError("Training block not found.")
    workouts = list(
        db.scalars(
            select(PlannedWorkout)
            .options(selectinload(PlannedWorkout.workout_log))
            .where(PlannedWorkout.block_id == block_id, PlannedWorkout.user_id == user_id)
        )
    )
    logs = [workout.workout_log for workout in workouts if workout.workout_log is not None]
    planned_distance = sum(
        (decimal_or_zero(workout.planned_distance_km) for workout in workouts),
        ZERO,
    )
    actual_distance = sum((decimal_or_zero(log.actual_distance_km) for log in logs), ZERO)

    return BlockStats(
        planned_distance_km=planned_distance,
        actual_distance_km=actual_distance,
        completion_rate=completion_rate(planned_distance, actual_distance),
        i_effective_km=sum((decimal_or_zero(log.i_effective_km) for log in logs), ZERO),
        t1_effective_km=sum((decimal_or_zero(log.t1_effective_km) for log in logs), ZERO),
        t2_effective_km=sum((decimal_or_zero(log.t2_effective_km) for log in logs), ZERO),
        m_effective_km=sum((decimal_or_zero(log.m_effective_km) for log in logs), ZERO),
        r_effective_km=sum((decimal_or_zero(log.r_effective_km) for log in logs), ZERO),
        avg_rpe=average_decimal([log.rpe for log in logs]),
        avg_weight_kg=average_decimal([log.weight_kg for log in logs]),
        max_pain_level=max(
            [log.pain_level for log in logs if log.pain_level is not None],
            default=None,
        ),
    )
