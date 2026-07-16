<template>
  <el-collapse class="evidence-collapse">
    <el-collapse-item name="evidence">
      <template #title>
        <span class="evidence-trigger"><DocumentChecked /> 查看判断依据</span>
      </template>

      <div class="evidence-content">
        <div v-if="evidence.length" class="evidence-list">
          <article v-for="(item, index) in evidence" :key="`${item.metric}-${index}`" class="evidence-item">
            <div class="evidence-item__title">
              <strong>{{ evidenceMetricLabels[item.metric] || item.metric }}</strong>
              <el-tag size="small" :type="item.used ? 'primary' : 'info'">{{ item.used ? "已参与" : "未参与" }}</el-tag>
            </div>
            <dl>
              <div><dt>实际值</dt><dd>{{ displayEvidenceValue(item.value, item.unit) }}</dd></div>
              <div><dt>比较窗口</dt><dd>{{ windowLabels[item.window] || item.window }}</dd></div>
              <div><dt>阈值</dt><dd>{{ displayEvidenceValue(item.threshold, item.unit) }}</dd></div>
              <div><dt>单位</dt><dd>{{ item.unit || "无" }}</dd></div>
              <div><dt>数据来源</dt><dd>{{ item.source }}</dd></div>
            </dl>
          </article>
        </div>
        <el-empty v-else :image-size="56" description="当前没有可展示的判断依据" />

        <div v-if="skippedSignals.length" class="skipped-signals">
          <strong>未参与信号</strong>
          <div class="tag-row">
            <el-tag v-for="signal in skippedSignals" :key="signal" type="info">
              {{ signalLabels[signal] || signal }}
            </el-tag>
          </div>
          <p>这些信号因对应数据不足而未参与本次判断。</p>
        </div>

        <details v-if="reasonCodes.length" class="advanced-reasons">
          <summary>高级详情</summary>
          <ul>
            <li v-for="code in reasonCodes" :key="code">
              <span>{{ reasonCodeLabels[code] || "规则判断记录" }}</span>
              <code>{{ code }}</code>
            </li>
          </ul>
        </details>

        <div class="evidence-footer">
          <span v-if="evidenceCoverage !== null && evidenceCoverage !== undefined">
            证据覆盖程度：{{ formatPercent(evidenceCoverage) }}
          </span>
          <span>规则集版本：{{ rulesetVersion || "暂无数据" }}</span>
        </div>
      </div>
    </el-collapse-item>
  </el-collapse>
</template>

<script setup lang="ts">
import { DocumentChecked } from "@element-plus/icons-vue";
import type { RunnerStateEvidence } from "@/types/runnerState";
import { evidenceMetricLabels, reasonCodeLabels, signalLabels, windowLabels } from "@/utils/runnerStateDisplay";
import { EMPTY_VALUE, formatNumber, formatPercent } from "@/utils/runnerStateFormat";

withDefaults(defineProps<{
  evidence?: RunnerStateEvidence[];
  skippedSignals?: string[];
  reasonCodes?: string[];
  rulesetVersion?: string | null;
  evidenceCoverage?: number | null;
}>(), {
  evidence: () => [],
  skippedSignals: () => [],
  reasonCodes: () => [],
  rulesetVersion: null,
  evidenceCoverage: null,
});

function displayEvidenceValue(value: number | string | null | undefined, unit?: string | null) {
  if (value === null || value === undefined || value === "") return EMPTY_VALUE;
  const formatted = typeof value === "number" ? formatNumber(value, 4) : String(value);
  return unit ? `${formatted} ${unit}` : formatted;
}
</script>

<style scoped>
.evidence-collapse { margin-top: 12px; border-top: 1px solid var(--line-soft); border-bottom: 0; }
.evidence-trigger { display: inline-flex; align-items: center; gap: 7px; color: #1976d2; font-size: 13px; }
.evidence-trigger svg { width: 16px; }
.evidence-content { min-width: 0; padding: 2px 2px 8px; }
.evidence-list { display: grid; gap: 10px; }
.evidence-item { min-width: 0; padding: 12px; border: 1px solid var(--line-soft); border-radius: 6px; background: #fbfcfd; }
.evidence-item__title { display: flex; justify-content: space-between; gap: 10px; align-items: center; }
.evidence-item__title strong { overflow-wrap: anywhere; }
dl { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px 14px; margin: 12px 0 0; }
dl div { min-width: 0; }
dt { color: var(--muted); font-size: 11px; }
dd { margin: 3px 0 0; overflow-wrap: anywhere; color: #344054; font-size: 12px; }
.skipped-signals { margin-top: 14px; padding: 12px; border-left: 3px solid #8293a4; background: #f6f8fa; }
.skipped-signals p { margin: 8px 0 0; color: var(--muted); font-size: 12px; }
.tag-row { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.advanced-reasons { margin-top: 12px; color: var(--muted); font-size: 12px; }
.advanced-reasons summary { cursor: pointer; color: #475467; }
.advanced-reasons ul { display: grid; gap: 6px; padding-left: 18px; }
.advanced-reasons li { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 8px; }
.advanced-reasons code { overflow-wrap: anywhere; }
.evidence-footer { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 8px; margin-top: 14px; color: var(--muted); font-size: 12px; }

@media (max-width: 520px) {
  dl { grid-template-columns: 1fr; }
  .evidence-footer { flex-direction: column; }
}
</style>
