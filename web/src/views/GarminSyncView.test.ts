import { flushPromises, shallowMount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createMemoryHistory, createRouter } from "vue-router";
import GarminSyncView from "./GarminSyncView.vue";
import {
  getGarminStatus,
  listGarminActivities,
  listGarminSyncJobs,
} from "@/api/garminSync";
import type { ExternalSyncJobRead, RunnerStateSnapshotSyncStatus } from "@/types/models";

vi.mock("@/api/garminSync", () => ({
  connectGarmin: vi.fn(),
  disconnectGarmin: vi.fn(),
  getGarminStatus: vi.fn(),
  listGarminActivities: vi.fn(),
  listGarminSyncJobs: vi.fn(),
  reconcileGarminActivities: vi.fn(),
  resolveGarminActivity: vi.fn(),
  retryGarminSyncJob: vi.fn(),
  startGarminSync: vi.fn(),
  updateGarminSyncSettings: vi.fn(),
}));

function job(snapshotStatus: RunnerStateSnapshotSyncStatus): ExternalSyncJobRead {
  return {
    id: 19,
    sync_run_id: "00000000-0000-4000-8000-000000000019",
    provider: "garmin",
    sync_mode: "recent_7d",
    status: "succeeded",
    fetched_count: 1,
    created_count: 1,
    updated_count: 0,
    duplicate_count: 0,
    matched_count: 1,
    unplanned_count: 0,
    needs_review_count: 0,
    ignored_count: 0,
    failed_count: 0,
    created_at: "2026-07-22T10:00:00+08:00",
    updated_at: "2026-07-22T10:00:01+08:00",
    runner_state_snapshot: {
      status: snapshotStatus,
      snapshot_id: snapshotStatus === "CREATED" ? 77 : null,
      error_code: null,
    },
  };
}

describe("GarminSyncView receipt polling", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.mocked(getGarminStatus).mockResolvedValue({
      connected: true,
      status: "connected",
      provider: "garmin",
      auto_import_enabled: true,
    });
    vi.mocked(listGarminActivities).mockResolvedValue([]);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("continues after a terminal job while the receipt processes, then stops", async () => {
    vi.mocked(listGarminSyncJobs)
      .mockResolvedValueOnce([job("PROCESSING")])
      .mockResolvedValueOnce([job("CREATED")]);
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: "/", component: { template: "<div />" } },
        { path: "/runner-state", component: { template: "<div />" } },
      ],
    });
    const wrapper = shallowMount(GarminSyncView, {
      global: {
        plugins: [router],
        stubs: {
          PageHeader: true,
          RouterLink: true,
          ElAlert: true,
          ElButton: true,
          ElCol: true,
          ElDatePicker: true,
          ElForm: true,
          ElFormItem: true,
          ElInput: true,
          ElOption: true,
          ElRow: true,
          ElSegmented: true,
          ElSelect: true,
          ElSwitch: true,
          ElTable: true,
          ElTableColumn: true,
          ElTag: true,
        },
      },
    });
    await flushPromises();
    expect(listGarminSyncJobs).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(2500);
    await flushPromises();
    expect(listGarminSyncJobs).toHaveBeenCalledTimes(2);

    await vi.advanceTimersByTimeAsync(20_000);
    await flushPromises();
    expect(listGarminSyncJobs).toHaveBeenCalledTimes(2);
    wrapper.unmount();
  });
});
