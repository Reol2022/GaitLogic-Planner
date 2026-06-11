import request from "./request";
import type { TrainingCalendarResult } from "@/types/models";

export function getTrainingCalendar(params: { month: string; cycle_id?: number | null }) {
  return request.get<TrainingCalendarResult>("/training-calendar", { params });
}
