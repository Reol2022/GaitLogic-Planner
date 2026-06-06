from pydantic import BaseModel


class ExcelImportErrorItem(BaseModel):
    sheet: str
    row: int
    message: str


class ExcelImportResult(BaseModel):
    status: str
    message: str
    total_count: int
    success_count: int
    failed_count: int
    errors: list[ExcelImportErrorItem]
