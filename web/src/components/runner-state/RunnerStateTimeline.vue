<template>
  <section class="history-card" aria-labelledby="state-timeline-title">
    <h2 id="state-timeline-title">状态时间线</h2>
    <p class="section-note">分类状态按日期展示，不转换成连续数值曲线。</p>
    <div v-if="items.length" class="timeline-list">
      <article v-for="(item, index) in items" :key="item.id" :class="{ changed: isChanged(index) }">
        <time>{{ formatDate(item.data_cutoff_date) }}</time>
        <div class="tag-line">
          <el-tag :type="tagType(volume(item))">跑量：{{ volume(item).label }}</el-tag>
          <el-tag :type="tagType(consistency(item))">执行：{{ consistency(item).label }}</el-tag>
          <el-tag :type="tagType(fatigue(item))">压力：{{ fatigue(item).label }}</el-tag>
        </div>
      </article>
    </div>
    <el-empty v-else :image-size="60" description="当前范围没有状态节点" />
  </section>
</template>

<script setup lang="ts">
import type { RunnerStateTimelineItem } from "@/types/runnerState";
import { consistencyDisplay, fatigueDisplay, volumeTrendDisplay, type StateDisplay } from "@/utils/runnerStateDisplay";
import { formatDate } from "@/utils/runnerStateFormat";

const props = defineProps<{ items: RunnerStateTimelineItem[] }>();
const volume = (item: RunnerStateTimelineItem) => volumeTrendDisplay[item.volume_trend ?? "UNKNOWN"];
const consistency = (item: RunnerStateTimelineItem) => consistencyDisplay[item.training_consistency ?? "UNKNOWN"];
const fatigue = (item: RunnerStateTimelineItem) => fatigueDisplay[item.fatigue_state ?? "UNKNOWN"];
function tagType(display: StateDisplay) { return display.tone === "positive" ? "success" : display.tone === "attention" ? "danger" : display.tone === "notice" ? "warning" : "info"; }
function isChanged(index: number) {
  if (index === 0) return true;
  const current = props.items[index];
  const previous = props.items[index - 1];
  return current.volume_trend !== previous.volume_trend || current.training_consistency !== previous.training_consistency || current.fatigue_state !== previous.fatigue_state;
}
</script>

<style scoped>
.history-card { padding: 18px; border: 1px solid var(--card-border); border-radius: var(--card-radius); background: #fff; box-shadow: var(--card-shadow); }
h2 { margin: 0; color: #172033; font-size: 18px; }.section-note { margin: 6px 0 16px; color: var(--muted); font-size: 12px; }
.timeline-list { position: relative; display: grid; gap: 8px; padding-left: 14px; border-left: 2px solid #dbe6ef; }
article { position: relative; display: grid; grid-template-columns: 100px 1fr; gap: 12px; padding: 10px 12px; border-radius: 8px; background: #fafbfc; }
article::before { position: absolute; left: -21px; top: 17px; width: 10px; height: 10px; border: 2px solid #fff; border-radius: 50%; background: #9aa9b8; content: ""; }
article.changed { background: #f5faff; } article.changed::before { background: #1976d2; box-shadow: 0 0 0 3px #dbeeff; }
time { color: #344054; font-weight: 700; }.tag-line { display: flex; flex-wrap: wrap; gap: 8px; min-width: 0; }
@media (max-width: 560px) { .history-card { padding: 14px; } article { grid-template-columns: 1fr; } }
</style>
