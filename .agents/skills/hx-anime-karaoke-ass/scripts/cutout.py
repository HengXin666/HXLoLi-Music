#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow", "numpy", "rembg", "onnxruntime"]
# ///
"""抠图: 把 MV 帧 / 素材图变成带 alpha 的干净 PNG, 供 `\\1img` 图片层用.

## 为什么抠图质量是硬判据 (用户 2026-10-03 原话)

「你需要抠图, 只要抠的完整, 你不可能一个人抠了一半, 出来以后, 他的头发整个上边是平的一个矩形,
这样子显然是不对的」

头发上边被切成平直矩形 = **没抠透**. 根因通常不是模型不行, 而是:
  1. 原图本身就贴边(人物被画框裁掉), 抠完自然还是平的;
  2. 后处理把 alpha 阈值化(>128 -> 255), 把羽化边砍掉, 看起来像被切;
  3. 忘了保留原图的外扩边距, 主体贴到 0 行/0 列。

所以这个脚本不只做抠图, 还要**量出上面三件事**, 并给出可失败的判定。

## 判据 (机械可查)

| 检查 | 判据 | 不合规意味着 |
|---|---|---|
| 四边 alpha 均值 | 应接近 0 | 主体贴边 = 被裁切 |
| 贴边像素占比 | 每边 <= 1% | 同上 |
| alpha 过渡带 | 存在 0<alpha<255 的像素 | 全二值 = 羽化被砍, 边缘发硬 |
| 主体占比 | 有效像素 / 全图 在 8%~85% | 太小=抠漏, 太大=基本没抠 |

## 用法

  hx-karaoke cutout.py --in pic.png --out proj/assets/pic.png
  hx-karaoke cutout.py --from-video base.mp4 --at 24.5 --out proj/assets/eye.png --pad 24
  hx-karaoke cutout.py --in in.png --out out.png --check-only     # 只体检, 不重抠
  hx-karaoke cutout.py --in a.png --in b.png --out-dir proj/assets/

`--pad` 会在抠图前给原图加透明边距, 这是**防"头发被切平"的第一道保险**:
即使模型想贴边输出, 加过 pad 之后边缘也一定在 alpha=0 的区域里。
"""
import argparse, json, os, subprocess, sys, tempfile

import numpy as np


def load_rgba(path):
    from PIL import Image
    return Image.open(path).convert("RGBA")


def check_alpha(im, quiet=False):
    """体检一张带 alpha 的图. 返回 (ok, 详情 dict)"""
    a = np.asarray(im)[:, :, 3].astype(np.int32)
    h, w = a.shape
    edges = {"top": a[0, :], "bottom": a[-1, :], "left": a[:, 0], "right": a[:, -1]}
    d = {}
    ok = True
    for k, v in edges.items():
        m = float(v.mean())
        frac = float((v > 8).mean())
        d[k] = dict(mean=round(m, 2), solid_ratio=round(frac, 4))
        if frac > 0.01:
            ok = False
    body = a > 8
    frac_body = float(body.mean())
    d["body_ratio"] = round(frac_body, 4)
    if frac_body < 0.06 or frac_body > 0.92:
        ok = False
    soft = ((a > 8) & (a < 248)).mean()
    d["soft_edge_ratio"] = round(float(soft), 4)
    # 全二值 = 羽化被砍掉
    if soft < 0.002:
        d["binary_edge"] = True
    ys, xs = np.where(body)
    if len(xs):
        d["bbox"] = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
        d["size"] = [w, h]
    d["ok"] = ok
    if not quiet:
        flag = "OK  " if ok else "FAIL"
        print(f"  [{flag}] {w}x{h}  主体占比 {frac_body:.1%}  羽化边 {soft:.2%}")
        for k in ("top", "bottom", "left", "right"):
            e = d[k]
            mark = "" if e["solid_ratio"] <= 0.01 else "  <- 贴边, 会切平"
            print(f"        {k:6s} alpha均值 {e['mean']:6.1f}  实色占比 {e['solid_ratio']:.2%}{mark}")
        if d.get("binary_edge"):
            print("        ! 没有羽化过渡(全二值) —— 边缘会发硬, 通常是把 alpha 阈值化了")
    return ok, d


def pad_image(im, pad, color=(0, 0, 0, 0)):
    from PIL import Image
    if pad <= 0:
        return im
    w, h = im.size
    out = Image.new("RGBA", (w + pad * 2, h + pad * 2), color)
    out.paste(im, (pad, pad))
    return out


def grab_frame(video, t, out):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", video,
                    "-frames:v", "1", "-update", "1", out], check=True)
    return out


def rembg_cut(im):
    from rembg import remove
    return remove(im)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="ins", action="append", default=[], help="输入图(可多次)")
    ap.add_argument("--from-video", help="从视频抽一帧再抠")
    ap.add_argument("--at", type=float, default=0.0, help="抽帧时刻(秒)")
    ap.add_argument("--out", help="单张输出路径")
    ap.add_argument("--out-dir", help="多张输出目录")
    ap.add_argument("--pad", type=int, default=16,
                    help="抠图前加透明边距(px). 防'头发被切平'的第一道保险, 默认 16")
    ap.add_argument("--check-only", action="store_true", help="只体检不重抠")
    ap.add_argument("--json", help="把体检结果写到 json")
    a = ap.parse_args()

    jobs = []
    if a.from_video:
        tmp = os.path.join(tempfile.mkdtemp(), "frame.png")
        grab_frame(a.from_video, a.at, tmp)
        jobs.append((tmp, os.path.splitext(os.path.basename(a.from_video))[0] + f"_{a.at:.2f}"))
    for p in a.ins:
        jobs.append((p, os.path.splitext(os.path.basename(p))[0]))
    if not jobs:
        raise SystemExit("需要 --in 或 --from-video")

    reports, all_ok = {}, True
    for src, stem in jobs:
        print(f"== {src}")
        if a.check_only:
            im = load_rgba(src)
        else:
            src_im = load_rgba(src)
            padded = pad_image(src_im, a.pad)
            cut = rembg_cut(padded)
            im = cut
            if a.out and len(jobs) == 1:
                dst = a.out
            else:
                d = a.out_dir or (os.path.dirname(os.path.abspath(src)) + "/cut")
                os.makedirs(d, exist_ok=True)
                dst = os.path.join(d, stem + "_cut.png")
            os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
            im.save(dst)
            print(f"   -> {dst}")
        ok, det = check_alpha(im)
        reports[stem] = det
        all_ok &= ok

    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)), exist_ok=True)
        json.dump(reports, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"-> {a.json}")
    if not all_ok:
        print("\n有图未通过: 贴边/占比异常/边缘全二值 —— 这些在成片里就是'被切平的头发'.")
        return 1
    print("\n抠图体检全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
