import { describe, expect, it } from "vitest";
import {
  coachDecisionDisplay,
  coachIntentDisplay,
  coachPlannedStatusDisplay,
  coachProviderStatusDisplay,
  coachRiskDisplay,
  coachStatusDisplay,
  coachToolName,
  coachToolStatusDisplay,
} from "./coachAgentDisplay";

describe("coach display mappings", () => {
  it("covers every fixed backend enum", () => {
    expect(Object.keys(coachIntentDisplay)).toEqual([
      "TODAY_RECOMMENDATION", "EXPLAIN_RUNNER_STATE", "GENERAL_TRAINING_QUESTION",
    ]);
    expect(Object.keys(coachStatusDisplay)).toEqual([
      "SUCCEEDED", "DEGRADED", "VALIDATION_FAILED", "REJECTED", "UNAVAILABLE",
    ]);
    expect(Object.keys(coachRiskDisplay)).toEqual(["LOW", "MODERATE", "HIGH", "UNKNOWN"]);
    expect(Object.keys(coachDecisionDisplay)).toEqual([
      "PROCEED", "PROCEED_WITH_CAUTION", "CONSIDER_ADJUSTMENT", "REST_OR_RECOVERY", "UNKNOWN",
    ]);
    expect(Object.keys(coachPlannedStatusDisplay)).toEqual([
      "PLANNED", "REST_DAY", "NO_PLAN", "CYCLE_NOT_ACTIVE", "UNKNOWN",
    ]);
    expect(Object.keys(coachProviderStatusDisplay)).toEqual([
      "SUCCEEDED", "DISABLED", "UNCONFIGURED", "FAILED", "NOT_CALLED",
    ]);
    expect(Object.keys(coachToolStatusDisplay)).toEqual([
      "SUCCEEDED", "FAILED", "NOT_FOUND", "NOT_ALLOWED", "INVALID_ARGUMENTS",
    ]);
  });

  it("keeps NO_PLAN separate from REST_DAY and uses safe decision labels", () => {
    expect(coachPlannedStatusDisplay.NO_PLAN).toBe("今日没有训练计划");
    expect(coachPlannedStatusDisplay.REST_DAY).toBe("今日为计划休息日");
    expect(coachDecisionDisplay.PROCEED.label).not.toContain("绝对安全");
    expect(coachDecisionDisplay.CONSIDER_ADJUSTMENT.label).not.toContain("已调整");
  });

  it("maps all nine known tools and safely hides unknown raw names", () => {
    const expected = {
      get_runner_state: "当前跑者状态",
      get_runner_state_history: "状态历史",
      get_recent_training: "近期训练",
      get_today_workout: "今日计划",
      get_current_training_cycle: "当前训练周期",
      get_training_rules: "训练规则",
      evaluate_today_workout: "今日训练评估",
      get_training_data_quality: "训练数据质量",
      retrieve_training_knowledge: "训练知识库",
    };
    for (const [name, label] of Object.entries(expected)) expect(coachToolName(name)).toBe(label);
    expect(coachToolName("private_internal_tool")).toBe("其他安全数据来源");
  });
});
