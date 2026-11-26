const { test } = require('node:test');
const assert = require('node:assert/strict');
const { DownloadClient, exportPath } = require('../.test-build/services/downloads');
const { AuthSession } = require('../.test-build/services/auth/session');
function fixture(base = 'https://synthetic.invalid/api') {
  let options, epoch = 1, invalidated = false, aborted = false; const removed = [], opened = [];
  const client = new DownloadClient({ download(value) { options = value; return { abort() { aborted = true; } }; }, remove(path) { removed.push(path); }, async open(path, fileType) { opened.push({ path, fileType }); } }, () => base, { token: () => 'synthetic-token', epoch: () => epoch, invalidate() { invalidated = true; epoch++; } });
  return { client, removed, opened, get options() { return options; }, get invalidated() { return invalidated; }, get aborted() { return aborted; }, switchAccount() { epoch++; } };
}
test('export routes are allowlisted; IDs and formats cannot inject paths or queries', () => {
  assert.equal(exportPath('plan-template'), '/plan-imports/template');
  assert.equal(exportPath('workout-template'), '/workout-imports/template');
  assert.equal(exportPath('ai-draft', 900101, 'xlsx'), '/ai-plan/drafts/900101/export?format=xlsx');
  for (const id of [0, -1, 1.5, '1/../../users', Number.MAX_SAFE_INTEGER + 1]) assert.throws(() => exportPath('ai-draft', id));
  assert.throws(() => exportPath('ai-draft', 1, 'xlsx&user_id=2')); assert.throws(() => exportPath('https://external.invalid'));
});
test('download only sends identity to the configured HTTPS API and opens an owned file with its format', async () => {
  const state = fixture(), operation = state.client.read('ai-draft', 900101);
  assert.equal(state.options.url, 'https://synthetic.invalid/api/ai-plan/drafts/900101/export?format=xlsx');
  assert.deepEqual(state.options.header, { Authorization: 'Bearer synthetic-token' });
  state.options.success({ statusCode: 200, tempFilePath: 'synthetic-temp-01' }); const file = await operation.promise;
  await state.client.open(file); assert.deepEqual(state.opened, [{ path: 'synthetic-temp-01', fileType: 'xlsx' }]);
  await assert.rejects(state.client.open({ ...file }), error => error.code === 'CANCELLED');
  state.client.releaseAll(); assert.deepEqual(state.removed, ['synthetic-temp-01']);
  await assert.rejects(state.client.open(file), error => error.code === 'CANCELLED');
});
test('late result after identity change is discarded and its temporary file is removed', async () => {
  const state = fixture(), operation = state.client.read('plan-template'); state.switchAccount();
  state.options.success({ statusCode: 401, tempFilePath: 'synthetic-late-file' });
  await assert.rejects(operation.promise, error => error.code === 'CANCELLED'); assert.equal(state.invalidated, false); assert.deepEqual(state.removed, ['synthetic-late-file']);
});
test('cancel aborts local download; a late file is still cleaned up', async () => {
  const state = fixture(), operation = state.client.read('workout-template'); operation.cancel();
  await assert.rejects(operation.promise, error => error.code === 'CANCELLED'); assert.equal(state.aborted, true);
  state.options.success({ statusCode: 200, tempFilePath: 'synthetic-cancelled-file' }); assert.deepEqual(state.removed, ['synthetic-cancelled-file']);
});
test('HTTP failures do not open error documents and distinguish expired identity', async () => {
  for (const statusCode of [401, 403, 429, 500]) {
    const state = fixture(), operation = state.client.read('plan-template'); state.options.success({ statusCode, tempFilePath: 'synthetic-error-file' });
    await assert.rejects(operation.promise, error => error.status === statusCode); assert.equal(state.opened.length, 0); assert.equal(state.invalidated, statusCode === 401); assert.deepEqual(state.removed, ['synthetic-error-file']);
  }
});
test('unconfigured or non-HTTPS destination receives no credentials', () => {
  for (const base of ['http://synthetic.invalid/api', 'https://example.invalid/api', 'https://synthetic.invalid/not-api']) { const state = fixture(base); assert.throws(() => state.client.read('plan-template')); assert.equal(state.options, undefined); }
});
test('identity cleanup runs after token clearing and a cleanup failure cannot restore the identity', () => {
  let removed = false; const state = { token: null, user: null, ready: false }; const session = new AuthSession(state, { get: () => 'synthetic-token', set() {}, remove() { removed = true; } });
  let called = 0; session.onInvalidate(() => { assert.equal(state.token, null); called++; throw new Error('synthetic-cleanup-failure'); });
  session.logout(); assert.equal(removed, true); assert.equal(called, 1); assert.equal(state.user, null); assert.equal(state.ready, true);
});
test('synchronous platform exceptions never expose raw diagnostic strings', async () => {
  const client = new DownloadClient({ download() { throw new Error('SYNTHETIC_PRIVATE_DIAGNOSTIC'); }, remove() {}, async open() {} }, () => 'https://synthetic.invalid/api', { token: () => 'synthetic', epoch: () => 1, invalidate() {} });
  await assert.rejects(client.read('plan-template').promise, error => error.code === 'DOWNLOAD_FAILED' && !error.message.includes('SYNTHETIC_PRIVATE'));
});
