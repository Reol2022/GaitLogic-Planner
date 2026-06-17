import request from "./request";

export interface OnboardingStatus {
  should_show_welcome: boolean;
  has_training_cycle: boolean;
  has_accepted_ai_plan: boolean;
  has_excel_import: boolean;
}

export function getOnboardingStatus() {
  return request.get<OnboardingStatus>("/onboarding/status", { skipErrorMessage: true });
}
