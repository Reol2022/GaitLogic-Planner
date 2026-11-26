import { defineConfig } from '../web/node_modules/vitest/dist/config.js';
import vue from '../web/node_modules/@vitejs/plugin-vue/dist/index.mjs';
import { fileURLToPath } from 'node:url';
export default defineConfig({
  plugins: [vue({ include: /\.uvue$/, template: { compilerOptions: { isCustomElement: tag => ['view', 'text', 'scroll-view', 'picker', 'picker-view', 'picker-view-column', 'switch'].includes(tag) } } })],
  resolve: { alias: { '@dcloudio/uni-app': fileURLToPath(new URL('./tests/component/lifecycle.ts', import.meta.url)), vue: fileURLToPath(new URL('../web/node_modules/vue/dist/vue.esm-bundler.js', import.meta.url)), vitest: fileURLToPath(new URL('../web/node_modules/vitest/dist/index.js', import.meta.url)), '@vue/test-utils': fileURLToPath(new URL('../web/node_modules/@vue/test-utils/dist/vue-test-utils.esm-bundler.mjs', import.meta.url)) } },
  test: { environment: 'jsdom', include: ['tests/component/**/*.spec.ts'], cache: false, pool: 'forks', maxWorkers: 1, minWorkers: 1 },
});
