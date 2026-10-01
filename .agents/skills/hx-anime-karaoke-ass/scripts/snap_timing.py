# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "numpy",
#   "scipy",
# ]
# ///

"""
网格吸附 + 挤压段展开（自动修正 CTC 的两类典型错误）
  1) 起点在网格(+lag)±tol 内 → 吸附到网格（提高精度）
  2) 连续“过短”音拍（<min_dur，CTC 没找到而堆在一起）→ 在前后可信锚点之间按网格槽均匀展开
用法: uv run snap_timing.py --timing timing_auto.json --grid grid.json --out timing_snap.json [--div 4 --lag 0.035]
输出后仍需 review_spectrogram.py --grid 人工复核；人工修正写 fixes.json 再 apply_fixes.py
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from beat_grid import grid_lines

ap = argparse.ArgumentParser()
ap.add_argument("--timing", required=True); ap.add_argument("--grid", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--div", type=int, default=4); ap.add_argument("--lag", type=float, default=0.035)
ap.add_argument("--tol", type=float, default=0.06); ap.add_argument("--min-dur", type=float, default=0.075)
a = ap.parse_args()
G = json.load(open(a.grid)); mor = json.load(open(a.timing))
calls = [m for m in mor if m.get("call")]; mor = [m for m in mor if not m.get("call")]   # 合いの手不参与吸附
mor.sort(key=lambda m: m["s"])
n_snap = n_spread = 0
for i, m in enumerate(mor):
    gl = grid_lines(G, m["s"] - 0.4, m["s"] + 0.4, a.div)
    q = min((g[0] + a.lag for g in gl), key=lambda t: abs(t - m["s"]))
    prev = mor[i - 1]["s"] if i else -1; nxt = mor[i + 1]["s"] if i + 1 < len(mor) else 1e9
    if abs(q - m["s"]) <= a.tol and abs(q - m["s"]) > 0.005 and prev + 0.04 < q < nxt - 0.04:
        m["s"] = round(q, 3); n_snap += 1
# 挤压段
lines = sorted(set(m["line"] for m in mor))
for li in lines:
    ms = [m for m in mor if m["line"] == li]
    i = 0
    while i < len(ms) - 1:
        if ms[i + 1]["s"] - ms[i]["s"] < a.min_dur:
            j = i + 1
            while j < len(ms) - 1 and ms[j + 1]["s"] - ms[j]["s"] < a.min_dur: j += 1
            # 挤压段 ms[i..j]；锚点 = ms[i-1] 和 ms[j+1]
            lo = ms[i - 1]["s"] + 0.05 if i > 0 else ms[i]["s"] - 0.4
            hi = ms[j + 1]["s"] if j + 1 < len(ms) else ms[j]["s"] + 0.6
            slots = [g[0] + a.lag for g in grid_lines(G, lo, hi, a.div * 2) if lo <= g[0] + a.lag < hi - 0.04]
            k = j - i + 1
            if len(slots) >= k:
                # 选取尽量均匀的 k 个槽（保留最后 k 个中靠后的，贴近下一个锚点前）
                pick = [slots[int(round(x * (len(slots) - 1) / max(1, k - 1)))] for x in range(k)] if k > 1 else [slots[-1]]
                pick = sorted(set(pick))
                if len(pick) == k:
                    for mm, t in zip(ms[i:j + 1], pick):
                        mm["s"] = round(t, 3)
                    n_spread += k
            i = j + 1
        else:
            i += 1
mor.sort(key=lambda m: m["s"]); mor += calls
json.dump(mor, open(a.out, "w"), ensure_ascii=False, indent=0)
print(f"吸附 {n_snap} 个，展开挤压段 {n_spread} 个 → {a.out}（终点请用 apply_fixes.py 重算）")
