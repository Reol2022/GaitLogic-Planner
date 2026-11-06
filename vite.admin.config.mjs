import vue from './web/node_modules/@vitejs/plugin-vue/dist/index.mjs';
import { defineConfig } from './web/node_modules/vite/dist/node/index.js';
import { fileURLToPath } from 'node:url';
export default defineConfig({
  root:fileURLToPath(new URL('./web/',import.meta.url)),
  base:process.env.ADMIN_PUBLIC_BASE || '/control/',
  cacheDir:'../admin-vite-cache',plugins:[vue()],
  resolve:{alias:{'@':fileURLToPath(new URL('./web/src/',import.meta.url))}},
  server:{host:'127.0.0.1',port:5174,proxy:{'/api':{target:process.env.VITE_DEV_API_PROXY_TARGET || 'http://127.0.0.1:8000',changeOrigin:true}}},
  build:{outDir:'../admin-dist',emptyOutDir:true,rollupOptions:{input:fileURLToPath(new URL('./web/admin.html',import.meta.url))}},
});
