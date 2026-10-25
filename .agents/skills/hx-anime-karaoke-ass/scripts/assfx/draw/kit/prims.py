# -*- coding: utf-8 -*-
"""数值格式与点集变换.

所有图形以 (0,0) 为中心附近构造; 配合 \\an5\\pos 使用时 libass 会把绘图包围盒中心
放在 \\pos 点, 旋转也绕该点. \\p1 下 1 单位 = 1px, 再乘 \\fscx/\\fscy.
"""
import math, random, re

K = 0.5523


def f(v):
    return f"{v:.1f}".rstrip("0").rstrip(".") if abs(v) < 1e5 else str(int(v))


def poly(pts, close=True):
    # Agent Notes: 卡拉OK skill 通用化  去掉单次制作的事实与清单式铺陈
    # 
    """Agent Notes
    .agents/notes/implemented/process/2026-10-04-karaoke-skill-genericize.md
    """
    s = "m " + f(pts[0][0]) + " " + f(pts[0][1]) + " l " + " ".join(f(x) + " " + f(y) for x, y in pts[1:])
    return s + " "


def rot(pts, ang, cx=0, cy=0):
    c, s = math.cos(ang), math.sin(ang)
    return [(cx + (x - cx) * c - (y - cy) * s, cy + (x - cx) * s + (y - cy) * c) for x, y in pts]


def move(pts, dx, dy):
    return [(x + dx, y + dy) for x, y in pts]


def scale(pts, sx, sy=None):
    sy = sx if sy is None else sy
    return [(x * sx, y * sy) for x, y in pts]


_NUM = re.compile(r"-?\d+(?:\.\d+)?")


def _translate(d, dx, dy):
    toks = d.split(); out = []; i = 0
    cmd_expect = False
    coords = []
    for t in toks:
        if t in ("m", "l", "b", "n", "s", "p", "c"):
            out.append(t); coords = []
            continue
        coords.append(float(t))
        if len(coords) == 2:
            out.append(f(coords[0] + dx)); out.append(f(coords[1] + dy)); coords = []
    return " ".join(out) + " "


translate = _translate


def affine(d, a, b, c, e, tx=0.0, ty=0.0):
    """对绘图坐标做仿射变换 x' = a*x + b*y + tx, y' = c*x + e*y + ty（贝塞尔控制点同样适用）"""
    toks = d.split(); out = []; coords = []
    for t in toks:
        if t in ("m", "l", "b", "n", "s", "p", "c"):
            out.append(t); coords = []
            continue
        coords.append(float(t))
        if len(coords) == 2:
            x, y = coords
            out.append(f(a * x + b * y + tx)); out.append(f(c * x + e * y + ty)); coords = []
    return " ".join(out) + " "


def flat(d, angle=0.0, squash=0.26):
    """“地面”图形：先在平面内旋转 angle 度，再把 y 压扁为 squash（= cos 倾角）。
    代替 \\frx 倾斜libass 透视距离只有 ~312px，大图形用 \\frx 会严重畸变甚至翻到镜头后。"""
    r = math.radians(angle); cs, sn = math.cos(r), math.sin(r)
    return affine(d, cs, -sn, sn * squash, cs * squash)


def bbox(d):
    """
    .agents/notes/implemented/process/2026-10-05-karaoke-scripts-grouping.md
绘图坐标包围盒 (x0, y0, x1, y1)"""
    # Agent Notes: hx-anime-karaoke-ass 的 scripts/ 按职责分组，并把 5 个超 300 行的模块拆开
    # 
    nums = [float(v) for v in _NUM.findall(d)]
    xs, ys = nums[0::2], nums[1::2]
    return min(xs), min(ys), max(xs), max(ys)


def norm(d):
    """把绘图平移到包围盒左上角 = (0,0)。
    libass 对 \\an5 绘图的对齐：原点放在 pos-(w/2,h/2)，即假设图形占据 [0,w]x[0,h]；
    以 (0,0) 为中心构造的图形若不归一化，会整体向左上偏移 (xmin,ymin)。"""
    x0, y0, _, _ = bbox(d)
    return _translate(d, -x0, -y0) if (abs(x0) > 0.01 or abs(y0) > 0.01) else d


def size(d):
    x0, y0, x1, y1 = bbox(d)
    return x1 - x0, y1 - y0


# ================================================================ 田园 / 夏日 / 羁绊
