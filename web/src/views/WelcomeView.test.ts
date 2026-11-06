import { flushPromises, shallowMount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import WelcomeView from './WelcomeView.vue';
import { preferenceKey } from '@/utils/coreExperience';
const state = vi.hoisted(() => ({ push: vi.fn(), token: '' }));
vi.mock('vue-router', () => ({ useRouter: () => ({ push: state.push }) }));
vi.mock('@/api/auth', () => ({ getStoredToken: () => state.token }));
vi.mock('@/api/usageEvents', () => ({ trackUsageEvent: vi.fn() }));
function page() { return shallowMount(WelcomeView, { global: { stubs: { ElButton: { template: '<button @click="$emit(\'click\')"><slot /></button>' }, RouterLink: true } } }); }
describe('task-based onboarding', () => {
  beforeEach(() => { localStorage.clear(); vi.clearAllMocks(); state.token = `header.${btoa(JSON.stringify({ sub: '101' }))}.signature`; });
  it('supports a record-only path without forcing a plan or device', async () => {
    const w = page();
    await w.findAll('button').find(b => b.text().includes('先记录和了解训练'))!.trigger('click');
    await w.findAll('button').find(b => b.text().includes('稍后连接'))!.trigger('click');
    await w.findAll('button').find(b => b.text().includes('查看记录入口'))!.trigger('click');
    expect(state.push).toHaveBeenCalledWith('/dashboard');
    expect(localStorage.getItem(preferenceKey(state.token, 'welcome-dismissed')!)).toBe('1');
    w.unmount();
  });
  it('restores choices only for the same account', async () => {
    const w = page();
    await w.findAll('button').find(b => b.text().includes('AI 帮我'))!.trigger('click');
    w.unmount();
    const restored = page(); await flushPromises();
    expect(restored.text()).toContain('第 2 / 3 步'); restored.unmount();
    state.token = `header.${btoa(JSON.stringify({ sub: '202' }))}.signature`;
    const other = page(); await flushPromises();
    expect(other.text()).toContain('第 1 / 3 步'); other.unmount();
  });
});
