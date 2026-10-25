#!/usr/bin/env python3
r"""母题库: 番剧母题的绘图路径生成器 (只产出 ASS \p1 路径, 不碰任何标签)。

设计契约:
  * 每个函数签名固定为 (w, h) -> 路径字符串, 且**路径的坐标原点在自身的左上角**;
  * 路径必须落在 [0,w] x [0,h] 之内  调用方靠这一点来保证归一化安全区不被突破;
  * 只用 m / l / b 三种指令 (最保守的子集, libass 与定制引擎都支持).

为什么要这么多形状: 实测教训是「一种图元重复 5929 次」等于不绚烂。
门禁 gradient_gate.py 的 G-A 判据要求种类 >= 12, 这份库给出 16 种。
"""
from __future__ import annotations

import math

# ── 通用 ──────────────────────────────────────────────────────────
def _poly(pts):
    return "m " + " l ".join("%.1f %.1f" % p for p in pts)


def _ring(cx, cy, r, n=16, r2=None, phase=0.0):
    r2 = r if r2 is None else r2
    pts = []
    for i in range(n * 2):
        ang = phase + math.pi * i / n
        rr = r if i % 2 == 0 else r2
        pts.append((cx + rr * math.cos(ang), cy + rr * math.sin(ang)))
    return _poly(pts)


# ── 东方 / 风祝 系 ────────────────────────────────────────────────
def wind(w, h):
    """风的轨迹: 三条渐短的撇。纵向分三层, 每层占 h/3, 留 5% 余量。"""
    rows = []
    bh = h / 3.0
    for k in range(3):
        y0 = k * bh + bh * 0.10
        rows.append(_poly([(0, y0), (w*(0.6-0.14*k), y0),
                           (w*(0.6-0.14*k) - w*0.10, y0 + bh*0.55), (0, y0 + bh*0.55)]))
    return " ".join(rows)


def gust(w, h):
    """气旋: 一个开口的椭圆螺旋。横向半径以 w 为限, 纵向以 h/2 为限。"""
    pts = []
    for i in range(18):
        t = i / 17.0
        ang = t * math.pi * 2.4
        rx = (0.10 + 0.40 * t) * w
        ry = (0.10 + 0.40 * t) * h * 0.5
        pts.append((w*0.5 + rx*math.cos(ang), h*0.5 + ry*math.sin(ang)))
    return _poly(pts)


def gohei(w, h):
    """御币: 竖杆加两条折纸垂带。"""
    p = _poly([(w*0.48, 0), (w*0.52, 0), (w*0.52, h), (w*0.48, h)])
    p += " " + _poly([(w*0.52, h*0.1), (w*0.95, h*0.25), (w*0.72, h*0.35), (w*0.95, h*0.5), (w*0.52, h*0.55)])
    return p


def shide(w, h):
    """纸垂: 锯齿状垂下的折线, 四折刚好铺满高度。"""
    pts = [(0, 0)]
    for k in range(4):
        pts.append((w, h*(k*0.25 + 0.125)))
        pts.append((0, h*(k*0.25 + 0.25)))
    return _poly(pts)


def snake(w, h):
    """蛇: 正弦绞线 (八坂/早苗的蛇符)。"""
    pts = [(w*i/23.0, h*0.5 + h*0.42*math.sin(i/23.0*math.pi*2.6)) for i in range(24)]
    return _poly(pts)


def frog(w, h):
    """蛙: 两条圆弧加两个眼点。"""
    p = _poly([(0, h*0.75), (w*0.25, h*0.25), (w*0.75, h*0.25), (w, h*0.75)])
    p += " " + _poly([(w*0.22, h*0.22), (w*0.3, h*0.22), (w*0.3, h*0.34), (w*0.22, h*0.34)])
    p += " " + _poly([(w*0.7, h*0.22), (w*0.78, h*0.22), (w*0.78, h*0.34), (w*0.7, h*0.34)])
    return p


def ofuda(w, h):
    """符纸: 竖长条带切口。"""
    return _poly([(w*0.35, 0), (w*0.65, 0), (w*0.65, h*0.85), (w*0.5, h), (w*0.35, h*0.85)])


# ── 通用图形母题 ──────────────────────────────────────────────────
def star(w, h):
    """星: 五角星 (封面里就有星星)。"""
    pts = []
    for i in range(10):
        ang = -math.pi/2 + math.pi*i/5
        r = 0.5 if i % 2 == 0 else 0.2
        pts.append((w*0.5 + r*w*math.cos(ang), h*0.5 + r*math.sin(ang)))
    return _poly(pts)


def petal(w, h):
    """花瓣: 三枚椭圆近似。"""
    out = []
    for k in range(3):
        cx = w*(0.18 + k*0.32)
        out.append(_poly([(cx, h*0.1), (cx + w*0.13, h*0.5), (cx, h*0.9), (cx - w*0.13, h*0.5)]))
    return " ".join(out)


def ripple(w, h):
    """涟漪: 三层同心扁环, 纵向压扁以适配横条。"""
    out = []
    for k in range(3):
        rx = w*(0.15 + k*0.17)
        # 纵向半径上界: 最外层 rx 已达 0.49w, 必须让 ry <= 0.5h 且留余量
        ry = min(rx * (h / w) * 1.15, h * 0.5 * (0.98 - 0.06 * k))
        pts = []
        n = 14
        for i in range(n*2):
            ang = math.pi * i / n
            rr = 1.0 if i % 2 == 0 else 0.72
            pts.append((w*0.5 + rx*rr*math.cos(ang), h*0.5 + ry*rr*math.sin(ang)))
        out.append(_poly(pts))
    return " ".join(out)


def moon(w, h):
    """月弧: 一弯新月。"""
    pts = [(w*0.5 + w*0.45*math.cos(math.pi*(0.15 + 0.7*i/15)), h*0.5 + h*0.48*math.sin(math.pi*(0.15 + 0.7*i/15)))
           for i in range(16)]
    pts += [(w*0.72 + w*0.3*math.cos(math.pi*(0.85 - 0.7*i/15)), h*0.5 + h*0.34*math.sin(math.pi*(0.85 - 0.7*i/15)))
            for i in range(16)]
    return _poly(pts)


def trail(w, h):
    """拖尾: 由粗到细的锥形。"""
    return _poly([(0, h*0.3), (w*0.75, 0), (w, h*0.5), (w*0.75, h), (0, h*0.7)])


def shard(w, h):
    """碎片: 不规则多边形 (崩坏意象)。"""
    return _poly([(0, h*0.6), (w*0.3, 0), (w*0.62, h*0.22), (w, h*0.1), (w*0.78, h*0.8), (w*0.25, h)])


def dots(w, h):
    """点阵: 一排小方块。"""
    n = 9
    s = min(w/n*0.6, h)
    return " ".join(_poly([(i*w/n, 0), (i*w/n + s, 0), (i*w/n + s, s), (i*w/n, s)]) for i in range(n))


def arc(w, h):
    """弧线: 折线近似的低弧。"""
    pts = [(w*i/9.0, h*0.5 - h*0.45*math.sin(math.pi*i/9.0)) for i in range(10)]
    return _poly(pts)


def band(w, h):
    """光带: 平行四边形。"""
    return _poly([(0, h*0.25), (w, 0), (w, h*0.75), (0, h)])


# ── 语义映射: 关键词 -> 母题 ──────────────────────────────────────
# 匹配顺序即优先级: 作品专有符号 > 句内具体名词 > 段落情绪兜底。
# 匹配顺序即优先级。**关键词必须是词, 不能是单个假名**  实测踩过: 助词「て」被当成
# 「手」的关键词, 5 句里 3 句被判成 arc。日文助词/词尾与名词共用假名, 单假名匹配必然误命中。
# 所以假名关键词一律要求 2 个音节以上, 且优先用汉字。
SEMANTIC_MAP = [
    (("風", "轨迹", "軌跡"), "trail"),
    (("風", "风", "かぜ"), "wind"),
    (("奇跡", "奇迹"), "star"),
    (("儚", "虚幻", "无常"), "shard"),
    (("星", "ほし"), "star"),
    (("花", "はな"), "petal"),
    (("涙", "泪", "なみだ"), "ripple"),
    (("月", "つき"), "moon"),
    (("光", "ひかり"), "band"),
    (("こころ", "心"), "ripple"),
    (("空", "そら"), "gust"),
    (("蛇", "へび"), "snake"),
    (("蛙", "かえる"), "frog"),
    (("御幣", "御幣", "みこ"), "gohei"),
    (("祈", "いの"), "ofuda"),
    (("別", "わか"), "shard"),
    (("消", "きえ"), "gust"),
    (("存在", "そんざい"), "dots"),
    # shide 之前没有任何关键词, 只能靠兜底轮换  这里补上它自己的触发词。
    (("紙垂", "しで", "垂"), "shide"),
]

LIBRARY = {
    "wind": wind, "gust": gust, "gohei": gohei, "shide": shide, "snake": snake,
    "frog": frog, "ofuda": ofuda, "star": star, "petal": petal, "ripple": ripple,
    "moon": moon, "trail": trail, "shard": shard, "dots": dots, "arc": arc, "band": band,
}


# Agent Notes: 卡拉OK skill 按步骤重构成 steps/NN-<key>/ 的契约 + impl 结构
# 
def pick(jp: str, fallback_index: int = 0) -> str:
    """
    .agents/notes/implemented/process/2026-10-02-karaoke-steps-restructure.md
按句子挑母题名。命中语义映射则用之, 否则按索引轮换兜底。"""
    for keys, name in SEMANTIC_MAP:
        if any(k in jp for k in keys):
            return name
    names = list(LIBRARY)
    return names[fallback_index % len(names)]


def path_of(name: str, w: float, h: float) -> str:
    return LIBRARY[name](w, h)


if __name__ == "__main__":
    # 自检: 每个母题都必须在 [0,w]x[0,h] 内, 且不是空路径
    import re
    bad = []
    for n, fn in LIBRARY.items():
        p = fn(400.0, 80.0)
        v = [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", p)]
        xs, ys = v[0::2], v[1::2]
        if not v or not p.startswith("m "):
            bad.append((n, "空或格式错"))
            continue
        if min(xs) < -0.01 or max(xs) > 400.01 or min(ys) < -0.01 or max(ys) > 80.01:
            bad.append((n, "越界 x[%.1f,%.1f] y[%.1f,%.1f]" % (min(xs), max(xs), min(ys), max(ys))))
    print("母题 %d 种" % len(LIBRARY))
    print("自检: " + ("全部在框内" if not bad else "有问题 -> %s" % bad))
    raise SystemExit(0 if not bad else 1)
