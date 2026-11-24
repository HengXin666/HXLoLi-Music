# -*- coding: utf-8 -*-
"""设计中间表示 (design IR): 把 "这首歌的设计语言" 写成数据, 生成器按它组合原语, 不再每句手写一次性函数.

一份工程一个 design.ir.json. 结构 (字段全集, 未列出的键报错, 防止拼错静默失效):
{
  "format": "assfx-ir", "version": 1, "song": "曲名",
  "motifs": {                       # 设计语言的词汇表: 这首歌只用这些母题
    "<id>": {"shape": "kit:snowflake | glyph:<字体>:<字> | svg:<文件> | prop:<名>",   # draw/resolve.py
             "role": "main | aux",  # 主母题 / 辅助母题; 一句最多一个主母题 (known-gaps #14)
             "grammar": "halo | orbit | rise | fall | scatter | trail | frame | stamp",    # grammar.py 的组合法
             "color": "glow | base | pale | dark | hi | #RRGGBB", "size": 28, "why": "出处 (元素表 / 镜头 / 词义)"}
  },
  "phrases": [{
    "i": 0, "lines": [0], "label": "画面时间点: 内容",
    "role": "carrier | high | rest",            # 承载 / 高光 / 留白 (高光强度最高, 留白低但不断)
    "main": "<motif id> | null",                # rest 句可以为 null, 其余必须有
    "aux": ["<motif id>", ...],
    "clock": "voice | beat | shot",             # 主母题跟谁走: 人声音拍 / 伴奏卡点 / 镜头 (五层时钟分开, 见 steps/4-kfx/index.md)
    "color": {"hue": 200, "sat": 0.5},          # 本句色相 (47-color); 或 "theme": "<主题名>"
    "relation": "carry | contrast | echo | cut | rest | none",   # 与上一句的关系 (48-thread)
    "text": {"ent": "fade", "ext": "wind", "hl": "wipe", "din": 0.8, "dout": 1.0},   # 字层预设 (42-text-main)
    "params": {"n": 6, "size": 1.0},            # 组合法旋钮 (覆盖母题默认)
    "escape": "fx_high:fx_thaw_bloom"           # 逃生口: 这句写专属函数 (module:function), 组合法不够用时用
  }]
}
"""
import json
import os

ROLES = ("carrier", "high", "rest")
CLOCKS = ("voice", "beat", "shot")
RELATIONS = ("carry", "contrast", "echo", "cut", "rest", "none")
GRAMMARS = ("halo", "orbit", "rise", "fall", "scatter", "trail", "frame", "stamp")
COLORS = ("glow", "base", "pale", "dark", "hi")
TOP_KEYS = {"format", "version", "song", "motifs", "phrases", "doc"}
MOTIF_KEYS = {"shape", "role", "grammar", "color", "size", "why"}
PHRASE_KEYS = {"i", "lines", "label", "role", "main", "aux", "clock", "color", "theme", "relation", "text", "params", "escape", "bed"}


def load(path):
    with open(path, encoding="utf-8") as fh:
        ir = json.load(fh)
    errs = validate(ir)
    if errs:
        raise ValueError("设计中间表示 %s 不合格:\n  " % os.path.basename(path) + "\n  ".join(errs))
    return ir


def _color_ok(c):
    return c in COLORS or (isinstance(c, str) and len(c) == 7 and c.startswith("#"))


def validate(ir):
    """返回错误列表 (空 = 合格). 只查结构与引用, 不查审美."""
    e = []
    if ir.get("format") != "assfx-ir" or ir.get("version") != 1:
        e.append("format/version 必须是 assfx-ir / 1")
    e += ["顶层多余键 %s" % k for k in sorted(set(ir) - TOP_KEYS)]
    motifs = ir.get("motifs") or {}
    for mid, m in sorted(motifs.items()):
        e += ["母题 %s 多余键 %s" % (mid, k) for k in sorted(set(m) - MOTIF_KEYS)]
        if not str(m.get("shape", "")).partition(":")[0] in ("kit", "glyph", "svg", "prop"):
            e.append("母题 %s 的 shape 缺来源前缀 (kit/glyph/svg/prop)" % mid)
        if m.get("role") not in ("main", "aux"):
            e.append("母题 %s 的 role 只能是 main / aux" % mid)
        if m.get("grammar") not in GRAMMARS:
            e.append("母题 %s 的 grammar %r 不在 %s" % (mid, m.get("grammar"), "/".join(GRAMMARS)))
        if "color" in m and not _color_ok(m["color"]):
            e.append("母题 %s 的 color %r 不认识" % (mid, m["color"]))
    seen = set()
    for n, p in enumerate(ir.get("phrases") or []):
        tag = "第 %d 项 (i=%s)" % (n, p.get("i"))
        e += ["%s 多余键 %s" % (tag, k) for k in sorted(set(p) - PHRASE_KEYS)]
        if p.get("i") in seen:
            e.append("%s 句号重复" % tag)
        seen.add(p.get("i"))
        if p.get("role") not in ROLES:
            e.append("%s role 只能是 %s" % (tag, "/".join(ROLES)))
        mn = p.get("main")
        if mn is None and p.get("role") != "rest":
            e.append("%s 不是留白句却没有主母题" % tag)
        if mn is not None and (mn not in motifs or motifs[mn].get("role") != "main"):
            e.append("%s 的主母题 %r 不在词汇表或不是 main" % (tag, mn))
        for a in p.get("aux") or []:
            if a not in motifs:
                e.append("%s 的辅助母题 %r 不在词汇表" % (tag, a))
            elif motifs[a].get("role") == "main":
                e.append("%s 把主母题 %r 当辅助母题挂上 (一句两套主母题, known-gaps #14)" % (tag, a))
        if p.get("clock", "voice") not in CLOCKS:
            e.append("%s clock 只能是 %s" % (tag, "/".join(CLOCKS)))
        if p.get("relation", "none") not in RELATIONS:
            e.append("%s relation 只能是 %s" % (tag, "/".join(RELATIONS)))
        esc = p.get("escape")
        if esc is not None and (not isinstance(esc, str) or esc.count(":") != 1):
            e.append("%s escape 写成 module:function" % tag)
    return e


def vocabulary(ir):
    """设计语言统计 (报数用): 每个母题被多少句当主母题 / 辅助母题, 逃生口句数."""
    use = {m: [0, 0] for m in ir.get("motifs", {})}
    esc = 0
    for p in ir.get("phrases", []):
        if p.get("main") in use:
            use[p["main"]][0] += 1
        for a in p.get("aux") or []:
            if a in use:
                use[a][1] += 1
        esc += bool(p.get("escape"))
    return use, esc
