import axios from "axios";
import request from "./request";
import type { CoachQueryRequest, CoachQueryResponse } from "@/types/coachAgent";

const ERROR_MESSAGES: Record<number, string> = {
  401: "登录状态已失效，请重新登录",
  403: "该教练能力暂未开放",
  400: "输入内容不符合要求",
  422: "输入内容不符合要求",
  429: "请求过于频繁，请稍后再试",
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
