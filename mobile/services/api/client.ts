import type { HttpMethod, Transport, RequestOperation } from '../../adapters/transport/types';

export class ApiError extends Error {
  constructor(public readonly code: string, message: string, public readonly status = 0, public readonly retryAfter: number | null = null) { super(message); }
}
export interface IdentityPort { token(): string | null; epoch(): number; invalidate(): void }
function validationHint(data: unknown): string | null {
  if (data == null || typeof data !== 'object') return null;
  const body = data as { detail?: unknown; error?: { detail?: unknown } };
  const detail = body.error?.detail ?? body.detail;
  if (!Array.isArray(detail)) return null;
  const labels: Record<string, string> = { username: '用户名（3–64 字符）', password: '密码（注册至少 8 字符）', email: '邮箱', name: '名称', block_name: '训练块名称', planned_content: '训练内容', start_date: '开始日期', end_date: '结束日期', workout_date: '训练日期', cycle_id: '所属周期', block_id: '所属训练块', rpe: '整堂训练 RPE', pain_level: '疼痛等级', plan_weeks: '计划周数', target_race_date: '赛事日期', plan_start_date: '计划开始日期', current_weekly_mileage_km: '当前周跑量', recent_4w_avg_mileage_km: '近四周平均周跑量', available_training_days_per_week: '每周训练天数', target_distance: '目标距离', daily_available_minutes: '每日可用时间' };
  const selected = new Set<string>();
  for (const issue of detail.slice(0, 10)) {
    if (issue == null || typeof issue !== 'object' || !Array.isArray(issue.loc)) continue;
    for (const part of issue.loc) if (typeof part === 'string' && labels[part]) selected.add(labels[part]);
  }
  return selected.size ? '请检查：' + [...selected].slice(0, 3).join('、') : null;
}
export class ApiClient {
  private pending = new Set<() => void>();
  constructor(private transport: Transport, private baseUrl: () => string, private identity: IdentityPort) {}
  abortAll() { for (const cancel of [...this.pending]) cancel(); this.pending.clear(); }
  request<T>(method: HttpMethod, path: string, data?: unknown, timeout = 20000, idempotencyKey?: string): RequestOperation<T> {
    if (!path.startsWith('/') || path.startsWith('//') || path.includes('..') || /[\r\n]/.test(path)) throw new ApiError('BAD_PATH', '请求路径无效');
    const base = this.baseUrl();
    if (!/^https:\/\/[a-z0-9.-]+(?::\d+)?\/api$/i.test(base) || base.includes('example.invalid')) {
      throw new ApiError('CONFIG_REQUIRED', '请先在设置中填写 HTTPS API 地址');
    }
    const token = this.identity.token(), epoch = this.identity.epoch();
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (idempotencyKey != null) {
      if (!/^[A-Za-z0-9_-]{16,128}$/.test(idempotencyKey)) throw new ApiError('BAD_IDEMPOTENCY_KEY', '请求标识无效');
      headers['Idempotency-Key'] = idempotencyKey;
    }
    if (token) headers.Authorization = `Bearer ${token}`;
    const operation = this.transport.request({ url: base + path, method, data, timeout, headers });
    let cancelled = false;
    const cancel = () => { cancelled = true; operation.cancel(); };
    this.pending.add(cancel);
    const promise = operation.promise.then(result => {
      if (cancelled || this.identity.epoch() !== epoch) throw new ApiError('CANCELLED', '请求已取消');
      if (result.status === 401) {
        const challenge = result.headers?.['WWW-Authenticate'] ?? result.headers?.['www-authenticate'];
        if (typeof challenge === 'string' && /\bresource_metadata\s*=/i.test(challenge)) {
          // A REST request reached an OAuth/MCP resource, not the Web JWT API.
          // Preserve identity and never start a conflicting login redirect.
          throw new ApiError('API_PROTOCOL_MISMATCH', '当前接口被转发到 MCP 服务，请升级后端或检查接口代理配置', 401);
        }
        if (token === this.identity.token()) this.identity.invalidate();
        throw new ApiError('UNAUTHENTICATED', path === '/auth/login' ? '账号或密码不正确' : '登录已失效，请重新登录', 401);
      }
      if (result.status < 200 || result.status >= 300) {
        const message = ((result.status === 400 || result.status === 422) ? validationHint(result.data) : null) || (result.status === 429 ? '请求过于频繁，请稍后重试' : result.status === 403 ? '当前账号无权访问此功能'
          : result.status === 404 ? '当前版本暂不支持此功能或记录不存在' : result.status === 409 ? '当前会话正在处理，请稍后重试'
          : result.status >= 500 ? '服务暂不可用，请稍后重试' : '请求未完成，请检查填写内容');
        const rawRetry = result.headers?.['Retry-After'] ?? result.headers?.['retry-after'];
        const retry = typeof rawRetry === 'string' && /^\d+$/.test(rawRetry) ? Number(rawRetry) : null;
        throw new ApiError(`HTTP_${result.status}`, message, result.status, retry);
      }
      return result.data as T;
    }).catch((error: unknown) => {
      if (error instanceof ApiError) throw error;
      const kind = cancelled ? 'CANCELLED' : error instanceof Error && error.message === 'TIMEOUT' ? 'TIMEOUT' : 'NETWORK';
      throw new ApiError(kind, kind === 'CANCELLED' ? '请求已取消' : kind === 'TIMEOUT' ? '请求超时，请稍后重试' : '网络不可用，请检查连接');
    }).finally(() => this.pending.delete(cancel));
    return { promise, cancel };
  }
  get<T>(path: string) { return this.request<T>('GET', path); }
  post<T>(path: string, data?: unknown, timeout?: number) { return this.request<T>('POST', path, data, timeout); }
  postOnce<T>(path: string, data: unknown, key: string, timeout?: number) { return this.request<T>('POST', path, data, timeout, key); }
  put<T>(path: string, data?: unknown) { return this.request<T>('PUT', path, data); }
  patch<T>(path: string, data?: unknown) { return this.request<T>('PATCH', path, data); }
  delete<T>(path: string) { return this.request<T>('DELETE', path); }
}
