import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";
import CoachAnswerCard from "./CoachAnswerCard.vue";
import CoachSafetyNotices from "./CoachSafetyNotices.vue";
import CoachTodayRecommendationCard from "./CoachTodayRecommendationCard.vue";
import CoachToolSummary from "./CoachToolSummary.vue";
import type {
  CoachPlannedWorkoutStatus,
  CoachQueryStatus,
  CoachTodayDecision,
} from "@/types/coachAgent";

describe("CoachTodayRecommendationCard", () => {
  it.each([
    ["PROCEED", "可以按计划执行"],
    ["PROCEED_WITH_CAUTION", "建议谨慎执行"],
    ["CONSIDER_ADJUSTMENT", "建议考虑调整"],
    ["REST_OR_RECOVERY", "建议休息或恢复"],
    ["UNKNOWN", "当前数据不足，无法确定"],
  ] as Array<[CoachTodayDecision, string]>)
  ("renders %s without weakening the deterministic decision", (decision, label) => {
    const wrapper = mount(CoachTodayRecommendationCard, {
      props: {
        recommendation: {
          decision,
          planned_workout_status: "PLANNED",
          headline: "虚构的确定性建议",
          key_evidence: [],
          data_quality: "PARTIAL",
        },
        riskLevel: decision === "REST_OR_RECOVERY" ? "HIGH" : "LOW",
      },
    });
    expect(wrapper.text()).toContain(label);
    expect(wrapper.text()).toContain("暂无可展示的关键依据");
    if (decision === "REST_OR_RECOVERY") expect(wrapper.text()).toContain("需要重点关注");
  });

  it.each([
    ["PLANNED", "今日有训练计划"],
    ["REST_DAY", "今日为计划休息日"],
    ["NO_PLAN", "今日没有训练计划"],
    ["CYCLE_NOT_ACTIVE", "当前没有生效的训练周期"],
    ["UNKNOWN", "今日计划状态未知"],
  ] as Array<[CoachPlannedWorkoutStatus, string]>)
  ("keeps planned status %s distinct", (plannedStatus, label) => {
    const wrapper = mount(CoachTodayRecommendationCard, {
      props: {
        recommendation: {
          decision: "UNKNOWN",
          planned_workout_status: plannedStatus,
          headline: "虚构建议",
          key_evidence: ["FICTIONAL_RULE"],
          data_quality: "UNKNOWN",
        },
        riskLevel: "UNKNOWN",
      },
    });
    expect(wrapper.text()).toContain(label);
  });
});

describe("CoachAnswerCard", () => {
  it.each([
    ["SUCCEEDED", "安全正文"],
    ["DEGRADED", "模型解释暂不可用，当前内容由系统规则和已有训练数据生成"],
    ["VALIDATION_FAILED", "模型内容未通过安全校验"],
    ["REJECTED", "该教练能力暂未开放"],
    ["UNAVAILABLE", "当前无法安全生成建议"],
  ] as Array<[CoachQueryStatus, string]>)
  ("renders the safe %s state", (status, expected) => {
    const wrapper = mount(CoachAnswerCard, {
      props: {
        status,
        answer: "安全正文",
        summary: "安全摘要",
        generatedAt: "2026-07-23T09:00:00+08:00",
        providerStatus: status === "DEGRADED" ? "FAILED" : "SUCCEEDED",
      },
    });
    expect(wrapper.text()).toContain(expected);
    if (["VALIDATION_FAILED", "REJECTED", "UNAVAILABLE"].includes(status)) {
      expect(wrapper.text()).not.toContain("安全正文");
    }
    expect(wrapper.text()).not.toContain("Provider request ID");
    expect(wrapper.text()).not.toContain("Trace Events");
  });

  it("renders model-shaped HTML as text and never as executable markup", () => {
    const wrapper = mount(CoachAnswerCard, {
      props: {
        status: "SUCCEEDED",
        answer: '<img src=x onerror="alert(1)">',
        generatedAt: "2026-07-23T09:00:00+08:00",
        providerStatus: "SUCCEEDED",
      },
    });
    expect(wrapper.find("img").exists()).toBe(false);
    expect(wrapper.text()).toContain("<img src=x");
  });
});

describe("CoachSafetyNotices", () => {
  it("keeps HIGH warnings visible and labels model/context/data limitations", () => {
    const wrapper = mount(CoachSafetyNotices, {
      props: {
        riskLevel: "HIGH",
        warnings: [{ code: "HIGH_RISK_REVIEW_REQUIRED", message: "虚构高关注提醒" }],
        limitations: [
          { code: "MODEL_EXPLANATION_UNAVAILABLE", message: "模型降级" },
          { code: "CONTEXT_TRIMMED", message: "上下文裁剪" },
          { code: "DATA_LIMITED", message: "数据不足" },
        ],
      },
    });
    expect(wrapper.find("[role='alert']").exists()).toBe(true);
    expect(wrapper.text()).toContain("需要重点关注");
    expect(wrapper.text()).toContain("模型解释限制");
    expect(wrapper.text()).toContain("上下文已裁剪");
    expect(wrapper.text()).toContain("数据不足");
  });

  it("renders no empty cards", () => {
    expect(mount(CoachSafetyNotices).html()).toBe("<!--v-if-->");
  });

  it("translates legacy English and internal limitation messages", () => {
    const wrapper = mount(CoachSafetyNotices, {
      props: {
        limitations: [
          { code: "DATA_QUALITY_IS_COMPLETENESS", message: "Coverage describes available fields and is not a medical or model confidence score." },
          { code: "STRUCTURED_SEGMENTS_UNAVAILABLE", message: "The current plan stores workout content as text, so structured segments were not invented." },
          { code: "RUNNER_STATE_LIMITATION", message: "rpe_incomplete_7d" },
          { code: "RUNNER_STATE_LIMITATION", message: "training_phase_unavailable_no_structured_cycle_phase" },
        ],
      },
    });
    expect(wrapper.text()).toContain("数据完整度只表示当前字段的可用情况");
    expect(wrapper.text()).toContain("系统不会推测或虚构结构化训练分段");
    expect(wrapper.text()).toContain("近 7 天部分训练缺少主观用力程度");
    expect(wrapper.text()).toContain("暂时无法判断当前训练阶段");
    expect(wrapper.text()).not.toContain("Coverage describes");
    expect(wrapper.text()).not.toContain("rpe_incomplete_7d");
  });
});

describe("CoachToolSummary", () => {
  it("uses a keyboard-native collapsed summary with only safe fields", () => {
    const wrapper = mount(CoachToolSummary, {
      props: {
        tools: [
          { tool_name: "get_runner_state", status: "SUCCEEDED", safe_error_code: null },
          { tool_name: "evaluate_today_workout", status: "FAILED", safe_error_code: "AGENT_TOOL_EXECUTION_FAILED" },
        ],
      },
    });
    expect(wrapper.find("details").attributes("open")).toBeUndefined();
    expect(wrapper.text()).toContain("当前跑者状态");
    expect(wrapper.text()).toContain("今日训练评估");
    expect(wrapper.text()).toContain("AGENT_TOOL_EXECUTION_FAILED");
    expect(wrapper.text()).not.toContain("arguments");
    expect(wrapper.text()).not.toContain("user_id");
  });
});
