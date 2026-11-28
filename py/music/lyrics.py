"""
一首歌挂多份 ASS 歌词 (博客播放器可切换)

约定 (只看文件名, 不需要额外配置文件):
  <音频同名>.ass            默认歌词, key = "default", 排第一 (博客没选过时播它)
  <音频同名>.<标签>.ass     另一份歌词, key = 标签 (只允许 [A-Za-z0-9_-], 要进 URL 和 info 文件名), 按标签排序
展示名: ASS [Script Info] 里一行注释 "; lyric-label: <名字>" (ASS 注释, 渲染器忽略); 没有时默认歌词叫 "默认", 其它用标签.
有标签版本时 playlist 条目多一个 lyrics 数组; 每份带标签的歌词的字体 / 边界框写到 static/info/<id>.<标签>.json (detailId).
"""

import re
from pathlib import Path

from .config import ASS_EXTENSIONS

TAG_RE = re.compile(r'^[A-Za-z0-9_-]+$')
LABEL_RE = re.compile(r'^;\s*lyric-label:\s*(.+?)\s*$')


def find_lyric_variants(audio_path: Path) -> list[tuple[str, Path]]:
    """
    .agents/notes/implemented/feature/2026-11-26-playlist-multi-lyrics.md
    <音频同名>.<标签>.ass 的 (标签, 路径), 按标签排序; 不含默认的 <音频同名>.ass.
    """
    stem, out = audio_path.stem, []
    for f in audio_path.parent.iterdir():
        if not f.is_file() or f.suffix.lower() not in ASS_EXTENSIONS:
            continue
        if not f.name.startswith(stem + '.'):
            continue
        tag = f.name[len(stem) + 1:-len(f.suffix)]
        if TAG_RE.match(tag):
            out.append((tag, f))
    return sorted(out)


def lyric_label(ass_path: Path, default: str) -> str:
    """[Script Info] 里 "; lyric-label: xxx" 注释给的展示名, 没有就用 default."""
    try:
        with open(ass_path, encoding='utf-8-sig', errors='replace') as fh:
            for i, line in enumerate(fh):
                s = line.strip()
                if i > 0 and s.startswith('['):
                    break
                m = LABEL_RE.match(s)
                if m:
                    return m.group(1)
    except OSError:
        pass
    return default
