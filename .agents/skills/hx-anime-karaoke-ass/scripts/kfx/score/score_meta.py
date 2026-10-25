# -*- coding: utf-8 -*-
"""A/B 两组判据: 设计表 15 格格式 + 素材来源.

两组的输入都是**工程文件**(design-table.md / anime.elements.md / anime.notes.md),
不需要读 ass, 所以与 C~F(要读事件)分开.
"""
import os
import re

from kfx.score.score_ass import design_table


def check_meta(proj, add):
    """写入 A/B 两组判据; 返回 design_table 的结果供 C~F 复用(可能为 None)."""
    dt, err = design_table(proj)
    NEED = ["主·出现", "主·逐字", "主·词组", "主·意象", "主·消失",
            "副·出现", "副·逐字", "副·消失",
            "背景·场景", "背景·情绪", "背景·番剧", "承上", "启下"]
    if dt is None:
        for i, n in enumerate(["15 列齐全", "无空串", "主·逐字 取值", "副·出现 取值",
                               "副·逐字 填写率", "承上/启下 同名率", "背景·场景 填写率"]):
            add(f"A{i+1}", "A 设计表", n, err, "见 design-table.md", False, err)
    else:
        cols, rows = dt
        add("A1", "A 设计表", "15 列齐全", f"{len(cols)} 列", "含 13 个阶段列", all(c in cols for c in NEED))
        blanks = sum(1 for r in rows if any(c == "" for c in r))
        add("A2", "A 设计表", "无空串行", f"{blanks}/{len(rows)} 行有空串", "0 行", blanks == 0,
            "空串=忘了做, `—`=决定不做")
        for key, iid, need in (("主·逐字", "A3", 3), ("副·出现", "A4", 3)):
            ci = cols.index(key) if key in cols else -1
            vals = {r[ci] for r in rows if r[ci] not in ("—", "")} if ci >= 0 else set()
            add(iid, "A 设计表", f"{key} 取值种类", f"{len(vals)} 种", f">={need} 种", len(vals) >= need,
                "全曲同值 = 从没设计过")
        ci = cols.index("副·逐字") if "副·逐字" in cols else -1
        f = sum(1 for r in rows if ci >= 0 and r[ci] not in ("—", "")) / max(1, len(rows))
        add("A5", "A 设计表", "副·逐字 填写率", f"{f:.0%}", ">=50%", f >= 0.5)
        ci1 = cols.index("启下") if "启下" in cols else -1
        ci2 = cols.index("承上") if "承上" in cols else -1
        carry = 0
        if ci1 >= 0 and ci2 >= 0:
            for r1, r2 in zip(rows, rows[1:]):
                w1 = set(re.findall(r"[\u4e00-\u9fffA-Za-z_]+", r1[ci1]))
                w2 = set(re.findall(r"[\u4e00-\u9fffA-Za-z_]+", r2[ci2]))
                if w1 & w2:
                    carry += 1
        cr = carry / max(1, len(rows) - 1)
        add("A6", "A 设计表", "承上/启下 同名率", f"{cr:.0%}", ">=60%", cr >= 0.6,
            "句间承接必须传可指认的变量")
        ci = cols.index("背景·场景") if "背景·场景" in cols else -1
        sc = sum(1 for r in rows if ci >= 0 and r[ci] not in ("—", "")) / max(1, len(rows))
        add("A7", "A 设计表", "背景·场景 填写率", f"{sc:.0%}", ">=70%", sc >= 0.7)

    # ---------------------------------------------------------------- B 素材来源
    ep = os.path.join(proj, "anime.elements.md")
    if os.path.exists(ep):
        et = open(ep, encoding="utf-8").read()
        n_el = len(re.findall(r"\|\s*\*\*[^|]+\*\*\s*\|\s*(\d+)\s*\|", et))
        add("B1", "B 素材", "元素表带计数条目", f"{n_el} 条", ">=4 条", n_el >= 4)
    else:
        add("B1", "B 素材", "元素表带计数条目", "缺文件", ">=4 条", False)
    if dt:
        cols, rows = dt
        amb = sum(1 for r in rows if "氛围句" in " ".join(r))
        add("B2", "B 素材", "氛围句占比", f"{amb}/{len(rows)}", "<=35%", amb / max(1, len(rows)) <= 0.35)
    else:
        add("B2", "B 素材", "氛围句占比", "无法评", "<=35%", False)
    np_ = os.path.join(proj, "anime.notes.md")
    if os.path.exists(np_):
        nt = open(np_, encoding="utf-8").read()
        add("B3", "B 素材", "anime.notes.md", f"{len(nt.strip())} 字",
            ">=500 字且含内核/原作关系/出处",
            len(nt.strip()) >= 500 and bool(re.search(r"内核|主題|主题", nt))
            and bool(re.search(r"与原作|改编", nt)) and bool(re.search(r"来源|出处|http", nt)))
    else:
        add("B3", "B 素材", "anime.notes.md", "缺文件", ">=500 字", False)
    return dt
