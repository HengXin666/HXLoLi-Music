#!/usr/bin/env python3
"""对真实 MV 逐帧求"白字最可读的水平带"  决定特效该放哪里。

为什么必须这么做:
  实测同一首歌的画面亮度可以从 0.002 (纯黑) 到 0.982 (纯白),
  封面只覆盖其中一个瞬间。固定安全区在全片范围内不成立。

做法: 把画面按 band 像素切成横带, 对每帧求出"白字最坏情况对比度最高"的
连续 2 条带, 并判定该帧是否存在可读位置。

用法: python3 mv_bands.py <视频> [--step 4] [--band 60]
输出: 逐帧最佳带 + 汇总 (有多少帧根本没有可读位置)
"""
import argparse
import os
import subprocess
import sys

import numpy as np
from PIL import Image


# Agent Notes: MV 素材只作本地测量用, 不进仓库
# 
def rel_lum(c):
    """Agent Notes
    .agents/notes/implemented/process/2026-09-29-mv-source-not-in-git.md
    """
    c = np.asarray(c, dtype=np.float64)
    if c.max() > 1.5:
        c = c / 255.0
    c = np.where(c <= 0.03928, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * c[..., 0] + 0.7152 * c[..., 1] + 0.0722 * c[..., 2]


def cr_white(lum: float) -> float:
    """
    .agents/notes/implemented/architecture/2026-09-29-kfx-mv-driven-safe-area.md
白字在某亮度上的对比度。

    位置必须按真实画面逐帧测, 不能用封面替代  见
    
    (实测同一首歌画面亮度可从 0.002 到 0.982, 15/23 帧不存在可读位置)。
    """
    return 1.05 / (float(lum) + 0.05)



def grab(video: str, t: float, out: str) -> bool:
    r = subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-ss", str(t), "-i", video, "-frames:v", "1", out],
        capture_output=True)
    return r.returncode == 0 and os.path.exists(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--step", type=int, default=4, help="采样间隔秒")
    ap.add_argument("--band", type=int, default=60, help="横带高度(原始像素)")
    ap.add_argument("--out", default="/tmp/mv-bands")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    # 时长
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration", "-of", "csv=p=0", a.video],
                       capture_output=True, text=True)
    try:
        dur = float(r.stdout.strip())
    except ValueError:
        print("取不到时长"); return 2

    times = [t for t in range(2, int(dur), a.step)]
    print("%s  时长 %.0fs, 采样 %d 帧" % (os.path.basename(a.video), dur, len(times)))
    print("%-6s %-22s %-10s %s" % ("t(s)", "最佳带 y0..y1", "白字最坏CR", "判定"))

    rows = []
    for t in times:
        p = os.path.join(a.out, "b_%04d.png" % t)
        if not os.path.exists(p) and not grab(a.video, t, p):
            continue
        img = Image.open(p).convert("RGB")
        W, H = img.size
        # 缩到 960 宽以便计算, 带高按比例
        sw = 960
        sh = int(H * sw / W)
        Y = rel_lum(np.asarray(img.resize((sw, sh), Image.LANCZOS)).astype(np.float32))
        b = max(1, int(a.band * sh / H))
        bands = []
        for y in range(0, sh - b + 1, b):
            bl = Y[y:y + b]
            # 最亮 5% 决定白字的最坏情况
            bands.append((y, cr_white(np.percentile(bl, 95))))
        best = None
        for i in range(len(bands) - 1):
            worst = min(bands[i][1], bands[i + 1][1])
            if best is None or worst > best[0]:
                best = (worst, bands[i][0], bands[i + 1][0] + b)
        if best is None:
            continue
        y0, y1 = int(best[1] * H / sh), int(best[2] * H / sh)
        ok = "可放白字" if best[0] >= 4.5 else ("勉强" if best[0] >= 3 else "不可放")
        print("%-6d y=%-5d..%-5d      %-10.2f %s" % (t, y0, y1, best[0], ok))
        rows.append((t, y0, y1, best[0]))

    if not rows:
        print("没有可用帧"); return 1
    oks = [r for r in rows if r[3] >= 4.5]
    print()
    print("=== 汇总 ===")
    print("可放白字的帧: %d / %d" % (len(oks), len(rows)))
    print("最佳带 y0 范围: %d .. %d" % (min(r[1] for r in rows), max(r[1] for r in rows)))
    print("最佳带 y1 范围: %d .. %d" % (min(r[2] for r in rows), max(r[2] for r in rows)))
    print()
    print("判定: " + ("画面本身多处不可读, **必须加局部暗底**" if len(oks) < len(rows) * 0.6
                      else "画面基本可读, 白字+描边即可"))
    return 0


if __name__ == "__main__":
    sys.exit(main())