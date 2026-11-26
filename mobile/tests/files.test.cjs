const { test } = require('node:test');
const assert = require('node:assert/strict');
const { FileClient, validateFile } = require('../.test-build/services/files');
const file = { name: 'synthetic.xlsx', path: 'synthetic-local-file', size: 1024 };
const key = 'synthetic-import-request-01';
function fixture(base = 'https://synthetic.invalid/api') {
  let options, aborted = false, epoch = 1, invalidated = false;
  const client = new FileClient(value => { options = value; return { abort() { aborted = true; } }; }, () => base, { token: () => 'synthetic-token', epoch: () => epoch, invalidate() { invalidated = true; epoch++; } });
  return { client, get options() { return options; }, get aborted() { return aborted; }, get invalidated() { return invalidated; }, switchAccount() { epoch++; } };
}
test('upload validates extension and bounded size before a platform call', () => {
  validateFile(file);
  for (const item of [{ ...file, name: 'synthetic.exe' }, { ...file, size: 0 }, { ...file, size: 2 * 1024 * 1024 + 1 }, { ...file, path: '' }]) assert.throws(() => validateFile(item));
});
test('multipart targets a fixed API route without overriding Content-Type boundary', async () => {
  const state = fixture(), operation = state.client.send('plan', file, { client_request_id: key }, key);
  assert.equal(state.options.url, 'https://synthetic.invalid/api/plan-imports/file');
  assert.equal(state.options.header['Content-Type'], undefined); assert.equal(state.options.header.Authorization, 'Bearer synthetic-token');
  assert.equal(state.options.header['Idempotency-Key'], key);
  state.options.success({ statusCode: 200, data: '{"import_id":900081}' });
  assert.deepEqual(await operation.promise, { import_id: 900081 });
});
test('untrusted URL, import kind and malformed key never receive a file or credential', () => {
  for (const base of ['http://synthetic.invalid/api', 'https://example.invalid/api', 'https://synthetic.invalid/other']) { const state = fixture(base); assert.throws(() => state.client.send('plan', file, {}, key)); assert.equal(state.options, undefined); }
  const state = fixture(); assert.throws(() => state.client.send('../../users', file, {}, key)); assert.throws(() => state.client.send('plan', file, {}, 'bad\r\nkey')); assert.equal(state.options, undefined);
});
test('late upload after account change cannot populate new account or invalidate it', async () => {
  const state = fixture(), operation = state.client.send('workout', file, {}, key); state.switchAccount();
  state.options.success({ statusCode: 401, data: '{"private":"synthetic"}' });
  await assert.rejects(operation.promise, error => error.code === 'CANCELLED'); assert.equal(state.invalidated, false);
});
test('cancelling upload stops local transport but does not claim server rollback', async () => {
  const state = fixture(), operation = state.client.send('workout', file, {}, key); operation.cancel();
  await assert.rejects(operation.promise, error => error.code === 'CANCELLED' && error.message.includes('不代表服务端停止'));
  assert.equal(state.aborted, true);
});
test('upload errors and malformed response are safe and never automatically retried', async () => {
  for (const statusCode of [403, 413, 429, 500]) {
    const state = fixture(), operation = state.client.send('plan', file, {}, key);
    state.options.success({ statusCode, data: 'SYNTHETIC_PRIVATE_RESPONSE' });
    await assert.rejects(operation.promise, error => error.status === statusCode && !error.message.includes('SYNTHETIC_PRIVATE_RESPONSE'));
  }
  const state = fixture(), operation = state.client.send('plan', file, {}, key);
  state.options.success({ statusCode: 200, data: 'not-json' }); await assert.rejects(operation.promise, error => error.code === 'BAD_RESPONSE');
});
test('current account 401 clears identity, timeout does not', async () => {
  const first = fixture(), one = first.client.send('plan', file, {}, key); first.options.success({ statusCode: 401, data: '{}' }); await assert.rejects(one.promise); assert.equal(first.invalidated, true);
  const second = fixture(), two = second.client.send('plan', file, {}, key); second.options.fail({ errCode: 5 }); await assert.rejects(two.promise, error => error.code === 'TIMEOUT'); assert.equal(second.invalidated, false);
});
test('platform upload exceptions are sanitized instead of exposing credentials or paths', async () => {
  const client = new FileClient(() => { throw new Error('SYNTHETIC_PRIVATE_DIAGNOSTIC'); }, () => 'https://synthetic.invalid/api', { token: () => 'synthetic', epoch: () => 1, invalidate() {} });
  await assert.rejects(client.send('plan', file, {}, key).promise, error => error.code === 'UPLOAD_FAILED' && !error.message.includes('SYNTHETIC_PRIVATE'));
});
