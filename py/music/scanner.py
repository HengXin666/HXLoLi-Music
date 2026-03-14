"""
目录扫描模块

扫描 static/music/ 目录, 收集所有音频文件及关联资源, 组装 track 数据
"""

import sys
from pathlib import Path

from .config import (
    STATIC_MUSIC_DIR, AUDIO_EXTENSIONS, FONT_DOWNLOAD_MAP,
)
from .cache import file_md5, get_file_id, path_to_url
from .metadata import extract_metadata, extract_cover_from_audio, find_matching_cover
from .ass_parser import (
    find_matching_ass, extract_ass_fonts, extract_ass_images,
    build_ass_image_data,
)
from .ass_prescan import prescan_ass_bounds
from .fonts import ensure_ass_fonts, find_fonts_in_dir


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
                # 自动下载配置表中有下载源的字体
                ensure_ass_fonts(ass_fonts, audio_path.parent)

                # 构建 assFontMap: 字体家族名 → 字体文件 URL 的映射
                # SubtitlesOctopus 的 availableFonts 需要此格式来正确加载字体
                font_map: dict[str, str] = {}
                local_fonts_dir = audio_path.parent / "fonts"
                for font_name in ass_fonts:
                    if font_name in FONT_DOWNLOAD_MAP:
                        info = FONT_DOWNLOAD_MAP[font_name]
                        font_file = local_fonts_dir / info["file"]
                        if font_file.exists():
                            font_map[font_name] = path_to_url(font_file)
                if font_map:
                    track["assFontMap"] = font_map
                    map_desc = ", ".join(f"{k} → {v.split('/')[-1]}" for k, v in font_map.items())
                    print(f"    └─ 字体映射: {len(font_map)} 个 ({map_desc})")

            # 解析 ASS 中 \\1img 引用的外部图片
            # 渲染引擎已原生支持 \1img 纹理渲染, 只需将图片写入 Worker 虚拟 FS
            ass_images = extract_ass_images(ass_path, ass_hash)
            if ass_images:
                track["assImages"] = ass_images
                print(f"    └─ ASS 图片: {len(ass_images)} 个 ({', '.join(ass_images[:3])}{'...' if len(ass_images) > 3 else ''})")

                # 将图片编码为 base64, 供前端写入 Worker 虚拟文件系统
                image_data = build_ass_image_data(ass_path, ass_images)
                if image_data:
                    track["assImageData"] = image_data

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
