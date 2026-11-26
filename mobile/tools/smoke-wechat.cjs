/* Simulator UI smoke with synthetic transport only. Never calls a real backend. */
const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');
const sdk = process.env.GAITLOGIC_MINIPROGRAM_AUTOMATOR_MODULE;
if (!sdk) throw new Error('Set GAITLOGIC_MINIPROGRAM_AUTOMATOR_MODULE to an installed miniprogram-automator module.');
const automator = require(path.resolve(sdk));
const tokenKey = 'gaitlogic.mobile.token.v1.production';
const baseKey = 'gaitlogic.mobile.production.api-base.v1';
const checks = [];
checks.push = function (...names) { console.log(JSON.stringify({ completed: names })); return Array.prototype.push.apply(this, names); };
async function waitFor(page, condition, label = 'simulator assertion') {
  const deadline = Date.now() + 12000;
  while (Date.now() < deadline) {
    if (typeof condition === 'string' ? await page.$(condition) : await condition()) return;
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  throw new Error('Timed out waiting for ' + label + '.');
}
async function field(page, name) {
  const selector = '#field-' + name;
  const direct = await page.$(selector);
  if (direct) return direct;
  for (const host of await page.$$('.runner-form-host')) {
    const nested = await host.$(selector);
    if (nested) return nested;
  }
  return null;
}
async function run() {
  const mini = await automator.connect({ wsEndpoint: process.env.GAITLOGIC_MINIPROGRAM_WS || 'ws://127.0.0.1:9420' });
  const exceptions = [];
  async function capture(name) {
    const directory = process.env.GAITLOGIC_MOBILE_SCREENSHOTS;
    if (!directory) return;
    fs.mkdirSync(directory, { recursive: true });
    await new Promise(resolve => setTimeout(resolve, 250));
    await mini.screenshot({ path: path.join(directory, name + '.png') });
  }
  mini.on('exception', () => exceptions.push('RUNTIME_EXCEPTION'));
  let changed = false, previousBase;
  try {
    const occupied = await mini.evaluate(key => !!wx.getStorageSync(key), tokenKey);
    assert.equal(occupied, false, 'Existing login detected; do not overwrite a user session.');
    previousBase = await mini.evaluate(key => wx.getStorageSync(key), baseKey);
    await mini.mockWxMethod('request', function (options) {
      const date = '2026-01-12';
      const route = options.url.split('/api')[1] || '';
      const state = getApp().__mobileSmoke || (getApp().__mobileSmoke = { conversation: null, messages: [] });
      const item = { record_ref: 'workout_log:900001', date, distance_km: 8.4, duration_seconds: 2640,
        average_pace_seconds_per_km: 314.29, average_heart_rate: null,
        actual_training_type: null, planned_training_type: null, source: 'MANUAL' };
      let statusCode = 200, data;
      if (route === '/auth/login') {
        if (options.data.password === 'synthetic-wrong') { statusCode = 401; data = {}; }
        else data = { access_token: 'synthetic-ui-test-not-a-real-jwt', token_type: 'bearer' };
      } else if (route === '/auth/me') data = { id: 900001, username: 'synthetic_mobile', nickname: '合成跑者', role: 'user', status: 'active' };
      else if (route.startsWith('/planned-workouts/') && route.endsWith('/completion-context')) data = {
        existing_workout_log: { id: 900031, status_normalized: 'completed_normal', rpe: null, actual_distance_km: 12, review_note: '合成原有笔记' }, linked_garmin_activities: [{ id: 900011 }, { id: 900012 }], candidate_garmin_activities: [] };
      else if (route.startsWith('/planned-workouts')) data = [];
      else if (route === '/workout-logs/900021' && options.method === 'PUT') { state.savedLog = options.data; data = { id: 900031, ...options.data }; }
      else if (route === '/training-cycles' && options.method === 'POST') { state.createdCycle = options.data; state.cycles = [{ id: 900041, status: 'draft', ...options.data }]; data = state.cycles[0]; }
      else if (route === '/training-cycles') data = state.cycles || [];
      else if (route === '/recovery-checkins/today') {
        if (options.method === 'PUT') state.savedRecovery = options.data;
        data = { checkin_date: date, source: 'GARMIN', sleep_duration_minutes: 440, hrv_value: null, resting_heart_rate_bpm: 50, body_battery_end: null, device_missing_fields_json: ['hrv_value', 'body_battery_end'], ...(state.savedRecovery || {}) };
      }
      else if (route === '/ai-plan/context') data = { as_of_date: date, timezone: 'Asia/Shanghai', suggestions: { recent_4w_avg_mileage_km: 40, current_weekly_mileage_km: 42 }, runner_facts: { training: { limitations: ['合成数据：同步覆盖未核实'] } }, feasibility: [] };
      else if (route === '/ai-plan/quota') data = { remaining_count: 0, can_generate: false };
      else if (route === '/ai-plan/drafts') data = [];
      else if (route === '/integrations/garmin/smart-sync') data = { status: 'AUTO_SYNC_DISABLED', enabled: false, last_success_by_scope: { training: null, recovery: null } };
      else if (route === '/integrations/garmin/sync-jobs') data = [{ id: 900051, status: 'failed', created_count: 0, updated_count: 0, failed_count: 1, finished_at: date, error_code: 'TIMEOUT', is_committed: false }];
      else if (route.startsWith('/mobile/training/detail')) {
        const activities = [
          { activity_ref: 'external_activity:900011', date, distance_km: 7, duration_seconds: 2160 },
          { activity_ref: 'external_activity:900012', date, distance_km: 1.4, duration_seconds: 480 },
        ];
        const decodedRoute = decodeURIComponent(route);
        const selected = decodedRoute.includes('activity_ref=external_activity:900012') ? activities[1]
          : decodedRoute.includes('activity_ref=external_activity:900011') ? activities[0] : null;
        state.detailSelection = selected?.activity_ref || 'NONE';
        data = { record: item, activities, selected_activity: selected ? { ...selected, source: 'GARMIN',
          average_heart_rate_bpm: null, average_running_power_w: null, rpe: selected.activity_ref.endsWith('900012') ? 2 : null,
          rpe_evidence: { source: 'garmin' } } : null,
          selection_required: !selected, normalized_segments: [], raw_segments_complete: !!selected,
          segments: selected ? [{ index: 17, distance_m: selected.distance_km * 1000, duration_seconds: selected.duration_seconds, lap_type: 'RWD_RUN' }] : [],
          segment_validation: { detail_status: 'SUMMARY_ONLY', structure_complete: false }, limitations: [] };
      }
      else if (route.startsWith('/mobile/training')) data = { as_of: date, range_start: '2026-01-06', range_end: date,
        items: [item], summary: { total_distance_km: 8.4, total_sessions: 1 }, details_complete: true, next_cursor: null };
      else if (route.startsWith('/mobile/series')) data = { as_of: date, range_start: '2026-01-06', range_end: date,
        items: [{ date: '2026-01-11', distance_km: null, session_count: 1, missing_distance_count: 1 },
          { date, distance_km: 8.4, session_count: 1, missing_distance_count: 0 }],
        unresolved_activity_count: 0, gaps: ['MISSING_RECORDED_DISTANCE'], limitations: [] };
      else if (route.startsWith('/training-calendar')) data = { month: '2026-01', days: [] };
      else if (route === '/runner-state/current') data = { snapshot: { recovery: { as_of_date: date, freshness: 'PARTIAL',
        sleep_duration_minutes: null, resting_heart_rate_bpm: null, limitations: [] },
        inferred_state: { fatigue_state: 'UNKNOWN' }, data_quality: { data_quality_level: 'LOW', limitations: [] } } };
      else if (route === '/integrations/garmin/status') data = { connected: false, status: 'DISCONNECTED',
        last_successful_sync_at: null, recovery_last_successful_sync_at: null, last_error_code: null };
      else if (route === '/coach/conversations' && options.method === 'POST') {
        state.conversation = { id: 'synthetic-ui-conversation', title: '合成测试对话', status: 'active', message_count: 0 };
        data = state.conversation;
      } else if (route.includes('/turns/')) data = { message_status: 'completed', progress: {
        stage: 'COMPLETED', sequence: 8, terminal: true, summary: [] } };
      else if (route.endsWith('/messages') && options.method === 'POST') {
        state.messages = [
          { id: 'synthetic-user', role: 'user', content: options.data.message, status: 'completed', sequence_no: 1, warnings: [], limitations: [] },
          { id: 'synthetic-assistant', role: 'assistant', content: '## 合成回复\n这是一条用于界面验收的固定消息，不是模型分析。', status: 'completed', sequence_no: 2, warnings: [], limitations: [] }
        ];
        data = { conversation_id: 'synthetic-ui-conversation', message_id: 'synthetic-assistant', status: 'completed',
          content: state.messages[1].content, response: { warnings: [], limitations: [] } };
      } else if (route.includes('/messages?')) data = { items: state.messages, total: state.messages.length, page: 1, page_size: 50 };
      else if (route.startsWith('/coach/conversations')) data = { items: state.conversation ? [state.conversation] : [], total: state.conversation ? 1 : 0, page: 1, page_size: 20 };
      else { statusCode = 404; data = {}; }
      // The official automation adapter supplies callbacks from this result.
      // Returning a RequestTask instead would incorrectly become response data.
      return { statusCode, data, header: {} };
    });
    changed = true;
    await mini.evaluate((key) => wx.setStorageSync(key, 'https://synthetic.example.test/api'), baseKey);
    let page = await mini.reLaunch('/pages/auth/login');
    await waitFor(page, '.title');
    assert.equal(await (await page.$('.title')).text(), '欢迎使用 GaitLogic');
    assert.equal((await page.$$('input')).length, 2, 'Connection settings must be hidden on normal login.');
    const viewport = await (await page.$('scroll-view')).size();
    assert.ok(Number(viewport.height) > 100);
    checks.push('login_page_visible');
    await capture('01-login');
    await (await page.$('.username-field')).input('synthetic_mobile');
    await (await page.$('.password-field')).input('synthetic-wrong');
    await (await page.$('button.primary')).tap();
    await waitFor(page, '.error-text');
    assert.match(await (await page.$('.error-text')).text(), /账号或密码不正确/);
    checks.push('wrong_password_feedback');
    await (await page.$('.password-field')).input('synthetic-correct');
    await (await page.$('button.primary')).tap();
    await waitFor(page, async () => (await mini.currentPage()).path === 'pages/today/index');
    page = await mini.currentPage();
    await waitFor(page, '.actual-item');
    assert.match(await (await page.$('.actual-item')).text(), /8.4/);
    checks.push('no_plan_actual_training_visible');
    await capture('02-today');
    await (await page.$('scroll-view')).scrollTo(0, 600);
    const scrollTop = await (await page.$('scroll-view')).property('scrollTop');
    assert.ok(Number(scrollTop) > 0);
    checks.push('vertical_scroll');
    page = await mini.switchTab('/pages/training/index');
    await waitFor(page, '.switch');
    const activityTab = (await Promise.all((await page.$$('.switch')).map(async button => ({ button, text: await button.text() })))).find(entry => entry.text === '活动');
    assert.ok(activityTab);
    await activityTab.button.tap();
    await waitFor(page, 'button.secondary');
    const buttons = await page.$$('button.secondary');
    const detailButton = (await Promise.all(buttons.map(async button => ({ button, text: await button.text() })))).find(entry => entry.text.includes('查看训练详情'));
    assert.ok(detailButton);
    await capture('03-training');
    await detailButton.button.tap();
    await waitFor(page, async () => (await mini.currentPage()).path === 'pages/training/detail');
    page = await mini.currentPage();
    await waitFor(page, '.hero-number');
    assert.match(await (await page.$('.hero-number')).text(), /8.4/);
    checks.push('training_detail_navigation');
    const activityButtons = await page.$$('button.secondary');
    assert.equal(activityButtons.length, 2);
    await activityButtons[1].tap();
    await (await page.$('scroll-view')).scrollTo(0, 800);
    try {
      await waitFor(page, async () => /活动\s*RPE\s*·\s*2\/10/.test(await (await page.$('.page')).text()), 'selected activity RPE');
    } catch {
      const selection = await mini.evaluate(() => getApp().__mobileSmoke?.detailSelection);
      const text = await (await page.$('.page')).text();
      throw new Error(JSON.stringify({ phase: 'selected_activity', selection, hasActivity: text.includes('选中活动'),
        effortSnippet: text.slice(Math.max(0, text.indexOf('活动 RPE')), Math.max(0, text.indexOf('活动 RPE')) + 80),
        hasRpe: text.includes('RPE'), hasReadError: text.includes('详情读取失败') }));
    }
    let detailText = await (await page.$('.page')).text();
    assert.match(detailText, /不代表整堂课 RPE/);
    assert.match(detailText, /暂无规范化分段/);
    const rawButton = (await Promise.all((await page.$$('button.secondary')).map(async button => ({ button, text: await button.text() })))).find(entry => entry.text.includes('查看原始存储圈'));
    assert.ok(rawButton);
    await rawButton.button.tap();
    await waitFor(page, async () => (await (await page.$('.page')).text()).includes('原始圈 17'));
    detailText = await (await page.$('.page')).text();
    assert.match(detailText, /不默认每圈为一公里/);
    checks.push('activity_effort_and_raw_lap_semantics');
    await capture('04-detail');
    await mini.navigateBack();
    page = await mini.currentPage();
    const calendarTab = (await Promise.all((await page.$$('.switch')).map(async button => ({ button, text: await button.text() })))).find(entry => entry.text === '日历');
    assert.ok(calendarTab);
    await calendarTab.button.tap();
    await waitFor(page, '.month-next');
    const weekToggle = (await Promise.all((await page.$$('button')).map(async button => ({ button, text: await button.text() })))).find(entry => entry.text === '所选周');
    assert.ok(weekToggle);
    await weekToggle.button.tap();
    await (await page.$('.month-next')).tap();
    await waitFor(page, async () => (await (await page.$('.selected-day')).text()).trim() === '19', 'next week arrow');
    for (const cell of await page.$$('.day-button')) {
      if ((await cell.text()).trim() === '20') { await cell.tap(); break; }
    }
    await waitFor(page, async () => (await (await page.$('.selected-day')).text()).trim() === '20', 'day tap');
    await (await page.$('.month-prev')).tap();
    await waitFor(page, async () => (await (await page.$('.selected-day')).text()).trim() === '13', 'previous week arrow');
    checks.push('calendar_week_arrows_and_date_taps');
    page = await mini.navigateTo('/pages/analytics/index');
    // uni-app x virtualHost removes the component tag in WeChat output.
    await waitFor(page, async () => (await (await page.$('.page')).text()).includes('距离趋势'));
    const chartText = await (await page.$('.page')).text();
    assert.match(chartText, /每日距离/);
    assert.match(chartText, /距离趋势/);
    assert.match(chartText, /缺失/);
    checks.push('charts_mounted');
    await capture('05-analytics');
    page = await mini.switchTab('/pages/coach/index');
    await waitFor(page, async () => (await page.$$('.body')).length > 0);
    checks.push('coach_empty_state');
    await (await page.$('button.secondary')).tap();
    await waitFor(page, 'input');
    await (await page.$('input')).input('请展示合成测试回复');
    await (await page.$('button.primary')).tap();
    await waitFor(page, async () => (await (await page.$('.chat-feed')).text()).includes('用于界面验收的固定消息'));
    assert.match(await (await page.$('.user-message')).text(), /请展示合成测试回复/);
    checks.push('coach_create_send_json');
    await capture('06-gilo');
    page = await mini.switchTab('/pages/profile/index');
    await waitFor(page, '.hero-title');
    assert.equal(await (await page.$('.hero-title')).text(), '合成跑者');
    checks.push('profile_identity');
    await capture('07-profile');
    async function tapLabel(currentPage, label) {
      const entries = await Promise.all((await currentPage.$$('button')).map(async button => ({ button, text: await button.text() })));
      const entry = entries.find(item => item.text.includes(label)); assert.ok(entry, label);
      // Event-level simulator interaction; not a physical touchscreen assertion.
      await entry.button.trigger('tap');
    }
    page = await mini.switchTab('/pages/workspace/index');
    await waitFor(page, '.tool-tile');
    assert.ok((await page.$('.tool-tile')).length >= 10);
    assert.equal(await (await page.$('.title')).text(), '训练工具箱');
    checks.push('tools_first_level_tab_and_grouped_tiles');
    await capture('08-tools');
    page = await mini.navigateTo('/pages/workspace/pace');
    await waitFor(page, async () => (await (await page.$('.page')).text()).includes('小时'), 'native clock labels');
    assert.match(await (await page.$('.hero-number')).text(), /4:16/);
    checks.push('native_pace_wheel_and_conversion');
    await capture('08-pace');
    await mini.navigateBack();
    const formAutomation = process.env.GAITLOGIC_MOBILE_FORM_AUTOMATION === '1';
    if (formAutomation) {
    page = await mini.navigateTo('/pages/workspace/resources?kind=cycles');
    await waitFor(page, 'button.primary'); await tapLabel(page, '新建');
    await waitFor(page, async () => !!await field(page, 'name'), 'cycle form name input'); await (await field(page, 'name')).input('合成迁移周期');
    await tapLabel(page, '预览修改');
    assert.equal(await mini.evaluate(() => getApp().__mobileSmoke.createdCycle == null), true, 'Preview must not write.');
    await tapLabel(page, '确认保存');
    await waitFor(page, async () => (await (await page.$('.page')).text()).includes('合成迁移周期') && (await field(page, 'name')) == null, 'cycle saved');
    const createdCycle = await mini.evaluate(() => getApp().__mobileSmoke.createdCycle);
    assert.equal(createdCycle.name, '合成迁移周期'); assert.equal(createdCycle.user_id, undefined); assert.equal(createdCycle.status, undefined);
    checks.push('cycle_create_requires_preview_and_confirmation');
    await mini.navigateBack();
    page = await mini.navigateTo('/pages/workspace/log?workout_id=900021');
    await waitFor(page, async () => !!await field(page, 'rpe'), 'subjective log form');
    assert.equal(await field(page, 'actual_distance_km'), null, 'Linked objective metrics must not be edited in this form.');
    await (await field(page, 'rpe')).input('4'); await tapLabel(page, '预览保存');
    assert.equal(await mini.evaluate(() => getApp().__mobileSmoke.savedLog == null), true);
    await tapLabel(page, '确认保存'); await waitFor(page, async () => await mini.evaluate(() => !!getApp().__mobileSmoke.savedLog));
    assert.deepEqual(await mini.evaluate(() => getApp().__mobileSmoke.savedLog), { rpe: 4 });
    checks.push('subjective_log_preserves_device_metrics_and_notes');
    await mini.navigateBack();
    page = await mini.navigateTo('/pages/workspace/recovery'); await waitFor(page, async () => !!await field(page, 'subjective_fatigue'), 'recovery form');
    await (await field(page, 'subjective_fatigue')).input('2'); await tapLabel(page, '预览保存'); await tapLabel(page, '确认保存');
    await waitFor(page, async () => await mini.evaluate(() => !!getApp().__mobileSmoke.savedRecovery));
    assert.deepEqual(await mini.evaluate(() => getApp().__mobileSmoke.savedRecovery), { subjective_fatigue: 2 });
    checks.push('recovery_partial_write_preserves_missing_hrv');
    await mini.navigateBack();
    page = await mini.navigateTo('/pages/workspace/ai-plan');
    await waitFor(page, async () => (await (await page.$('.page')).text()).includes('今日剩余额度 0'));
    await tapLabel(page, '采用自动建议跑量');
    assert.equal(String(await (await field(page, 'current_weekly_mileage_km')).value()), '42');
    assert.match(await (await page.$('.page')).text(), /当前不可生成/);
    checks.push('plan_explicit_autofill_and_quota_guard');
    await mini.navigateBack();
    } else {
      console.log(JSON.stringify({ status: 'BLOCKED', scope: 'NATIVE_FORM_INTERACTION', reason: 'AUTOMATOR_CANNOT_SELECT_VIRTUAL_HOST_INPUTS', componentCoverage: 'Run npm run test:components separately; not native input acceptance.' }));
      page = await mini.navigateTo('/pages/workspace/ai-plan');
      await waitFor(page, async () => (await (await page.$('.page')).text()).includes('今日剩余额度 0'), 'plan quota and context');
      assert.match(await (await page.$('.page')).text(), /合成数据：同步覆盖未核实/);
      assert.match(await (await page.$('.page')).text(), /当前不可生成/);
      checks.push('plan_context_and_zero_quota_visible');
      await mini.navigateBack();
    }
    page = await mini.navigateTo('/pages/workspace/sync');
    await waitFor(page, async () => (await (await page.$('.page')).text()).includes('#900051'));
    assert.match(await (await page.$('.page')).text(), /AUTO_SYNC_DISABLED/);
    assert.match(await (await page.$('.page')).text(), /未确认提交入库/);
    checks.push('sync_terminal_failure_not_reported_as_success');
    await mini.navigateBack();
    page = await mini.switchTab('/pages/profile/index'); await waitFor(page, '.logout-button');
    await (await page.$('scroll-view')).scrollTo(0, 2000);
    await (await page.$('.logout-button')).trigger('tap');
    await waitFor(page, async () => (await mini.currentPage()).path === 'pages/auth/login');
    assert.equal(await mini.evaluate(key => !!wx.getStorageSync(key), tokenKey), false);
    checks.push('logout_clears_test_session');
    assert.equal(exceptions.length, 0, 'Runtime exception occurred; inspect private tool console.');
    console.log(JSON.stringify({ status: formAutomation ? 'PASS' : 'PARTIAL', mode: 'WECHAT_SIMULATOR_SYNTHETIC_TRANSPORT', checks, nativeFormInteraction: formAutomation ? 'PASS' : 'BLOCKED', realBackend: false, realDevice: false }));
  } catch (error) {
    console.error(JSON.stringify({ status: 'ASSERTION_FAILED', completedChecks: checks, reason: String(error.message || error).slice(0, 500) }));
    throw error;
  } finally {
    if (changed) {
      // Only test-owned identity is removed. No real session is accepted above.
      const hasSyntheticToken = await mini.evaluate(key => wx.getStorageSync(key) === 'synthetic-ui-test-not-a-real-jwt', tokenKey);
      if (hasSyntheticToken) {
        const profile = await mini.switchTab('/pages/profile/index');
        await waitFor(profile, '.hero-title', 'test cleanup profile');
        await (await profile.$('scroll-view')).scrollTo(0, 2000);
        await (await profile.$('.logout-button')).trigger('tap');
      }
      await mini.evaluate(() => { delete getApp().__mobileSmoke; });
      await mini.evaluate((token, base, before) => {
        wx.removeStorageSync(token);
        if (before) wx.setStorageSync(base, before); else wx.removeStorageSync(base);
      }, tokenKey, baseKey, previousBase);
      await mini.reLaunch('/pages/auth/login').catch(() => {});
      await mini.restoreWxMethod('request');
    }
    await mini.disconnect();
  }
}
run().catch(error => { console.error(JSON.stringify({ status: 'FAIL', mode: 'WECHAT_SIMULATOR_SYNTHETIC_TRANSPORT', completedChecks: checks,
  reason: String(error.message || error).slice(0, 500) })); process.exitCode = 1; });
