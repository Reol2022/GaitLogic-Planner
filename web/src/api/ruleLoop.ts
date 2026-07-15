import request from "./request";
import type { RuleLoopEvaluation, TrainingAdjustmentDraft } from "@/types/models";

export function getTodayRuleEvaluation(date?: string) {
  return request.get<RuleLoopEvaluation>("/training-readiness/today-evaluation", {
    params: { date },
    skipErrorMessage: true,
  });
}

export function recalculateTodayRuleEvaluation(date?: string) {
  return request.post<RuleLoopEvaluation>("/training-readiness/today-evaluation/recalculate", undefined, {
    params: { date },
  });
}

export function validateTrainingPlan(cycleId: number, force = false) {
  return request.post<RuleLoopEvaluation>(`/training-plans/${cycleId}/validate`, undefined, {
    params: { force },
  });
}

export function validateAiPlanDraft(draftId: number, force = false) {
  return request.post<RuleLoopEvaluation>(`/ai-plan-drafts/${draftId}/validate`, { force });
}

export function validatePlanImportDraft(importId: number, force = false) {
  return request.post<RuleLoopEvaluation>(`/plan-import-drafts/${importId}/validate`, { force });
}

export function listTrainingAdjustmentDrafts() {
  return request.get<{ items: TrainingAdjustmentDraft[]; total: number }>("/training-adjustment-drafts");
}

export function getWorkoutRuleReview(workoutLogId: number) {
  return request.get<RuleLoopEvaluation>(`/workout-logs/${workoutLogId}/rule-review`, { skipErrorMessage: true });
}

export function createWorkoutRuleReview(workoutLogId: number, force = false) {
  return request.post<RuleLoopEvaluation>(`/workout-logs/${workoutLogId}/rule-review`, undefined, {
    params: { force },
  });
}

export function getTrainingAdjustmentDraft(draftId: number) {
  return request.get<TrainingAdjustmentDraft>(`/training-adjustment-drafts/${draftId}`);
}

export function confirmTrainingAdjustmentDraft(draftId: number) {
  return request.post<TrainingAdjustmentDraft>(`/training-adjustment-drafts/${draftId}/confirm`);
}

export function applyTrainingAdjustmentDraft(draftId: number) {
  return request.post<{ draft_id: number; status: string; applied_result: Record<string, unknown> }>(
    `/training-adjustment-drafts/${draftId}/apply`,
  );
}

export function rejectTrainingAdjustmentDraft(draftId: number) {
  return request.post<TrainingAdjustmentDraft>(`/training-adjustment-drafts/${draftId}/reject`);
}
