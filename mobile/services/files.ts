import { ApiError } from './api/client';
import type { IdentityPort } from './api/client';
import type { RequestOperation } from '../adapters/transport/types';
export interface SelectedFile { name: string; path: string; size: number }
export interface UploadOptions { url: string; filePath: string; name: string; header: Record<string, string>; formData: Record<string, string>; timeout: number; success(result: { statusCode: number; data: string }): void; fail(error: { errCode?: number }): void }
export type UploadPort = (options: UploadOptions) => { abort(): void };
export function validateFile(file: SelectedFile): void {
  if (!file.path || !/\.xlsx$/i.test(file.name) || !Number.isFinite(file.size) || file.size <= 0 || file.size > 2 * 1024 * 1024) throw new ApiError('FILE_INVALID', '请选择不超过 2 MB 的标准 .xlsx 模板文件');
}
/** Multipart boundary belongs to the platform. Never persist paths, credentials or raw responses. */
export class FileClient {
  constructor(private upload: UploadPort, private baseUrl: () => string, private identity: IdentityPort) {}
  send<T>(kind: 'plan' | 'workout', file: SelectedFile, data: Record<string, string>, key: string): RequestOperation<T> {
    validateFile(file);
    if (kind !== 'plan' && kind !== 'workout') throw new ApiError('BAD_PATH', '导入类型无效');
    if (!/^[A-Za-z0-9_-]{16,128}$/.test(key)) throw new ApiError('BAD_IDEMPOTENCY_KEY', '请求标识无效');
    const base = this.baseUrl(), token = this.identity.token(), epoch = this.identity.epoch();
    if (!/^https:\/\/[a-z0-9.-]+(?::\d+)?\/api$/i.test(base) || base.includes('example.invalid')) throw new ApiError('CONFIG_REQUIRED', '请先确认可信 HTTPS API 地址');
    if (!token) throw new ApiError('UNAUTHENTICATED', '请先登录');
    let task: { abort(): void } | null = null, cancelled = false, finished = false, rejectPending: (error: unknown) => void = () => {};
    const promise = new Promise<T>((resolve, reject) => {
      rejectPending = reject;
      task = this.upload({ url: base + (kind === 'plan' ? '/plan-imports/file' : '/workout-imports/file'), filePath: file.path, name: 'file', header: { Authorization: 'Bearer ' + token, 'Idempotency-Key': key }, formData: data, timeout: 120000,
        success: result => {
          finished = true;
          if (cancelled || epoch !== this.identity.epoch()) { reject(new ApiError('CANCELLED', '请求已取消')); return; }
          if (result.statusCode === 401) { if (token === this.identity.token()) this.identity.invalidate(); reject(new ApiError('UNAUTHENTICATED', '登录已失效，请重新登录', 401)); return; }
          if (result.statusCode < 200 || result.statusCode >= 300) { reject(new ApiError('UPLOAD_REJECTED', result.statusCode === 403 ? '当前账号无权导入' : result.statusCode === 413 ? '文件超过服务器大小限制' : result.statusCode === 429 ? '导入过于频繁，请稍后重试' : '文件导入未完成，请检查模板、权限及服务器版本', result.statusCode)); return; }
          try { if (result.data.length > 2 * 1024 * 1024) throw new Error(); resolve(JSON.parse(result.data) as T); } catch { reject(new ApiError('BAD_RESPONSE', '导入响应格式无效，请先核对草稿状态')); }
        },
        fail: error => { finished = true; reject(new ApiError(cancelled ? 'CANCELLED' : error.errCode === 5 ? 'TIMEOUT' : 'NETWORK', cancelled ? '已取消本页等待' : error.errCode === 5 ? '上传超时，请核对导入草稿后再决定是否重试' : '上传网络不可用，请检查连接')); },
      });
    }).catch((error: unknown) => { if (error instanceof ApiError) throw error; throw new ApiError('UPLOAD_FAILED', '上传未完成，请检查设备与连接'); });
    return { promise, cancel() { if (!finished) { cancelled = true; finished = true; task?.abort(); rejectPending(new ApiError('CANCELLED', '已取消本页等待，不代表服务端停止解析')); } } };
  }
}
