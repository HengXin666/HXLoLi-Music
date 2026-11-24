# -*- coding: utf-8 -*-
"""单元清单: 生成器自己声明有哪些单元, 每个单元有哪些参数, 每个参数怎么调.

为什么要它: 预览台不该从事件 Name 去猜"这是什么". 生成器最清楚.
生成器在 ASS 旁边写 <out>.manifest.json; 预览台读它, 改参数, 再经 ASSFX_OVERRIDES 喂回生成器
(见 overrides.py). 思路同 video-shotcraft 的 workbench.ts 清单: 一份事实源, 按 schema 编辑.

只开放内容级参数. 节奏命门不开放: 逐字错落曲线, \\t 加速度, 退场向量的随机区间, pop 比例,
band 尺寸, 位置 (铁律 6b).

生成器里这样用 (Generator 已代办大部分):
    from assfx.layer.manifest import REG, recipe, register_theme
    register_theme("SKY", TH_SKY, why="sky shots")
    @recipe("rain", why="light falls on sung chars", knobs=[knob("drops", 2, 0, 6, 1, "drops per char")])
    def fx_rain(f, ph, k): n = f.opt("drops", 2) ...
"""
import hashlib
import json
import os
import re

from assfx.layer.trace import TR

FORMAT, VERSION = "assfx-manifest", 1

ENT_OPTS = ["slide", "rise", "drop", "zoom", "flip", "flipx", "spin", "fade", "glitch"]
EXT_OPTS = ["wind", "rise", "sink", "scatter", "zoom", "flip", "flipx", "fade"]
HL_OPTS = ["wipe", "pulse", "bloom", "flipx", "shake", "ink", "jump", "none"]


def field(key, typ, label, group, why, **kw):
    """一条 schema. group: design | window | random | knob. why 显示在页面上."""
    d = dict(key=key, type=typ, label=label, group=group, why=why)
    d.update(kw)
    return d


def knob(key, default, lo, hi, step, why, label=None):
    return field(key, "slider", label or key, "knob", why, default=default, min=lo, max=hi, step=step)


# FX 统一旋钮: 在 FX 发射器内部生效. 但只对用到对应发射器的配方有意义:
# density 只作用于 burst/drift (发射粒子), size/alpha 只作用于 shape (画图形).
# FX 运行时记下用到了哪些 (FX._use), 清单按单元写成 knobs_used, 预览台面板只显示这些, 服务端拒收无效旋钮.
FX_KNOBS = [
    field("density", "slider", "密度", "knob", "粒子/碎片个数倍率. 解决太满抢画面或太空等于没有",
          default=1.0, min=0.3, max=2.0, step=0.05),
    field("size", "slider", "尺寸", "knob", "图形尺寸倍率, 仍受 band 夹取",
          default=1.0, min=0.5, max=1.5, step=0.05),
    field("alpha", "slider", "透明度", "knob", "特效透明度偏移, 正数更淡. 用于亮画面",
          default=0, min=-60, max=60, step=5),
]

SALT = field("salt", "int", "随机签", "random", "只重抽本单元的随机, 别的单元不变",
             default=0, min=0, max=9999)

# window 组参数会牵动相邻句的出入场 (见 Generator.plan), deps 列出允许跟着变的单元
PHRASE_SCHEMA = [
    field("theme", "preset", "主题色组", "design", "本句色族, 走色彩系统 (47-color)", source="themes"),
    field("th.hi", "color", "高亮色", "design", "唱到时的字色"),
    field("th.glow", "color", "外发光", "design", "唱到时的外发光"),
    field("th.dark", "color", "阴影色", "design", "阴影色, 保证任何画面都看得清"),
    field("motion", "preset", "动作预设", "design", "带意义说明的出入场组合", source="motions"),
    field("ent", "select", "入场", "design", "入场方式, 表达句意 (42-text-main)", options=ENT_OPTS),
    field("ext", "select", "退场", "design", "退场方式", options=EXT_OPTS),
    field("hl", "select", "高亮", "design", "唱到时的高亮手法", options=HL_OPTS),
    field("fx", "preset", "特效配方", "design", "本句特效配方", source="recipes"),
    field("din", "slider", "入场时长", "window", "入场时长", min=0.12, max=1.5, step=0.02, unit="s"),
    field("dout", "slider", "退场时长", "window", "退场时长; 会推迟下一句入场",
          min=0.2, max=1.5, step=0.02, unit="s"),
    field("lead", "slider", "提前量", "window", "首拍前最多提前出现多久",
          min=0.05, max=1.5, step=0.05, unit="s"),
    field("hold", "slider", "停留", "window", "末拍结束后停留多久",
          min=0.0, max=1.5, step=0.05, unit="s"),
    SALT,
] + FX_KNOBS

SEGMENT_SCHEMA = [
    field("level", "select", "卡点等级", "design", "卡点密度等级 L0..L3 (44-beat)", options=[0, 1, 2, 3]),
    field("family", "preset", "色族", "design", "本段色族", source="families"),
    field("enabled", "boolean", "启用", "design", "关掉本段这一层"),
    SALT,
] + FX_KNOBS

CARD_SCHEMA = [SALT] + FX_KNOBS


class UnitKnobs(dict):
    """统一旋钮的值, 带上所属单元的 key. FX.set_knobs 读到它, 就把用到的旋钮记回这个单元."""
    unit_key = None


def unit_knobs(key, params):
    k = UnitKnobs({f["key"]: params[f["key"]] for f in FX_KNOBS})
    k.unit_key = key
    REG.mark(key, ())          # 先记空表: 一次 FX 都没跑的单元, 面板不显示任何统一旋钮
    return k


class Registry:
    """一次生成器运行里收集单元与预设. Doc.write() 时落盘."""

    def __init__(self):
        self.reset()

    def reset(self):
        self._by_key = {}
        self.units, self.themes, self.motions, self.recipes, self.families = [], {}, {}, {}, {}
        self.inputs = {}
        self._keys = set()
        self.meta = {}       # 工程级元数据 (Generator 写): text_lift = 字层抬高量 (Doc.TEXT_LIFT), 台子据此认字身层

    def add(self, unit):
        if unit["key"] in self._keys:
            raise SystemExit("manifest: duplicate unit key %s" % unit["key"])
        self._keys.add(unit["key"])
        self.units.append(unit)
        self._by_key[unit["key"]] = unit
        TR.mark_unit(unit["key"])
        return unit

    def mark(self, key, names):
        """单元用到的统一旋钮 (FX._use 调). 单元先登记后运行 FX 的路径 (段 / 卡片) 走这里."""
        u = self._by_key.get(key)
        if u is not None:
            u["knobs_used"] = sorted(set(u.get("knobs_used") or ()) | set(names))

    def input_file(self, name, path):
        """按哈希记上游输入; 变了预览台会标出受影响的单元."""
        self.inputs[name] = file_sha(path)

    def doc(self):
        """清单正文. meta.text_lift 供验收台认字身层 (不再假设 TEXT_LIFT=0).

        Agent Notes: .agents/notes/implemented/feature/2026-11-17-karaoke-station-loop.md
        """
        presets = dict(themes=self.themes, motions=self.motions, families=self.families,
                       recipes={k: {kk: vv for kk, vv in v.items() if kk != "fn"} for k, v in self.recipes.items()})
        tr = TR.doc()
        if tr:     # 代码依赖 (trace.py): 每个单元的 deps.code / deps.data / emit, 全局的 fns 与 entry
            for u in self.units:
                d = u.setdefault("deps", {})
                d["code"] = tr["units"].get(u["key"], [])
                if u["key"] in tr["data"]:
                    d["data"] = tr["data"][u["key"]]
                u["emit"] = tr["emit"].get(u["key"], {})
        body = dict(format=FORMAT, version=VERSION, inputs=self.inputs, units=self.units, presets=presets,
                    schema=dict(phrase=PHRASE_SCHEMA, segment=SEGMENT_SCHEMA, card=CARD_SCHEMA))
        if tr:
            body["code"] = dict(fns=tr["fns"], entry=tr["entry"], data_names=tr["data_names"])
        if self.meta:
            body["meta"] = dict(self.meta)
        body["revision"] = sha_obj(dict(u=[(u["key"], u.get("fp")) for u in self.units], p=presets))
        return body

    def write(self, ass_path):
        if not self.units:
            return None
        path = manifest_path(ass_path)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.doc(), f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
        return path


REG = Registry()


def manifest_path(ass_path):
    return re.sub(r"\.ass$", "", ass_path) + ".manifest.json"


def file_sha(path):
    try:
        return hashlib.sha1(open(path, "rb").read()).hexdigest()[:12]
    except OSError:
        return None


def sha_obj(obj):
    return hashlib.sha1(json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()[:12]


HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
TH_KEYS = ("hi", "glow", "dark", "base", "cn")


def check_theme(name, th):
    bad = [k for k in TH_KEYS if k in th and not HEX.match(str(th[k]))]
    miss = [k for k in ("hi", "glow", "dark") if k not in th]
    if bad or miss:
        raise SystemExit("theme %s: bad colors %s, missing %s" % (name, bad, miss))
    return {k: th[k].upper() for k in TH_KEYS if k in th}


def register_theme(name, th, why=""):
    REG.themes[name] = dict(check_theme(name, th), why=why)
    return th


def register_family(name, colors, why=""):
    if not colors or any(not HEX.match(c) for c in colors):
        raise SystemExit("family %s: colors must be #RRGGBB" % name)
    REG.families[name] = dict(colors=list(colors), why=why)


def register_motion(name, ent, ext, hl, why, din=None, dout=None):
    if not why:
        raise SystemExit("motion %s: 必须写 why. 说不出意义的预设等于抽奖" % name)
    for v, opts in ((ent, ENT_OPTS), (ext, EXT_OPTS), (hl, HL_OPTS)):
        if v not in opts:
            raise SystemExit("motion %s: %s not in %s" % (name, v, opts))
    m = dict(ent=ent, ext=ext, hl=hl, why=why)
    if din is not None:
        m["din"] = din
    if dout is not None:
        m["dout"] = dout
    REG.motions[name] = m


def load_presets(path):
    """读 skill 预设 (scripts/assfx/presets/*.json). 先校验格式, 不合格直接拒收."""
    d = json.load(open(path, encoding="utf-8"))
    fmt = d.get("format")
    if d.get("version") != 1 or fmt not in ("assfx-themes", "assfx-motions"):
        raise SystemExit("%s: need format assfx-themes|assfx-motions, version 1" % path)
    for name, v in d.get("items", {}).items():
        if fmt == "assfx-themes":
            register_theme(name, v, v.get("why", ""))
        else:
            register_motion(name, v.get("ent"), v.get("ext"), v.get("hl"), v.get("why", ""), v.get("din"), v.get("dout"))
    return fmt


def recipe(name=None, why="", knobs=()):
    """把 fx_* 函数标成配方. knobs 是配方专属旋钮, 函数里用 f.opt() 读."""
    def deco(fn):
        nm = name or fn.__name__[3:]
        fn._recipe = dict(name=nm, why=why or (fn.__doc__ or "").strip().split("\n")[0], knobs=list(knobs))
        REG.recipes[nm] = dict(fn._recipe, fn=fn)
        return fn
    return deco


def register_fxmap(fxmap):
    """没加装饰器的 fx_* 也登记成配方, 只是没有专属旋钮."""
    for nm, fn in fxmap.items():
        if nm not in REG.recipes:
            info = getattr(fn, "_recipe", None) or dict(name=nm, why=(fn.__doc__ or "").strip().split("\n")[0], knobs=[])
            REG.recipes[nm] = dict(info, fn=fn)


def theme_name(th):
    """与 th 相同的已登记主题名; 没有返回 None (本句内联主题)."""
    for n, v in REG.themes.items():
        if all(str(th.get(k, "")).upper() == v.get(k, "") for k in ("hi", "glow", "dark") if k in v):
            return n
    return None
