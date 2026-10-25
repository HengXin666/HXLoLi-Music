# -*- coding: utf-8 -*-
"""工具与场景道具: 路径仿射/包围盒助手, 以及翼/兔/音符/鸟居/烟花等具象物件."""
import math
import re

import math
import random
import re

from assfx.draw.kit.prims import K, f, poly, rot, move, scale   # noqa: F401

from assfx.draw.kit.nature import (arc, bezier_pts, circle, cloud, ellipse, ellipse_ring, flame,   # noqa: F401
                              heart, leaf, petal, rect, ring, sakura, star, stroke)
from assfx.draw.kit.prims import affine, bbox, norm, size, translate, _translate   # noqa: F401


def wing(s, spread=1.0, side=1):
    """单侧翅膀：5 片分层羽（side=1 向右展开，-1 向左）；spread∈[0.3,1.2] 控制张开程度"""
    out = ""
    for i in range(5):
        a = math.radians(-70 + i * 22 * spread)
        L = s * (1.0 - i * 0.12)
        w = s * 0.16
        tip = (math.cos(a) * L, math.sin(a) * L)
        nx, ny = -math.sin(a), math.cos(a)
        p0 = (0, 0)
        c1 = (tip[0] * 0.35 + nx * w, tip[1] * 0.35 + ny * w)
        c2 = (tip[0] * 0.85 + nx * w * 0.8, tip[1] * 0.85 + ny * w * 0.8)
        c3 = (tip[0] * 0.85 - nx * w * 0.4, tip[1] * 0.85 - ny * w * 0.4)
        c4 = (tip[0] * 0.35 - nx * w * 0.5, tip[1] * 0.35 - ny * w * 0.5)
        out += (f"m {f(p0[0])} {f(p0[1])} b {f(c1[0])} {f(c1[1])} {f(c2[0])} {f(c2[1])} {f(tip[0])} {f(tip[1])} "
                f"b {f(c3[0])} {f(c3[1])} {f(c4[0])} {f(c4[1])} {f(p0[0])} {f(p0[1])} ")
    return affine(out, side, 0, 0, 1) if side < 0 else out


def wing_pair(s, spread=1.0, gap=0.0):
    """左右一对翅膀（中间可留 gap） 用于"成对/并肩"母题"""
    return affine(wing(s, spread), 1, 0, 0, 1, gap / 2, 0) + affine(wing(s, spread), -1, 0, 0, 1, -gap / 2, 0)


def rabbit(s):
    """兔子玩偶剪影：圆脸 + 两只垂耳 + 小身体"""
    head = ellipse(s * 0.42, s * 0.36, 0, -s * 0.05)
    ear_l = affine(ellipse(s * 0.12, s * 0.42), math.cos(0.5), -math.sin(0.5), math.sin(0.5), math.cos(0.5), -s * 0.3, -s * 0.55)
    ear_r = affine(ellipse(s * 0.12, s * 0.42), math.cos(-0.35), -math.sin(-0.35), math.sin(-0.35), math.cos(-0.35), s * 0.28, -s * 0.58)
    body = ellipse(s * 0.34, s * 0.3, 0, s * 0.5)
    eyes = ellipse(s * 0.045, s * 0.06, -s * 0.14, -s * 0.07, ccw=True) + ellipse(s * 0.045, s * 0.06, s * 0.14, -s * 0.07, ccw=True)
    return head + ear_l + ear_r + body + eyes


def music_note(s, double=False):
    """音符 ♪ / ♫"""
    if not double:
        return (affine(ellipse(s * 0.3, s * 0.21), math.cos(-0.4), -math.sin(-0.4), math.sin(-0.4), math.cos(-0.4), -s * 0.12, s * 0.62)
                + rect(s * 0.07, s * 1.05, s * 0.13, 0.05 * s)
                + f"m {f(s*0.1)} {f(-s*0.48)} b {f(s*0.3)} {f(-s*0.3)} {f(s*0.5)} {f(-s*0.2)} {f(s*0.42)} {f(s*0.1)} "
                  f"b {f(s*0.38)} {f(-s*0.12)} {f(s*0.25)} {f(-s*0.2)} {f(s*0.1)} {f(-s*0.28)} ")
    h = ellipse(s * 0.26, s * 0.18)
    rh = lambda dx, dy: affine(h, math.cos(-0.4), -math.sin(-0.4), math.sin(-0.4), math.cos(-0.4), dx, dy)
    return (rh(-s * 0.42, s * 0.62) + rh(s * 0.38, s * 0.5) + rect(s * 0.06, s * 1.0, -s * 0.2, 0.08 * s) + rect(s * 0.06, s * 1.0, s * 0.6, -0.04 * s)
            + poly([(-s * 0.23, -s * 0.42), (s * 0.63, -s * 0.56), (s * 0.63, -s * 0.38), (-s * 0.23, -s * 0.24)]))


def violin(s):
    """小提琴剪影（琴身 8 字 + 指板 + 琴头卷轴）"""
    body = (f"m 0 {f(-s*0.2)} b {f(s*0.2)} {f(-s*0.2)} {f(s*0.26)} {f(-s*0.05)} {f(s*0.18)} {f(s*0.05)} "
            f"b {f(s*0.3)} {f(s*0.12)} {f(s*0.32)} {f(s*0.42)} 0 {f(s*0.45)} "
            f"b {f(-s*0.32)} {f(s*0.42)} {f(-s*0.3)} {f(s*0.12)} {f(-s*0.18)} {f(s*0.05)} "
            f"b {f(-s*0.26)} {f(-s*0.05)} {f(-s*0.2)} {f(-s*0.2)} 0 {f(-s*0.2)} ")
    neck = rect(s * 0.06, s * 0.42, 0, -s * 0.4)
    scroll = circle(s * 0.05, s * 0.02, -s * 0.63)
    holes = (stroke([(-s * 0.1, 0), (-s * 0.12, s * 0.08), (-s * 0.09, s * 0.16)], s * 0.018)
             + stroke([(s * 0.1, 0), (s * 0.12, s * 0.08), (s * 0.09, s * 0.16)], s * 0.018))
    return body + neck + scroll + holes


def torii(s):
    """鸟居：两根立柱 + 笠木 + 贯"""
    kasagi = (f"m {f(-s*0.62)} {f(-s*0.42)} b {f(-s*0.3)} {f(-s*0.36)} {f(s*0.3)} {f(-s*0.36)} {f(s*0.62)} {f(-s*0.42)} "
              f"l {f(s*0.58)} {f(-s*0.32)} b {f(s*0.3)} {f(-s*0.27)} {f(-s*0.3)} {f(-s*0.27)} {f(-s*0.58)} {f(-s*0.32)} ")
    nuki = rect(s * 0.96, s * 0.07, 0, -s * 0.14)
    posts = rect(s * 0.08, s * 0.72, -s * 0.33, s * 0.1) + rect(s * 0.08, s * 0.72, s * 0.33, s * 0.1)
    gaku = rect(s * 0.07, s * 0.14, 0, -s * 0.24)
    return kasagi + nuki + posts + gaku


def wheel(r, spokes=16, w=None):
    """单车轮：轮圈 + 辐条 + 花鼓"""
    w = w or max(1.5, r * 0.07)
    out = ring(r, w) + circle(r * 0.08)
    for i in range(spokes):
        a = 2 * math.pi * i / spokes
        out += stroke([(math.cos(a) * r * 0.08, math.sin(a) * r * 0.08), (math.cos(a + 0.2) * (r - w), math.sin(a + 0.2) * (r - w))], max(0.8, r * 0.012))
    return out


def ramune(s):
    """波子汽水瓶：颈部收腰 + 玻璃珠"""
    bottle = (f"m {f(-s*0.12)} {f(-s*0.6)} l {f(s*0.12)} {f(-s*0.6)} l {f(s*0.12)} {f(-s*0.42)} "
              f"b {f(s*0.04)} {f(-s*0.36)} {f(s*0.04)} {f(-s*0.24)} {f(s*0.14)} {f(-s*0.2)} "
              f"b {f(s*0.26)} {f(-s*0.15)} {f(s*0.26)} {f(-s*0.05)} {f(s*0.26)} 0 l {f(s*0.26)} {f(s*0.55)} "
              f"b {f(s*0.26)} {f(s*0.62)} {f(s*0.2)} {f(s*0.66)} {f(s*0.12)} {f(s*0.66)} l {f(-s*0.12)} {f(s*0.66)} "
              f"b {f(-s*0.2)} {f(s*0.66)} {f(-s*0.26)} {f(s*0.62)} {f(-s*0.26)} {f(s*0.55)} l {f(-s*0.26)} 0 "
              f"b {f(-s*0.26)} {f(-s*0.05)} {f(-s*0.26)} {f(-s*0.15)} {f(-s*0.14)} {f(-s*0.2)} "
              f"b {f(-s*0.04)} {f(-s*0.24)} {f(-s*0.04)} {f(-s*0.36)} {f(-s*0.12)} {f(-s*0.42)} ")
    marble = ellipse(s * 0.09, s * 0.09, 0, -s * 0.3, ccw=True)
    return bottle + marble


def firework(n, r, w=2.0, inner=0.25):
    """烟火：n 条放射线（整圆）"""
    out = ""
    for i in range(n):
        a = 2 * math.pi * i / n
        out += stroke([(math.cos(a) * r * inner, math.sin(a) * r * inner), (math.cos(a) * r, math.sin(a) * r)], w, taper=True)
    return out


def dandelion(s):
    """蒲公英绒球种子（伞状冠毛 + 细柄 + 种子）"""
    out = ""
    for i in range(9):
        a = math.radians(-160 + i * 17.5)
        out += stroke([(0, 0), (math.cos(a) * s * 0.55, math.sin(a) * s * 0.55)], max(0.6, s * 0.03))
    return out + stroke([(0, 0), (0, s * 0.6)], max(0.7, s * 0.035)) + ellipse(s * 0.05, s * 0.12, 0, s * 0.68)


def big_cloud(s):
    """积雨云（入道云）：多团叠加"""
    return (circle(s * 0.28, -s * 0.5, s * 0.1) + circle(s * 0.36, -s * 0.18, -s * 0.12) + circle(s * 0.46, s * 0.2, -s * 0.28)
            + circle(s * 0.3, s * 0.55, s * 0.02) + circle(s * 0.25, s * 0.78, s * 0.14) + rect(s * 1.5, s * 0.3, s * 0.12, s * 0.22))


def sunflower(s):
    """向日葵：20 瓣 + 花心"""
    out = ""
    for i in range(20):
        a = 2 * math.pi * i / 20
        p = affine(petal(s * 0.28), math.cos(a), -math.sin(a), math.sin(a), math.cos(a), math.sin(a) * -s * 0.62, math.cos(a) * s * 0.62)
        out += p
    return out + circle(s * 0.34)


def raindrop(L, w=1.6):
    return stroke([(0, -L / 2), (0, L / 2)], w, taper=True)


def curtain(w, h, folds=5, sway=0.0):
    """窗帘：顶边平直、下摆波浪（sway 使下摆偏向一侧）"""
    pts = [(-w / 2, -h / 2), (w / 2, -h / 2)]
    n = folds * 8
    for i in range(n + 1):
        x = w / 2 - w * i / n
        y = h / 2 + math.sin(i / n * folds * 2 * math.pi) * h * 0.04
        pts.append((x + sway * h * 0.25 * (1 - abs(0.5 - i / n) * 0), y))
    return poly(pts)


def lantern(s):
    """纸灯笼（圆形吊灯）"""
    return ellipse(s * 0.5, s * 0.42) + rect(s * 0.3, s * 0.08, 0, -s * 0.46) + rect(s * 0.3, s * 0.08, 0, s * 0.46) + rect(s * 0.03, s * 0.3, 0, -s * 0.64)


def window_frame(w, h, bar=4, panes=(2, 1)):
    """窗框（镂空格子）"""
    out = rect(w, h)
    cw = (w - bar * (panes[0] + 1)) / panes[0]; ch = (h - bar * (panes[1] + 1)) / panes[1]
    for i in range(panes[0]):
        for j in range(panes[1]):
            cx = -w / 2 + bar + cw / 2 + i * (cw + bar); cy = -h / 2 + bar + ch / 2 + j * (ch + bar)
            x0, y0, x1, y1 = cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2
            out += poly([(x0, y0), (x0, y1), (x1, y1), (x1, y0)])     # 逆时针 = 镂空
    return out


# ================================================================ 运动会 / 庆典 / 元气
def tipi(s):
    """印第安帐篷：三角篷身 + 交叉支杆 + 门帘开口"""
    body = poly([(0, -s * 0.5), (s * 0.45, s * 0.5), (-s * 0.45, s * 0.5)])
    door = poly([(0, s * 0.05), (-s * 0.14, s * 0.5), (s * 0.14, s * 0.5)][::-1])
    poles = stroke([(-s * 0.12, -s * 0.72), (s * 0.03, -s * 0.42)], s * 0.035) + stroke([(s * 0.12, -s * 0.72), (-s * 0.03, -s * 0.42)], s * 0.035)
    return body + door + poles


def cactus(s):
    """仙人掌（树形，两臂上举）"""
    trunk = rect(s * 0.24, s * 1.0, 0, 0) + circle(s * 0.12, 0, -s * 0.5)
    arm_l = rect(s * 0.3, s * 0.14, -s * 0.22, s * 0.05) + rect(s * 0.14, s * 0.34, -s * 0.33, -s * 0.1) + circle(s * 0.07, -s * 0.33, -s * 0.27)
    arm_r = rect(s * 0.3, s * 0.14, s * 0.22, -s * 0.1) + rect(s * 0.14, s * 0.3, s * 0.33, -s * 0.23) + circle(s * 0.07, s * 0.33, -s * 0.38)
    return trunk + arm_l + arm_r


def gong(s):
    """铜锣：圆锣 + 两根支架 + 横梁"""
    return (ring(s * 0.36, s * 0.07) + circle(s * 0.12) + rect(s * 0.06, s * 1.0, -s * 0.46, s * 0.05)
            + rect(s * 0.06, s * 1.0, s * 0.46, s * 0.05) + rect(s * 1.05, s * 0.07, 0, -s * 0.45))


def hurdle(s):
    """跨栏架"""
    return (rect(s * 1.0, s * 0.16, 0, -s * 0.3) + rect(s * 0.06, s * 0.7, -s * 0.44, s * 0.05) + rect(s * 0.06, s * 0.7, s * 0.44, s * 0.05)
            + rect(s * 0.3, s * 0.06, -s * 0.44, s * 0.4) + rect(s * 0.3, s * 0.06, s * 0.44, s * 0.4))


def vault_box(s, tiers=4):
    """跳箱：梯形分层 + 顶部软垫"""
    out = ""
    for i in range(tiers):
        y0 = -s * 0.3 + i * s * 0.2; y1 = y0 + s * 0.17
        hw0 = s * (0.36 + i * 0.04); hw1 = s * (0.38 + i * 0.04)
        out += poly([(-hw0, y0), (hw0, y0), (hw1, y1), (-hw1, y1)])
    return out + ellipse(s * 0.36, s * 0.07, 0, -s * 0.34)


def bread(s):
    """圆面包：半球 + 顶部芝麻点"""
    return (ellipse(s * 0.5, s * 0.34) + ellipse(s * 0.04, s * 0.025, -s * 0.06, -s * 0.18, ccw=True)
            + ellipse(s * 0.04, s * 0.025, s * 0.07, -s * 0.2, ccw=True) + ellipse(s * 0.04, s * 0.025, 0, -s * 0.24, ccw=True))


def bunting(w, n=7, h=None, sag=None):
    """三角彩旗串（返回 [(绘图, (cx,cy))]，方便逐面上色）"""
    h = h or w / n * 0.7; sag = sag if sag is not None else h * 0.4
    out = []
    for i in range(n):
        t0 = i / n; t1 = (i + 1) / n; tm = (t0 + t1) / 2
        yy = lambda t: sag * 4 * t * (1 - t)
        x0 = -w / 2 + w * t0 + 2; x1 = -w / 2 + w * t1 - 2; xm = -w / 2 + w * tm
        out.append((poly([(x0, yy(t0)), (x1, yy(t1)), (xm, yy(tm) + h)]), (xm, yy(tm) + h / 3)))
    return out


def comic_burst(s, n=12, jag=0.62, rng=None):
    """漫画爆炸框（锯齿星）"""
    pts = []
    for i in range(2 * n):
        r = s if i % 2 == 0 else s * jag * (rng.uniform(0.85, 1.1) if rng else 1)
        a = math.pi * i / n
        pts.append((math.cos(a) * r, math.sin(a) * r * 0.8))
    return poly(pts)


def confetti(w, h):
    return rect(w, h)


def arrow(L, w=2.0):
    """羽箭：箭杆 + 箭头 + 尾羽（指向 +x）"""
    return (rect(L, w) + poly([(L / 2 + w * 5, 0), (L / 2 - w, -w * 3), (L / 2 - w, w * 3)])
            + poly([(-L / 2, 0), (-L / 2 - w * 4, -w * 3), (-L / 2 + w * 3, -w * 3), (-L / 2 + w * 5, 0)])
            + poly([(-L / 2, 0), (-L / 2 + w * 5, 0), (-L / 2 + w * 3, w * 3), (-L / 2 - w * 4, w * 3)]))


def medal(s):
    """No.1 奖牌：圆牌 + V 形绶带"""
    return (circle(s * 0.34, 0, s * 0.22) + ring(s * 0.26, s * 0.04, 0, s * 0.22)
            + poly([(-s * 0.3, -s * 0.6), (-s * 0.12, -s * 0.6), (s * 0.06, s * 0.0), (-s * 0.1, s * 0.02)])
            + poly([(s * 0.3, -s * 0.6), (s * 0.12, -s * 0.6), (-s * 0.06, s * 0.0), (s * 0.1, s * 0.02)]))


def door(s):
    """门（拱顶）+ 门把"""
    return (f"m {f(-s*0.32)} {f(s*0.5)} l {f(-s*0.32)} {f(-s*0.2)} b {f(-s*0.32)} {f(-s*0.58)} {f(s*0.32)} {f(-s*0.58)} {f(s*0.32)} {f(-s*0.2)} "
            f"l {f(s*0.32)} {f(s*0.5)} " + circle(s * 0.05, s * 0.18, s * 0.1, ) + "")


def umbrella(s):
    """雨伞"""
    top = (f"m {f(-s*0.5)} 0 b {f(-s*0.5)} {f(-s*0.55)} {f(s*0.5)} {f(-s*0.55)} {f(s*0.5)} 0 "
           f"b {f(s*0.4)} {f(-s*0.1)} {f(s*0.25)} {f(-s*0.1)} {f(s*0.17)} 0 b {f(s*0.08)} {f(-s*0.1)} {f(-s*0.08)} {f(-s*0.1)} {f(-s*0.17)} 0 "
           f"b {f(-s*0.25)} {f(-s*0.1)} {f(-s*0.4)} {f(-s*0.1)} {f(-s*0.5)} 0 ")
    return top + stroke([(0, 0), (0, s * 0.45), (s * 0.06, s * 0.52), (s * 0.12, s * 0.45)], s * 0.045)


def bookmark(s):
    """书签（燕尾）+ 流苏孔"""
    return poly([(-s * 0.18, -s * 0.5), (s * 0.18, -s * 0.5), (s * 0.18, s * 0.5), (0, s * 0.32), (-s * 0.18, s * 0.5)]) + circle(s * 0.05, 0, -s * 0.38)[:0]


def puff(s):
    """喷嚏/蒸汽小云团"""
    return circle(s * 0.35, -s * 0.25, 0) + circle(s * 0.42, s * 0.1, -s * 0.1) + circle(s * 0.3, s * 0.4, s * 0.08)


def pepper(s):
    """辣椒/香料荚"""
    return (f"m {f(-s*0.1)} {f(-s*0.4)} b {f(s*0.25)} {f(-s*0.35)} {f(s*0.3)} {f(s*0.2)} {f(-s*0.05)} {f(s*0.55)} "
            f"b {f(s*0.05)} {f(s*0.1)} {f(-s*0.2)} {f(-s*0.2)} {f(-s*0.1)} {f(-s*0.4)} "
            + rect(s * 0.05, s * 0.18, -s * 0.12, -s * 0.48))
