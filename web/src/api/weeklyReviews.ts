import request from "./request";
import type {
  AdjustmentItem,
  WeeklyReviewDetail,
  WeeklyReviewReport,
  WeeklyReviewSummary,
  WorkoutMainTypeNormalized,
} from "@/types/models";

export function getWeeklyReviewSummary(cycleId: number, blockId: number) {
  return request.get<WeeklyReviewSummary>("/weekly-reviews/summary", {
    params: { cycle_id: cycleId, block_id: blockId },
  });
}

export function generateWeeklyReview(payload: {
  cycle_id: number;
  source_block_id: number;
  target_block_id?: number | null;
  force_regenerate?: boolean;
}) {
  return request.post<WeeklyReviewDetail>("/weekly-reviews/generate", payload);
}

export function listWeeklyReviews(cycleId?: number | null) {
  return request.get<{ items: WeeklyReviewReport[]; total: number; page: number; page_size: number }>(
    "/weekly-reviews",
    { params: { cycle_id: cycleId || undefined, page: 1, page_size: 50 } },
  );
}

export function getWeeklyReview(id: number) {
  return request.get<WeeklyReviewDetail>(`/weekly-reviews/${id}`);
}

export function updateAdjustmentItem(
  draftId: number,
  itemId: number,
  payload: Partial<Pick<AdjustmentItem, "is_selected" | "suggested_content" | "suggested_distance_km" | "suggested_target_pace_text">> & {
    suggested_main_type?: WorkoutMainTypeNormalized | null;
  },
) {
  return request.patch<WeeklyReviewDetail>(`/plan-adjustment-drafts/${draftId}/items/${itemId}`, payload);
}

export function applyAdjustmentDraft(draftId: number, selectedItemIds: number[]) {
  return request.post<{ draft_id: number; status: string; applied_item_ids: number[] }>(
    `/plan-adjustment-drafts/${draftId}/apply`,
    { selected_item_ids: selectedItemIds },
  );
}

export function rejectAdjustmentDraft(draftId: number) {
  return request.post<WeeklyReviewDetail>(`/plan-adjustment-drafts/${draftId}/reject`);
}
