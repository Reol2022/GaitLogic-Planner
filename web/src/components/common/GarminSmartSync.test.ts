import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { flushPromises, mount } from '@vue/test-utils';
import Banner from './GarminSmartSyncBanner.vue';
import Settings from './GarminSmartSyncSettings.vue';
import { checkSmartSync, getSmartSync, saveSmartSync, type SyncFreshness } from '@/api/smartSync';

vi.mock('@/api/smartSync', () => ({ checkSmartSync: vi.fn(), getSmartSync: vi.fn(), saveSmartSync: vi.fn() }));
const value = (status: string): SyncFreshness => ({ status, scope: 'all', enabled: true, interval_minutes: 30,
  recovery_enabled: false, job_id: null, error_category: null, last_success_at: null,
  last_success_by_scope: {}, next_retry_at: null });
beforeEach(() => { vi.resetAllMocks(); vi.useFakeTimers(); });
afterEach(() => { vi.useRealTimers(); });

describe('Smart Sync feedback', () => {
  it('does not display or poll fresh data', async () => {
    vi.mocked(checkSmartSync).mockResolvedValue(value('FRESH'));
    const wrapper = mount(Banner); await flushPromises();
    expect(wrapper.text()).toBe('');
    await vi.advanceTimersByTimeAsync(30000);
    expect(getSmartSync).not.toHaveBeenCalled(); wrapper.unmount();
  });
  it('polls real queued state and refreshes facts after completion', async () => {
    vi.mocked(checkSmartSync).mockResolvedValue(value('QUEUED'));
    vi.mocked(getSmartSync).mockResolvedValue(value('FRESH'));
    const listener = vi.fn(); window.addEventListener('garmin-facts-updated', listener);
    const wrapper = mount(Banner); await flushPromises();
    expect(wrapper.text()).toContain('正在更新 Garmin');
    await vi.advanceTimersByTimeAsync(3500); await flushPromises();
    expect(wrapper.text()).toBe(''); expect(listener).toHaveBeenCalledOnce();
    wrapper.unmount(); window.removeEventListener('garmin-facts-updated', listener);
  });
  it('stops polling on unmount', async () => {
    vi.mocked(checkSmartSync).mockResolvedValue(value('RUNNING'));
    const wrapper = mount(Banner); await flushPromises(); wrapper.unmount();
    await vi.advanceTimersByTimeAsync(30000);
    expect(getSmartSync).not.toHaveBeenCalled();
  });
  it('isolates coordinator outages without automatic retry storms', async () => {
    vi.mocked(checkSmartSync).mockRejectedValue(new Error('synthetic failure'));
    const wrapper = mount(Banner); await flushPromises();
    await vi.advanceTimersByTimeAsync(30000);
    expect(checkSmartSync).toHaveBeenCalledOnce(); expect(wrapper.text()).toBe(''); wrapper.unmount();
  });
  it('keeps recovery opt-in separate and saves explicit user choices', async () => {
    vi.mocked(getSmartSync).mockResolvedValue(value('STALE'));
    vi.mocked(saveSmartSync).mockResolvedValue(value('STALE'));
    const wrapper = mount(Settings, { global: { stubs: { ElButton: { template: '<button><slot /></button>' } } } });
    await flushPromises();
    const boxes = wrapper.findAll('input');
    expect((boxes[1].element as HTMLInputElement).checked).toBe(false);
    await boxes[1].setValue(true);
    await wrapper.find('select').setValue('60');
    await wrapper.find('button').trigger('click'); await flushPromises();
    expect(saveSmartSync).toHaveBeenCalledWith({ enabled: true, interval_minutes: 60, recovery_enabled: true });
    wrapper.unmount();
  });
  it('hides settings before server-side feature enablement', async () => {
    vi.mocked(getSmartSync).mockResolvedValue(value('DISABLED'));
    const wrapper = mount(Settings); await flushPromises();
    expect(wrapper.find('section').exists()).toBe(false); wrapper.unmount();
  });
});
