import { describe, expect, it } from "vitest";
import {
  consistencyDisplay,
  fatigueDisplay,
  sortRiskFlags,
  trainingPhaseDisplay,
  volumeTrendDisplay,
} from "./runnerStateDisplay";
import { formatDistance, formatPercent, formatRpe } from "./runnerStateFormat";
import { buildRunnerStateSummary } from "./runnerStateSummary";
import { createRunnerStateSnapshot } from "@/test/runnerStateFixture";

describe("runner state display mappings", () => {
  it.each([
    ["DECREASING", "下降"], ["STABLE", "稳定"], ["INCREASING", "增长"], ["SPIKING", "明显增长"], ["UNKNOWN", "暂无法判断"],
  ] as const)("maps volume state %s", (state, label) => expect(volumeTrendDisplay[state].label).toBe(label));

  it.each([
    ["LOW", "近期训练执行波动较大"], ["MODERATE", "近期训练执行较稳定"], ["HIGH", "近期训练执行稳定"], ["UNKNOWN", "暂无法判断"],
  ] as const)("maps consistency state %s", (state, label) => expect(consistencyDisplay[state].label).toBe(label));

  it.each([
    ["NORMAL", "暂未发现明显压力信号"], ["ELEVATED", "训练压力信号有所增加"], ["HIGH", "多项训练压力信号同时出现"], ["UNKNOWN", "数据不足，暂无法判断"],
  ] as const)("maps fatigue state %s", (state, label) => expect(fatigueDisplay[state].label).toBe(label));

  it("shows an unknown phase as not set", () => {
    expect(trainingPhaseDisplay.UNKNOWN.label).toBe("未设置");
  });

  it("uses the approved Chinese phase terminology", () => {
    expect(trainingPhaseDisplay.BUILD.label).toBe("建设期");
    expect(trainingPhaseDisplay.PEAK.label).toBe("峰值期");
  });

  it("sorts risks by attention, warning and info", () => {
    const risks = sortRiskFlags([
      { code: "INFO", severity: "INFO", message: "i", suggested_action_type: "REVIEW", triggered_rule: "i", evidence: [] },
      { code: "WARN", severity: "WARNING", message: "w", suggested_action_type: "REVIEW", triggered_rule: "w", evidence: [] },
      { code: "ATTN", severity: "ATTENTION", message: "a", suggested_action_type: "REVIEW", triggered_rule: "a", evidence: [] },
    ]);
    expect(risks.map((item) => item.severity)).toEqual(["ATTENTION", "WARNING", "INFO"]);
  });
});

describe("runner state presentation formatting and summary", () => {
  it("distinguishes missing values from real zero", () => {
    expect(formatDistance(null)).toBe("暂无数据");
    expect(formatDistance(0)).toBe("0 km");
    expect(formatPercent(0)).toBe("0%");
    expect(formatRpe(0)).toBe("0");
  });

  it("uses the stable deterministic summary", () => {
    expect(buildRunnerStateSummary(createRunnerStateSnapshot()).title).toBe("近期训练整体较稳定");
  });

  it("uses the pressure summary without recalculating a score", () => {
    const snapshot = createRunnerStateSnapshot();
    snapshot.fatigue!.state = "HIGH";
    snapshot.inferred_state.fatigue_state = "HIGH";
    expect(buildRunnerStateSummary(snapshot).title).toBe("近期训练压力有所增加");
  });

  it("explicitly reports insufficient data", () => {
    const snapshot = createRunnerStateSnapshot();
    snapshot.volume_trend!.state = "UNKNOWN";
    expect(buildRunnerStateSummary(snapshot).title).toContain("数据不足");
  });
});
