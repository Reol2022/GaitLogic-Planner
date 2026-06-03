from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from server.api.deps import get_db
from server.schemas.dashboard import BlockStats, DashboardSummary
from server.services import dashboard_service

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardSummary)
def get_dashboard(
    cycle_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return dashboard_service.get_dashboard_summary(db, cycle_id)


@router.get("/stats/blocks/{block_id}", response_model=BlockStats)
def get_block_stats(block_id: int, db: Session = Depends(get_db)):
    return dashboard_service.get_block_stats(db, block_id)

