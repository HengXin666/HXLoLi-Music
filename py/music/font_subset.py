"""
字体子集化

一首歌只用到几百个字, 却要下载整套 CJK 字体 (LXGW WenKai 23MB, Shippori 14MB, NotoSansSC 17MB),
歌词要等字体到齐才换成正确字形. 这里按每首歌 ASS 里实际出现的字符裁出子集字体,
写到 static/cdn/subset/<key>/<原文件名>, 文件名和字体家族名都不变, 前端无需改动.

- key = 原字体 md5 + 字符集 的哈希, 字体或歌词不变就复用上次的产物
- 裁剪失败 (缺 fontTools, 字体损坏) 时返回原字体, 不影响播放列表生成
- 本次没用到的旧子集在 cleanup_unused() 里删掉
"""

import hashlib
import re
import shutil
from pathlib import Path

from .cache import file_md5, path_to_url
from .config import PROJECT_ROOT

try:
    from fontTools import subset as _ft_subset
    from fontTools.ttLib import TTFont
    HAS_FONTTOOLS = True
except ImportError:  # pragma: no cover
    HAS_FONTTOOLS = False

SUBSET_DIR = PROJECT_ROOT / 'static' / 'cdn' / 'subset'
SUBSET_EXTS = {'.ttf', '.otf'}
# 小于这个体积的字体 (拉丁字体, kfx 符号字体) 裁了也省不了多少, 原样用
MIN_SUBSET_BYTES = 1 << 20

# 总是保留: ASCII 可见字符和全角空格, 防止库内部或换行符替换出的字缺形
_BASE_CHARS = {chr(c) for c in range(0x20, 0x7F)} | {'\u3000', '\u00A0'}
_OVERRIDE = re.compile(r'\{[^}]*\}')

_used: set[Path] = set()
_chars_cache: dict[tuple[str, str], frozenset[str]] = {}


def ass_chars(ass_paths: list[Path]) -> frozenset[str]:
    """ASS 里 Dialogue 正文实际出现的字符 (去掉 {...} 覆盖标签)."""
    out: set[str] = set(_BASE_CHARS)
    for p in ass_paths:
        key = (str(p), file_md5(p))
        if key not in _chars_cache:
            chars: set[str] = set()
            with open(p, encoding='utf-8-sig', errors='replace') as fh:
                for line in fh:
                    if not line.startswith('Dialogue:'):
                        continue
                    parts = line.rstrip('\r\n').split(',', 9)
                    if len(parts) < 10:
                        continue
                    text = _OVERRIDE.sub('', parts[9]).replace('\\N', '').replace('\\n', '').replace('\\h', ' ')
                    chars.update(text)
            _chars_cache[key] = frozenset(chars)
        out |= _chars_cache[key]
    return frozenset(out)


def subset_font(font_path: Path, chars: frozenset[str]) -> Path:
    """返回子集字体路径; 不能裁就返回原路径."""
    if not HAS_FONTTOOLS or font_path.suffix.lower() not in SUBSET_EXTS:
        return font_path
    if font_path.stat().st_size < MIN_SUBSET_BYTES:
        return font_path
    digest = hashlib.sha1((file_md5(font_path) + ''.join(sorted(chars))).encode('utf-8')).hexdigest()[:12]
    out = SUBSET_DIR / digest / font_path.name
    if out.is_file():
        _used.add(out.parent)
        return out
    try:
        opts = _ft_subset.Options()
        opts.layout_features = ['*']
        opts.name_IDs = ['*']
        opts.name_legacy = True
        opts.name_languages = ['*']
        opts.notdef_outline = True
        opts.glyph_names = False
        opts.hinting = False
        opts.recalc_bounds = True
        font = TTFont(str(font_path), lazy=False)
        sub = _ft_subset.Subsetter(opts)
        sub.populate(unicodes=[ord(c) for c in chars])
        sub.subset(font)
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_suffix(out.suffix + '.tmp')
        font.save(str(tmp))
        tmp.replace(out)
    except Exception as e:  # 字体损坏等: 用原字体
        print(f"    └─ [警告] 字体子集化失败, 用原字体: {font_path.name}: {e}")
        return font_path
    _used.add(out.parent)
    src_mb = font_path.stat().st_size / 1048576
    print(f"    └─ 字体子集: {font_path.name} {src_mb:.1f}MB → {out.stat().st_size / 1024:.0f}KB ({len(chars)} 字)")
    return out


def subset_url(url: str, chars: frozenset[str]) -> str:
    """/static/... 字体 URL → 子集字体 URL; 找不到文件就原样返回."""
    if not url.startswith('/'):
        return url
    p = PROJECT_ROOT / url.lstrip('/')
    if not p.is_file():
        return url
    return path_to_url(subset_font(p, chars))


def cleanup_unused() -> None:
    """删掉本次没用到的旧子集目录 (只在完整扫描后调用)."""
    if not SUBSET_DIR.is_dir():
        return
    for d in SUBSET_DIR.iterdir():
        if d.is_dir() and d not in _used:
            shutil.rmtree(d, ignore_errors=True)
            print(f"[信息] 删除旧字体子集: {d.name}")
