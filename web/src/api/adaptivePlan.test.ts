import { beforeEach, describe, expect, it, vi } from "vitest";

const { post } = vi.hoisted(() => ({ post: vi.fn() }));

vi.mock("./request", () => ({
  default: {
    get: vi.fn(),
    post,
  },
}));

import { generateLangGraphWeeklyReview } from "./adaptivePlan";

describe("adaptive plan API", () => {
  beforeEach(() => {
    post.mockReset();
  });

  it("allows the two-stage Thinking workflow to exceed the global request timeout", () => {
    const payload = {
      week_start: "2026-08-10",
      week_end: "2026-08-16",
      timezone: "Asia/Shanghai",
    };

    generateLangGraphWeeklyReview(payload);

    expect(post).toHaveBeenCalledWith("/weekly-reviews/graph", payload, {
      timeout: 900000,
    });
  });
});
