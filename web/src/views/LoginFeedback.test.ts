import { mount, flushPromises } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ElementPlus from "element-plus";
import LoginView from "./LoginView.vue";
import AuthDialog from "@/components/AuthDialog.vue";

const { login, saveToken, push } = vi.hoisted(() => ({ login: vi.fn(), saveToken: vi.fn(), push: vi.fn() }));
vi.mock("@/api/auth", async (importOriginal) => ({
  ...await importOriginal<typeof import("@/api/auth")>(), loginUser: login, setStoredToken: saveToken,
}));
vi.mock("vue-router", () => ({ useRouter: () => ({ push }), useRoute: () => ({ query: {} }) }));
vi.mock("@/api/systemSettings", () => ({ getSystemSettings: vi.fn().mockResolvedValue({ allow_public_registration: false }) }));

for (const [name, component] of [["login page", LoginView], ["login dialog", AuthDialog]] as const) {
  describe(name, () => {
    beforeEach(() => { vi.clearAllMocks(); login.mockReset(); });
    function render() {
      return mount(component, { global: { plugins: [ElementPlus], stubs: {
        SiteFilingFooter: true, RouterLink: true,
        ElDialog: { template: "<section><slot name='header'/><slot/></section>" },
      } } });
    }
    async function fill(wrapper: ReturnType<typeof render>, password = "wrong") {
      await wrapper.find('input[autocomplete="username"]').setValue("synthetic-runner");
      await wrapper.find('input[autocomplete="current-password"]').setValue(password);
    }
    it.each([
      [{ isAxiosError: true, response: { status: 401 } }, "用户名或密码错误，请重新输入。"],
      [{ isAxiosError: true, response: { status: 429 } }, "登录尝试过于频繁，请稍后再试。"],
      [{ isAxiosError: true, code: "ERR_NETWORK" }, "网络错误"],
      [{ isAxiosError: true, code: "ECONNABORTED" }, "请求超时"],
      [{ isAxiosError: true, response: { status: 503 } }, "服务暂时不可用"],
    ])("displays a persistent safe error and does not navigate", async (error, message) => {
      login.mockRejectedValue(error);
      const wrapper=render(); await flushPromises(); await fill(wrapper);
      await wrapper.find("form").trigger("submit");
      await vi.waitFor(() => expect(wrapper.find('[role="alert"]').text()).toContain(message));
      expect(login).toHaveBeenCalledWith({ username: "synthetic-runner", password: "wrong" }, { skipErrorMessage: true });
      expect(saveToken).not.toHaveBeenCalled(); expect(push).not.toHaveBeenCalled();
      expect(wrapper.find('button[type="submit"]').classes()).not.toContain("is-loading");
      wrapper.unmount();
    });
    it("shows required-field feedback without sending credentials", async () => {
      const wrapper=render(); await flushPromises(); await wrapper.find("form").trigger("submit");
      await vi.waitFor(() => expect(wrapper.find('[role="alert"]').text()).toContain("请填写用户名和密码"));
      expect(login).not.toHaveBeenCalled(); wrapper.unmount();
    });
    it("ignores duplicate submits while a request is pending", async () => {
      login.mockReturnValue(new Promise(() => {}));
      const wrapper=render(); await flushPromises(); await fill(wrapper);
      await wrapper.find("form").trigger("submit"); await wrapper.find("form").trigger("submit");
      await vi.waitFor(() => expect(login).toHaveBeenCalledTimes(1)); wrapper.unmount();
    });
    it("clears the old error when the user retries", async () => {
      login.mockRejectedValueOnce({ isAxiosError: true, response: { status: 401 } });
      const wrapper=render(); await flushPromises(); await fill(wrapper);
      await wrapper.find("form").trigger("submit");
      await vi.waitFor(() => expect(wrapper.find('[role="alert"]').text()).toContain("用户名或密码错误"));
      login.mockReturnValue(new Promise(() => {}));
      await fill(wrapper, "corrected-synthetic-password");
      await wrapper.find("form").trigger("submit");
      await vi.waitFor(() => expect(login).toHaveBeenCalledTimes(2));
      expect(wrapper.find('[role="alert"]').exists()).toBe(false);
      wrapper.unmount();
    });
    if (name === "login page") it("saves the token and navigates after successful login", async () => {
      login.mockResolvedValue({ access_token: "synthetic-token" });
      const wrapper=render(); await flushPromises(); await fill(wrapper, "synthetic-password");
      await wrapper.find("form").trigger("submit");
      await vi.waitFor(() => expect(push).toHaveBeenCalledWith("/"));
      expect(saveToken).toHaveBeenCalledWith("synthetic-token");
      expect(wrapper.find('[role="alert"]').exists()).toBe(false); wrapper.unmount();
    });
  });
}
