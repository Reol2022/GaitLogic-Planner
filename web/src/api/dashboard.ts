import request from "./request";
import type { BlockStats, DashboardSummary } from "@/types/models";

export function getDashboard(cycleId?: number | null) {
  return request.get<DashboardSummary>("/api/dashboard", {
    params: { cycle_id: cycleId || undefined },
  });
}

export function getBlockStats(blockId: number) {
  return request.get<BlockStats>(`/api/stats/blocks/${blockId}`);
}

