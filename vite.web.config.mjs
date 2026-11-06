import vue from "./web/node_modules/@vitejs/plugin-vue/dist/index.mjs";
import { defineConfig } from "./web/node_modules/vite/dist/node/index.js";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const packageJson = require("./web/package.json");
const webRoot = fileURLToPath(new URL("./web/", import.meta.url));
const srcRoot = fileURLToPath(new URL("./web/src/", import.meta.url));
const apiProxyTarget = process.env.VITE_DEV_API_PROXY_TARGET || "http://127.0.0.1:8000";

// Canonical management entry is a separate HTML page on the same dev server.
// Keep old /control bookmarks from falling through to the runner SPA/login.
function managementEntry() {
  const aliases = new Map([
    ['/control', '/'], ['/control/', '/'], ['/control/admin.html', '/'],
    ['/control/login', '/login'], ['/control/users', '/users'],
    ['/control/ai', '/ai'], ['/control/audit', '/audit'],
  ]);
  const install = (server) => { server.middlewares.use((req, res, next) => {
    const pathname = (req.url || '').split('?')[0];
    if (!aliases.has(pathname)) return next();
    res.statusCode = 302;
    res.setHeader('Location', `/admin.html#${aliases.get(pathname)}`);
    res.end();
  }); };
  return { name: 'management-entry', configureServer: install, configurePreviewServer: install };
}

export default defineConfig({
  root: webRoot,
  cacheDir: "../web-vite-cache",
  plugins: [managementEntry(), vue()],
  define: {
    __APP_VERSION__: JSON.stringify(packageJson.version),
    "import.meta.env.VITE_APP_VERSION": JSON.stringify(packageJson.version),
  },
  resolve: {
    alias: {
      "@": srcRoot,
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: apiProxyTarget,
        changeOrigin: true,
      },
    },
  },
  preview: {
    port: 5173,
    proxy: {
      "/api": {
        target: apiProxyTarget,
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "../web-dist",
    emptyOutDir: true,
    rollupOptions: {
      input: {
        runner: fileURLToPath(new URL('./web/index.html', import.meta.url)),
        admin: fileURLToPath(new URL('./web/admin.html', import.meta.url)),
      },
    },
  },
});
