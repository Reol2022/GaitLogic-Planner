import { describe, expect, it } from "vitest";
import {
  coachRagDemoFixtures,
  createCoachRagDemoResponse,
  getCoachRagDemoScenario,
} from "./coachRagDemo";

describe("coach RAG demo fixtures", () => {
  it("provides four fully fictional public scenarios", () => {
    expect(Object.keys(coachRagDemoFixtures)).toEqual([
      "general",
      "explain",
      "today",
      "degraded",
    ]);
    const serialized = JSON.stringify(coachRagDemoFixtures);
    for (const privateMarker of [
      "api_key",
      "access_token",
      "user_id",
      "email",
      "phone",
      "gps",
      "index_id",
      "trace_events",
    ]) {
      expect(serialized.toLowerCase()).not.toContain(privateMarker);
    }
  });

  it("selects only allowlisted scenarios from the query string", () => {
    expect(getCoachRagDemoScenario("?demo=general")).toBe("general");
    expect(getCoachRagDemoScenario("?demo=degraded")).toBe("degraded");
    expect(getCoachRagDemoScenario("?demo=provider")).toBeNull();
    expect(getCoachRagDemoScenario("?message=private")).toBeNull();
  });

  it("returns an isolated response copy", () => {
    const first = createCoachRagDemoResponse("today");
    const second = createCoachRagDemoResponse("today");
    expect(first).toEqual(second);
    expect(first).not.toBe(second);
    expect(first.knowledge_references).not.toBe(second.knowledge_references);
  });

  it("keeps TODAY authority and degraded references safe", () => {
    expect(coachRagDemoFixtures.today.today_recommendation).toMatchObject({
      decision: "PROCEED_WITH_CAUTION",
      planned_workout_status: "PLANNED",
    });
    expect(coachRagDemoFixtures.today.risk_level).toBe("MODERATE");
    expect(coachRagDemoFixtures.today.knowledge_references).toHaveLength(2);
    expect(coachRagDemoFixtures.degraded.status).toBe("DEGRADED");
    expect(coachRagDemoFixtures.degraded.knowledge_references).toEqual([]);
  });
});
