from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from planner_core.database.models import UserAccount
from server.api.deps import get_current_user, get_db
from server.common.response import MessageResponse
from server.schemas.coach_agent import CoachQueryRequest, CoachQueryResponse
from server.schemas.coach_conversation import (
    CoachConversationCreate,
    CoachConversationMessageCreate,
    CoachConversationMessageResult,
    CoachConversationPage,
    CoachConversationRead,
    CoachConversationUpdate,
    CoachMessagePage,
)
from server.observability.factory import get_configured_tracer
from server.services.coach_agent_query_service import CoachAgentQueryService
from server.services.coach_conversation_service import CoachConversationService

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
    service = CoachAgentQueryService(
        db,
        tracer=get_configured_tracer(),
    )
    result = service.reject_direct_public_intent(
        user_id=int(current_user.id), payload=payload
    ) or service.query(user_id=int(current_user.id), payload=payload)
    if result.status == "REJECTED":
        response.status_code = status.HTTP_403_FORBIDDEN
    elif result.status == "UNAVAILABLE":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return result


def _conversation_service(db: Session) -> CoachConversationService:
    return CoachConversationService(db, tracer=get_configured_tracer())


@router.post("/conversations", response_model=CoachConversationRead, status_code=status.HTTP_201_CREATED)
def create_conversation(
    payload: CoachConversationCreate,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> CoachConversationRead:
    return _conversation_service(db).create(user_id=int(current_user.id), payload=payload)


@router.get("/conversations", response_model=CoachConversationPage)
def list_conversations(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    conversation_status: str | None = Query(default=None, alias="status", pattern="^(active|archived)$"),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> CoachConversationPage:
    return _conversation_service(db).list(
        user_id=int(current_user.id), page=page, page_size=page_size, status=conversation_status
    )


@router.get("/conversations/{conversation_id}", response_model=CoachConversationRead)
def get_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> CoachConversationRead:
    return _conversation_service(db).get(user_id=int(current_user.id), conversation_id=conversation_id)


@router.get("/conversations/{conversation_id}/messages", response_model=CoachMessagePage)
def list_conversation_messages(
    conversation_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> CoachMessagePage:
    return _conversation_service(db).list_messages(
        user_id=int(current_user.id), conversation_id=conversation_id, page=page, page_size=page_size
    )


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=CoachConversationMessageResult,
)
def submit_conversation_message(
    conversation_id: str,
    payload: CoachConversationMessageCreate,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> CoachConversationMessageResult:
    return _conversation_service(db).send_message(
        user_id=int(current_user.id), conversation_id=conversation_id, payload=payload
    )


@router.patch("/conversations/{conversation_id}", response_model=CoachConversationRead)
def update_conversation(
    conversation_id: str,
    payload: CoachConversationUpdate,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> CoachConversationRead:
    return _conversation_service(db).update(
        user_id=int(current_user.id), conversation_id=conversation_id, payload=payload
    )


@router.delete("/conversations/{conversation_id}", response_model=MessageResponse)
def delete_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> MessageResponse:
    _conversation_service(db).delete(user_id=int(current_user.id), conversation_id=conversation_id)
    return MessageResponse(message="Coach conversation deleted.")
