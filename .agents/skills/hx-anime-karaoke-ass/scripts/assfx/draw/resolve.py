# -*- coding: utf-8 -*-
"""形状写法 -> ASS 路径. 设计中间表示 (layer/ir.py) 里的 motif.shape 一律经这里解析.

写法 (一个字符串, 前缀定来源):
  kit:<函数>[:参数,...]        几何语汇 draw/shapes.py, 第一个参数恒为尺寸 (例 kit:star:5,0.42 -> S.star(5, s, s*0.42))
  glyph:<字体文件>:<字>        字形轮廓, 精确三次贝塞尔 (glyph.py); 字体在 ASSFX_FONTS 或 skill 的 fonts/
  svg:<相对工程目录的 .svg>    精确矢量 (base/svg2ass.py faithful 模式, 不采样成折线)
  prop:<名字>                  现成具象物件 asset/props.py (通用物件, 不可参数化)
返回 callable(size) -> 路径, 让同一个母题能按尺寸反复取 (粒子, 生长).
"""
import os

from assfx.draw import shapes as S

_SKILL_FONTS = os.path.abspath(os.path.join(os.path.dirname(__file__), *[".."] * 4, "fonts"))
PREFIXES = ("kit", "glyph", "svg", "prop")


def _num(v):
    try:
        return int(v)
    except ValueError:
        return float(v)


def _kit(name, args):
    fn = getattr(S, name, None)
    if not callable(fn):
        raise KeyError("draw/shapes.py 里没有 %s" % name)
    if name == "star":                           # star(n, ro, ri): 参数 n, ri/ro 比例
        n, r = (args + [5, 0.45])[:2]
        return lambda s: fn(int(n), s, s * float(r))
    if name in ("ring",):
        w = (args + [0.18])[0]
        return lambda s: fn(s, s * float(w))
    return lambda s: fn(s, *args)


# Agent Notes: 组合式生成: 设计中间表示 + 形状来源 + 母题来源门禁 + 跨作品指纹
# 
def shape_fn(spec, proj=None, fonts=None):
    """Agent Notes
    .agents/notes/implemented/architecture/2026-11-17-karaoke-compositional-generator.md
    spec 见模块头. proj: svg 相对路径的基准 (工程目录). 解析失败直接抛错 (设计写错了要立刻知道, 不静默退化)."""
    kind, _, rest = spec.partition(":")
    if kind not in PREFIXES:
        raise ValueError("形状写法 %r 的来源前缀不认识, 只认 %s" % (spec, "/".join(PREFIXES)))
    if kind == "kit":
        name, _, a = rest.partition(":")
        return _kit(name, [_num(x) for x in a.split(",") if x])
    if kind == "glyph":
        from assfx.draw.glyph import glyph_path
        font, _, ch = rest.rpartition(":")
        path = font if os.path.isabs(font) else os.path.join(fonts or os.environ.get("ASSFX_FONTS") or _SKILL_FONTS, font)
        cache = {}

        def g(s):
            key = round(s, 2)
            if key not in cache:
                cache[key] = glyph_path(path, ch, s)[0]
            return cache[key]
        g(40)                                   # 立刻校验字体与字存在
        return g
    if kind == "svg":
        from assfx.base.svg2ass import from_file
        path = rest if os.path.isabs(rest) else os.path.join(proj or ".", rest)
        if not os.path.exists(path):
            raise FileNotFoundError("svg 形状不存在: %s (矢量素材放工程目录, 不放 skill)" % path)
        return lambda s: from_file(path, size=s, faithful=True)
    from assfx.asset import props
    return props.get(rest)


def source_of(spec):
    """形状的来源类别 (指纹与清单用): kit / glyph / svg / prop."""
    return spec.partition(":")[0]
