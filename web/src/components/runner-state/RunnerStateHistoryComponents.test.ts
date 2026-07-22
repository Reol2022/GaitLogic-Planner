import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import RunnerStateDataQualityTrend from "./RunnerStateDataQualityTrend.vue";
import RunnerStateSnapshotDetail from "./RunnerStateSnapshotDetail.vue";
import RunnerStateTimeline from "./RunnerStateTimeline.vue";
import RunnerStateVolumeChart from "./RunnerStateVolumeChart.vue";
import { createRunnerStateSnapshotDetail, createRunnerStateTimelineItem } from "@/test/runnerStateFixture";

const { setOption, dispose, resize } = vi.hoisted(() => ({ setOption: vi.fn(), dispose: vi.fn(), resize: vi.fn() }));
vi.mock("echarts", () => ({ init: () => ({ setOption, dispose, resize }) }));

const commonStubs = {
  ElEmpty: { props: ["description"], template: "<div>{{ description }}</div>" },
  ElTag: { template: "<span><slot /></span>" },
};

describe("runner state history display components", () => {
  beforeEach(() => { setOption.mockReset(); dispose.mockReset(); resize.mockReset(); });

  it("keeps missing distance values null in the ECharts series and provides a table", async () => {
    const items = [createRunnerStateTimelineItem({ distance_7d_km: null, distance_28d_weekly_average_km: 40 })];
    const wrapper = mount(RunnerStateVolumeChart, { props: { items }, global: { stubs: commonStubs } });
    await wrapper.vm.$nextTick();
    expect(setOption).toHaveBeenCalled();
    const option = setOption.mock.calls[0][0];
    expect(option.series[0].data).toEqual([null]);
    expect(option.series[0].connectNulls).toBe(false);
    expect(wrapper.text()).toContain("暂无数据");
    expect(wrapper.find("table").exists()).toBe(true);
  });

  it("shows categorical states as tags rather than numeric curves", () => {
    const wrapper = mount(RunnerStateTimeline, { props: { items: [createRunnerStateTimelineItem()] }, global: { stubs: commonStubs } });
    expect(wrapper.text()).toContain("跑量：稳定");
    expect(wrapper.text()).toContain("执行：近期训练执行稳定");
    expect(wrapper.find("canvas").exists()).toBe(false);
  });

  it("uses the approved data-quality terminology and preserves missing values", () => {
    const wrapper = mount(RunnerStateDataQualityTrend, {
      props: { items: [createRunnerStateTimelineItem({ rpe_coverage_28d: null, heart_rate_coverage_28d: null })] },
      global: { stubs: commonStubs },
    });
    expect(wrapper.text()).toContain("数据完整度");
    expect(wrapper.text()).toContain("证据覆盖程度");
    expect(wrapper.text()).not.toContain("判断准确率");
    expect(wrapper.text()).toContain("暂无数据");
  });

  it("shows immutable-history notice and saved versions in detail", () => {
    const wrapper = mount(RunnerStateSnapshotDetail, {
      props: { visible: true, detail: createRunnerStateSnapshotDetail(), loading: false, error: "" },
      global: { stubs: {
        ElDrawer: { template: "<div><slot /></div>" },
        ElAlert: { props: ["title"], template: "<div>{{ title }}</div>" },
        ElSkeleton: true,
        ElResult: true,
        RunnerStateSnapshotContent: true,
      } },
    });
    expect(wrapper.text()).toContain("不会根据当前训练数据重新计算");
    expect(wrapper.text()).toContain("runner-state-rules-1.0.0");
    expect(wrapper.text()).toContain("runner-state-snapshot-1.0.0");
  });
});
