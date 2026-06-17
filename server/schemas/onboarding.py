from pydantic import BaseModel


class OnboardingStatusRead(BaseModel):
    should_show_welcome: bool
    has_training_cycle: bool
    has_accepted_ai_plan: bool
    has_excel_import: bool
