# -*- coding: utf-8 -*-
"""G2 (agent 改代码版, plan 2.3): 改前预测影响集, 改后三条硬核对.

基准 = accept.py begin 时存下的 raw + 清单 + 工程 .py (review/accept/base/).
预测 (不跑生成器, 只读源码):
  1. 清单 code.fns 里每个函数, 按当前源码重算哈希 (trace.source_hashes). 不同 = 改了.
  2. 影响集 = deps.code 含改动函数的单元
             + entry 函数改了: 它名下的单元; 名下没有单元就是全部
             + 单元数据常量 (如 PHRASES) 改了: 列表字面量逐项比, 改了第 i 项就是第 i 个句单元; 长度变了就是全部句单元
             + 以上句单元的 deps.window (出入场规划牵动下一句)
核对 (重跑生成器之后), 三条都是硬条件:
  A. "好" 的状态不许是 touched (goods.py). 不能被声明豁免.
  B. 实际变了的单元 <= 问题范围 + 已声明的全局影响集.
  C. 实际变了的单元 <= 预测影响集 + 输入变了的单元. 否则是追踪漏了依赖: 报错, 修追踪, 不许放行.
"""
import ast
import os

from accept import sel as S
from assfx.layer.trace import source_hashes
from assdoc import spec as SP


def changed_fns(man, proj):
    code = man.get("code") or {}
    fns = code.get("fns") or {}
    now = source_hashes(proj, list(fns), code.get("data_names"))
    return sorted(k for k, v in fns.items() if now.get(k) != v.get("h"))


def _list_items(src_dir, rel, name):
    """模块里 name = [...] 的各项 AST dump; 不是列表字面量返回 None."""
    p = os.path.join(src_dir, rel)
    if not os.path.exists(p):
        return None
    for st in ast.parse(open(p, encoding="utf-8").read()).body:
        if isinstance(st, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in st.targets):
            return [ast.dump(e) for e in st.value.elts] if isinstance(st.value, ast.List) else None
    return None


def data_changes(man, base_src, proj):
    """单元数据常量改了哪些句单元. 返回 (单元集合, 说明列表)."""
    phr = [u["key"] for u in man.get("units", []) if u["kind"] == "phrase"]
    out, why = set(), []
    for rel, names in ((man.get("code") or {}).get("data_names") or {}).items():
        for nm in names:
            a, b = _list_items(base_src, rel, nm), _list_items(proj, rel, nm)
            if a == b:
                continue
            if a is None or b is None or len(a) != len(b) or len(a) != len(phr):
                out |= set(phr)
                why.append("%s:%s 结构或长度变了, 按全部句单元算" % (rel, nm))
                continue
            idx = [i for i in range(len(a)) if a[i] != b[i]]
            out |= {phr[i] for i in idx}
            why.append("%s:%s 第 %s 项变了" % (rel, nm, ",".join(map(str, idx))))
    return out, why


def predict(man, base_src, proj):
    """返回 dict(fns, units, why). units 已含 window 牵动."""
    us = S.units(man)
    fns = changed_fns(man, proj)
    code = man.get("code") or {}
    units, why = set(), []
    for k in fns:
        dep = {u for u, x in us.items() if k in (x.get("deps") or {}).get("code", [])}
        if k in (code.get("entry") or {}):
            under = set(code["entry"][k])
            dep |= under or set(us)
            why.append("%s 是 entry 函数, 影响%s" % (k, "它名下的 %d 个单元" % len(under) if under else "全部单元"))
        if not dep:
            why.append("%s 改了, 但没有单元依赖它" % k)
        units |= dep
    du, dw = data_changes(man, base_src, proj)
    units |= du
    why += dw
    for k in list(units):
        units |= set(((us.get(k) or {}).get("deps") or {}).get("window") or [])
    return dict(fns=fns, units=sorted(units, key=str), why=why)


def actual(old_doc, old_man, new_doc, new_man):
    """实际变了的单元 (含新增/消失的单元, None = 不归任何单元的事件), 以及输入变了的单元."""
    ch = set(SP.changed_units(old_doc, new_doc, new_man))
    a, b = S.units(old_man), S.units(new_man)
    ch |= set(a) ^ set(b)
    inp = {k for k in set(a) & set(b) if a[k].get("fp") != b[k].get("fp")}
    return ch, inp


def verify(old_doc, old_man, new_doc, new_man, pred, scope, declared, goods):
    """返回 (失败列表, 报告 dict). 失败列表为空才放行."""
    ch, inp = actual(old_doc, old_man, new_doc, new_man)
    st = goods.status(new_doc, new_man)
    fail = []
    touched = {g: m for g, (s, m) in st.items() if s == "touched"}
    if touched:
        fail.append("A 碰到了 \"好\": %s. 只能分叉或撤回, 除非用户先撤掉 \"好\"" %
                    "; ".join("%s %s" % kv for kv in touched.items()))
    over = ch - set(scope) - set(declared)
    if over:
        fail.append("B 越出问题范围: %s. 要么分叉共用函数, 要么 --declare 声明并写理由" %
                    ", ".join(map(SP.label, sorted(over, key=str))))
    leak = ch - set(pred["units"]) - inp
    if leak:
        fail.append("C 追踪漏了依赖: %s 变了但不在预测里. 修追踪 (用 G.scope 包住, 或把隐式状态改成参数), 不许放行" %
                    ", ".join(map(SP.label, sorted(leak, key=str))))
    rep = dict(changed=sorted(ch, key=str), inputs=sorted(inp), predicted=pred["units"], scope=list(scope),
               declared=list(declared), goods={g: s for g, (s, m) in st.items()})
    return fail, rep
