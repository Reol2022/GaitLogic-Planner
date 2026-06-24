import request from "./request";
import type {
  DailyTrainingLoad,
  RecoveryCheckin,
  RecoveryCheckinPayload,
  TrainingLoadSummaryRead,
  TrainingReadinessAssessment,
  TrainingReadinessToday,
} from "@/types/models";

export function getTodayRecoveryCheckin() {
  return request.get<RecoveryCheckin | null>("/recovery-checkins/today", { skipErrorMessage: true });
}

export function saveTodayRecoveryCheckin(payload: RecoveryCheckinPayload) {
  return request.put<RecoveryCheckin>("/recovery-checkins/today", payload);
}

export function deleteRecoveryCheckin(checkinDate: string) {
  return request.delete<{ message: string }>(`/recovery-checkins/${checkinDate}`);
}

export function listRecoveryCheckins(startDate?: string, endDate?: string) {
  return request.get<{ items: RecoveryCheckin[] }>("/recovery-checkins", {
    params: { start_date: startDate, end_date: endDate },
  });
}

export function getTodayReadiness() {
  return request.get<TrainingReadinessToday>("/training-readiness/today", { skipErrorMessage: true });
}

export function recalculateReadiness(date?: string) {
  return request.post<TrainingReadinessToday>("/training-readiness/recalculate", undefined, {
    params: { date },
  });
}

export function listReadinessHistory(days = 30) {
  return request.get<{ items: TrainingReadinessAssessment[] }>("/training-readiness/history", {
    params: { days },
  });
}

export function getTrainingLoadSummary(date?: string) {
  return request.get<{ summary: TrainingLoadSummaryRead }>("/training-load/summary", {
    params: { date },
    skipErrorMessage: true,
  });
}

export function getTrainingLoadTrend(startDate?: string, endDate?: string) {
  return request.get<{ start_date: string; end_date: string; items: DailyTrainingLoad[] }>("/training-load/trend", {
    params: { start_date: startDate, end_date: endDate },
  });
}
