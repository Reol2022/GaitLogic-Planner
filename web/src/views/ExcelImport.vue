<template>
  <div class="page-stack">
    <section class="panel">
      <div class="panel-header">
        <h2 class="panel-title">下载标准模板</h2>
      </div>
      <div class="panel-body excel-import-card">
        <div>
          <div class="excel-import-title">请先下载系统提供的标准模板</div>
          <p class="excel-import-copy">按模板填写后再上传。系统只支持标准模板，不兼容自行改名或改表头的 Excel。</p>
        </div>
        <el-button type="primary" :icon="Download" :loading="downloading" @click="handleDownload">
          下载标准模板
        </el-button>
      </div>
    </section>

    <section class="panel">
      <div class="panel-header">
        <h2 class="panel-title">上传 Excel</h2>
      </div>
      <div class="panel-body">
        <el-upload
          class="excel-upload"
          drag
          accept=".xlsx"
          :auto-upload="false"
          :limit="1"
          :file-list="fileList"
          :on-change="handleFileChange"
          :on-remove="handleFileRemove"
        >
          <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
          <div class="el-upload__text">拖拽 .xlsx 到这里，或点击选择文件</div>
          <template #tip>
            <div class="el-upload__tip">只支持系统标准模板生成的 .xlsx 文件。</div>
          </template>
        </el-upload>

        <div class="upload-actions">
          <el-button type="primary" :icon="Upload" :loading="uploading" :disabled="!selectedFile" @click="handleUpload">
            上传并导入
          </el-button>
        </div>
      </div>
    </section>

    <section v-if="result" class="panel">
      <div class="panel-header">
        <h2 class="panel-title">导入结果</h2>
        <el-tag :type="resultTagType" effect="dark">{{ resultLabel }}</el-tag>
      </div>
      <div class="panel-body">
        <div class="metric-grid import-metrics">
          <div class="metric-card">
            <div class="metric-label">总行数</div>
            <div class="metric-value">{{ result.total_count }}</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">成功数</div>
            <div class="metric-value">{{ result.success_count }}</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">失败数</div>
            <div class="metric-value">{{ result.failed_count }}</div>
          </div>
        </div>

        <el-alert
          v-if="result.status !== 'failed'"
          title="导入完成后，可刷新训练计划页面查看数据。"
          type="success"
          show-icon
          :closable="false"
        />

        <el-table v-if="result.errors.length" :data="result.errors" border class="error-table">
          <el-table-column prop="sheet" label="Sheet" width="160" />
          <el-table-column prop="row" label="行号" width="100" />
          <el-table-column prop="message" label="错误原因" />
        </el-table>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import type { UploadFile, UploadUserFile } from "element-plus";
import { ElMessage } from "element-plus";
import { Download, Upload, UploadFilled } from "@element-plus/icons-vue";
import {
  downloadExcelTemplate,
  EXCEL_TEMPLATE_FILENAME,
  importExcelFile,
} from "@/api/excel";
import type { ExcelImportResult } from "@/types/models";

const downloading = ref(false);
const uploading = ref(false);
const fileList = ref<UploadUserFile[]>([]);
const selectedFile = ref<File | null>(null);
const result = ref<ExcelImportResult | null>(null);

const resultLabel = computed(() => {
  if (!result.value) return "";
  if (result.value.status === "success") return "成功";
  if (result.value.status === "partial_success") return "部分成功";
  return "失败";
});

const resultTagType = computed(() => {
  if (!result.value) return "info";
  if (result.value.status === "success") return "success";
  if (result.value.status === "partial_success") return "warning";
  return "danger";
});

async function handleDownload() {
  downloading.value = true;
  try {
    const blob = await downloadExcelTemplate();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = EXCEL_TEMPLATE_FILENAME;
    link.click();
    URL.revokeObjectURL(url);
  } finally {
    downloading.value = false;
  }
}

function handleFileChange(uploadFile: UploadFile, uploadFiles: UploadUserFile[]) {
  const raw = uploadFile.raw;
  if (!raw || !raw.name.toLowerCase().endsWith(".xlsx")) {
    ElMessage.error("只支持上传 .xlsx 文件");
    fileList.value = [];
    selectedFile.value = null;
    return;
  }
  fileList.value = uploadFiles.slice(-1);
  selectedFile.value = raw;
}

function handleFileRemove() {
  fileList.value = [];
  selectedFile.value = null;
}

async function handleUpload() {
  if (!selectedFile.value) {
    ElMessage.error("请先选择 .xlsx 文件");
    return;
  }
  uploading.value = true;
  try {
    result.value = await importExcelFile(selectedFile.value);
    if (result.value.status === "failed") {
      ElMessage.error(result.value.message);
    } else {
      ElMessage.success("导入完成，请刷新训练计划页面查看数据");
    }
  } finally {
    uploading.value = false;
  }
}
</script>
