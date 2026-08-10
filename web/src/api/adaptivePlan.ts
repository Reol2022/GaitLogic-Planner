import request from "./request";
import type {
  AdaptiveApprovalResult,
  AdaptiveProposal,
  LangGraphWeeklyReview,
  WeeklyFacts,
} from "@/types/adaptivePlan";

export interface WeeklyFactsQuery {
  week_start: string;
  week_end: string;
  cycle_id?: number | null;
  timezone?: string;
}

export function getCanonicalWeeklyFacts(params: WeeklyFactsQuery) {
  return request.get<WeeklyFacts>("/weekly-reviews/facts", { params });
}

export function generateLangGraphWeeklyReview(payload: WeeklyFactsQuery) {
  return request.post<LangGraphWeeklyReview>("/weekly-reviews/graph", payload);
}

export function getAdaptiveProposal(proposalId: number) {
  return request.get<AdaptiveProposal>(`/adaptive-plan/proposals/${proposalId}`);
}

export function approveAdaptiveProposal(proposalId: number) {
  return request.post<AdaptiveApprovalResult>(`/adaptive-plan/proposals/${proposalId}/approve`);
}

export function rejectAdaptiveProposal(proposalId: number) {
  return request.post<AdaptiveApprovalResult>(`/adaptive-plan/proposals/${proposalId}/reject`);
}
