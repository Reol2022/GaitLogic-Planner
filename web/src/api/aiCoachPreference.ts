import request from "./request";
import type { AICoachPreference, AICoachPreferencePayload } from "@/types/models";

export function getAICoachPreference() {
  return request.get<AICoachPreference>("/ai-coach-preference");
}

export function updateAICoachPreference(payload: AICoachPreferencePayload) {
  return request.put<AICoachPreference>("/ai-coach-preference", payload);
}
