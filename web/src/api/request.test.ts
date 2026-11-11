import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  reject: undefined as undefined | ((error: unknown) => Promise<unknown>),
  message: vi.fn(), requestAuth: vi.fn(), mode: vi.fn(() => "modal"),
}));
vi.mock("axios", () => ({ default: {
  isAxiosError: (e: { isAxiosError?: boolean }) => e?.isAxiosError === true,
  create: () => ({ interceptors: {
    request: { use: vi.fn() },
    response: { use: (_ok: unknown, reject: typeof mocks.reject) => { mocks.reject = reject; } },
  } }),
} }));
vi.mock("element-plus", () => ({ ElMessage: { error: mocks.message } }));
vi.mock("@/utils/authPrompt", () => ({ requestAuth: mocks.requestAuth }));
vi.mock("@/utils/systemSettingsCache", () => ({ getCachedAuthEntryMode: mocks.mode }));
import "./request";

describe("authentication response errors", () => {
  beforeEach(() => { localStorage.clear(); vi.clearAllMocks(); });
  it.each(["/auth/login", "/api/auth/login"]) ("shows rejected credentials without expiring another session: %s", async (url) => {
    localStorage.setItem("gaitlogic_access_token", "synthetic-existing-token");
    const error = { response: { status: 401 }, config: { url } };
    await expect(mocks.reject!(error)).rejects.toBe(error);
    expect(mocks.message).toHaveBeenCalledWith("用户名或密码错误，请重新输入。");
    expect(mocks.requestAuth).not.toHaveBeenCalled();
    expect(localStorage.getItem("gaitlogic_access_token")).toBe("synthetic-existing-token");
  });
  it("lets the login form own the inline message", async () => {
    const error = { response: { status: 401 }, config: { url: "/auth/login", skipErrorMessage: true } };
    await expect(mocks.reject!(error)).rejects.toBe(error);
    expect(mocks.message).not.toHaveBeenCalled();
    expect(mocks.requestAuth).not.toHaveBeenCalled();
  });
  it("still expires an unauthorized protected request", async () => {
    localStorage.setItem("gaitlogic_access_token", "synthetic-expired-token");
    const error = { response: { status: 401 }, config: { url: "/auth/me" } };
    await expect(mocks.reject!(error)).rejects.toBe(error);
    expect(localStorage.getItem("gaitlogic_access_token")).toBeNull();
    expect(mocks.requestAuth).toHaveBeenCalledTimes(1);
  });
});
