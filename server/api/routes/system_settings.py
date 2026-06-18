from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from server.api.deps import get_db
from server.schemas.admin_system_settings import PublicSystemSettingsRead
from server.services import admin_system_settings_service

router = APIRouter(prefix="/system-settings", tags=["system settings"])


@router.get("", response_model=PublicSystemSettingsRead)
def get_public_system_settings(db: Session = Depends(get_db)):
    return admin_system_settings_service.get_public_system_settings(db)
