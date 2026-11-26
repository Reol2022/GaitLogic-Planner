const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { resourceFor, resources, positiveId, formPayload, valuesFor, changedPayload } = require('../.test-build/domain/runner-workspace');
const { planPayload, planEnd } = require('../.test-build/domain/plan-form');
const { convert, clock } = require('../.test-build/domain/pace');
const { PageScope } = require('../.test-build/services/page-scope');
const { ApiClient } = require('../.test-build/services/api/client');
const root = path.resolve(__dirname, '..');
test('workspace resources are an explicit whitelist, with no authority or ownership fields', () => {
  assert.throws(() => resourceFor('admin'));
  assert.throws(() => resourceFor('../../users'));
  for (const resource of resources) {
    assert.ok(resource.endpoint.startsWith('/'));
    for (const field of resource.fields) assert.doesNotMatch(field.key, /^(user_id|role|source_type|field_sources_json|status|is_locked|plan_version)$/);
  }
});
test('only positive safe IDs may enter resource paths', () => {
  assert.equal(positiveId('328'), 328);
  for (const value of [null, '', '-1', '0', '1e3', '1/2', '../1', '1?user_id=2', 1.5, Number.MAX_SAFE_INTEGER + 1]) assert.throws(() => positiveId(value));
});
test('form payload preserves missing values as null, not zero, and strips injected fields', () => {
  const fields = [{ key: 'rpe', label: 'RPE', kind: 'number', min: 1, max: 10, integer: true }];
  assert.deepEqual(formPayload(fields, { rpe: '', user_id: '2' }), { rpe: null });
  assert.deepEqual(formPayload(fields, { rpe: '2' }), { rpe: 2 });
  for (const rpe of ['0', '11', '2.5', 'NaN', 'Infinity']) assert.throws(() => formPayload(fields, { rpe }));
});
test('partial update submits changed fields only, leaving Garmin metrics and notes untouched', () => {
  const fields = [{ key: 'rpe', label: 'RPE', kind: 'number' }, { key: 'review_note', label: '笔记' }];
  const original = valuesFor(fields, { rpe: null, review_note: '合成原有笔记', actual_distance_km: 12 });
  assert.deepEqual(changedPayload(fields, { ...original, rpe: '4' }, original), { rpe: 4 });
  assert.deepEqual(changedPayload(fields, original, original), {});
});
test('invalid dates and inverted intervals are rejected', () => {
  const fields = resourceFor('cycles').fields;
  assert.throws(() => formPayload(fields, { name: '合成周期', start_date: '2026-02-30' }));
  assert.throws(() => formPayload(fields, { name: '合成周期', start_date: '2026-12-02', end_date: '2026-12-01' }));
});
function plan(overrides = {}) { return { runner_level: 'intermediate', current_weekly_mileage_km: '40', recent_4w_avg_mileage_km: '38', available_training_days_per_week: '4', target_distance: 'half_marathon', plan_start_date: '2026-12-01', plan_weeks: '8', intensity_style: 'standard', can_double_run: 'false', ...overrides }; }
test('plan context uses user input, real booleans and explicit constraint arrays', () => {
  const payload = planPayload(plan({ fixed_rest_days: '周一,周一,周五', excluded_workout_types: 'I,R' }), { 周二: '45' });
  assert.equal(payload.can_double_run, false);
  assert.equal(payload.current_weekly_mileage_km, 40);
  assert.deepEqual(payload.fixed_rest_days, ['周一', '周五']);
  assert.deepEqual(payload.daily_available_minutes, { 周二: 45 });
  assert.deepEqual(payload.excluded_workout_types, ['I', 'R']);
  assert.equal(payload.use_training_context, true);
});
test('missing running basis is not fabricated as zero and source fields cannot be injected', () => {
  assert.throws(() => planPayload(plan({ current_weekly_mileage_km: '' }), {}));
  const payload = planPayload(plan({ user_id: '2', verified_pb: 'true' }), {});
  assert.equal(payload.user_id, undefined); assert.equal(payload.verified_pb, undefined);
});
test('rest days, training days, daily time and PB completeness are validated', () => {
  assert.throws(() => planPayload(plan({ fixed_rest_days: '周一,周二,周三,周四' }), {}));
  assert.throws(() => planPayload(plan({ fixed_rest_days: 'Monday' }), {}));
  assert.throws(() => planPayload(plan(), { 周一: '601' }));
  assert.throws(() => planPayload(plan(), { 周一: '0', 周二: '0', 周三: '0', 周四: '0', 周五: '0', 周六: '30', 周日: '30' }));
  assert.throws(() => planPayload(plan({ recent_pb_distance: 'half_marathon' }), {}));
  assert.throws(() => planPayload(plan({ excluded_workout_types: 'FAKE_TYPE' }), {}));
});
test('plan end uses inclusive calendar dates without timezone drift', () => {
  assert.equal(planEnd(plan({ plan_start_date: '2026-12-28', plan_weeks: '1' })), '2027-01-03');
  assert.equal(planEnd(plan({ plan_weeks: '0' })), '');
  assert.equal(planEnd(plan({ plan_start_date: '2026-02-30' })), '');
});
test('pace calculator handles four directions, presets and clock carry', () => {
  assert.deepEqual(convert('pace', 10, 3000, 0, 0), { km: 10, time: 3000, pace: 300, lap: 120 });
  assert.equal(convert('time', 21.0975, 0, 300, 0).time, 6329.25);
  assert.equal(convert('distance', 0, 3600, 300, 0).km, 12);
  assert.equal(convert('lap', 10, 0, 0, 80).pace, 200);
  assert.equal(convert('pace', 0, 100, 0, 0), null);
  assert.equal(convert('pace', -1, 100, 0, 0), null);
  assert.equal(clock(299.9), '5:00'); assert.equal(clock(3599.9, true), '01:00:00');
});
test('page scope rejects results from another account or hidden page', async () => {
  let epoch = 1; const scope = new PageScope(() => epoch), version = scope.begin();
  assert.equal(scope.current(version), true); epoch++;
  assert.equal(scope.current(version), false);
  const newVersion = scope.begin(); let cancelled = false;
  let resolve; const promise = scope.wait({ promise: new Promise(yes => { resolve = yes; }), cancel() { cancelled = true; } });
  scope.stop(); resolve('late'); await promise;
  assert.equal(cancelled, true); assert.equal(scope.current(newVersion), false);
});
test('sync request idempotency headers are validated and no write is retried', async () => {
  const calls = []; const client = new ApiClient({ request(options) { calls.push(options); return { promise: Promise.resolve({ status: 200, data: { id: 1 } }), cancel() {} }; } }, () => 'https://synthetic.invalid/api', { token: () => 'synthetic', epoch: () => 1, invalidate() {} });
  await client.postOnce('/integrations/garmin/sync', { sync_mode: 'incremental' }, 'synthetic-sync-request-01').promise;
  assert.equal(calls.length, 1); assert.equal(calls[0].headers['Idempotency-Key'], 'synthetic-sync-request-01');
  assert.throws(() => client.postOnce('/integrations/garmin/sync', {}, 'bad\r\nkey'));
});
test('validation feedback names safe fields without echoing input, raw errors or unknown locations', async () => {
  const client = new ApiClient({ request() { return { promise: Promise.resolve({ status: 400, data: { error: { detail: [{ loc: ['body', 'plan_weeks'], input: 'SYNTHETIC_PRIVATE_VALUE', msg: 'SYNTHETIC_PRIVATE_ERROR' }, { loc: ['body', 'SYNTHETIC_PRIVATE_LOCATION'] }] } } }), cancel() {} }; } }, () => 'https://synthetic.invalid/api', { token: () => null, epoch: () => 1, invalidate() {} });
  await assert.rejects(client.post('/ai-plan/generate', {}).promise, error => {
    assert.equal(error.message, '请检查：计划周数'); assert.doesNotMatch(error.message, /SYNTHETIC_PRIVATE/); return true;
  });
});
test('all runner workspace destinations are registered native pages, not webview fallbacks', () => {
  const config = JSON.parse(fs.readFileSync(path.join(root, 'pages.json'), 'utf8'));
  const index = fs.readFileSync(path.join(root, 'pages/workspace/index.uvue'), 'utf8');
  for (const match of index.matchAll(/path: '(\/pages\/[^'?]+)(?:\?[^']*)?'/g)) assert.ok(config.pages.some(page => '/' + page.path === match[1]), match[1]);
  assert.doesNotMatch(index, /<web-view/);
});
test('sensitive workspace forms are not persisted in local storage or written on mount', () => {
  for (const name of ['resources', 'log', 'recovery', 'ai-plan', 'preferences', 'feedback', 'sync', 'cycle-state', 'weekly', 'pace-profile', 'conversations', 'tasks', 'status', 'imports', 'exports', 'garmin-settings', 'history']) {
    const source = fs.readFileSync(path.join(root, 'pages/workspace', name + '.uvue'), 'utf8');
    assert.doesNotMatch(source, /setStorageSync|localStorage|console\.log/);
    assert.match(source, /onHide\(hide\)/);
    assert.doesNotMatch(source, /onShow\([^\n]*(?:save|generate|commit|submit|start)\(/);
  }
});
test('migration inventory covers every existing Web route and only points to registered native pages', () => {
  const routes = [...fs.readFileSync(path.join(root, '../web/src/router/index.ts'), 'utf8').matchAll(/path:\s*"([^"\n]+)"/g)].map(match => match[1]);
  const inventory = JSON.parse(fs.readFileSync(path.join(root, 'migration-map.json'), 'utf8')).routes;
  // The guard's redirect object repeats /login; compare unique route paths.
  assert.deepEqual([...new Set(inventory.map(item => item.web))].sort(), [...new Set(routes)].sort());
  const pages = JSON.parse(fs.readFileSync(path.join(root, 'pages.json'), 'utf8')).pages;
  for (const item of inventory) {
    assert.ok(['implemented', 'partial', 'pending', 'retained', 'redirect', 'infrastructure'].includes(item.state));
    if (item.native != null) assert.ok(pages.some(page => page.path === item.native), item.web);
  }
  assert.ok(inventory.some(item => item.state === 'pending'), 'Do not claim a completed migration while features remain pending.');
});
