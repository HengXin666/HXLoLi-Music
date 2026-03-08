#!/usr/bin/env python3
"""
HXLoLi-Music 本地文件服务器

在本地开发 HXLoLi 时, 启动此服务器可以让前端直接读取本地仓库的音乐资源,
无需等待远程 CDN 更新.

使用方法:
    cd /path/to/HXLoLi-Music
    python3 serve.py          # 默认端口 9527
    python3 serve.py 8080     # 自定义端口

前端 (HXLoLi) 在本地开发模式 (localhost) 下会自动检测此服务器,
如果可用则从本地加载, 否则自动 fallback 到 jsDelivr CDN.
"""

import os
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from functools import partial
from urllib.parse import unquote

# 默认端口 (前端 musicDataLoader.ts 中的 LOCAL_MUSIC_SERVER 端口一致)
DEFAULT_PORT = 9527

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent


class CORSHandler(SimpleHTTPRequestHandler):
    """带 CORS 和 Range 请求支持的静态文件服务器

    - 允许跨域请求 (前端 localhost:3000 访问 localhost:9527)
    - 支持 Range 请求 (音频拖动进度条 / 断点续传)
    - 支持 HEAD 请求 (用于可用性检测)
    - 路由: / 映射到项目根目录 (playlist.json 在此)
    - 路由: /static/music/ 映射到 static/music/ 目录
    """

    # 使用 HTTP/1.1 以支持 Range 请求和持久连接
    protocol_version = "HTTP/1.1"

    def _add_cors_headers(self):
        """添加 CORS 和缓存控制头"""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, HEAD, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        # HTTP/1.1 默认 keep-alive, 但 SimpleHTTPRequestHandler 不支持, 必须显式关闭
        self.send_header('Connection', 'close')

    def end_headers(self):
        self._add_cors_headers()
        super().end_headers()

    def do_OPTIONS(self):
        """处理 CORS 预检请求"""
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        """处理 GET 请求, 支持 Range 头 (音频 seek 必需)"""
        range_header = self.headers.get('Range')
        if not range_header:
            # 无 Range 头, 走默认逻辑
            super().do_GET()
            return

        # 解析文件路径
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            super().do_GET()
            return

        try:
            file_size = os.path.getsize(path)
        except OSError:
            self.send_error(404, "File not found")
            return

        # 解析 Range: bytes=start-end
        try:
            range_spec = range_header.replace('bytes=', '').strip()
            parts = range_spec.split('-')
            start = int(parts[0]) if parts[0] else 0
            end = int(parts[1]) if parts[1] else file_size - 1
        except (ValueError, IndexError):
            self.send_error(416, "Invalid Range")
            return

        # 范围校验
        if start >= file_size or end >= file_size or start > end:
            self.send_response(416)
            self.send_header('Content-Range', f'bytes */{file_size}')
            self.end_headers()
            return

        content_length = end - start + 1
        content_type = self.guess_type(path)

        try:
            f = open(path, 'rb')
            f.seek(start)
            data = f.read(content_length)
            f.close()
        except OSError:
            self.send_error(500, "Internal Server Error")
            return

        self.send_response(206)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(content_length))
        self.send_header('Content-Range', f'bytes {start}-{end}/{file_size}')
        self.send_header('Accept-Ranges', 'bytes')
        self.end_headers()
        self.wfile.write(data)

    def do_HEAD(self):
        """处理 HEAD 请求, 添加 Accept-Ranges 头告知客户端支持 Range"""
        path = self.translate_path(self.path)
        if not os.path.isdir(path):
            try:
                file_size = os.path.getsize(path)
                content_type = self.guess_type(path)
                self.send_response(200)
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', str(file_size))
                self.send_header('Accept-Ranges', 'bytes')
                self.end_headers()
                return
            except OSError:
                pass
        super().do_HEAD()

    def log_message(self, format, *args):
        """自定义日志格式"""
        path = unquote(args[0].split(' ')[1]) if args else ''
        status = args[1] if len(args) > 1 else ''
        # 只打印非 200/206 或者非静态资源的请求
        if str(status) not in ('200', '206'):
            print(f"  ⚠️  {status} {path}")
        elif path.endswith('.json'):
            print(f"  📋 {path}")
        elif any(path.endswith(ext) for ext in ('.mp3', '.flac', '.ogg', '.m4a', '.wav', '.opus')):
            print(f"  🎵 {path}")
        elif any(path.endswith(ext) for ext in ('.ass', '.ssa')):
            print(f"  📝 {path}")
        elif any(path.endswith(ext) for ext in ('.ttf', '.otf', '.woff', '.woff2')):
            print(f"  🔤 {path}")
        # 其他请求静默


def main():
    port = DEFAULT_PORT
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"[错误] 无效的端口号: {sys.argv[1]}")
            sys.exit(1)

    os.chdir(PROJECT_ROOT)

    handler = partial(CORSHandler, directory=str(PROJECT_ROOT))

    # 允许端口重用, 避免服务器重启时 "Address already in use" 错误
    class ReusableHTTPServer(HTTPServer):
        allow_reuse_address = True
        allow_reuse_port = True

    server = ReusableHTTPServer(('0.0.0.0', port), handler)

    print("=" * 50)
    print("🎵 HXLoLi-Music 本地文件服务器")
    print("=" * 50)
    print()
    print(f"  📂 根目录:  {PROJECT_ROOT}")
    print(f"  🌐 地址:    http://localhost:{port}")
    print()
    print("  前端 (HXLoLi) 在 localhost 开发模式下会自动检测此服务器")
    print("  修改文件后刷新页面即可看到最新效果, 无需推送到远程")
    print()
    print("  按 Ctrl+C 停止服务器")
    print("=" * 50)
    print()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n[信息] 服务器已停止")
        server.server_close()


if __name__ == '__main__':
    main()
