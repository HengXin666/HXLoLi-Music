"""
目录扫描模块

扫描 static/music/ 目录, 收集所有音频文件及关联资源, 组装 track 数据
"""

import sys
from pathlib import Path

from .config import (
    STATIC_MUSIC_DIR, AUDIO_EXTENSIONS, FONT_DOWNLOAD_MAP, NON_ANIME_DIRS,
    COVER_EXTENSIONS,
)
from .cache import file_md5, get_file_id, path_to_url
from .metadata import extract_metadata, extract_cover_from_audio, find_matching_cover
from .ass_parser import (
    find_matching_ass, extract_ass_fonts, extract_ass_images,
    build_ass_image_data,
)
from .ass_prescan import prescan_ass_bounds
from .fonts import ensure_ass_fonts, find_fonts_in_dir
from .lyrics import find_lyric_variants, lyric_label


def anime_of(audio_path: Path) -> dict | None:
    """
    .agents/notes/implemented/feature/2026-11-02-playlist-anime-group.md
    番剧归属 = static/music/ 下的一级目录名 (原样, 不改写); 直接放在 static/music/ 根下或在 NON_ANIME_DIRS 里的为 None.
    """
    parts = audio_path.relative_to(STATIC_MUSIC_DIR).parts
    if len(parts) < 2 or parts[0] in NON_ANIME_DIRS:
        return None
    return {"title": parts[0]}


UNKNOWN_ARTIST = 'Unknown'
NAME_SEP = ' - '


def split_artist_title(title: str, artist: str) -> tuple[str, str]:
    """
    .agents/notes/implemented/feature/2026-11-25-playlist-artist-title-split.md
    标签里没有歌手时, 文件名 (此时就是 title) 按 "歌手 - 歌名" 拆开; 有歌手标签或标题里没有 " - " 的原样返回.
    """
    if artist.strip() and artist.strip() != UNKNOWN_ARTIST:
        return title, artist
    left, sep, right = title.partition(NAME_SEP)
    if not sep or not left.strip() or not right.strip():
        return title, artist
    return right.strip(), left.strip()


DIR_COVER_NAMES = ('cover', 'folder')


def dir_covers_of(audio_path: Path) -> dict[str, str]:
    """
    .agents/notes/implemented/feature/2026-11-25-playlist-dir-covers.md
    歌曲所在的每一级目录 (static/music/ 之下, 不含根) 里的 cover.* / folder.*: {相对 static/music/ 的目录路径: 图片 URL}.
    """
    out: dict[str, str] = {}
    rel_dirs = audio_path.parent.relative_to(STATIC_MUSIC_DIR).parts
    for depth in range(1, len(rel_dirs) + 1):
        d = STATIC_MUSIC_DIR.joinpath(*rel_dirs[:depth])
        for name in DIR_COVER_NAMES:
            hit = next((d / (name + ext) for ext in sorted(COVER_EXTENSIONS) if (d / (name + ext)).is_file()), None)
            if hit:
                out['/'.join(rel_dirs[:depth])] = path_to_url(hit)
                break
    return out


def ass_detail(ass_path: Path, audio_path: Path, meta: dict) -> dict | None:
    """
    一份 ASS 的红线检查 + 字体 / 图片 / 边界框字段 (assFonts assFontMap assImages assImageData assBounds assBoundsTimeline).
    红线未通过返回 None. 默认歌词和带标签的歌词 (lyrics.py) 都走这里.
    """
    out: dict = {}
    # Agent Notes: KFX 质量红线（静态拦截）
    # 

    # KFX 质量红线: 光有卡拉OK效果不算成品。
    # 判据见 
    # 其中注音层/特效贴合/配色三条已改为结构式判据, 见
    # 
    from .kfx_gate import run_gate
    gate = run_gate(ass_path)
    if gate is not None:
        if gate["ok"]:
            print(f"    └─ 红线: 通过 ({gate['events']} 事件, {gate['size_mb']:.1f} MB)")
        else:
            # 2026-11-28 用户: 进了 static/music 的都是在验收台发布过, 本人看过确认的 (白名单).
            # 红线只提示, 不再把歌挡在播放列表外.
            print(f"    └─ 红线 (仅提示, 已发布即放行): 未通过 — {'; '.join(gate['fails'])}")

    # 计算 ASS 文件哈希
    ass_hash = file_md5(ass_path)

    # 解析 ASS 中使用的字体名
    ass_fonts = extract_ass_fonts(ass_path, ass_hash)
    if ass_fonts:
        out["assFonts"] = ass_fonts
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
            out["assFontMap"] = font_map
            map_desc = ", ".join(f"{k} → {v.split('/')[-1]}" for k, v in font_map.items())
            print(f"    └─ 字体映射: {len(font_map)} 个 ({map_desc})")

    # 解析 ASS 中 \\1img 引用的外部图片
    # 渲染引擎已原生支持 \1img 纹理渲染, 只需将图片写入 Worker 虚拟 FS
    ass_images = extract_ass_images(ass_path, ass_hash)
    if ass_images:
        out["assImages"] = ass_images
        print(f"    └─ ASS 图片: {len(ass_images)} 个 ({', '.join(ass_images[:3])}{'...' if len(ass_images) > 3 else ''})")

        # 将图片编码为 base64, 供前端写入 Worker 虚拟文件系统
        image_data = build_ass_image_data(ass_path, ass_images)
        if image_data:
            out["assImageData"] = image_data

    # 用 ffmpeg 预扫描 ASS 字幕边界框 (滑动窗口 + EMA 平滑)
    duration = meta.get("duration", 0)
    if duration > 0:
        scan_result = prescan_ass_bounds(ass_path, duration, ass_hash)
        if scan_result:
            out["assBounds"] = scan_result['bounds']
            if scan_result.get('timeline'):
                out["assBoundsTimeline"] = scan_result['timeline']
                print(f"    └─ 时间轴 bounds: {len(scan_result['timeline'])} 个关键点")
    return out


def scan_music_dir() -> list[dict]:
    """
    .agents/notes/implemented/process/2026-09-28-kfx-quality-redline.md
扫描 static/music/ 目录, 收集所有音频文件信息"""
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

        title, artist = split_artist_title(meta["title"], meta["artist"])
        track = {
            "id": get_file_id(audio_path),
            "title": title,
            "artist": artist,
            "audioUrl": path_to_url(audio_path),
            "anime": anime_of(audio_path),
        }
        dir_covers = dir_covers_of(audio_path)
        if dir_covers:
            track["dirCovers"] = dir_covers

        if ass_path:
            track["assUrl"] = path_to_url(ass_path)
            print(f"    └─ 歌词: {ass_path.name}")
            detail = ass_detail(ass_path, audio_path, meta)
            if detail is None:
                print(f"    └─ 已跳过该曲目（不达标不进播放列表）")
                continue
            track.update(detail)

        # 一首歌多份歌词: <音频同名>.<标签>.ass (见 lyrics.py)
        variants = find_lyric_variants(audio_path)
        if variants:
            lyrics = []
            if ass_path:
                lyrics.append({"key": "default", "label": lyric_label(ass_path, "默认"), "assUrl": track["assUrl"]})
            for tag, vpath in variants:
                print(f"    └─ 歌词 [{tag}]: {vpath.name}")
                vdetail = ass_detail(vpath, audio_path, meta)
                if vdetail is None:
                    print(f"    └─ 歌词 [{tag}] 未过红线, 不挂")
                    continue
                detail_id = f"{track['id']}.{tag}"
                if all_fonts:
                    vdetail["fonts"] = [path_to_url(f) for f in all_fonts]
                lyrics.append({"key": tag, "label": lyric_label(vpath, tag), "assUrl": path_to_url(vpath),
                               "detailId": detail_id})
                track.setdefault("_lyricDetails", {})[detail_id] = vdetail
            if lyrics and (len(lyrics) > 1 or not ass_path):
                track["lyrics"] = lyrics

        if cover_path:
            track["coverUrl"] = path_to_url(cover_path)
            print(f"    └─ 封面: {cover_path.name}")

        if all_fonts:
            track["fonts"] = [path_to_url(f) for f in all_fonts]
            print(f"    └─ 字体文件: {len(all_fonts)} 个")

        tracks.append(track)

    return tracks
