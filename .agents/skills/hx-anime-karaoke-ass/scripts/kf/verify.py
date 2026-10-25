# -*- coding: utf-8 -*-
"""`verify` 阶段: 把 kf 融合稿与人工终稿逐音拍对比, 列出偏差最大的那些."""


import os
import statistics
import sys

from kf.align import load_json


def cmd_verify(a):
    A = load_json(a.a if os.path.isabs(a.a) else os.path.join(a.project, a.a))
    B = load_json(a.b if os.path.isabs(a.b) else os.path.join(a.project, a.b))
    ka = {(m["line"], m["unit"], m["mora"]): m["s"] for m in A}
    kb = {(m["line"], m["unit"], m["mora"]): m["s"] for m in B}
    common = set(ka) & set(kb)
    if not common:
        sys.exit("[verify] 两份时间轴没有共同的 (line,unit,mora) 键，无法比较。")
    dif = sorted(((abs(ka[k] - kb[k]), k) for k in common), reverse=True)
    vals = [d for d, _ in dif]
    print("[verify] %s vs %s" % (a.a, a.b))
    print("[verify] 共同音拍 %d / %d vs %d" % (len(common), len(ka), len(kb)))
    print("[verify] 差: 中位 %.3f s  均值 %.3f s  90分位 %.3f s  最大 %.3f s"
          % (statistics.median(vals), sum(vals) / len(vals),
             sorted(vals)[int(len(vals) * 0.9)], vals[0]))
    over = [x for x in dif if x[0] > a.thr]
    print("[verify] 超过 %.2fs 的 %d 个（占 %.1f%%）" % (a.thr, len(over), 100 * len(over) / len(common)))
    print("\n最差 %d 个：" % a.top)
    for d, (li, ui, mi) in dif[:a.top]:
        print("   line %2d unit %2d mora %d    %8.3f vs %8.3f    %+.3f"
              % (li, ui, mi, ka[(li, ui, mi)], kb[(li, ui, mi)], ka[(li, ui, mi)] - kb[(li, ui, mi)]))
    return 0
