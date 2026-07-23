import { describe, expect, it } from "vitest";
import { createCoachResponse } from "@/test/coachAgentFixture";
import {
  appendCoachTurn,
  buildCoachConversationContext,
  MAX_COACH_TURNS,
  type CoachConversationTurn,
} from "./coachAgentConversation";

function turn(index: number, size = 10): CoachConversationTurn {
  return {
    id: `turn-${index}`,
    question: `Q${index}-${"x".repeat(size)}`,
    response: createCoachResponse({ request_id: `turn-${index}`, summary: `A${index}-${"y".repeat(size)}` }),
  };
}

describe("coach in-memory conversation", () => {
  it("keeps at most eight turns and drops the oldest", () => {
    let turns: CoachConversationTurn[] = [];
    let trimmed = false;
    for (let index = 0; index < 10; index += 1) {
      const result = appendCoachTurn(turns, turn(index));
      turns = result.turns;
      trimmed ||= result.trimmed;
    }
    expect(turns).toHaveLength(MAX_COACH_TURNS);
    expect(turns[0].id).toBe("turn-2");
    expect(trimmed).toBe(true);
  });

  it("sends only bounded public user and assistant summaries", () => {
    const result = buildCoachConversationContext(Array.from({ length: 8 }, (_, index) => turn(index, 1000)));
    expect(result.trimmed).toBe(true);
    expect(result.messages.reduce((sum, item) => sum + item.content.length, 0)).toBeLessThanOrEqual(6000);
    expect(result.messages.every((item) => ["user", "assistant"].includes(item.role))).toBe(true);
    expect(JSON.stringify(result.messages)).not.toContain("tool_calls");
    expect(JSON.stringify(result.messages)).not.toContain("trace_id");
  });
});
