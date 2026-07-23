import { flushPromises, shallowMount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import CoachAgentView from "./CoachAgentView.vue";
import { createCoachResponse } from "@/test/coachAgentFixture";

const { queryCoach, getCoachAgentErrorMessage } = vi.hoisted(() => ({
  queryCoach: vi.fn(),
  getCoachAgentErrorMessage: vi.fn((error: unknown) => error instanceof Error ? error.message : "安全请求错误"),
}));

vi.mock("@/api/coachAgent", () => ({ queryCoach, getCoachAgentErrorMessage }));

const stubs = {
  PageHeader: { props: ["title", "subtitle"], template: "<header><h1>{{ title }}</h1><p>{{ subtitle }}</p></header>" },
  ElIcon: { template: "<i><slot /></i>" },
  ElInput: {
    props: ["modelValue", "disabled", "maxlength"],
    emits: ["update:modelValue", "keydown"],
    template: `<textarea class="coach-textarea" :value="modelValue" :disabled="disabled" :maxlength="maxlength" @input="$emit('update:modelValue', $event.target.value)" @keydown="$emit('keydown', $event)" />`,
  },
  ElButton: {
    props: ["disabled", "loading"],
    emits: ["click"],
    template: "<button :disabled='disabled' @click='$emit(\"click\")'><slot /></button>",
  },
  CoachTodayRecommendationCard: {
    props: ["recommendation", "riskLevel"],
    template: "<div class='recommendation-stub'>确定性规则建议 {{ recommendation.decision }}</div>",
  },
  CoachSafetyNotices: {
    props: ["warnings", "limitations", "riskLevel"],
    template: "<div v-if='warnings.length || limitations.length' class='notices-stub'>安全提示</div>",
  },
  CoachAnswerCard: {
    props: ["status", "answer", "summary", "generatedAt", "providerStatus"],
    template: "<div class='answer-stub'>AI 解释 {{ status }} {{ answer }}</div>",
  },
  CoachToolSummary: {
    props: ["tools"],
    template: "<div class='tools-stub'>本次参考的数据 {{ tools.length }}</div>",
  },
};

function mountPage() {
  return shallowMount(CoachAgentView, { global: { stubs } });
}

describe("CoachAgentView", () => {
  beforeEach(() => {
    queryCoach.mockReset();
    getCoachAgentErrorMessage.mockClear();
  });

  it("shows three supported intents and never exposes WEEKLY or provider configuration", () => {
    const wrapper = mountPage();
    expect(wrapper.text()).toContain("今日训练建议");
    expect(wrapper.text()).toContain("解释当前状态");
    expect(wrapper.text()).toContain("一般训练问题");
    expect(wrapper.text()).not.toContain("WEEKLY_REVIEW");
    expect(wrapper.text()).not.toContain("API Key");
    expect(wrapper.text()).not.toContain("Base URL");
    expect(wrapper.text()).not.toContain("选择模型");
    expect(wrapper.text()).toContain("不会自动改课表");
  });

  it("switches intents, applies examples, and disables empty general questions", async () => {
    const wrapper = mountPage();
    const buttons = wrapper.findAll(".intent-card");
    await buttons[1].trigger("click");
    expect(wrapper.find("textarea").element.value).toContain("Runner State");
    await buttons[2].trigger("click");
    expect(wrapper.find("textarea").element.value).toBe("");
    expect(wrapper.find(".send-button").attributes("disabled")).toBeDefined();
  });

  it("sends one bounded request and renders authority before AI explanation", async () => {
    queryCoach.mockResolvedValue(createCoachResponse());
    const wrapper = mountPage();
    await wrapper.find(".send-button").trigger("click");
    await flushPromises();

    expect(queryCoach).toHaveBeenCalledTimes(1);
    const payload = queryCoach.mock.calls[0][0];
    expect(payload.intent).toBe("TODAY_RECOMMENDATION");
    expect(payload.conversation_context).toEqual([]);
    expect(JSON.stringify(payload)).not.toMatch(/user_id|provider|model|base_url|api_key|tools/);
    const html = wrapper.html();
    expect(html.indexOf("recommendation-stub")).toBeLessThan(html.indexOf("answer-stub"));
    expect(wrapper.text()).toContain("SUCCEEDED");
  });

  it("prevents duplicate submissions while a request is pending", async () => {
    let resolveRequest: ((value: unknown) => void) | undefined;
    queryCoach.mockReturnValue(new Promise((resolve) => { resolveRequest = resolve; }));
    const wrapper = mountPage();
    await wrapper.find(".send-button").trigger("click");
    await wrapper.find(".send-button").trigger("click");
    expect(queryCoach).toHaveBeenCalledTimes(1);
    expect(wrapper.text()).toContain("正在读取训练事实");
    resolveRequest?.(createCoachResponse());
    await flushPromises();
  });

  it("preserves input on 429 or network failure for manual retry", async () => {
    queryCoach.mockRejectedValue(new Error("请求过于频繁，请稍后再试"));
    const wrapper = mountPage();
    const input = wrapper.find("textarea");
    await input.setValue("请保留这条虚构问题");
    await wrapper.find(".send-button").trigger("click");
    await flushPromises();
    expect(wrapper.find("textarea").element.value).toBe("请保留这条虚构问题");
    expect(wrapper.find("[role='alert']").text()).toBe("请求过于频繁，请稍后再试");
  });

  it("treats DEGRADED as a renderable result and can clear the memory-only session", async () => {
    queryCoach.mockResolvedValue(createCoachResponse({
      status: "DEGRADED",
      provider_status: "FAILED",
      limitations: [{ code: "MODEL_EXPLANATION_UNAVAILABLE", message: "虚构降级说明" }],
    }));
    const wrapper = mountPage();
    await wrapper.find(".send-button").trigger("click");
    await flushPromises();
    expect(wrapper.find(".answer-stub").text()).toContain("DEGRADED");
    expect(wrapper.text()).toContain("安全提示");
    const clear = wrapper.findAll("button").find((item) => item.text() === "清空会话");
    await clear?.trigger("click");
    expect(wrapper.find(".conversation").exists()).toBe(false);
    expect(wrapper.text()).toContain("从一个训练问题开始");
  });

  it("aborts on unmount and does not persist conversations in browser storage", async () => {
    queryCoach.mockReturnValue(new Promise(() => undefined));
    const localSet = vi.spyOn(Storage.prototype, "setItem");
    const sessionSet = vi.spyOn(window.sessionStorage, "setItem");
    const wrapper = mountPage();
    await wrapper.find(".send-button").trigger("click");
    wrapper.unmount();
    expect(localSet).not.toHaveBeenCalled();
    expect(sessionSet).not.toHaveBeenCalled();
    localSet.mockRestore();
    sessionSet.mockRestore();
  });
});
