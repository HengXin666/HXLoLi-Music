#!/usr/bin/env python3
"""
音乐播放列表生成脚本

扫描 music/ 目录下的音频文件, 提取元数据, 自动生成 playlist.json

此脚本设计用于在 HXLoLi-Music 仓库根目录下运行:
    cd py && uv run python -m music.gen_music_playlist

生成的 playlist.json 通过 jsDelivr CDN 被 HXLoLi 主仓库运行时加载
URL 均为相对路径 (如 /music/xxx.mp3), 前端会拼接 CDN 前缀

依赖 (由 uv 管理):
    mutagen, requests

支持的音频格式: mp3, flac, ogg, m4a, wav, opus
"""

import json

from .config import OUTPUT_FILE, PROJECT_ROOT, INFO_DIR
from .cache import load_cache, save_cache
from .fonts import ensure_cjk_fallback_font
from .scanner import scan_music_dir


# 需要从 playlist.json 拆分到 info/{id}.json 的重字段
# 这些字段体积大 (如 assBoundsTimeline、assImageData)，按需加载以减小 playlist.json 体积
DETAIL_FIELDS = [
    'assFontMap', 'assImages', 'assImageData',
    'assBounds', 'assBoundsTimeline', 'fonts',
]


def split_track_detail(track: dict) -> tuple[dict, dict | None]:
    """将 track 拆分为元信息 (playlist) 和详细配置 (info)

    Returns:
        (meta, detail): meta 保留在 playlist.json, detail 写入 info/{id}.json
        如果没有详细配置字段, detail 为 None
    """
    meta = {}
    detail = {}
    for key, value in track.items():
        if key in DETAIL_FIELDS:
            detail[key] = value
        else:
            meta[key] = value
    return meta, detail if detail else None


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

    # 拆分: playlist.json 仅保留元信息, 详细配置写入 static/info/{id}.json
    meta_tracks = []
    detail_count = 0
    INFO_DIR.mkdir(parents=True, exist_ok=True)

    for track in tracks:
        meta, detail = split_track_detail(track)
        meta_tracks.append(meta)

        if detail:
            detail_path = INFO_DIR / f"{track['id']}.json"
            with open(detail_path, 'w', encoding='utf-8') as f:
                f.write(json.dumps(detail, ensure_ascii=False, indent=4) + '\n')
            detail_count += 1

    ts_content = generate_json(meta_tracks)

    # 确保输出目录存在
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(ts_content)

    # 保存缓存
    save_cache()

    print(f"[完成] 已写入: {OUTPUT_FILE.relative_to(PROJECT_ROOT)}")
    if detail_count > 0:
        print(f"[完成] 已写入 {detail_count} 个详细配置到: {INFO_DIR.relative_to(PROJECT_ROOT)}/")
    print()

    # 打印摘要
    for i, t in enumerate(tracks, 1):
        ass_mark = "🎤" if "assUrl" in t else "  "
        cover_mark = "🖼️" if "coverUrl" in t else "  "
        font_mark = "🔤" if "assFonts" in t else "  "
        print(f"  {i:2d}. {ass_mark}{cover_mark}{font_mark} {t['title']} - {t['artist']}")


if __name__ == '__main__':
    main()
