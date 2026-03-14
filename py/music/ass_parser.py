"""ASS 字幕文件解析模块

解析 ASS/SSA 字幕文件中的字体引用、\\1img 图片引用,
并将外部图片以 base64 方式记录供渲染引擎虚拟文件系统加载
"""
import re
import base64
from pathlib import Path

from .config import STATIC_MUSIC_DIR, ASS_EXTENSIONS
from .cache import get_cache, set_cache

# 匹配 ASS \\1img(path) 标签中的图片路径
_RE_ASS_IMG = re.compile(r'\\1img\(([^)]+)\)')


def _read_ass_text(ass_path: Path) -> str | None:
    """尝试多种编码读取 ASS 文件文本, 失败返回 None"""
    for encoding in ('utf-8-sig', 'utf-8', 'gbk', 'shift_jis', 'latin-1'):
        try:
            return ass_path.read_text(encoding=encoding)
        except (UnicodeDecodeError, UnicodeError):
            continue
    return None


def _extract_ass_fonts_impl(ass_path: Path) -> list[str]:
    """从 ASS 文件中解析 Style 行使用的字体名列表 — 实际计算逻辑

    返回去重后的字体名列表 (保留原始大小写)
    """
    fonts = set()
    try:
        text = _read_ass_text(ass_path)
        if text is None:
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


def _collect_static_image_paths(text: str) -> list[str]:
    """从 ASS 文本中收集所有静态 \\1img 图片路径 (去重, 保持顺序)

    过滤含 Lua 表达式的动态路径 (含 ! 或 $ 的)
    """
    seen: set[str] = set()
    paths: list[str] = []
    for match in _RE_ASS_IMG.finditer(text):
        rel = match.group(1).strip()
        if '!' in rel or '$' in rel:
            continue
        if rel not in seen:
            seen.add(rel)
            paths.append(rel)
    return paths


def _extract_ass_images_impl(ass_path: Path) -> list[str]:
    """从 ASS 文件中解析 \\1img(...) 引用的图片路径列表 — 实际计算逻辑

    \\1img 是 Aegisub 扩展标签, 用于在字幕中嵌入外部图片。
    返回去重后的相对路径列表 (相对于 ASS 文件所在目录)。
    注意: 路径中可能含有 Lua 表达式 (如 !math.fmod(...)!), 这类动态路径会被过滤掉。
    """
    try:
        text = _read_ass_text(ass_path)
        if text is None:
            return []
        return _collect_static_image_paths(text)
    except Exception as e:
        print(f"  [警告] 解析 ASS 图片失败 {ass_path.name}: {e}")
        return []


def extract_ass_images(ass_path: Path, ass_hash: str) -> list[str]:
    """提取 ASS 图片路径列表, 优先使用缓存"""
    cache_key = str(ass_path.relative_to(STATIC_MUSIC_DIR))
    cached = get_cache('ass_images', cache_key, ass_hash)
    if cached is not None:
        return cached.get('images', [])

    images = _extract_ass_images_impl(ass_path)
    set_cache('ass_images', cache_key, ass_hash, {'images': images})
    return images


def build_ass_image_data(ass_path: Path, image_paths: list[str]) -> dict[str, str]:
    """将 ASS \\1img 引用的外部图片编码为 base64 数据

    渲染引擎通过 Emscripten 虚拟文件系统加载图片, 原生支持 \\1img 纹理渲染。
    此函数将图片编码为 base64, 由前端写入 worker 的虚拟 FS。

    Args:
        ass_path: ASS 文件路径
        image_paths: \\1img 引用的相对路径列表

    Returns:
        dict: 相对路径 -> base64 编码数据 (data URI 格式)
    """
    if not image_paths:
        return {}

    result: dict[str, str] = {}
    missing: list[str] = []

    # MIME 类型映射
    ext_to_mime = {
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
        '.bmp': 'image/bmp',
    }

    for rel_path in image_paths:
        img_file = ass_path.parent / rel_path
        if not img_file.exists():
            missing.append(rel_path)
            continue

        img_data = img_file.read_bytes()
        ext = img_file.suffix.lower()
        mime = ext_to_mime.get(ext, 'application/octet-stream')
        b64 = base64.b64encode(img_data).decode('ascii')
        result[rel_path] = f"data:{mime};base64,{b64}"

    if missing:
        print(f"  [警告] 以下图片文件不存在: {', '.join(missing)}")

    if result:
        total_size = sum(len(v) for v in result.values())
        print(f"    └─ ASS 图片 base64: {len(result)} 个 ({total_size} bytes)")

    return result


def find_matching_ass(audio_path: Path) -> Path | None:
    """查找与音频文件同名的 ASS 歌词文件"""
    stem = audio_path.stem
    parent = audio_path.parent
    for ext in ASS_EXTENSIONS:
        ass_path = parent / (stem + ext)
        if ass_path.exists():
            return ass_path
    return None


# ---------- \1img Dialogue 事件解析 ----------

# ASS 时间格式: H:MM:SS.CC → 秒
def _ass_time_to_sec(t: str) -> float:
    """将 ASS 时间戳 (H:MM:SS.CC) 转为秒"""
    parts = t.strip().split(':')
    h = int(parts[0])
    m = int(parts[1])
    s_cs = parts[2].split('.')
    s = int(s_cs[0])
    cs = int(s_cs[1]) if len(s_cs) > 1 else 0
    return h * 3600 + m * 60 + s + cs / 100.0


# 正则: 提取 \pos(x,y)
_RE_POS = re.compile(r'\\pos\(\s*([\d.]+)\s*,\s*([\d.]+)\s*\)')
# 正则: 提取 \move(x1,y1,x2,y2[,t1,t2])
_RE_MOVE = re.compile(r'\\move\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*(?:,\s*([\d.]+)\s*,\s*([\d.]+)\s*)?\)')
# 正则: 提取 \fad(fadein,fadeout)
_RE_FAD = re.compile(r'\\fad\(\s*(\d+)\s*,\s*(\d+)\s*\)')
# 正则: 提取 \an(\d)
_RE_AN = re.compile(r'\\an(\d)')
# 正则: 提取绘图命令中的矩形 (m x y l x y l x y l x y)
_RE_DRAWING_RECT = re.compile(r'\}(m\s+[\d.-]+\s+[\d.-]+(?:\s+l\s+[\d.-]+\s+[\d.-]+)+)')


def _parse_drawing_size(drawing: str) -> tuple[float, float] | None:
    """从 ASS 绘图命令中提取边界框大小 (宽, 高)

    绘图命令如: m 0 0 l 100 0 l 100 80 l 0 80
    """
    coords = []
    for token in re.finditer(r'(?:m|l)\s+([\d.-]+)\s+([\d.-]+)', drawing):
        coords.append((float(token.group(1)), float(token.group(2))))
    if len(coords) < 2:
        return None
    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]
    w = max(xs) - min(xs)
    h = max(ys) - min(ys)
    return (w, h) if w > 0 and h > 0 else None


def extract_ass_image_events(ass_path: Path, ass_hash: str) -> list[dict] | None:
    """解析 ASS 中所有包含 \\1img 的 Dialogue 行, 提取图片事件信息

    注意: 渲染引擎已原生支持 \\1img 纹理渲染, 此函数仅作为备用方案保留。
    当渲染引擎已能正确处理 \\1img 时, 前端无需使用此数据进行叠加渲染。

    提取每个事件的:
    - 时间范围 (start, end)
    - 图片路径 (img)
    - 位置 (pos 或 move)
    - 淡入淡出 (fadIn, fadOut)
    - 锚点 (an)
    - 绘图区域大小 (drawW, drawH)

    Returns:
        事件列表, 如果没有 \\1img 则返回 None
    """
    cache_key = str(ass_path.relative_to(STATIC_MUSIC_DIR))
    cached = get_cache('ass_image_events', cache_key, ass_hash)
    if cached is not None:
        events = cached.get('events')
        if events:
            print(f"    └─ ASS 图片事件: 使用缓存 ({len(events)} 个)")
        return events if events else None

    text = _read_ass_text(ass_path)
    if text is None:
        set_cache('ass_image_events', cache_key, ass_hash, {'events': None})
        return None

    events: list[dict] = []

    for line in text.splitlines():
        line = line.strip()
        if not line.startswith('Dialogue:'):
            continue
        if '\\1img(' not in line:
            continue

        parts = line.split(',', 9)
        if len(parts) < 10:
            continue

        start_time = _ass_time_to_sec(parts[1])
        end_time = _ass_time_to_sec(parts[2])
        text_field = parts[9]

        # 提取 \1img 路径
        img_match = _RE_ASS_IMG.search(text_field)
        if not img_match:
            continue
        img_path = img_match.group(1).strip()

        event: dict = {
            'start': round(start_time, 3),
            'end': round(end_time, 3),
            'img': img_path,
        }

        # 提取 \pos 或 \move
        pos_match = _RE_POS.search(text_field)
        move_match = _RE_MOVE.search(text_field)
        if move_match:
            event['move'] = [
                float(move_match.group(1)),
                float(move_match.group(2)),
                float(move_match.group(3)),
                float(move_match.group(4)),
            ]
            if move_match.group(5) is not None:
                event['moveT'] = [
                    float(move_match.group(5)),
                    float(move_match.group(6)),
                ]
        elif pos_match:
            event['pos'] = [
                float(pos_match.group(1)),
                float(pos_match.group(2)),
            ]

        # 提取 \fad
        fad_match = _RE_FAD.search(text_field)
        if fad_match:
            event['fadIn'] = int(fad_match.group(1))
            event['fadOut'] = int(fad_match.group(2))

        # 提取 \an
        an_match = _RE_AN.search(text_field)
        if an_match:
            event['an'] = int(an_match.group(1))

        # 提取绘图命令获取显示区域大小
        draw_match = _RE_DRAWING_RECT.search(text_field)
        if draw_match:
            size = _parse_drawing_size(draw_match.group(1))
            if size:
                event['drawW'] = size[0]
                event['drawH'] = size[1]

        events.append(event)

    set_cache('ass_image_events', cache_key, ass_hash, {'events': events if events else None})

    if events:
        print(f"    └─ ASS 图片事件: {len(events)} 个")
        return events
    return None
