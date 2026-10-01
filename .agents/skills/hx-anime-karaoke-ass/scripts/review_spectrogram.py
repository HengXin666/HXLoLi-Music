# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "matplotlib"]
# ///
"""
人工复核卡拉OK时间：人声频谱（0-1500Hz，看谐波=音符）+ 音拍起点竖线
用法:
  uv run review_spectrogram.py --vocals stems/vocals16k.wav --timing timing.json --lines 0-3 --out review.png
  uv run review_spectrogram.py ... --windows 20.1-25.8,26.1-31.0 --out review.png
读图要点:
  - 横向亮条=持续的音符；音符起点处谐波断开/跳变/辅音噪声(竖向宽带)
  - 每个音拍竖线应落在对应音符的起音处；落在换气噪声/长音中间的都是错的
  - 长音（伸ばし）只有一个起点，中途不要切
  - 修正写进 fixes.json: {"line,unit,mora": 新起点秒}
"""
import argparse, json, wave, numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from scipy.signal import stft

ap = argparse.ArgumentParser()
ap.add_argument("--vocals", required=True); ap.add_argument("--timing", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--lines"); ap.add_argument("--windows"); ap.add_argument("--font", default="/usr/share/fonts/noto-preview/NotoSansSC.ttf")
ap.add_argument("--pad", type=float, default=0.4)
ap.add_argument("--onsets", action="store_true", help="叠加 check_sync 的起音候选（白色短刻度）与基频轨迹（青色点）")
ap.add_argument("--grid", help="beat_grid.py 输出；叠加节拍网格（粗线=拍，细线=细分）")
ap.add_argument("--grid-div", type=int, default=4); ap.add_argument("--grid-lag", type=float, default=0.035,
                help="元音相对网格的平均滞后（CTC 起点≈辅音后元音）")
a = ap.parse_args()
try:
    font_manager.fontManager.addfont(a.font); plt.rcParams["font.family"] = font_manager.FontProperties(fname=a.font).get_name()
except Exception:
    pass
w = wave.open(a.vocals)
A = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
f, t, Z = stft(A, 16000, nperseg=1024, noverlap=1024 - 160)
S = 20 * np.log10(np.abs(Z) + 1e-6)
mor = json.load(open(a.timing))
wins = []
if a.windows:
    wins = [tuple(map(float, x.split("-"))) for x in a.windows.split(",")]
else:
    l0, l1 = map(int, a.lines.split("-"))
    for li in range(l0, l1 + 1):
        ms = [m for m in mor if m["line"] == li]
        if ms: wins.append((ms[0]["s"] - a.pad, ms[-1]["e"] + 0.2))
if a.onsets:
    import sys, os; sys.path.insert(0, os.path.dirname(__file__))
    from check_sync import yin_f0, onset_candidates, mel_flux
    from align_ctc import energy_db
    F0 = yin_f0(A); DB_ = energy_db(A, smooth=3); FL_ = mel_flux(A)
    nn = min(len(F0), len(DB_), len(FL_)); CAND = onset_candidates(DB_[:nn], FL_[:nn], F0[:nn])
fig, axes = plt.subplots(len(wins), 1, figsize=(20, 3.4 * len(wins)), squeeze=False)
for ax, (x0, x1) in zip(axes[:, 0], wins):
    m = (t >= x0) & (t <= x1); fm = f <= 1500
    ax.imshow(S[fm][:, m], origin="lower", aspect="auto", extent=[x0, x1, 0, 1500], cmap="magma", vmin=-80, vmax=-10)
    if a.grid:
        import sys, os; sys.path.insert(0, os.path.dirname(__file__))
        from beat_grid import grid_lines
        G = json.load(open(a.grid))
        for gt, beat in grid_lines(G, x0, x1, a.grid_div):
            ax.axvline(gt + a.grid_lag, color="lime" if beat else "#3a8a3a", lw=1.4 if beat else 0.7, alpha=0.8, ls="--")
    if a.onsets:
        tt = np.arange(len(F0)) * 0.01; sel = (tt >= x0) & (tt <= x1) & ~np.isnan(F0)
        hz = 440 * 2 ** ((F0[sel] - 69) / 12)
        ax.plot(tt[sel], np.clip(hz, 0, 1490), ".", ms=2, color="#7fffd4", alpha=0.8)
        for c in CAND[(CAND >= x0) & (CAND <= x1)]:
            ax.plot([c, c], [1420, 1500], color="white", lw=2)
    for x in mor:
        if x0 <= x["s"] <= x1:
            ax.axvline(x["s"], color="cyan", lw=1)
            ax.text(x["s"] + 0.01, 1330, x["text"], color="white", fontsize=14)
            ax.text(x["s"] + 0.01, 60, f'{x["line"]},{x["unit"]},{x["mora"]}', color="yellow", fontsize=7)
    step = 0.1 if x1 - x0 < 12 else 0.5
    ax.set_xticks(np.arange(np.ceil(x0 / step) * step, x1, step)); ax.tick_params(labelsize=7)
    ax.grid(axis="x", color="gray", lw=0.3, alpha=0.5)
plt.tight_layout(); plt.savefig(a.out, dpi=72)
print("saved", a.out)
