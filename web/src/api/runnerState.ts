import request from "./request";
import type { RunnerStateCurrentResponse } from "@/types/runnerState";

export function getCurrentRunnerState() {
  return request.get<RunnerStateCurrentResponse>("/runner-state/current", {
    skipErrorMessage: true,
  });
}
