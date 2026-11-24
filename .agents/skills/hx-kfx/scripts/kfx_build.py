"""hx-kfx build: lyrics.txt + timing.json + direction.json -> karaoke ASS.

usage: python kfx_build.py <project_dir> [--direction direction.kfx.json] [--out out.kfx.ass]

project_dir holds lyrics.txt and timing.json (see lyrics.py for formats).
Exit codes: 0 ok, 2 direction / input rejected.
"""
from __future__ import annotations

import argparse
import hashlib
import random
import sys
from dataclasses import fields
from pathlib import Path

import kfx_assw as assw
import kfx_direction as dirmod
import kfx_lyrics as lyrics
import kfx_manifest as manifest
import kfx_layout as layout
import kfx_shapes as shapes
from kfx_fx_scene import SceneFx
from kfx_fx_text import Slot, TextFx

LEAD = 0.75      # a line shows this long before its first syllable (when there is room)
MIN_LEAD = 0.30
HOLD = 0.70      # stays after its last syllable (when there is room)


class Ctx:
    def __init__(self, geo, fonts):
        self.geo = geo
        self.fonts = fonts
        self.events: list[assw.Event] = []
        self.line_x0 = self.line_x1 = 960.0
        self.zh_w = 0.0
        self.sung_extra: dict[int, str] = {}


def schedule(lines, xd_of) -> list[Slot]:
    """One line on screen at a time; back-to-back lines crossfade.

    A line enters LEAD before its first syllable, but never before the previous line's
    last syllable has finished: when the singer leaves no gap the new line simply arrives
    as it is sung. The old line starts leaving just before the new one arrives and, if the
    gap is tight, leaves fast (>= 0.22 s), so two lines never sit on top of each other.
    """
    tins = []
    for i, ln in enumerate(lines):
        prev_e = lines[i - 1].e + 0.10 if i else 0.0
        tins.append(max(ln.s - LEAD, prev_e))
    slots = []
    for i, ln in enumerate(lines):
        nxt = tins[i + 1] if i + 1 < len(lines) else ln.e + 99
        tout = max(ln.e + 0.02, min(ln.e + HOLD, nxt - 0.05))
        # when the next line is already arriving, leave fast so the two never pile up
        room = nxt - tout + 0.2
        xd = xd_of(i) if i + 1 == len(lines) else max(0.22, min(xd_of(i), room))
        slots.append(Slot(tins[i], tout, xd))
    return slots


def _font(spec: dict, root: Path) -> layout.FontSpec:
    f = Path(spec["file"])
    if not f.is_absolute():
        f = (root / f).resolve()
    if not f.exists():
        raise dirmod.DirectionError(f"font file not found: {f}")
    return layout.FontSpec(spec["name"], f, bool(spec.get("bold")), bool(spec.get("italic")))


def title_card(ctx: Ctx, tc: dict, rnd):
    """opening card over the intro: song title, its meaning, the show it closes."""
    E, g = ctx.events, ctx.geo
    t0, t1 = float(tc["t0"]), float(tc["t1"])
    pal = tc["palette"]
    L = assw.ms(t1 - t0)
    halo = assw.col(pal["halo"])
    out = assw.col(pal["outline"])
    # lower third, so the card never sits on the MV's own subject in the middle of the frame
    rows = [("TITLE", tc["jp"], g.jp_y - 64, 0.0, pal["sung"]),
            ("TLAT", tc.get("latin", ""), g.jp_y + 8, 0.35, pal["glow"]),
            ("CARD", tc.get("credit", ""), g.jp_y + 58, 0.7, pal["base"]),
            ("CN", tc.get("zh", ""), g.jp_y + 104, 0.9, pal["zh"])]
    for st, text, y, d, c in rows:
        if not text:
            continue
        a = assw.ms(d)
        for layer, body in ((1, f"\\bord8\\1a&HFF&\\3c{halo}\\3a&HFF&\\t({a},{a + 900},\\3a&H70&)"),
                            (2, f"\\bord1.6\\1c{assw.col(c)}\\3c{out}\\alpha&HFF&\\t({a},{a + 900},\\alpha&H00&)")):
            E.append(assw.Event(layer, t0, t1, st,
                                f"{{\\an5\\pos({g.cx},{assw.f1(y)})\\shad0\\blur8\\fsp18"
                                f"\\t({a},{a + 1300},0.5,\\blur0.7\\fsp6){body}"
                                f"\\t({L - 900},{L},\\alpha&HFF&\\blur10\\fsp12)}}{text}", "card"))
    # a single glint crossing the title
    E.append(assw.Event(4, t0 + 1.2, t0 + 2.4, "FX",
                        f"{{\\an5\\move({g.cx - 260},{g.jp_y - 64},{g.cx + 260},{g.jp_y - 64})\\bord0\\shad0"
                        f"\\blur2\\1c{assw.col(pal['glow'])}\\alpha&H20&\\t(800,1200,\\alpha&HFF&)\\p1}}"
                        f"{shapes.sparkle(22)}", "card"))


def build(project: Path, dpath: Path, out: Path) -> dict:
    lines = lyrics.load(project / "lyrics.txt", project / "timing.json")
    D = dirmod.load(dpath, len(lines))
    raw = D.raw
    fonts = {k: _font(v, D.root) for k, v in raw["fonts"].items()}
    for need in ("jp", "ruby", "zh", "lat"):
        if need not in fonts:
            raise dirmod.DirectionError(f"fonts.{need} missing")
    geo = layout.Geometry(**{f.name: raw.get("geometry", {}).get(f.name, getattr(layout.Geometry(), f.name))
                             for f in fields(layout.Geometry)})
    ctx = Ctx(geo, fonts)
    tfx, sfx = TextFx(ctx), SceneFx(ctx)
    seed = int(hashlib.sha1(str(raw.get("seed", "hx-kfx")).encode()).hexdigest()[:8], 16)
    xd_of = lambda i: 0.75 if D.section_of(i).exit in ("shatter", "white", "erase") else 0.5
    slots = schedule(lines, xd_of)
    last = lines[-1].idx
    if raw.get("final_hold"):
        slots[-1].tout = max(slots[-1].tout, float(raw["final_hold"]))
    words = D.words
    if D.title:
        title_card(ctx, D.title, random.Random(seed))
    man_units = []
    for ln, slot in zip(lines, slots):
        rnd = random.Random(seed * 1000 + ln.idx)
        sec = D.section_of(ln.idx)
        pal = sec.palette
        placed = layout.place_line(ln, geo, fonts["jp"], fonts["lat"], fonts["ruby"], fonts["zh"], sec.scale)
        ctx.line_x0, ctx.line_x1, ctx.zh_w = placed.x0, placed.x1, placed.zh_w
        man_units.append(manifest.unit(ln, slot, placed, geo, sec))
        ctx.sung_extra = {}
        for m in D.moments_of(ln.idx):
            sfx.moment(m, ln, sec, slot, rnd)
        n = len(ln.units)
        lead = max(0.0, ln.s - slot.tin)
        stag = min(0.04, 0.45 / max(1, n), max(0.012, lead / max(1, n)))
        jp_scale = f"\\fscx{assw.f1(placed.scale * 100)}\\fscy{assw.f1(placed.scale * 100)}" \
            if abs(placed.scale - 1) > 1e-3 else ""
        for k, u in enumerate(ln.units):
            accent = next((w for w in words if _unit_in_word(ln, k, w["jp"])), None)
            sung_c = accent["color"] if accent else pal["sung"]
            glow_c = assw.mix(accent["color"], "#FFFFFF", 0.55) if accent else pal["glow"]
            appear = slot.tin + k * stag
            # exit wave runs left->right and finishes at tout, so the next line never waits
            exit_at = max(u.e + 0.02, slot.tout - (n - 1 - k) * min(0.025, stag))
            style = "LAT" if u.latin else "JP"
            text = (f"{{{jp_scale}}}" if jp_scale else "") + u.text
            tfx.glyph(style=style, text=text, x=u.x, y=geo.jp_y, slot=slot, appear=appear,
                      sing_s=u.s, sing_e=u.e, pal=pal, enter=sec.enter, exit_kind=sec.exit,
                      exit_at=exit_at, rnd=rnd, bord=2.2, halo_bord=7, sung_col=sung_c, glow_col=glow_c,
                      wipe_w=u.w, pop=1.16 if accent else 1.10, extra_sung=ctx.sung_extra.get(id(u), ""),
                      tag=f"L{ln.idx:02d}:jp-")
            if u.ruby:
                for (rx, piece), mo in zip(layout.ruby_slots(u, geo, fonts["ruby"], placed.scale),
                                           u.morae if len(u.morae) > 1 else [u.morae[0]]):
                    m_s = mo.s
                    m_e = mo.e if "".join(mm.text for mm in u.morae) == u.ruby else u.e
                    tfx.glyph(style="RB", text=(f"{{{jp_scale}}}" if jp_scale else "") + piece, x=rx, y=geo.jp_y - geo.ruby_gap * placed.scale,
                              slot=slot, appear=appear, sing_s=m_s, sing_e=m_e, pal=pal, enter=sec.enter,
                              exit_kind=sec.exit, exit_at=exit_at, rnd=rnd, bord=1.4, halo_bord=4,
                              sung_col=sung_c, glow_col=glow_c, wipe_w=geo.ruby_fs * placed.scale * len(piece) * 0.9,
                              pop=1.18, tag=f"L{ln.idx:02d}:rb-")
        tfx.zh_line(ln, slot, pal, sec.enter, sec.exit, words, rnd)
        sfx.onset_particles(ln, sec, rnd)
        sfx.ambient(ln, sec, slot, rnd)
    styles = [
        assw.style("JP", fonts["jp"].name, geo.jp_fs, bold=fonts["jp"].bold),
        assw.style("RB", fonts["ruby"].name, geo.ruby_fs, bold=fonts["ruby"].bold, spacing=1),
        assw.style("CN", fonts["zh"].name, geo.zh_fs, bold=fonts["zh"].bold, spacing=2),
        assw.style("LAT", fonts["lat"].name, geo.lat_fs, italic=True),
        assw.style("TITLE", fonts["jp"].name, 120, bold=fonts["jp"].bold),
        assw.style("TLAT", fonts["lat"].name, 50, italic=True, spacing=8),
        assw.style("CARD", fonts["jp"].name, 34, bold=fonts["jp"].bold, spacing=3),
        assw.style("FX", fonts["zh"].name, 20),
    ]
    song = raw.get("song", {})
    comments = [f"hx-kfx: generated from {dpath.name}; do not hand-edit, change the direction file",
                f"hx-kfx: sections {' '.join(s.id for s in D.sections)}"]
    doc = assw.document(song.get("title", project.name), styles, ctx.events, comments)
    out.write_text(doc, encoding="utf-8")
    manifest.write(out, man_units, dpath)
    return {"lines": len(lines), "events": len(ctx.events), "bytes": len(doc.encode()),
            "end": max(e.end for e in ctx.events), "last_line": last}


def _unit_in_word(line, k, word: str) -> bool:
    """True when unit k is part of an occurrence of `word` in the line's plain text."""
    plain = [u.text for u in line.units]
    starts = []
    acc = 0
    for t in plain:
        starts.append(acc)
        acc += len(t)
    full = "".join(plain)
    a, b = starts[k], starts[k] + len(plain[k])
    i = full.find(word)
    while i >= 0:
        if a < i + len(word) and b > i:
            return True
        i = full.find(word, i + 1)
    return False


def main(argv=None) -> int:
    """CLI entry: build one song from its direction file.

    Decision: .agents/notes/implemented/architecture/2026-11-20-hx-kfx-v2-direction-engine.md
    """
    ap = argparse.ArgumentParser(prog="hx-kfx build")
    ap.add_argument("project", type=Path)
    ap.add_argument("--direction", default="direction.kfx.json")
    ap.add_argument("--out", default="out.kfx.ass")
    a = ap.parse_args(argv)
    try:
        info = build(a.project, a.project / a.direction, a.project / a.out)
    except dirmod.DirectionError as e:
        print(e, file=sys.stderr)
        return 2
    print(f"wrote {a.project / a.out}: {info}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
