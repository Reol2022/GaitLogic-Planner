const show: Array<() => unknown> = [], hide: Array<() => unknown> = [];
let query: Record<string, string> = {};
export function reset(options: Record<string, string> = {}): void { show.length = 0; hide.length = 0; query = options; }
export function onLoad(callback: (options: Record<string, string>) => void): void { callback(query); }
export function onShow(callback: () => unknown): void { show.push(callback); }
export function onHide(callback: () => unknown): void { hide.push(callback); }
export function onUnload(_callback: () => unknown): void {}
export async function showPage(): Promise<void> { for (const callback of show) await callback(); }
export function hidePage(): void { for (const callback of hide) callback(); }
