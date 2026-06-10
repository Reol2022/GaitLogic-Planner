import request from "./request";
import type { PaceRule, PaceRulePayload } from "@/types/models";

export function listPaceRules() {
  return request.get<PaceRule[]>("/pace-rules");
}

export function createPaceRule(payload: PaceRulePayload) {
  return request.post<PaceRule>("/pace-rules", payload);
}

export function updatePaceRule(id: number, payload: Partial<PaceRulePayload>) {
  return request.put<PaceRule>(`/pace-rules/${id}`, payload);
}

export function deletePaceRule(id: number) {
  return request.delete(`/pace-rules/${id}`);
}
