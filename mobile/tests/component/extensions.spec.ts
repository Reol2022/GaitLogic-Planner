import { beforeEach, afterEach, describe, it, expect, vi } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import { reset, showPage, hidePage } from './lifecycle';
import Exports from '../../pages/workspace/exports.uvue';
import Garmin from '../../pages/workspace/garmin-settings.uvue';
import History from '../../pages/workspace/history.uvue';
const mocks = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), put: vi.fn(), read: vi.fn(), open: vi.fn(), release: vi.fn(), epoch: 1 }));
vi.mock('../../services/runtime', () => ({
  api: { get: (...args: unknown[]) => mocks.get(...args), post: (...args: unknown[]) => mocks.post(...args), put: (...args: unknown[]) => mocks.put(...args) },
  auth: { epoch: () => mocks.epoch }, requireAuth: async () => true,
  downloads: { read: (...args: unknown[]) => mocks.read(...args), open: (...args: unknown[]) => mocks.open(...args), releaseAll: () => mocks.release() },
}));
function operation<T>(value: T) { return { promise: Promise.resolve(value), cancel: vi.fn() }; }
let wrapper: ReturnType<typeof mount> | null = null;
async function render(component: any, query: Record<string, string> = {}) { reset(query); wrapper = mount(component); await showPage(); await flushPromises(); return wrapper; }
async function click(label: string) { const button = wrapper!.findAll('button').find(button => button.text().includes(label)); expect(button, label).toBeTruthy(); await button!.trigger('click'); await flushPromises(); }
beforeEach(() => { vi.clearAllMocks(); mocks.epoch = 1; mocks.get.mockImplementation(() => operation([])); mocks.post.mockImplementation(() => operation({})); mocks.put.mockImplementation(() => operation({})); mocks.open.mockResolvedValue(undefined); });
afterEach(() => { hidePage(); wrapper?.unmount(); wrapper = null; });
describe('migration extensions with synthetic transports (not provider or device acceptance)', () => {
  it('downloads only after explicit action and opens only after another user action', async () => {
    const document = { name: 'gaitlogic-plan-900101.xlsx', path: 'synthetic-temp-file', epoch: 1 };
    mocks.read.mockImplementation(() => operation(document));
    await render(Exports, { draft_id: '900101' }); expect(mocks.read).not.toHaveBeenCalled(); await click('下载文件');
    expect(mocks.read).toHaveBeenCalledWith('ai-draft', 900101, 'xlsx'); expect(mocks.open).not.toHaveBeenCalled();
    expect(wrapper!.text()).toContain('尚未证明已保存到系统下载目录');
    await click('打开文件'); expect(mocks.open).toHaveBeenCalledWith(document);
    const before = mocks.release.mock.calls.length; hidePage(); expect(mocks.release.mock.calls.length).toBe(before);
    await showPage(); await flushPromises(); expect(mocks.release.mock.calls.length).toBeGreaterThan(before);
  });
  it('does not retain a late downloaded file after leaving the page', async () => {
    let finish: (value: unknown) => void = () => {};
    mocks.read.mockImplementation(() => ({ promise: new Promise(resolve => { finish = resolve; }), cancel: vi.fn() }));
    await render(Exports); await click('下载文件'); hidePage(); finish({ name: 'synthetic.xlsx', path: 'synthetic-late', epoch: 1 }); await flushPromises();
    expect(wrapper!.text()).not.toContain('synthetic.xlsx'); expect(mocks.release).toHaveBeenCalled(); expect(mocks.open).not.toHaveBeenCalled();
  });
  it('Garmin connection and MFA require user actions; secrets never appear as page text', async () => {
    let connected = false;
    mocks.get.mockImplementation((path: string) => operation(path.endsWith('/status') ? { connected, status: connected ? 'connected' : 'disconnected', auto_import_enabled: true, region: 'cn' } : { enabled: false, recovery_enabled: false, interval_minutes: 30 }));
    mocks.post.mockImplementation((path: string) => { if (path.endsWith('/mfa')) { connected = true; return operation({ status: 'connected' }); } return operation({ status: 'mfa_required', mfa_token: 'synthetic-mfa-reference' }); });
    await render(Garmin); expect(mocks.post).not.toHaveBeenCalled(); await wrapper!.get('#garmin-username').setValue('synthetic@example.test'); await wrapper!.get('#garmin-password').setValue('synthetic-password');
    await click('准备连接'); expect(mocks.post).not.toHaveBeenCalled(); await click('确认操作');
    expect(mocks.post).toHaveBeenCalledWith('/integrations/garmin/connect', { username: 'synthetic@example.test', password: 'synthetic-password', region: 'cn' }, 180000);
    expect(wrapper!.text()).toContain('完成 Garmin 验证'); expect(wrapper!.text()).not.toContain('synthetic-password'); expect(wrapper!.text()).not.toContain('synthetic-mfa-reference');
    await wrapper!.get('#garmin-mfa').setValue('111111'); await click('提交验证码');
    expect(mocks.post).toHaveBeenCalledWith('/integrations/garmin/connect/mfa', { mfa_token: 'synthetic-mfa-reference', mfa_code: '111111' }, 180000);
    expect(wrapper!.text()).toContain('已连接'); expect(mocks.post.mock.calls.some(call => call[0].endsWith('/sync'))).toBe(false);
  });
  it('Garmin region stays fixed on failure, with no retry and cleared password', async () => {
    mocks.get.mockImplementation((path: string) => operation(path.endsWith('/status') ? { connected: false, status: 'disconnected', auto_import_enabled: true } : { enabled: false, recovery_enabled: false, interval_minutes: 30 }));
    mocks.post.mockImplementation(() => ({ promise: Promise.reject(new Error('合成连接失败')), cancel: vi.fn() }));
    await render(Garmin); await wrapper!.get('#garmin-username').setValue('synthetic'); await wrapper!.get('#garmin-password').setValue('synthetic-password'); await click('准备连接'); await click('确认操作');
    expect(mocks.post).toHaveBeenCalledTimes(1); expect(mocks.post.mock.calls[0][1].region).toBe('cn'); expect(wrapper!.get('#garmin-password').element.value).toBe(''); expect(wrapper!.text()).toContain('不会自动重试或切换区域');
  });
  it('changing sync switches does not write until settings are confirmed', async () => {
    mocks.get.mockImplementation((path: string) => operation(path.endsWith('/status') ? { connected: true, status: 'connected', auto_import_enabled: true } : { enabled: false, recovery_enabled: false, interval_minutes: 30 }));
    await render(Garmin); await click('定时同步：关'); await click('准备保存定时设置'); expect(mocks.put).not.toHaveBeenCalled(); await click('确认操作');
    expect(mocks.put).toHaveBeenCalledWith('/integrations/garmin/smart-sync', { enabled: true, recovery_enabled: false, interval_minutes: 30 }); expect(mocks.post).not.toHaveBeenCalled();
  });
  it('missing snapshot service does not discard available readiness history', async () => {
    mocks.get.mockImplementation((path: string) => path.includes('/snapshots/') ? { promise: Promise.reject(new Error('合成快照不可用')), cancel: vi.fn() } : operation({ items: [{ id: 900201, assessment_date: '2026-01-12', status: 'watch', data_quality: 'medium', reasons_json: ['合成准备度依据'], missing_data_json: ['HRV 基线缺失'] }] }));
    await render(History); await click('准备度'); expect(wrapper!.text()).toContain('合成准备度依据'); expect(wrapper!.text()).toContain('HRV 基线缺失'); expect(wrapper!.text()).toContain('部分历史记录读取失败'); expect(mocks.post).not.toHaveBeenCalled();
  });
  it('null recovery metrics stay unavailable and history reads never create snapshots', async () => {
    mocks.get.mockImplementation((path: string) => operation(path.includes('/timeline?') ? { start_date: '2026-01-01', end_date: '2026-01-28', days_with_snapshots: 0, items: [] } : path.startsWith('/recovery-checkins') ? { items: [{ id: 900202, checkin_date: '2026-01-12', hrv_value: null, resting_heart_rate_bpm: null, source: 'GARMIN' }] } : { items: [] }));
    await render(History); expect(wrapper!.text()).toContain('HRV 暂无'); expect(wrapper!.text()).not.toContain('HRV 0'); expect(mocks.post).not.toHaveBeenCalled();
  });
});
