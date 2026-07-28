import { describe, expect, it } from "vitest";
import { createCoachResponse } from "@/test/coachAgentFixture";
import { coachRagDemoFixtures } from "@/demo/coachRagDemo";
import { resolveCoachKnowledgeStatus } from "./coachKnowledgeDisplay";

describe("resolveCoachKnowledgeStatus", () => {
  it("derives USED from materialized public references", () => {
    expect(resolveCoachKnowledgeStatus(coachRagDemoFixtures.general)).toBe("USED");
  });

  it("derives EMPTY from a successful retrieval without references", () => {
    expect(resolveCoachKnowledgeStatus(createCoachResponse({
      knowledge_references: [],
      tool_calls: [{
        tool_name: "retrieve_training_knowledge",
        status: "SUCCEEDED",
        safe_error_code: null,
      }],
    }))).toBe("EMPTY");
  });

  it("derives UNAVAILABLE only from safe public signals", () => {
    expect(resolveCoachKnowledgeStatus(coachRagDemoFixtures.degraded)).toBe(
      "UNAVAILABLE",
    );
  });

  it("derives DISABLED from the explicit new contract and not old responses", () => {
    expect(resolveCoachKnowledgeStatus(createCoachResponse())).toBe("DISABLED");
    const oldResponse = createCoachResponse();
    delete oldResponse.knowledge_references;
    expect(resolveCoachKnowledgeStatus(oldResponse)).toBeNull();
  });
});
