<template>
  <div class="page-stack data-sync-page">
    <PageHeader title="数据同步" subtitle="连接运动平台，统一同步跑步活动并写入训练闭环。" />

    <section class="sync-summary" v-if="summary">
      <div>
        <strong>{{ summary.connected_count }}</strong>
        <span>已连接数据源</span>
      </div>
      <div>
        <strong>{{ summary.needs_review_count }}</strong>
        <span>待确认活动</span>
      </div>
      <div>
        <strong>{{ summary.failed_job_count }}</strong>
        <span>近 7 天异常任务</span>
      </div>
    </section>

    <section class="provider-grid" v-loading="loading">
      <article
        v-for="provider in providers"
        :key="provider.key"
        class="provider-card"
        :class="{ 'is-disabled': provider.status !== 'available' }"
        role="button"
        tabindex="0"
        @click="openProvider(provider.key)"
        @keydown.enter.prevent="openProvider(provider.key)"
      >
        <div class="provider-icon">
          <el-icon><Connection /></el-icon>
        </div>
        <div class="provider-main">
          <div class="provider-title">
            <strong>{{ provider.display_name }}</strong>
            <el-tag size="small" :type="providerTagType(provider.status)">
              {{ statusLabel(provider.status) }}
            </el-tag>
          </div>
          <p>{{ provider.notes || "该平台暂未提供说明。" }}</p>
          <div class="provider-meta">
            <span>{{ connectionText(provider.key) }}</span>
            <span>{{ provider.supported_sync_modes.length }} 种同步模式</span>
          </div>
          <div v-if="connectionMap.get(provider.key)" class="provider-switches" @click.stop>
            <el-switch
              :model-value="connectionMap.get(provider.key)?.auto_import_enabled"
              size="small"
              inline-prompt
              active-text="导入"
              inactive-text="仅同步"
              @change="(value) => savePreference(provider.key, 'auto_import_enabled', Boolean(value))"
            />
            <el-switch
              :model-value="connectionMap.get(provider.key)?.auto_sync_enabled"
              size="small"
              inline-prompt
              active-text="自动"
              inactive-text="手动"
              @change="(value) => savePreference(provider.key, 'auto_sync_enabled', Boolean(value))"
            />
          </div>
        </div>
        <el-icon class="provider-arrow"><ArrowRight /></el-icon>
      </article>
    </section>

    <el-empty v-if="!loading && providers.length === 0" description="暂无可用同步平台" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { ArrowRight, Connection } from "@element-plus/icons-vue";
import {
  getDataSyncSummary,
  listDataSyncConnections,
  listDataSyncProviders,
  updateDataSyncPreferences,
} from "@/api/dataSync";
import type { DataSyncConnectionRead, DataSyncSummary, ProviderDescriptor } from "@/types/models";
import { statusLabel } from "@/utils/statusLabels";

const router = useRouter();
const loading = ref(false);
const providers = ref<ProviderDescriptor[]>([]);
const connections = ref<DataSyncConnectionRead[]>([]);
const summary = ref<DataSyncSummary | null>(null);

const connectionMap = computed(() => new Map(connections.value.map((item) => [item.provider, item])));

function connectionText(providerKey: string) {
  const connection = connectionMap.value.get(providerKey);
  if (!connection) return "尚未连接";
  if (connection.connected) return `已连接 ${connection.masked_account_identifier || ""}`.trim();
  return statusLabel(connection.status);
}

function providerTagType(status: string) {
  if (status === "available") return "success";
  if (status === "disabled_in_production") return "info";
  return "warning";
}

function openProvider(providerKey: string) {
  const provider = providers.value.find((item) => item.key === providerKey);
  if (provider?.status !== "available") return;
  if (providerKey === "garmin") {
    router.push("/data-sync/garmin");
  }
}

async function savePreference(
  providerKey: string,
  key: "auto_import_enabled" | "auto_sync_enabled",
  value: boolean,
) {
  const updated = await updateDataSyncPreferences(providerKey, { [key]: value });
  const index = connections.value.findIndex((item) => item.provider === providerKey);
  if (index >= 0) connections.value[index] = updated;
  ElMessage.success("同步偏好已更新");
  summary.value = await getDataSyncSummary(true);
}

async function load() {
  loading.value = true;
  try {
    const [providerResponse, connectionRows, summaryResponse] = await Promise.all([
      listDataSyncProviders(),
      listDataSyncConnections(),
      getDataSyncSummary(true),
    ]);
    providers.value = providerResponse.providers;
    connections.value = connectionRows;
    summary.value = summaryResponse;
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<style scoped>
.data-sync-page {
  gap: 14px;
}

.provider-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.sync-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.sync-summary > div {
  display: grid;
  gap: 2px;
  padding: 14px 16px;
  border: 1px solid var(--card-border);
  border-radius: var(--card-radius);
  background: #ffffff;
  box-shadow: var(--card-shadow);
}

.sync-summary strong {
  color: #172033;
  font-size: 24px;
}

.sync-summary span {
  color: #667085;
  font-size: 13px;
}

.provider-card {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 14px;
  min-width: 0;
  padding: 16px;
  border: 1px solid var(--card-border);
  border-radius: var(--card-radius);
  background: #fff;
  color: inherit;
  text-align: left;
  box-shadow: var(--card-shadow);
  cursor: pointer;
}

.provider-card.is-disabled {
  cursor: not-allowed;
  opacity: 0.72;
}

.provider-icon {
  display: grid;
  place-items: center;
  width: 42px;
  height: 42px;
  border-radius: 8px;
  background: #edf5ff;
  color: #1976d2;
  font-size: 22px;
}

.provider-main {
  min-width: 0;
}

.provider-title,
.provider-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.provider-title strong {
  color: #172033;
  font-size: 16px;
}

.provider-main p {
  margin: 8px 0;
  color: #667085;
  font-size: 13px;
  line-height: 1.5;
}

.provider-meta {
  flex-wrap: wrap;
  color: #475467;
  font-size: 12px;
}

.provider-switches {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.provider-arrow {
  color: #98a2b3;
}

@media (max-width: 768px) {
  .provider-grid {
    grid-template-columns: 1fr;
  }

  .sync-summary {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .sync-summary > div {
    padding: 12px 10px;
  }

  .provider-card {
    grid-template-columns: auto minmax(0, 1fr);
  }

  .provider-arrow {
    display: none;
  }
}
</style>
