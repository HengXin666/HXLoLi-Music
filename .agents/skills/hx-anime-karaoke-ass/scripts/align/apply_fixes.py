# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "numpy",
#   "torch",
#   "transformers",
# ]
# ///

"""把人工复核的修正应用到自动对齐结果，并重算终点
用法: hx-karaoke apply_fixes.py --timing timing_auto.json --fixes fixes.json --vocals vocals16k.wav --out timing.json
fixes.json: {"line,unit,mora": 起点秒, ...}；可选 "_end": {"line": 句尾终点秒}
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from ctc.align_ctc import read_wav, energy_db, finalize

ap = argparse.ArgumentParser()
ap.add_argument("--timing", required=True); ap.add_argument("--fixes", required=True)
ap.add_argument("--vocals", required=True); ap.add_argument("--out", required=True)
a = ap.parse_args()
mor = json.load(open(a.timing)); fx = json.load(open(a.fixes)) if os.path.exists(a.fixes) else {}
ends = {int(k): v for k, v in fx.pop("_end", {}).items()}
n = 0
for m in mor:
    k = f'{m["line"]},{m["unit"]},{m["mora"]}'
    if k in fx:
        m["s"] = float(fx[k]); n += 1
A = read_wav(a.vocals); DB = energy_db(A)
finalize(mor, DB, len(A) / 16000)
for m in mor:
    last = max(x["s"] for x in mor if x["line"] == m["line"])
    if m["line"] in ends and m["s"] == last:
        m["e"] = ends[m["line"]]
mm = [m for m in mor if not m.get("call")]
bad = [(x, y) for x, y in zip(mm, mm[1:]) if y["s"] <= x["s"]]
assert not bad, f"起点不单调: {bad[:3]}"
json.dump(mor, open(a.out, "w"), ensure_ascii=False, indent=0)
print(f"applied {n} fixes -> {a.out}")
