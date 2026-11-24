# -*- coding: utf-8 -*-
"""母题来源记录: 每句实际发射了哪些主母题 (known-gaps #14 "一句两套主母题" 的代码侧查法).

为什么用运行期记录而不是读代码: 主母题可能藏在转调里 (fx_high.fx_sword_cut 里又调 fx_main.p29),
静态读函数名会漏. 这里在生成时按单元 key 记下"谁以主母题身份发过事件", 生成后写 <out>.motifs.json,
门禁 gate/check_motif_mono.py 读它. 不改 ASS 输出 (字节不变).

用法 (逃生口函数里, 或工程自己的 pNN 函数):
    from assfx.layer.provenance import main_motif
    @main_motif("chain")
    def p29(f, ph, k): ...
组合器自己发的主母题由 compose.py 记, 不用装饰.
"""
import functools
import json
import os

LOG = {}            # 单元 key -> {"main": [母题 id 按首次出现序], "aux": [...], "src": {id: 函数限定名}}
_CUR = [None]


def begin(key):
    _CUR[0] = key
    LOG.setdefault(key, {"main": [], "aux": [], "src": {}})


def end():
    _CUR[0] = None


def note(motif, role="main", src=None):
    key = _CUR[0]
    if key is None:
        return
    rec = LOG.setdefault(key, {"main": [], "aux": [], "src": {}})
    lst = rec["main" if role == "main" else "aux"]
    if motif not in lst:
        lst.append(motif)
    if src and motif not in rec["src"]:
        rec["src"][motif] = src


def main_motif(motif, role="main"):
    """装饰器: 被装饰函数每次被调用, 就在当前单元记一次该母题 (role=main/aux)."""
    def deco(fn):
        @functools.wraps(fn)
        def run(*a, **kw):
            note(motif, role, "%s.%s" % (fn.__module__, fn.__qualname__))
            return fn(*a, **kw)
        return run
    return deco


def write(out_ass, units=None, ir_path=None):
    """生成后写 <out>.motifs.json. units: [(key, 句号 i, IR 声明的主母题)] 由组合器给, 门禁据此对照声明与实际."""
    side = os.path.splitext(out_ass)[0] + ".motifs.json"
    doc = {"format": "assfx-motifs", "version": 1, "ir": ir_path and os.path.basename(ir_path), "units": []}
    for key, i, declared in units or [(k, None, None) for k in LOG]:
        rec = LOG.get(key, {"main": [], "aux": [], "src": {}})
        doc["units"].append({"key": key, "i": i, "declared": declared, **rec})
    with open(side, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1, sort_keys=True)
    return side
