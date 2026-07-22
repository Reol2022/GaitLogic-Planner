import { beforeEach, describe, expect, it, vi } from "vitest";

const { get, post } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));

vi.mock("./request", () => ({
  default: { get, post },
}));

import {
  getCurrentRunnerState,
  getRunnerStateSnapshotDetail,
  getRunnerStateTimeline,
  listRunnerStateSnapshots,
  saveCurrentRunnerStateSnapshot,
} from "./runnerState";

describe("runner state api", () => {
  beforeEach(() => { get.mockReset(); post.mockReset(); });

  it("only requests the existing current-state GET endpoint", async () => {
    get.mockResolvedValue({ snapshot: {} });
    await getCurrentRunnerState();

    expect(get).toHaveBeenCalledTimes(1);
    expect(get).toHaveBeenCalledWith("/runner-state/current", { skipErrorMessage: true });
    expect(get.mock.calls.flat().join(" ")).not.toContain("snapshot/save");
  });

  it("uses only the designed snapshot endpoints and methods", async () => {
    const controller = new AbortController();
    get.mockResolvedValue({});
    post.mockResolvedValue({});
    await saveCurrentRunnerStateSnapshot();
    await getRunnerStateTimeline("12w", controller.signal);
    await listRunnerStateSnapshots({ start_date: "2026-04-27", end_date: "2026-07-19", limit: 30, offset: 0 }, controller.signal);
    await getRunnerStateSnapshotDetail(42, controller.signal);

    expect(post).toHaveBeenCalledWith("/runner-state/snapshots", {}, { skipErrorMessage: true });
    expect(get).toHaveBeenCalledWith("/runner-state/snapshots/timeline", expect.objectContaining({ params: { range: "12w" } }));
    expect(get).toHaveBeenCalledWith("/runner-state/snapshots", expect.objectContaining({ params: expect.objectContaining({ offset: 0 }) }));
    expect(get).toHaveBeenCalledWith("/runner-state/snapshots/42", expect.objectContaining({ signal: controller.signal }));
    expect([get, post].flatMap((mock) => mock.mock.calls).flat().join(" ")).not.toMatch(/PUT|PATCH|DELETE/);
  });
});
