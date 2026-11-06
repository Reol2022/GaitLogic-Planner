import { describe, expect, it } from "vitest";
import { coachEntry, coachEntryPrompt, localDate, preferenceKey, syncNextStep } from "./coreExperience";

const token = (sub: string) => `header.${btoa(JSON.stringify({ sub }))}.signature`;
describe('core experience contracts', () => {
  it('isolates UX preferences without putting tokens in storage keys', () => {
    const a = preferenceKey(token('1'), 'guide');
    expect(a).not.toBe(preferenceKey(token('2'), 'guide'));
    expect(a).not.toContain('signature');
    expect(preferenceKey(null, 'guide')).toBeNull();
    expect(preferenceKey('invalid', 'guide')).toBeNull();
    expect(preferenceKey(token('../other'), 'guide')).toBeNull();
  });
  it('uses a local calendar date rather than a UTC day', () => {
    expect(localDate(new Date(2026, 0, 1, 0, 1))).toBe('2026-01-01');
  });
  it('keeps coach launch routes bounded and questions explicit', () => {
    expect(coachEntry('today', '2026-11-05')).toEqual({ path: '/coach', query: { topic: 'today', date: '2026-11-05' } });
    expect(coachEntryPrompt('today', '2026-11-05')).toContain('2026-11-05');
    expect(coachEntryPrompt('plan', null)).toContain('不修改正式计划');
    expect(coachEntryPrompt('delete_plan', null)).toBeNull();
    expect(coachEntryPrompt('__proto__', null)).toBeNull();
    expect(coachEntryPrompt('today', '<script>')).not.toContain('<script>');
  });
  it('does not confuse queued, fetched and committed data', () => {
    expect(syncNextStep('queued')).toContain('尚未开始');
    expect(syncNextStep('running')).toContain('不代表全部活动已提交');
    expect(syncNextStep('partially_succeeded')).toContain('部分数据已提交');
    expect(syncNextStep('failed', 'TOKEN_DECRYPTION_FAILED')).toContain('重新认证');
    expect(syncNextStep('failed', 'RATE_LIMITED')).toContain('不要频繁重试');
  });
});
