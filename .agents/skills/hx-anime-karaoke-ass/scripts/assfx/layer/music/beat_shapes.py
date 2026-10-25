# -*- coding: utf-8 -*-
"""卡点层的图形族与色族: 从烘焙素材(assets/shapes.json)注入.

`bind_baked` 必须被调用  不调则 BEAT_SHAPES 为空, beat_scatter 会直接报错.
烘焙素材的坐标是 ±100 的规范尺寸(bbox 200x200), **不是像素尺寸**, 所以发射时要按
BAKED_NORM 换算成 \\fscx/\\fscy.
"""
import math

from assfx.draw import shapes as S


# 图形族: 现代、有区分度、不指涉具体人物. 用烘焙素材(assets/shapes.json)而非手绘多边形
#  实测烘焙素材精度中位 36 段、最大 116 段, 合成路径中位只有 4 段, 那就是"图形很粗糙"
# 的机械证据; 所以借 flower/orbit/snowflake/atom 这类本身有细节的小图形, 不靠尺寸取胜.
BEAT_SHAPES = {}

# 需要图片路径的族(用 assets/shapes.json 的烘焙图), 由 bind_baked() 注入
# 名字必须**真实存在于 assets/shapes.json**  写不存在的名字会静默回退
# (见 42-text-main/impl/per-line.md §7b). 这里只用实测存在的 8 个.
_BAKED_SPEC = {
    "star":   ("star4",     0.55),   # 四芒星: 锐
    "flower": ("flower",    0.42),   # 花: 花瓣有细节
    "orbit":  ("orbit",     0.40),   # 轨道环: 多段曲线
    "snow":   ("snowflake", 0.40),   # 雪花: 92 段
    "atom":   ("atom",      0.42),   # 原子: 多环
    "seed":   ("seed",      0.45),
    "cross":  ("cross",     0.40),
    "diam":   ("diamond",   0.50),
}
BEAT_BAKED = {}          # 运行时填: name -> 归一化系数(见 bind_baked)
BAKED_NORM = 200.0       # bake_shapes.py 的规范尺寸(实测各素材 bbox 均 ~200)


def bind_baked(baked):
    """把烘焙素材(assets/shapes.json)接进卡点层的图形族.

    `baked`: {name: {"d": path}}  由生成器读入后传入. **必须调用**.

    ⚠ **烘焙素材的坐标是 ±100 的规范尺寸(bbox 200x200), 不是"像素尺寸"**.
    第一版直接把路径当 sz 用, 于是 `sz=14~26` 实际画出 **200px** 的图,
    再乘 fade(18~52%) 仍有 100px+  实测单条墨迹达 1063px(而 band 高只有 242px),
    这就是"图形非常大"的根因.
    修法: 用 `\fscx/\fscy` 把 200px 的规范路径缩到目标像素尺寸 
    缩放在 `beat_scatter` 里按 `BAKED_NORM` 换算后内联加进 `\\fscx/\\fscy`.
    """
    BEAT_SHAPES.clear()
    BEAT_BAKED.clear()
    for key, (bk_name, k) in _BAKED_SPEC.items():
        if bk_name in baked:
            BEAT_SHAPES[key] = (lambda n: (lambda r: baked[n]["d"]))(bk_name)
            BEAT_BAKED[key] = k          # 记录该素材的"归一化系数", 供 _size_tag 用
    return sorted(BEAT_SHAPES)


def _hex(r):
    pts = []
    for i in range(6):
        a = math.radians(60 * i - 90)
        pts.append((math.cos(a) * r, math.sin(a) * r))
    return S.poly(pts)


# 同刻并置的色族: 亮青蓝系为主 + 两支高饱和对比色(实测参考用色风格)
BEAT_COLORS = {
    "cyan":   ["#00FFFF", "#00B4FF", "#8EFFE6", "#41FF32", "#32FF6C", "#32FFB9"],
    "sunset": ["#FFD060", "#FF8A3C", "#FF5A8A", "#FFF0C0", "#FFB0D8", "#FFFFFF"],
    "jade":   ["#7CFFC4", "#3FE0A0", "#A8FFE0", "#E8FFF4", "#21C7A8", "#8EFFE6"],
    "violet": ["#C08CFF", "#8A5AFF", "#E0C8FF", "#FF8AE0", "#6A5AE0", "#F0E0FF"],
}
