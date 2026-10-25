#!/usr/bin/env python3
"""由画面亮度反解暗底需要多不透明  把可读性从审美判断变成一次除法。

推导:
  目标 CR >= 4.5。白字亮度 L_w ~ 1.0, 故 CR = 1.05/(L_b+0.05)
  => 背景允许亮度上限 L_b <= 0.183
  叠加纯黑暗底不透明度 a 后, L_b = L_m*(1-a)
  => a >= 1 - 0.183/L_m

用法:
  python3 backdrop_alpha.py 0.468                 # 给定带亮度
  python3 backdrop_alpha.py --video MV.mp4        # 直接从视频逐段测
"""
import argparse
import os
import subprocess
import sys

import numpy as np
from PIL import Image

LMAX = 0.183  # CR 4.5 允许的背景亮度上限


def rel_lum(rgb):
    c = np.asarray(rgb, dtype=np.float64) / 255.0
    c = np.where(c <= 0.03928, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * c[..., 0] + 0.7152 * c[..., 1] + 0.0722 * c[..., 2]


def need(Lm):
    if Lm <= LMAX:
        return 0.0, 1.05 / (Lm + 0.05)
    a = 1.0 - LMAX / Lm
    return a, 1.05 / (Lm * (1 - a) + 0.05)


def hexa(a):
    return '\\1a&H%02X&' % int(round((1 - a) * 255))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('lum', nargs='?', type=float, help='该带画面亮度中位 (0-1)')
    ap.add_argument('--video')
    ap.add_argument('--band', type=int, default=137, help='字幕带高(原始像素)')
    ap.add_argument('--y', type=int, default=900, help='带中心 y (1080 系)')
    ap.add_argument('--step', type=int, default=5, help='采样间隔秒')
    a = ap.parse_args()

    if a.lum is not None:
        n, cr = need(a.lum)
        print('带亮度 %.3f -> 原 CR %.2f' % (a.lum, 1.05 / (a.lum + 0.05)))
        print('需要暗底 alpha >= %.2f  即 %s' % (n, hexa(n) if n > 0 else '不需要暗底'))
        return 0

    if not a.video:
        ap.print_help()
        return 2

    tmp = '/tmp/backdrop-alpha'
    os.makedirs(tmp, exist_ok=True)
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries',
                        'format=duration', '-of', 'csv=p=0', a.video],
                       capture_output=True, text=True)
    try:
        dur = float(r.stdout.strip())
    except ValueError:
        print('取不到时长'); return 2

    print(os.path.basename(a.video))
    print('带: y=%d 高 %d (1080 系)' % (a.y, a.band))
    print()
    print('%-8s %-10s %-8s %-12s %s' % ('t(s)', '带亮度', '原CR', '需要alpha', 'ASS'))
    for t in range(0, int(dur), a.step):
        p = os.path.join(tmp, 'b_%05d.png' % t)
        if not os.path.exists(p):
            subprocess.run(['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
                            '-copyts', '-ss', str(t), '-i', a.video,
                            '-frames:v', '1', p], capture_output=True)
        if not os.path.exists(p):
            continue
        img = Image.open(p).convert('RGB')
        W, H = img.size
        sw = 960; sh = int(H * sw / W)
        Y = rel_lum(np.asarray(img.resize((sw, sh), Image.LANCZOS)).astype(np.float32))
        y0 = max(0, int((a.y - a.band / 2) * sh / 1080))
        y1 = min(sh, int((a.y + a.band / 2) * sh / 1080))
        bl = Y[y0:y1]
        if bl.size == 0:
            continue
        Lm = float(np.median(bl))
        n, cr = need(Lm)
        flag = hexa(n) if n > 0 else '不需要'
        print('%-8d %-10.3f %-8.2f %-12.2f %s' % (t, Lm, 1.05 / (Lm + 0.05), n, flag))
    return 0


if __name__ == '__main__':
    sys.exit(main())