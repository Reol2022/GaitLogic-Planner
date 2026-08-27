import request from "./request";
import type {
  AdaptiveApprovalResult,
  AdaptiveProposal,
  ProposalRevisionResult,
  LangGraphWeeklyReview,
  WeeklyFacts,
} from "@/types/adaptivePlan";

export interface WeeklyFactsQuery {
  week_start: string;
  week_end: string;
  cycle_id?: number | null;
  source_block_id?: number | null;
  target_block_id?: number | null;
  timezone?: string;
}

export function getCanonicalWeeklyFacts(params: WeeklyFactsQuery) {
  return request.get<WeeklyFacts>("/weekly-reviews/facts", { params });
}

export function generateLangGraphWeeklyReview(payload: WeeklyFactsQuery) {
  return request.post<LangGraphWeeklyReview>("/weekly-reviews/graph", payload, {
    // Weekly analysis and plan design are two independent Thinking requests.
    // Their combined wall-clock time can legitimately exceed the global 120s budget.
    timeout: 900000,
  });
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

export function reviseAdaptiveProposal(
  reviewId: number,
  payload: { proposal_id: number; feedback: { reason_codes: string[]; free_text?: string | null } },
) {
  return request.post<ProposalRevisionResult>(`/weekly-reviews/${reviewId}/proposal/revise`, payload, {
    timeout: 900000,
  });
}
