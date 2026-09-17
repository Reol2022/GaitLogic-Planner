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
    """Persist the deterministic completion of active cycles whose planned end passed.

    This intentionally depends only on the configured cycle end date, never on workout
    completion rate.  It is safe to invoke from read paths and is also suitable for a
    future scheduled reconciliation job.
    """
    effective_date = as_of_date or date.today()
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
        # Workouts after the configured cycle boundary cannot remain executable.
        _mark_future_workouts_superseded(db, cycle.id, cycle.end_date + timedelta(days=1))
    db.commit()
    return len(expired)


def get_active_cycle(
    db: Session,
    user_id: int,
    *,
    as_of_date: date | None = None,
) -> TrainingCycle | None:
    reconcile_expired_cycles(db, user_id, as_of_date=as_of_date)
    return db.scalar(
        select(TrainingCycle).where(
            TrainingCycle.user_id == user_id,
            TrainingCycle.status == TrainingCycleStatus.active,
        )
    )


def get_active_cycle_with_blocks(db: Session, user_id: int) -> TrainingCycle | None:
    """Load the one active cycle and its bounded structural children read-only."""
    reconcile_expired_cycles(db, user_id)
    return db.scalar(
        select(TrainingCycle)
        .options(selectinload(TrainingCycle.blocks))
        .where(
            TrainingCycle.user_id == user_id,
            TrainingCycle.status == TrainingCycleStatus.active,
        )
    )


def get_lifecycle_snapshot(
    db: Session,
    user_id: int,
    *,
    as_of_date: date | None = None,
) -> TrainingCycleLifecycleRead:
    """Return a stable UI/API lifecycle view without changing persisted enum values."""
    effective_date = as_of_date or date.today()
    active = get_active_cycle(db, user_id, as_of_date=effective_date)
    latest_completed = db.scalar(
        select(TrainingCycle)
        .where(
            TrainingCycle.user_id == user_id,
            TrainingCycle.status == TrainingCycleStatus.completed,
        )
        .order_by(
            TrainingCycle.actual_end_date.desc(),
            TrainingCycle.end_date.desc(),
            TrainingCycle.completed_at.desc(),
            TrainingCycle.id.desc(),
        )
    )
    next_cycle = db.scalar(
        select(TrainingCycle)
        .where(
            TrainingCycle.user_id == user_id,
            TrainingCycle.status == TrainingCycleStatus.draft,
            TrainingCycle.start_date.is_not(None),
            TrainingCycle.start_date > effective_date,
        )
        .order_by(TrainingCycle.start_date, TrainingCycle.id)
    )
    if active is not None:
        days_until_end = (active.end_date - effective_date).days if active.end_date else None
        state = (
            TrainingCycleLifecycleState.ENDING_SOON
            if days_until_end is not None and 0 <= days_until_end <= 7
            else TrainingCycleLifecycleState.ACTIVE
        )
        return TrainingCycleLifecycleRead(
            state=state,
            active_cycle=active,
            latest_completed_cycle=latest_completed,
            next_cycle=next_cycle,
            days_until_end=days_until_end,
        )
    if latest_completed is not None:
        return TrainingCycleLifecycleRead(
            state=TrainingCycleLifecycleState.COMPLETED,
            latest_completed_cycle=latest_completed,
            next_cycle=next_cycle,
            transition="awaiting_next_cycle" if next_cycle is None else None,
        )
    if next_cycle is not None:
        return TrainingCycleLifecycleRead(
            state=TrainingCycleLifecycleState.UPCOMING,
            next_cycle=next_cycle,
        )
    archived_cycle = db.scalar(
        select(TrainingCycle)
        .where(
            TrainingCycle.user_id == user_id,
            TrainingCycle.status == TrainingCycleStatus.archived,
        )
        .order_by(TrainingCycle.updated_at.desc(), TrainingCycle.id.desc())
    )
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
