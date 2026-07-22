import { describe, expect, it } from "vitest";
import { createRunnerStateTimeline, createRunnerStateTimelineItem } from "@/test/runnerStateFixture";
import { buildHistorySummary, buildRiskEvents } from "./runnerStateHistory";

describe("runner state history utilities", () => {
  it("builds a deterministic summary without a score or probability", () => {
    const result = buildHistorySummary(createRunnerStateTimeline());
    expect(result.recordLine).toContain("已记录 1 天");
    expect(result.latestLine).toContain("跑量稳定");
    expect(JSON.stringify(result)).not.toMatch(/评分|概率|准确率/);
  });

  it("returns a clear empty summary", () => {
    const result = buildHistorySummary(createRunnerStateTimeline([]));
    expect(result.recordLine).toContain("还没有保存记录");
  });

  it("sorts risk events newest first without merging repeated flags", () => {
    const flag = { code: "VOLUME_SPIKE", severity: "WARNING" as const, message: "虚构提示", suggested_action_type: "REVIEW" as const, triggered_rule: "fictional", evidence: [] };
    const events = buildRiskEvents([
      createRunnerStateTimelineItem({ id: 1, data_cutoff_date: "2026-07-10", risk_flags: [flag] }),
      createRunnerStateTimelineItem({ id: 2, data_cutoff_date: "2026-07-12", risk_flags: [flag] }),
    ]);
    expect(events.map((event) => event.snapshotId)).toEqual([2, 1]);
  });
});
