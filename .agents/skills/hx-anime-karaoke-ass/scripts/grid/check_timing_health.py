# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "scipy"]
# ///
"""时间轴体检：把「音拍被拖长/挤压」这类 CTC 塌缩问题变成可机械判据。

为什么需要：CTC 对齐在两种地方会失手，且都是"看起来正常、听起来差几秒"：
  A) 长音（伸ばし） 歌手把一个音节拖了 2~4 秒，CTC 会把这段全算给这一个音拍，
     于是它后面的音拍起点被整体推迟；听感上字幕"慢了半拍到几秒"。
  B) 换气/间奏  CTC 会把句内 8 秒空档吞进最后一个音拍，下一句首拍被推迟。
本脚本用三个互相独立的量交叉定位，不依赖任何单一模型：
  1) 音拍时长分布（相对中位） 抓"过长"
  2) 人声谱通量起音（spectral flux） 抓"这一拍实际什么时候起唱"
  3) 句内静音段（>=0.45s） 抓"这里其实是间奏不是歌词"

输出：可直接抄进 fixes.json 的建议 {"line,unit,mora": 新起点}。

用法:
  hx-karaoke check_timing_health.py --vocals stems/vocals16k.wav --timing timing.json \
       [--grid grid.json] --report review/health.txt [--fixes-out review/suggest.json]
"""
import argparse, bisect, json, wave
import numpy as np
from scipy.signal import stft

def read_wav(p):
    w = wave.open(p)
    assert w.getframerate() == 16000
    return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768

def onsets(a, sr=16000, hop=160, nfft=1024, k=0.6):
    f, t, Z = stft(a, fs=sr, nperseg=nfft, noverlap=nfft - hop, window="hann")
    S = np.log1p(np.abs(Z)); S = S[(f > 150) & (f < 4500)]
    flux = np.maximum(0, np.diff(S, axis=1)).sum(axis=0)
    flux = np.convolve(flux, np.ones(3) / 3, "same")
    m, sd = flux.mean(), flux.std()
    return np.array([t[i] for i in range(1, len(flux) - 1)
                     if flux[i] > flux[i-1] and flux[i] >= flux[i+1] and flux[i] > m + k * sd])

def db_profile(a, hop=1600):
    n = len(a) // hop
    rms = np.sqrt(np.mean(a[:n*hop].reshape(n, hop) ** 2, axis=1))
    return 20 * np.log10(rms + 1e-9)

def silence(db, thr, min_s=0.45):
    low = db < thr; out = []; s = None
    for i, v in enumerate(low):
        if v and s is None: s = i
        if not v and s is not None:
            if (i - s) / 10.0 >= min_s: out.append((s / 10.0, i / 10.0))
            s = None
    if s is not None: out.append((s / 10.0, len(low) / 10.0))
    return out

ap = argparse.ArgumentParser()
ap.add_argument("--vocals", required=True); ap.add_argument("--timing", required=True)
ap.add_argument("--grid"); ap.add_argument("--report", default="")
ap.add_argument("--fixes-out", default="")
ap.add_argument("--long-ratio", type=float, default=1.8, help="单拍 > 中位拍长 × 此值 = 过长")
ap.add_argument("--min-long", type=float, default=1.0, help="且绝对时长 > 此秒数")
# 门禁开关。默认全开（塌缩与句内间奏都必须为 0）；给 -1 = 该条不限（显式放行）。
ap.add_argument("--max-collapse", type=int, default=0,
                help="允许的 CTC 塌缩处数上限；默认 0。给 -1 = 关闭本项门禁")
ap.add_argument("--max-inner-silence", type=int, default=0,
                help="允许的句内间奏处数上限；默认 0。给 -1 = 关闭本项门禁")
a = ap.parse_args()

A = read_wav(a.vocals); DB = db_profile(A)
voiced = DB[DB > np.percentile(DB, 30)]
thr = float(np.median(voiced) - 20)
ON = onsets(A); ON.sort()
# Agent Notes: 逐字时间以网络逐字歌词为权威，CTC 只用于定整体平移
# 
# Agent Notes: 逐字时间以网络逐字歌词为权威，CTC 只用于定整体平移
# .agents/notes/implemented/process/2026-10-02-karaoke-lyrics-timing-authority.md
T = json.load(open(a.timing))
by = {}
for m in T: by.setdefault(m["line"], []).append(m)
for v in by.values(): v.sort(key=lambda x: x["s"])

durs = np.array([m["e"] - m["s"] for m in T if not m.get("call")])
med = float(np.median(durs))

L = []
def w(s_=""): L.append(s_)

w(f"# 时间轴体检报告")
w(f"人声 {len(A)/16000:.1f}s | 音拍 {len(T)} | 中位拍长 {med*1000:.0f}ms | 静音阈 {thr:.1f}dB | 起音候选 {len(ON)}")
w("")
w(f"## A. 过长音拍（> {a.long_ratio}× 中位 = {med*a.long_ratio*1000:.0f}ms，且 > {a.min_long}s）")
w("   内部静音占比 = 该拍时长里处于静音(低于阈值)的比例。")
w("   <15% 真拖长（字幕停在此字上正确，不要改）｜>35% CTC塌缩（必须修）｜中间 存疑")
w(f"{'line':>4} {'unit':>4} {'mora':>4} {'音节':>4} {'起点':>8} {'时长':>7} {'内部静音':>8} {'占比':>5} {'最近起音':>8} {'Δms':>6}  判定")
FR = 20.0   # db_profile 用 hop=1600 => 100ms/帧 => 每秒 10 帧
longs = []
for m in T:
    d = m["e"] - m["s"]
    if d > med * a.long_ratio and d > a.min_long:
        i0, i1 = int(round(m["s"] * 10)), int(round(m["e"] * 10))
        seg = DB[max(0, i0):i1]
        sil = float((seg < thr).sum()) * 0.1 if len(seg) else 0.0
        frac = sil / d if d > 0 else 0.0
        j = int(np.argmin(np.abs(ON - m["s"]))) if len(ON) else -1
        near = ON[j] if j >= 0 else float("nan")
        dd = (m["s"] - near) * 1000 if j >= 0 else float("nan")
        longs.append((m, d, near, dd, sil, frac))
n_col = 0
for m, d, near, dd, sil, frac in sorted(longs, key=lambda x: -x[5]):
    verdict = "真拖长" if frac < 0.15 else ("!! CTC塌缩" if frac > 0.35 else "存疑")
    if frac > 0.35: n_col += 1
    w(f"{m['line']:>4} {m['unit']:>4} {m['mora']:>4} {m['text']:>4} {m['s']:8.2f} {d:6.2f}s {sil:7.2f}s {frac*100:4.0f}% {near:8.2f} {dd:6.0f}  {verdict}")
w(f"共 {len(longs)} 处长音；其中 **CTC塌缩 {n_col} 处（应为 0）**、真拖长 {sum(1 for x in longs if x[5]<0.15)} 处")
w("")
w(f"## B. 句内静音 >=0.45s（CTC 把间奏吞进句子的嫌疑）")
spans = [(li, v[0]["s"], v[-1]["e"]) for li, v in sorted(by.items())]
sil = silence(DB, thr, 0.45)
n_in = 0
for s0, s1 in sil:
    inside = [li for li, s, e in spans if s0 >= s - 0.05 and s1 <= e + 0.05]
    between = [(li, lj) for li, s, e in spans for lj, s2, e2 in spans if lj == li + 1 and e <= s0 and s2 >= s1]
    if inside:
        n_in += 1
        w(f"  !! 句内间奏 {s0:.2f}-{s1:.2f} ({s1-s0:.2f}s) 属于 line {inside}  ← 必须在歌词里拆开或改分句")
    elif between:
        w(f"     行间间奏 {s0:.2f}-{s1:.2f} ({s1-s0:.2f}s) 在 {between[0][0]}→{between[0][1]} 之间（正常，可放卡片）")
w(f"句内间奏 {n_in} 处（应为 0）")
w("")
w(f"## C. 音拍与最近起音的偏差（>120ms 无法匹配 = 可疑）")
miss = 0
for li, v in sorted(by.items()):
    ds = []
    for m in v:
        j = int(np.argmin(np.abs(ON - m["s"])))
        d = m["s"] - ON[j]
        if abs(d) <= 0.12: ds.append(d)
    if len(ds) < max(1, len(v) * 0.6):
        miss += 1
        w(f"  line {li:>2}: 仅 {len(ds)}/{len(v)} 拍匹配到起音  区间 {v[0]['s']:.2f}-{v[-1]['e']:.2f}")
w(f"{miss} 行匹配率 <60%")
w("")
w(f"## 判定")
w(f"CTC塌缩 {n_col} 处 / 句内间奏 {n_in} 处（两者都应为 0）")
if a.max_collapse is not None:
    w(f"门禁：塌缩 <= {a.max_collapse}、句内间奏 <= {a.max_inner_silence}")
txt = "\n".join(L)
print(txt)
if a.report:
    open(a.report, "w", encoding="utf-8").write(txt + "\n")
    print(f"\n[saved] {a.report}")

# ---- 门禁：把「报告」升级成「可失败的检查」 ----
# 为什么必须非零退出：本脚本原先只打印，实测有工程把它跑出了 2 处塌缩又原样交付，
# fixes.json 只写了一条，成片里那句歌词比声音晚了 20 秒。打印不会拦住任何人。
if a.max_collapse is not None and a.max_collapse < 0:
    a.max_collapse = None
if a.max_inner_silence is not None and a.max_inner_silence < 0:
    a.max_inner_silence = None
bad = []
if a.max_collapse is not None and n_col > a.max_collapse:
    bad.append("CTC塌缩 %d 处 > %d" % (n_col, a.max_collapse))
if a.max_inner_silence is not None and n_in > a.max_inner_silence:
    bad.append("句内间奏 %d 处 > %d" % (n_in, a.max_inner_silence))
if bad:
    print("\n[FAIL] " + "；".join(bad))
    print("[FAIL] 修法二选一：")
    print("   1) 有网络逐字歌词时走 kf_timing.py（推荐，实测把塌缩 2→0、句内间奏 3→0）：")
    print("        hx-karaoke kf_timing.py fetch --title ... --artist ... --project proj")
    print("        hx-karaoke kf_timing.py align --project proj --auto timing_auto.json")
    print("   2) 没有逐字源时，按 report 里列出的 (line,unit,mora) 手工写 fixes.json 再 apply_fixes.py")
    print("   确认无需修改时用 --max-collapse -1（或把 -1 视为放行）显式声明，不要静默放过。")
    sys.exit(1)
if a.max_collapse is not None:
    print("\n[PASS] 塌缩 %d 处、句内间奏 %d 处，均在限内。" % (n_col, n_in))
