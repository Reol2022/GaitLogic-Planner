from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from planner_core.database.models import UserAccount
from server.api.deps import get_current_user, get_db
from server.common.response import MessageResponse
from server.schemas.ai_plan import (
    AIPlanApplyResponse,
    AIPlanDraftDetail,
    AIPlanDraftRead,
    AIPlanGenerateRequest,
    AIPlanGenerateResponse,
    AIPlanQuotaRead,
)
from server.services import ai_plan_service
from server.services.ai_plan_export_service import SUPPORTED_EXPORT_FORMATS, export_ai_plan_draft

router = APIRouter(prefix="/ai-plan", tags=["AI plan"])


def to_generate_response(draft) -> AIPlanGenerateResponse:
    return AIPlanGenerateResponse(
        job_id=draft.job_id,
        draft_id=draft.id,
        title=draft.title,
        goal=draft.goal,
        summary=draft.summary,
        risk_notes=draft.risk_notes or [],
        workouts=draft.workouts,
    )


@router.post("/generate", response_model=AIPlanGenerateResponse, status_code=status.HTTP_201_CREATED)
def generate_ai_plan(
    payload: AIPlanGenerateRequest,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    draft = ai_plan_service.generate_ai_plan(db, current_user.id, payload)
    return to_generate_response(draft)


@router.get("/drafts", response_model=list[AIPlanDraftRead])
def list_ai_plan_drafts(
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return ai_plan_service.list_drafts(db, current_user.id)


@router.get("/drafts/{draft_id}", response_model=AIPlanDraftDetail)
def get_ai_plan_draft(
    draft_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return ai_plan_service.get_draft(db, draft_id, current_user.id)


@router.get("/drafts/{draft_id}/export")
def export_ai_plan_draft_file(
    draft_id: int,
    format: str = Query(default="xlsx", pattern="^[a-zA-Z0-9_]+$"),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    draft = ai_plan_service.get_draft(db, draft_id, current_user.id)
    export_file = export_ai_plan_draft(draft, format)
    return Response(
        content=export_file.content,
        media_type=export_file.media_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(export_file.filename)}",
            "X-Supported-Export-Formats": ",".join(sorted(SUPPORTED_EXPORT_FORMATS)),
        },
    )


@router.post("/drafts/{draft_id}/apply", response_model=AIPlanApplyResponse)
def apply_ai_plan_draft(
    draft_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    cycle = ai_plan_service.apply_draft_to_training_plan(db, draft_id, current_user.id)
    return AIPlanApplyResponse(message="AI 课表草稿已应用为正式训练计划", cycle_id=cycle.id)


@router.post("/drafts/{draft_id}/reject", response_model=MessageResponse)
def reject_ai_plan_draft(
    draft_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    ai_plan_service.reject_draft(db, draft_id, current_user.id)
    return MessageResponse(message="AI 课表草稿已拒绝")


@router.get("/quota", response_model=AIPlanQuotaRead)
def get_ai_plan_quota(
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return ai_plan_service.get_quota_status(db, current_user.id)
