<template>
  <section class="quality-section" aria-labelledby="runner-quality-title">
    <div class="section-heading">
      <div>
        <span>数据质量</span>
        <h2 id="runner-quality-title">本次判断的数据基础</h2>
      </div>
      <el-tag :type="qualityTagType">{{ qualityLabel }}</el-tag>
    </div>

    <div class="quality-grid">
      <div><span>数据完整度</span><strong>{{ formatPercent(quality.confidence) }}</strong></div>
      <div><span>有效训练数量</span><strong>7 天 {{ quality.valid_workout_count_7d }} 次 / 28 天 {{ quality.valid_workout_count_28d }} 次</strong></div>
      <div><span>距离覆盖情况</span><strong>{{ availability("actual_distance_km") }}</strong></div>
      <div><span>时长覆盖情况</span><strong>{{ availability("actual_duration_seconds") }}</strong></div>
      <div><span>RPE 覆盖率</span><strong>7 天 {{ formatPercent(quality.rpe_coverage_7d) }} / 28 天 {{ formatPercent(quality.rpe_coverage_28d) }}</strong></div>
      <div><span>心率覆盖率</span><strong>7 天 {{ formatPercent(quality.heart_rate_coverage_7d) }} / 28 天 {{ formatPercent(quality.heart_rate_coverage_28d) }}</strong></div>
      <div><span>计划数据情况</span><strong>{{ availability("planned_workouts") }}</strong></div>
    </div>

    <div v-if="limitations.length" class="limitations">
      <strong>当前限制</strong>
      <ul>
        <li v-for="item in limitations" :key="item">{{ limitationLabel(item) }}</li>
      </ul>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { RunnerStateDataQuality } from "@/types/runnerState";
import { formatPercent } from "@/utils/runnerStateFormat";

const props = withDefaults(defineProps<{ quality: RunnerStateDataQuality; inferenceLimitations?: string[] }>(), {
  inferenceLimitations: () => [],
});

const qualityLabels = { NONE: "暂无数据", LOW: "数据较少", MEDIUM: "数据基本可用", HIGH: "数据较完整" } as const;
const qualityLabel = computed(() => qualityLabels[props.quality.data_quality_level]);
const qualityTagType = computed(() => props.quality.data_quality_level === "HIGH" ? "success" : props.quality.data_quality_level === "MEDIUM" ? "primary" : "info");
const limitations = computed(() => Array.from(new Set([...props.quality.limitations, ...props.inferenceLimitations])));

const limitationLabels: Record<string, string> = {
  intensity_distance_uses_main_workout_type: "强度距离按训练主类型统计",
  composite_workout_intensity_segments_not_split: "复合训练暂不能可靠拆分强度分段",
  high_intensity_composite_segments_use_main_workout_type: "复合训练的高强度判断使用主训练类型",
  training_phase_unavailable_no_structured_cycle_phase: "训练周期没有结构化阶段信息",
  recovery_day_fatigue_rule_disabled_v1: "本版本未启用无恢复日规则",
  near_zero_volume_baseline_cutoff_not_defined: "接近零的跑量基线边界尚未定义",
  days_since_last_quality_session_unavailable: "最近关键课日期暂无数据",
};

function availability(field: string) {
  return props.quality.available_fields.includes(field) ? "可用" : "暂无数据";
}

function limitationLabel(value: string) {
  if (limitationLabels[value]) return limitationLabels[value];
  if (value.startsWith("rpe_incomplete_")) return "部分训练缺少 RPE";
  if (value.startsWith("heart_rate_incomplete_")) return "部分训练缺少心率";
  if (value.startsWith("completion_rate_") && value.includes("no_planned_sessions")) return "当前窗口没有可用计划数据";
  return value;
}
</script>

<style scoped>
.quality-section { padding: 18px; border: 1px solid var(--card-border); border-radius: var(--card-radius); background: #fff; box-shadow: var(--card-shadow); }
.section-heading { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.section-heading span { color: #1976d2; font-size: 12px; font-weight: 700; }
.section-heading h2 { margin: 4px 0 0; font-size: 19px; }
.quality-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin-top: 16px; }
.quality-grid > div { min-width: 0; padding: 11px; border: 1px solid var(--line-soft); border-radius: 5px; background: #fbfcfd; }
.quality-grid span { display: block; color: var(--muted); font-size: 11px; }
.quality-grid strong { display: block; margin-top: 5px; overflow-wrap: anywhere; color: #344054; font-size: 13px; }
.limitations { margin-top: 14px; padding: 12px 14px; border-left: 3px solid #8293a4; background: #f6f8fa; }
.limitations strong { font-size: 13px; }
.limitations ul { display: grid; gap: 5px; margin: 8px 0 0; padding-left: 18px; color: var(--muted); font-size: 12px; }

@media (max-width: 900px) { .quality-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 520px) { .quality-grid { grid-template-columns: 1fr; } }
</style>
