import { flushPromises, shallowMount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import RunnerStateView from "./RunnerStateView.vue";
import RunnerStateSummary from "@/components/runner-state/RunnerStateSummary.vue";
import RunnerStateRiskList from "@/components/runner-state/RunnerStateRiskList.vue";
import { createRunnerStateSnapshot } from "@/test/runnerStateFixture";

const { getCurrentRunnerState, messageSuccess, messageError } = vi.hoisted(() => ({
  getCurrentRunnerState: vi.fn(),
  messageSuccess: vi.fn(),
  messageError: vi.fn(),
}));

vi.mock("@/api/runnerState", () => ({ getCurrentRunnerState }));
vi.mock("@/api/request", () => ({
  getRequestErrorMessage: (error: unknown) => error instanceof Error ? error.message : "请求失败",
}));
vi.mock("element-plus", () => ({
  ElMessage: { success: messageSuccess, error: messageError },
}));

const stubs = {
  PageHeader: {
    props: ["title", "subtitle"],
    template: "<header><h1>{{ title }}</h1><p>{{ subtitle }}</p><slot name='actions' /></header>",
  },
  ElPopover: { template: "<div><slot name='reference' /><slot /></div>" },
  ElButton: {
    props: ["disabled", "loading"],
    emits: ["click"],
    template: "<button :disabled='disabled' @click='$emit(\"click\")'><slot /></button>",
  },
  ElSkeleton: { template: "<div>骨架加载</div>" },
  ElResult: {
    props: ["title", "subTitle"],
    template: "<div><strong>{{ title }}</strong><span>{{ subTitle }}</span><slot name='extra' /></div>",
  },
  ElAlert: { template: "<div><slot name='title' /></div>" },
  RunnerStateCard: true,
  RunnerStateDataQuality: true,
  RunnerStateMetrics: true,
  RunnerStateRiskList: true,
  RunnerStateSummary: true,
};

function mountPage() {
  return shallowMount(RunnerStateView, { global: { stubs } });
}

describe("RunnerStateView", () => {
  beforeEach(() => {
    getCurrentRunnerState.mockReset();
    messageSuccess.mockReset();
    messageError.mockReset();
  });

  it("shows a loading skeleton while the current state is loading", async () => {
    getCurrentRunnerState.mockReturnValue(new Promise(() => undefined));
    const wrapper = mountPage();
    await wrapper.vm.$nextTick();
    expect(wrapper.find("[aria-label='训练状态加载中']").exists()).toBe(true);
  });

  it("loads and presents the current snapshot", async () => {
    getCurrentRunnerState.mockResolvedValue({ snapshot: createRunnerStateSnapshot() });
    const wrapper = mountPage();
    await flushPromises();

    expect(getCurrentRunnerState).toHaveBeenCalledTimes(1);
    expect(wrapper.findComponent(RunnerStateSummary).exists()).toBe(true);
    expect(wrapper.findComponent(RunnerStateRiskList).props("flags")).toEqual([]);
    expect(wrapper.text()).toContain("数据截止 2026-07-15");
  });

  it("shows a comprehensible initial API error", async () => {
    getCurrentRunnerState.mockRejectedValue(new Error("虚构的网络错误"));
    const wrapper = mountPage();
    await flushPromises();
    expect(wrapper.text()).toContain("训练状态加载失败");
    expect(wrapper.text()).toContain("虚构的网络错误");
  });

  it("refreshes successfully and prevents duplicate refresh requests", async () => {
    getCurrentRunnerState.mockResolvedValueOnce({ snapshot: createRunnerStateSnapshot() });
    const wrapper = mountPage();
    await flushPromises();

    let resolveRefresh: ((value: unknown) => void) | undefined;
    getCurrentRunnerState.mockReturnValueOnce(new Promise((resolve) => { resolveRefresh = resolve; }));
    await wrapper.find(".refresh-button").trigger("click");
    await wrapper.find(".refresh-button").trigger("click");
    expect(getCurrentRunnerState).toHaveBeenCalledTimes(2);

    resolveRefresh?.({ snapshot: createRunnerStateSnapshot() });
    await flushPromises();
    expect(messageSuccess).toHaveBeenCalledWith("训练状态已刷新");
  });

  it("keeps the last successful state when refresh fails", async () => {
    getCurrentRunnerState.mockResolvedValueOnce({ snapshot: createRunnerStateSnapshot() });
    const wrapper = mountPage();
    await flushPromises();
    getCurrentRunnerState.mockRejectedValueOnce(new Error("刷新网络错误"));

    await wrapper.find(".refresh-button").trigger("click");
    await flushPromises();

    expect(wrapper.findComponent(RunnerStateSummary).exists()).toBe(true);
    expect(wrapper.text()).toContain("仍显示上一次成功加载的状态");
    expect(messageError).toHaveBeenCalled();
  });

  it("does not display diagnostic or automatic-adjustment claims", async () => {
    getCurrentRunnerState.mockResolvedValue({ snapshot: createRunnerStateSnapshot() });
    const wrapper = mountPage();
    await flushPromises();
    const text = wrapper.text();
    expect(text).not.toContain("即将受伤");
    expect(text).not.toContain("过度训练");
    expect(text).not.toContain("自动调整课表");
  });
});
