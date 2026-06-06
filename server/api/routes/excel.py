from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from planner_core.database.models import UserAccount
from server.api.deps import get_current_user, get_db
from server.common.exceptions import BadRequestError
from server.schemas.excel_import import ExcelImportResult
from server.services.excel_import_service import import_excel_workbook
from server.services.excel_template_service import TEMPLATE_FILENAME, generate_excel_template_bytes

router = APIRouter(prefix="/excel", tags=["Excel 导入"])


@router.get("/template")
def download_excel_template(current_user: UserAccount = Depends(get_current_user)) -> Response:
    content = generate_excel_template_bytes()
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{TEMPLATE_FILENAME}"'},
    )


@router.post("/import", response_model=ExcelImportResult)
async def upload_excel_import(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> ExcelImportResult:
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise BadRequestError("只支持上传 .xlsx 文件。")
    content = await file.read()
    if not content:
        raise BadRequestError("上传文件不能为空。")
    return import_excel_workbook(db, content, file.filename, current_user.id)
