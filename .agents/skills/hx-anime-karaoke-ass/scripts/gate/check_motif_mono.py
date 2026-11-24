#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""门禁: 一句只许一套主母题 (known-gaps #14), 并核对设计中间表示与生成结果一致.

读生成器写的 <out>.motifs.json (assfx/layer/provenance.py; 组合器 Composer.finish() 写):
  FAIL  一句里有两个以上不同的主母题在发射 (典型: 换主母题时旧高光函数没删, 新的又挂在后面)
  FAIL  实际发射的主母题与 design.ir.json 声明的不同
  FAIL  设计中间表示本身不合格 (assfx/layer/ir.py validate)
  WARN  非留白句没有记到任何主母题 (逃生口函数没声明来源, 门禁看不见它画了什么)
  WARN  具象素材没写可读下限 (assets/motif.json 的 kind=figurative 缺 min_px; draw/sources/legible.py)
为什么 FAIL 不需要先标阈值 (10b): 这是计数等式 (主母题数 == 1, 实际 == 声明), 不是量出来的连续量;
正例 (オンリー 定稿 33 句) 0 条 FAIL, 反例 (tests 里按 2026-11-12 p29 剑 + 链重建) 报出, 记录见 shared/calibration.md.
用法:
  hx-karaoke gate/check_motif_mono.py proj/out.ass [--ir proj/design.ir.json] [--motif-cfg proj/assets/motif.json]
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OK, BAD, WARN = "PASS", "FAIL", "WARN"


# Agent Notes: 组合式生成: 设计中间表示 + 形状来源 + 母题来源门禁 + 跨作品指纹
# 
def check(motifs_doc, ir=None, motif_cfg=None):
    """Agent Notes
    .agents/notes/implemented/architecture/2026-11-17-karaoke-compositional-generator.md
    返回 [(级别, 单元, 说明)]."""
    from assfx.layer import ir as IR
    from assfx.draw.legible import audit
    res = []
    roles = {}
    if ir is not None:
        for e in IR.validate(ir):
            res.append((BAD, "ir", e))
        roles = {p["i"]: p.get("role") for p in ir.get("phrases", [])}
    for u in motifs_doc.get("units", []):
        tag = "L%02d" % u["i"] if u.get("i") is not None else u["key"]
        mains = [m for m in u.get("main", []) if not m.startswith("echo:")]
        if len(mains) > 1:
            src = "; ".join("%s <- %s" % (m, u.get("src", {}).get(m, "?")) for m in mains)
            res.append((BAD, tag, "一句 %d 套主母题并存: %s (删掉旧的那套, 或把其中一个降为辅助母题 role=aux)" % (len(mains), src)))
        dec = u.get("declared")
        if dec and mains and dec not in mains:
            res.append((BAD, tag, "设计声明主母题 %s, 实际发射的是 %s (改设计或改代码, 两边要一致)" % (dec, "/".join(mains))))
        if not mains and roles.get(u.get("i")) not in (None, "rest") and dec is None:
            res.append((WARN, tag, "非留白句没有记到主母题 (逃生口函数用 @main_motif 声明来源)"))
    for lv, slot, why in audit((motif_cfg or {}).get("slots")):
        res.append((WARN, "slot:" + slot, why))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ass")
    ap.add_argument("--ir")
    ap.add_argument("--motif-cfg")
    a = ap.parse_args()
    side = os.path.splitext(a.ass)[0] + ".motifs.json"
    if not os.path.exists(side):
        print("%s motifs.json 缺失 %s: 生成器没接组合器 (Composer.finish) 或没写来源旁证, 主母题无法核对" % (BAD, side))
        return 1
    doc = json.load(open(side, encoding="utf-8"))
    irp = a.ir or (doc.get("ir") and os.path.join(os.path.dirname(os.path.abspath(a.ass)), doc["ir"]))
    ir = json.load(open(irp, encoding="utf-8")) if irp and os.path.exists(irp) else None
    cfg = json.load(open(a.motif_cfg, encoding="utf-8")) if a.motif_cfg and os.path.exists(a.motif_cfg) else None
    res = check(doc, ir, cfg)
    for st, unit, why in res:
        print("%-4s %-8s %s" % (st, unit, why))
    bad = [r for r in res if r[0] == BAD]
    print("%s: %d 单元, %d 失败, %d 警告%s" % ("FAILED" if bad else "PASSED", len(doc.get("units", [])), len(bad),
                                         len([r for r in res if r[0] == WARN]), "" if ir is not None else " (没找到 design.ir.json, 只查了实际发射)"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
