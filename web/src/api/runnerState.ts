import request from "./request";
import type {
  RunnerStateCurrentResponse,
  RunnerStateSnapshotCreateResult,
  RunnerStateSnapshotDetail,
  RunnerStateSnapshotListResponse,
  RunnerStateTimelineRange,
  RunnerStateTimelineResponse,
} from "@/types/runnerState";

export function getCurrentRunnerState() {
  return request.get<RunnerStateCurrentResponse>("/runner-state/current", {
    skipErrorMessage: true,
  });
}

export function saveCurrentRunnerStateSnapshot() {
  return request.post<RunnerStateSnapshotCreateResult>("/runner-state/snapshots", {}, {
    skipErrorMessage: true,
  });
}

export function getRunnerStateTimeline(range: RunnerStateTimelineRange, signal?: AbortSignal) {
  return request.get<RunnerStateTimelineResponse>("/runner-state/snapshots/timeline", {
    params: { range },
    signal,
    skipErrorMessage: true,
  });
}

export function listRunnerStateSnapshots(params: {
  start_date: string;
  end_date: string;
  limit?: number;
  offset?: number;
}, signal?: AbortSignal) {
  return request.get<RunnerStateSnapshotListResponse>("/runner-state/snapshots", {
    params,
    signal,
    skipErrorMessage: true,
  });
}

export function getRunnerStateSnapshotDetail(snapshotId: number, signal?: AbortSignal) {
  return request.get<RunnerStateSnapshotDetail>(`/runner-state/snapshots/${snapshotId}`, {
    signal,
    skipErrorMessage: true,
  });
}
