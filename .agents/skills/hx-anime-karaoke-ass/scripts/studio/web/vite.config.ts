import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// 开发: vite dev 把接口与资源代理到 python 服务 (scripts/studio/server/app.py, 默认 5199).
// 运行: python 服务直接发 dist/, 不需要 node.
/*
 * Agent Notes: studio 前端构建 (dist/ 由 python 服务直接发)
 * .agents/notes/implemented/feature/2026-11-09-karaoke-studio.md
 */
const API = process.env.HX_STUDIO_API ?? 'http://127.0.0.1:5199';

export default defineConfig({
  plugins: [react()],
  base: '/',
  server: {
    port: 5198,
    proxy: {
      '/api/watch': { target: API.replace(/^http/, 'ws'), ws: true },
      '/api': API,
      '/media': API,
      '/octopus': API,
      '/fonts': API,
    },
  },
  build: { outDir: 'dist', emptyOutDir: true, sourcemap: false },
});
