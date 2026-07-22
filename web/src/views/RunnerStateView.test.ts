import { flushPromises, shallowMount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import RunnerStateView from "./RunnerStateView.vue";
import { createRunnerStateSnapshot, createRunnerStateSnapshotDetail } from "@/test/runnerStateFixture";

const { getCurrentRunnerState, saveCurrentRunnerStateSnapshot, messageSuccess, messageError, messageInfo } = vi.hoisted(() => ({
  getCurrentRunnerState: vi.fn(),
  saveCurrentRunnerStateSnapshot: vi.fn(),
  messageSuccess: vi.fn(),
  messageError: vi.fn(),
  messageInfo: vi.fn(),
}));

vi.mock("@/api/runnerState", () => ({ getCurrentRunnerState, saveCurrentRunnerStateSnapshot }));
vi.mock("@/api/request", () => ({
  getRequestErrorMessage: (error: unknown) => error instanceof Error ? error.message : "请求失败",
}));
vi.mock("element-plus", () => ({
  ElMessage: { success: messageSuccess, error: messageError, info: messageInfo },
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
  ElAlert: { props: ["title"], template: "<div>{{ title }}<slot name='title' /></div>" },
  ElTabs: {
    props: ["modelValue"],
    emits: ["update:modelValue", "tab-change"],
    template: `<div><button class="current-tab" @click="$emit('update:modelValue', 'current'); $emit('tab-change', 'current')">当前状态</button><button class="history-tab" @click="$emit('update:modelValue', 'history'); $emit('tab-change', 'history')">历史趋势</button><slot /></div>`,
  },
  ElTabPane: true,
  RunnerStateSnapshotContent: {
    name: "RunnerStateSnapshotContent",
    props: ["snapshot"],
    template: "<div class='snapshot-content-stub'>当前状态内容</div>",
  },
  RunnerStateSaveButton: {
    props: ["loading"],
    emits: ["save"],
    template: "<button class='save-button' :disabled='loading' @click='$emit(\"save\")'>保存今日状态</button>",
  },
  RunnerStateHistoryView: { template: "<div class='history-view-stub'>历史内容</div>" },
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
    messageInfo.mockReset();
    saveCurrentRunnerStateSnapshot.mockReset();
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
    expect(wrapper.find(".snapshot-content-stub").exists()).toBe(true);
    expect(wrapper.findComponent({ name: "RunnerStateSnapshotContent" }).props("snapshot").risk_flags).toEqual([]);
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

    expect(wrapper.find(".snapshot-content-stub").exists()).toBe(true);
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

  it("does not mount history until the history tab is selected", async () => {
    getCurrentRunnerState.mockResolvedValue({ snapshot: createRunnerStateSnapshot() });
    const wrapper = mountPage();
    await flushPromises();
    expect(wrapper.find(".history-view-stub").exists()).toBe(false);
    await wrapper.find(".history-tab").trigger("click");
    expect(wrapper.find(".history-view-stub").exists()).toBe(true);
    await wrapper.find(".current-tab").trigger("click");
    expect(wrapper.find(".snapshot-content-stub").exists()).toBe(true);
  });

  it("handles created and duplicate snapshot saves as normal results", async () => {
    getCurrentRunnerState.mockResolvedValue({ snapshot: createRunnerStateSnapshot() });
    saveCurrentRunnerStateSnapshot
      .mockResolvedValueOnce({ snapshot: createRunnerStateSnapshotDetail(), created: true, duplicate: false })
      .mockResolvedValueOnce({ snapshot: createRunnerStateSnapshotDetail(), created: false, duplicate: true });
    const wrapper = mountPage();
    await flushPromises();
    await wrapper.find(".save-button").trigger("click");
    await flushPromises();
    expect(messageSuccess).toHaveBeenCalledWith("今日训练状态已保存");
    await wrapper.find(".save-button").trigger("click");
    await flushPromises();
    expect(messageInfo).toHaveBeenCalledWith("当前状态与最近保存记录一致，无需重复保存");
  });

  it("keeps the current snapshot when saving fails", async () => {
    getCurrentRunnerState.mockResolvedValue({ snapshot: createRunnerStateSnapshot() });
    saveCurrentRunnerStateSnapshot.mockRejectedValue(new Error("虚构保存失败"));
    const wrapper = mountPage();
    await flushPromises();
    await wrapper.find(".save-button").trigger("click");
    await flushPromises();
    expect(wrapper.find(".snapshot-content-stub").exists()).toBe(true);
    expect(messageError).toHaveBeenCalledWith("保存失败：虚构保存失败");
  });
});
