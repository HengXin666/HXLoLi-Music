#!/usr/bin/env python3
"""逐帧扫描渲染结果的内容包围盒, 检验特效是否落在声明的固定安全区内。

用法:
    python3 measure_bbox.py --frames <帧目录> --safe X0,Y0,X1,Y1 [--bg 11,16,22] [--window 500,350]

退出码 0 = 零越界 (归一化成立); 1 = 越界或没渲染出内容; 2 = 参数错。

为什么用「与背景色的通道差之和」而不是固定灰度阈值: 幽灵态文字与背景的差异很小,
固定灰度阈值会把幽灵态判成空帧, 从而漏掉「整行先出现」这一条的反例。
"""
from __future__ import annotations
import argparse
import glob
import sys

import numpy as np
from PIL import Image


def parse_csv(s: str, n: int, cast=float):
    parts = [p for p in s.replace(" ", "").split(",") if p != ""]
    if len(parts) != n:
        raise ValueError(f"需要 {n} 个数值, 得到 {len(parts)}")
    return tuple(cast(p) for p in parts)


# 「四个方向越界量全为 0」是归一化的唯一判据; 换掉它整套流程就失去回归保护
# (see 同目录 build_normalized.py 的 normalized-safe-area 决策锚点).
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", required=True, help="PNG 帧目录 (按文件名排序)")
    ap.add_argument("--safe", required=True, help="声明的安全区 X0,Y0,X1,Y1")
    ap.add_argument("--bg", default="0,0,0", help="渲染时的背景色 R,G,B")
    ap.add_argument("--window", default="500,350", help="播放器窗口 W,H, 用于算裁剪缩放")
    ap.add_argument("--diff", type=int, default=26, help="与背景的通道差阈值")
    a = ap.parse_args()

    sx0, sy0, sx1, sy1 = parse_csv(a.safe, 4, int)
    bg = np.array(parse_csv(a.bg, 3, int), dtype=np.int16)
    win_w, win_h = parse_csv(a.window, 2, int)

    files = sorted(glob.glob(a.frames.rstrip("/") + "/*.png"))
    if not files:
        print(f"! 帧目录为空: {a.frames}", file=sys.stderr)
        return 2

    boxes, empty = [], 0
    for f in files:
        arr = np.asarray(Image.open(f).convert("RGB")).astype(np.int16)
        mask = np.abs(arr - bg).sum(axis=2) > a.diff
        ys, xs = np.nonzero(mask)
        if len(xs) == 0:
            empty += 1
            continue
        boxes.append((int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())))

    if not boxes:
        print("! 所有帧都是空的: 特效没有渲染出来", file=sys.stderr)
        return 1

    x0 = min(b[0] for b in boxes); y0 = min(b[1] for b in boxes)
    x1 = max(b[2] for b in boxes); y1 = max(b[3] for b in boxes)

    print(f"帧数 {len(files)} (空帧 {empty}, 有内容 {len(boxes)})")
    print(f"内容包围盒并集  x[{x0},{x1}] 宽 {x1-x0}   y[{y0},{y1}] 高 {y1-y0}")
    print(f"声明的安全区    x[{sx0},{sx1}] 宽 {sx1-sx0}   y[{sy0},{sy1}] 高 {sy1-sy0}")

    over = dict(left=max(0, sx0 - x0), top=max(0, sy0 - y0),
                right=max(0, x1 - sx1), bottom=max(0, y1 - sy1))
    ok = all(v == 0 for v in over.values())
    print(f"越界量          {over}")
    print(f"越界检查        {'PASS' if ok else 'FAIL'}")

    ws = np.array([b[2] - b[0] for b in boxes]); hs = np.array([b[3] - b[1] for b in boxes])
    print(f"逐帧框          宽 中位 {np.median(ws):.0f} min {ws.min()} max {ws.max()} std {ws.std():.2f}")
    print(f"                高 中位 {np.median(hs):.0f} min {hs.min()} max {hs.max()} std {hs.std():.2f}")

    sc = np.array([min(win_w / max(b[2] - b[0], 1), win_h / max(b[3] - b[1], 1), 1.0) for b in boxes])
    jump = np.abs(np.diff(sc)) if len(sc) > 1 else np.array([0.0])
    print(f"动态裁剪(对照)  scale {sc.min():.4f}..{sc.max():.4f}  相邻跳变最大 {jump.max():.4f}")
    fixed = min(win_w / max(sx1 - sx0, 1), win_h / max(sy1 - sy0, 1), 1.0)
    print(f"归一化裁剪      scale 恒为 {fixed:.4f}  相邻跳变恒为 0")
    # 归一化不是无条件放大: 它用「恒定」换掉「中位更大但会漂移」。
    # 动态裁剪在中位帧上往往给出比常量更大的 scale, 却在窄帧/宽帧之间来回跳。
    print(f"恒定 vs 中位      {(fixed / np.median(sc) - 1) * 100:+.1f}%  (负值是正常的: "
          f"动态裁剪中位更大但漂移 {sc.max()-sc.min():.4f})")
    print(f"漂移幅度对比      动态 {(sc.max()-sc.min())/np.median(sc)*100:.1f}%  vs  归一化 0.0%")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
