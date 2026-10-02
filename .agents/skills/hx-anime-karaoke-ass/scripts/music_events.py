#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy"]
# ///
"""音乐事件表: 把伴奏抽成"卡点层"的时间基.

## 为什么必须有这一层 (2026-10-03 用户提出)

现在所有特效的触发源只有一个: **人声音拍**(每个字的 c["s"] 来自对人声轨的 CTC 对齐).
特效挂在它上面, 所以特效只会"跟唱", 不会"跟曲".

实测证据(参考成品 天使の3P「大切がきこえる」01:00 高潮段):
  * 绘图事件 3328 条, 是文字事件(1516)的 **2.2 倍**
  * 高潮段 44 次"群发"(50ms 内 >=3 条同起), 间隔落在 **0.125s 十六分音符网格**上
    (对齐误差中位 0.20; 随机应为 0.5)
  * **群发时刻与同刻字的音拍零重合** -- 图形属于音乐, 不属于字

## 职责边界 (定错了会毁掉同步感)

  * **人声触发承担"同步正确性"** -- 字什么时候唱出来只能由人声决定, 错了立刻被看出.
  * **伴奏触发承担"情绪强度"** -- 环境何时脉动/爆发由伴奏决定, 它不承担信息正确性, 可以夸张.

推论: **卡点层不许长成"字"** -- 一旦它看起来像文字, 观众就会拿它判断"唱到哪了",
而它是伴奏触发, 必然与人声错位, 结果是觉得字幕错了.

## 输出的事件类型

| type | 判据 | 用途 |
|---|---|---|
| `onset` | 谱通量局部峰 | 瞬态迸发(鼓点) |
| `beat` | 节拍网格点(由 onset 自相关推定 BPM 与相位) | 呼吸/脉动 |
| `sub` | 低频能量峰(80Hz 以下) | 下沉/重量感 |
| `section` | 长时间尺度的能量台阶 | 段落边界(与 chordwiki 转调点互验) |

网格点同时输出 **十六分音符** 级 -- 参考成品的群发就落在这个网格上.

用法:
  hx-karaoke music_events.py --inst proj/stems/inst.wav --out proj/review/music-events.json
  hx-karaoke music_events.py --inst inst.wav --out review/music-events.json --bpm-hint 138
  hx-karaoke music_events.py --inst inst.wav --out review/music-events.json --verify --vocals stems/vocals16k.wav

`--verify` 会算"卡点事件与歌词音拍的时间重合率", 判据是**应当很低**.
"""
import argparse, json, math, os, sys, wave

import numpy as np


# ------------------------------------------------------------------ 音频
def read_wav(path, want_sr=22050):
    with wave.open(path, "rb") as w:
        sr, n, ch, sw = w.getframerate(), w.getnframes(), w.getnchannels(), w.getsampwidth()
        raw = w.readframes(n)
    if sw != 2:
        raise SystemExit("只支持 16-bit PCM: %s (sampwidth=%d)" % (path, sw))
    a = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    if ch > 1:
        a = a.reshape(-1, ch).mean(axis=1)
    if sr != want_sr:
        idx = np.linspace(0, len(a) - 1, int(len(a) * want_sr / sr))
        a = np.interp(idx, np.arange(len(a)), a).astype(np.float32)
        sr = want_sr
    return a, sr


def stft_mag(x, sr, win=2048, hop=256):
    n = 1 + max(0, (len(x) - win) // hop)
    w = np.hanning(win).astype(np.float32)
    S = np.empty((n, win // 2 + 1), dtype=np.float32)
    for i in range(n):
        seg = x[i * hop:i * hop + win]
        if seg.size < win:
            S = S[:i]
            break
        S[i] = np.abs(np.fft.rfft(seg * w))
    return S, sr / hop


def spectral_flux(S):
    """正向谱通量: 只算能量增加的 bin -- 这才是"起音", 不是"亮度变化" """
    d = np.diff(S, axis=0)
    d[d < 0] = 0
    f = d.sum(axis=1)
    med = np.median(f)
    return np.maximum(f - med, 0)


def pick_peaks(env, fr, min_gap=0.06, rel=0.28, abs_floor=0.0):
    """局部极大 + 相对阈值: 只留每个"峰包"的最高点"""
    thr = max(abs_floor, env.max() * rel)
    idx = []
    i = 0
    n = len(env)
    gap = max(1, int(min_gap * fr))
    while i < n:
        if env[i] >= thr:
            j = i
            while j + 1 < n and env[j + 1] >= thr * 0.55:
                j += 1
            k = i + int(np.argmax(env[i:j + 1]))
            idx.append(k)
            i = j + 1
        else:
            i += 1
    # 二次去重: 靠太近的只留大的
    out = []
    for k in idx:
        if out and (k - out[-1]) < gap:
            if env[k] > env[out[-1]]:
                out[-1] = k
        else:
            out.append(k)
    return out


# ------------------------------------------------------------------ BPM / 相位
def estimate_bpm(onset_t, lo=60, hi=200):
    """由起音间隔直方图推 BPM -- 比自相关更稳(对弱起拍不敏感)"""
    if len(onset_t) < 6:
        return None, None
    iv = np.diff(onset_t)
    iv = iv[(iv > 0.15) & (iv < 2.0)]
    if len(iv) < 4:
        return None, None
    best = None
    for bpm in np.arange(lo, hi + 0.5, 0.5):
        per = 60.0 / bpm
        # 每个间隔落在整数倍拍上的误差(允许 8 分/16 分细分)
        err = 0.0
        for x in iv:
            for div in (0.5, 1.0, 1.5, 2.0, 3.0, 4.0):
                pass
            k = x / per
            frac = abs(k - round(k))
            frac = min(frac, min(abs(x / (per * d) - round(x / (per * d))) for d in (0.5, 0.25, 2, 3, 4)))
            err += frac
        err /= len(iv)
        if best is None or err < best[1]:
            best = (bpm, err)
    return best


def beat_phase(onset_t, bpm, n_div=4):
    """给定 BPM 求相位: 让最多起音落在网格上"""
    per = 60.0 / bpm
    step = per / n_div
    best = None
    for ph in np.arange(0, step, step / 24):
        err = sum(min(abs((t - ph) / step - round((t - ph) / step)) for t in onset_t) for t in onset_t)
        err /= max(1, len(onset_t))
        if best is None or err < best[1]:
            best = (ph, err)
    return best


def low_energy(x, sr, hop, win=2048, cut=90.0):
    """低频包络(80~90Hz 以下) -- 重量感/下沉"""
    n = 1 + max(0, (len(x) - win) // hop)
    out = np.zeros(n, dtype=np.float32)
    w = np.hanning(win).astype(np.float32)
    # 简易低通: 滑动平均后再取包络, 等价于压掉高频
    k = max(1, int(sr / cut / 2))
    lp = np.convolve(x, np.ones(k, dtype=np.float32) / k, mode="same")
    for i in range(n):
        seg = lp[i * hop:i * hop + win]
        if seg.size < win:
            break
        out[i] = float(np.sqrt(np.mean(seg ** 2)))
    return out


def sections(env, fr, min_len=4.0, n_sec=8):
    """段落边界: 对能量包络做长窗平滑后找台阶"""
    k = max(1, int(2.0 * fr))
    sm = np.convolve(env, np.ones(k) / k, mode="same")
    if len(sm) < n_sec * 2:
        return []
    # 等分后取每段中位, 再把相邻差值大的地方当边界
    step = max(1, int(len(sm) / n_sec))
    centers = [float(np.median(sm[i:i + step])) for i in range(0, len(sm) - step + 1, step)]
    out = []
    for i in range(1, len(centers)):
        if abs(centers[i] - centers[i - 1]) > 0.35 * (max(centers) + 1e-9):
            out.append(round(i * step / fr, 2))
    return out


# ------------------------------------------------------------------ 主流程
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inst", required=True, help="伴奏轨 wav (04-vocals 的 inst.wav)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--vocals", help="给人声轨, 配合 --verify 算与音拍的重合率")
    ap.add_argument("--timing", help="timing.json, 配合 --verify")
    ap.add_argument("--bpm-hint", type=float, default=None)
    ap.add_argument("--div", type=int, default=4, help="网格细分: 4=十六分音符(默认), 2=八分")
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args()

    x, sr = read_wav(a.inst)
    S, fr = stft_mag(x, sr)
    flux = spectral_flux(S)
    lo = low_energy(x, sr, int(sr / fr)) if False else low_energy(x, sr, int(sr / fr))
    dur = len(x) / sr
    print(f"伴奏 {dur:.1f}s, 谱帧率 {fr:.0f}/s")

    pk = pick_peaks(flux, fr)
    onset_t = [round(i / fr, 3) for i in pk]
    print(f"起音 {len(onset_t)} 个")

    bpm, berr = (a.bpm_hint, None) if a.bpm_hint else estimate_bpm(onset_t)
    phase = None
    if bpm:
        ph, perr = beat_phase(onset_t, float(bpm), a.div)
        phase = round(float(ph), 4)
        print(f"BPM {bpm:.1f}  相位 {phase:.3f}s  网格 {60.0/float(bpm)/a.div*1000:.1f}ms ({'十六分' if a.div==4 else '八分'})")
    grid = []
    if bpm:
        step = 60.0 / float(bpm) / a.div
        t = phase
        while t < dur:
            grid.append(round(t, 3))
            t += step
        print(f"网格点 {len(grid)} 个")
        # 自检: 起音应当落在网格上. 归一化误差 中位 <0.30 = 贴合, 0.5 = 随机.
        # 实测本工程 0.051(BPM 84.5), 是"网格与 BPM 都对"的机械证据.
        import bisect
        errs = []
        for tt in onset_t:
            i = bisect.bisect_left(grid, tt)
            d = min(abs(grid[j] - tt) for j in (i - 1, i, i + 1) if 0 <= j < len(grid))
            errs.append(d / step)
        errs.sort()
        med = errs[len(errs) // 2] if errs else 1.0
        grid_fit = round(float(med), 4)
        print(f"起音对网格的归一化误差 中位 {med:.3f}  ({'贴合' if med < 0.30 else '不贴合 -- BPM 或相位错了'})")

    # 低频峰
    lp_pk = pick_peaks(low_energy(x, sr, int(sr / fr)), fr, min_gap=0.08, rel=0.45)
    sub_t = [round(i / fr, 3) for i in lp_pk]
    secs = sections(flux, fr)
    print(f"低频峰 {len(sub_t)} 个, 段落边界 {secs}")

    # 每次起音的强度 -> 供生成器决定群发条数
    strength = {}
    for i in pk:
        strength[round(i / fr, 3)] = float(flux[i] / (flux.max() + 1e-9))

    ev = dict(
        source=os.path.abspath(a.inst), sr=sr, duration=round(dur, 3),
        bpm=(round(float(bpm), 2) if bpm else None), grid_div=a.div,
        phase=phase, grid_step=(round(60.0 / float(bpm) / a.div, 4) if bpm else None),
        grid=grid, onset=onset_t, sub=sub_t, section=secs, strength=strength,
        grid_fit=grid_fit if bpm else None,
    )

    if a.verify and a.vocals and a.timing:
        vy, vsr = read_wav(a.vocals)
        tmx = json.load(open(a.timing, encoding="utf-8"))
        mora = sorted((float(m["s"]) for m in tmx))
        import bisect
        hit = 0
        for t in onset_t:
            i = bisect.bisect_left(mora, t)
            for j in (i - 1, i):
                if 0 <= j < len(mora) and abs(mora[j] - t) < 0.04:
                    hit += 1
                    break
        r = hit / max(1, len(onset_t))
        ev["verify"] = dict(mora_count=len(mora), onset_count=len(onset_t), coincide=hit, ratio=round(r, 4))
        print(f"\n★ 起音与歌词音拍(±40ms)重合率: {hit}/{len(onset_t)} = {r:.1%}")
        print("  判据: 卡点层应当**不与人声音拍重合** -- 重合率高说明抽到的是人声泄漏, 换伴奏轨或降 rel")

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump(ev, open(a.out, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"\n-> {a.out}  ({os.path.getsize(a.out)/1024:.1f} KB)")
    print("用法: 生成器按 grid 排卡点层; 按 strength 决定单次群发条数(3~10, 峰值 23)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
