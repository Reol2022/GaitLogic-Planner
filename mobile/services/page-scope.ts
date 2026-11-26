import type { RequestOperation } from '../adapters/transport/types';
/** Scope excludes late reads/writes from a hidden page or a different account. */
export class PageScope {
  private version = 0;
  private identity = 0;
  private pending = new Set<() => void>();
  constructor(private epoch: () => number) {}
  begin(): number { this.stop(); this.identity = this.epoch(); return this.version; }
  current(version: number): boolean { return version === this.version && this.identity === this.epoch(); }
  stop(): void { this.version++; for (const cancel of this.pending) cancel(); this.pending.clear(); }
  async wait<T>(operation: RequestOperation<T>): Promise<T> {
    this.pending.add(operation.cancel);
    try { return await operation.promise; } finally { this.pending.delete(operation.cancel); }
  }
}
