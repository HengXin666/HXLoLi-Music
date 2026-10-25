#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""KFX 自检打分: 把散在各处的设计判据算成**一张表 + 一个总分**.

产物 `proj/review/score.md`, 交给 `steps/5-verify/16-blind-review` 的盲审子代理.

## 为什么需要它

判据此前散在六份 impl 文档里 (`three-layers` / `density` / `color` / `thread` / `beat` / `bg`),
**每一步都写了判据, 但没有一处把它们算成一张总分**. 后果实测:

    门禁 6/6 通过, 用户却连提三次「特效太多了」「图形很粗糙」「尺寸这么大」

判据不汇总 = 没有判据. 这个脚本把 A~F 六组判据**机械化**, 让"好不好"先有数字.

## 用法

    hx-karaoke score_kfx.py --project proj
    hx-karaoke score_kfx.py --project proj --out proj/review/score.md --min-score 8

退出码: 总分 < `--min-score` (默认 8.0) 时为 1.

## 六组与阈值来源

| 组 | 内容 | 阈值来源 |
|---|---|---|
| A | 设计表 15 格格式 | `42-text-main/impl/design-table.md` 的正则 |
| B | 素材来源 | `check_gates.py` 的既有判据 |
| C | 密度与层次 | `impl/density.md` 的实测值 |
| D | 色彩 | `47-color` 的色相跨度判据 |
| E | 层的时间基 | `44-beat` 的重合率 / `45-bg` 的同向率 |
| F | 生成器结构 | `gen/README.md` 的分层规范 |

**改阈值必须同时改这里的注释**  阈值没有出处就变成拍脑袋.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from kfx.score.score_ass import parse_ass
from kfx.score.score_meta import check_meta
from kfx.score.score_render import check_render

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=".")
    ap.add_argument("--ass", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("--min-score", type=float, default=8.0)
    ap.add_argument("--spike", action="store_true",
                    help="段落级 spike: 只评产物自身(密度/层次/色彩/时间基), 跳过需要"
                         "design-table / elements / notes / timing 的判据. 用于验证单句效果, "
                         "不用于出片前的终审.")
    a = ap.parse_args()
    proj = a.project
    items = []

    def add(i, block, name, value, thr, ok, why=""):
        """Agent Notes
        .agents/notes/implemented/process/2026-10-03-karaoke-blind-review-gate.md
        """
        items.append(dict(id=i, block=block, name=name, value=value, thr=thr, ok=bool(ok), why=why))

    dt = check_meta(proj, add)
    # 不给 --ass 时, 取工程根下**最近修改**的 .ass。
    # 不写死文件名: 产物名是每个工程自己的事(实测踩过: 写死 `out_v5.ass` 会让
    # 其它工程悄悄评到错的文件)。
    ass = a.ass or ""
    if not ass:
        # 搜索范围含工程根与 out/  产物放 out/ 是常见做法, 只扫根目录会报
        # "未找到 out.ass" 并把每条判据都打成 FAIL(盲审 2026-10-06 实测 17/18 FAIL)。
        cands = []
        for d in (proj, os.path.join(proj, "out")):
            if os.path.isdir(d):
                cands += [os.path.join(d, f) for f in os.listdir(d) if f.endswith(".ass")]
        cands = [p for p in cands if os.path.isfile(p)]
        if cands:
            ass = max(cands, key=os.path.getmtime)
    evs, bands = ([], {})
    if ass and os.path.exists(ass):
        evs, bands = parse_ass(ass)

    check_render(proj, evs, bands, dt, add)


    # ---------------------------------------------------------------- 计分
    W = {"A": 2.0, "B": 1.0, "C": 1.5, "D": 1.5, "E": 1.0, "F": 1.0}
    if a.spike:
        # 段落级 spike 只评产物自身: C(密度与层次) 与 D(色彩) 与产物一一对应;
        # A/B/E/F 依赖 design-table / elements / notes / music-events / gen 模块,
        # 单句工程必然没有  保留它们会把"没做完整工程"误报成"产物不合格"。
        keep = {"C", "D"}
        dropped = [i for i in items if i["block"][0] not in keep]
        items = [i for i in items if i["block"][0] in keep]
        if dropped:
            print(f"[spike] 跳过 {len(dropped)} 条需要完整工程文件的判据（A/B/E/F 组）")
    tot_w = sum(W[i["block"][0]] for i in items)
    got = sum(W[i["block"][0]] for i in items if i["ok"])
    score = 10.0 * got / max(1e-6, tot_w)

    lines = ["# KFX 自检打分", "",
             f"- 工程: `{os.path.abspath(proj)}`",
             f"- 产物: `{os.path.basename(ass) if ass else '未找到 out.ass'}`",
             f"- **总分: {score:.1f} / 10**(门槛 {a.min_score})", "",
             "| # | 组 | 判据 | 实测 | 阈值 | 结果 |", "|---|---|---|---|---|---|"]
    for i in items:
        mark = "PASS" if i["ok"] else "**FAIL**"
        lines.append(f"| {i['id']} | {i['block']} | {i['name']} | {i['value']} | {i['thr']} | {mark} |")
    fails = [i for i in items if not i["ok"]]
    lines += ["", f"## 未过项 ({len(fails)})", ""]
    if fails:
        for i in fails:
            extra = f"  {i['why']}" if i["why"] else ""
            lines.append(f"- **{i['id']} {i['name']}**: 实测 {i['value']}, 需 {i['thr']}{extra}")
    else:
        lines.append("- 无")
    txt = "\n".join(lines) + "\n"
    # Agent Notes: 出片前的子代理盲审 + 判据汇总打分
    # 
    out = a.out or os.path.join(proj, "review", "score.md")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    open(out, "w", encoding="utf-8").write(txt)
    print(txt)
    print(f"-> {out}")
    return 0 if score >= a.min_score else 1


if __name__ == "__main__":
    raise SystemExit(main())


if __name__ == "__main__":
    raise SystemExit(main())
