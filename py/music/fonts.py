"""
字体管理模块

CJK 字体下载、ASS 字体自动下载、字体文件查找
"""

from pathlib import Path

from .config import (
    FONTS_DIR, CJK_FONT_NAME, CJK_FONT_URL,
    FONT_DOWNLOAD_MAP, FONT_EXTENSIONS, STATIC_MUSIC_DIR,
)

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    import py7zr
    HAS_PY7ZR = True
except ImportError:
    HAS_PY7ZR = False


def ensure_cjk_fallback_font() -> bool:
    """确保 CJK fallback 字体文件存在

    如果不存在，尝试从 GitHub 下载 Noto Sans SC。
    返回字体是否可用。
    """
    font_path = FONTS_DIR / CJK_FONT_NAME
    if font_path.exists():
        print(f"[信息] CJK 字体已存在: {font_path.name}")
        return True

    if not HAS_REQUESTS:
        print(f"[警告] CJK 字体不存在且无法下载 (缺少 requests 库)")
        print(f"  请手动下载 Noto Sans SC 到: {font_path}")
        return False

    print(f"[信息] 下载 CJK 字体: {CJK_FONT_NAME} ...")
    FONTS_DIR.mkdir(parents=True, exist_ok=True)

    try:
        resp = requests.get(CJK_FONT_URL, stream=True, timeout=60)
        resp.raise_for_status()
        total = int(resp.headers.get('content-length', 0))
        downloaded = 0
        with open(font_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
                downloaded += len(chunk)
                if total > 0:
                    pct = downloaded * 100 // total
                    print(f"\r  下载进度: {pct}% ({downloaded}/{total})", end='', flush=True)
        print()
        print(f"[完成] CJK 字体已下载: {font_path.name} ({font_path.stat().st_size} bytes)")
        return True
    except Exception as e:
        print(f"\n[错误] 下载 CJK 字体失败: {e}")
        print(f"  请手动下载到: {font_path}")
        print(f"  URL: {CJK_FONT_URL}")
        if font_path.exists():
            font_path.unlink()
        return False


def _download_file(url: str, dest: Path, label: str = "") -> bool:
    """下载文件到 dest, 显示进度。返回是否成功。"""
    if not HAS_REQUESTS:
        print(f"    └─ [{label}] 无法自动下载 (缺少 requests 库)")
        return False
    try:
        resp = requests.get(url, stream=True, timeout=120)
        resp.raise_for_status()
        total = int(resp.headers.get('content-length', 0))
        downloaded = 0
        with open(dest, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
                downloaded += len(chunk)
                if total > 0:
                    pct = downloaded * 100 // total
                    print(f"\r         进度: {pct}% ({downloaded}/{total})", end='', flush=True)
        print()
        return True
    except Exception as e:
        print(f"\n         [错误] 下载失败: {e}")
        if dest.exists():
            dest.unlink()
        return False


def ensure_ass_fonts(ass_fonts: list[str], target_dir: Path) -> None:
    """检查 ASS 字体列表, 对配置表中有下载源的字体自动下载到 target_dir/fonts/

    支持直接下载 .ttf/.otf, 以及从 .7z 压缩包中提取指定文件。

    Args:
        ass_fonts: ASS 文件中引用的字体名列表
        target_dir: 歌曲所在目录 (字体将下载到 target_dir/fonts/)
    """
    if not ass_fonts:
        return

    fonts_dir = target_dir / "fonts"

    for font_name in ass_fonts:
        if font_name not in FONT_DOWNLOAD_MAP:
            continue

        info = FONT_DOWNLOAD_MAP[font_name]
        font_file = fonts_dir / info["file"]

        if font_file.exists():
            print(f"    └─ 字体已存在: {font_file.relative_to(STATIC_MUSIC_DIR)}")
            continue

        fonts_dir.mkdir(parents=True, exist_ok=True)
        url = info["url"]
        archive_path = info.get("archive_path")  # 压缩包内的目标文件路径

        if archive_path:
            # 需要从压缩包中提取
            if not HAS_PY7ZR and url.endswith('.7z'):
                print(f"    └─ [字体] '{font_name}' 需要 py7zr 解压, 请安装: uv add py7zr")
                print(f"         目标路径: {font_file}")
                continue

            print(f"    └─ [字体] 下载并解压 '{font_name}' ...")
            archive_file = fonts_dir / Path(url).name
            ok = _download_file(url, archive_file, label="字体")
            if not ok:
                print(f"         请手动下载到: {font_file}")
                continue

            # 解压目标文件
            try:
                if url.endswith('.7z'):
                    with py7zr.SevenZipFile(archive_file, mode='r') as z:
                        z.extract(targets=[archive_path], path=fonts_dir)
                    extracted = fonts_dir / archive_path
                    if extracted != font_file and extracted.exists():
                        extracted.rename(font_file)
                print(f"         [完成] {font_file.name} ({font_file.stat().st_size} bytes)")
            except Exception as e:
                print(f"         [错误] 解压失败: {e}")
                print(f"         请手动解压 {archive_file.name} 中的 {archive_path} 到 {font_file}")
            finally:
                if archive_file.exists():
                    archive_file.unlink()
        else:
            # 直接下载字体文件
            print(f"    └─ [字体] 下载 '{font_name}' -> {info['file']} ...")
            ok = _download_file(url, font_file, label="字体")
            if ok:
                print(f"         [完成] {font_file.name} ({font_file.stat().st_size} bytes)")
            else:
                print(f"         请手动下载到: {font_file}")


def find_fonts_in_dir(directory: Path) -> list[Path]:
    """查找目录及 fonts/ 子目录下的字体文件"""
    fonts = []
    # 检查 fonts/ 子目录
    fonts_dir = directory / "fonts"
    if fonts_dir.exists():
        for f in fonts_dir.iterdir():
            if f.suffix.lower() in FONT_EXTENSIONS:
                fonts.append(f)
    # 检查当前目录下的字体
    for f in directory.iterdir():
        if f.suffix.lower() in FONT_EXTENSIONS:
            fonts.append(f)
    return sorted(set(fonts))
