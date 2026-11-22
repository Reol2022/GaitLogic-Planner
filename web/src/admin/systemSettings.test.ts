import { afterEach, expect, it, vi } from 'vitest';
import { api } from './api';
import { getConsoleSystemSettings, saveConsoleSystemSettings } from './systemSettings';
afterEach(() => vi.restoreAllMocks());

it('uses the independent admin client and narrow existing API contract', async () => {
  const value = { auth_entry_mode: 'modal' as const, allow_public_registration: false };
  const get = vi.spyOn(api, 'get').mockResolvedValueOnce({ data: value });
  const put = vi.spyOn(api, 'put').mockResolvedValueOnce({ data: value });
  expect(await getConsoleSystemSettings()).toEqual(value);
  await saveConsoleSystemSettings({ ...value, id: 8 } as typeof value);
  expect(get).toHaveBeenCalledWith('/admin/system-settings');
  expect(put).toHaveBeenCalledWith('/admin/system-settings', value);
});
