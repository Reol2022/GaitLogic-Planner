import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { flushPromises, mount } from '@vue/test-utils';
import { ElMessageBox } from 'element-plus';
import System from './System.vue';
import { getConsoleSystemSettings, saveConsoleSystemSettings } from './systemSettings';
import { adminNavigation, ADMIN_SYSTEM_SETTINGS_URL } from './navigation';
import { sidebarGroups } from '@/utils/sidebarNavigation';

vi.mock('./systemSettings', () => ({ getConsoleSystemSettings: vi.fn(), saveConsoleSystemSettings: vi.fn() }));
const settings = { id: 1, auth_entry_mode: 'modal' as const, allow_public_registration: false, updated_at: '2026-01-01T12:00:00' };
const stubs = {
  ElButton: { props: ['disabled', 'loading'], template: '<button :disabled="disabled || loading"><slot /></button>' },
  ElForm: { template: '<form @submit.prevent><slot /></form>' },
  ElFormItem: { template: '<label><slot /></label>' },
  ElRadioGroup: { props: ['modelValue'], emits: ['update:modelValue'], template: '<select :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><option value="standalone">单独登录页</option><option value="modal">弹窗登录</option></select>' },
  ElRadioButton: true,
  ElSwitch: { props: ['modelValue'], emits: ['update:modelValue'], template: '<input type="checkbox" :checked="modelValue" @change="$emit(\'update:modelValue\', $event.target.checked)" />' },
  ElAlert: { props: ['title'], template: '<p role="alert">{{ title }}</p>' },
  RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
};
const create = () => mount(System, { global: { stubs } });
beforeEach(() => {
  vi.mocked(getConsoleSystemSettings).mockReset().mockResolvedValue({ ...settings });
  vi.mocked(saveConsoleSystemSettings).mockReset().mockResolvedValue({ ...settings });
  // The confirmation result is intentionally unused; only resolution matters.
  vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue(undefined as never);
});
afterEach(() => vi.restoreAllMocks());

describe('console system settings', () => {
  it('loads real settings before enabling save', async () => {
    const wrapper = create();
    expect(wrapper.findAll('button')[1].attributes('disabled')).toBeDefined();
    await flushPromises();
    expect((wrapper.find('select').element as HTMLSelectElement).value).toBe('modal');
    expect((wrapper.find('input').element as HTMLInputElement).checked).toBe(false);
    expect(wrapper.findAll('button')[1].attributes('disabled')).toBeUndefined();
    wrapper.unmount();
  });
  it('does not save defaults after a failed load', async () => {
    vi.mocked(getConsoleSystemSettings).mockRejectedValueOnce(new Error('加载失败'));
    const wrapper = create(); await flushPromises();
    expect(wrapper.find('[role="alert"]').text()).toContain('加载失败');
    expect(wrapper.findAll('button')[1].attributes('disabled')).toBeDefined();
    expect(saveConsoleSystemSettings).not.toHaveBeenCalled(); wrapper.unmount();
  });
  it('requires explicit confirmation and submits only edited settings', async () => {
    const wrapper = create(); await flushPromises();
    await wrapper.find('select').setValue('standalone');
    await wrapper.find('input').setValue(true);
    await wrapper.findAll('button')[1].trigger('click'); await flushPromises();
    expect(ElMessageBox.confirm).toHaveBeenCalledOnce();
    expect(saveConsoleSystemSettings).toHaveBeenCalledTimes(1);
    expect(saveConsoleSystemSettings).toHaveBeenCalledWith({ auth_entry_mode: 'standalone', allow_public_registration: true });
    wrapper.unmount();
  });
  it('cancelling confirmation does not write', async () => {
    vi.mocked(ElMessageBox.confirm).mockRejectedValueOnce('cancel');
    const wrapper = create(); await flushPromises();
    await wrapper.findAll('button')[1].trigger('click'); await flushPromises();
    expect(saveConsoleSystemSettings).not.toHaveBeenCalled(); wrapper.unmount();
  });
  it('shows save failures and preserves edits for retry', async () => {
    vi.mocked(saveConsoleSystemSettings).mockRejectedValueOnce(new Error('保存失败'));
    const wrapper = create(); await flushPromises();
    await wrapper.find('select').setValue('standalone');
    await wrapper.findAll('button')[1].trigger('click'); await flushPromises();
    expect(wrapper.find('[role="alert"]').text()).toContain('保存失败');
    expect((wrapper.find('select').element as HTMLSelectElement).value).toBe('standalone');
    wrapper.unmount();
  });
  it('uses one canonical console entry and keeps runner preferences local', () => {
    expect(adminNavigation.find(item => item.path === '/system')?.label).toBe('系统设置');
    const adminLinks = sidebarGroups(true, true).flatMap(group => group.items);
    expect(adminLinks.find(item => item.path === ADMIN_SYSTEM_SETTINGS_URL)?.external).toBe(true);
    expect(adminLinks.some(item => item.path === '/admin/system-settings')).toBe(false);
    const runnerLinks = sidebarGroups(false, true).flatMap(group => group.items);
    expect(runnerLinks.some(item => item.path === ADMIN_SYSTEM_SETTINGS_URL)).toBe(false);
    expect(runnerLinks.some(item => item.path === '/ai-coach-preference')).toBe(true);
  });
});
