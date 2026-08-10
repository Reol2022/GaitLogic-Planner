from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from planner_core.database.models import UserAccount
from server.api.deps import get_current_user, get_db
from server.schemas.coach_agent import CoachQueryRequest, CoachQueryResponse
from server.observability.factory import get_configured_tracer
from server.services.coach_agent_query_service import CoachAgentQueryService

router = APIRouter(prefix="/coach", tags=["coach agent"])


@router.post(
    "/query",
    response_model=CoachQueryResponse,
    summary="Query the read-only GaitLogic Coach",
    description=(
        "Uses deterministic training facts and rules as authority. The Coach does not "
        "modify plans and does not provide medical diagnosis."
    ),
)
def query_coach(
    payload: CoachQueryRequest,
    response: Response,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> CoachQueryResponse:
    result = CoachAgentQueryService(
        db,
        tracer=get_configured_tracer(),
    ).query(user_id=int(current_user.id), payload=payload)
    if result.status == "REJECTED":
        response.status_code = status.HTTP_403_FORBIDDEN
    elif result.status == "UNAVAILABLE":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return result
