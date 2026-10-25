#!/usr/bin/env python3
"""歌词时间轴 ↔ 音频对齐检测。

用途: 拿到一份带时间轴的歌词 (ASS/JSON), 判断它和本地音频是否对齐,
     差多少, 以及是整体偏移还是长度差(尾部静音)。

原理: 提取音频的能量包络 (10ms 分辨率), 找"开始有声"的点;
     再取歌词首句的起始时间; 两者之差即整体偏移。
     另外比较音频有效时长 与 歌词末尾时间, 差值大就是尾部多出来的部分。

用法:
  python3 check_align.py --ass lyrics.ass --audio song.mp3
"""
import argparse, re, subprocess, sys
import numpy as np


def audio_envelope(path, sr=8000, hop=80):
    """解码成单声道 PCM, 返回 (包络数组, 每格毫秒数)。"""
    cmd = ["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(sr),
           "-f", "s16le", "-"]
    raw = subprocess.run(cmd, capture_output=True).stdout
    if not raw:
        raise SystemExit("ffmpeg 解码失败: %s" % path)
    a = np.frombuffer(raw, dtype="<i2").astype(np.float32)
    n = len(a) // hop
    env = np.abs(a[:n * hop]).reshape(n, hop).mean(axis=1)
    return env, hop / sr * 1000.0


def first_sound(env, ms_per_cell, thresh_ratio=0.08, sustain_cells=8):
    """返回首次"持续有声"的时刻 (毫秒)。"""
    if env.size == 0:
        return 0.0
    th = env.max() * thresh_ratio
    above = env > th
    run = 0
    for i, v in enumerate(above):
        run = run + 1 if v else 0
        if run >= sustain_cells:
            return max(0.0, (i - sustain_cells + 1) * ms_per_cell)
    return 0.0


def last_sound(env, ms_per_cell, thresh_ratio=0.08, sustain_cells=8):
    """返回最后"持续有声"的结束时刻 (毫秒)。"""
    if env.size == 0:
        return 0.0
    th = env.max() * thresh_ratio
    above = env > th
    run = 0
    best = 0
    for i, v in enumerate(above):
        run = run + 1 if v else 0
        if run >= sustain_cells:
            best = i + 1
    return best * ms_per_cell


def parse_ass_times(path):
    t = open(path, encoding="utf-8-sig", errors="replace").read()
    out = []
    for line in t.splitlines():
        if not line.startswith("Dialogue:"):
            continue
        f = line.split(",", 9)
        if len(f) < 10:
            continue
        for s in (f[1], f[2]):
            h, m, rest = s.split(":")
            sec, cs = rest.split(".")
            out.append(int(h) * 3600000 + int(m) * 60000 + int(sec) * 1000 + int(cs) * 10)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ass", required=True)
    ap.add_argument("--audio", required=True)
    a = ap.parse_args()

    env, ms = audio_envelope(a.audio)
    fs = first_sound(env, ms)
    ls = last_sound(env, ms)
    times = parse_ass_times(a.ass)
    if not times:
        raise SystemExit("歌词里没有 Dialogue 事件")
    t0, t1 = min(times), max(times)

    print("音频: %s" % a.audio)
    print("  首次有声 %8.0f ms" % fs)
    print("  最后有声 %8.0f ms" % ls)
    print("  总时长   %8.0f ms" % (env.size * ms))
    print("歌词: %s  (%d 个时间戳)" % (a.ass, len(times)))
    print("  首句开始 %8.0f ms" % t0)
    print("  末句结束 %8.0f ms" % t1)
    print()

    # 判据 1: 整体偏移  音频首次有声 vs 歌词首句
    # 歌词首句常常是曲名/STAFF, 允许它落在音频开头; 关键看差值
    off = t0 - fs
    print("整体偏移 (歌词首句 - 音频首次有声) = %+.0f ms" % off)
    if abs(off) < 300:
        print("  -> 对齐良好")
    elif abs(off) < 2000:
        print("  -> 轻微偏移, 可整体平移 %+.0f ms 校正" % (-off))
    else:
        print("  -> 明显偏移! 需要 %+.0f ms 校正" % (-off))

    # 判据 2: 尾部长度差  常见于音频带静音尾巴
    tail = (env.size * ms) - t1
    print()
    print("尾部余量 (音频总长 - 歌词末句) = %.0f ms" % tail)
    if tail > 1000:
        print("  -> 音频末尾多出 %.1f 秒 (%s)" % (tail / 1000.0,
              "静音尾巴" if ls < t1 + 500 else "可能有额外内容"))
    delta = (env.size * ms) - (t1 - t0)
    print()
    print("结论: 音频 %.1f 秒 vs 歌词跨度 %.1f 秒, 差 %.1f 秒"
          % (env.size * ms / 1000, (t1 - t0) / 1000, delta / 1000))
    return 0


if __name__ == "__main__":
    sys.exit(main())
