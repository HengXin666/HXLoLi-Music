#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "fonttools", "pillow"]
# ///
"""矢量件母题压字门禁的标定 (硬规则 10b): 在一批真实成品上量分布, 再定 FAIL / WARN 的分界.

量什么: 每份成品里 "画在字上面且离字 < MOTIF_GAP" 的矢量件 (front), 和标了 Effect=over 的豁免件,
各自的 尺寸 ext (px) / 峰值不透明度 op / 在屏时长 dur (s). 正例 (用户验收过的成品) 不许被判 FAIL,
反例 (用 --negative 给, 或 tests 里构造的大件压字) 必须被判 FAIL.
用法:
  hx-karaoke qa/calib_vector_gap.py --fontsdir fonts --json calib.json a.ass b.ass ...
输出: 每份一行分位数 + 汇总; --json 写全部记录 (只写进工程或临时目录, 不进 skill, 硬规则 11).
"""
import argparse, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from assfx.draw import motif_gap as MG                       # noqa: E402
from qa.validate_ass import load_ass                          # noqa: E402


def over_stats(events, styles):
    """Effect=over 件的 ext / op / dur (与 check_vectors 同一套量法)."""
    out = []
    for ev in events:
        if (ev.get("Effect") or "").strip() != MG.VEC_OVER or not MG._R_DRAW.search(ev["Text"]):
            continue
        trk = MG.track(ev["Text"], (ev["e"] - ev["s"]) * 1000)
        if not trk:
            continue
        stl = styles.get(ev["Style"], {})
        px, py, pad, _, info = MG.vector_points(ev["Text"], trk[2], trk[3], stl, styles, 4.0)
        if not len(px):
            continue
        tags = "".join(re.findall(r"\{([^}]*)\}", ev["Text"]))
        out.append(dict(ext=float(max(px.max() - px.min(), py.max() - py.min())), op=MG._peak_opacity(tags, stl, info),
                        dur=ev["e"] - ev["s"], layer=int(ev["Layer"])))
    return out


def pct(v, qs=(50, 90, 99, 100)):
    if not v:
        return "-"
    v = sorted(v)
    return "/".join("%.2f" % v[min(len(v) - 1, int(round(q / 100 * (len(v) - 1))))] for q in qs)


# Agent Notes: 组合式生成: 设计中间表示 + 形状来源 + 母题来源门禁 + 跨作品指纹
# 
def main():
    """Agent Notes
    .agents/notes/implemented/architecture/2026-11-17-karaoke-compositional-generator.md
    """
    ap = argparse.ArgumentParser()
    ap.add_argument("ass", nargs="+")
    ap.add_argument("--fontsdir")
    ap.add_argument("--json")
    a = ap.parse_args()
    allrec = {}
    for p in a.ass:
        _, styles, events, _ = load_ass(p)
        errs, warns, _ = MG.check_ass(events, styles, p, a.fontsdir)
        st = dict(MG.VEC_STATS)
        fr = st.get("front", []); bh = st.get("behind", [])
        ov = over_stats(events, styles)
        rec = dict(front=fr, behind=[{k: r[k] for k in ("ext", "op", "dur", "gap", "layer", "cov")} for r in bh], over=ov,
                   n_err=len(errs))
        allrec[os.path.basename(p)] = rec
        print("%s\n  front<8px %d  ext %s  op %s  dur %s\n  behind<8px %d  cov %s\n  over %d  ext %s  op %s  dur %s"
              % (os.path.basename(p), len(fr), pct([r["ext"] for r in fr]), pct([r["op"] for r in fr]), pct([r["dur"] for r in fr]),
                 len(bh), pct([r["cov"] for r in bh]), len(ov), pct([r["ext"] for r in ov]), pct([r["op"] for r in ov]),
                 pct([r["dur"] for r in ov])), flush=True)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(allrec, fh, ensure_ascii=False, indent=1, default=float)


if __name__ == "__main__":
    main()
