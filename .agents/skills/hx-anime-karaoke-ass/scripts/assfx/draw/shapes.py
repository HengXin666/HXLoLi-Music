# -*- coding: utf-8 -*-
"""矢量绘图库(ASS \\p1 绘图代码)的**聚合入口**.

同一批图形按用途分成四个模块, 这里把它们并成一个命名空间  调用方一律
`from assfx.draw import shapes as S`, 所以拆模块不该让调用点跟着改.

| 模块 | 内容 |
|---|---|
| prims    | 数值格式与点集变换 (f / poly / rot / move / scale) |
| nature   | 基本形、光效、自然物 |
| battle   | 破坏/战斗、魔法/学识 |
| props2   | 路径仿射/包围盒助手, 与翼/兔/音符/鸟居/烟花等道具 |
"""
from assfx.draw.kit.prims import *      # noqa: F401,F403
from assfx.draw.kit.nature import *     # noqa: F401,F403
from assfx.draw.kit.battle import *     # noqa: F401,F403
from assfx.draw.kit.props2 import *     # noqa: F401,F403
from assfx.draw.kit.prims import affine, bbox, flat, norm, size, _translate as translate   # noqa: F401
