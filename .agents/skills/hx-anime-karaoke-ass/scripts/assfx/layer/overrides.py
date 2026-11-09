# -*- coding: utf-8 -*-
"""参数层: 预览台写的 overrides.json 经环境变量 ASSFX_OVERRIDES 喂给生成器.

文件格式 (预览台 spec.py 写, 这里只读):
  {"format": "assfx-overrides", "version": 1,
   "units": {"<单元key>": {"params": {"theme": "SUN", "din": 0.7, "salt": 3, ...}, ...}}}
只认 params; pin / note / fp 等是预览台自己的记账, 生成器不看.

非法值直接报错退出, 不静默忽略: 静默忽略会让"改了但没生效"变成看不见的问题.
"""
import copy
import json
import os

from assfx.layer import manifest as M

ENV = "ASSFX_OVERRIDES"
KAR_DEFAULTS = dict(ent="slide", ext="wind", hl="wipe", din=0.5, dout=0.6)


def load(path=None):
    """{key: params}. 没设环境变量或文件不存在时返回空表 (= 生成器原样输出)."""
    path = path or os.environ.get(ENV)
    if not path or not os.path.exists(path):
        return {}
    d = json.load(open(path, encoding="utf-8"))
    if d.get("format") != "assfx-overrides" or d.get("version") != 1:
        raise SystemExit("%s: 不是 assfx-overrides v1" % path)
    return {k: dict(v.get("params") or {}) for k, v in (d.get("units") or {}).items() if v.get("params")}


def _fields(schema, recipe, recipes):
    out = {f["key"]: f for f in schema}
    if recipe and recipe in recipes:
        out.update({k["key"]: k for k in recipes[recipe].get("knobs", [])})
    return out


def check(key, params, schema, recipe=None, pools=None):
    """按 schema 查类型与范围. 返回 None 或报错文字.
    pools: {themes/motions/recipes/families: {名: ...}}; 缺省取本进程的 REG (生成器侧).
    预览台侧传清单里的 presets, 于是两边用同一套规则."""
    if pools is None:
        pools = dict(themes=M.REG.themes, motions=M.REG.motions, recipes=M.REG.recipes, families=M.REG.families)
    fs = _fields(schema, params.get("fx", recipe), pools.get("recipes", {}))
    for k, v in params.items():
        f = fs.get(k)
        if f is None:
            return "%s: 未知参数 %s" % (key, k)
        t = f["type"]
        if t in ("slider", "number", "int"):
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                return "%s.%s: 要数字, 得到 %r" % (key, k, v)
            if ("min" in f and v < f["min"]) or ("max" in f and v > f["max"]):
                return "%s.%s=%s 超出 [%s, %s]" % (key, k, v, f.get("min"), f.get("max"))
        elif t == "select" and v not in f["options"]:
            return "%s.%s=%r 不在 %s" % (key, k, v, f["options"])
        elif t == "color" and not M.HEX.match(str(v)):
            return "%s.%s=%r 不是 #RRGGBB" % (key, k, v)
        elif t == "boolean" and not isinstance(v, bool):
            return "%s.%s 要 true/false" % (key, k)
        elif t == "preset":
            pool = pools.get(f["source"], {})
            if v not in pool:
                return "%s.%s=%r 不是已登记的%s (有: %s)" % (key, k, v, f["source"], ", ".join(sorted(pool)) or "无")
    return None


def need(key, params, schema, recipe=None):
    err = check(key, params, schema, recipe)
    if err:
        raise SystemExit("overrides 非法: " + err)


def knobs_of(params, recipe=None):
    """FX 用的旋钮表: 统一三项 + 配方专属项 (缺省取 schema 默认)."""
    out = {f["key"]: f["default"] for f in M.FX_KNOBS}
    if recipe and recipe in M.REG.recipes:
        out.update({k["key"]: k["default"] for k in M.REG.recipes[recipe].get("knobs", [])})
    out.update({k: v for k, v in params.items() if k in out})
    return out


def phrase_defaults(P, lead):
    """一句在没有任何覆盖时的有效参数 (报给清单, 页面据此标"已改")."""
    o = dict(KAR_DEFAULTS, **{k: v for k, v in (P.get("o") or {}).items() if k in KAR_DEFAULTS})
    th = P.get("th") or {}
    d = dict(theme=M.theme_name(th) or "", motion="", fx=P.get("fx") or "",
             lead=P.get("lead", lead), hold=P.get("hold", 0.25), salt=0)
    d.update({"th." + k: str(th[k]).upper() for k in ("hi", "glow", "dark") if k in th})
    d.update({k: o[k] for k in ("ent", "ext", "hl", "din", "dout")})
    d.update(knobs_of({}, d["fx"]))
    return d


def merge_phrase(P, params):
    """把覆盖值合进一份 PHRASES 项的拷贝. 顺序: 预设在前, 单项在后 (单项能改预设里的某一格)."""
    if not params:
        return P
    P2 = dict(P)
    P2["o"] = dict(P.get("o") or {})
    P2["th"] = dict(P.get("th") or {})
    if params.get("theme"):
        th = {k: v for k, v in M.REG.themes[params["theme"]].items() if k != "why"}
        P2["th"].update(th)
    for k in ("hi", "glow", "dark"):
        if "th." + k in params:
            P2["th"][k] = params["th." + k]
    if params.get("motion"):
        P2["o"].update({k: v for k, v in M.REG.motions[params["motion"]].items() if k != "why"})
    for k in ("ent", "ext", "hl", "din", "dout"):
        if k in params:
            P2["o"][k] = params[k]
    for k in ("fx", "lead", "hold"):
        if k in params:
            P2[k] = params[k]
    P2["knobs"] = knobs_of(params, P2.get("fx"))
    return P2


def effective(defaults, params):
    """报给清单的有效参数: 预设展开后的值 (选了动作预设, ent/ext/hl 显示预设里的值), 单项覆盖最后叠."""
    eff = dict(defaults)
    if params.get("theme") in M.REG.themes:
        eff.update({"th." + k: v for k, v in M.REG.themes[params["theme"]].items() if k in ("hi", "glow", "dark")})
    if params.get("motion") in M.REG.motions:
        eff.update({k: v for k, v in M.REG.motions[params["motion"]].items() if k != "why"})
    eff.update(params)
    return eff


def merge_flat(defaults, params):
    """段/卡片: 默认值上叠覆盖值."""
    out = copy.deepcopy(defaults)
    out.update(params or {})
    return out
