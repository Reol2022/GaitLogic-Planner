import type { Transport, HttpResponse } from './types';

export function createUniTransport(): Transport {
  return { request(options) {
    let task: { abort(): void } | null = null;
    let rejectPending: (error: unknown) => void = () => {};
    let finished = false;
    const promise = new Promise<HttpResponse>((resolve, reject) => {
      rejectPending = reject;
      task = uni.request({ url: options.url, method: options.method, data: options.data,
        header: options.headers, timeout: options.timeout, sslVerify: true,
        success(result: { statusCode: number; data: unknown; header?: Record<string, unknown> }) {
          finished = true; resolve({ status: result.statusCode, data: result.data, headers: result.header });
        },
        fail(error: { errCode?: number; errMsg?: string }) {
          finished = true;
          // Never propagate upstream diagnostic strings, URLs, payloads or credentials.
          reject(new Error(error.errCode === 5 || (error.errMsg || '').toLowerCase().includes('timeout') ? 'TIMEOUT' : 'NETWORK'));
        },
        complete() { task = null; },
      });
    });
    return { promise, cancel() { if (!finished) { finished = true; task?.abort(); rejectPending(new Error('CANCELLED')); } } };
  } };
}
