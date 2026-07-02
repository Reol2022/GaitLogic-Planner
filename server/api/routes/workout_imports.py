from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Header, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from planner_core.database.models import UserAccount
from server.api.deps import get_current_user, get_db
from server.schemas.workout_import import (
    WorkoutImportApplyResponse,
    WorkoutImportBatchRead,
    WorkoutImportCreateResponse,
    WorkoutImportItemPatch,
    WorkoutImportStructuredRequest,
)
from server.services import workout_import_service, workout_import_template_service
from server.services.feature_access_service import assert_workout_import_available

router = APIRouter(prefix="/workout-imports", tags=["workout-imports"])


@router.post("/structured", response_model=WorkoutImportCreateResponse)
def create_structured_workout_import(
    payload: WorkoutImportStructuredRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> WorkoutImportCreateResponse:
    assert_workout_import_available(db, current_user)
    return workout_import_service.create_structured_import(db, current_user.id, payload, idempotency_key)


@router.post("/file", response_model=WorkoutImportCreateResponse)
async def create_file_workout_import(
    file: UploadFile = File(...),
    merge_strategy: str = Form("create_missing_only"),
    timezone: str = Form("Asia/Shanghai"),
    client_request_id: str | None = Form(None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> WorkoutImportCreateResponse:
    assert_workout_import_available(db, current_user)
    content = await file.read()
    return await workout_import_service.create_file_import(
        db,
        current_user.id,
        filename=file.filename or "upload",
        content_type=file.content_type,
        content=content,
        merge_strategy=merge_strategy,
        timezone=timezone,
        client_request_id=client_request_id,
        idempotency_key=idempotency_key,
    )


@router.get("/template")
def download_workout_import_template(
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> Response:
    assert_workout_import_available(db, current_user)
    content = workout_import_template_service.generate_workout_import_template_bytes()
    return Response(
        content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="workout-import-template.xlsx"'},
    )


@router.get("", response_model=list[WorkoutImportBatchRead])
def list_workout_imports(
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> list[WorkoutImportBatchRead]:
    assert_workout_import_available(db, current_user)
    return workout_import_service.list_workout_imports(db, current_user.id)


@router.get("/{batch_id}", response_model=WorkoutImportBatchRead)
def get_workout_import(
    batch_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> WorkoutImportBatchRead:
    assert_workout_import_available(db, current_user)
    return workout_import_service.get_workout_import(db, current_user.id, batch_id)


@router.patch("/{batch_id}/items/{item_id}", response_model=WorkoutImportBatchRead)
def update_workout_import_item(
    batch_id: int,
    item_id: int,
    payload: WorkoutImportItemPatch,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> WorkoutImportBatchRead:
    assert_workout_import_available(db, current_user)
    return workout_import_service.update_workout_import_item(db, current_user.id, batch_id, item_id, payload)


@router.post("/{batch_id}/validate", response_model=WorkoutImportBatchRead)
def validate_workout_import(
    batch_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> WorkoutImportBatchRead:
    assert_workout_import_available(db, current_user)
    return workout_import_service.validate_workout_import(db, current_user.id, batch_id)


@router.post("/{batch_id}/apply", response_model=WorkoutImportApplyResponse)
def apply_workout_import(
    batch_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> WorkoutImportApplyResponse:
    assert_workout_import_available(db, current_user)
    return workout_import_service.apply_workout_import(db, current_user.id, batch_id)


@router.post("/{batch_id}/cancel", response_model=WorkoutImportBatchRead)
def cancel_workout_import(
    batch_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> WorkoutImportBatchRead:
    assert_workout_import_available(db, current_user)
    return workout_import_service.cancel_workout_import(db, current_user.id, batch_id)
