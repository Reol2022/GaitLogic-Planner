import request from "./request";
import type { FeedbackItem, FeedbackPayload } from "@/types/models";

export function submitFeedback(payload: FeedbackPayload) {
  return request.post<{ message: string }>("/feedback", payload);
}

export function listMyFeedback() {
  return request.get<FeedbackItem[]>("/feedback/my");
}
