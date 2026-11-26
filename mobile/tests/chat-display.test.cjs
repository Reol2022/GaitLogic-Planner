const { test } = require('node:test');
const assert = require('node:assert/strict');
const { Utf8Chunks, SseProbe } = require('../.test-build/services/chat/stream-parser');
const { ChatService } = require('../.test-build/services/chat/service');
const { metric, duration, pace, effort, dateOffset, weekStart, sourceLabel, messageStatus, connectionStatus } = require('../.test-build/utils/display');
const { markdownBlocks } = require('../.test-build/utils/markdown');
const bytes = text => Uint8Array.from(Buffer.from(text)).buffer;
test('UTF-8 Chinese survives every byte boundary', () => {
  const text = '洛教练：今天跑步🏃'; const input = new Uint8Array(bytes(text));
  for (let split = 1; split < input.length; split++) {
    const decoder = new Utf8Chunks();
    assert.equal(decoder.push(input.slice(0, split).buffer) + decoder.push(input.slice(split).buffer), text); decoder.finish();
  }
});
test('SSE events survive per-byte chunking and multiple events in a chunk', () => {
  const parser = new SseProbe(), events = [];
  const input = new Uint8Array(bytes('event: token\r\ndata: 你好\r\n\r\ndata: 第二条\n\ndata: [DONE]\n\n'));
  for (const byte of input) events.push(...parser.push(Uint8Array.of(byte).buffer));
  assert.deepEqual(events, [{ type: 'token', data: '你好' }, { type: 'message', data: '第二条' }]);
  assert.equal(parser.done, true); parser.finish();
  const combined = new SseProbe();
  assert.equal(combined.push(bytes('data: a\n\ndata: b\n\n')).length, 2);
});
test('SSE server error event is exposed, not rendered as success', () => {
  const parser = new SseProbe();
  assert.deepEqual(parser.push(bytes('event: error\ndata: unavailable\n\n')), [{ type: 'error', data: 'unavailable' }]);
});
test('incomplete UTF8 and broken event endings are rejected', () => {
  const decoder = new Utf8Chunks(); decoder.push(Uint8Array.of(0xe4).buffer);
  assert.throws(() => decoder.finish(), /TRUNCATED/);
  const parser = new SseProbe(); parser.push(bytes('data: unfinished'));
  assert.throws(() => parser.finish(), /TRUNCATED/);
});
test('oversized streaming events are rejected', () => {
  const parser = new SseProbe(); assert.throws(() => parser.push(bytes('data: ' + 'x'.repeat(70000))), /TOO_LARGE/);
});
test('real Chat contract uses one JSON response and preserves idempotency identifier', async () => {
  let posted;
  const api = { get() { throw new Error('should not poll completed request'); }, post(path, data) {
    posted = { path, data }; return { promise: Promise.resolve({ status: 'completed', content: '合成回答' }), cancel() {} };
  } };
  const chat = new ChatService(api); const result = await chat.send('session-a', '合成问题', 'mobile_fixed_001').promise;
  assert.equal(chat.transportMode, 'JSON_WITH_STATUS_POLLING'); assert.equal(result.content, '合成回答');
  assert.equal(posted.data.client_turn_id, 'mobile_fixed_001');
});
test('cancel aborts transport without claiming the server task stopped', async () => {
  let reject, cancellations = 0;
  const chat = new ChatService({ post() { return { promise: new Promise((_, no) => { reject = no; }), cancel() { cancellations++; reject(new Error('CANCELLED')); } }; } });
  const request = chat.send('a', 'synthetic', 'mobile_fixed_002'); request.cancel();
  await assert.rejects(request.promise, /CANCELLED/); assert.equal(cancellations, 1);
});
test('missing health metrics do not become zero', () => {
  for (const value of [null, undefined, '', NaN]) assert.equal(metric(value), '暂无');
  assert.equal(metric(0, ' km'), '0 km'); assert.equal(pace(null), '暂无'); assert.equal(duration(null), '暂无');
});
test('activity RPE accepts only normalized 1-10 ratings, never a raw scale or default zero', () => {
  for (const value of [null, undefined, '', false, '2', 0, -1, 2.5, 20, 100, NaN]) assert.equal(effort(value), '暂无');
  assert.equal(effort(2), '2/10');
  assert.equal(effort(10), '10/10');
});
test('runner-facing labels localize known statuses without treating unknown as success', () => {
  assert.equal(sourceLabel('MANUAL'), '手动记录');
  assert.equal(sourceLabel('GARMIN'), '佳明同步');
  assert.equal(messageStatus('completed'), '已完成');
  assert.equal(messageStatus('unexpected'), '状态待确认');
  assert.equal(connectionStatus('DISCONNECTED'), '尚未连接');
  assert.equal(connectionStatus(null), '状态待确认');
});
test('date windows follow the supplied server day and calendar week', () => {
  assert.equal(weekStart('2026-06-21'), '2026-06-15');
  assert.equal(dateOffset('2026-03-01', -1), '2026-02-28');
  assert.equal(pace(299.9), '5:00/km');
});
test('Markdown stays text, including untrusted HTML and long content', () => {
  const blocks = markdownBlocks('# 标题\n- 项目\n```\n<script>not executed</script>\n```');
  assert.equal(blocks[0].kind, 'heading'); assert.equal(blocks[1].kind, 'list');
  assert.equal(blocks[2].kind, 'code'); assert(blocks[2].text.includes('<script>'));
  assert(markdownBlocks('长'.repeat(70000)).map(b => b.text).join('').length <= 60000);
});
