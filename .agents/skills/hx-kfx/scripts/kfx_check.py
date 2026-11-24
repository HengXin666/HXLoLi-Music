"""Mechanical gates for a generated karaoke ASS. Every rule here can fail.

usage: python kfx_check.py <project_dir> [--ass out.kfx.ass] [--direction direction.kfx.json]
                                         [--render --fonts <dir>]
exit 0 = all pass, 1 = a gate failed, 2 = input rejected.

  G1 timing     every syllable (kanji row and each furigana mora) lights up at its own
                timing.json onset (+-15 ms); nothing lights before the line is on screen
  G2 bilingual  every line has its translation; every kanji unit has furigana
  G3 one line   two lyric lines never sit on screen together outside a fast exit
  G4 band       every effect starts and ends inside the lyric band (y 600..1080)
  G5 palette    unsung text readable (direction validation), sung clearly brighter
  G6 render     (--render) libass draws ink in the band at the middle of every line
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import kfx_direction as dirmod
import kfx_lyrics as lyrics

EV = re.compile(r"Dialogue: (\d+),(\d+):(\d+):([\d.]+),(\d+):(\d+):([\d.]+),([^,]*),([^,]*),0,0,0,,(.*)")
POS = re.compile(r"\\pos\(([-\d.]+),([-\d.]+)\)")
MOVE = re.compile(r"\\move\(([-\d.]+),([-\d.]+),([-\d.]+),([-\d.]+)")


def parse(ass: Path):
    out = []
    for ln in ass.read_text(encoding="utf-8-sig").splitlines():
        m = EV.match(ln)
        if m:
            s = int(m[2]) * 3600 + int(m[3]) * 60 + float(m[4])
            e = int(m[5]) * 3600 + int(m[6]) * 60 + float(m[7])
            out.append(dict(layer=int(m[1]), s=s, e=e, style=m[8], name=m[9], text=m[10]))
    return out


def gates(project: Path, ass: Path, dpath: Path) -> list[tuple[str, bool, str]]:
    lines = lyrics.load(project / "lyrics.txt", project / "timing.json")
    D = dirmod.load(dpath, len(lines))
    evs = parse(ass)
    res = []

    # G1: onsets
    sung_starts = sorted(e["s"] for e in evs if e["name"].endswith((":jp-sung", ":rb-sung")))
    miss = []
    import bisect
    for ln in lines:
        for u in ln.units:
            want = [u.s] + ([m.s for m in u.morae] if u.ruby else [])
            for t in want:
                i = bisect.bisect_left(sung_starts, t - 0.015)
                if i >= len(sung_starts) or abs(sung_starts[i] - t) > 0.015:
                    miss.append(f"line {ln.idx} '{u.text}' @{t:.2f}")
    res.append(("G1 timing", not miss, f"{len(miss)} syllables without an onset" + (f": {miss[:4]}" if miss else "")))

    # G2: bilingual + ruby
    no_zh = [ln.idx for ln in lines if not ln.zh.strip()]
    kanji = re.compile(r"[\u4e00-\u9fff々]")
    no_rb = [f"{ln.idx}:{u.text}" for ln in lines for u in ln.units if kanji.search(u.text) and not u.ruby]
    zh_ev = sum(1 for e in evs if e["name"].endswith(":zh-base"))
    ok = not no_zh and not no_rb and zh_ev == len(lines)
    res.append(("G2 bilingual+ruby", ok, f"zh events {zh_ev}/{len(lines)}, lines w/o zh {no_zh}, kanji w/o ruby {no_rb[:5]}"))

    # G3: one line at a time (base layers of consecutive lines must not coexist > 0.05 s)
    by_line: list[list[dict]] = [[] for _ in lines]
    for e in evs:
        m = re.match(r"L(\d+):(jp|rb|zh)-(base|sung|halo)$", e["name"])
        if m:
            by_line[int(m[1])].append(e)
    bad = []
    for i in range(len(lines) - 1):
        if not by_line[i] or not by_line[i + 1]:
            continue
        end_i = max(b["e"] for b in by_line[i])
        start_n = min(b["s"] for b in by_line[i + 1])
        if end_i - start_n > 0.08:
            bad.append(f"{i}->{i + 1} overlap {end_i - start_n:.2f}s")
    res.append(("G3 one line on screen", not bad, ", ".join(bad) or "no overlapping lines"))

    # G4: band
    out_band = []
    for e in evs:
        ys = [float(m[2]) for m in POS.finditer(e["text"])]
        for m in MOVE.finditer(e["text"]):
            ys += [float(m[2]), float(m[4])]
        if any(y < 600 or y > 1080 for y in ys) and e["name"] != "card":
            out_band.append(f"{e['name']}@{e['s']:.2f}")
    res.append(("G4 band", not out_band, f"{len(out_band)} events outside y 600..1080 {out_band[:4]}"))

    # G5: palette
    weak = [s.id for s in D.sections if dirmod.contrast(s.palette["sung"], s.palette["base"]) < 1.15
            and dirmod.luminance(s.palette["sung"]) <= dirmod.luminance(s.palette["base"])]
    res.append(("G5 palette", not weak, f"sections where sung is not brighter than unsung: {weak}"))
    return res


def render_gate(ass: Path, project: Path, fonts: Path) -> tuple[str, bool, str]:
    """one ffmpeg pass over a black clip at 4 fps, keeping only the mid-line frames."""
    from PIL import Image
    lines = lyrics.load(project / "lyrics.txt", project / "timing.json")
    idx = [round((ln.s + ln.e) / 2 * 4) for ln in lines]
    sel = "+".join(f"eq(n\\,{n})" for n in idx)
    empty = []
    with tempfile.TemporaryDirectory() as td:
        dur = max(idx) / 4 + 1
        vf = f"ass='{ass}':fontsdir='{fonts}',select='{sel}'"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                        f"color=c=black:s=1920x1080:d={dur:.2f}:r=4", "-vf", vf, "-fps_mode", "passthrough",
                        str(Path(td) / "f%03d.png")], check=True)
        got = sorted(Path(td).glob("f*.png"))
        if len(got) != len(lines):
            return ("G6 render", False, f"expected {len(lines)} frames, ffmpeg gave {len(got)}")
        for ln, p in zip(lines, got):
            im = Image.open(p).convert("L").crop((0, 700, 1920, 1000))
            if sum(im.histogram()[201:]) < 2000:
                empty.append(ln.idx)
    return ("G6 render", not empty, f"lines with almost no ink at mid-line: {empty}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="hx-kfx check")
    ap.add_argument("project", type=Path)
    ap.add_argument("--ass", default="out.kfx.ass")
    ap.add_argument("--direction", default="direction.kfx.json")
    ap.add_argument("--render", action="store_true")
    ap.add_argument("--fonts", type=Path)
    a = ap.parse_args(argv)
    try:
        res = gates(a.project, a.project / a.ass, a.project / a.direction)
        if a.render:
            if not a.fonts:
                print("--render needs --fonts", file=sys.stderr)
                return 2
            res.append(render_gate(a.project / a.ass, a.project, a.fonts))
    except dirmod.DirectionError as e:
        print(e, file=sys.stderr)
        return 2
    for name, ok, msg in res:
        print(f"{'PASS' if ok else 'FAIL'}  {name}: {msg}")
    return 0 if all(ok for _, ok, _ in res) else 1


if __name__ == "__main__":
    raise SystemExit(main())
