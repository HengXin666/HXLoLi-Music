# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "numpy",
#   "scipy",
# ]
# ///

"""
从伴奏估计 BPM 与节拍相位，输出十六分音符网格；可把音拍起点吸附到网格（仅作建议）。
用法:
  uv run beat_grid.py --inst stems/inst.wav --out grid.json [--bpm-min 70 --bpm-max 200]
  uv run beat_grid.py --grid grid.json --timing timing.json --report     # 列出偏离网格>60ms 的音拍
原理: 伴奏频谱通量(onset envelope) → 自相关找节拍周期 → 梳状滤波找相位 → 用局部 onset 峰做分段相位微调
J-pop 人声基本落在 1/16 网格（少量切分音落在 1/32 或三连音），网格是判断"这个音拍到底在哪"的最强先验。
"""
import argparse, json, wave, numpy as np
from scipy.signal import stft


def onset_env(path):
    w = wave.open(path); sr = w.getframerate(); ch = w.getnchannels()
    a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    if ch == 2: a = a.reshape(-1, 2).mean(1)
    hop = int(sr * 0.01)
    f, t, Z = stft(a, sr, nperseg=2048, noverlap=2048 - hop)
    S = np.log1p(np.abs(Z) * 100)
    flux = np.maximum(0, np.diff(S, axis=1)).sum(0)
    flux = flux - np.convolve(flux, np.ones(50) / 50, "same")
    return np.maximum(flux, 0), 100.0


def estimate(env, fps, bmin, bmax):
    ac = np.correlate(env - env.mean(), env - env.mean(), "full")[len(env) - 1:]
    lags = np.arange(len(ac))
    best, bl = -1, None
    for L in range(int(fps * 60 / bmax), int(fps * 60 / bmin) + 1):
        sc = ac[L] + 0.5 * ac[2 * L] + 0.5 * ac[L // 2] if 2 * L < len(ac) else ac[L]
        if sc > best: best, bl = sc, L
    # 亚帧精度: 用长跨度的多周期峰值
    period = bl / fps
    for k in (8, 16, 32):
        L = int(round(bl * k)); r = max(2, k // 2)
        if L + r < len(ac):
            j = L - r + int(np.argmax(ac[L - r:L + r + 1]))
            period = j / fps / k
    return 60 / period, period


def phase(env, fps, period, t0=0, t1=None):
    t1 = t1 or len(env) / fps
    ph = np.linspace(0, period, 200, endpoint=False); best, bp = -1, 0
    for p in ph:
        ts = np.arange(t0 + p, t1, period)
        idx = (ts * fps).astype(int); idx = idx[idx < len(env)]
        sc = env[idx].sum() + 0.5 * env[np.clip(idx + 1, 0, len(env) - 1)].sum()
        if sc > best: best, bp = sc, p
    return bp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inst"); ap.add_argument("--out"); ap.add_argument("--grid"); ap.add_argument("--timing")
    ap.add_argument("--report", action="store_true"); ap.add_argument("--bpm-min", type=float, default=70)
    ap.add_argument("--bpm-max", type=float, default=200); ap.add_argument("--seg", type=float, default=20.0)
    a = ap.parse_args()
    if a.inst:
        env, fps = onset_env(a.inst)
        bpm, period = estimate(env, fps, a.bpm_min, a.bpm_max)
        # 分段相位（容忍轻微速度漂移）
        segs = []
        dur = len(env) / fps
        for s in np.arange(0, dur, a.seg):
            segs.append([float(s), float(phase(env, fps, period, s, min(dur, s + a.seg)) + s)])
        g = dict(bpm=round(bpm, 3), period=period, segments=segs)
        json.dump(g, open(a.out, "w"), indent=1)
        print(f"BPM ≈ {bpm:.2f}  (beat {period*1000:.1f} ms, 16th {period/4*1000:.1f} ms)")
        print("各段节拍相位:", " ".join(f"{s:.0f}s:{p:.3f}" for s, p in segs[:8]), "...")
    if a.grid and a.timing and a.report:
        g = json.load(open(a.grid)); mor = json.load(open(a.timing))
        for m in mor:
            q = snap(g, m["s"])
            if abs(q - m["s"]) > 0.06:
                print(f'{m["line"]},{m["unit"]},{m["mora"]} 「{m["text"]}」 {m["s"]:.3f} → 最近16分 {q:.3f} ({(q-m["s"])*1000:+.0f}ms)')


def grid_lines(g, t0, t1, div=4):
    out = []
    for s, p in g["segments"]:
        if s > t1 or s + 20 < t0: continue
    # 用离 t0 最近段的相位
    seg = min(g["segments"], key=lambda sp: abs(sp[0] + 10 - (t0 + t1) / 2))
    st = g["period"] / div
    k0 = np.floor((t0 - seg[1]) / st); k1 = np.ceil((t1 - seg[1]) / st)
    for k in np.arange(k0, k1 + 1):
        t = seg[1] + k * st
        out.append((t, int(k) % div == 0))
    return out


def snap(g, t, div=4):
    ls = grid_lines(g, t - 0.5, t + 0.5, div)
    return min(ls, key=lambda x: abs(x[0] - t))[0]


if __name__ == "__main__":
    main()
