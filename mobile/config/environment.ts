export const mobileVersion = '0.1.0';
// Set the build profile deliberately before native compilation. Neither
// profile contains credentials; production never accepts HTTP or disables TLS.
export const buildEnvironment: 'development' | 'production' = 'production';
export const profiles = {
  development: { apiBaseUrl: 'https://dev.example.invalid/api' },
  production: { apiBaseUrl: 'https://backgait.reol2020.cn/api' },
};
const key = `gaitlogic.mobile.${buildEnvironment}.api-base.v1`;
export function validateBaseUrl(url: string, development = false): string {
  const value = url.trim().replace(/\/+$/, '');
  if (!/^https:\/\/[a-z0-9.-]+(?::\d+)?\/api$/i.test(value)
    && !(development && /^http:\/\/(?:localhost|127\.0\.0\.1|10\.0\.2\.2)(?::\d+)?\/api$/.test(value))) {
    throw new Error('API 地址必须为有效 HTTPS 地址并以 /api 结尾');
  }
  return value;
}
export function getApiBaseUrl(): string {
  const value = uni.getStorageSync(key);
  return typeof value === 'string' && value ? value : profiles[buildEnvironment].apiBaseUrl;
}
export function setApiBaseUrl(url: string): void { uni.setStorageSync(key, validateBaseUrl(url)); }
