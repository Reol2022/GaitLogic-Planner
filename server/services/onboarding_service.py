from sqlalchemy import select
from sqlalchemy.orm import Session

from planner_core.database.models import AIPlanDraft, ExcelImportJob, TrainingCycle
from planner_core.enums import AIPlanDraftStatus, ExcelImportStatus
from server.schemas.onboarding import OnboardingStatusRead


def get_onboarding_status(db: Session, user_id: int) -> OnboardingStatusRead:
    has_training_cycle = db.scalar(
        select(TrainingCycle.id).where(TrainingCycle.user_id == user_id).limit(1)
    ) is not None
    has_accepted_ai_plan = db.scalar(
        select(AIPlanDraft.id)
        .where(AIPlanDraft.user_id == user_id, AIPlanDraft.status == AIPlanDraftStatus.accepted)
        .limit(1)
    ) is not None
    has_excel_import = db.scalar(
        select(ExcelImportJob.id)
        .where(
            ExcelImportJob.user_id == user_id,
            ExcelImportJob.status.in_([ExcelImportStatus.success, ExcelImportStatus.partial_success]),
        )
        .limit(1)
    ) is not None
    return OnboardingStatusRead(
        should_show_welcome=not (has_training_cycle or has_accepted_ai_plan or has_excel_import),
        has_training_cycle=has_training_cycle,
        has_accepted_ai_plan=has_accepted_ai_plan,
        has_excel_import=has_excel_import,
    )
