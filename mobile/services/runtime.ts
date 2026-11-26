import { reactive } from 'vue';
import { ApiClient } from './api/client';
import { AuthSession, TOKEN_KEY } from './auth/session';
import { createUniTransport } from '../adapters/transport/uni';
import { uniStorage } from '../adapters/storage/uni';
import { getApiBaseUrl, buildEnvironment } from '../config/environment';
import { platform } from '../adapters/platform/uni';
import { FileClient } from './files';
import { DownloadClient } from './downloads';
import { documents } from '../adapters/platform/documents';
export { platform };
export const auth = new AuthSession(reactive({ token: null, user: null, ready: false }), uniStorage, `${TOKEN_KEY}.${buildEnvironment}`);
export const api = new ApiClient(createUniTransport(), getApiBaseUrl,
  { token: () => auth.state.token, epoch: () => auth.epoch(), invalidate: () => {
    const hadToken = auth.state.token !== null;
    auth.invalidate();
    if (hadToken) uni.reLaunch({ url: '/pages/auth/login' });
  } });
auth.connect(api);
export const files = new FileClient(options => uni.uploadFile(options), getApiBaseUrl, { token: () => auth.state.token, epoch: () => auth.epoch(), invalidate: () => { auth.invalidate(); uni.reLaunch({ url: '/pages/auth/login' }); } });
export const downloads = new DownloadClient(documents, getApiBaseUrl, { token: () => auth.state.token, epoch: () => auth.epoch(), invalidate: () => { auth.invalidate(); uni.reLaunch({ url: '/pages/auth/login' }); } });
auth.onInvalidate(() => downloads.releaseAll());
export async function requireAuth(): Promise<boolean> {
  await auth.restore();
  if (!auth.state.user) { uni.reLaunch({ url: '/pages/auth/login' }); return false; }
  return true;
}
