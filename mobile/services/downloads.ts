import { ApiError } from './api/client';
import type { IdentityPort } from './api/client';
import type { RequestOperation } from '../adapters/transport/types';
export type ExportFormat = 'xlsx' | 'csv' | 'markdown' | 'json' | 'ics' | 'garmin_csv' | 'coros_csv' | 'device_csv';
const formats: string[] = ['xlsx', 'csv', 'markdown', 'json', 'ics', 'garmin_csv', 'coros_csv', 'device_csv'];
export function exportPath(kind: 'plan-template' | 'workout-template' | 'ai-draft', id?: number, format: ExportFormat = 'xlsx'): string {
  if (kind === 'plan-template') return '/plan-imports/template';
  if (kind === 'workout-template') return '/workout-imports/template';
  if (kind !== 'ai-draft' || !Number.isSafeInteger(id) || Number(id) < 1 || !formats.includes(format)) throw new ApiError('BAD_EXPORT', '导出参数无效');
  return '/ai-plan/drafts/' + id + '/export?format=' + format;
}
export interface DownloadOptions { url: string; header: Record<string, string>; timeout: number; success(result: { statusCode: number; tempFilePath: string }): void; fail(error: { errCode?: number }): void; complete(): void }
export interface DocumentPort { download(options: DownloadOptions): { abort(): void }; remove(path: string): void; open(path: string, fileType?: string): Promise<void> }
export interface DownloadedDocument { readonly name: string; readonly path: string; readonly epoch: number }
/** Only service-generated endpoints and platform-returned, owned temporary files. */
export class DownloadClient {
  private owned = new Map<string, DownloadedDocument>();
  constructor(private port: DocumentPort, private baseUrl: () => string, private identity: IdentityPort) {}
  read(kind: 'plan-template' | 'workout-template' | 'ai-draft', id?: number, format: ExportFormat = 'xlsx'): RequestOperation<DownloadedDocument> {
    const path = exportPath(kind, id, format), base = this.baseUrl(), token = this.identity.token(), epoch = this.identity.epoch();
    if (!/^https:\/\/[a-z0-9.-]+(?::\d+)?\/api$/i.test(base) || base.includes('example.invalid')) throw new ApiError('CONFIG_REQUIRED', '请确认可信 HTTPS API 地址');
    if (!token) throw new ApiError('UNAUTHENTICATED', '请先登录');
    let task: { abort(): void } | null = null, finished = false, cancelled = false, rejectPending: (error: unknown) => void = () => {};
    const promise = new Promise<DownloadedDocument>((resolve, reject) => {
      rejectPending = reject;
      task = this.port.download({ url: base + path, header: { Authorization: 'Bearer ' + token }, timeout: 120000,
        success: result => {
          const file = result.tempFilePath;
          if (finished || cancelled || epoch !== this.identity.epoch()) { if (file) this.port.remove(file); reject(new ApiError('CANCELLED', '账号或页面已变化，未保留文件')); return; }
          finished = true;
          if (result.statusCode < 200 || result.statusCode >= 300 || !file) {
            if (file) this.port.remove(file);
            if (result.statusCode === 401 && token === this.identity.token()) this.identity.invalidate();
            reject(new ApiError('DOWNLOAD_FAILED', result.statusCode === 401 ? '登录已失效，请重新登录' : result.statusCode === 403 ? '无权下载此文件' : result.statusCode === 429 ? '下载过于频繁，请稍后重试' : '文件下载失败，请检查记录与服务版本', result.statusCode)); return;
          }
          const extension = kind === 'ai-draft' ? (format.endsWith('_csv') ? 'csv' : format === 'markdown' ? 'md' : format) : 'xlsx';
          const document = { path: file, epoch, name: kind === 'ai-draft' ? 'gaitlogic-plan-' + id + '.' + extension : kind + '.xlsx' };
          this.owned.set(file, document); resolve(document);
        },
        fail: error => { if (finished) return; finished = true; reject(new ApiError(cancelled ? 'CANCELLED' : error.errCode === 5 ? 'TIMEOUT' : 'NETWORK', cancelled ? '下载已取消' : error.errCode === 5 ? '下载超时，请稍后重试' : '下载网络不可用')); }, complete: () => { task = null; },
      });
    }).catch((error: unknown) => { if (error instanceof ApiError) throw error; throw new ApiError('DOWNLOAD_FAILED', '下载未完成，请检查设备与连接'); });
    return { promise, cancel() { if (!finished) { cancelled = true; finished = true; task?.abort(); rejectPending(new ApiError('CANCELLED', '下载已取消')); } } };
  }
  async open(document: DownloadedDocument): Promise<void> {
    if (this.owned.get(document.path) !== document || document.epoch !== this.identity.epoch()) throw new ApiError('CANCELLED', '文件已失效，请重新下载');
    await this.port.open(document.path, document.name.split('.').pop());
  }
  releaseAll(): void { for (const path of this.owned.keys()) { try { this.port.remove(path); } catch { /* Clear ownership even if platform cache deletion fails. */ } } this.owned.clear(); }
}
