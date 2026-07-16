import { mount, shallowMount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import RunnerStateDataQuality from "./RunnerStateDataQuality.vue";
import RunnerStateEvidence from "./RunnerStateEvidence.vue";
import RunnerStateMetrics from "./RunnerStateMetrics.vue";
import RunnerStateRiskList from "./RunnerStateRiskList.vue";
import { createRunnerStateSnapshot } from "@/test/runnerStateFixture";

const elementStubs = {
  ElTag: { template: "<span><slot /></span>" },
  ElEmpty: { props: ["description"], template: "<span>{{ description }}</span>" },
  ElCollapse: { template: "<div><slot /></div>" },
  ElCollapseItem: { template: "<section><slot name='title' /><slot /></section>" },
  ElButton: { template: "<button><slot /></button>" },
  ElIcon: { template: "<i><slot /></i>" },
  Warning: true,
};

describe("runner state presentation components", () => {
  it("shows missing values and real zero correctly", () => {
    const snapshot = createRunnerStateSnapshot();
    snapshot.recent_training.distance_7d_km = null;
    snapshot.recent_training.average_rpe_7d = 0;
    const wrapper = mount(RunnerStateMetrics, { props: { snapshot } });
    expect(wrapper.text()).toContain("暂无数据");
    expect(wrapper.text()).toContain("平均 RPE0");
  });

  it("shows data quality by individual field", () => {
    const snapshot = createRunnerStateSnapshot();
    const wrapper = shallowMount(RunnerStateDataQuality, {
      props: { quality: snapshot.data_quality, inferenceLimitations: snapshot.inference_metadata?.limitations },
      global: { stubs: elementStubs },
    });
    expect(wrapper.text()).toContain("距离覆盖情况");
    expect(wrapper.text()).toContain("时长覆盖情况");
    expect(wrapper.text()).toContain("RPE 覆盖率");
    expect(wrapper.text()).toContain("心率覆盖率");
    expect(wrapper.text()).toContain("计划数据情况");
  });

  it("renders evidence, skipped signals and evidence coverage without calling it accuracy", () => {
    const snapshot = createRunnerStateSnapshot();
    const wrapper = shallowMount(RunnerStateEvidence, {
      props: {
        evidence: snapshot.volume_trend?.evidence,
        skippedSignals: ["RPE_CHANGE"],
        reasonCodes: ["INSUFFICIENT_RPE_COVERAGE"],
        evidenceCoverage: 0.8,
        rulesetVersion: "runner-state-rules-1.0.0",
      },
      global: { stubs: elementStubs },
    });
    expect(wrapper.text()).toContain("查看判断依据");
    expect(wrapper.text()).toContain("未参与信号");
    expect(wrapper.text()).toContain("RPE 相对基线变化");
    expect(wrapper.text()).toContain("证据覆盖程度：80%");
    expect(wrapper.text()).not.toContain("准确率");
    expect(wrapper.text()).not.toContain("置信概率");
  });

  it("hides an empty risk section", () => {
    const wrapper = shallowMount(RunnerStateRiskList, { props: { flags: [] }, global: { stubs: elementStubs } });
    expect(wrapper.text()).toBe("");
  });

  it("renders multiple risks in severity order", () => {
    const snapshot = createRunnerStateSnapshot();
    snapshot.risk_flags = [
      { code: "FREQUENT_HIGH_INTENSITY_SESSIONS", severity: "INFO", message: "信息提示", suggested_action_type: "REVIEW", triggered_rule: "a", evidence: [] },
      { code: "VOLUME_SPIKE", severity: "WARNING", message: "检查提示", suggested_action_type: "REVIEW_RECOVERY", triggered_rule: "b", evidence: [] },
      { code: "CONSECUTIVE_HIGH_INTENSITY_DAYS", severity: "ATTENTION", message: "关注提示", suggested_action_type: "ADD_RECOVERY", triggered_rule: "c", evidence: [] },
    ];
    const wrapper = shallowMount(RunnerStateRiskList, {
      props: { flags: snapshot.risk_flags },
      global: { mocks: { $router: { push: () => undefined } }, stubs: { ...elementStubs, RunnerStateEvidence: true } },
    });
    const text = wrapper.text();
    expect(text.indexOf("关注提示")).toBeLessThan(text.indexOf("检查提示"));
    expect(text.indexOf("检查提示")).toBeLessThan(text.indexOf("信息提示"));
    expect(text).not.toContain("自动修改");
  });
});
