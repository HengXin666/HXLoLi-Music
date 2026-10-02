# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "numpy",
#   "scipy",
#   "torch",
#   "transformers",
# ]
# ///

"""
音画同步自动体检：找出“字先亮、声后到”（抢拍）或“声先到、字后亮”（拖拍）的音拍。

两个独立信号：
  A) 静音抢拍：音拍起点处人声能量仍在底噪（换气/句首空白），人声要到 s+Δ 才真正起来 → 抢拍 Δ
     这是肉眼最容易察觉的错误（句首字在无声时就亮了），也是 CTC/网格吸附最常见的系统误差
  B) 起音偏移：连续演唱中，用人声 log-mel 频谱通量找最近的起音峰，与音拍起点比较
     （只在起点附近没有更好的峰、且偏移方向一致时才报，避免把颤音/滑音当成起音）

用法:
  hx-karaoke check_sync.py --vocals stems/vocals16k.wav --timing timing.json [--report sync.txt] [--fixes-out sync_fixes.json]
输出每条可疑音拍（line,unit,mora 文本 起点 建议起点 Δ 依据），以及按句汇总。
--fixes-out 会写出建议修正（只含 A 类 + 置信度高的 B 类），人工复核频谱后再合并进 fixes.json。
"""
import argparse, json, os, sys
import numpy as np
from scipy.signal import stft
sys.path.insert(0, os.path.dirname(__file__))
from align_ctc import read_wav, energy_db

HOP = 0.01


def mel_flux(A, sr=16000):
    f, t, Z = stft(A, sr, nperseg=512, noverlap=512 - 160)
    P = np.abs(Z) ** 2
    # 简易 mel 滤波（80~4000Hz，40 带）
    mel = lambda x: 2595 * np.log10(1 + x / 700)
    edges = np.linspace(mel(80), mel(4000), 42)
    hz = 700 * (10 ** (edges / 2595) - 1)
    fb = np.zeros((40, len(f)))
    for i in range(40):
        l, c, r = hz[i], hz[i + 1], hz[i + 2]
        fb[i] = np.clip(np.minimum((f - l) / (c - l), (r - f) / (r - c)), 0, None)
    M = np.log(fb @ P + 1e-8)
    d = np.diff(M, axis=1, prepend=M[:, :1])
    flux = np.clip(d, 0, None).sum(0)
    flux = np.convolve(flux, np.ones(3) / 3, "same")
    flux = (flux - np.median(flux)) / (np.percentile(flux, 99) - np.median(flux) + 1e-9)
    return flux


def yin_f0(A, sr=16000, hop=160, win=800, fmin=110, fmax=900, th=0.15):
    """简易 YIN 基频（半音，无声=nan），10ms 一帧"""
    n = (len(A) - win) // hop
    tmax = int(sr / fmin); tmin = int(sr / fmax)
    F = np.full(n, np.nan)
    B = 2048
    for b0 in range(0, n, B):
        idx_ = np.arange(b0, min(n, b0 + B))
        fr = np.stack([A[i * hop:i * hop + win] for i in idx_])
        fr = fr - fr.mean(1, keepdims=True)
        X = np.fft.rfft(fr, 2 * win)
        ac = np.fft.irfft(X * np.conj(X))[:, :tmax + 1]
        cs = np.cumsum(fr ** 2, 1)
        e0 = cs[:, -1:]
        # d(tau) = sum x^2[j] + sum x^2[j+tau] - 2 r(tau)   (近似：窗口内)
        tau = np.arange(tmax + 1)
        tail = e0 - np.concatenate([np.zeros((len(fr), 1)), cs[:, :-1]], 1)[:, :tmax + 1]
        head = cs[:, win - 1 - tau] if False else np.take(cs, np.clip(win - 1 - tau, 0, win - 1), axis=1)
        d = head + tail - 2 * ac
        d[:, 0] = 0
        cm = d[:, 1:] * np.arange(1, tmax + 1) / (np.cumsum(d[:, 1:], 1) + 1e-12)
        cm = np.concatenate([np.ones((len(fr), 1)), cm], 1)
        cm[:, :tmin] = 9
        ok = cm < th
        first = np.where(ok.any(1), ok.argmax(1), -1)
        for k, t0 in enumerate(first):
            if t0 <= 0:
                continue
            t = t0
            while t + 1 <= tmax and cm[k, t + 1] < cm[k, t]:
                t += 1
            F[idx_[k]] = 12 * np.log2(sr / t / 440) + 69
    return F


def onset_candidates(DB, FL, F0):
    """起音候选：能量跃升 / 音高跳变 / 频谱通量峰；返回秒列表"""
    n = min(len(DB), len(FL), len(F0))
    c = []
    for i in range(3, n - 6):
        if DB[i + 3] - DB[i - 3] > 7 and DB[i + 3] == DB[i - 2:i + 6].max():
            c.append(i - 1)
    med = np.copy(F0)
    for i in range(3, n - 3):
        w = F0[i - 3:i + 4]; w = w[~np.isnan(w)]
        med[i] = np.median(w) if w.size >= 4 else np.nan
    for i in range(8, n - 8):
        a_, b_ = med[i - 8:i - 1], med[i + 1:i + 8]
        a_ = a_[~np.isnan(a_)]; b_ = b_[~np.isnan(b_)]
        if a_.size >= 4 and b_.size >= 4 and abs(np.median(b_) - np.median(a_)) > 0.8:
            if abs(med[i + 1] - med[i - 1]) >= abs(med[i + 2] - med[i]) and abs(med[i + 1] - med[i - 1]) >= abs(med[i] - med[i - 2]):
                c.append(i)
    for i in range(2, n - 2):
        if FL[i] > 0.45 and FL[i] == FL[i - 2:i + 3].max():
            c.append(i)
    c = sorted(set(c))
    out = []
    for i in c:
        if not out or i - out[-1] > 4:
            out.append(i)
    return np.array(out) * HOP


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vocals", required=True); ap.add_argument("--timing", required=True)
    ap.add_argument("--report"); ap.add_argument("--fixes-out")
    ap.add_argument("--lead", type=float, default=0.15, help="A 类阈值：起点后人声迟到超过此值即报")
    ap.add_argument("--shift", type=float, default=0.18, help="B 类阈值：最近起音候选在起点后超过此值即报")
    ap.add_argument("--late", type=float, default=0.15, help="C 类：人声起音附近 ±late 内没有音拍起点即报")
    ap.add_argument("--tol", type=float, default=0.09, help="B 类：起点 ±tol 内有候选即视为对齐")
    ap.add_argument("--floor", type=float, default=None, help="静音阈值 dB，默认=人声有声段中位数-22")
    ap.add_argument("--drop", type=float, default=10.0, help="A 类：起点能量低于本拍局部峰值多少 dB 视为“还没唱”")
    a = ap.parse_args()
    A = read_wav(a.vocals); DB = energy_db(A, smooth=3); FL = mel_flux(A); F0 = yin_f0(A)
    n = min(len(DB), len(FL), len(F0)); DB = DB[:n]; FL = FL[:n]; F0 = F0[:n]
    voiced = DB[DB > np.percentile(DB, 40)]
    floor = a.floor if a.floor is not None else float(np.median(voiced) - 22)
    C = onset_candidates(DB, FL, F0)
    mor = [m for m in json.load(open(a.timing)) if not m.get("call")]; mor.sort(key=lambda m: m["s"])
    idx = lambda t: int(np.clip(round(t / HOP), 0, n - 1))
    out, fixes = [], {}
    for i, m in enumerate(mor):
        s = m["s"]; key = f'{m["line"]},{m["unit"]},{m["mora"]}'
        nxt = mor[i + 1]["s"] if i + 1 < len(mor) else s + 2
        if m["text"] in ("っ", "ー"):          # 促音本来就是无声闭塞；长音是延续，不检查起音
            continue
        # ---- A: 静音/弱音抢拍：起点处能量明显低于“本拍稍后的峰值”，且要到 s+Δ 才持续起来
        #      （用局部峰值做参照，不用全局/整句电平：分离残留的伴奏常在 -25dB 左右，轻声句整体又偏弱）
        win_end = min(s + 0.5, max(nxt, s + 0.25))
        pk_db = DB[idx(s):idx(win_end) + 1].max()
        seg = DB[idx(s):idx(s + 0.05) + 1]
        if seg.size and pk_db > floor and seg.mean() < pk_db - a.drop:
            thr = pk_db - 6
            j = idx(s); lim = idx(win_end)
            while j < lim and not (DB[j:j + 4] >= thr).all():
                j += 1
            if j < lim:
                on = j * HOP - 0.03          # 元音能量越过阈值前 ~30ms 为辅音起点
                lead = on - s
                if lead >= a.lead:
                    out.append((key, m["text"], s, round(on, 3), round(lead, 3), "A 起点无声"))
                    fixes[key] = round(on, 3)
                    continue
        # ---- B: 连续演唱：起点附近(±tol)没有任何起音候选（能量跃升/音高跳变/通量峰），
        #         而稍后 [s+shift, 下一拍) 内有 → 抢拍
        near = C[(C >= s - a.tol) & (C <= s + a.tol)]
        if near.size:
            continue
        later = C[(C >= s + a.shift) & (C < min(nxt - 0.04, s + 0.5))]
        if later.size:
            on = float(later[0]); d = on - s
            out.append((key, m["text"], s, round(on, 3), round(d, 3), "B 起音在后"))
    # ---- C: 声先字后（拖拍）：人声从静音中起来（持续 ≥40ms、越过局部峰值-6dB），但附近没有任何音拍起点
    starts = np.array([m["s"] for m in mor])
    j = 5
    while j < n - 10:
        if DB[j - 5:j].max() < DB[j:j + 30].max() - 14 and (DB[j:j + 4] >= DB[j:j + 30].max() - 8).all():
            t = j * HOP - 0.03
            if starts.size and np.abs(starts - t).min() > a.late:
                k = int(np.searchsorted(starts, t))
                if 0 < k < len(mor) and mor[k - 1]["e"] > t - 0.05 or (k < len(mor) and starts[k] - t < 0.8):
                    m = mor[k] if k < len(mor) else mor[-1]
                    # 只报“歌词行内/行首”，行间的器乐/和声起音忽略
                    if k < len(mor) and (starts[k] - t) < 0.8:
                        key = f'{m["line"]},{m["unit"]},{m["mora"]}'
                        out.append((key, m["text"], m["s"], round(t, 3), round(t - m["s"], 3), "C 声先字后"))
            j += 30
        else:
            j += 1
    lines = {}
    for r in out:
        lines.setdefault(int(r[0].split(",")[0]), []).append(r)
    txt = [f"静音阈值 {floor:.1f} dB；可疑 {len(out)} 处（A=起点无声 B=起音在后 → 字快了；C=声先字后 → 字慢了；|Δ|≥0.25s 标 !!）"]
    for li in sorted(lines):
        for key, tx, s, on, dl, why in lines[li]:
            txt.append(f"{'!!' if abs(dl) >= 0.25 else '  '}{key:>9} {tx:<3} s={s:8.3f}  人声起音≈{on:8.3f}  "
                       f"{'快' if dl > 0 else '慢'}了 {abs(dl):.2f}s  [{why}]")
    rep = "\n".join(txt)
    print(rep)
    if a.report:
        open(a.report, "w").write(rep + "\n")
    if a.fixes_out:
        json.dump(fixes, open(a.fixes_out, "w"), indent=1)
        print("建议修正 ->", a.fixes_out, len(fixes))


if __name__ == "__main__":
    main()
