import { flushPromises, shallowMount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import RunnerStateHistoryView from "./RunnerStateHistoryView.vue";
import {
  createRunnerStateSnapshotDetail,
  createRunnerStateSnapshotList,
  createRunnerStateTimeline,
} from "@/test/runnerStateFixture";

const { getRunnerStateTimeline, listRunnerStateSnapshots, getRunnerStateSnapshotDetail } = vi.hoisted(() => ({
  getRunnerStateTimeline: vi.fn(),
  listRunnerStateSnapshots: vi.fn(),
  getRunnerStateSnapshotDetail: vi.fn(),
}));

vi.mock("@/api/runnerState", () => ({ getRunnerStateTimeline, listRunnerStateSnapshots, getRunnerStateSnapshotDetail }));
vi.mock("@/api/request", () => ({ getRequestErrorMessage: (error: unknown) => error instanceof Error ? error.message : "请求失败" }));

const stubs = {
  ElRadioGroup: { template: "<div><slot /></div>" },
  ElRadioButton: { template: "<button><slot /></button>" },
  ElAlert: { props: ["title", "description"], template: "<div>{{ title }} {{ description }}</div>" },
  ElSkeleton: true,
  ElEmpty: { props: ["description"], template: "<div>{{ description }}<slot /></div>" },
  ElButton: { emits: ["click"], template: "<button @click='$emit(\"click\")'><slot /></button>" },
  RunnerStateHistorySummary: true,
  RunnerStateVolumeChart: true,
  RunnerStateTimeline: true,
  RunnerStateRiskTimeline: { emits: ["open-detail"], template: "<button class='risk-detail' @click='$emit(\"open-detail\", 3001)'>风险详情</button>" },
  RunnerStateDataQualityTrend: true,
  RunnerStateSnapshotList: { emits: ["open-detail", "page-change"], template: "<div><button class='list-detail' @click='$emit(\"open-detail\", 3001)'>详情</button><button class='next-page' @click='$emit(\"page-change\", 2)'>下一页</button></div>" },
  RunnerStateSnapshotDetail: {
    name: "RunnerStateSnapshotDetail",
    props: ["visible", "detail", "loading", "error"],
    emits: ["update:visible"],
    template: "<div class='detail-stub'>{{ detail?.ruleset_version }} {{ error }}<button class='close-detail' @click='$emit(\"update:visible\", false)'>关闭</button></div>",
  },
};

function mountHistory() {
  return shallowMount(RunnerStateHistoryView, { global: { stubs } });
}

describe("RunnerStateHistoryView", () => {
  beforeEach(() => {
    getRunnerStateTimeline.mockReset();
    listRunnerStateSnapshots.mockReset();
    getRunnerStateSnapshotDetail.mockReset();
    getRunnerStateTimeline.mockResolvedValue(createRunnerStateTimeline());
    listRunnerStateSnapshots.mockResolvedValue(createRunnerStateSnapshotList());
  });

  it("loads timeline first and uses its server dates for the raw list", async () => {
    mountHistory();
    await flushPromises();
    expect(getRunnerStateTimeline).toHaveBeenCalledWith("28d", expect.any(AbortSignal));
    expect(listRunnerStateSnapshots).toHaveBeenCalledWith({
      start_date: "2026-06-22",
      end_date: "2026-07-19",
      limit: 30,
      offset: 0,
    }, expect.any(AbortSignal));
  });

  it("shows a normal empty state without automatically saving", async () => {
    getRunnerStateTimeline.mockResolvedValue(createRunnerStateTimeline([]));
    listRunnerStateSnapshots.mockResolvedValue(createRunnerStateSnapshotList([]));
    const wrapper = mountHistory();
    await flushPromises();
    expect(wrapper.text()).toContain("还没有训练状态记录");
    expect(wrapper.text()).toContain("返回当前状态");
  });

  it("keeps the previous timeline when a later request fails", async () => {
    const wrapper = mountHistory();
    await flushPromises();
    getRunnerStateTimeline.mockRejectedValueOnce(new Error("虚构趋势错误"));
    await (wrapper.vm as unknown as { refresh: () => Promise<void> }).refresh();
    await flushPromises();
    expect(wrapper.text()).toContain("仍保留上一次成功结果");
    expect(wrapper.findComponent({ name: "RunnerStateHistorySummary" }).exists()).toBe(true);
  });

  it("paginates the raw list without reloading the timeline", async () => {
    const wrapper = mountHistory();
    await flushPromises();
    await wrapper.find(".next-page").trigger("click");
    await flushPromises();
    expect(getRunnerStateTimeline).toHaveBeenCalledTimes(1);
    expect(listRunnerStateSnapshots).toHaveBeenLastCalledWith(expect.objectContaining({ offset: 30 }), expect.any(AbortSignal));
  });

  it("loads saved detail directly and never calls the current-state API", async () => {
    getRunnerStateSnapshotDetail.mockResolvedValue(createRunnerStateSnapshotDetail());
    const wrapper = mountHistory();
    await flushPromises();
    await wrapper.find(".list-detail").trigger("click");
    await flushPromises();
    expect(getRunnerStateSnapshotDetail).toHaveBeenCalledWith(3001, expect.any(AbortSignal));
    expect(wrapper.text()).toContain("runner-state-rules-1.0.0");
  });

  it("prevents an older timeline response from replacing a newer one", async () => {
    const wrapper = mountHistory();
    await flushPromises();
    let resolveOlder: ((value: ReturnType<typeof createRunnerStateTimeline>) => void) | undefined;
    const older = new Promise<ReturnType<typeof createRunnerStateTimeline>>((resolve) => { resolveOlder = resolve; });
    getRunnerStateTimeline
      .mockReturnValueOnce(older)
      .mockResolvedValueOnce({ ...createRunnerStateTimeline(), range: "12w", start_date: "2026-04-27" });

    const firstRefresh = (wrapper.vm as unknown as { refresh: () => Promise<void> }).refresh();
    const secondRefresh = (wrapper.vm as unknown as { refresh: () => Promise<void> }).refresh();
    await secondRefresh;
    await flushPromises();
    resolveOlder?.(createRunnerStateTimeline());
    await firstRefresh;
    await flushPromises();

    const summary = wrapper.findComponent({ name: "RunnerStateHistorySummary" });
    expect(summary.props("timeline").range).toBe("12w");
  });

  it("releases saved detail state when the detail drawer closes", async () => {
    getRunnerStateSnapshotDetail.mockResolvedValue(createRunnerStateSnapshotDetail());
    const wrapper = mountHistory();
    await flushPromises();
    await wrapper.find(".list-detail").trigger("click");
    await flushPromises();
    expect(wrapper.findComponent({ name: "RunnerStateSnapshotDetail" }).props("detail")).not.toBeNull();
    await wrapper.find(".close-detail").trigger("click");
    expect(wrapper.findComponent({ name: "RunnerStateSnapshotDetail" }).props("detail")).toBeNull();
  });
});
