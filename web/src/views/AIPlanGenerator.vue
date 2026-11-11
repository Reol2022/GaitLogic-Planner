<template>
  <div class="page-stack ai-plan-page">
    <Transition name="generation-mask">
      <div v-if="generating" class="generation-overlay" role="status" aria-live="polite">
        <div class="generation-panel">
          <div class="generation-spinner" />
          <div class="generation-copy">
            <h3>正在生成课表草稿</h3>
            <p>{{ generationStatusText }}</p>
          </div>
          <div class="generation-meta">
            <span>等待服务端返回</span>
            <span>本接口暂不返回逐阶段进度，请勿重复提交</span>
          </div>
        </div>
      </div>
    </Transition>

    <PageHeader title="AI 课表草稿生成器" subtitle="AI 生成内容仅作为训练计划草稿，请结合自身恢复、伤病和实际训练反馈调整。">
      <template #actions>
        <div class="quota-box">
          <span>{{ quota?.model_name || "deepseek-v4-flash" }}</span>
          <strong>今日剩余 {{ quota?.remaining_count ?? "-" }} 次</strong>
          <em>冷却 {{ quota?.cooldown_seconds ?? 60 }} 秒</em>
        </div>
      </template>
    </PageHeader>

    <section class="panel plan-context-panel" aria-label="自动获取训练基础">
      <div class="panel-head"><div><h3>自动获取训练基础</h3><p>读取系统中已有记录，不会重新请求 Garmin；数据不会自动覆盖你填写的表单。</p></div><el-button :loading="contextLoading" :disabled="generating" @click="loadRunnerContext">{{ planContext ? '重新获取' : '获取训练基础' }}</el-button></div>
      <template v-if="planContext">
        <div class="context-metrics">
          <div><span>近4周平均已记录跑量</span><strong>{{ trainingBasis?.recent_4w_avg_recorded_km ?? '未知' }} km/周</strong></div>
          <div><span>训练频率（按训练日）</span><strong>{{ trainingBasis?.training_days_per_week_28d ?? '未知' }} 天/周</strong></div>
          <div><span>最长单条活动</span><strong>{{ trainingBasis?.longest_recorded_activity?.distance_km ?? '未知' }} km</strong></div>
          <div><span>近28天已完成记录</span><strong>{{ trainingBasis?.recent_28d_record_count ?? '未知' }} 条</strong></div>
        </div>
        <p class="form-help">统计截至 {{ planContext.as_of_date }}（{{ planContext.timezone }}）；日志更新 {{ trainingBasis?.last_record_updated_at || '未知' }}；最近成功同步 {{ planContext.runner_facts.last_sync_at || '未知' }}；最近同步状态 {{ planContext.runner_facts.last_sync_status || '未知' }}。</p>
        <p v-for="item in planContext.runner_facts.performances || []" :key="item.distance+item.updated_at" class="form-help">已保存的用户自述成绩：{{ item.distance }} · {{ formatResult(item.result_seconds) }}（并非 Garmin 验证比赛成绩）</p>
        <p v-if="!planContext.runner_facts.performances?.length" class="form-help">暂无可用成绩；可以在表单中补充自述成绩。</p>
        <p v-if="!trainingBasis?.complete_for_recorded_data || trainingBasis?.recent_4w_avg_recorded_km === null" class="context-warning">训练基础部分缺失：未记录周不按零处理，待关联或缺失距离不用于完整跑量推断。</p>
        <p v-if="planContext.runner_facts.recovery?.missing_fields?.length" class="form-help">恢复缺口：{{ planContext.runner_facts.recovery.missing_fields.join('、') }}。缺少单项指标不等于无法制定计划。</p>
        <details><summary>查看来源与统计限制</summary><p v-for="text in trainingBasis?.limitations || []" :key="text" class="form-help">{{ text }}</p></details>
        <el-button :disabled="!Object.keys(acceptedMileage(planContext)).length || generating" @click="acceptContextMileage">确认采用跑量到表单</el-button>
      </template>
      <p v-else-if="contextError" class="context-warning">{{ contextError }}。仍可手动填写；关闭“结合已有训练数据”后可使用纯表单生成。</p>
      <el-checkbox v-model="form.use_training_context" :disabled="generating">生成时结合已有训练数据（重新读取，不用旧快照覆盖手动表单）</el-checkbox>
      <div v-if="assessment" class="context-assessment"><h4>生成前检查</h4><p v-for="issue in assessment.feasibility" :key="issue.code" :class="{'context-warning':issue.severity==='error'}">{{ issue.message }}</p></div>
    </section>

    <section class="ai-grid">
      <article class="panel ai-form-card">
        <div class="panel-head">
          <div>
            <h3>跑者与目标信息</h3>
            <p>硬约束优先；偏好只在约束允许时采用。输入和训练事实快照随本次任务保存。</p>
          </div>
        </div>

        <el-form label-position="top" class="ai-form">
          <div class="form-row">
            <el-form-item label="近期参考距离">
              <el-select v-model="form.recent_pb_distance" clearable style="width: 100%">
                <el-option
                  v-for="item in distanceOptions"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="近期参考成绩">
              <el-time-picker
                v-model="form.recent_pb_result"
                value-format="HH:mm:ss"
                format="HH:mm:ss"
                :default-value="new Date(2000, 0, 1, 0, 0, 0)"
                placeholder="例如 00:25:00"
                style="width: 100%"
              />
            </el-form-item>
          </div>

          <div class="form-row">
            <el-form-item label="当前周跑量 km">
              <el-input-number v-model="form.current_weekly_mileage_km" :min="0" :max="300" style="width: 100%" />
              <div class="form-help">请填写你最近能够稳定完成的周跑量，而不是历史最高周跑量。</div>
              <div class="form-help">{{ mileageSource(form.current_weekly_mileage_km,acceptedValues.current_weekly_mileage_km) }}</div>
            </el-form-item>
            <el-form-item label="最近 4 周平均跑量 km">
              <el-input-number v-model="form.recent_4w_avg_mileage_km" :min="0" :max="300" style="width: 100%" />
              <div class="form-help">{{ mileageSource(form.recent_4w_avg_mileage_km,acceptedValues.recent_4w_avg_mileage_km) }}</div>
            </el-form-item>
          </div>

          <div class="form-row">
            <el-form-item label="每周可训练天数">
              <el-input-number v-model="form.available_training_days_per_week" :min="1" :max="7" style="width: 100%" />
            </el-form-item>
            <el-form-item label="目标距离">
              <el-select v-model="form.target_distance" style="width: 100%">
                <el-option v-for="item in distanceOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </div>

          <div class="form-row">
            <el-form-item label="目标成绩">
              <el-time-picker
                v-model="form.target_result"
                value-format="HH:mm:ss"
                format="HH:mm:ss"
                :default-value="new Date(2000, 0, 1, 0, 0, 0)"
                placeholder="例如 02:00:00"
                style="width: 100%"
              />
              <div class="form-help">目标过于激进时，系统会保留目标，但会在计划中提示风险。</div>
            </el-form-item>
            <el-form-item label="目标赛事日期">
              <el-date-picker
                v-model="form.target_race_date"
                value-format="YYYY-MM-DD"
                :disabled-date="disableTargetRaceDate"
                style="width: 100%"
                @change="syncWeeksFromRace"
              />
            </el-form-item>
          </div>

          <el-form-item label="伤病说明">
            <el-input
              v-model="form.injury_notes"
              type="textarea"
              :rows="2"
              placeholder="例如：左小腿偶有紧张，无明显疼痛"
            />
            <div class="form-help">如有持续疼痛或明确伤病，请优先接受专业评估，AI 计划不替代医疗建议。</div>
          </el-form-item>

          <div class="form-row">
            <el-form-item label="计划开始日期">
              <el-date-picker
                v-model="form.plan_start_date"
                value-format="YYYY-MM-DD"
                :disabled-date="disablePlanStartDate"
                style="width: 100%"
                @change="syncWeeksFromRace"
              />
            </el-form-item>
            <el-form-item label="计划周数">
              <el-input-number v-model="form.plan_weeks" :min="1" :max="16" style="width: 100%" />
              <div class="form-help">每周从计划开始日起连续计算7天；最后一周可提前截止到比赛日。</div>
              <el-button v-if="form.target_race_date" link type="primary" :disabled="generating" @click="syncWeeksFromRace">按赛事匹配周数</el-button>
            </el-form-item>
          </div>

          <div class="date-summary" :class="{ invalid: Boolean(dateConstraintError) }">
            <div class="date-summary-main">
              <span class="label">计划结束日</span>
              <strong>{{ planEndDate || "未计算" }}</strong>
            </div>
            <div class="date-summary-meta">
              <span v-if="raceGapText">{{ raceGapText }}</span>
              <span v-if="dateConstraintError">{{ dateConstraintError }}</span>
            </div>
          </div>

          <el-collapse class="advanced-collapse">
            <el-collapse-item title="高级设置" name="advanced">
              <div class="form-row">
                <el-form-item label="跑者水平">
                  <el-select v-model="form.runner_level" style="width: 100%">
                    <el-option label="初级" value="beginner" />
                    <el-option label="进阶" value="intermediate" />
                    <el-option label="严肃跑者" value="advanced" />
                  </el-select>
                </el-form-item>
                <el-form-item label="强度风格">
                  <el-select v-model="form.intensity_style" style="width: 100%">
                    <el-option label="保守" value="conservative" />
                    <el-option label="标准" value="standard" />
                    <el-option label="积极" value="aggressive" />
                  </el-select>
                </el-form-item>
              </div>
              <div class="form-row">
                <el-form-item label="目标赛事名称">
                  <el-input v-model="form.target_race_name" placeholder="目标赛事名称" />
                </el-form-item>
                <el-form-item label="是否可以双跑">
                  <el-switch v-model="form.can_double_run" active-text="可以" inactive-text="不可以" />
                </el-form-item>
              </div>
              <el-form-item label="固定休息日">
                <el-select v-model="form.fixed_rest_days" multiple clearable style="width: 100%">
                  <el-option v-for="day in weekDays" :key="day" :label="day" :value="day" />
                </el-select>
              </el-form-item>
              <el-form-item label="每日可用时间（分钟，留空表示未限制；0表示不训练）"><div class="daily-time-grid"><label v-for="day in weekDays" :key="day">{{ day }}<el-input-number v-model="dailyMinutes[day]" :aria-label="`${day}可用分钟`" :min="0" :max="600" :controls="false" placeholder="不限" /></label></div></el-form-item>
              <el-form-item label="长距离偏好日（软偏好）"><el-select v-model="form.long_run_preferred_day" clearable><el-option v-for="day in weekDays" :key="day" :value="day" :label="day" /></el-select></el-form-item>
              <el-form-item label="不希望出现的课型（硬约束）"><el-select v-model="form.excluded_workout_types" multiple clearable><el-option v-for="type in ['REC','E','LSD','M','T1','T2','I','R','Mixed']" :key="type" :value="type" :label="type" /></el-select></el-form-item>
              <el-form-item label="训练偏好 / 训练哲学">
                <el-input
                  v-model="form.training_preferences"
                  type="textarea"
                  :rows="3"
                  placeholder="例如：偏丹尼尔斯体系；二四日关键课；不做激进双阈值；长距离希望保守推进"
                />
              </el-form-item>
              <el-form-item label="包含配速建议">
                <el-switch v-model="form.include_pace_guidance" />
              </el-form-item>
              <router-link class="preference-link" to="/ai-coach-preference">打开 AI 教练偏好配置</router-link>
            </el-collapse-item>
          </el-collapse>

          <el-alert v-if="generationError" class="generation-error" :title="generationError" type="error" :closable="false" show-icon role="alert" />
          <div class="form-actions">
            <el-button
              type="primary"
              :loading="generating"
              :disabled="generating || assessing || !quota?.can_generate || Boolean(dateConstraintError)"
              @click="generate"
            >
              生成草稿
            </el-button>
            <el-button :disabled="generating" @click="loadAll">刷新额度/草稿</el-button>
          </div>
        </el-form>
      </article>

      <article class="panel draft-card">
        <div class="panel-head">
          <div>
            <h3>草稿预览</h3>
            <p>确认后再应用为正式训练计划。</p>
          </div>
        </div>
        <template v-if="currentDraft">
          <div class="draft-summary-card">
            <h4>{{ currentDraft.title }}</h4>
            <p>{{ currentDraft.summary }}</p>
            <div class="draft-metrics">
              <span><b>目标</b>{{ currentDraft.target_race_name || currentDraft.goal || "-" }} {{ currentDraft.target_result || "" }}</span>
              <span><b>周期</b>{{ currentDraft.start_date || "-" }} 至 {{ currentDraft.end_date || "-" }}</span>
              <span><b>总周期</b>{{ groupedWorkouts.length }} 周</span>
              <span><b>第一周跑量</b>{{ firstWeekDistance }} km</span>
              <span><b>关键课</b>{{ firstWeekKeyWorkoutCount }} 次/首周</span>
              <span><b>风格</b>{{ intensityStyleLabel }}</span>
            </div>
            <el-alert
              v-if="currentDraft.risk_notes?.length"
              type="warning"
              :closable="false"
              :title="currentDraft.risk_notes.join('；')"
            />
          </div>
          <details v-if="currentDraft.plan_context" class="context-assessment"><summary>本次生成依据与约束</summary><p>生成时快照：{{ currentDraft.plan_context.as_of_date }}，不是最新恢复结论。</p><template v-if="currentDraft.plan_context.hard_constraints"><p>每周最多 {{ currentDraft.plan_context.hard_constraints.available_training_days_per_week }} 天；固定休息日：{{ currentDraft.plan_context.hard_constraints.fixed_rest_days.join('、') || '未指定' }}；双跑：{{ currentDraft.plan_context.hard_constraints.can_double_run ? '允许' : '不允许' }}。</p><p>每日时间上限：{{ JSON.stringify(currentDraft.plan_context.hard_constraints.daily_available_minutes) }} 分钟；禁用课型：{{ currentDraft.plan_context.hard_constraints.excluded_workout_types.join('、') || '未指定' }}。</p></template><p v-for="issue in currentDraft.plan_context.feasibility" :key="issue.code">{{ issue.message }}</p></details>
          <div class="draft-actions">
            <el-button type="primary" :disabled="currentDraft.status !== 'draft' || applying" :loading="applying" @click="apply(currentDraft.id)">
              保存并启用
            </el-button>
            <el-button :disabled="currentDraft.status !== 'draft' || applying" @click="apply(currentDraft.id,false)">仅保存，暂不启用</el-button>
            <el-button :disabled="generating" @click="currentDraft = null">返回修改</el-button>
            <el-button :disabled="generating" @click="generate">重新生成</el-button>
            <el-button :disabled="currentDraft.status !== 'draft'" @click="reject(currentDraft.id)">拒绝草稿</el-button>
            <el-dropdown trigger="click" @command="(format) => downloadCurrentDraft(String(format))">
              <el-button :icon="Download">导出</el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item v-for="item in exportOptions" :key="item.value" :command="item.value">
                    {{ item.label }}
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
          <p class="export-note">
            Garmin / 高驰参考 CSV 仅用于手动录入或二次转换，不会直连设备账号。
          </p>
          <div v-if="firstWeekGroup" class="week-block">
            <h4>第一周完整预览：{{ firstWeekGroup.name }}</h4>
            <el-table :data="firstWeekGroup.items" size="small">
              <el-table-column prop="workout_date" label="日期" width="110" />
              <el-table-column prop="weekday" label="星期" width="70" />
              <el-table-column prop="planned_content" label="训练内容" min-width="220" show-overflow-tooltip />
              <el-table-column prop="focus_note" label="训练目的 / 执行提示" min-width="220" show-overflow-tooltip />
              <el-table-column prop="planned_distance_km" label="km" width="70" />
              <el-table-column prop="main_type_raw" label="类型" width="80" />
              <el-table-column prop="target_pace_text" label="目标配速" width="130" show-overflow-tooltip />
            </el-table>
          </div>
          <el-collapse v-if="restWeekGroups.length">
            <el-collapse-item v-for="group in restWeekGroups" :key="group.name" :title="group.name" :name="group.name">
              <el-table :data="group.items" size="small">
                <el-table-column prop="workout_date" label="日期" width="110" />
                <el-table-column prop="planned_content" label="训练内容" min-width="260" show-overflow-tooltip />
                <el-table-column prop="planned_distance_km" label="km" width="70" />
                <el-table-column prop="main_type_raw" label="类型" width="80" />
              </el-table>
            </el-collapse-item>
          </el-collapse>
        </template>
        <el-empty v-else description="暂无草稿，先生成一份训练计划草稿" />
      </article>
    </section>

    <section class="panel">
      <div class="panel-head">
        <div>
          <h3>历史草稿</h3>
          <p>只显示当前账号生成的 AI 课表草稿。</p>
        </div>
      </div>
      <el-table :data="drafts" v-loading="loadingDrafts" class="history-table mobile-friendly-table">
        <el-table-column prop="title" label="标题" min-width="220" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">{{ statusLabel(row.status) }}</template>
        </el-table-column>
        <el-table-column label="创建时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" min-width="360" class-name="action-column history-action-column">
          <template #default="{ row }">
            <div class="table-actions history-actions">
              <el-button size="small" @click="viewDraft(row.id)">查看</el-button>
              <el-button size="small" type="primary" :disabled="row.status !== 'draft' || applying" @click="viewDraft(row.id)">预览与应用</el-button>
              <el-button size="small" :disabled="row.status !== 'draft'" @click="reject(row.id)">拒绝</el-button>
              <el-dropdown trigger="click" @command="(format) => downloadDraft(row, String(format))">
                <el-button size="small" :icon="Download">导出</el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item v-for="item in exportOptions" :key="item.value" :command="item.value">
                      {{ item.label }}
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { Download } from "@element-plus/icons-vue";

import {
  applyAIPlanDraft,
  exportAIPlanDraft,
  generateAIPlan,
  getAIPlanDraftDetail,
  getAIPlanDrafts,
  getAIPlanQuota,
  rejectAIPlanDraft,
  getAIPlanContext,
  assessAIPlanContext,
} from "@/api/aiPlan";
import { validateAiPlanDraft } from "@/api/ruleLoop";
import { trackUsageEvent } from "@/api/usageEvents";
import type { AIPlanDraft, AIPlanExportFormat, AIPlanGeneratePayload, AIPlanQuota, RaceDistance } from "@/types/models";
import { statusLabel } from "@/utils/statusLabels";
import {acceptedMileage,mileageSource} from '@/utils/planContext';
import {aiPlanCalendar} from '@/utils/aiPlanCalendar';
import type {PlanContext} from '@/types/planContext';

const router = useRouter();
const today = formatLocalDate(new Date());
const distanceOptions: Array<{ label: string; value: RaceDistance }> = [
  { label: "1500m", value: "1500m" },
  { label: "3000m", value: "3000m" },
  { label: "5000m", value: "5000m" },
  { label: "10000m", value: "10000m" },
  { label: "半马", value: "half_marathon" },
  { label: "全马", value: "marathon" },
];
const weekDays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];
const exportOptions: Array<{ label: string; value: AIPlanExportFormat; extension: string }> = [
  { label: "Excel 工作簿", value: "xlsx", extension: "xlsx" },
  { label: "CSV 表格", value: "csv", extension: "csv" },
  { label: "Markdown 文档", value: "markdown", extension: "md" },
  { label: "JSON 数据", value: "json", extension: "json" },
  { label: "日历 ICS", value: "ics", extension: "ics" },
  { label: "Garmin 参考 CSV", value: "garmin_csv", extension: "csv" },
  { label: "高驰参考 CSV", value: "coros_csv", extension: "csv" },
];

const form = reactive<AIPlanGeneratePayload>({
  runner_level: "intermediate",
  recent_pb_distance: null,
  recent_pb_result: null,
  current_weekly_mileage_km: 40,
  recent_4w_avg_mileage_km: 35,
  available_training_days_per_week: 5,
  can_double_run: false,
  fixed_rest_days: [],
  injury_notes: "",
  training_preferences: "",
  target_race_name: "",
  target_race_date: "",
  target_distance: "half_marathon",
  target_result: null,
  plan_start_date: today,
  plan_weeks: 8,
  intensity_style: "standard",
  include_pace_guidance: true,
  use_training_context:true,
  excluded_workout_types:[],
  long_run_preferred_day:null,
});
const dailyMinutes=reactive<Record<string,number|undefined>>({});
const planContext=ref<PlanContext|null>(null),assessment=ref<PlanContext|null>(null);
const contextLoading=ref(false),contextError=ref('');
const acceptedValues=ref<Record<string,number>>({});
const trainingBasis=computed(()=>planContext.value?.runner_facts.training);
function formatResult(seconds:number){return `${Math.floor(seconds/3600)}:${String(Math.floor(seconds/60)%60).padStart(2,'0')}:${String(seconds%60).padStart(2,'0')}`;}
async function loadRunnerContext(){
  contextLoading.value=true;contextError.value='';
  try{planContext.value=await getAIPlanContext();}catch{contextError.value='暂未获取训练基础，可重试';}finally{contextLoading.value=false;}
}
async function acceptContextMileage(){
  if(!planContext.value)return;
  const values=acceptedMileage(planContext.value);
  if(!Object.keys(values).length)return;
  try{await ElMessageBox.confirm('将覆盖表单中对应的跑量字段。每周训练天数、目标和其他约束不会改变，是否继续？','确认使用已记录跑量',{confirmButtonText:'采用统计值',cancelButtonText:'保留手动输入'});}catch{return;}
  Object.assign(form,values);acceptedValues.value=values;
}
function generationPayload():AIPlanGeneratePayload{const minutes:Record<string,number>={};for(const [day,value] of Object.entries(dailyMinutes))if(typeof value==='number')minutes[day]=value;return {...form,daily_available_minutes:minutes,recent_pb_distance:form.recent_pb_distance || null,recent_pb_result:form.recent_pb_result || null,injury_notes:form.injury_notes || null,training_preferences:form.training_preferences || null,target_race_name:form.target_race_name || null,target_race_date:form.target_race_date || null,target_result:form.target_result || null,long_run_preferred_day:form.long_run_preferred_day || null};}

const quota = ref<AIPlanQuota | null>(null);
const drafts = ref<AIPlanDraft[]>([]);
const currentDraft = ref<AIPlanDraft | null>(null);
const generating = ref(false);
const generationError = ref("");
const assessing=ref(false);
const applying = ref(false);
const loadingDrafts = ref(false);
let generationStartedAt = 0;

const groupedWorkouts = computed(() => {
  const map = new Map<string, NonNullable<AIPlanDraft["workouts"]>>();
  for (const workout of currentDraft.value?.workouts || []) {
    const key = workout.block_name || "训练块";
    const group = map.get(key) || [];
    group.push(workout);
    map.set(key, group);
  }
  return Array.from(map.entries()).map(([name, items]) => ({ name, items }));
});
const firstWeekGroup = computed(() => groupedWorkouts.value[0] || null);
const restWeekGroups = computed(() => groupedWorkouts.value.slice(1));
const firstWeekDistance = computed(() =>
  (firstWeekGroup.value?.items || []).reduce((sum, item) => sum + Number(item.planned_distance_km || 0), 0).toFixed(1),
);
const firstWeekKeyWorkoutCount = computed(() =>
  (firstWeekGroup.value?.items || []).filter((item) =>
    ["tempo", "interval_speed", "mixed"].includes(item.main_type_normalized),
  ).length,
);
const intensityStyleLabel = computed(() => {
  const labels = { conservative: "保守", standard: "标准", aggressive: "积极" };
  return labels[form.intensity_style] || form.intensity_style;
});

const calendar = computed(() => aiPlanCalendar(form.plan_start_date, form.plan_weeks, form.target_race_date));
const planEndDate = computed(() => calendar.value.endDate);
const raceGapText = computed(() => calendar.value.summary);
const dateConstraintError = computed(() => calendar.value.error);

const generationStatusText = computed(() => {
  return "训练基础与约束已准备，正在等待模型生成与服务端校验结果。";
});

function parseLocalDate(value: string) {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day);
}

function formatLocalDate(value: Date) {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function disableTargetRaceDate(value: Date) {
  if (!form.plan_start_date) return false;
  return value < parseLocalDate(form.plan_start_date);
}

function disablePlanStartDate(value: Date) {
  if (!form.target_race_date) return false;
  return value > parseLocalDate(form.target_race_date);
}

function syncWeeksFromRace() {
  if (!form.plan_start_date || !form.target_race_date) return;
  const recommended = calendar.value.recommendedWeeks;
  if (recommended) form.plan_weeks = recommended;
}

function formatDateTime(value: string) {
  return value ? value.replace("T", " ").slice(0, 16) : "";
}

async function loadQuota() {
  quota.value = await getAIPlanQuota();
}

async function loadDrafts() {
  loadingDrafts.value = true;
  try {
    drafts.value = await getAIPlanDrafts();
  } finally {
    loadingDrafts.value = false;
  }
}

async function loadAll() {
  await Promise.all([loadQuota(), loadDrafts()]);
}

async function generate() {
  if(generating.value || assessing.value)return;
  generationError.value = "";
  if (dateConstraintError.value) {
    ElMessage.warning(dateConstraintError.value);
    return;
  }
  const payload=generationPayload();
  assessing.value=true;
  try{
    assessment.value=await assessAIPlanContext(payload);
    if(assessment.value.feasibility.some(issue=>issue.severity==='error')){ElMessage.warning('约束存在冲突，请查看生成前检查。');return;}
    if(assessment.value.feasibility.length){try{await ElMessageBox.confirm(assessment.value.feasibility.map(issue=>issue.message).join('\n'),'确认训练基础与限制',{confirmButtonText:'了解限制，生成草稿',cancelButtonText:'返回修改',type:'warning'});}catch{return;}}
  }catch(error){generationError.value=getGenerateErrorMessage(error);ElMessage.error(generationError.value);return;}finally{assessing.value=false;}
  generating.value = true;
  generationStartedAt = Date.now();
  trackUsageEvent("ai_plan_generate_started");
  try {
    const result = await generateAIPlan(payload);
    currentDraft.value = await getAIPlanDraftDetail(result.draft_id);
    trackUsageEvent("ai_plan_generate_succeeded", { draft_id: result.draft_id });
    ElMessage.success("AI 课表草稿已生成");
    await loadAll();
  } catch (error) {
    const recovered = await recoverDraftAfterUncertainGeneration(error, generationStartedAt);
    if (recovered) {
      trackUsageEvent("ai_plan_generate_succeeded", { recovered: true });
      ElMessage.success("AI 课表草稿已生成，已自动刷新预览");
      return;
    }
    trackUsageEvent("ai_plan_generate_failed", { error_type: "request_failed" });
    generationError.value = getGenerateErrorMessage(error);
    ElMessage.error(generationError.value);
  } finally {
    window.setTimeout(() => {
      generating.value = false;
    }, 350);
  }
}

function isUncertainGenerationError(error: unknown) {
  const err = error as {
    code?: string;
    message?: string;
    response?: { status?: number };
  };
  const status = err?.response?.status || 0;
  return err?.code === "ECONNABORTED" || status >= 500;
}

function getGenerateErrorMessage(error: unknown) {
  const err = error as {
    code?: string;
    message?: string;
    response?: { status?: number; data?: { message?: string } };
  };
  if (isUncertainGenerationError(error)) {
    return "AI 生成请求耗时较长或模型服务暂时不可用。已刷新历史草稿，请稍后再查看或重新生成。";
  }
  return err?.response?.data?.message || err?.message || "AI 课表生成失败，请稍后重试。";
}

function sleep(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

async function recoverDraftAfterUncertainGeneration(error: unknown, startedAt: number) {
  if (!isUncertainGenerationError(error)) return false;
  const earliest = startedAt - 2 * 60 * 1000;
  for (let attempt = 0; attempt < 4; attempt += 1) {
    if (attempt > 0) await sleep(3500);
    try {
      await loadAll();
    } catch {
      continue;
    }
    const candidate = drafts.value.find((draft) => {
      const createdAt = new Date(draft.created_at).getTime();
      return Number.isFinite(createdAt) && createdAt >= earliest;
    });
    if (candidate) {
      currentDraft.value = await getAIPlanDraftDetail(candidate.id);
      return true;
    }
  }
  return false;
}

async function viewDraft(id: number) {
  currentDraft.value = await getAIPlanDraftDetail(id);
}

async function apply(id: number,activate=true) {
  if (applying.value) return;
  applying.value = true;
  try {
    const validation = await validateAiPlanDraft(id, true);
    if (validation.evaluation.final_action === "block_auto_apply") {
      ElMessage.error(validation.message || "规则校验已阻止自动应用，请先调整草稿。");
      return;
    }
    const needsConfirm = validation.evaluation.final_action === "require_user_review";
    if (needsConfirm) {
      await ElMessageBox.confirm(
        validation.message || "规则校验提示该计划需要二次确认。确认后仍可应用，但建议先检查关键课和恢复安排。",
        "应用前规则校验",
        { confirmButtonText: "确认应用", cancelButtonText: "返回检查", type: "warning" },
      );
    }
    await ElMessageBox.confirm(activate?'保存并启用新周期。已有启用周期时不会自动替换，请先结束原周期。':'保存为正式周期草稿，暂不启用。','确认计划应用',{confirmButtonText:activate?'保存并启用':'仅保存',cancelButtonText:'返回预览'});
    const result = await applyAIPlanDraft(id, needsConfirm,activate);
    if(activate && (!result.activated || result.cycle_status!=='active'))throw new Error('服务端未确认周期已启用，请检查计划状态。');
    trackUsageEvent("ai_plan_applied", { draft_id: id, cycle_id: result.cycle_id });
    ElMessage.success(result.message);
    await router.push({path:'/cycles',query:{cycle_id:String(result.cycle_id)}});
  } catch(error) {
    if(error!=='cancel' && error!=='close')ElMessage.error(getGenerateErrorMessage(error));
  } finally {
    applying.value = false;
  }
}

async function reject(id: number) {
  const result = await rejectAIPlanDraft(id);
  ElMessage.success(result.message);
  await loadAll();
  currentDraft.value = await getAIPlanDraftDetail(id);
}

async function downloadDraft(draft: AIPlanDraft, format: string) {
  const exportFormat = format as AIPlanExportFormat;
  const option = exportOptions.find((item) => item.value === exportFormat);
  const blob = await exportAIPlanDraft(draft.id, exportFormat);
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${safeFilename(draft.title || `ai-plan-${draft.id}`)}.${option?.extension || "txt"}`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

async function downloadCurrentDraft(format: string) {
  if (!currentDraft.value) return;
  await downloadDraft(currentDraft.value, format);
}

function safeFilename(value: string) {
  return value.replace(/[\\/:*?"<>|]/g, "-").replace(/\s+/g, "-").slice(0, 80) || "ai-plan-draft";
}

onMounted(()=>{void loadAll();void loadRunnerContext();});
</script>

<style scoped>
.context-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin:14px 0}.context-metrics span,.context-metrics strong{display:block}.context-metrics span{font-size:12px;color:#667085}.context-metrics strong{font-size:18px;margin-top:6px;color:#243b53}.context-warning{font-size:13px;line-height:1.7;color:#996016}.context-assessment{padding:12px;background:#f8fafc;margin-top:12px;border-radius:8px;font-size:13px;line-height:1.7}.daily-time-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;width:100%}.daily-time-grid label{display:grid;gap:4px;font-size:12px}.daily-time-grid :deep(.el-input-number){width:100%}.plan-context-panel>.el-checkbox{display:flex;white-space:normal;height:auto;min-height:44px;margin-top:12px}.plan-context-panel :deep(.el-checkbox__label){white-space:normal;line-height:1.6}.plan-context-panel details{font-size:13px;margin:10px 0}.plan-context-panel summary{cursor:pointer}@media(max-width:640px){.context-metrics{grid-template-columns:1fr 1fr}.daily-time-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.plan-context-panel .panel-head{align-items:flex-start;flex-direction:column}}
.ai-plan-page .panel {
  padding: 22px;
}

.ai-plan-page {
  position: relative;
}

.generation-overlay {
  position: fixed;
  inset: 0;
  z-index: 3000;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(15, 23, 42, 0.42);
  backdrop-filter: blur(3px);
}

.generation-panel {
  display: grid;
  gap: 16px;
  width: min(460px, 100%);
  padding: 24px;
  border: 1px solid #d7e7f4;
  border-radius: 8px;
  background: #ffffff;
  box-shadow: 0 24px 70px rgba(15, 23, 42, 0.28);
}

.generation-spinner {
  width: 42px;
  height: 42px;
  border: 4px solid #d7e7f4;
  border-top-color: #1976d2;
  border-radius: 50%;
  animation: generation-spin 1.6s linear infinite;
}

.generation-copy {
  display: grid;
  gap: 6px;
}

.generation-copy h3 {
  margin: 0;
  color: #172033;
  font-size: 20px;
}

.generation-copy p,
.generation-meta {
  margin: 0;
  color: #667085;
  font-size: 13px;
}

.generation-meta {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.generation-mask-enter-active,
.generation-mask-leave-active {
  transition:
    opacity 0.18s ease,
    transform 0.18s ease;
}

.generation-mask-enter-from,
.generation-mask-leave-to {
  opacity: 0;
  transform: translateY(4px);
}

@keyframes generation-spin {
  to {
    transform: rotate(360deg);
  }
}

.ai-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 22px;
  border: 1px solid var(--line-soft);
  border-radius: 8px;
  background: #ffffff;
  box-shadow: var(--shadow-sm);
}

.hero-kicker {
  margin-bottom: 8px;
  color: #1976d2;
  font-size: 13px;
  font-weight: 700;
}

.ai-hero h2 {
  margin: 0;
  color: #172033;
  font-size: 26px;
}

.ai-hero p {
  max-width: 880px;
  margin: 8px 0 0;
  color: #667085;
  line-height: 1.7;
}

.quota-box {
  display: grid;
  gap: 4px;
  min-width: 190px;
  padding: 12px 14px;
  border: 1px solid #d7e7f4;
  border-radius: 8px;
  background: #f6fbff;
}

.quota-box span,
.quota-box em {
  color: #667085;
  font-size: 12px;
  font-style: normal;
}

.quota-box strong {
  color: #1976d2;
}

.ai-grid {
  display: grid;
  grid-template-columns: minmax(460px, 0.95fr) minmax(420px, 1.05fr);
  gap: 16px;
}
.ai-grid>article{min-width:0}
.draft-actions{flex-wrap:wrap}
.draft-actions>.el-button{margin-left:0}

.panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.panel-head h3 {
  margin: 0;
  color: #1f2937;
  font-size: 17px;
  font-weight: 650;
}

.panel-head p {
  margin: 6px 0 0;
  color: #667085;
  font-size: 13px;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.form-help {
  margin-top: 6px;
  color: #667085;
  font-size: 12px;
  line-height: 1.5;
}

.preference-link {
  display: inline-flex;
  margin-top: 8px;
  color: #1976d2;
  font-weight: 700;
  text-decoration: none;
}

.advanced-collapse {
  margin-bottom: 16px;
}

.generation-error {
  margin-bottom: 16px;
}

.date-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  margin: -2px 0 18px;
  padding: 14px 16px;
  border: 1px solid #d7e7f4;
  border-radius: 8px;
  background: linear-gradient(135deg, #f7fbff, #ffffff);
}

.date-summary.invalid {
  border-color: #ffd1ca;
  background: #fff7f5;
}

.date-summary-main {
  display: grid;
  gap: 4px;
}

.date-summary-main .label {
  color: #667085;
  font-size: 12px;
}

.date-summary-main strong {
  color: #172033;
  font-size: 20px;
}

.date-summary-meta {
  display: grid;
  gap: 4px;
  color: #667085;
  font-size: 13px;
  text-align: right;
}

.date-summary.invalid .date-summary-meta {
  color: #b42318;
}

.form-actions,
.draft-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.draft-summary-card {
  display: grid;
  gap: 12px;
  margin-bottom: 14px;
  padding: 16px;
  border: 1px solid #d7e7f4;
  border-radius: 8px;
  background: #f8fbff;
}

.draft-summary-card h4,
.week-block h4 {
  margin: 0;
  color: #172033;
}

.draft-summary-card p {
  margin: 0;
  color: #667085;
}

.draft-metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.draft-metrics span {
  display: grid;
  gap: 3px;
  padding: 10px;
  border: 1px solid #e5edf6;
  border-radius: 6px;
  background: #ffffff;
  color: #344054;
  font-size: 13px;
}

.draft-metrics b {
  color: #667085;
  font-size: 12px;
}

.export-note {
  margin: 8px 0 0;
  color: #667085;
  font-size: 12px;
  line-height: 1.6;
  text-align: right;
}

.week-block {
  margin-top: 18px;
}

.table-actions {
  display: flex;
  gap: 8px;
}

.history-actions {
  align-items: center;
  flex-wrap: wrap;
  min-width: 0;
}

.history-actions .el-button {
  flex: 0 0 auto;
  min-width: 64px;
  margin-left: 0;
}

.history-actions :deep(.el-dropdown) {
  flex: 0 0 auto;
}

.history-actions :deep(.el-dropdown .el-button) {
  width: auto;
}

.history-table :deep(.history-action-column .cell) {
  overflow: visible;
}

.history-table {
  width: 100%;
}

@media (max-width: 1180px) {
  .ai-grid,
  .form-row {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .ai-plan-page {
    gap: 12px;
  }

  .ai-plan-page .panel,
  .ai-hero {
    padding: 16px;
  }

  .ai-hero {
    align-items: stretch;
    flex-direction: column;
  }

  .ai-hero h2 {
    font-size: 22px;
  }

  .ai-hero p {
    font-size: 13px;
    line-height: 1.65;
  }

  .quota-box {
    min-width: 0;
  }

  .date-summary {
    align-items: flex-start;
    flex-direction: column;
    padding: 12px;
  }

  .date-summary-meta {
    text-align: left;
  }

  .form-actions,
  .draft-actions {
    align-items: stretch;
    flex-direction: column;
  }

  .form-actions .el-button,
  .draft-actions .el-button {
    width: 100%;
    margin-left: 0;
  }

  .draft-actions :deep(.el-dropdown) {
    width: 100%;
  }

  .export-note {
    text-align: left;
  }

  .week-block {
    overflow-x: auto;
  }

  .generation-panel {
    padding: 20px;
  }

  .generation-meta {
    flex-direction: column;
    gap: 4px;
  }
}
</style>
