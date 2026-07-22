import { shallowMount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import RunnerStateSnapshotSyncStatus from "./RunnerStateSnapshotSyncStatus.vue";
import type {
  RunnerStateSnapshotSyncResult,
  RunnerStateSnapshotSyncStatus as SnapshotStatus,
} from "@/types/models";

const expectedMessages: Record<SnapshotStatus, string> = {
  PROCESSING: "训练数据已同步，正在更新训练状态",
  CREATED: "训练状态历史已更新",
  DUPLICATE_PAYLOAD: "当前训练状态未发生变化，无需新增历史记录",
  SKIPPED_NO_MATERIAL_CHANGE: "本次同步未产生影响训练状态的新数据",
  SKIPPED_NOT_COMMITTED: "本次同步未提交训练数据，因此未更新训练状态",
  FAILED_NON_BLOCKING: "训练数据已同步，状态历史暂未更新",
};

function result(status: SnapshotStatus): RunnerStateSnapshotSyncResult {
  return {
    status,
    snapshot_id: status === "CREATED" ? 41 : null,
    error_code: status === "FAILED_NON_BLOCKING" ? "FICTIONAL_SAFE_CODE" : null,
  };
}

describe("RunnerStateSnapshotSyncStatus", () => {
  it.each(Object.entries(expectedMessages))("renders %s", (status, message) => {
    const wrapper = shallowMount(RunnerStateSnapshotSyncStatus, {
      props: { result: result(status as SnapshotStatus) },
      global: {
        stubs: { RouterLink: { props: ["to"], template: "<a><slot /></a>" } },
      },
    });

    expect(wrapper.text()).toContain(message);
  });

  it("offers the runner-state link only after a snapshot is created", () => {
    const created = shallowMount(RunnerStateSnapshotSyncStatus, {
      props: { result: result("CREATED") },
      global: {
        stubs: { RouterLink: { props: ["to"], template: "<a><slot /></a>" } },
      },
    });
    const failed = shallowMount(RunnerStateSnapshotSyncStatus, {
      props: { result: result("FAILED_NON_BLOCKING") },
      global: {
        stubs: { RouterLink: { props: ["to"], template: "<a><slot /></a>" } },
      },
    });

    expect(created.text()).toContain("查看训练状态");
    expect(failed.text()).not.toContain("查看训练状态");
    expect(failed.text()).not.toContain("同步失败");
  });

  it("renders nothing for an old response without a receipt", () => {
    const wrapper = shallowMount(RunnerStateSnapshotSyncStatus, {
      props: { result: null },
      global: { stubs: { RouterLink: true } },
    });

    expect(wrapper.text()).toBe("");
  });
});
