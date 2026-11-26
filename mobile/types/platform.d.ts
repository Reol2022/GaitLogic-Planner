// Minimal static-analysis boundary, NOT a substitute for the HBuilderX compiler
// or a claim that every uni API is implemented on each native target.
declare const uni: {
  chooseFile(options: { count: number; type: string; extension: string[]; success(result: { tempFiles: Array<{ name: string; path: string; size: number }> }): void; fail(error: { errCode?: number }): void }): void;
  uploadFile(options: import('../services/files').UploadOptions): { abort(): void };
  downloadFile(options: import('../services/downloads').DownloadOptions): { abort(): void };
  openDocument(options: { filePath: string; fileType?: string; showMenu: boolean; success(): void; fail(): void }): void;
  getFileSystemManager(): { unlink(options: { filePath: string; success(): void; fail(): void }): void };
  request(options: { url: string; method: string; data?: unknown; header: Record<string, string>; timeout: number; sslVerify: boolean;
    success(result: { statusCode: number; data: unknown; header?: Record<string, unknown> }): void;
    fail(error: { errCode?: number; errMsg?: string }): void; complete(): void }): { abort(): void };
  getStorageSync(key: string): unknown;
  setStorageSync(key: string, value: string): void;
  removeStorageSync(key: string): void;
  navigateTo(options: { url: string }): void;
  switchTab(options: { url: string }): void;
  setNavigationBarColor(options: { frontColor: '#ffffff' | '#000000'; backgroundColor: string }): void;
  setTabBarStyle(options: { color: string; selectedColor: string; backgroundColor: string; borderStyle: 'black' | 'white' }): void;
  reLaunch(options: { url: string }): void;
  setClipboardData(options: { data: string }): void;
  showToast(options: { title: string; icon?: string }): void;
};
declare module '@dcloudio/uni-app' {
  export function onLaunch(fn: () => void): void;
  export function onShow(fn: () => void): void;
  export function onHide(fn: () => void): void;
  export function onUnload(fn: () => void): void;
  export function onLoad(fn: (query: Record<string, string | undefined>) => void): void;
}
declare module '*.uvue' { const component: import('vue').DefineComponent; export default component; }
declare function defineProps<T>(): T;
declare function defineEmits<T>(): T;
