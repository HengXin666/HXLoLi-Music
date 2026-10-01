#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pillow",
# ]
# ///
"""检查特效到底看不看得见 —— 补 validate_ass.py 管不到的那半边。

validate_ass 只判「有没有越界」，不判「有没有画出来」。实测踩过：某工程校验全过、
clamp 只有 10 次，但 FX 层单独渲染整帧只有 35 个亮像素 —— 特效尺寸是同款示例的 1/10、
a_peak 中位 110，等于没画。这个文件就是把这个失败模式变成可失败的命令。

做法：把 Name 为 fx:* 的事件单独抽成一份 ass，纯黑底渲染若干句，数亮像素。
同时列出图形尺寸与 a_peak 的分布，跟示例工程的量级对照。

用法:
  uv run check_fx_visible.py proj/out.ass --fontsdir fonts --times 61,181,232
  uv run check_fx_visible.py proj/out.ass --fontsdir fonts --auto   # 自动挑 FX 最密的几句
"""
import argparse, os, re, subprocess, sys, tempfile
from PIL import Image

MIN_LIT = 2000   # 整帧亮像素低于此值判定「特效太淡」


def split_fx(ass, out_path):
    """只保留 fx:* 事件，其余事件丢掉。"""
    head, fx = [], []
    for l in open(ass, encoding="utf-8-sig").read().splitlines():
        if l.startswith("Dialogue:"):
            p = l[len("Dialogue:"):].split(",", 9)
            if len(p) >= 10 and p[4].startswith("fx:"):
                fx.append(l)
        else:
            head.append(l)
    open(out_path, "w", encoding="utf-8").write("\n".join(head + fx) + "\n")
    return len(fx)


def fx_times(ass, top=4):
    """挑 FX 事件最密的时间点。"""
    from collections import Counter
    c = Counter()
    for l in open(ass, encoding="utf-8-sig").read().splitlines():
        if not l.startswith("Dialogue:"):
            continue
        p = l[len("Dialogue:"):].split(",", 9)
        if len(p) < 10 or not p[4].startswith("fx:"):
            continue
        h, m, rest = p[1].split(":")
        t = int(h) * 3600 + int(m) * 60 + float(rest)
        c[int(t)] += 1
    return [t + 0.5 for t, _ in c.most_common(top)]


def stats(ass):
    """列出图形尺寸与 a_peak 量级，便于跟示例对照。"""
    peaks, lens = [], []
    for l in open(ass, encoding="utf-8-sig").read().splitlines():
        if not l.startswith("Dialogue:"):
            continue
        p = l[len("Dialogue:"):].split(",", 9)
        if len(p) < 10 or not p[4].startswith("fx:"):
            continue
        t = p[9]
        peaks += [int(x, 16) for x in re.findall(r"alpha&H([0-9A-Fa-f]{2})&", t)]
        lens.append(len(t))
    a = [255 - v for v in peaks if v <= 255]   # alpha 是反的: FF=全透明
    return dict(n_fx=len(lens), a_peak_max=max(a) if a else 0,
                a_peak_med=sorted(a)[len(a) // 2] if a else 0,
                path_med=sorted(lens)[len(lens) // 2] if lens else 0)


def render_lit(fx_ass, t, fontsdir, tmp):
    o = os.path.join(tmp, "f%d.png" % int(t * 100))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
                    "-i", "color=0x000000:s=1920x1080:d=%.1f:r=24" % (t + 3),
                    "-vf", "subtitles=%s:fontsdir=%s" % (fx_ass.replace(":", "\\:"), fontsdir),
                    "-ss", str(t), "-frames:v", "1", "-update", "1", o], check=True)
    im = Image.open(o).convert("RGB"); px = im.load(); W, H = im.size
    n = 0; xs = []; ys = []
    for y in range(0, H, 2):
        for x in range(0, W, 2):
            if sum(px[x, y]) > 30:
                n += 1; xs.append(x); ys.append(y)
    box = "x %d-%d y %d-%d" % (min(xs), max(xs), min(ys), max(ys)) if xs else "-"
    return n, box


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ass")
    ap.add_argument("--fontsdir", required=True)
    ap.add_argument("--times", help="逗号分隔的秒数")
    ap.add_argument("--auto", action="store_true", help="自动挑 FX 最密的时间点")
    ap.add_argument("--min-lit", type=int, default=MIN_LIT)
    a = ap.parse_args()

    tmp = tempfile.mkdtemp()
    fx_ass = os.path.join(tmp, "fx.ass")
    n = split_fx(a.ass, fx_ass)
    if n == 0:
        print("没有任何 fx:* 事件 —— 这份 ass 没有特效");
        return 1

    st = stats(a.ass)
    print("FX 事件 %d 条 | a_peak 中位 %d 最大 %d | 路径长度中位 %d"
          % (st["n_fx"], st["a_peak_med"], st["a_peak_max"], st["path_med"]))
    print("   对照量级: a_peak 150~210, 路径 200~1800")

    ts = [float(x) for x in a.times.split(",")] if a.times else fx_times(a.ass)
    bad = 0
    print("");
    print("%8s  %10s  %s" % ("时刻", "亮像素", "范围"))
    for t in ts:
        n_lit, box = render_lit(fx_ass, t, a.fontsdir, tmp)
        flag = "OK" if n_lit >= a.min_lit else "太淡"
        if n_lit < a.min_lit:
            bad += 1
        print("%8.1fs  %10d  %-24s %s" % (t, n_lit, box, flag))

    if bad:
        print("");
        print("%d/%d 个时刻的特效太淡（< %d 亮像素）。" % (bad, len(ts), a.min_lit))
        print("加大图形尺寸或提高 a_peak，别把 band 当成目标尺寸。")
        return 1
    print("");
    print("特效可见性 OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())