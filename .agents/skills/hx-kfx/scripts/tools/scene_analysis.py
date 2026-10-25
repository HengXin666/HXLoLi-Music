#!/usr/bin/env python3
"""画面驱动: 从 MV 帧/封面求「该压多暗」「用什么色」「哪里最静」的机械判据。

用法:
    python3 scene_analysis.py <图片...> [--playres 1920,1080] [--target-cr 12]

三块输出全部来自像素统计, 不是审美判断:
  1. 白字可读性: 直接叠白字有多少区域达不到目标对比度, 压暗到多少才可行;
  2. 主色板: k-means 聚类, 标出每簇对白字的对比度  用来挑描边色与局部暗底色;
  3. 安静带: 逐横条带的边缘密度, 给出候选安全区的纵向位置.

亮度必须按 sRGB 反 gamma 后再线性加权; 直接对 0-255 求加权平均会得到全 0.
"""
from __future__ import annotations
import argparse
import sys

import numpy as np
from PIL import Image, ImageFilter


def rel_lum(rgb) -> np.ndarray:
    """sRGB -> WCAG 相对亮度。输入 0-255 或 0-1 均可。"""
    c = np.asarray(rgb, dtype=np.float64)
    if c.max() > 1.5:
        c = c / 255.0
    c = np.where(c <= 0.03928, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * c[..., 0] + 0.7152 * c[..., 1] + 0.0722 * c[..., 2]


def contrast(a, b) -> float:
    la, lb = float(rel_lum(np.asarray(a))), float(rel_lum(np.asarray(b)))
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def kmeans(X: np.ndarray, k: int, seed: int = 7, iters: int = 30):
    rng = np.random.RandomState(seed)
    C = X[rng.choice(len(X), k, replace=False)].astype(np.float64).copy()
    lab = np.zeros(len(X), dtype=int)
    for _ in range(iters):
        d = ((X[:, None, :] - C[None, :, :]) ** 2).sum(-1)
        lab = d.argmin(1)
        for i in range(k):
            m = lab == i
            if m.sum():
                C[i] = X[m].mean(0)
    return C, np.bincount(lab, minlength=k)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("images", nargs="+")
    ap.add_argument("--playres", default="1920,1080")
    ap.add_argument("--target-cr", type=float, default=12.0)
    ap.add_argument("--band", type=int, default=60)
    ap.add_argument("--clusters", type=int, default=12)
    a = ap.parse_args()

    W, H = (int(v) for v in a.playres.split(","))
    for p in a.images:
        img = Image.open(p).convert("RGB").resize((W, H), Image.LANCZOS)
        arr = np.asarray(img).astype(np.float32)
        Y = rel_lum(arr)
        print(f"\n=== {p}  ({W}x{H}) ===")
        print(f"亮度 中位 {np.median(Y):.3f}  p90 {np.percentile(Y,90):.3f}  "
              f"暗(<0.10) {(Y<0.10).mean()*100:.1f}%  亮(>0.60) {(Y>0.60).mean()*100:.1f}%")

        need = 1.05 / a.target_cr - 0.05
        print(f"白字达 {a.target_cr:.0f}:1 需底板亮度 <= {need:.4f}; "
              f"当前仅 {(Y<=need).mean()*100:.1f}% 区域满足")
        for k in (0.5, 0.4, 0.3, 0.25, 0.2):
            print(f"  压暗到 {k*100:.0f}%: 不达标区域 {(Y*k>need).mean()*100:.1f}%")

        flat = arr.reshape(-1, 3)
        idx = np.random.RandomState(1).choice(len(flat), min(60000, len(flat)), replace=False)
        C, cnt = kmeans(flat[idx].astype(np.float64), a.clusters)
        print("--- 主色 (对白字对比度; CR>=4.5 的可作描边) ---")
        for i in np.argsort(-cnt):
            c = C[i].astype(int)
            cr = contrast(c, (255, 255, 255))
            tag = "  <= 可作描边/暗底" if cr >= 4.5 else ""
            print(f"  #{c[0]:02X}{c[1]:02X}{c[2]:02X}  RGB({c[0]:3d},{c[1]:3d},{c[2]:3d})  "
                  f"{cnt[i]/cnt.sum()*100:5.1f}%  亮度 {float(rel_lum(c)):.3f}  对白 CR {cr:5.2f}{tag}")

        g = np.asarray(Image.open(p).convert("L").resize((W, H), Image.LANCZOS)).astype(np.uint8)
        edges = np.asarray(Image.fromarray(g).filter(ImageFilter.FIND_EDGES)).astype(np.float32)
        rows = []
        for y in range(0, H - a.band + 1, a.band):
            bl = Y[y:y + a.band]
            rows.append((y, float(edges[y:y + a.band].mean()), float(bl.mean()),
                         float(1.05 / (np.percentile(bl, 92) + 0.05))))
        med_e = float(np.median([r[1] for r in rows]))
        print(f"--- 逐 {a.band}px 横条带 (边缘密度中位 {med_e:.1f}); 低密度 = 画面安静 ---")
        for y, e, lum, crw in rows:
            mark = "  <安静" if e < med_e else ""
            print(f"  y={y:4d} edge={e:5.1f} lum={lum:.3f} 白字最坏CR={crw:5.2f}{mark}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
