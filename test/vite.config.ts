import react from '@vitejs/plugin-react';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { defineConfig, type Plugin } from 'vite';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const parentRoot = path.resolve(__dirname, '..');

/**
 * 自定义 Vite 插件：将静态资源请求代理到父目录
 * 这样前端可以直接用 /static/music/xxx.mp3, /playlist.json 等路径访问本仓库的文件
 */
function serveParentStatic(): Plugin {
  return {
    name: 'serve-parent-static',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        if (!req.url) return next();

        const decodedUrl = decodeURIComponent(req.url.split('?')[0]);

        // 代理 /static/music/* 到父目录 (支持 Range 请求, 以便音频可拖动)
        if (decodedUrl.startsWith('/static/music/')) {
          const filePath = path.join(parentRoot, decodedUrl);
          if (fs.existsSync(filePath)) {
            const stat = fs.statSync(filePath);
            const ext = path.extname(filePath).toLowerCase();
            const mimeMap: Record<string, string> = {
              '.mp3': 'audio/mpeg',
              '.flac': 'audio/flac',
              '.ogg': 'audio/ogg',
              '.m4a': 'audio/mp4',
              '.wav': 'audio/wav',
              '.opus': 'audio/opus',
              '.ass': 'text/plain; charset=utf-8',
              '.ssa': 'text/plain; charset=utf-8',
              '.jpg': 'image/jpeg',
              '.jpeg': 'image/jpeg',
              '.png': 'image/png',
              '.webp': 'image/webp',
              '.gif': 'image/gif',
              '.ttf': 'font/ttf',
              '.otf': 'font/otf',
              '.woff': 'font/woff',
              '.woff2': 'font/woff2',
              '.js': 'application/javascript',
              '.wasm': 'application/wasm',
            };
            const mime = mimeMap[ext] || 'application/octet-stream';
            const totalSize = stat.size;
            const rangeHeader = req.headers.range;

            res.setHeader('Access-Control-Allow-Origin', '*');
            res.setHeader('Accept-Ranges', 'bytes');

            if (rangeHeader) {
              // 解析 Range 头, 例如 "bytes=0-1023"
              const match = rangeHeader.match(/bytes=(\d*)-(\d*)/);
              if (match) {
                const start = match[1] ? parseInt(match[1], 10) : 0;
                const end = match[2] ? parseInt(match[2], 10) : totalSize - 1;
                const chunkSize = end - start + 1;

                if (start >= totalSize || end >= totalSize || start > end) {
                  res.writeHead(416, { 'Content-Range': `bytes */${totalSize}` });
                  res.end();
                  return;
                }

                res.writeHead(206, {
                  'Content-Type': mime,
                  'Content-Range': `bytes ${start}-${end}/${totalSize}`,
                  'Content-Length': chunkSize,
                });
                fs.createReadStream(filePath, { start, end }).pipe(res);
              } else {
                // Range 格式无法解析, 返回完整文件
                res.setHeader('Content-Type', mime);
                res.setHeader('Content-Length', totalSize);
                fs.createReadStream(filePath).pipe(res);
              }
            } else {
              res.setHeader('Content-Type', mime);
              res.setHeader('Content-Length', totalSize);
              fs.createReadStream(filePath).pipe(res);
            }
            return;
          }
        }

        // 代理 /static/info/* 到父目录 (歌曲详细配置, 按需加载)
        if (decodedUrl.startsWith('/static/info/')) {
          const filePath = path.join(parentRoot, decodedUrl);
          if (fs.existsSync(filePath)) {
            res.setHeader('Content-Type', 'application/json; charset=utf-8');
            res.setHeader('Access-Control-Allow-Origin', '*');
            fs.createReadStream(filePath).pipe(res);
            return;
          }
        }

        // 代理 /playlist.json 到父目录
        if (decodedUrl === '/playlist.json') {
          const filePath = path.join(parentRoot, 'playlist.json');
          if (fs.existsSync(filePath)) {
            res.setHeader('Content-Type', 'application/json; charset=utf-8');
            res.setHeader('Access-Control-Allow-Origin', '*');
            fs.createReadStream(filePath).pipe(res);
            return;
          }
        }

        // 代理 /music/ass-worker/* 到 HXLoLi 仓库的 static/music/ass-worker/
        // 因为 AssLyrics 加载 worker 用的路径是 baseUrl + 'music/ass-worker/...'
        if (decodedUrl.startsWith('/music/ass-worker/')) {
          // 优先查找本地 test/public/music/ass-worker/
          const localPath = path.join(__dirname, 'public', decodedUrl);
          if (fs.existsSync(localPath)) {
            const ext = path.extname(localPath).toLowerCase();
            const mime = ext === '.js' ? 'application/javascript'
                       : ext === '.wasm' ? 'application/wasm'
                       : ext === '.ttf' ? 'font/ttf'
                       : 'application/octet-stream';
            res.setHeader('Content-Type', mime);
            res.setHeader('Access-Control-Allow-Origin', '*');
            fs.createReadStream(localPath).pipe(res);
            return;
          }
          // 回退到 HXLoLi 仓库的 static/ 目录
          const hxloliPath = path.resolve(parentRoot, '..', 'HXLoLi', 'static', decodedUrl.slice(1));
          if (fs.existsSync(hxloliPath)) {
            const ext = path.extname(hxloliPath).toLowerCase();
            const mime = ext === '.js' ? 'application/javascript'
                       : ext === '.wasm' ? 'application/wasm'
                       : ext === '.ttf' ? 'font/ttf'
                       : 'application/octet-stream';
            res.setHeader('Content-Type', mime);
            res.setHeader('Access-Control-Allow-Origin', '*');
            fs.createReadStream(hxloliPath).pipe(res);
            return;
          }
        }

        next();
      });
    },
  };
}

export default defineConfig({
  plugins: [
    react(),
    serveParentStatic(),
  ],
  server: {
    port: 3000,
    open: true,
  },
  publicDir: 'public',
  build: {
    outDir: 'dist',
  },
});
