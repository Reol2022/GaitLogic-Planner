import type { ExternalSyncJobRead } from "@/types/models";

export const MAX_RUNNER_STATE_RECEIPT_POLLS = 8;

export function hasActiveSyncJobs(jobs: ExternalSyncJobRead[]): boolean {
  return jobs.some((job) => job.status === "queued" || job.status === "running");
}

export function hasProcessingRunnerStateReceipt(jobs: ExternalSyncJobRead[]): boolean {
  return jobs.some((job) => job.runner_state_snapshot?.status === "PROCESSING");
}

export function shouldContinueGarminPolling(
  jobs: ExternalSyncJobRead[],
  receiptPollCount: number,
): boolean {
  return (
    hasActiveSyncJobs(jobs)
    || (
      hasProcessingRunnerStateReceipt(jobs)
      && receiptPollCount < MAX_RUNNER_STATE_RECEIPT_POLLS
    )
  );
}
