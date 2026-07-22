import { describe, expect, it } from "vitest";
import type { ExternalSyncJobRead, RunnerStateSnapshotSyncStatus } from "@/types/models";
import {
  MAX_RUNNER_STATE_RECEIPT_POLLS,
  shouldContinueGarminPolling,
} from "./garminSyncStatus";

function job(
  status: string,
  snapshotStatus?: RunnerStateSnapshotSyncStatus,
): ExternalSyncJobRead {
  return {
    id: 1,
    sync_run_id: "00000000-0000-4000-8000-000000000001",
    provider: "garmin",
    sync_mode: "recent_7d",
    status,
    fetched_count: 0,
    created_count: 0,
    updated_count: 0,
    duplicate_count: 0,
    matched_count: 0,
    unplanned_count: 0,
    needs_review_count: 0,
    ignored_count: 0,
    failed_count: 0,
    created_at: "2026-07-22T10:00:00+08:00",
    updated_at: "2026-07-22T10:00:00+08:00",
    runner_state_snapshot: snapshotStatus ? {
      status: snapshotStatus,
      snapshot_id: null,
      error_code: null,
    } : undefined,
  };
}

describe("Garmin sync polling", () => {
  it("continues for queued and running jobs", () => {
    expect(shouldContinueGarminPolling([job("queued")], 0)).toBe(true);
    expect(shouldContinueGarminPolling([job("running")], 0)).toBe(true);
  });

  it("briefly continues after the job finishes while the receipt is processing", () => {
    const rows = [job("succeeded", "PROCESSING")];

    expect(shouldContinueGarminPolling(rows, 0)).toBe(true);
    expect(shouldContinueGarminPolling(rows, MAX_RUNNER_STATE_RECEIPT_POLLS)).toBe(false);
  });

  it("stops for terminal receipts and old responses without the optional field", () => {
    expect(shouldContinueGarminPolling([job("succeeded", "CREATED")], 0)).toBe(false);
    expect(shouldContinueGarminPolling([job("succeeded")], 0)).toBe(false);
  });
});
