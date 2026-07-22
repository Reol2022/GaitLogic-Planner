from datetime import date

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.orm import Session

from planner_core.database.models import UserAccount
from server.api.deps import get_current_user, get_db
from server.schemas.runner_state import RunnerStateCurrentResponse
from server.schemas.runner_state_snapshot import (
    RunnerStateSnapshotCreateRequest,
    RunnerStateSnapshotCreateResult,
    RunnerStateSnapshotDetail,
    RunnerStateSnapshotListResponse,
    RunnerStateTimelineRange,
    RunnerStateTimelineResponse,
)
from server.services.runner_state_service import RunnerStateService
from server.services.runner_state_snapshot_service import RunnerStateSnapshotService

router = APIRouter(prefix="/runner-state", tags=["runner state"])


@router.get(
    "/current",
    response_model=RunnerStateCurrentResponse,
    summary="Get the current runner-state snapshot",
    description=(
        "Calculates a non-persistent runner-state snapshot and versioned heuristic "
        "inference for the authenticated user. Results support training review, "
        "do not constitute medical advice, and never modify the training plan."
    ),
)
def get_current_runner_state(
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> RunnerStateCurrentResponse:
    return RunnerStateCurrentResponse(
        snapshot=RunnerStateService(db).get_current(current_user)
    )


@router.post(
    "/snapshots",
    response_model=RunnerStateSnapshotCreateResult,
    summary="Save the current runner-state snapshot",
    description=(
        "Calculates and immutably stores the authenticated user's current state. "
        "The server fixes the trigger to MANUAL and deduplicates identical state. "
        "The result supports training review and does not constitute medical advice."
    ),
)
def create_runner_state_snapshot(
    request: RunnerStateSnapshotCreateRequest = Body(
        default=RunnerStateSnapshotCreateRequest()
    ),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> RunnerStateSnapshotCreateResult:
    del request
    return RunnerStateSnapshotService(db).save_current(current_user)


@router.get(
    "/snapshots",
    response_model=RunnerStateSnapshotListResponse,
    summary="List runner-state snapshots",
    description=(
        "Returns immutable snapshot summaries for the authenticated user. "
        "All distinct same-day snapshots are retained."
    ),
)
def list_runner_state_snapshots(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> RunnerStateSnapshotListResponse:
    return RunnerStateSnapshotService(db).list_snapshots(
        user_id=int(current_user.id),
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/snapshots/timeline",
    response_model=RunnerStateTimelineResponse,
    summary="Get the runner-state history timeline",
    description=(
        "Returns the authenticated user's last saved snapshot per cutoff date for "
        "a server-calculated Asia/Shanghai range. It does not recalculate state, "
        "write data, or return the complete snapshot payload."
    ),
)
def get_runner_state_timeline(
    timeline_range: RunnerStateTimelineRange = Query(
        default=RunnerStateTimelineRange.DAYS_28, alias="range"
    ),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> RunnerStateTimelineResponse:
    return RunnerStateSnapshotService(db).list_timeline_snapshots(
        user_id=int(current_user.id), timeline_range=timeline_range
    )


@router.get(
    "/snapshots/{snapshot_id}",
    response_model=RunnerStateSnapshotDetail,
    summary="Get a runner-state snapshot",
    description=(
        "Returns the exact state payload saved for the authenticated user. "
        "The historical state is never recalculated with newer rules."
    ),
)
def get_runner_state_snapshot(
    snapshot_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> RunnerStateSnapshotDetail:
    return RunnerStateSnapshotService(db).get_snapshot(
        user_id=int(current_user.id), snapshot_id=snapshot_id
    )
