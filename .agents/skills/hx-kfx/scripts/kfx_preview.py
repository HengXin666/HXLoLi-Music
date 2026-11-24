"""Render real frames (libass via ffmpeg) over the MV and tile them into one sheet.

usage: python kfx_preview.py <ass> --video base.mp4 --fonts <dir> --at 27.5 36 53 ... [--sheet out.jpg]
       python kfx_preview.py <ass> --video base.mp4 --fonts <dir> --lines   (one frame mid each line)

Looking at this sheet is the last step of the skill and cannot be skipped: gates prove
bounds and timing, only eyes prove "this looks like the scene".
"""
from __future__ import annotations

import argparse
import re
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw


def _esc(p: Path) -> str:
    return str(p).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def frame(ass: Path, video: Path | None, fonts: Path, t: float, out: Path) -> None:
    src = (["-ss", f"{t:.3f}", "-copyts", "-i", str(video)] if video else
           ["-f", "lavfi", "-i", f"color=c=0x202020:s=1920x1080:d={t + 1:.2f}:r=10", "-ss", f"{t:.3f}"])
    vf = f"ass='{_esc(ass)}':fontsdir='{_esc(fonts)}'"
    cmd = ["ffmpeg", "-v", "error", "-y", *src, "-vf", vf, "-frames:v", "1", str(out)]
    subprocess.run(cmd, check=True)


def line_times(ass: Path) -> list[float]:
    """mid point of each lyric line, read back from the jp-sung events."""
    starts: dict[str, float] = {}
    for ln in ass.read_text(encoding="utf-8-sig").splitlines():
        m = re.match(r"Dialogue: \d+,(\d+):(\d+):([\d.]+),[^,]+,CN,L\d+:zh-sung,", ln)
        if m:
            t = int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])
            starts[f"{t:.2f}"] = t
    ts = sorted(starts.values())
    return [t + 1.2 for t in ts]


def sheet(paths: list[tuple[float, Path]], out: Path, cols: int = 3, w: int = 640) -> None:
    ims = [(t, Image.open(p).convert("RGB").resize((w, w * 9 // 16))) for t, p in paths]
    rows = (len(ims) + cols - 1) // cols
    S = Image.new("RGB", (cols * w, rows * w * 9 // 16), "black")
    d = ImageDraw.Draw(S)
    for i, (t, im) in enumerate(ims):
        x, y = (i % cols) * w, (i // cols) * w * 9 // 16
        S.paste(im, (x, y))
        d.text((x + 6, y + 4), f"{t:.1f}s", fill=(255, 255, 0))
    S.save(out, quality=88)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="hx-kfx preview")
    ap.add_argument("ass", type=Path)
    ap.add_argument("--video", type=Path)
    ap.add_argument("--fonts", type=Path, required=True)
    ap.add_argument("--at", type=float, nargs="*", default=[])
    ap.add_argument("--lines", action="store_true")
    ap.add_argument("--sheet", type=Path, default=Path("preview.jpg"))
    ap.add_argument("--cols", type=int, default=3)
    a = ap.parse_args(argv)
    ts = list(a.at) + (line_times(a.ass) if a.lines else [])
    with tempfile.TemporaryDirectory() as td:
        got = []
        for i, t in enumerate(ts):
            p = Path(td) / f"f{i:03d}.png"
            frame(a.ass, a.video, a.fonts, t, p)
            got.append((t, p))
        sheet(got, a.sheet, a.cols)
    print(f"sheet: {a.sheet} ({len(ts)} frames)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
