import axios from "axios";
import request from "./request";
import type {
  CoachConversation,
  CoachConversationMessageResult,
  CoachConversationTurnStatus,
  CoachConversationPage,
  CoachConversationStatus,
  CoachMessagePage,
  CoachQueryRequest,
  CoachQueryResponse,
} from "@/types/coachAgent";

const ERROR_MESSAGES: Record<number, string> = {
  401: "登录状态已失效，请重新登录",
  403: "该教练能力暂未开放",
  400: "输入内容不符合要求",
  422: "输入内容不符合要求",
  429: "请求过于频繁，请稍后再试",
  409: "当前对话正在生成回复，请等待完成后再发送",
  503: "AI 教练暂不可用",
};

export class CoachAgentRequestError extends Error {
  constructor(
    message: string,
    public readonly status: number | null,
  ) {
    super(message);
    this.name = "CoachAgentRequestError";
  }
}

export function getCoachAgentErrorMessage(error: unknown): string {
  if (error instanceof CoachAgentRequestError) return error.message;
  if (!axios.isAxiosError(error)) return "暂时无法连接服务，请稍后重试";
  const status = error.response?.status;
  if (status !== undefined && ERROR_MESSAGES[status]) return ERROR_MESSAGES[status];
  return "暂时无法连接服务，请稍后重试";
}

export async function queryCoach(
  payload: CoachQueryRequest,
  signal?: AbortSignal,
): Promise<CoachQueryResponse> {
  try {
    return await request.post<CoachQueryResponse>("/coach/query", payload, {
      signal,
      skipErrorMessage: true,
    });
  } catch (error) {
    const status = axios.isAxiosError(error) ? error.response?.status ?? null : null;
    throw new CoachAgentRequestError(getCoachAgentErrorMessage(error), status);
  }
}

export async function createCoachConversation(title?: string): Promise<CoachConversation> {
  return request.post<CoachConversation>("/coach/conversations", title ? { title } : {});
}

export async function listCoachConversations(
  page = 1,
  pageSize = 20,
  status?: CoachConversationStatus,
): Promise<CoachConversationPage> {
  return request.get<CoachConversationPage>("/coach/conversations", {
    params: { page, page_size: pageSize, status },
  });
}

export async function getCoachConversationMessages(
  conversationId: string,
  page = 1,
  pageSize = 50,
): Promise<CoachMessagePage> {
  return request.get<CoachMessagePage>(`/coach/conversations/${conversationId}/messages`, {
    params: { page, page_size: pageSize },
  });
}

export async function sendCoachConversationMessage(
  conversationId: string,
  message: string,
  clientTurnId: string,
): Promise<CoachConversationMessageResult> {
  return request.post<CoachConversationMessageResult>(
    `/coach/conversations/${conversationId}/messages`,
    { client_turn_id: clientTurnId, message },
    { skipErrorMessage: true },
  );
}

export async function getCoachConversationTurnStatus(
  conversationId: string,
  clientTurnId: string,
): Promise<CoachConversationTurnStatus> {
  return request.get<CoachConversationTurnStatus>(
    `/coach/conversations/${conversationId}/turns/${clientTurnId}/status`,
  );
}

export async function updateCoachConversation(
  conversationId: string,
  payload: { title?: string; status?: CoachConversationStatus },
): Promise<CoachConversation> {
  return request.patch<CoachConversation>(`/coach/conversations/${conversationId}`, payload);
}

export async function deleteCoachConversation(conversationId: string): Promise<void> {
  await request.delete(`/coach/conversations/${conversationId}`);
}
