import type { StoragePort } from '../../adapters/transport/types';
import { ApiClient, ApiError } from '../api/client';
import type { User } from '../../types/contracts';
export const TOKEN_KEY = 'gaitlogic.mobile.token.v1';
export interface AuthState { token: string | null; user: User | null; ready: boolean }
export class AuthSession {
  private generation = 0;
  private restoring: Promise<void> | null = null;
  private client: ApiClient | null = null;
  private invalidationHandlers: Array<() => void> = [];
  constructor(public readonly state: AuthState, private storage: StoragePort, private tokenKey = TOKEN_KEY) { this.state.token = storage.get(tokenKey); }
  connect(client: ApiClient) { this.client = client; }
  epoch() { return this.generation; }
  onInvalidate(handler: () => void): void { this.invalidationHandlers.push(handler); }
  invalidate() {
    this.generation++; this.client?.abortAll();
    this.storage.remove(this.tokenKey); this.state.token = null; this.state.user = null; this.state.ready = true; this.restoring = null;
    for (const handler of this.invalidationHandlers) { try { handler(); } catch { /* Cleanup must not prevent identity invalidation. */ } }
  }
  logout() { this.invalidate(); }
  async login(username: string, password: string) {
    if (!this.client) throw new Error('AUTH_UNINITIALIZED');
    this.invalidate(); this.state.ready = false;
    const epoch = this.generation;
    try {
      const result = await this.client.post<{ access_token: string }>('/auth/login', { username, password }).promise;
      if (epoch !== this.generation) return;
      if (typeof result.access_token !== 'string' || !result.access_token) throw new ApiError('BAD_RESPONSE', '登录响应无效，请检查 API 地址');
      this.state.token = result.access_token;
      this.storage.set(this.tokenKey, result.access_token);
      const user = await this.client.get<User>('/auth/me').promise;
      if (!user || !Number.isInteger(user.id) || user.id < 1 || typeof user.username !== 'string') throw new ApiError('BAD_RESPONSE', '用户资料响应无效');
      if (epoch === this.generation) { this.state.user = user; this.state.ready = true; }
    } catch (error) { if (epoch === this.generation) this.invalidate(); throw error; }
  }
  restore(): Promise<void> {
    if (this.state.user || !this.state.token) { this.state.ready = true; return Promise.resolve(); }
    if (this.restoring) return this.restoring;
    const epoch = this.generation;
    const pending = (async () => {
      try {
        const user = await this.client!.get<User>('/auth/me').promise;
        if (!user || !Number.isInteger(user.id) || user.id < 1 || typeof user.username !== 'string') throw new ApiError('BAD_RESPONSE', '用户资料响应无效');
        if (epoch === this.generation) this.state.user = user;
      } finally { if (epoch === this.generation) { this.state.ready = true; this.restoring = null; } }
    })();
    this.restoring = pending;
    return pending;
  }
}
