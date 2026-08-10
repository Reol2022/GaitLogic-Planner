import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import WeeklyFactsPanel from "./WeeklyFactsPanel.vue";
import type { WeeklyFacts } from "@/types/adaptivePlan";

const facts = {
  period: { week_start: "2026-07-06", week_end: "2026-07-12", timezone: "Asia/Shanghai" },
  planned: { planned_running_session_count: 4, planned_distance_km: 40, planned_key_session_count: 1, planned_high_intensity_session_count: 1 },
  completed: { completed_running_session_count: 3, actual_distance_km: 32, completed_key_session_count: 0, partial_session_count: 1, missed_session_count: 1, extra_session_count: 0 },
  adherence: { session_completion_rate: 0.75, distance_completion_rate: 0.8 },
  deviations: [{ deviation_type: "KEY_SESSION_MISSED", date: "2026-07-09", severity: "ATTENTION", evidence_codes: ["NO_COMPLETED_LOG"] }],
  runner_state_trend: { current_runner_state: "STABLE", fatigue_level: "ELEVATED" },
  data_quality: { level: "PARTIAL" },
  classification: { primary_status: "MIXED", rule_codes: [], evidence_codes: [], warnings: [], limitations: [] },
  result_hash: "f".repeat(64),
} satisfies WeeklyFacts;

describe("WeeklyFactsPanel", () => {
  it("distinguishes missing values, zero, partial, missed and extra sessions", () => {
    const wrapper = mount(WeeklyFactsPanel, { props: { facts } });
    expect(wrapper.text()).toContain("32.0 km");
    expect(wrapper.text()).toContain("部分完成1");
    expect(wrapper.text()).toContain("未完成1");
    expect(wrapper.text()).toContain("临时加练0");
    expect(wrapper.text()).toContain("KEY_SESSION_MISSED");
  });

  it("renders missing distance as unavailable rather than zero", () => {
    const missing = { ...facts, completed: { ...facts.completed, actual_distance_km: null } };
    expect(mount(WeeklyFactsPanel, { props: { facts: missing } }).text()).toContain("暂无数据");
  });
});
