from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from planner_core.database.models import UserAccount
from server.api.deps import get_current_user, get_db
from server.schemas.runner_state import RunnerStateCurrentResponse
from server.services.runner_state_service import RunnerStateService

router = APIRouter(prefix="/runner-state", tags=["runner state"])


@router.get(
    "/current",
    response_model=RunnerStateCurrentResponse,
    summary="Get the current runner-state snapshot",
    description=(
        "Calculates a non-persistent 7-day and 28-day runner-state snapshot for "
        "the authenticated user. Inferred states remain UNKNOWN in v0.10.3-A."
    ),
)
def get_current_runner_state(
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> RunnerStateCurrentResponse:
    return RunnerStateCurrentResponse(
        snapshot=RunnerStateService(db).get_current(current_user)
    )
