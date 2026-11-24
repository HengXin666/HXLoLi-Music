"""Real glyph metrics -> unit x positions (no guessing widths).

libass sizes a font so that (usWinAscent + usWinDescent) == \\fs, so the em the
glyphs are drawn at is fs * upem / (winAscent + winDescent). We measure advances
with Pillow at that em; measured against libass ink on 2026-11-20 within 1%.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PIL import ImageFont
import struct

from kfx_lyrics import Line


@dataclass(frozen=True)
class FontSpec:
    name: str        # family name written into the ASS style
    file: Path       # ttf used for measuring (must be the same font the player loads)
    bold: bool = False
    italic: bool = False


def _tables(path: str) -> dict[str, tuple[int, int]]:
    """sfnt table directory (offset, length); first face of a .ttc. No fontTools needed."""
    with open(path, "rb") as f:
        head = f.read(12)
        base = 0
        if head[:4] == b"ttcf":
            f.seek(12)
            base = struct.unpack(">I", f.read(4))[0]
            f.seek(base)
            head = f.read(12)
        n = struct.unpack(">H", head[4:6])[0]
        out = {}
        for _ in range(n):
            tag, _sum, off, ln = struct.unpack(">4sIII", f.read(16))
            out[tag.decode("latin1")] = (off, ln)
    return out


@lru_cache(maxsize=None)
def _em_ratio(path: str) -> float:
    t = _tables(path)
    with open(path, "rb") as f:
        f.seek(t["head"][0] + 18)
        upem = struct.unpack(">H", f.read(2))[0]
        cell = 0
        if "OS/2" in t:
            f.seek(t["OS/2"][0] + 74)
            win_asc, win_desc = struct.unpack(">HH", f.read(4))
            cell = win_asc + win_desc
        if cell <= 0:
            f.seek(t["hhea"][0] + 4)
            asc, desc = struct.unpack(">hh", f.read(4))
            cell = asc - desc
    return upem / cell


@lru_cache(maxsize=None)
def _pil(path: str, px: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, px)


def advance(font: FontSpec, fs: float, text: str, spacing: float = 0.0) -> float:
    """Width libass will advance for `text` at style size `fs` (px in PlayRes)."""
    em = fs * _em_ratio(str(font.file))
    pil = _pil(str(font.file), 200)
    return pil.getlength(text) * em / 200.0 + spacing * len(text)


@dataclass
class Geometry:
    cx: float = 960.0
    jp_y: float = 842.0      # \an5 centre of the kanji row
    ruby_gap: float = 50.0   # ruby centre sits this far above jp centre
    zh_gap: float = 68.0     # zh centre sits this far below jp centre
    jp_fs: float = 70.0
    ruby_fs: float = 28.0
    zh_fs: float = 42.0
    lat_fs: float = 62.0
    word_gap: float = 26.0   # visual gap where the lyric has a space
    max_w: float = 1560.0    # wider lines are scaled down as a whole


@dataclass
class Placed:
    scale: float           # 1.0 normally, <1 when the line was too wide
    x0: float
    x1: float
    zh_w: float


def place_line(line: Line, geo: Geometry, jp: FontSpec, lat: FontSpec,
               ruby: FontSpec, zh: FontSpec, want: float = 1.0) -> Placed:
    """Fill unit.x (centre) / unit.w for a line; returns the line box."""
    widths = []
    for u in line.units:
        if u.latin:
            w = advance(lat, geo.lat_fs, u.text) + 10
        else:
            w = advance(jp, geo.jp_fs, u.text)
        if u.ruby:
            rw = advance(ruby, geo.ruby_fs, u.ruby, 1.0)
            w = max(w, rw + 4)    # never let furigana collide with the neighbour
        widths.append(w)
    gaps = [geo.word_gap if u.gap_before else 0.0 for u in line.units]
    total = sum(widths) + sum(gaps)
    scale = min(want, geo.max_w / total)
    x = geo.cx - total * scale / 2
    for u, w, g in zip(line.units, widths, gaps):
        x += g * scale
        u.w = w * scale
        u.x = x + u.w / 2
        x += u.w
    zh_w = advance(zh, geo.zh_fs, line.zh, 2.0)
    return Placed(scale, geo.cx - total * scale / 2, geo.cx + total * scale / 2, zh_w)


def ruby_slots(u, geo: Geometry, ruby: FontSpec, scale: float) -> list[tuple[float, str]]:
    """Centre x for each mora of a unit's furigana, spread over the ruby width."""
    pieces = [m.text for m in u.morae]
    if "".join(pieces) != u.ruby:
        pieces = [u.ruby]          # timing kana differs from ruby text: draw it whole
    ws = [advance(ruby, geo.ruby_fs * scale, p, 1.0) for p in pieces]
    total = sum(ws)
    x = u.x - total / 2
    out = []
    for p, w in zip(pieces, ws):
        out.append((x + w / 2, p))
        x += w
    return out
