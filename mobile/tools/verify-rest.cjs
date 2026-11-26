/* Test-only Node HTTPS transport. Not a replacement for uni.request device tests. */
const assert = require('node:assert/strict');
const https = require('node:https');
const fs = require('node:fs');
const { ApiClient } = require('../.test-build/services/api/client');
const { AuthSession, TOKEN_KEY } = require('../.test-build/services/auth/session');
const checks = [];

async function main(config) {
  const base = new URL(config.base);
  assert.equal(base.protocol, 'https:');
  assert.equal(base.hostname, '127.0.0.1');
  assert.equal(base.pathname, '/api');
  const ca = fs.readFileSync(config.caPath);
  function wire(options, tls = { ca }) {
    return new Promise((resolve, reject) => {
      const body = options.data === undefined ? undefined : JSON.stringify(options.data);
      const request = https.request(options.url, {
        ...tls, rejectUnauthorized: true, method: options.method || 'GET',
        headers: { ...options.headers, ...(body ? { 'Content-Length': Buffer.byteLength(body) } : {}) },
      }, response => {
        let raw = '';
        response.setEncoding('utf8');
        response.on('data', chunk => { raw += chunk; if (raw.length > 1024 * 1024) request.destroy(new Error('RESPONSE_LIMIT')); });
        response.on('end', () => {
          try { resolve({ status: response.statusCode, headers: response.headers, data: JSON.parse(raw) }); }
          catch { reject(new Error('INVALID_JSON')); }
        });
      });
      request.setTimeout(options.timeout || 5000, () => request.destroy(new Error('TIMEOUT')));
      request.on('error', reject);
      if (body) request.write(body);
      request.end();
      options.attach?.(request);
    });
  }
  const transport = { request(options) {
    let pending;
    const promise = wire({ ...options, attach(request) { pending = request; } });
    return { promise, cancel() { pending?.destroy(new Error('CANCELLED')); } };
  } };
  const stored = new Map();
  const storage = { get: key => stored.get(key) || null, set: (key, value) => stored.set(key, value), remove: key => stored.delete(key) };
  const auth = new AuthSession({ token: null, user: null, ready: false }, storage);
  const api = new ApiClient(transport, () => config.base, {
    token: () => auth.state.token, epoch: () => auth.epoch(), invalidate: () => auth.invalidate(),
  });
  auth.connect(api);
  try {
    await assert.rejects(wire({ url: config.base + '/auth/me' }, {}));
    checks.push('untrusted_tls_rejected');
    await assert.rejects(wire({ url: config.base + '/auth/me' }, { ca, servername: 'wrong.synthetic.invalid' }), error => error.code === 'ERR_TLS_CERT_ALTNAME_INVALID');
    checks.push('wrong_tls_hostname_rejected');
    await assert.rejects(auth.login(config.users[0].username, 'synthetic-wrong'), error => error.status === 401 && /密码/.test(error.message));
    checks.push('real_password_failure');
    await auth.login(config.users[0].username, config.password);
    assert.equal(auth.state.user.id, config.users[0].id);
    assert.equal(stored.size, 1);
    checks.push('password_jwt_me');
    const refs = [];
    let cursor = null;
    do {
      const data = await api.get('/mobile/training?days=28&limit=10' + (cursor ? '&cursor=' + encodeURIComponent(cursor) : '')).promise;
      assert.equal(data.summary.total_sessions, 25);
      assert.equal(data.summary.total_distance_km, 42.5);
      refs.push(...data.items.map(item => item.record_ref));
      cursor = data.next_cursor;
    } while (cursor);
    assert.equal(refs.length, 25);
    assert.equal(new Set(refs).size, 25);
    checks.push('unplanned_full_window_pagination');
    const series = await api.get('/mobile/series?start_date=' + config.start + '&end_date=' + config.end).promise;
    assert.equal(series.items.reduce((sum, day) => sum + day.session_count, 0), 25);
    assert.equal(series.items.reduce((sum, day) => sum + day.distance_km, 0), 42.5);
    checks.push('series_summary_consistent');
    const detail = await api.get('/mobile/training/detail?record_ref=' + encodeURIComponent(config.recordRef)).promise;
    assert.equal(detail.linked_activity_count, 3);
    assert.equal(detail.selection_required, true);
    assert.equal(detail.selected_activity, null);
    assert.equal(detail.segments.length, 0);
    const selected = await api.get('/mobile/training/detail?record_ref=' + encodeURIComponent(config.recordRef) + '&activity_ref=' + encodeURIComponent(config.activityRef)).promise;
    assert.equal(selected.selected_activity.activity_ref, config.activityRef);
    assert.equal(selected.segments.length, 2);
    checks.push('multiple_activities_explicit_selection');
    await assert.rejects(api.get('/mobile/training?days=29').promise, error => error.status === 400);
    checks.push('date_limits_preserved');
    auth.state.user = null;
    await auth.restore();
    assert.equal(auth.state.user.id, config.users[0].id);
    checks.push('stored_token_identity_restore');
    auth.logout();
    assert.equal(stored.has(TOKEN_KEY), false);
    assert.equal(auth.state.user, null);
    await assert.rejects(api.get('/mobile/training').promise, error => error.status === 401);
    checks.push('logout_removes_access');
    await auth.login(config.users[1].username, config.password);
    const other = await api.get('/mobile/training?days=28&user_id=' + config.users[0].id).promise;
    assert.equal(other.items.length, 0);
    await assert.rejects(api.get('/mobile/training/detail?record_ref=' + encodeURIComponent(config.recordRef)).promise, error => error.status === 404);
    checks.push('account_switch_object_isolation');
    auth.state.token = config.mcpToken;
    await assert.rejects(api.get('/mobile/training').promise, error => error.status === 401);
    assert.equal(auth.state.token, null);
    checks.push('mcp_token_not_web_identity');
    console.log(JSON.stringify({ status: 'PASS', mode: 'NODE_MOBILE_CLIENT_HTTPS_MYSQL', checks,
      realTcp: true, realBackend: true, uniRequest: false, realDevice: false }));
  } finally { auth.logout(); }
}
let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => { input += chunk; });
process.stdin.on('end', async () => {
  try { await main(JSON.parse(input)); }
  catch {
    console.error(JSON.stringify({ status: 'FAIL', mode: 'NODE_MOBILE_CLIENT_HTTPS_MYSQL', completedChecks: checks }));
    process.exitCode = 1;
  }
});
