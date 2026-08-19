import { beforeEach, describe, expect, it, vi } from "vitest";

const { post } = vi.hoisted(() => ({ post: vi.fn() }));

vi.mock("./request", () => ({
  default: {
    get: vi.fn(),
    patch: vi.fn(),
    post,
  },
}));

import { generateWeeklyReview } from "./weeklyReviews";

describe("weekly reviews API", () => {
  beforeEach(() => {
    post.mockReset();
  });

  it("allows the two-stage Thinking workflow to exceed the global request timeout", () => {
    const payload = {
      cycle_id: 7,
      source_block_id: 11,
      target_block_id: 12,
      force_regenerate: false,
    };

    generateWeeklyReview(payload);

    expect(post).toHaveBeenCalledWith("/weekly-reviews/generate", payload, {
      timeout: 900000,
    });
  });
});
