#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow", "numpy"]
# ///
"""镜头时间线: 从 MV 抽帧算主色与亮暗, 供背景层与色彩系统驱动.

## 为什么需要它

`45-bg` 要求背景层由**镜头 / 情感 / 番剧符号**三者驱动, 但此前只有情感(手写的段落表),
镜头那一维是空的 —— 实测 v5 的背景层只有"每 0.6s 一颗颗粒", 色温不跟画面走.

这个脚本把"这一秒画面是什么颜色、是亮是暗"变成机器可读的表,
于是背景层可以**真的读画面**, 而不是靠人肉看抽帧.

## 输出

`review/scene-timeline.json`:
    shots: [{t0, t1, hue, sat, val, rgb, is_dark, cut}]      镜头段(按画面突变切)
    per_sec: {秒: [hue, sat, val]}                            逐秒采样(背景层直接查)

`cut=True` 表示这一段与前一段之间有明显画面切换(用于"特效对齐镜头切换").

## 两张用法

    from scene_timeline import SceneTimeline
    ST = SceneTimeline.load("proj/review/scene-timeline.json")
    hue, sat, val = ST.at(197.0)          # 该秒画面主色(HSV, h 0~360)
    for t in ST.cuts(60, 120):            # 这一段的镜头切换点
        ...

## 判据 (可机械验)

  * 亮度: `val` 是 HSV 的 V, 直接决定背景层该压暗还是提亮 (亮场必须压暗, 否则字看不清)
  * 色温: `hue` 与段落表的色族要**同向**. 实测某句画面是橙红而背景层用青蓝 = 没读画面.
    比对法: 取该句覆盖镜头的 hue 均值, 与背景层事件的 `\\1c` hue 均值做符号比对.
"""
import argparse, json, os, subprocess, sys

import numpy as np


def grab(video, t):
    """抽一帧 -> RGB ndarray (小尺寸, 只要颜色不要细节)"""
    from PIL import Image
    import io
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", video,
                        "-frames:v", "1", "-vf", "scale=160:-1", "-f", "image2pipe",
                        "-vcodec", "png", "-"], capture_output=True)
    if r.returncode != 0 or not r.stdout:
        return None
    return np.asarray(Image.open(io.BytesIO(r.stdout)).convert("RGB")).astype(np.float32) / 255.0


def rgb_to_hsv(rgb):
    """rgb: HxWx3 (0~1) -> (h 0~360, s, v) 的均值, 用画面中位色而非纯均值(避免被大片黑吃掉)"""
    import colorsys
    px = rgb.reshape(-1, 3)
    # 取中位色: 对番剧画面比均值稳(均值会被字幕/黑边拉偏)
    med = np.median(px, axis=0)
    h, s, v = colorsys.rgb_to_hsv(float(med[0]), float(med[1]), float(med[2]))
    # 另算一个"有内容区域"的均值: 剔掉最暗的 40%(黑边/暗底)
    lum = px.mean(axis=1)
    thr = np.percentile(lum, 60)
    sel = px[lum >= thr]
    if len(sel) > 50:
        m2 = sel.mean(axis=0)
        h2, s2, v2 = colorsys.rgb_to_hsv(float(m2[0]), float(m2[1]), float(m2[2]))
    else:
        h2, s2, v2 = h, s, v
    return round(h * 360, 1), round(s, 3), round(v, 3), [int(x * 255) for x in med]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--step", type=float, default=1.0, help="采样间隔秒; 默认 1.0")
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--dur", type=float, default=0.0, help="0 = 整片")
    ap.add_argument("--cut-thresh", type=float, default=0.28,
                    help="相邻采样的 HSV 距离超过它算一次镜头切换")
    a = ap.parse_args()

    # 时长
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "csv=p=0", a.video], capture_output=True, text=True)
    dur = a.dur or float((probe.stdout or "0").strip() or 0)
    if dur <= 0:
        raise SystemExit("拿不到视频时长: %s" % a.video)
    t0, t1 = a.start, min(dur, a.start + dur if a.dur else dur)
    print(f"扫描 {t0:.1f}~{t1:.1f}s, 步长 {a.step}s")

    per_sec, samples = {}, []
    t = t0
    n = 0
    while t < t1:
        rgb = grab(a.video, t)
        if rgb is not None:
            h, s, v, med = rgb_to_hsv(rgb)
            per_sec[round(t, 2)] = [h, s, v]
            samples.append((t, h, s, v, med))
            n += 1
        t += a.step
    if not samples:
        raise SystemExit("一帧都没抽到")
    print(f"采到 {n} 帧")

    def dist(x, y):
        dh = min(abs(x[1] - y[1]), 360 - abs(x[1] - y[1])) / 180.0
        return (dh * 2 + abs(x[2] - y[2]) + abs(x[3] - y[3])) / 4

    shots, cur = [], [samples[0]]
    for prev, cur_s in zip(samples, samples[1:]):
        if dist(prev, cur_s) > a.cut_thresh:
            shots.append((cur[0][0], cur[-1][0] + a.step, cur))
            cur = [cur_s]
        else:
            cur.append(cur_s)
    shots.append((cur[0][0], cur[-1][0] + a.step, cur))

    out_shots = []
    for i, (s0, s1, grp) in enumerate(shots):
        hs = [g[1] for g in grp]; ss = [g[2] for g in grp]; vs = [g[3] for g in grp]
        med = grp[len(grp) // 2][4]
        out_shots.append(dict(t0=round(s0, 2), t1=round(s1, 2),
                              hue=round(float(np.median(hs)), 1),
                              sat=round(float(np.median(ss)), 3),
                              val=round(float(np.median(vs)), 3),
                              rgb=med, is_dark=float(np.median(vs)) < 0.30))
    print(f"切成 {len(out_shots)} 个镜头段")
    dark = sum(1 for s in out_shots if s["is_dark"])
    print(f"  其中暗场 {dark} 段 ({dark/len(out_shots):.0%});"
          f" 亮场(背景层须压暗) {sum(1 for s in out_shots if s['val'] > 0.62)} 段")

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump(dict(source=os.path.abspath(a.video), step=a.step,
                   shots=out_shots, per_sec=per_sec),
              open(a.out, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"-> {a.out} ({os.path.getsize(a.out)/1024:.1f} KB)")
    print("用法: 背景层按 shots 取色温与明暗; 特效对齐 shots 的 t0(镜头切换)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
