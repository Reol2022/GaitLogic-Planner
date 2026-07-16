import type { RunnerStateSnapshot } from "@/types/runnerState";

export interface RunnerStateSummaryCopy {
  title: string;
  body: string;
  tone: "neutral" | "positive" | "notice" | "attention";
}

export function buildRunnerStateSummary(snapshot: RunnerStateSnapshot): RunnerStateSummaryCopy {
  const volume = snapshot.volume_trend?.state ?? "UNKNOWN";
  const consistency = snapshot.training_consistency?.state ?? snapshot.inferred_state.training_consistency;
  const fatigue = snapshot.fatigue?.state ?? snapshot.inferred_state.fatigue_state;

  if (volume === "UNKNOWN" || consistency === "UNKNOWN" || fatigue === "UNKNOWN") {
    return {
      title: "当前数据不足，暂无法完整判断",
      body: "已展示当前可用指标。继续记录训练、RPE 和计划完成情况后，系统会基于更多证据更新状态。",
      tone: "neutral",
    };
  }

  if (fatigue === "HIGH" || volume === "SPIKING") {
    return {
      title: "近期训练压力有所增加",
      body: "近 7 天跑量或多项训练压力信号出现明显变化。建议结合体感检查恢复情况，并复核后续训练安排。",
      tone: "attention",
    };
  }

  if (fatigue === "ELEVATED" || volume === "INCREASING" || consistency === "LOW") {
    return {
      title: "近期训练状态出现一些变化",
      body: "当前跑量、训练执行或压力信号有所变化。建议结合近期体感和计划执行情况进行复核。",
      tone: "notice",
    };
  }

  return {
    title: "近期训练整体较稳定",
    body: "近 7 天跑量与此前基线接近，训练执行保持稳定。目前未发现明显训练压力信号。",
    tone: "positive",
  };
}
