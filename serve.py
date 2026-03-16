#!/usr/bin/env python3
"""
HXLoLi-Music 本地文件服务器 (FastAPI 异步版)

在本地开发 HXLoLi 时, 启动此服务器可以让前端直接读取本地仓库的音乐资源,
无需等待远程 CDN 更新.

使用方法:
    cd /path/to/HXLoLi-Music
    uv run serve.py          # 默认端口 9527
    uv run serve.py 8080     # 自定义端口

前端 (HXLoLi) 在本地开发模式 (localhost) 下会自动检测此服务器,
如果可用则从本地加载, 否则自动 fallback 到 jsDelivr CDN.
"""

import sys
import logging
from pathlib import Path
from urllib.parse import unquote

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

# 默认端口 (前端 musicDataLoader.ts 中的 LOCAL_MUSIC_SERVER 端口一致)
DEFAULT_PORT = 9527

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent


# ---------------------------------------------------------------------------
# 自定义日志: 用 emoji 区分不同类型的请求
# ---------------------------------------------------------------------------
class EmojiAccessFilter(logging.Filter):
    """
    过滤 uvicorn.access 日志, 只保留特定类型的请求.

    uvicorn 传入的 record.args 为:
        (client_addr, method, full_path, http_version, status_code)
    """

    # 需要记录的文件扩展名 -> emoji 映射
    _EXT_EMOJI: dict[str, str] = {
        '.json': '📋',
        '.mp3': '🎵', '.flac': '🎵', '.ogg': '🎵',
        '.m4a': '🎵', '.wav': '🎵', '.opus': '🎵',
        '.ass': '📝', '.ssa': '📝',
        '.ttf': '🔤', '.otf': '🔤', '.woff': '🔤', '.woff2': '🔤',
    }

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            (_client_addr, _method, full_path, _http_version, status_code) = record.args  # type: ignore[misc]
            path = unquote(full_path)
            status = str(status_code)
        except (ValueError, TypeError):
            return True

        # 非 200/206 的请求始终打印 (错误)
        if status not in ('200', '206'):
            record.msg = f"  ⚠️  {status} {path}"
            record.args = None
            return True

        # 匹配扩展名
        for ext, emoji in self._EXT_EMOJI.items():
            if path.endswith(ext):
                record.msg = f"  {emoji} {path}"
                record.args = None
                return True

        # 其他请求静默
        return False


# ---------------------------------------------------------------------------
# 创建 FastAPI 应用
# ---------------------------------------------------------------------------
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

# CORS: 允许所有来源
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "HEAD", "OPTIONS"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# 缓存控制中间件
# ---------------------------------------------------------------------------
@app.middleware("http")
async def add_cache_control(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response


# ---------------------------------------------------------------------------
# 路由: 捕获所有路径, 作为静态文件服务
# ---------------------------------------------------------------------------
@app.api_route("/{full_path:path}", methods=["GET", "HEAD"])
async def serve_file(request: Request, full_path: str):
    """提供静态文件服务, 支持 Range 请求 (音频 seek 必需)"""

    # 将 URL 路径映射到文件系统
    if not full_path or full_path == "/":
        full_path = "index.html"

    file_path = PROJECT_ROOT / full_path

    # 安全检查: 防止路径穿越
    try:
        file_path = file_path.resolve()
        if not str(file_path).startswith(str(PROJECT_ROOT)):
            return Response(status_code=403)
    except (OSError, ValueError):
        return Response(status_code=400)

    # 目录 -> 尝试 index.html
    if file_path.is_dir():
        file_path = file_path / "index.html"

    if not file_path.is_file():
        return Response(status_code=404)

    file_size = file_path.stat().st_size

    # HEAD 请求
    if request.method == "HEAD":
        from mimetypes import guess_type
        content_type = guess_type(str(file_path))[0] or "application/octet-stream"
        return Response(
            status_code=200,
            headers={
                "Content-Type": content_type,
                "Content-Length": str(file_size),
                "Accept-Ranges": "bytes",
            },
        )

    # Range 请求
    range_header = request.headers.get("range")
    if range_header:
        try:
            range_spec = range_header.replace("bytes=", "").strip()
            parts = range_spec.split("-")
            start = int(parts[0]) if parts[0] else 0
            end = int(parts[1]) if parts[1] else file_size - 1
        except (ValueError, IndexError):
            return Response(status_code=416, headers={
                "Content-Range": f"bytes */{file_size}",
            })

        # 范围校验
        if start >= file_size or end >= file_size or start > end:
            return Response(status_code=416, headers={
                "Content-Range": f"bytes */{file_size}",
            })

        content_length = end - start + 1
        from mimetypes import guess_type
        content_type = guess_type(str(file_path))[0] or "application/octet-stream"

        # 异步读取文件片段
        data = b""
        with open(file_path, "rb") as f:
            f.seek(start)
            data = f.read(content_length)

        return Response(
            content=data,
            status_code=206,
            headers={
                "Content-Type": content_type,
                "Content-Length": str(content_length),
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
            },
        )

    # 普通 GET 请求: 使用 FileResponse (支持异步文件发送)
    return FileResponse(
        path=file_path,
        headers={"Accept-Ranges": "bytes"},
    )


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------
def main():
    port = DEFAULT_PORT
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"[错误] 无效的端口号: {sys.argv[1]}")
            sys.exit(1)

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

    # 配置 uvicorn access 日志使用 emoji 过滤器 + 简洁格式化器
    log_config = uvicorn.config.LOGGING_CONFIG
    # 用简单的 formatter 替换 uvicorn 的 AccessFormatter (后者会解包 args)
    log_config["formatters"]["access"] = {
        "format": "%(message)s",
    }
    log_config["filters"] = {
        "emoji_access": {"()": __name__ + ".EmojiAccessFilter"},
    }
    log_config["handlers"]["access"]["filters"] = ["emoji_access"]
    # 关闭 uvicorn 默认的启动信息, 我们已经打印了自己的
    log_config["loggers"]["uvicorn"]["level"] = "WARNING"

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_config=log_config,
    )


if __name__ == "__main__":
    main()
