# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy"]
# ///
"""量"歌词比人声慢多少" —— 把可从音频测出的量一次测死，以后不再重算。

做法：对每一句，取它的第一个音拍起点 t0；在人声 stem 上于 [t0-0.45, t0+0.35] 找
能量上升沿（RMS 正差分最大点），delta = onset - t0。全体取中位 = 系统性滞后。

    uv run check_lag.py --project proj
判据与已核实的假阳性见 ../steps/08-review-timing/impl/lag-verdict.md —— **先读它，不要重新推导**：
逐句起音法给出的"字幕偏晚"在长句/长音句上是**系统性假阳性**，不要照它平移。
"""
import argparse
import json
import os
import sys
import wave

import numpy as np


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True, help="工程目录（内有 timing.json 与 stems/vocals16k.wav）")
    ap.add_argument("--report", help="默认 <project>/review/lag.json")
    a = ap.parse_args()

    p = os.path.abspath(a.project)
    tm = json.load(open(os.path.join(p, "timing.json")))
    w = wave.open(os.path.join(p, "stems", "vocals16k.wav"))
    sr = w.getframerate()
    a16 = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64) / 32768.0
    hop = int(0.005 * sr)
    n = (len(a16) - hop) // hop
    rms = np.sqrt(np.array([np.mean(a16[i*hop:(i+1)*hop]**2) for i in range(n)]) + 1e-12)
    rms_db = 20 * np.log10(rms)
    by = {}
    for m in tm:
        if m.get("call"):
            continue
        by.setdefault(m["line"], []).append(m)
    deltas = []
    rows = []
    for li in sorted(by):
        v = sorted(by[li], key=lambda x: x["s"])
        t0 = v[0]["s"]
        i0 = max(1, int((t0 - 0.45) / 0.005)); i1 = min(n - 1, int((t0 + 0.35) / 0.005))
        if i1 - i0 < 4:
            continue
        seg = rms_db[i0:i1]
        # 该句能量基准
        line_lo, line_hi = int(t0/0.005), int((v[-1]["e"])/0.005)
        base = np.percentile(rms_db[max(0,line_lo):min(n,line_hi)], 60)
        thr = base - 14.0            # 起音判据: 比该句基准低 14dB 以内
        onset = None
        for i in range(1, len(seg)):
            if seg[i] >= thr and seg[i-1] < thr:
                onset = i0 + i
                break
        if onset is None:
            # 退而求其次: 正差分最大处
            d = np.diff(seg)
            onset = i0 + int(np.argmax(d)) + 1
        dt = onset * 0.005 - t0
        deltas.append(dt)
        rows.append((li, t0, dt))
    print("=== 逐句滞后 (onset - 首拍) ===")
    for li, t0, dt in rows:
        flag = "  <== 偏晚" if dt > 0.08 else ""
        print("  行%2d t0=%7.2f  delta=%+6.3fs%s" % (li, t0, dt, flag))
    d = np.array(deltas)
    print()
    print("中位滞后 %+.3fs   均值 %+.3fs   标准差 %.3fs" % (np.median(d), d.mean(), d.std()))
    print("正的(字幕偏晚)占 %d/%d" % (int((d > 0).sum()), len(d)))
    out = a.report or os.path.join(p, "review", "lag.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump({"median_lag": float(np.median(d)), "n": len(d)}, open(out, "w"), indent=1)
    print("-> %s" % out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
