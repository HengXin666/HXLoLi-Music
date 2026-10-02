#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow"]
# ///
"""出片: 用**定制版 libass** 逐帧渲染字幕, 叠加到 MV, 编成视频.

## 为什么不能直接用 render.sh

`render.sh` 是**外挂字幕**封装(MKV), 那是字幕组的交付形态, 没问题.
但如果你要一个**烧好字幕的成品视频**(能直接发给别人看的 mp4), 就不能用
`ffmpeg -vf subtitles=`: 本机 ffmpeg 的 libass **不支持 VSFilterMod 标签**,
`\\1img` 会静默退化成纯色块 —— 出来的片子和观众看到的不是一回事.

所以出片必须走定制版渲染器:

    逐帧: SubtitlesOctopus(定制版) -> 透明 PNG
    叠加: ffmpeg overlay 到 MV 同刻帧
    编码: libx264 + aac

## 吞吐 (实测)

约 **1.7 帧/秒**(1920x1080, 含 seek 与 PNG 编解码).
5212 帧(20fps x 260s)的全曲约 **50 分钟**.
`--fps` 默认沿用源视频帧率; 想更快就降到 12 或 10 —— 歌词特效不是高速运动,
12fps 观感与 20fps 差别很小, 时间省 40%.

## 用法

    hx-karaoke render_video.py --ass proj/out.ass --video proj/base.mp4 --out proj/out.mp4
    hx-karaoke render_video.py --ass proj/out.ass --video base.mp4 --out out.mp4 \\
        --start 176 --end 196 --fps 12        # 只出高潮段
    hx-karaoke render_video.py --ass proj/out.ass --video base.mp4 --out out.mp4 --keep-frames

产物默认写 `--out`, 中间帧写 `--tmp`(默认 /home 下的暂存目录, **不写 /tmp** ——
它是 tmpfs, 全曲 PNG 有 4~6GB, 会把它写满).
"""
import argparse, math, os, shutil, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_TMP = os.path.expanduser("~/Storage/hxkv-frames")


def probe(video):
    """用 JSON 输出取参数.

    ⚠ 不要用 `-of csv`: 字段顺序**不是**按你请求的顺序排的 ——
    实测请求 `r_frame_rate,width,height` 得到的是 `1920,1080,20/1`,
    按请求顺序解析会把 `20/1` 当 width 去 int() 而崩(踩过).
    """
    import json as _json
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v",
                        "-show_entries", "stream=r_frame_rate,width,height",
                        "-of", "json", video], capture_output=True, text=True)
    try:
        st = _json.loads(r.stdout)["streams"][0]
    except Exception:
        raise SystemExit("ffprobe 读不到视频信息: %s" % (r.stderr or r.stdout)[:200])
    num, den = (str(st.get("r_frame_rate", "25/1")).split("/") + ["1"])[:2]
    fps = float(num) / float(den or 1)
    return fps, int(st["width"]), int(st["height"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ass", required=True)
    ap.add_argument("--video", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--end", type=float, default=0.0, help="0 = 到片尾")
    ap.add_argument("--fps", type=float, default=0.0, help="0 = 沿用源视频帧率")
    ap.add_argument("--tmp", default=DEFAULT_TMP)
    ap.add_argument("--keep-frames", action="store_true")
    ap.add_argument("--crf", type=int, default=19)
    ap.add_argument("--fontsdir", default=os.path.join(os.path.dirname(HERE), "fonts"))
    ap.add_argument("--audio", action="store_true", default=True,
                    help="保留原视频音轨(默认开)")
    a = ap.parse_args()

    src_fps, W, H = probe(a.video)
    fps = a.fps or src_fps
    t0 = max(0.0, a.start)
    # 片长
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", a.video], capture_output=True, text=True)
    dur = float((r.stdout or "0").strip() or 0)
    t1 = a.end if a.end > 0 else dur
    t1 = min(t1, dur) if dur > 0 else t1
    n = max(1, int(round((t1 - t0) * fps)))
    print(f"源: {W}x{H} @ {src_fps:g}fps, 总长 {dur:.1f}s")
    print(f"出片区间: {t0:.2f} ~ {t1:.2f}s, 输出 {fps:g}fps, 共 {n} 帧")
    print(f"预计渲染时间: {n/1.7/60:.1f} 分钟 (实测 1.7 帧/秒)")

    fr_dir = os.path.join(a.tmp, "sub")
    ov_dir = os.path.join(a.tmp, "ov")
    for d in (fr_dir, ov_dir):
        shutil.rmtree(d, ignore_errors=True)
        os.makedirs(d, exist_ok=True)

    # ---- 1) 逐帧渲染字幕(透明 PNG)
    times = [t0 + i / fps for i in range(n)]
    # 分批: argv 长度有限, 每批 400 个时刻
    B = 400
    t_start = time.time()
    for bi in range(0, len(times), B):
        batch = times[bi:bi + B]
        cmd = [sys.executable, os.path.join(HERE, "render_octopus.py"), a.ass,
               "--out", fr_dir + "/", "--times", ",".join("%.3f" % t for t in batch),
               "--width", str(W), "--height", str(H), "--fontsdir", a.fontsdir]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print(r.stdout[-1500:]); print(r.stderr[-1500:])
            raise SystemExit("字幕渲染失败(批 %d)" % (bi // B))
        done = min(bi + B, len(times))
        el = time.time() - t_start
        print(f"  字幕 {done}/{n} 帧  {el:.0f}s  预计剩余 {max(0,(n-done))/max(0.1,(done/el))*1:.0f}s", flush=True)

    # ---- 2) 叠加到 MV
    print("叠加到 MV ...")
    # 用 filter 一次做完: movie= 读字幕帧序列 + overlay
    # 字幕帧名是 %08.2f, 用 image2 序列读不方便 -> 直接按索引重命名
    files = sorted(os.listdir(fr_dir))
    if len(files) != n:
        print(f"  [warn] 帧数不符: 得到 {len(files)}, 期望 {n}")
    for i, fn in enumerate(files):
        os.rename(os.path.join(fr_dir, fn), os.path.join(fr_dir, "f%06d.png" % i))
    if len(files) == 0:
        raise SystemExit("没渲染出任何字幕帧")

    cmd = ["ffmpeg", "-v", "error", "-y",
           "-ss", "%.3f" % t0, "-i", a.video,
           "-framerate", "%g" % fps, "-i", os.path.join(fr_dir, "f%06d.png"),
           "-filter_complex", "[0:v]scale=%d:%d[bg];[bg][1:v]overlay=0:0:format=auto[v]" % (W, H),
           "-map", "[v]", "-t", "%.3f" % (t1 - t0),
           "-r", "%g" % fps, "-c:v", "libx264", "-preset", "medium", "-crf", str(a.crf),
           "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
    if a.audio:
        cmd += ["-map", "0:a?", "-c:a", "aac", "-b:a", "192k"]
    cmd += [a.out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-2000:])
        raise SystemExit("编码失败")
    sz = os.path.getsize(a.out) / 1e6
    print(f"-> {a.out}  ({sz:.1f} MB)")

    if not a.keep_frames:
        shutil.rmtree(fr_dir, ignore_errors=True)
        shutil.rmtree(ov_dir, ignore_errors=True)
        print("中间帧已清理 (要保留加 --keep-frames)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
