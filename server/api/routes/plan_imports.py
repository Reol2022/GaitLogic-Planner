from datetime import date

from fastapi import APIRouter, Depends, File, Form, Header, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from planner_core.database.models import UserAccount
from server.api.deps import get_current_user, get_db
from server.schemas.plan_import import (
    PlanImportApplyResponse,
    PlanImportCreateResponse,
    PlanImportDraftRead,
    PlanImportItemUpdate,
    PlanImportStructuredRequest,
)
from server.services import plan_import_service, plan_import_template_service

router = APIRouter(prefix="/plan-imports", tags=["plan imports"])


@router.post("/structured", response_model=PlanImportCreateResponse)
def create_structured_plan_import(
    payload: PlanImportStructuredRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> PlanImportCreateResponse:
    return plan_import_service.create_structured_import(db, current_user.id, payload, idempotency_key)


@router.post("/file", response_model=PlanImportCreateResponse)
async def create_file_plan_import(
    file: UploadFile = File(...),
    target_cycle_id: int | None = Form(default=None),
    target_block_id: int | None = Form(default=None),
    client_request_id: str = Form(...),
    anchor_strategy: str = Form(default="after_last_completed"),
    effective_date: date | None = Form(default=None),
    merge_strategy: str = Form(default="replace_uncompleted_in_range"),
    timezone: str = Form(default="Asia/Shanghai"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> PlanImportCreateResponse:
    content = await file.read()
    return await plan_import_service.create_file_import(
        db,
        current_user.id,
        filename=file.filename or "plan-import",
        content_type=file.content_type,
        content=content,
        target_cycle_id=target_cycle_id,
        target_block_id=target_block_id,
        client_request_id=client_request_id,
        anchor_strategy=anchor_strategy,
        effective_date=effective_date,
        merge_strategy=merge_strategy,
        timezone=timezone,
        idempotency_key=idempotency_key,
    )


@router.get("/template")
def download_plan_import_template(current_user: UserAccount = Depends(get_current_user)) -> Response:
    content = plan_import_template_service.generate_plan_import_template_bytes()
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="plan-import-template.xlsx"'},
    )


@router.get("/{import_id}", response_model=PlanImportDraftRead)
def get_plan_import(
    import_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> PlanImportDraftRead:
    return plan_import_service.get_plan_import(db, current_user.id, import_id)


@router.patch("/{import_id}/items/{item_id}", response_model=PlanImportDraftRead)
def update_plan_import_item(
    import_id: int,
    item_id: int,
    payload: PlanImportItemUpdate,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> PlanImportDraftRead:
    return plan_import_service.update_plan_import_item(db, current_user.id, import_id, item_id, payload)


@router.post("/{import_id}/validate", response_model=PlanImportDraftRead)
def validate_plan_import(
    import_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> PlanImportDraftRead:
    return plan_import_service.validate_plan_import(db, current_user.id, import_id)


@router.post("/{import_id}/apply", response_model=PlanImportApplyResponse)
def apply_plan_import(
    import_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> PlanImportApplyResponse:
    return plan_import_service.apply_plan_import(db, current_user.id, import_id)


@router.post("/{import_id}/cancel", response_model=PlanImportDraftRead)
def cancel_plan_import(
    import_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> PlanImportDraftRead:
    return plan_import_service.cancel_plan_import(db, current_user.id, import_id)
