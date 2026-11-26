export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
export interface HttpResponse { status: number; data: unknown; headers?: Record<string, unknown> }
export interface RequestOperation<T> { promise: Promise<T>; cancel(): void }
export interface Transport {
  request(options: { url: string; method: HttpMethod; data?: unknown; headers: Record<string, string>; timeout: number }): RequestOperation<HttpResponse>;
}
export interface StoragePort { get(key: string): string | null; set(key: string, value: string): void; remove(key: string): void }
