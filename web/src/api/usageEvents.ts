import request from "./request";

export type UsageEventName =
  | "onboarding_viewed"
  | "onboarding_ai_selected"
  | "onboarding_excel_selected"
  | "onboarding_manual_selected"
  | "ai_plan_generate_started"
  | "ai_plan_generate_succeeded"
  | "ai_plan_generate_failed"
  | "ai_plan_applied"
  | "today_viewed"
  | "workout_quick_checkin_opened"
  | "workout_log_saved"
  | "calendar_viewed"
  | "weekly_review_viewed"
  | "weekly_review_summary_viewed"
  | "weekly_review_generate_started"
  | "weekly_review_generate_succeeded"
  | "weekly_review_generate_failed"
  | "weekly_review_regenerated"
  | "adjustment_draft_viewed"
  | "adjustment_item_selected"
  | "adjustment_item_edited"
  | "adjustment_draft_applied"
  | "adjustment_draft_rejected";

export function trackUsageEvent(
  eventName: UsageEventName,
  metadata: Record<string, unknown> = {},
  pagePath = window.location.pathname,
) {
  return request
    .post<{ message: string }>(
      "/usage-events",
      {
        event_name: eventName,
        page_path: pagePath,
        metadata_json: metadata,
      },
      { skipErrorMessage: true },
    )
    .catch(() => undefined);
}
