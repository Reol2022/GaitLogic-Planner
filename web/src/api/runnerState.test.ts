import { beforeEach, describe, expect, it, vi } from "vitest";

const { get } = vi.hoisted(() => ({ get: vi.fn() }));

vi.mock("./request", () => ({
  default: { get },
}));

import { getCurrentRunnerState } from "./runnerState";

describe("runner state api", () => {
  beforeEach(() => get.mockReset());

  it("only requests the existing current-state GET endpoint", async () => {
    get.mockResolvedValue({ snapshot: {} });
    await getCurrentRunnerState();

    expect(get).toHaveBeenCalledTimes(1);
    expect(get).toHaveBeenCalledWith("/runner-state/current", { skipErrorMessage: true });
    expect(get.mock.calls.flat().join(" ")).not.toContain("snapshot/save");
  });
});
