"""Lyrics + timing -> Line/Unit/Mora model.

lyrics.txt line format (one sung line per row, '#' rows are comments):
    MM:SS.mmm | <jp with ruby markup> | <zh>
ruby markup:
    [漢字|かな]          kanji group with furigana (one timing unit)
    {(If you do)|いふ}   latin/english phrase shown as-is, timed by its kana (one unit, no ruby)
every other non-space char is one unit; a space is a visual gap, not a unit.

timing.json: list of {line, unit, mora, text, s, e} (seconds). It is the time authority;
lyrics.txt only supplies glyphs, ruby and the translation.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

PUNCT = set("？！?!、。，,.…・「」『』")
TOKEN = re.compile(r"\[([^|\]]+)\|([^\]]+)\]|\{([^|}]+)\|([^}]+)\}|(\s+)|(.)")


@dataclass
class Mora:
    text: str
    s: float
    e: float


@dataclass
class Unit:
    text: str            # glyphs drawn on the main line
    ruby: str = ""       # furigana ('' = none)
    latin: bool = False  # english phrase -> latin font
    gap_before: bool = False
    morae: list[Mora] = field(default_factory=list)
    # filled by layout
    x: float = 0.0
    w: float = 0.0

    @property
    def s(self) -> float:
        return self.morae[0].s

    @property
    def e(self) -> float:
        return self.morae[-1].e


@dataclass
class Line:
    idx: int
    jp_raw: str
    zh: str
    units: list[Unit]

    @property
    def s(self) -> float:
        return self.units[0].s

    @property
    def e(self) -> float:
        return self.units[-1].e

    @property
    def plain(self) -> str:
        return "".join(u.text for u in self.units)


def parse_jp(raw: str) -> list[Unit]:
    units: list[Unit] = []
    gap = False
    for m in TOKEN.finditer(raw.strip()):
        kb, kr, lb, lr, sp, ch = m.groups()
        if sp:
            gap = True
            continue
        if kb:
            u = Unit(kb, kr)
        elif lb:
            u = Unit(lb.strip("()"), "", latin=True)
        elif ch in PUNCT and units:
            units[-1].text += ch   # punctuation is drawn but never timed
            continue
        else:
            u = Unit(ch)
        u.gap_before = gap and bool(units)
        gap = False
        units.append(u)
    return units


def read_lyrics(path: Path) -> list[tuple[str, str]]:
    rows = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw or raw.startswith("#"):
            continue
        parts = [p.strip() for p in raw.split("|")]
        # the jp column itself contains '|' inside ruby markup: rebuild it
        head, rest = raw.split("|", 1)
        jp, zh = rest.rsplit("|", 1)
        rows.append((jp.strip(), zh.strip()))
        del parts, head
    return rows


def load(lyrics_path: Path, timing_path: Path) -> list[Line]:
    rows = read_lyrics(lyrics_path)
    timing = json.loads(timing_path.read_text(encoding="utf-8"))
    by_line: dict[int, dict[int, list[Mora]]] = {}
    for t in timing:
        by_line.setdefault(t["line"], {}).setdefault(t["unit"], []).append(
            (t["mora"], Mora(t["text"], float(t["s"]), float(t["e"]))))
    if len(by_line) != len(rows):
        raise SystemExit(f"timing has {len(by_line)} lines, lyrics.txt has {len(rows)}")
    lines = []
    for i, (jp, zh) in enumerate(rows):
        units = parse_jp(jp)
        tu = by_line[i]
        if len(tu) != len(units):
            got = [u.text for u in units]
            raise SystemExit(f"line {i}: lyrics has {len(units)} units {got}, timing has {len(tu)}")
        for k, u in zip(sorted(tu), units):
            u.morae = [m for _, m in sorted(tu[k], key=lambda p: p[0])]
            if any(m.e <= m.s for m in u.morae):
                raise SystemExit(f"line {i} unit {k}: non-positive mora duration")
        lines.append(Line(i, jp, zh, units))
    for a, b in zip(lines, lines[1:]):
        if b.s < a.s:
            raise SystemExit(f"line {b.idx} starts before line {a.idx}")
    return lines
