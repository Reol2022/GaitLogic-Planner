import request from "./request";
import type { FeedbackItem, FeedbackPayload } from "@/types/models";

export function submitFeedback(payload: FeedbackPayload) {
  return request.post<{ message: string }>("/api/feedback", payload);
}

export function listMyFeedback() {
  return request.get<FeedbackItem[]>("/api/feedback/my");
}
