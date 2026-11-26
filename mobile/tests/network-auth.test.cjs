const { test } = require('node:test');
const assert = require('node:assert/strict');
const { ApiClient, ApiError } = require('../.test-build/services/api/client');
const { AuthSession, TOKEN_KEY } = require('../.test-build/services/auth/session');
const base = () => 'https://synthetic.invalid/api';
function memory(initial) { const map = new Map(initial || []); return { get: key => map.get(key) || null,
  set: (key, value) => map.set(key, value), remove: key => map.delete(key), map }; }
function mock(handler) {
  const calls = []; return { calls, request(options) { calls.push(options); let reject;
    const promise = new Promise((yes, no) => { reject = no; Promise.resolve().then(() => handler(options)).then(yes, no); });
    return { promise, cancel() { reject(new Error('CANCELLED')); } }; } };
}
function account(transport, storage = memory()) {
  const session = new AuthSession({ token: null, user: null, ready: false }, storage);
  const api = new ApiClient(transport, base, { token: () => session.state.token,
    epoch: () => session.epoch(), invalidate: () => session.invalidate() });
  session.connect(api); return { session, api, storage };
}
test('login uses original JSON contract and only stores token', async () => {
  const transport = mock(o => ({ status: 200, data: o.url.endsWith('/login') ? { access_token: 'synthetic-token' } : { id: 11, username: 'runner-a' } }));
  const { session, storage } = account(transport);
  await session.login('runner-a', 'SYNTHETIC_NOT_A_REAL_PASSWORD');
  assert.equal(session.state.user.id, 11); assert.equal(storage.get(TOKEN_KEY), 'synthetic-token');
  assert.equal(storage.map.size, 1); assert.equal(transport.calls[1].headers.Authorization, 'Bearer synthetic-token');
});
test('failed login clears prior user and shows actionable text', async () => {
  const { session } = account(mock(() => ({ status: 401, data: {} })));
  session.state.user = { id: 9 }; session.state.token = 'old';
  await assert.rejects(session.login('a', 'bad'), e => e.status === 401 && /密码/.test(e.message));
  assert.equal(session.state.user, null); assert.equal(session.state.token, null);
});
test('startup restores identity from stored token without persisting profile', async () => {
  const { session, storage } = account(mock(() => ({ status: 200, data: { id: 12, username: 'runner-b' } })), memory([[TOKEN_KEY, 'stored']]));
  await Promise.all([session.restore(), session.restore()]);
  assert.equal(session.state.user.id, 12); assert.equal(storage.map.size, 1);
});
test('expired token clears identity on restore', async () => {
  const { session, storage } = account(mock(() => ({ status: 401 })), memory([[TOKEN_KEY, 'expired']]));
  await assert.rejects(session.restore(), e => e.code === 'UNAUTHENTICATED');
  assert.equal(storage.get(TOKEN_KEY), null); assert.equal(session.state.user, null);
});
test('network outage does not erase stored credentials', async () => {
  const { session } = account(mock(() => { throw new Error('SECRET_NETWORK_DIAGNOSTIC'); }), memory([[TOKEN_KEY, 'stored']]));
  await assert.rejects(session.restore(), e => e.code === 'NETWORK' && !e.message.includes('SECRET'));
  assert.equal(session.state.token, 'stored');
});
test('logout aborts in-flight calls and cannot repopulate previous account', async () => {
  let resolve;
  const { session, api } = account(mock(() => new Promise(r => { resolve = r; })));
  session.state.token = 'a'; session.state.user = { id: 1 };
  const request = api.get('/mobile/training'); const result = assert.rejects(request.promise, e => e.code === 'CANCELLED');
  await Promise.resolve(); await Promise.resolve(); session.logout();
  resolve?.({ status: 200, data: { private: 'synthetic-a' } }); await result;
  assert.equal(session.state.user, null);
});
test('stale response after identity change is rejected even if transport cannot abort', async () => {
  let resolve; let epoch = 1, invalidations = 0;
  const transport = { request: () => ({ promise: new Promise(r => { resolve = r; }), cancel() {} }) };
  const api = new ApiClient(transport, base, { token: () => 'b', epoch: () => epoch, invalidate: () => invalidations++ });
  const request = api.get('/auth/me'); epoch++;
  resolve({ status: 401 }); await assert.rejects(request.promise, e => e.code === 'CANCELLED');
  assert.equal(invalidations, 0);
});
test('all five methods are transported without automatic retries', async () => {
  const transport = mock(() => ({ status: 200, data: {} })); const { api } = account(transport);
  for (const verb of ['get', 'post', 'put', 'patch', 'delete']) await api[verb]('/synthetic').promise;
  assert.deepEqual(transport.calls.map(c => c.method), ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']);
});
for (const status of [400, 403, 404, 409, 429, 500, 503]) test(`HTTP ${status} is safe and not retried`, async () => {
  const transport = mock(() => ({ status, data: { message: 'SECRET_PROVIDER_BODY' }, headers: { 'Retry-After': '30' } }));
  const { api } = account(transport);
  await assert.rejects(api.post('/synthetic').promise, e => e.status === status && !e.message.includes('SECRET') && e.retryAfter === 30);
  assert.equal(transport.calls.length, 1);
});
test('timeout and user cancellation are separate safe categories', async () => {
  const { api } = account(mock(() => { throw new Error('TIMEOUT'); }));
  await assert.rejects(api.get('/synthetic').promise, e => e.code === 'TIMEOUT');
  const pending = account(mock(() => new Promise(() => {}))).api.get('/synthetic');
  pending.cancel(); await assert.rejects(pending.promise, e => e.code === 'CANCELLED');
});
test('external URLs and unconfigured environments never receive tokens', () => {
  const transport = mock(() => ({ status: 200 })); const { api } = account(transport);
  for (const path of ['https://evil.invalid', '//evil.invalid', '/a/../b']) assert.throws(() => api.get(path), ApiError);
  const unconfigured = new ApiClient(transport, () => 'https://example.invalid/api', { token: () => 'secret', epoch: () => 0, invalidate() {} });
  assert.throws(() => unconfigured.get('/auth/me'), e => e.code === 'CONFIG_REQUIRED');
  assert.equal(transport.calls.length, 0);
});
test('malformed login response is not persisted as an undefined credential', async () => {
  const { session, storage } = account(mock(() => ({ status: 200, data: {} })));
  await assert.rejects(session.login('synthetic', 'synthetic'), e => e.code === 'BAD_RESPONSE');
  assert.equal(storage.get(TOKEN_KEY), null);
});
test('environment names keep token storage isolated', () => {
  const storage = memory([[TOKEN_KEY + '.development', 'synthetic-dev']]);
  const production = new AuthSession({ token: null, user: null, ready: false }, storage, TOKEN_KEY + '.production');
  assert.equal(production.state.token, null);
  const development = new AuthSession({ token: null, user: null, ready: false }, storage, TOKEN_KEY + '.development');
  assert.equal(development.state.token, 'synthetic-dev');
  production.logout(); assert.equal(development.state.token, 'synthetic-dev');
});
test('MCP OAuth challenge on a REST path does not clear Web identity or retry', async () => {
  const transport = mock(() => ({ status: 401, headers: {
    'www-authenticate': 'Bearer resource_metadata="https://synthetic.invalid/.well-known/oauth-protected-resource/mcp"',
  } }));
  const { session, api, storage } = account(transport);
  session.state.token = 'synthetic-web-token'; session.state.user = { id: 11 };
  storage.set(TOKEN_KEY, 'synthetic-web-token');
  await assert.rejects(api.get('/mobile/training').promise, error => error.code === 'API_PROTOCOL_MISMATCH');
  assert.equal(session.state.token, 'synthetic-web-token');
  assert.equal(session.state.user.id, 11);
  assert.equal(storage.get(TOKEN_KEY), 'synthetic-web-token');
  assert.equal(transport.calls.length, 1);
});
