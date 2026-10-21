from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, selectinload

from planner_core.database.models import PlannedWorkout, TrainingCycle, WorkoutLog
from planner_core.enums import (
    PlannedWorkoutLifecycleStatus,
    TrainingCycleStatus,
    WorkoutStatusNormalized,
)
from server.common.exceptions import BadRequestError, NotFoundError
from server.schemas.training_cycle import (
    TrainingCycleActivateRequest,
    TrainingCycleActivationPreview,
    TrainingCycleCompleteRequest,
    TrainingCycleCreate,
    TrainingCycleLifecycleRead,
    TrainingCycleLifecycleState,
)

COMPLETED_LOG_STATUSES = {
    WorkoutStatusNormalized.completed_high,
    WorkoutStatusNormalized.completed_normal,
    WorkoutStatusNormalized.completed_adjusted,
}


def create_draft(db: Session, payload: TrainingCycleCreate, user_id: int) -> TrainingCycle:
    cycle = TrainingCycle(**payload.model_dump(), user_id=user_id)
    _set_cycle_status(cycle, TrainingCycleStatus.draft)
    db.add(cycle)
    db.commit()
    db.refresh(cycle)
    return cycle


def reconcile_expired_cycles(
    db: Session,
    user_id: int,
    *,
    as_of_date: date | None = None,
) -> int:
    """Explicitly persist deterministic completion for expired active cycles.

    This is a write-side maintenance operation. Read paths must use the effective
    lifecycle helpers below and must never call this function implicitly.
    """
    effective_date = as_of_date or date.today()
    try:
        with db.no_autoflush:
            expired = list(
                db.scalars(
                    select(TrainingCycle)
                    .where(
                        TrainingCycle.user_id == user_id,
                        TrainingCycle.status == TrainingCycleStatus.active,
                        TrainingCycle.end_date.is_not(None),
                        TrainingCycle.end_date < effective_date,
                    )
                    .with_for_update()
                )
            )
        if not expired:
            return 0

        now = datetime.utcnow()
        for cycle in expired:
            _set_cycle_status(cycle, TrainingCycleStatus.completed)
            cycle.actual_end_date = cycle.actual_end_date or cycle.end_date
            cycle.completed_at = cycle.completed_at or now
            _mark_future_workouts_superseded(db, cycle.id, cycle.end_date + timedelta(days=1))
        db.commit()
        return len(expired)
    except Exception:
        db.rollback()
        raise


def _effective_start(cycle: TrainingCycle) -> date | None:
    return cycle.actual_start_date or cycle.start_date


def _effective_end(cycle: TrainingCycle) -> date | None:
    return cycle.actual_end_date or cycle.end_date


def _is_effectively_active(cycle: TrainingCycle, as_of_date: date) -> bool:
    if cycle.status != TrainingCycleStatus.active:
        return False
    start_date = _effective_start(cycle)
    end_date = _effective_end(cycle)
    return (start_date is None or start_date <= as_of_date) and (
        end_date is None or end_date >= as_of_date
    )


def _is_effectively_completed(cycle: TrainingCycle, as_of_date: date) -> bool:
    if cycle.status == TrainingCycleStatus.completed:
        return True
    end_date = _effective_end(cycle)
    return cycle.status == TrainingCycleStatus.active and end_date is not None and end_date < as_of_date


def to_effective_cycle_read(cycle: TrainingCycle, *, as_of_date: date | None = None):
    """Project persisted cycle data into a non-mutating user-facing read model."""
    from server.schemas.training_cycle import TrainingCycleRead

    effective_date = as_of_date or date.today()
    result = TrainingCycleRead.model_validate(cycle)
    if _is_effectively_completed(cycle, effective_date):
        return result.model_copy(
            update={
                "status": TrainingCycleStatus.completed,
                "actual_end_date": result.actual_end_date or result.end_date,
            }
        )
    return result


def get_active_cycle(
    db: Session,
    user_id: int,
    *,
    as_of_date: date | None = None,
) -> TrainingCycle | None:
    effective_date = as_of_date or date.today()
    with db.no_autoflush:
        candidates = list(
            db.scalars(
                select(TrainingCycle).where(
                    TrainingCycle.user_id == user_id,
                    TrainingCycle.status == TrainingCycleStatus.active,
                )
            )
        )
    return next((cycle for cycle in candidates if _is_effectively_active(cycle, effective_date)), None)


def get_active_cycle_with_blocks(
    db: Session, user_id: int, *, as_of_date: date | None = None
) -> TrainingCycle | None:
    """Load the one active cycle and its bounded structural children read-only."""
    effective_date = as_of_date or date.today()
    with db.no_autoflush:
        candidates = list(
            db.scalars(
                select(TrainingCycle)
                .options(selectinload(TrainingCycle.blocks))
                .where(
                    TrainingCycle.user_id == user_id,
                    TrainingCycle.status == TrainingCycleStatus.active,
                )
            )
        )
    return next((cycle for cycle in candidates if _is_effectively_active(cycle, effective_date)), None)


def get_lifecycle_snapshot(
    db: Session,
    user_id: int,
    *,
    as_of_date: date | None = None,
) -> TrainingCycleLifecycleRead:
    """Return a stable UI/API lifecycle view without changing persisted enum values."""
    effective_date = as_of_date or date.today()
    active = get_active_cycle(db, user_id, as_of_date=effective_date)
    with db.no_autoflush:
        cycles = list(
            db.scalars(
                select(TrainingCycle)
                .where(TrainingCycle.user_id == user_id)
                .order_by(TrainingCycle.id)
            )
        )
    completed_candidates = [cycle for cycle in cycles if _is_effectively_completed(cycle, effective_date)]
    completed_candidates.sort(
        key=lambda cycle: (_effective_end(cycle) or date.min, cycle.completed_at or datetime.min, cycle.id),
        reverse=True,
    )
    latest_completed = completed_candidates[0] if completed_candidates else None
    upcoming_candidates = [
        cycle for cycle in cycles
        if cycle.status in {TrainingCycleStatus.draft, TrainingCycleStatus.active}
        and _effective_start(cycle) is not None
        and _effective_start(cycle) > effective_date
    ]
    upcoming_candidates.sort(key=lambda cycle: (_effective_start(cycle), cycle.id))
    next_cycle = upcoming_candidates[0] if upcoming_candidates else None
    if active is not None:
        days_until_end = (active.end_date - effective_date).days if active.end_date else None
        state = (
            TrainingCycleLifecycleState.ENDING_SOON
            if days_until_end is not None and 0 <= days_until_end <= 7
            else TrainingCycleLifecycleState.ACTIVE
        )
        return TrainingCycleLifecycleRead(
            state=state,
            active_cycle=to_effective_cycle_read(active, as_of_date=effective_date),
            latest_completed_cycle=(to_effective_cycle_read(latest_completed, as_of_date=effective_date) if latest_completed else None),
            next_cycle=(to_effective_cycle_read(next_cycle, as_of_date=effective_date) if next_cycle else None),
            days_until_end=days_until_end,
        )
    if latest_completed is not None:
        return TrainingCycleLifecycleRead(
            state=TrainingCycleLifecycleState.COMPLETED,
            latest_completed_cycle=to_effective_cycle_read(latest_completed, as_of_date=effective_date),
            next_cycle=(to_effective_cycle_read(next_cycle, as_of_date=effective_date) if next_cycle else None),
            transition="awaiting_next_cycle" if next_cycle is None else None,
        )
    if next_cycle is not None:
        return TrainingCycleLifecycleRead(
            state=TrainingCycleLifecycleState.UPCOMING,
            next_cycle=to_effective_cycle_read(next_cycle, as_of_date=effective_date),
        )
    archived_cycle = next((cycle for cycle in reversed(cycles) if cycle.status == TrainingCycleStatus.archived), None)
    if archived_cycle is not None:
        return TrainingCycleLifecycleRead(state=TrainingCycleLifecycleState.CANCELLED)
    return TrainingCycleLifecycleRead(state=TrainingCycleLifecycleState.DRAFT)


def get_cycle(db: Session, cycle_id: int, user_id: int) -> TrainingCycle:
    cycle = db.scalar(
        select(TrainingCycle).where(
            TrainingCycle.id == cycle_id,
            TrainingCycle.user_id == user_id,
        )
    )
    if cycle is None:
        raise NotFoundError("Training cycle not found.")
    return cycle


def activation_preview(
    db: Session,
    user_id: int,
    cycle_id: int,
    effective_start_date: date,
) -> TrainingCycleActivationPreview:
    cycle = get_cycle(db, cycle_id, user_id)
    current = get_active_cycle(db, user_id)
    end_date = effective_start_date - timedelta(days=1)
    future_count = _future_uncompleted_plan_count(db, current.id, effective_start_date) if current else 0
    return TrainingCycleActivationPreview(
        current_cycle_id=current.id if current else None,
        current_cycle_name=current.name if current else None,
        new_cycle_id=cycle.id,
        new_cycle_name=cycle.name,
        effective_start_date=effective_start_date,
        current_cycle_actual_end_date=end_date if current else None,
        future_uncompleted_plan_count=future_count,
        completed_logs_preserved=True,
    )


def activate_cycle(
    db: Session,
    user_id: int,
    cycle_id: int,
    payload: TrainingCycleActivateRequest,
) -> TrainingCycle:
    cycles = list(
        db.scalars(
            select(TrainingCycle)
            .where(TrainingCycle.user_id == user_id)
            .order_by(TrainingCycle.id)
            .with_for_update()
        )
    )
    target = next((cycle for cycle in cycles if cycle.id == cycle_id), None)
    if target is None:
        raise NotFoundError("Training cycle not found.")
    if target.status == TrainingCycleStatus.active:
        if target.actual_start_date is None:
            target.actual_start_date = payload.effective_start_date
        target.activated_at = target.activated_at or datetime.utcnow()
        db.commit()
        db.refresh(target)
        return target
    if target.status != TrainingCycleStatus.draft:
        raise BadRequestError("Only draft cycles can be activated.")

    current = next((cycle for cycle in cycles if cycle.status == TrainingCycleStatus.active), None)
    now = datetime.utcnow()
    if current is not None:
        if not payload.complete_current_cycle:
            raise BadRequestError("Activating a new cycle requires completing the current active cycle first.")
        end_date = payload.effective_start_date - timedelta(days=1)
        _set_cycle_status(current, TrainingCycleStatus.completed)
        current.actual_end_date = end_date
        current.completed_at = now
        current.superseded_by_cycle_id = target.id
        _mark_future_workouts_superseded(db, current.id, payload.effective_start_date)

    _set_cycle_status(target, TrainingCycleStatus.active)
    target.actual_start_date = payload.effective_start_date
    target.activated_at = now
    target.actual_end_date = None
    target.completed_at = None
    db.commit()
    db.refresh(target)
    return target


def complete_cycle(
    db: Session,
    user_id: int,
    cycle_id: int,
    payload: TrainingCycleCompleteRequest,
) -> TrainingCycle:
    cycle = get_cycle(db, cycle_id, user_id)
    if cycle.status not in {TrainingCycleStatus.active, TrainingCycleStatus.draft}:
        return cycle
    end_date = payload.actual_end_date or date.today()
    _set_cycle_status(cycle, TrainingCycleStatus.completed)
    cycle.actual_end_date = end_date
    cycle.completed_at = cycle.completed_at or datetime.utcnow()
    _mark_future_workouts_superseded(db, cycle.id, end_date + timedelta(days=1))
    db.commit()
    db.refresh(cycle)
    return cycle


def archive_cycle(db: Session, user_id: int, cycle_id: int) -> TrainingCycle:
    cycle = get_cycle(db, cycle_id, user_id)
    if cycle.status == TrainingCycleStatus.active:
        raise BadRequestError("Active cycle must be completed before archive.")
    _set_cycle_status(cycle, TrainingCycleStatus.archived)
    db.commit()
    db.refresh(cycle)
    return cycle


def resolve_cycle_for_date(db: Session, user_id: int, activity_date: date) -> tuple[TrainingCycle | None, str]:
    candidates = list(
        db.scalars(
            select(TrainingCycle).where(
                TrainingCycle.user_id == user_id,
                TrainingCycle.status.in_([TrainingCycleStatus.active, TrainingCycleStatus.completed]),
                or_(
                    _date_in_actual_range(activity_date),
                    _date_in_planned_range(activity_date),
                ),
            )
        )
    )
    if len(candidates) == 1:
        return candidates[0], "assigned"
    if len(candidates) > 1:
        return None, "needs_review"
    return None, "unassigned"


def _date_in_actual_range(activity_date: date):
    return and_(
        TrainingCycle.actual_start_date.is_not(None),
        TrainingCycle.actual_start_date <= activity_date,
        or_(TrainingCycle.actual_end_date.is_(None), TrainingCycle.actual_end_date >= activity_date),
    )


def _date_in_planned_range(activity_date: date):
    return and_(
        TrainingCycle.actual_start_date.is_(None),
        TrainingCycle.start_date.is_not(None),
        TrainingCycle.start_date <= activity_date,
        or_(TrainingCycle.end_date.is_(None), TrainingCycle.end_date >= activity_date),
    )


def _set_cycle_status(cycle: TrainingCycle, status: TrainingCycleStatus) -> None:
    cycle.status = status
    cycle.active_user_id = cycle.user_id if status == TrainingCycleStatus.active else None


def _future_uncompleted_plan_count(db: Session, cycle_id: int, from_date: date) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(PlannedWorkout)
            .outerjoin(WorkoutLog, WorkoutLog.planned_workout_id == PlannedWorkout.id)
            .where(
                PlannedWorkout.cycle_id == cycle_id,
                PlannedWorkout.workout_date >= from_date,
                PlannedWorkout.lifecycle_status == PlannedWorkoutLifecycleStatus.planned,
                or_(WorkoutLog.id.is_(None), WorkoutLog.status_normalized.notin_(COMPLETED_LOG_STATUSES)),
            )
        )
        or 0
    )


def _mark_future_workouts_superseded(db: Session, cycle_id: int, from_date: date) -> None:
    workouts = list(
        db.scalars(
            select(PlannedWorkout)
            .outerjoin(WorkoutLog, WorkoutLog.planned_workout_id == PlannedWorkout.id)
            .where(
                PlannedWorkout.cycle_id == cycle_id,
                PlannedWorkout.workout_date >= from_date,
                PlannedWorkout.lifecycle_status == PlannedWorkoutLifecycleStatus.planned,
                or_(WorkoutLog.id.is_(None), WorkoutLog.status_normalized.notin_(COMPLETED_LOG_STATUSES)),
            )
        )
    )
    for workout in workouts:
        workout.lifecycle_status = PlannedWorkoutLifecycleStatus.superseded
        workout.is_locked = True
        workout.lock_reason = "superseded_by_new_cycle"
