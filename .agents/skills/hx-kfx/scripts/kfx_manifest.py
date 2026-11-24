"""Unit list for the HX ASS Studio (scripts/studio in hx-anime-karaoke-ass).

The studio reads `<out stem>.manifest.json` next to the ASS to list lines, chars and timing.
Only the fields the studio reads are written: key/kind/name/label/lines/t/band/chars/params/cn.
"""
from __future__ import annotations

import json
from pathlib import Path


def unit(line, slot, placed, geo, sec) -> dict:
    chars = []
    for u in line.units:
        glyphs = list(u.text)
        n = max(1, len(glyphs))
        cw = u.w / n
        x0 = u.x - u.w / 2
        dt = (u.e - u.s) / n
        for i, ch in enumerate(glyphs):
            chars.append([ch, round(u.s + i * dt, 3), round(u.s + (i + 1) * dt, 3),
                          round(x0 + i * cw, 1), round(cw, 1)])
    top = geo.jp_y - geo.ruby_gap * placed.scale - geo.ruby_fs
    bottom = geo.jp_y + geo.zh_gap + geo.zh_fs
    return {"key": f"kfx#{line.idx}", "kind": "phrase", "name": f"L{line.idx:02d}", "label": f"L{line.idx:02d} {sec.id}",
            "lines": [line.idx], "t": [round(slot.tin, 3), round(slot.tout, 3)],
            "band": [round(placed.x0, 1), round(top, 1), round(placed.x1, 1), round(bottom, 1)],
            "chars": chars, "cn": line.zh,
            "params": {"fx": sec.id, "ent": sec.enter, "ext": sec.exit,
                       "th.hi": sec.palette["sung"], "th.glow": sec.palette["glow"], "th.dark": sec.palette["outline"]}}


def write(out_ass: Path, units: list[dict], direction: Path) -> Path:
    p = out_ass.with_name(out_ass.name[:-4] + ".manifest.json") if out_ass.name.endswith(".ass") \
        else out_ass.with_suffix(".manifest.json")
    doc = {"format": "hx-kfx", "version": 2, "inputs": {"direction": direction.name},
           "meta": {"text_lift": 0}, "units": units}
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    return p
