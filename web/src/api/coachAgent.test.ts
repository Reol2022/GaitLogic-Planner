import { beforeEach, describe, expect, it, vi } from "vitest";

const { post, isAxiosError } = vi.hoisted(() => ({
  post: vi.fn(),
  isAxiosError: vi.fn((error: { isAxiosError?: boolean }) => error?.isAxiosError === true),
}));

vi.mock("./request", () => ({ default: { post } }));
vi.mock("axios", () => ({ default: { isAxiosError }, isAxiosError }));

import {
  CoachAgentRequestError,
  getCoachAgentErrorMessage,
  queryCoach,
} from "./coachAgent";
import { createCoachResponse } from "@/test/coachAgentFixture";

describe("coach agent api", () => {
  beforeEach(() => {
    post.mockReset();
    isAxiosError.mockClear();
  });

  it("sends one authenticated-client POST with only the public request", async () => {
    post.mockResolvedValue(createCoachResponse());
    const payload = {
      message: "虚构问题",
      intent: "TODAY_RECOMMENDATION" as const,
      conversation_context: [{ role: "user" as const, content: "公开摘要" }],
    };
    await queryCoach(payload);
    expect(post).toHaveBeenCalledTimes(1);
    expect(post).toHaveBeenCalledWith("/coach/query", payload, {
      signal: undefined,
      skipErrorMessage: true,
    });
    const sent = JSON.stringify(post.mock.calls[0][1]);
    for (const key of ["user_id", "provider", "model", "base_url", "api_key", "system_prompt", "tools"]) {
      expect(sent).not.toContain(key);
    }
  });

  it.each([
    [401, "登录状态已失效，请重新登录"],
    [403, "该教练能力暂未开放"],
    [400, "输入内容不符合要求"],
    [422, "输入内容不符合要求"],
    [429, "请求过于频繁，请稍后再试"],
    [503, "AI 教练暂不可用"],
  ])("maps HTTP %s to a safe message", async (status, message) => {
    post.mockRejectedValue({ isAxiosError: true, response: { status } });
    await expect(queryCoach({ message: "虚构问题" })).rejects.toMatchObject({
      name: "CoachAgentRequestError",
      status,
      message,
    });
    expect(post).toHaveBeenCalledTimes(1);
  });

  it("maps network failures without exposing raw details", async () => {
    post.mockRejectedValue({ isAxiosError: true, code: "ERR_NETWORK" });
    await expect(queryCoach({ message: "虚构问题" })).rejects.toThrow("暂时无法连接服务，请稍后重试");
    expect(post).toHaveBeenCalledTimes(1);
  });

  it("exposes the same safe message for wrapped request errors", () => {
    expect(getCoachAgentErrorMessage(new CoachAgentRequestError("安全错误", 429))).toBe("安全错误");
  });
});
