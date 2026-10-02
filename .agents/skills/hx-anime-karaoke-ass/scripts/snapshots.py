# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pillow",
# ]
# ///
"""
抽帧目检：在指定时间点用 libass 渲染“视频+字幕”，拼成网格图。可叠加 band 边框（--bands）检查特效范围。

用法:
  hx-karaoke snapshots.py --video base.mp4 --ass subs.ass --fontsdir fonts --times 26.5,30.2,51.3 --out sheet.jpg
        [--cols 2 --width 960 --bands --crop-bottom 0.45 --ffmpeg ffmpeg]
  --times 也可写成 auto:<ass>  → 对每个 band 取“第一个音拍后 0.3s”和“中点”
提示: 目检重点——注音贴字(4~6px)、中文不压画面主体、特效是否贴合画面、亮场可读性、切换时是否打架
"""
import argparse, os, re, subprocess, sys, tempfile
from PIL import Image, ImageDraw


def bands_of(ass):
    out = []
    for line in open(ass, encoding="utf-8-sig"):
        m = re.match(r";\s*assfx-band:\s*(\S+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)", line)
        if m:
            out.append((m.group(1),) + tuple(float(v) for v in m.groups()[1:]))
    return out


def with_bands(ass, tmpdir):
    """复制一份 ASS，追加 band 边框事件（红色细线）"""
    src = open(ass, encoding="utf-8-sig").read()
    evs = []
    for n, x0, y0, x1, y1, t0, t1 in bands_of(ass):
        w, h = x1 - x0, y1 - y0
        d = f"m 0 0 l {w} 0 l {w} {h} l 0 {h} l 0 0 m 2 2 l 2 {h-2} l {w-2} {h-2} l {w-2} 2 l 2 2"
        def ts(t):
            cs = int(round(max(0, t) * 100)); h_, cs = divmod(cs, 360000); m_, cs = divmod(cs, 6000); s_, cs = divmod(cs, 100)
            return f"{h_}:{m_:02d}:{s_:02d}.{cs:02d}"
        evs.append(f"Dialogue: 99,{ts(t0)},{ts(t1)},FX,dbg,0,0,0,,{{\\an7\\pos({x0},{y0})\\bord0\\shad0\\1c&H3030FF&\\1a&H40&\\p1}}{d}{{\\p0}}")
        evs.append(f"Dialogue: 99,{ts(t0)},{ts(t1)},FX,dbg,0,0,0,,{{\\an7\\pos({x0+4},{y0+2})\\fs18\\bord1\\1c&H3030FF&}}{n}")
    p = os.path.join(tmpdir, "dbg.ass")
    open(p, "w", encoding="utf-8").write(src.rstrip("\n") + "\n" + "\n".join(evs) + "\n")
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True); ap.add_argument("--ass", required=True); ap.add_argument("--fontsdir", required=True)
    ap.add_argument("--times", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--cols", type=int, default=2); ap.add_argument("--width", type=int, default=960)
    ap.add_argument("--bands", action="store_true"); ap.add_argument("--crop-bottom", type=float, default=0.0,
                    help="只保留画面下方这一比例（如 0.45），便于看清字幕区")
    ap.add_argument("--ffmpeg", default="ffmpeg")
    a = ap.parse_args()
    tmp = tempfile.mkdtemp()
    ass = with_bands(a.ass, tmp) if a.bands else a.ass
    if a.times.startswith("auto"):
        ts_ = []
        for n, x0, y0, x1, y1, t0, t1 in bands_of(a.ass):
            ts_ += [round(t0 + 0.9, 2), round((t0 + t1) / 2, 2)]
    else:
        ts_ = [float(t) for t in a.times.split(",")]
    tiles = []
    for i, t in enumerate(ts_):
        png = os.path.join(tmp, f"f{i}.png")
        esc = ass.replace(":", "\\:").replace("'", "\\'")
        subprocess.run([a.ffmpeg, "-v", "error", "-y", "-ss", str(max(0, t - 2)), "-copyts", "-i", a.video, "-ss", str(t),
                        "-vf", f"subtitles='{esc}':fontsdir={a.fontsdir}", "-frames:v", "1", png], check=True)
        im = Image.open(png).convert("RGB")
        if a.crop_bottom:
            im = im.crop((0, int(im.height * (1 - a.crop_bottom)), im.width, im.height))
        im = im.resize((a.width, int(im.height * a.width / im.width)))
        ImageDraw.Draw(im).text((8, 6), f"{t:.2f}s", fill=(255, 80, 80))
        tiles.append(im)
    w, h = tiles[0].size; rows = (len(tiles) + a.cols - 1) // a.cols
    sheet = Image.new("RGB", (w * a.cols, h * rows))
    for i, im in enumerate(tiles):
        sheet.paste(im, ((i % a.cols) * w, (i // a.cols) * h))
    sheet.save(a.out, quality=90)
    print("saved", a.out, len(tiles), "frames")


if __name__ == "__main__":
    main()
