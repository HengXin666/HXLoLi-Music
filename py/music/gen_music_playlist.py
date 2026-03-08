#!/usr/bin/env python3
"""
音乐播放列表生成脚本

扫描 music/ 目录下的音频文件, 提取元数据, 自动生成 playlist.json

此脚本设计用于在 HXLoLi-Music 仓库根目录下运行:
    cd py && uv run python music/gen_music_playlist.py

生成的 playlist.json 通过 jsDelivr CDN 被 HXLoLi 主仓库运行时加载
URL 均为相对路径 (如 /music/xxx.mp3), 前端会拼接 CDN 前缀

依赖 (由 uv 管理):
    mutagen, requests

支持的音频格式: mp3, flac, ogg, m4a, wav, opus
"""

import os
import re
import sys
import json
import hashlib
from pathlib import Path

try:
    from mutagen import File as MutagenFile
    from mutagen.mp3 import MP3
    from mutagen.flac import FLAC
    from mutagen.oggvorbis import OggVorbis
    from mutagen.mp4 import MP4
    from mutagen.wave import WAVE
    from mutagen.oggopus import OggOpus
    from mutagen.id3 import ID3
    HAS_MUTAGEN = True
except ImportError:
    HAS_MUTAGEN = False
    print("[警告] 未安装 mutagen, 将使用文件名作为元数据")
    print("  安装: cd py && uv sync")
    print()

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

import struct
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed

# 项目根目录 (py/music/gen_music_playlist.py -> py/music -> py -> 项目根)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
STATIC_MUSIC_DIR = PROJECT_ROOT / "static" / "music"
FONTS_DIR = STATIC_MUSIC_DIR / "fonts"
OUTPUT_FILE = PROJECT_ROOT / "playlist.json"
CACHE_FILE = PROJECT_ROOT / ".playlist_cache.json"

# 支持的音频文件扩展名
AUDIO_EXTENSIONS = {'.mp3', '.flac', '.ogg', '.m4a', '.wav', '.opus'}
# ASS 字幕扩展名
ASS_EXTENSIONS = {'.ass', '.ssa'}
# 封面图片扩展名
COVER_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
# 字体扩展名
FONT_EXTENSIONS = {'.ttf', '.otf', '.woff', '.woff2'}

# baseUrl: 空字符串, 生成相对路径 (前端会拼接 CDN 前缀)
BASE_URL = ""

# CJK Fallback 字体下载 URL (Noto Sans SC - 支持简体中文、日文假名和常用汉字)
CJK_FONT_NAME = "NotoSansSC-Regular.ttf"
CJK_FONT_URL = (
    "https://github.com/google/fonts/raw/main/ofl/notosanssc/NotoSansSC%5Bwght%5D.ttf"
)

# 封面图片的 MIME -> 扩展名映射
MIME_TO_EXT = {
    'image/jpeg': '.jpg',
    'image/png': '.png',
    'image/webp': '.webp',
    'image/gif': '.gif',
}


# ========== 缓存机制 ==========
# 缓存文件记录每个资源文件的 MD5 及上次的计算结果
# 只有文件内容变更 (哈希变化) 时才重新计算, 避免重复调用 ffmpeg 等重操作

_cache_data: dict = {}  # 运行时缓存, 由 load_cache() 填充
_cache_dirty = False     # 标记缓存是否有更新, 用于决定是否写入文件


def load_cache() -> None:
    """从磁盘加载缓存文件"""
    global _cache_data
    if CACHE_FILE.exists():
        try:
            _cache_data = json.loads(CACHE_FILE.read_text(encoding='utf-8'))
            print(f"[缓存] 已加载缓存: {len(_cache_data)} 条记录")
        except (json.JSONDecodeError, Exception) as e:
            print(f"[缓存] 缓存文件损坏, 将重新生成: {e}")
            _cache_data = {}
    else:
        print("[缓存] 无缓存文件, 将全量计算")
        _cache_data = {}


def save_cache() -> None:
    """将缓存写入磁盘"""
    if not _cache_dirty:
        return
    try:
        CACHE_FILE.write_text(
            json.dumps(_cache_data, ensure_ascii=False, indent=2) + '\n',
            encoding='utf-8',
        )
        print(f"[缓存] 已保存缓存: {len(_cache_data)} 条记录")
    except Exception as e:
        print(f"[缓存] 保存缓存失败: {e}")


def file_md5(filepath: Path) -> str:
    """计算文件内容的 MD5 哈希 (用于缓存判断)"""
    h = hashlib.md5()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def get_cache(namespace: str, key: str, file_hash: str) -> dict | None:
    """从缓存中获取数据

    Args:
        namespace: 缓存命名空间 (如 'metadata', 'ass_fonts', 'ass_bounds')
        key: 缓存键 (通常是文件相对路径)
        file_hash: 当前文件的 MD5 哈希

    Returns:
        缓存的数据 dict, 如果缓存未命中或哈希不匹配则返回 None
    """
    cache_key = f"{namespace}:{key}"
    entry = _cache_data.get(cache_key)
    if entry and entry.get('hash') == file_hash:
        return entry.get('data')
    return None


def set_cache(namespace: str, key: str, file_hash: str, data: dict) -> None:
    """写入缓存数据"""
    global _cache_dirty
    cache_key = f"{namespace}:{key}"
    _cache_data[cache_key] = {
        'hash': file_hash,
        'data': data,
    }
    _cache_dirty = True


def get_file_id(filepath: Path) -> str:
    """生成文件唯一 ID (基于相对路径的 hash)"""
    rel = filepath.relative_to(STATIC_MUSIC_DIR)
    return hashlib.md5(str(rel).encode()).hexdigest()[:12]


def _extract_metadata_impl(filepath: Path) -> dict:
    """从音频文件中提取元数据 (标题、艺术家、时长) — 实际计算逻辑"""
    title = filepath.stem  # 默认使用文件名
    artist = "Unknown"
    duration = 0

    if not HAS_MUTAGEN:
        return {"title": title, "artist": artist, "duration": duration}

    try:
        audio = MutagenFile(str(filepath))
        if audio is None:
            return {"title": title, "artist": artist, "duration": duration}

        # 获取时长
        if hasattr(audio, 'info') and hasattr(audio.info, 'length'):
            duration = round(audio.info.length, 2)

        # 根据不同格式提取标签
        if isinstance(audio, MP3):
            # ID3 tags
            if audio.tags:
                title = str(audio.tags.get('TIT2', title))
                artist = str(audio.tags.get('TPE1', artist))
        elif isinstance(audio, FLAC):
            title = audio.get('title', [title])[0]
            artist = audio.get('artist', [artist])[0]
        elif isinstance(audio, (OggVorbis, OggOpus)):
            title = audio.get('title', [title])[0]
            artist = audio.get('artist', [artist])[0]
        elif isinstance(audio, MP4):
            # iTunes-style tags
            title = audio.tags.get('\xa9nam', [title])[0] if audio.tags else title
            artist = audio.tags.get('\xa9ART', [artist])[0] if audio.tags else artist
        elif isinstance(audio, WAVE):
            # WAV 文件一般没有标签
            pass
        else:
            # 尝试通用方式
            tags = getattr(audio, 'tags', None)
            if tags:
                if hasattr(tags, 'get'):
                    title = tags.get('title', [title])[0] if isinstance(tags.get('title', title), list) else tags.get('title', title)
                    artist = tags.get('artist', [artist])[0] if isinstance(tags.get('artist', artist), list) else tags.get('artist', artist)

    except Exception as e:
        print(f"  [警告] 无法读取 {filepath.name} 的元数据: {e}")

    return {"title": str(title), "artist": str(artist), "duration": duration}


def extract_metadata(filepath: Path, audio_hash: str) -> dict:
    """提取音频元数据, 优先使用缓存"""
    cache_key = str(filepath.relative_to(STATIC_MUSIC_DIR))
    cached = get_cache('metadata', cache_key, audio_hash)
    if cached is not None:
        print(f"    └─ 元数据: 使用缓存")
        return cached

    result = _extract_metadata_impl(filepath)
    set_cache('metadata', cache_key, audio_hash, result)
    return result


def extract_cover_from_audio(audio_path: Path, audio_hash: str) -> Path | None:
    """从音频文件中提取嵌入的封面图片，保存到同目录下

    如果同名封面已经存在则跳过。
    使用缓存: 如果音频文件未变更且封面文件仍存在, 则跳过提取。
    返回封面文件路径，无封面则返回 None。
    """
    if not HAS_MUTAGEN:
        return None

    stem = audio_path.stem
    parent = audio_path.parent

    # 如果同名封面已存在，跳过提取
    for ext in COVER_EXTENSIONS:
        if (parent / (stem + ext)).exists():
            return parent / (stem + ext)

    # 检查缓存: 上次提取过且音频没变, 说明确实没有嵌入封面
    cache_key = str(audio_path.relative_to(STATIC_MUSIC_DIR))
    cached = get_cache('cover_extract', cache_key, audio_hash)
    if cached is not None:
        cover_name = cached.get('cover_name')
        if cover_name:
            cover_path = parent / cover_name
            if cover_path.exists():
                return cover_path
        else:
            # 上次就没提取到封面, 且音频没变
            return None

    try:
        audio = MutagenFile(str(audio_path))
        if audio is None:
            return None

        img_data = None
        img_mime = None

        if isinstance(audio, MP3):
            # ID3 APIC frames
            if audio.tags:
                for key in audio.tags:
                    if key.startswith('APIC'):
                        apic = audio.tags[key]
                        img_data = apic.data
                        img_mime = apic.mime
                        break

        elif isinstance(audio, FLAC):
            # FLAC pictures
            if audio.pictures:
                pic = audio.pictures[0]
                img_data = pic.data
                img_mime = pic.mime

        elif isinstance(audio, MP4):
            # MP4/M4A covr atom
            if audio.tags and 'covr' in audio.tags:
                covers = audio.tags['covr']
                if covers:
                    cover = covers[0]
                    img_data = bytes(cover)
                    # MP4Cover.FORMAT_JPEG = 13, FORMAT_PNG = 14
                    if hasattr(cover, 'imageformat'):
                        img_mime = 'image/png' if cover.imageformat == 14 else 'image/jpeg'
                    else:
                        img_mime = 'image/jpeg'

        elif isinstance(audio, (OggVorbis, OggOpus)):
            # Ogg 格式嵌入封面 (metadata_block_picture)
            import base64
            from mutagen.flac import Picture
            pics = audio.get('metadata_block_picture', [])
            if pics:
                try:
                    pic = Picture(base64.b64decode(pics[0]))
                    img_data = pic.data
                    img_mime = pic.mime
                except Exception:
                    pass

        if img_data and img_mime:
            ext = MIME_TO_EXT.get(img_mime, '.jpg')
            cover_path = parent / (stem + ext)
            cover_path.write_bytes(img_data)
            print(f"    └─ 提取封面: {cover_path.name} ({len(img_data)} bytes)")
            set_cache('cover_extract', cache_key, audio_hash, {'cover_name': cover_path.name})
            return cover_path

    except Exception as e:
        print(f"  [警告] 提取封面失败 {audio_path.name}: {e}")

    # 没有嵌入封面, 也写入缓存避免下次重复尝试
    set_cache('cover_extract', cache_key, audio_hash, {'cover_name': None})
    return None


def _extract_ass_fonts_impl(ass_path: Path) -> list[str]:
    """从 ASS 文件中解析 Style 行使用的字体名列表 — 实际计算逻辑

    返回去重后的字体名列表 (保留原始大小写)
    """
    fonts = set()
    try:
        # ASS 文件可能用不同编码
        for encoding in ('utf-8-sig', 'utf-8', 'gbk', 'shift_jis', 'latin-1'):
            try:
                text = ass_path.read_text(encoding=encoding)
                break
            except (UnicodeDecodeError, UnicodeError):
                continue
        else:
            return []

        # 匹配 Style 行，提取 Fontname 字段 (Style 格式的第 2 个字段)
        # Format: Name, Fontname, Fontsize, ...
        for line in text.splitlines():
            line = line.strip()
            if line.startswith('Style:'):
                # Style: name,fontname,fontsize,...
                parts = line[6:].split(',')
                if len(parts) >= 2:
                    font_name = parts[1].strip()
                    if font_name and font_name != 'Arial':  # Arial 已有 fallback
                        fonts.add(font_name)

    except Exception as e:
        print(f"  [警告] 解析 ASS 字体失败 {ass_path.name}: {e}")

    return sorted(fonts)


def extract_ass_fonts(ass_path: Path, ass_hash: str) -> list[str]:
    """提取 ASS 字体列表, 优先使用缓存"""
    cache_key = str(ass_path.relative_to(STATIC_MUSIC_DIR))
    cached = get_cache('ass_fonts', cache_key, ass_hash)
    if cached is not None:
        print(f"    └─ ASS 字体: 使用缓存")
        return cached.get('fonts', [])

    fonts = _extract_ass_fonts_impl(ass_path)
    set_cache('ass_fonts', cache_key, ass_hash, {'fonts': fonts})
    return fonts


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


def find_matching_ass(audio_path: Path) -> Path | None:
    """查找与音频文件同名的 ASS 歌词文件"""
    stem = audio_path.stem
    parent = audio_path.parent
    for ext in ASS_EXTENSIONS:
        ass_path = parent / (stem + ext)
        if ass_path.exists():
            return ass_path
    return None


def find_matching_cover(audio_path: Path) -> Path | None:
    """查找与音频文件同名的封面图片"""
    stem = audio_path.stem
    parent = audio_path.parent
    for ext in COVER_EXTENSIONS:
        cover_path = parent / (stem + ext)
        if cover_path.exists():
            return cover_path
    # 也查找目录中的 cover.* / folder.*
    for name_prefix in ['cover', 'folder', 'albumart']:
        for ext in COVER_EXTENSIONS:
            cover_path = parent / (name_prefix + ext)
            if cover_path.exists():
                return cover_path
    return None


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


def path_to_url(filepath: Path) -> str:
    """将文件路径转换为 URL (相对于仓库根目录)"""
    rel = filepath.relative_to(PROJECT_ROOT)
    return f"{BASE_URL}/{rel.as_posix()}"


# ========== ASS 预扫描 (用 ffmpeg + libass 计算边界框) ==========
# 对应 C++ 版 preprocessLyricBoundingBoxes: 固定 1920x1080 画布, 采样帧扫描像素

# 预扫描分辨率 (与 C++ 版 _assParse.setFrameSize(1920, 1080) 一致)
PRESCAN_WIDTH = 1920
PRESCAN_HEIGHT = 1080
PRESCAN_FPS = 2  # 每秒采样帧数


def _scan_frame_rgba(data: bytes, width: int, height: int) -> dict:
    """扫描单帧 RGBA 原始数据, 返回该帧的 TwoBlockBounds.

    上下分区: y < midLine 归上区块, y >= midLine 归下区块.
    像素 RGB 非黑 视为有内容 (ffmpeg 渲染在黑底上, alpha 恒为 255).

    每个区块有独立的 left/right, 避免不同位置的内容互相干扰裁剪窗口.
    同时保留全局 left/right 用于兼容.
    """
    mid_line = height >> 1
    step = 2  # 隔行扫描加速
    top_y_min = float('inf')
    top_y_max = 0
    btm_y_min = float('inf')
    btm_y_max = 0
    # 全局 left/right (兼容)
    left = float('inf')
    right = 0
    # top/btm 独立 left/right
    left_t = float('inf')
    right_t = 0
    left_b = float('inf')
    right_b = 0

    row_bytes = width * 4  # RGBA, 每像素4字节
    for y in range(0, height, step):
        row_start = y * row_bytes
        for x in range(0, width, step):
            px = row_start + x * 4
            # 检查 RGB 任一通道非零 (ffmpeg 黑底上的字幕)
            if data[px] > 0 or data[px + 1] > 0 or data[px + 2] > 0:
                if x < left:
                    left = x
                if x + step > right:
                    right = x + step
                if y < mid_line:
                    if y < top_y_min:
                        top_y_min = y
                    if y + step > top_y_max:
                        top_y_max = y + step
                    if x < left_t:
                        left_t = x
                    if x + step > right_t:
                        right_t = x + step
                else:
                    if y < btm_y_min:
                        btm_y_min = y
                    if y + step > btm_y_max:
                        btm_y_max = y + step
                    if x < left_b:
                        left_b = x
                    if x + step > right_b:
                        right_b = x + step

    # 裁剪到画布范围
    if right > width:
        right = width
    if right_t > width:
        right_t = width
    if right_b > width:
        right_b = width
    if top_y_max > height:
        top_y_max = height
    if btm_y_max > height:
        btm_y_max = height

    return {
        'topYMin': top_y_min if top_y_min != float('inf') else 0,
        'topYMax': top_y_max,
        'btmYMin': btm_y_min if btm_y_min != float('inf') else 0,
        'btmYMax': btm_y_max,
        'left': left if left != float('inf') else 0,
        'right': right,
        'leftT': left_t if left_t != float('inf') else 0,
        'rightT': right_t,
        'leftB': left_b if left_b != float('inf') else 0,
        'rightB': right_b,
    }


def _merge_bounds(a: dict, b: dict) -> dict:
    """合并两个 bounds (取并集)

    对于 top/btm 区域: 如果一方的 yMax==0 表示该方无此区域, 则使用另一方的值
    对于 left/right: 如果一方的 right==0 表示该方无内容, 则使用另一方的值
    """
    # top 区域
    a_has_top = a['topYMax'] > 0
    b_has_top = b['topYMax'] > 0
    if a_has_top and b_has_top:
        top_y_min = min(a['topYMin'], b['topYMin'])
        top_y_max = max(a['topYMax'], b['topYMax'])
    elif a_has_top:
        top_y_min, top_y_max = a['topYMin'], a['topYMax']
    elif b_has_top:
        top_y_min, top_y_max = b['topYMin'], b['topYMax']
    else:
        top_y_min, top_y_max = 0, 0

    # btm 区域
    a_has_btm = a['btmYMax'] > 0
    b_has_btm = b['btmYMax'] > 0
    if a_has_btm and b_has_btm:
        btm_y_min = min(a['btmYMin'], b['btmYMin'])
        btm_y_max = max(a['btmYMax'], b['btmYMax'])
    elif a_has_btm:
        btm_y_min, btm_y_max = a['btmYMin'], a['btmYMax']
    elif b_has_btm:
        btm_y_min, btm_y_max = b['btmYMin'], b['btmYMax']
    else:
        btm_y_min, btm_y_max = 0, 0

    # 全局左右 (兼容)
    a_has_lr = a['right'] > 0
    b_has_lr = b['right'] > 0
    if a_has_lr and b_has_lr:
        left = min(a['left'], b['left'])
        right = max(a['right'], b['right'])
    elif a_has_lr:
        left, right = a['left'], a['right']
    elif b_has_lr:
        left, right = b['left'], b['right']
    else:
        left, right = 0, 0

    # top 区域独立左右
    a_has_lr_t = a.get('rightT', 0) > 0
    b_has_lr_t = b.get('rightT', 0) > 0
    if a_has_lr_t and b_has_lr_t:
        left_t = min(a['leftT'], b['leftT'])
        right_t = max(a['rightT'], b['rightT'])
    elif a_has_lr_t:
        left_t, right_t = a['leftT'], a['rightT']
    elif b_has_lr_t:
        left_t, right_t = b['leftT'], b['rightT']
    else:
        left_t, right_t = 0, 0

    # btm 区域独立左右
    a_has_lr_b = a.get('rightB', 0) > 0
    b_has_lr_b = b.get('rightB', 0) > 0
    if a_has_lr_b and b_has_lr_b:
        left_b = min(a['leftB'], b['leftB'])
        right_b = max(a['rightB'], b['rightB'])
    elif a_has_lr_b:
        left_b, right_b = a['leftB'], a['rightB']
    elif b_has_lr_b:
        left_b, right_b = b['leftB'], b['rightB']
    else:
        left_b, right_b = 0, 0

    return {
        'topYMin': top_y_min, 'topYMax': top_y_max,
        'btmYMin': btm_y_min, 'btmYMax': btm_y_max,
        'left': left, 'right': right,
        'leftT': left_t, 'rightT': right_t,
        'leftB': left_b, 'rightB': right_b,
    }


def _smooth_bounds_timeline(
    frame_bounds: list[dict],
    fps: int = PRESCAN_FPS,
    window_sec: float = 2.0,
    ema_alpha: float = 0.15,
) -> list[dict]:
    """对逐帧 bounds 序列做 滑动窗口并集 + EMA 平滑, 生成稳定的时间轴 bounds

    核心理念:
    - 空帧 (无字幕内容) 不参与滑动窗口并集计算
    - EMA 只在有内容的区间段内平滑, 空帧区间保持空状态
    - 扩张 (bounds 变大) 立即响应, 收缩 (bounds 变小) 缓慢衰减
    - 双向 EMA 消除正向滞后

    Args:
        frame_bounds: 每帧的 bounds dict 列表 (包含空帧)
        fps: 采样帧率
        window_sec: 滑动窗口半径 (秒)
        ema_alpha: EMA 平滑系数, 越小越平滑

    Returns:
        平滑后的 bounds 时间序列, 每项含 't' 时间戳
    """
    n = len(frame_bounds)
    if n == 0:
        return []

    window_frames = int(window_sec * fps)
    FIELDS_MIN = ['topYMin', 'btmYMin', 'left']    # 取 min 的字段
    FIELDS_MAX = ['topYMax', 'btmYMax', 'right']    # 取 max 的字段
    EMPTY = {'topYMin': 0, 'topYMax': 0, 'btmYMin': 0, 'btmYMax': 0, 'left': 0, 'right': 0, 'leftT': 0, 'rightT': 0, 'leftB': 0, 'rightB': 0}

    def has_content(b: dict) -> bool:
        return b['topYMax'] > 0 or b['btmYMax'] > 0 or b['right'] > 0

    # ---- 第 1 步: 滑动窗口并集 ----
    # 只合并有内容的帧, 空帧不参与
    windowed = []
    for i in range(n):
        lo = max(0, i - window_frames)
        hi = min(n, i + window_frames + 1)
        merged = None
        for j in range(lo, hi):
            fb = frame_bounds[j]
            if not has_content(fb):
                continue
            if merged is None:
                merged = dict(fb)
            else:
                merged = _merge_bounds(merged, fb)
        windowed.append(merged if merged else dict(EMPTY))

    # ---- 第 2 步: 正向 EMA 平滑 ----
    # 关键: 分区域检查——只有 top/btm/lr 区域都存在时才做 EMA
    # 如果某个区域当前帧不存在 (max=0), 直接用前一帧的值延续
    smoothed = [dict(windowed[0])]
    for i in range(1, n):
        prev = smoothed[-1]
        cur = windowed[i]
        cur_has = has_content(cur)
        prev_has = has_content(prev)

        if not cur_has:
            # 当前窗口无内容 → 直接标记为空
            smoothed.append(dict(EMPTY))
            continue

        if not prev_has:
            # 前一帧是空的, 当前有内容 → 不从空帧平滑, 直接用当前值
            smoothed.append(dict(cur))
            continue

        # 两帧都有内容 → 分区域 EMA 平滑
        s = {}

        # top 区域
        cur_has_top = cur['topYMax'] > 0
        prev_has_top = prev['topYMax'] > 0
        if cur_has_top and prev_has_top:
            s['topYMin'] = cur['topYMin'] if cur['topYMin'] < prev['topYMin'] else int(prev['topYMin'] + ema_alpha * (cur['topYMin'] - prev['topYMin']))
            s['topYMax'] = cur['topYMax'] if cur['topYMax'] > prev['topYMax'] else int(prev['topYMax'] + ema_alpha * (cur['topYMax'] - prev['topYMax']))
        elif cur_has_top:
            s['topYMin'] = cur['topYMin']; s['topYMax'] = cur['topYMax']
        elif prev_has_top:
            s['topYMin'] = prev['topYMin']; s['topYMax'] = prev['topYMax']
        else:
            s['topYMin'] = 0; s['topYMax'] = 0

        # btm 区域
        cur_has_btm = cur['btmYMax'] > 0
        prev_has_btm = prev['btmYMax'] > 0
        if cur_has_btm and prev_has_btm:
            s['btmYMin'] = cur['btmYMin'] if cur['btmYMin'] < prev['btmYMin'] else int(prev['btmYMin'] + ema_alpha * (cur['btmYMin'] - prev['btmYMin']))
            s['btmYMax'] = cur['btmYMax'] if cur['btmYMax'] > prev['btmYMax'] else int(prev['btmYMax'] + ema_alpha * (cur['btmYMax'] - prev['btmYMax']))
        elif cur_has_btm:
            s['btmYMin'] = cur['btmYMin']; s['btmYMax'] = cur['btmYMax']
        elif prev_has_btm:
            s['btmYMin'] = prev['btmYMin']; s['btmYMax'] = prev['btmYMax']
        else:
            s['btmYMin'] = 0; s['btmYMax'] = 0

        # 全局左右 (如果两帧都有内容则 right 一定 > 0)
        s['left'] = cur['left'] if cur['left'] < prev['left'] else int(prev['left'] + ema_alpha * (cur['left'] - prev['left']))
        s['right'] = cur['right'] if cur['right'] > prev['right'] else int(prev['right'] + ema_alpha * (cur['right'] - prev['right']))

        # top 区域独立左右
        cur_has_lr_t = cur.get('rightT', 0) > 0
        prev_has_lr_t = prev.get('rightT', 0) > 0
        if cur_has_lr_t and prev_has_lr_t:
            s['leftT'] = cur['leftT'] if cur['leftT'] < prev['leftT'] else int(prev['leftT'] + ema_alpha * (cur['leftT'] - prev['leftT']))
            s['rightT'] = cur['rightT'] if cur['rightT'] > prev['rightT'] else int(prev['rightT'] + ema_alpha * (cur['rightT'] - prev['rightT']))
        elif cur_has_lr_t:
            s['leftT'] = cur['leftT']; s['rightT'] = cur['rightT']
        elif prev_has_lr_t:
            s['leftT'] = prev['leftT']; s['rightT'] = prev['rightT']
        else:
            s['leftT'] = 0; s['rightT'] = 0

        # btm 区域独立左右
        cur_has_lr_b = cur.get('rightB', 0) > 0
        prev_has_lr_b = prev.get('rightB', 0) > 0
        if cur_has_lr_b and prev_has_lr_b:
            s['leftB'] = cur['leftB'] if cur['leftB'] < prev['leftB'] else int(prev['leftB'] + ema_alpha * (cur['leftB'] - prev['leftB']))
            s['rightB'] = cur['rightB'] if cur['rightB'] > prev['rightB'] else int(prev['rightB'] + ema_alpha * (cur['rightB'] - prev['rightB']))
        elif cur_has_lr_b:
            s['leftB'] = cur['leftB']; s['rightB'] = cur['rightB']
        elif prev_has_lr_b:
            s['leftB'] = prev['leftB']; s['rightB'] = prev['rightB']
        else:
            s['leftB'] = 0; s['rightB'] = 0

        smoothed.append(s)

    # ---- 第 3 步: 反向 EMA 再平滑一遍 (消除正向 EMA 的滞后) ----
    for i in range(n - 2, -1, -1):
        nxt = smoothed[i + 1]
        cur = smoothed[i]
        nxt_has = has_content(nxt)
        cur_has = has_content(cur)

        if not cur_has or not nxt_has:
            continue  # 空帧不参与反向平滑

        # top 区域: 双方都有 top 时才平滑
        if cur['topYMax'] > 0 and nxt['topYMax'] > 0:
            if nxt['topYMin'] < cur['topYMin']:
                cur['topYMin'] = nxt['topYMin']
            else:
                cur['topYMin'] = int(cur['topYMin'] + ema_alpha * (nxt['topYMin'] - cur['topYMin']))
            if nxt['topYMax'] > cur['topYMax']:
                cur['topYMax'] = nxt['topYMax']
            else:
                cur['topYMax'] = int(cur['topYMax'] + ema_alpha * (nxt['topYMax'] - cur['topYMax']))

        # btm 区域
        if cur['btmYMax'] > 0 and nxt['btmYMax'] > 0:
            if nxt['btmYMin'] < cur['btmYMin']:
                cur['btmYMin'] = nxt['btmYMin']
            else:
                cur['btmYMin'] = int(cur['btmYMin'] + ema_alpha * (nxt['btmYMin'] - cur['btmYMin']))
            if nxt['btmYMax'] > cur['btmYMax']:
                cur['btmYMax'] = nxt['btmYMax']
            else:
                cur['btmYMax'] = int(cur['btmYMax'] + ema_alpha * (nxt['btmYMax'] - cur['btmYMax']))

        # 全局左右
        if nxt['left'] < cur['left']:
            cur['left'] = nxt['left']
        else:
            cur['left'] = int(cur['left'] + ema_alpha * (nxt['left'] - cur['left']))
        if nxt['right'] > cur['right']:
            cur['right'] = nxt['right']
        else:
            cur['right'] = int(cur['right'] + ema_alpha * (nxt['right'] - cur['right']))

        # top 独立左右
        if cur.get('rightT', 0) > 0 and nxt.get('rightT', 0) > 0:
            if nxt['leftT'] < cur['leftT']:
                cur['leftT'] = nxt['leftT']
            else:
                cur['leftT'] = int(cur['leftT'] + ema_alpha * (nxt['leftT'] - cur['leftT']))
            if nxt['rightT'] > cur['rightT']:
                cur['rightT'] = nxt['rightT']
            else:
                cur['rightT'] = int(cur['rightT'] + ema_alpha * (nxt['rightT'] - cur['rightT']))

        # btm 独立左右
        if cur.get('rightB', 0) > 0 and nxt.get('rightB', 0) > 0:
            if nxt['leftB'] < cur['leftB']:
                cur['leftB'] = nxt['leftB']
            else:
                cur['leftB'] = int(cur['leftB'] + ema_alpha * (nxt['leftB'] - cur['leftB']))
            if nxt['rightB'] > cur['rightB']:
                cur['rightB'] = nxt['rightB']
            else:
                cur['rightB'] = int(cur['rightB'] + ema_alpha * (nxt['rightB'] - cur['rightB']))

    # ---- 第 4 步: 构建带时间戳的输出, 并去重相邻相同项 ----
    # 注意: 空帧的 bounds 全为 0, 前端碰到全 0 的点应跳过裁剪
    timeline = []
    prev_entry = None
    for i, s in enumerate(smoothed):
        t = round(i / fps, 2)
        entry = {
            't': t,
            'topYMin': s['topYMin'], 'topYMax': s['topYMax'],
            'btmYMin': s['btmYMin'], 'btmYMax': s['btmYMax'],
            'left': s['left'], 'right': s['right'],
            'leftT': s.get('leftT', 0), 'rightT': s.get('rightT', 0),
            'leftB': s.get('leftB', 0), 'rightB': s.get('rightB', 0),
        }
        # 相邻相同则跳过 (减少 JSON 体积), 但保留首尾
        if prev_entry is not None and i < n - 1:
            same = all(
                entry[k] == prev_entry[k]
                for k in ('topYMin', 'topYMax', 'btmYMin', 'btmYMax', 'left', 'right',
                          'leftT', 'rightT', 'leftB', 'rightB')
            )
            if same:
                continue
        timeline.append(entry)
        prev_entry = entry

    return timeline


def _prescan_ass_bounds_impl(ass_path: Path, duration_sec: float) -> dict | None:
    """用 ffmpeg 渲染 ASS 字幕并扫描像素, 计算时间轴 bounds — 实际计算逻辑

    新方案 (滑动窗口 + EMA 平滑):
    - 固定 1920x1080 画布
    - 以 2fps 采样整首歌
    - 逐帧记录独立 bounds
    - 滑动窗口 (±2s) 取并集 + EMA 平滑
    - 输出时间序列 + 全局 bounds 兼容旧逻辑

    Args:
        ass_path: ASS 字幕文件路径
        duration_sec: 歌曲总时长 (秒)

    Returns:
        包含 'bounds' (全局) 和 'timeline' (时间序列) 的 dict, 无内容返回 None
    """
    if duration_sec <= 0:
        print(f"    └─ [预扫描] 时长为 0, 跳过")
        return None

    # 检查 ffmpeg 是否可用
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        print(f"    └─ [预扫描] ffmpeg 不可用, 跳过")
        return None

    w, h = PRESCAN_WIDTH, PRESCAN_HEIGHT
    frame_size = w * h * 4  # RGBA 每帧字节数

    # 生成临时 fontconfig 配置, 将 ASS 中引用的字体映射到 CJK fallback 字体
    # 这样 ffmpeg 的 libass 在找不到原始字体时会使用 NotoSansSC, 与前端 SubtitlesOctopus 一致
    fonts_dir_str = str(FONTS_DIR).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    ass_fonts = _extract_ass_fonts_impl(ass_path)
    alias_entries = '\n'.join(
        f'  <alias><family>{fn}</family><accept><family>Noto Sans SC</family></accept></alias>'
        for fn in ass_fonts
    )
    fc_config = f"""<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "fonts.dtd">
<fontconfig>
  <dir>{fonts_dir_str}</dir>
{alias_entries}
</fontconfig>
"""
    fc_tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.conf', delete=False, encoding='utf-8')
    fc_tmp.write(fc_config)
    fc_tmp.close()
    fc_tmp_path = fc_tmp.name

    # ffmpeg 命令: 黑底 + ASS 字幕渲染, 输出 rawvideo RGBA
    # 注意: subtitles 滤镜需要对特殊字符转义
    # fontsdir 指向 fonts/ 目录, 配合 fontconfig 配置确保 CJK 字体 fallback
    ass_path_escaped = str(ass_path).replace('\\', '/').replace(':', '\\:').replace("'", "\\'")
    fonts_dir_escaped = str(FONTS_DIR).replace('\\', '/').replace(':', '\\:').replace("'", "\\'")
    cmd = [
        'ffmpeg',
        '-f', 'lavfi',
        '-i', f'color=c=black:s={w}x{h}:d={duration_sec:.2f}:r={PRESCAN_FPS}',
        '-vf', f"subtitles=filename='{ass_path_escaped}':fontsdir='{fonts_dir_escaped}'",
        '-f', 'rawvideo',
        '-pix_fmt', 'rgba',
        '-v', 'error',
        '-',
    ]

    # 设置 FONTCONFIG_FILE 环境变量, 让 libass 使用我们的字体映射配置
    env = os.environ.copy()
    env['FONTCONFIG_FILE'] = fc_tmp_path

    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
        )
    except Exception as e:
        print(f"    └─ [预扫描] ffmpeg 启动失败: {e}")
        return None

    # 逐帧记录 bounds (不再全局合并)
    frame_bounds: list[dict] = []
    global_bounds = {
        'topYMin': 0, 'topYMax': 0,
        'btmYMin': 0, 'btmYMax': 0,
        'left': 0, 'right': 0,
    }
    has_content = False

    try:
        while True:
            data = proc.stdout.read(frame_size)
            if len(data) < frame_size:
                break
            fb = _scan_frame_rgba(data, w, h)
            frame_bounds.append(fb)
            # 同时维护全局 bounds (兼容旧逻辑)
            if fb['topYMax'] > 0 or fb['btmYMax'] > 0 or fb['right'] > 0:
                if not has_content:
                    global_bounds = dict(fb)
                    has_content = True
                else:
                    global_bounds = _merge_bounds(global_bounds, fb)
    finally:
        proc.stdout.close()
        proc.wait()

    stderr_output = proc.stderr.read().decode(errors='replace').strip()
    proc.stderr.close()
    if stderr_output:
        print(f"    └─ [预扫描] ffmpeg stderr: {stderr_output[:200]}")

    # 清理临时 fontconfig 文件
    try:
        os.unlink(fc_tmp_path)
    except OSError:
        pass

    frame_count = len(frame_bounds)
    if not has_content:
        print(f"    └─ [预扫描] {frame_count} 帧, 无字幕内容")
        return None

    # 生成平滑时间轴 bounds
    timeline = _smooth_bounds_timeline(frame_bounds, PRESCAN_FPS)

    print(f"    └─ [预扫描] {frame_count} 帧, 全局 bounds: "
          f"top=[{global_bounds['topYMin']},{global_bounds['topYMax']}] "
          f"btm=[{global_bounds['btmYMin']},{global_bounds['btmYMax']}] "
          f"lr=[{global_bounds['left']},{global_bounds['right']}]")
    print(f"    └─ [预扫描] 时间轴: {len(timeline)} 个关键点 "
          f"(从 {frame_count} 帧去重压缩)")

    return {
        'bounds': global_bounds,
        'timeline': timeline,
    }


def prescan_ass_bounds(ass_path: Path, duration_sec: float, ass_hash: str) -> dict | None:
    """预扫描 ASS 字幕边界框, 优先使用缓存

    缓存键包含 ASS 哈希和时长, 任一变更则重新计算
    """
    cache_key = str(ass_path.relative_to(STATIC_MUSIC_DIR))
    # 将时长编入哈希, 因为同一 ASS 文件配不同时长音频会影响扫描帧数
    # 使用 v2 版缓存命名空间, 新方案的缓存格式与旧版不兼容
    combined_hash = f"{ass_hash}:{duration_sec:.2f}"
    cached = get_cache('ass_bounds_v2', cache_key, combined_hash)
    if cached is not None:
        result = cached.get('result')
        if result:
            bounds = result.get('bounds', {})
            timeline_len = len(result.get('timeline', []))
            print(f"    └─ [预扫描] 使用缓存: "
                  f"top=[{bounds.get('topYMin',0)},{bounds.get('topYMax',0)}] "
                  f"btm=[{bounds.get('btmYMin',0)},{bounds.get('btmYMax',0)}] "
                  f"lr=[{bounds.get('left',0)},{bounds.get('right',0)}] "
                  f"timeline={timeline_len}点")
        else:
            print(f"    └─ [预扫描] 使用缓存: 无字幕内容")
        return result

    result = _prescan_ass_bounds_impl(ass_path, duration_sec)
    set_cache('ass_bounds_v2', cache_key, combined_hash, {'result': result})
    return result


def scan_music_dir() -> list[dict]:
    """扫描 static/music/ 目录, 收集所有音频文件信息"""
    if not STATIC_MUSIC_DIR.exists():
        print(f"[错误] 音乐目录不存在: {STATIC_MUSIC_DIR}")
        sys.exit(1)

    tracks = []
    # 递归扫描所有音频文件
    audio_files = sorted([
        f for f in STATIC_MUSIC_DIR.rglob('*')
        if f.suffix.lower() in AUDIO_EXTENSIONS and f.is_file()
    ])

    if not audio_files:
        print("[信息] 没有找到音频文件")
        return tracks

    print(f"[信息] 找到 {len(audio_files)} 个音频文件")

    # 收集全局字体
    global_fonts = find_fonts_in_dir(STATIC_MUSIC_DIR)

    for audio_path in audio_files:
        print(f"  处理: {audio_path.relative_to(STATIC_MUSIC_DIR)}")

        # 计算音频文件哈希 (用于缓存判断)
        audio_hash = file_md5(audio_path)

        # 提取元数据
        meta = extract_metadata(audio_path, audio_hash)

        # 查找关联的 ASS 歌词
        ass_path = find_matching_ass(audio_path)

        # 尝试从音频文件中提取封面 (如果本地没有)
        cover_path = extract_cover_from_audio(audio_path, audio_hash)

        # 如果提取失败，查找已有封面文件
        if not cover_path:
            cover_path = find_matching_cover(audio_path)

        # 查找目录级字体 + 全局字体
        local_fonts = find_fonts_in_dir(audio_path.parent)
        all_fonts = sorted(set(global_fonts + local_fonts))

        track = {
            "id": get_file_id(audio_path),
            "title": meta["title"],
            "artist": meta["artist"],
            "audioUrl": path_to_url(audio_path),
        }

        if ass_path:
            track["assUrl"] = path_to_url(ass_path)
            print(f"    └─ 歌词: {ass_path.name}")

            # 计算 ASS 文件哈希
            ass_hash = file_md5(ass_path)

            # 解析 ASS 中使用的字体名
            ass_fonts = extract_ass_fonts(ass_path, ass_hash)
            if ass_fonts:
                track["assFonts"] = ass_fonts
                print(f"    └─ ASS 字体: {', '.join(ass_fonts)}")

            # 用 ffmpeg 预扫描 ASS 字幕边界框 (滑动窗口 + EMA 平滑)
            duration = meta.get("duration", 0)
            if duration > 0:
                scan_result = prescan_ass_bounds(ass_path, duration, ass_hash)
                if scan_result:
                    track["assBounds"] = scan_result['bounds']
                    if scan_result.get('timeline'):
                        track["assBoundsTimeline"] = scan_result['timeline']
                        print(f"    └─ 时间轴 bounds: {len(scan_result['timeline'])} 个关键点")

        if cover_path:
            track["coverUrl"] = path_to_url(cover_path)
            print(f"    └─ 封面: {cover_path.name}")

        if all_fonts:
            track["fonts"] = [path_to_url(f) for f in all_fonts]
            print(f"    └─ 字体文件: {len(all_fonts)} 个")

        tracks.append(track)

    return tracks


def generate_json(tracks: list[dict]) -> str:
    """生成 JSON 文件内容"""
    return json.dumps(tracks, ensure_ascii=False, indent=4) + '\n'


def main():
    print("=" * 50)
    print("🎵 音乐播放列表生成器")
    print("=" * 50)
    print()

    # 加载缓存
    load_cache()

    # 确保 CJK fallback 字体可用
    ensure_cjk_fallback_font()
    print()

    tracks = scan_music_dir()

    print()
    print(f"[信息] 共 {len(tracks)} 首歌曲")

    ts_content = generate_json(tracks)

    # 确保输出目录存在
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(ts_content)

    # 保存缓存
    save_cache()

    print(f"[完成] 已写入: {OUTPUT_FILE.relative_to(PROJECT_ROOT)}")
    print()

    # 打印摘要
    for i, t in enumerate(tracks, 1):
        ass_mark = "🎤" if "assUrl" in t else "  "
        cover_mark = "🖼️" if "coverUrl" in t else "  "
        font_mark = "🔤" if "assFonts" in t else "  "
        print(f"  {i:2d}. {ass_mark}{cover_mark}{font_mark} {t['title']} - {t['artist']}")


if __name__ == '__main__':
    main()
