import { beforeEach, afterEach, describe, it, expect, vi } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import { reset, showPage, hidePage } from './lifecycle';
import Resources from '../../pages/workspace/resources.uvue';
import Log from '../../pages/workspace/log.uvue';
import Recovery from '../../pages/workspace/recovery.uvue';
import AIPlan from '../../pages/workspace/ai-plan.uvue';
import Weekly from '../../pages/workspace/weekly.uvue';
import Imports from '../../pages/workspace/imports.uvue';
import Toolbox from '../../pages/workspace/index.uvue';
import Coach from '../../pages/coach/index.uvue';
import Training from '../../pages/training/index.uvue';
import Settings from '../../pages/profile/settings.uvue';
import Today from '../../pages/today/index.uvue';
import Today from '../../pages/today/index.uvue';
import Calendar from '../../components/training/PlanCalendar.uvue';
import { tabSwipe } from '../../utils/swipe';
const mocks = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), put: vi.fn(), upload: vi.fn(), navigate: vi.fn(), epoch: 1 }));
vi.mock('../../services/runtime', () => ({
  api: { get: (...args: unknown[]) => mocks.get(...args), post: (...args: unknown[]) => mocks.post(...args), put: (...args: unknown[]) => mocks.put(...args) },
  auth: { state: { user: { id: 1 } }, epoch: () => mocks.epoch }, requireAuth: async () => true, platform: { navigate: (...args: unknown[]) => mocks.navigate(...args) },
  files: { send: (...args: unknown[]) => mocks.upload(...args) },
}));
function operation<T>(data: T) { return { promise: Promise.resolve(data), cancel: vi.fn() }; }
let wrapper: ReturnType<typeof mount> | null = null;
async function render(component: any, query: Record<string, string> = {}) { reset(query); wrapper = mount(component); await showPage(); await flushPromises(); return wrapper; }
async function click(label: string) { const button = wrapper!.findAll('button').find(button => button.text().includes(label)); expect(button, label).toBeTruthy(); await button!.trigger('click'); await flushPromises(); }
async function input(key: string, value: string) { await wrapper!.get('#field-' + key).trigger('input', { detail: { value } }); await flushPromises(); }
beforeEach(() => { vi.clearAllMocks(); mocks.epoch = 1; mocks.get.mockImplementation(() => operation([])); mocks.post.mockImplementation(() => operation({})); mocks.put.mockImplementation(() => operation({})); });
afterEach(() => { hidePage(); wrapper?.unmount(); wrapper = null; vi.unstubAllGlobals(); });
describe('native-source components in jsdom (not device or real backend acceptance)', () => {
  it('keeps the daily total while showing confirmed and unclassified components of a merged workout', async () => {
    const day = '2026-11-26';
    const record = { record_ref: 'workout_log:41', distance_km: 9, duration_seconds: 2400 };
    const training = { as_of: day, items: [record], summary: { total_distance_km: 9, total_sessions: 1 }, details_complete: true };
    const activities = [1, 2, 3].map((index) => ({ activity_ref: 'external_activity:' + index, date: day, distance_km: 3, duration_seconds: 800, average_pace_seconds_per_km: index === 2 ? 215 : null }));
    mocks.get.mockImplementation((path: string) => {
      if (path.startsWith('/mobile/training/detail?')) return operation({
        activities, selected_activity: null, normalized_segments: [], session_confirmation: { status: 'CONFIRMED', activity_roles: [
          { activity_ref: 'external_activity:1', role: 'warmup' }, { activity_ref: 'external_activity:2', role: 'main' },
        ] },
      });
      if (path.startsWith('/mobile/training')) return operation(training);
      if (path.startsWith('/mobile/series')) return operation({ items: [] });
      if (path.startsWith('/runner-state')) return operation({ snapshot: null });
      if (path.startsWith('/integrations/')) return operation(null);
      return operation([]);
    });
    await render(Today);
    expect(wrapper!.get('.daily-total').text()).toBe('共 9 公里');
    expect(wrapper!.get('.actual-item').text()).not.toContain('9 公里');
    expect(wrapper!.findAll('.today-section').slice(0, 3).map(section => section.text())).toEqual(['今天跑了什么共 9 公里', '训练安排', '恢复一览']);
    expect(wrapper!.text()).not.toContain('查看训练记录');
    await click('查看本周训练与设备状态');
    expect(wrapper!.text()).toContain('查看训练记录');
    const rows = wrapper!.findAll('.breakdown-row');
    expect(rows).toHaveLength(3);
    expect(rows[0].text()).toContain('热身 · 已确认');
    expect(rows[1].text()).toContain('3:35/km');
    expect(rows[2].text()).toContain('活动 3');
    expect(wrapper!.text()).not.toContain('18 公里');
  });
  it('switches appearance immediately, persists only appearance, and updates the native tab when reopened', async () => {
    const nav = vi.fn(), tabs = vi.fn(), save = vi.fn();
    vi.stubGlobal('uni', { getStorageSync: () => undefined, setStorageSync: save, setNavigationBarColor: nav, setTabBarStyle: tabs });
    await render(Settings);
    expect(wrapper!.get('.screen').classes()).toContain('theme-dark');
    await wrapper!.get('switch').trigger('change', { detail: { value: false } });
    expect(save).toHaveBeenLastCalledWith('gaitlogic.mobile.appearance.v1', 'light');
    expect(wrapper!.get('.screen').classes()).toContain('theme-light');
    expect(nav).toHaveBeenLastCalledWith({ frontColor: '#000000', backgroundColor: '#f3f6f9' });
    wrapper!.unmount();
    await render(Toolbox);
    expect(wrapper!.get('.screen').classes()).toContain('theme-light');
    expect(tabs).toHaveBeenLastCalledWith(expect.objectContaining({ backgroundColor: '#ffffff' }));
    wrapper!.unmount();
    await render(Settings);
    await wrapper!.get('switch').trigger('change', { detail: { value: true } });
    expect(save).toHaveBeenLastCalledWith('gaitlogic.mobile.appearance.v1', 'dark');
    expect(wrapper!.get('.screen').classes()).toContain('theme-dark');
  });
  it('flips the calendar from side arrows and horizontal drags, not from vertical scrolling', async () => {
    wrapper = mount(Calendar, { props: { month: '2026-11', asOf: '2026-11-26', days: [] } });
    await wrapper.get('.month-prev').trigger('click');
    await wrapper.get('.month-next').trigger('click');
    const zone = wrapper.get('.month-swipe-zone');
    await zone.trigger('touchstart', { touches: [{ clientX: 165, clientY: 100 }] });
    await zone.trigger('touchend', { touches: [], changedTouches: [{ clientX: 80, clientY: 107 }] });
    await zone.trigger('touchstart', { touches: [{ clientX: 165, clientY: 100 }] });
    await zone.trigger('touchend', { touches: [], changedTouches: [{ clientX: 100, clientY: 225 }] });
    expect(wrapper.emitted('monthChange')).toEqual([[-1], [1], [1]]);
  });
  it('allows center-screen swipes to adjacent tabs without treating vertical drags as navigation', () => {
    const change = vi.fn();
    const swipe = tabSwipe('/pages/training/index', change);
    function drag(from: number, to: number, vertical = 0) {
      swipe.start({ touches: [{ clientX: from, clientY: 100 }], changedTouches: [] });
      swipe.end({ touches: [], changedTouches: [{ clientX: to, clientY: 100 + vertical }] });
    }
    drag(10, 100); drag(380, 280); drag(190, 90); drag(10, 110, 130);
    expect(change.mock.calls).toEqual([['/pages/today/index'], ['/pages/coach/index'], ['/pages/coach/index']]);
    const first = tabSwipe('/pages/today/index', change);
    first.start({ touches: [{ clientX: 10, clientY: 100 }], changedTouches: [] });
    first.end({ touches: [], changedTouches: [{ clientX: 100, clientY: 100 }] });
    expect(change).toHaveBeenCalledTimes(3);
  });
  it('navigates weeks in place and preserves week mode when the next week crosses a month', async () => {
    wrapper = mount(Calendar, { props: { month: '2026-11', asOf: '2026-11-19', days: [] } });
    await wrapper.findAll('button').find(button => button.text() === '所选周')!.trigger('click');
    expect(wrapper.findAll('.day-cell')).toHaveLength(7);
    await wrapper.get('.month-next').trigger('click');
    expect(wrapper.text()).toContain('2026-11-26');
    expect(wrapper.emitted('monthChange')).toBeUndefined();
    await wrapper.get('.month-next').trigger('click');
    expect(wrapper.emitted('monthChange')).toEqual([[1]]);
    await wrapper.setProps({ month: '2026-12' });
    expect(wrapper.text()).toContain('2026-12-03');
    expect(wrapper.findAll('.day-cell')).toHaveLength(7);
  });
  it('does not swallow date or arrow taps after a swipe, and ignores the trailing click of the swipe itself', async () => {
    wrapper = mount(Calendar, { props: { month: '2026-11', asOf: '2026-11-12', days: [] } });
    await click('所选周');
    const point = (x: number) => ({ clientX: x, clientY: 90 });
    const zone = wrapper.get('.month-swipe-zone');
    await zone.trigger('touchstart', { touches: [point(160)] });
    await zone.trigger('touchend', { touches: [], changedTouches: [point(80)] });
    expect(wrapper.get('.selected-day').attributes('aria-label')).toBe('2026-11-19');
    await wrapper.get('.month-next').trigger('click');
    expect(wrapper.get('.selected-day').attributes('aria-label')).toBe('2026-11-19');
    const day = wrapper.get('[aria-label="2026-11-20"]');
    await day.trigger('touchstart', { touches: [point(160)] });
    await day.trigger('touchend', { touches: [], changedTouches: [point(160)] });
    await day.trigger('click');
    expect(wrapper.get('.selected-day').attributes('aria-label')).toBe('2026-11-20');
    const prev = wrapper.get('.month-prev');
    await prev.trigger('touchstart', { touches: [point(24)] });
    await prev.trigger('touchend', { touches: [], changedTouches: [point(24)] });
    await prev.trigger('click');
    expect(wrapper.get('.selected-day').attributes('aria-label')).toBe('2026-11-13');
  });
  it('loads the training chart for the same server-anchored seven days and keeps missing distance distinct from zero', async () => {
    mocks.get.mockImplementation((path: string) => {
      if (path.startsWith('/mobile/series?')) return operation({ items: [{ date: '2026-11-25', distance_km: null }, { date: '2026-11-26', distance_km: 9.5 }] });
      if (path.startsWith('/training-calendar')) return operation({ month: '2026-11', days: [] });
      return operation({ as_of: '2026-11-26', items: [], summary: { total_distance_km: 9.5, total_sessions: 1 } });
    });
    await render(Training);
    expect(mocks.get).toHaveBeenCalledWith('/mobile/series?start_date=2026-11-20&end_date=2026-11-26');
    expect(wrapper!.get('.chart-panel').text()).toContain('9.5');
    expect(wrapper!.findAll('.bar-fill')).toHaveLength(1);
    expect(wrapper!.findAll('.bar-missing')).toHaveLength(1);
  });
  it('labels backend interval and long run types and changes the selected plan without treating unplanned days as rest', async () => {
    wrapper = mount(Calendar, { props: { month: '2026-11', asOf: '2026-11-26', days: [
      { date: '2026-11-26', planned_workout_id: 1, planned_content: '合成间歇课', planned_distance_km: 8, main_type: 'interval_speed' },
      { date: '2026-11-28', planned_workout_id: 2, planned_content: '合成长距离', planned_distance_km: 16, main_type: 'long_run' },
    ] } });
    expect(wrapper.get('.today-cell .plan-marker').exists()).toBe(true);
    expect(wrapper.get('.calendar-detail').text()).toContain('合成间歇课');
    await wrapper.get('[aria-label="2026-11-28"]').trigger('click');
    expect(wrapper.get('.selected-day').attributes('aria-label')).toBe('2026-11-28');
    expect(wrapper.get('.calendar-detail').text()).toContain('合成长距离');
    expect(wrapper.get('.calendar-detail').text()).toContain('长跑');
    expect(wrapper.findAll('.day-button .activity-marker')).toHaveLength(0);
  });
  it('presents the Web calendar summary, explicit completion and selected-day editing', async () => {
    wrapper = mount(Calendar, { props: {
      month: '2026-11', asOf: '2026-11-26',
      summary: { planned_distance_km: '40', actual_distance_km: '32', completion_rate: '0.8', completed_days: 4, missed_days: 1 },
      days: [{ date: '2026-11-26', planned_workout_id: 42, planned_content: '合成轻松跑', planned_distance_km: '8', main_type: 'easy', actual_distance_km: 7.5, status_normalized: 'completed_adjusted' }],
    } });
    expect(wrapper.get('.summary-panel').text()).toContain('80%');
    expect(wrapper.get('.day-symbol').text()).toBe('◐ 调整完成');
    expect(wrapper.get('.selected-day').findAll('.day-marker')).toHaveLength(2);
    expect(wrapper.get('.calendar-detail').text()).toContain('7.5公里');
    await click('编辑日志');
    expect(wrapper.emitted('editLog')).toEqual([[42]]);
    await wrapper.get('picker').trigger('change', { detail: { value: '2026-12' } });
    expect(wrapper.emitted('monthSelect')).toEqual([['2026-12']]);
  });
  it('removes live coach progress when the reply arrives, even while refreshing history', async () => {
    vi.useFakeTimers();
    try {
      let finishReply!: (value: unknown) => void;
      let finishHistory!: (value: unknown) => void;
      let messageReads = 0;
      mocks.get.mockImplementation((path: string) => {
        if (path.endsWith('/status')) return operation({ progress: { stage: 'GENERATING', sequence: 1, terminal: false, summary: [{ message: '已获取当前训练状态' }] } });
        if (path.includes('/messages?')) return ++messageReads === 1 ? operation({ items: [], total: 0 }) : { promise: new Promise(resolve => { finishHistory = resolve; }), cancel: vi.fn() };
        return operation({ items: [{ id: 'test-chat', title: '合成对话' }] });
      });
      mocks.post.mockImplementation(() => ({ promise: new Promise(resolve => { finishReply = resolve; }), cancel: vi.fn() }));
      // Use Vue microtasks here; flushPromises schedules a timer under jsdom.
      reset(); wrapper = mount(Coach); await showPage(); await vi.advanceTimersByTimeAsync(0);
      await wrapper.get('.starter').trigger('click');
      await wrapper.get('.send-button').trigger('click');
      await vi.advanceTimersByTimeAsync(650);
      expect(wrapper.get('.progress-card').text()).toContain('正在组织回答');
      finishReply({ message_id: 'r1', status: 'completed', content: '合成回答正文' });
      await vi.advanceTimersByTimeAsync(0);
      expect(wrapper.text()).toContain('合成回答正文');
      expect(wrapper.find('.progress-card').exists()).toBe(false);
      finishHistory({ items: [{ id: 'r1', status: 'completed', role: 'assistant', content: '合成回答正文', sequence_no: 2, warnings: [], limitations: [] }], total: 1 });
      await vi.advanceTimersByTimeAsync(0);
      expect(wrapper.find('.progress-card').exists()).toBe(false);
    } finally { vi.useRealTimers(); }
  });
  it('opens grouped toolbox destinations without issuing a data write', async () => {
    await render(Toolbox);
    expect(wrapper!.get('.title').text()).toBe('训练工具箱');
    const tiles = wrapper!.findAll('.tool-tile');
    expect(tiles.length).toBeGreaterThan(10);
    await tiles.find(tile => tile.text().includes('配速换算'))!.trigger('click');
    expect(mocks.navigate).toHaveBeenLastCalledWith('/pages/workspace/pace');
    await tiles.find(tile => tile.text().includes('训练统计'))!.trigger('click');
    expect(mocks.navigate).toHaveBeenLastCalledWith('/pages/analytics/index');
    expect(mocks.post).not.toHaveBeenCalled();
  });
  it('creates a cycle only after preview and explicit confirmation, without ownership fields', async () => {
    let cycles: unknown[] = [];
    mocks.get.mockImplementation(() => operation(cycles));
    mocks.post.mockImplementation((_path: string, data: Record<string, unknown>) => { cycles = [{ id: 900041, status: 'draft', ...data }]; return operation(cycles[0]); });
    await render(Resources, { kind: 'cycles' }); await click('新建'); await input('name', '合成迁移周期'); await click('预览修改');
    expect(mocks.post).not.toHaveBeenCalled(); await click('确认保存');
    expect(mocks.post).toHaveBeenCalledTimes(1);
    const [path, body] = mocks.post.mock.calls[0]; expect(path).toBe('/training-cycles'); expect(body.name).toBe('合成迁移周期'); expect(body.user_id).toBeUndefined(); expect(body.status).toBeUndefined();
    expect(wrapper!.text()).toContain('草稿 · 未启用');
  });
  it('rejects invalid required input before any cycle write', async () => {
    await render(Resources, { kind: 'cycles' }); await click('新建'); await click('预览修改');
    expect(wrapper!.text()).toContain('请填写周期名称'); expect(mocks.post).not.toHaveBeenCalled();
  });
  it('writes session self-rating without replacing device distance, activity RPE or existing notes', async () => {
    mocks.get.mockImplementation(() => operation({ existing_workout_log: { status_normalized: 'completed_normal', actual_distance_km: 12, rpe: null, review_note: '合成原有笔记' }, linked_garmin_activities: [{ id: 1 }, { id: 2 }] }));
    await render(Log, { workout_id: '900021' }); expect(wrapper!.find('#field-actual_distance_km').exists()).toBe(false);
    await input('rpe', '4'); await click('预览保存'); expect(mocks.put).not.toHaveBeenCalled(); await click('确认保存');
    expect(mocks.put).toHaveBeenCalledWith('/workout-logs/900021', { rpe: 4 });
  });
  it('rejects a zero RPE rather than using it as missing', async () => {
    mocks.get.mockImplementation(() => operation({ existing_workout_log: { status_normalized: 'completed_normal' }, linked_garmin_activities: [{ id: 1 }] }));
    await render(Log, { workout_id: '900021' }); await input('rpe', '0'); await click('预览保存');
    expect(wrapper!.text()).toContain('超出允许范围'); expect(mocks.put).not.toHaveBeenCalled();
  });
  it('recovery writes only changed subjective feedback, keeping unknown HRV and sleep data', async () => {
    mocks.get.mockImplementation(() => operation({ checkin_date: '2026-01-12', source: 'GARMIN', hrv_value: null, sleep_duration_minutes: 440, device_missing_fields_json: ['hrv_value'] }));
    await render(Recovery); await input('subjective_fatigue', '2'); await click('预览保存'); expect(mocks.put).not.toHaveBeenCalled(); await click('确认保存');
    expect(mocks.put).toHaveBeenCalledWith('/recovery-checkins/today', { subjective_fatigue: 2 });
  });
  it('does not silently autofill training basis and prevents generation when quota is unavailable', async () => {
    mocks.get.mockImplementation((path: string) => operation(path === '/ai-plan/context' ? { as_of_date: '2026-01-12', timezone: 'Asia/Shanghai', suggestions: { current_weekly_mileage_km: 42, recent_4w_avg_mileage_km: 40 }, runner_facts: {}, feasibility: [] } : path === '/ai-plan/quota' ? { remaining_count: 0, can_generate: false } : []));
    await render(AIPlan); expect(wrapper!.get('#field-current_weekly_mileage_km').element.value).toBe('');
    await click('采用自动建议跑量'); expect(wrapper!.get('#field-current_weekly_mileage_km').element.value).toBe('42');
    const generate = wrapper!.findAll('button').find(button => button.text().includes('检查并预览生成请求'))!;
    expect(generate.attributes('disabled')).toBeDefined(); expect(mocks.post).not.toHaveBeenCalled();
  });
  it('changing an AI plan field invalidates the assessed request before generation', async () => {
    mocks.get.mockImplementation((path: string) => operation(path === '/ai-plan/context' ? { suggestions: {}, runner_facts: {}, feasibility: [] } : path === '/ai-plan/quota' ? { can_generate: true, remaining_count: 1 } : []));
    mocks.post.mockImplementation(() => operation({ feasibility: [] }));
    await render(AIPlan); await input('current_weekly_mileage_km', '40'); await input('recent_4w_avg_mileage_km', '38');
    // The date picker is identified by the enclosing field's label/order in the real template.
    const dates = wrapper!.findAll('picker').filter(item => item.attributes('mode') === 'date');
    expect(dates.length).toBe(2); await dates[1].trigger('change', { detail: { value: '2026-12-01' } });
    await click('检查并预览生成请求'); expect(wrapper!.text()).toContain('生成前确认');
    await input('current_weekly_mileage_km', '45'); expect(wrapper!.text()).not.toContain('确认生成草稿');
    expect(mocks.post.mock.calls.some(call => call[0] === '/ai-plan/generate')).toBe(false);
  });
  it('weekly graph analysis does not apply a pending proposal without explicit HITL confirmation', async () => {
    const facts = { period: { week_start: '2026-01-05', week_end: '2026-01-11' }, planned: { planned_distance_km: 40 }, completed: { actual_distance_km: 38, completed_running_session_count: 4 }, data_quality: { level: 'PARTIAL' }, classification: { warnings: [], limitations: ['合成缺口'] } };
    mocks.get.mockImplementation((path: string) => operation(path.includes('/facts?') ? facts : path.includes('/proposals/') ? { id: 900061, status: 'pending_approval', proposal: { changes: [{ plan_id: 900071, date: '2026-01-12', reason: '合成原因', before: { content: '原计划', distance_km: 10 }, after: { content: '待确认建议', distance_km: 8 } }], warnings: [], limitations: [] } } : { items: [] }));
    mocks.post.mockImplementation((path: string) => operation(path === '/weekly-reviews/graph' ? { overview: '合成分析', next_week_focus: [], warnings: [], limitations: [], proposal_record_id: 900061 } : { status: 'applied' }));
    await render(Weekly); const dates = wrapper!.findAll('picker'); await dates[0].trigger('change', { detail: { value: '2026-01-05' } }); await dates[1].trigger('change', { detail: { value: '2026-01-11' } });
    await click('读取这周事实'); await click('准备生成周复盘'); expect(mocks.post).not.toHaveBeenCalled(); await click('确认生成复盘');
    expect(wrapper!.text()).toContain('待确认建议'); expect(mocks.post.mock.calls.some(call => call[0].endsWith('/approve'))).toBe(false);
    await click('准备确认调整'); expect(mocks.post.mock.calls.some(call => call[0].endsWith('/approve'))).toBe(false);
    await click('确认应用上述调整'); expect(mocks.post).toHaveBeenCalledWith('/adaptive-plan/proposals/900061/approve', {});
  });
  it('file import separates local selection, upload, preview and confirmed application', async () => {
    vi.stubGlobal('uni', { chooseFile: (options: any) => options.success({ tempFiles: [{ name: 'synthetic.xlsx', path: 'synthetic-local-file', size: 1024 }] }) });
    let status = 'ready';
    mocks.upload.mockImplementation(() => operation({ import_id: 900081 }));
    mocks.get.mockImplementation(() => operation({ import_id: 900081, status, diff_summary: { created_count: 1, updated_count: 0, removed_count: 0, conflict_count: 0 }, conflicts: [], warnings: [{ message: '合成提示：仍需审阅' }], items: [{ id: 900082, planned_date: '2026-12-01', suggested_content: '合成轻松跑', suggested_distance_km: 8, operation: 'create' }] }));
    mocks.post.mockImplementation(() => { status = 'applied'; return operation({ status }); });
    await render(Imports); const date = wrapper!.find('picker[mode="date"]'); await date.trigger('change', { detail: { value: '2026-12-01' } });
    await click('选择文件'); expect(mocks.upload).not.toHaveBeenCalled(); await click('准备上传草稿'); expect(mocks.upload).not.toHaveBeenCalled(); await click('确认上传');
    expect(mocks.upload).toHaveBeenCalledTimes(1); const [kind, file, metadata, key] = mocks.upload.mock.calls[0];
    expect(kind).toBe('plan'); expect(file.name).toBe('synthetic.xlsx'); expect(metadata.merge_strategy).toBe('fill_empty_only'); expect(metadata.effective_date).toBe('2026-12-01'); expect(metadata.client_request_id).toBe(key);
    expect(wrapper!.text()).toContain('合成提示：仍需审阅'); expect(mocks.post).not.toHaveBeenCalled();
    await click('准备应用导入'); expect(mocks.post).not.toHaveBeenCalled(); await click('确认已审阅风险并应用');
    expect(mocks.post).toHaveBeenCalledWith('/plan-imports/900081/apply?confirm_high=true', {}); expect(wrapper!.text()).toContain('applied');
  });
  it('AI draft rejection requires confirmation and never calls plan application', async () => {
    let status = 'draft';
    const draft = () => ({ id: 900301, title: '合成草稿 A', status, start_date: '2026-12-01', end_date: '2026-12-28', risk_notes: ['合成风险提示'], workouts: [] });
    mocks.get.mockImplementation((path: string) => operation(path === '/ai-plan/drafts' ? [draft()] : path.endsWith('/900301') ? draft() : path === '/ai-plan/context' ? { suggestions: {}, runner_facts: {}, feasibility: [] } : { remaining_count: 0, can_generate: false }));
    mocks.post.mockImplementation(() => { status = 'rejected'; return operation({ message: 'ok' }); });
    await render(AIPlan); const card = wrapper!.findAll('.card').find(item => item.text().includes('合成草稿 A →'))!; await card.trigger('click'); await flushPromises();
    await click('拒绝这份草稿'); expect(mocks.post).not.toHaveBeenCalled(); await click('确认拒绝');
    expect(mocks.post).toHaveBeenCalledWith('/ai-plan/drafts/900301/reject', {}); expect(mocks.post.mock.calls.some(call => call[0].includes('/apply'))).toBe(false); expect(wrapper!.text()).toContain('已拒绝');
  });
  it('selecting another AI draft invalidates the previous rejection confirmation', async () => {
    const drafts = [900301, 900302].map(id => ({ id, title: '合成草稿 ' + id, status: 'draft', workouts: [] }));
    mocks.get.mockImplementation((path: string) => operation(path === '/ai-plan/drafts' ? drafts : path.startsWith('/ai-plan/drafts/') ? drafts.find(item => path.endsWith('/' + item.id)) : path === '/ai-plan/context' ? { suggestions: {}, runner_facts: {}, feasibility: [] } : { remaining_count: 0, can_generate: false }));
    await render(AIPlan); const first = wrapper!.findAll('.card').find(item => item.text().includes('合成草稿 900301 →'))!; await first.trigger('click'); await flushPromises(); await click('拒绝这份草稿');
    const second = wrapper!.findAll('.card').find(item => item.text().includes('合成草稿 900302 →'))!; await second.trigger('click'); await flushPromises();
    expect(wrapper!.text()).not.toContain('确认拒绝草稿'); expect(mocks.post).not.toHaveBeenCalled();
  });
  it('invalid files never become uploadable and conflict drafts cannot be applied', async () => {
    vi.stubGlobal('uni', { chooseFile: (options: any) => options.success({ tempFiles: [{ name: 'synthetic.exe', path: 'synthetic-local-file', size: 1024 }] }) });
    await render(Imports); await click('选择文件'); expect(wrapper!.text()).toContain('标准 .xlsx 模板');
    const upload = wrapper!.findAll('button').find(button => button.text().includes('准备上传草稿'))!; expect(upload.attributes('disabled')).toBeDefined(); expect(mocks.upload).not.toHaveBeenCalled();
    mocks.get.mockImplementation(() => operation({ import_id: 900081, status: 'conflict', conflicts: [{ message: '合成冲突：已有计划' }], warnings: [], items: [] }));
    await wrapper!.get('input.input').setValue('900081'); await click('读取草稿');
    expect(wrapper!.text()).toContain('合成冲突：已有计划');
    const apply = wrapper!.findAll('button').find(button => button.text().includes('准备应用导入'))!;
    expect(apply.attributes('disabled')).toBeDefined(); expect(mocks.post).not.toHaveBeenCalled();
  });
});
