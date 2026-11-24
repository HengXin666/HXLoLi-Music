"""direction.json: every design decision for one song, each with its reason.

The generator never invents colours, motifs or moments; it only executes this file.
Validation fails (exit code 2) instead of silently falling back.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
ENTERS = {"ink", "drift", "drop", "flash", "wind"}
EXITS = {"rise", "dissolve", "shatter", "wind", "erase", "white", "veil"}
FLOWS = {"fall", "rise", "wind", "burst"}
MOTIFS = {"mote", "sparkle", "snow", "leaf", "petal", "droplet", "ember", "shard"}
MOMENTS = {"cracks", "magic_circle", "red_thread", "rays", "flip", "tear", "veil", "whiteout", "tilt"}
PALETTE_KEYS = ("base", "sung", "outline", "glow", "halo", "zh", "zh_sung")


class DirectionError(SystemExit):
    def __init__(self, msg: str):
        super().__init__(2)
        self.msg = msg

    def __str__(self):
        return self.msg


def luminance(h: str) -> float:
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (int(h[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


@dataclass
class Particles:
    motif: str = "mote"
    flow: str = "fall"
    per_unit: float = 1.0
    ambient: float = 0.0        # extra slow background pieces per second of the line
    size: tuple[float, float] = (6.0, 12.0)
    colors: list[str] = field(default_factory=list)


@dataclass
class Section:
    id: str
    lines: tuple[int, int]
    scene: str
    why: str
    palette: dict
    enter: str
    exit: str
    particles: Particles
    scale: float = 1.0          # >1 for short lines that carry the song's title / climax


@dataclass
class Moment:
    line: int
    kind: str
    why: str
    units: list[int] = field(default_factory=list)
    color: str = ""


@dataclass
class Direction:
    root: Path
    raw: dict
    sections: list[Section]
    moments: list[Moment]
    words: list[dict]
    title: dict | None

    def section_of(self, line: int) -> Section:
        for s in self.sections:
            if s.lines[0] <= line <= s.lines[1]:
                return s
        raise DirectionError(f"line {line} has no section")

    def moments_of(self, line: int) -> list[Moment]:
        return [m for m in self.moments if m.line == line]


def _need(d: dict, key: str, where: str):
    if key not in d or d[key] in ("", None):
        raise DirectionError(f"{where}: missing '{key}'")
    return d[key]


def load(path: Path, n_lines: int) -> Direction:
    raw = json.loads(path.read_text(encoding="utf-8"))
    errs: list[str] = []
    sections = []
    for i, s in enumerate(raw.get("sections", [])):
        where = f"sections[{i}]"
        try:
            pal = _need(s, "palette", where)
            for k in PALETTE_KEYS:
                if not HEX.match(str(pal.get(k, ""))):
                    errs.append(f"{where}.palette.{k} must be #RRGGBB")
            if all(HEX.match(str(pal.get(k, ""))) for k in ("base", "sung", "outline")):
                if luminance(pal["base"]) < 0.40:
                    errs.append(f"{where}: unsung 'base' too dark (L={luminance(pal['base']):.2f} < 0.40); "
                                "viewers read ahead on unsung text")
                if contrast(pal["base"], pal["outline"]) < 7:
                    errs.append(f"{where}: base/outline contrast {contrast(pal['base'], pal['outline']):.1f} < 7")
            p = s.get("particles", {})
            part = Particles(p.get("motif", "mote"), p.get("flow", "fall"), float(p.get("per_unit", 1)),
                             float(p.get("ambient", 0)), tuple(p.get("size", (6, 12))),
                             list(p.get("colors", [])))
            if part.motif not in MOTIFS:
                errs.append(f"{where}: motif {part.motif} not in {sorted(MOTIFS)}")
            if part.flow not in FLOWS:
                errs.append(f"{where}: flow {part.flow} not in {sorted(FLOWS)}")
            for c in part.colors:
                if not HEX.match(c):
                    errs.append(f"{where}: particle colour {c}")
            sec = Section(_need(s, "id", where), tuple(_need(s, "lines", where)), _need(s, "scene", where),
                          _need(s, "why", where), pal, s.get("enter", "ink"), s.get("exit", "rise"), part,
                          float(s.get("scale", 1.0)))
            if sec.enter not in ENTERS:
                errs.append(f"{where}: enter {sec.enter} not in {sorted(ENTERS)}")
            if sec.exit not in EXITS:
                errs.append(f"{where}: exit {sec.exit} not in {sorted(EXITS)}")
            sections.append(sec)
        except DirectionError as e:
            errs.append(e.msg)
    covered = {}
    for s in sections:
        for ln in range(s.lines[0], s.lines[1] + 1):
            if ln in covered:
                errs.append(f"line {ln} is in both {covered[ln]} and {s.id}")
            covered[ln] = s.id
    missing = [i for i in range(n_lines) if i not in covered]
    if missing:
        errs.append(f"lines without a section: {missing}")
    moments = []
    for i, m in enumerate(raw.get("moments", [])):
        where = f"moments[{i}]"
        if m.get("kind") not in MOMENTS:
            errs.append(f"{where}: kind {m.get('kind')} not in {sorted(MOMENTS)}")
            continue
        if not m.get("why"):
            errs.append(f"{where}: missing 'why'")
        if not (0 <= int(m.get("line", -1)) < n_lines):
            errs.append(f"{where}: line out of range")
            continue
        if m.get("color") and not HEX.match(m["color"]):
            errs.append(f"{where}: colour {m['color']}")
        moments.append(Moment(int(m["line"]), m["kind"], m.get("why", ""), list(m.get("units", [])),
                              m.get("color", "")))
    words = raw.get("words", [])
    for i, w in enumerate(words):
        if not (w.get("jp") and w.get("color") and w.get("why")):
            errs.append(f"words[{i}] needs jp, color, why")
        elif not HEX.match(w["color"]):
            errs.append(f"words[{i}].color must be #RRGGBB")
    if errs:
        raise DirectionError("direction.json rejected:\n  - " + "\n  - ".join(errs))
    return Direction(path.parent, raw, sections, moments, words, raw.get("title_card"))
