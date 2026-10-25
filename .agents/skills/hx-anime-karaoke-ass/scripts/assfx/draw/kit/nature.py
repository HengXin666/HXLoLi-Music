# -*- coding: utf-8 -*-
"""基本形、光效与自然物: 可参数化的几何语汇(圆/环/弧/星/花/叶/雪…).

尺寸参数 s/r 为像素. 镂空约定: 外轮廓顺时针 + 内轮廓逆时针(libass 非零环绕规则).
"""
import math
import random
import re

from assfx.draw.kit.prims import K, f, poly, rot, move, scale   # noqa: F401


def ellipse(rx, ry, cx=0, cy=0, ccw=False):
    kx, ky = K * rx, K * ry
    if not ccw:
        return (f"m {f(cx)} {f(cy-ry)} b {f(cx+kx)} {f(cy-ry)} {f(cx+rx)} {f(cy-ky)} {f(cx+rx)} {f(cy)} "
                f"b {f(cx+rx)} {f(cy+ky)} {f(cx+kx)} {f(cy+ry)} {f(cx)} {f(cy+ry)} "
                f"b {f(cx-kx)} {f(cy+ry)} {f(cx-rx)} {f(cy+ky)} {f(cx-rx)} {f(cy)} "
                f"b {f(cx-rx)} {f(cy-ky)} {f(cx-kx)} {f(cy-ry)} {f(cx)} {f(cy-ry)} ")
    return (f"m {f(cx)} {f(cy-ry)} b {f(cx-kx)} {f(cy-ry)} {f(cx-rx)} {f(cy-ky)} {f(cx-rx)} {f(cy)} "
            f"b {f(cx-rx)} {f(cy+ky)} {f(cx-kx)} {f(cy+ry)} {f(cx)} {f(cy+ry)} "
            f"b {f(cx+kx)} {f(cy+ry)} {f(cx+rx)} {f(cy+ky)} {f(cx+rx)} {f(cy)} "
            f"b {f(cx+rx)} {f(cy-ky)} {f(cx+kx)} {f(cy-ry)} {f(cx)} {f(cy-ry)} ")


def circle(r, cx=0, cy=0):
    return ellipse(r, r, cx, cy)


def ring(r, w, cx=0, cy=0):
    return ellipse(r, r, cx, cy) + ellipse(r - w, r - w, cx, cy, ccw=True)


def ellipse_ring(rx, ry, w):
    return ellipse(rx, ry) + ellipse(rx - w, ry - w * ry / rx, ccw=True)


def rect(w, h, cx=0, cy=0):
    return poly([(cx - w / 2, cy - h / 2), (cx + w / 2, cy - h / 2), (cx + w / 2, cy + h / 2), (cx - w / 2, cy + h / 2)])


def arc(r, a0, a1, w, n=None):
    """粗圆弧（角度制，0°=右，顺时针为正，因为 y 轴向下）"""
    n = n or max(6, int(abs(a1 - a0) / 6))
    out = [(r * math.cos(math.radians(a0 + (a1 - a0) * i / n)), r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]
    inn = [((r - w) * math.cos(math.radians(a0 + (a1 - a0) * i / n)), (r - w) * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n, -1, -1)]
    return poly(out + inn)


def stroke(pts, w, taper=False):
    """粗折线（两侧偏移后闭合）；taper=True 两端收尖（笔触/划痕）"""
    L, R = [], []
    n = len(pts)
    for i, (x, y) in enumerate(pts):
        if i == 0:
            dx, dy = pts[1][0] - x, pts[1][1] - y
        elif i == n - 1:
            dx, dy = x - pts[i - 1][0], y - pts[i - 1][1]
        else:
            dx, dy = pts[i + 1][0] - pts[i - 1][0], pts[i + 1][1] - pts[i - 1][1]
        d = math.hypot(dx, dy) or 1
        nx, ny = -dy / d, dx / d
        k = math.sin(math.pi * i / (n - 1)) if taper and n > 2 else 1.0
        hw = w / 2 * max(0.15, k)
        L.append((x + nx * hw, y + ny * hw)); R.append((x - nx * hw, y - ny * hw))
    return poly(L + R[::-1])


def bezier_pts(p0, p1, p2, p3, n=16):
    out = []
    for i in range(n + 1):
        t = i / n; u = 1 - t
        out.append((u**3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t**3 * p3[0],
                    u**3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t**3 * p3[1]))
    return out


# ---------------------------------------------------------------- 光效
def star(n, ro, ri, ang0=-90):
    pts = []
    for i in range(2 * n):
        r = ro if i % 2 == 0 else ri
        a = math.radians(ang0 + i * 180 / n)
        pts.append((r * math.cos(a), r * math.sin(a)))
    return poly(pts)


def sparkle(r):
    """四角星（内凹贝塞尔）"""
    k = r * 0.12
    return (f"m 0 {f(-r)} b {f(k)} {f(-k)} {f(k)} {f(-k)} {f(r)} 0 b {f(k)} {f(k)} {f(k)} {f(k)} 0 {f(r)} "
            f"b {f(-k)} {f(k)} {f(-k)} {f(k)} {f(-r)} 0 b {f(-k)} {f(-k)} {f(-k)} {f(-k)} 0 {f(-r)} ")


def streak(L, th):
    return (f"m {f(-L/2)} 0 b {f(-L*0.2)} {f(-th)} {f(L*0.2)} {f(-th)} {f(L/2)} 0 "
            f"b {f(L*0.2)} {f(th*0.35)} {f(-L*0.2)} {f(th*0.35)} {f(-L/2)} 0 ")


# ---------------------------------------------------------------- 自然物
def heart(s):
    return (f"m 0 {f(s*0.35)} b {f(-s*0.9)} {f(-s*0.2)} {f(-s*0.45)} {f(-s*0.95)} 0 {f(-s*0.4)} "
            f"b {f(s*0.45)} {f(-s*0.95)} {f(s*0.9)} {f(-s*0.2)} 0 {f(s*0.35)} ")


def petal(s):
    return f"m 0 {f(-s)} b {f(s*0.55)} {f(-s*0.6)} {f(s*0.45)} {f(s*0.5)} 0 {f(s)} b {f(-s*0.45)} {f(s*0.5)} {f(-s*0.55)} {f(-s*0.6)} 0 {f(-s)} "


def sakura(s):
    """五瓣花（瓣尖带缺口）"""
    out = ""
    for i in range(5):
        a = math.radians(-90 + i * 72)
        base = [(0, 0), (-s * 0.32, -s * 0.45), (-s * 0.22, -s * 0.95), (0, -s * 0.82), (s * 0.22, -s * 0.95), (s * 0.32, -s * 0.45)]
        out += poly(rot(base, a + math.pi / 2))
    return out


def flower(s, n=6):
    out = ""
    for i in range(n):
        a = i * 2 * math.pi / n
        pts = [(0, 0)] + [(s * 0.5 * math.sin(t * math.pi) * 0.55 * (1 if j < 7 else -1), -s * t) for j, t in
                          enumerate([0.1, 0.3, 0.5, 0.7, 0.85, 0.95, 1.0])]
        pts = [(0, 0), (s * 0.28, -s * 0.35), (s * 0.3, -s * 0.7), (0, -s), (-s * 0.3, -s * 0.7), (-s * 0.28, -s * 0.35)]
        out += poly(rot(pts, a))
    return out + ellipse(s * 0.22, s * 0.22, ccw=True)


def leaf(s):
    return (f"m 0 {f(-s)} b {f(s*0.6)} {f(-s*0.5)} {f(s*0.5)} {f(s*0.5)} 0 {f(s)} "
            f"b {f(-s*0.5)} {f(s*0.5)} {f(-s*0.6)} {f(-s*0.5)} 0 {f(-s)} ")


def maple(s):
    pts = []
    rs = [1.0, 0.45, 0.8, 0.42, 0.62, 0.3, 0.2, 0.3, 0.62, 0.42, 0.8, 0.45]
    for i, r in enumerate(rs):
        a = math.radians(-90 + i * 30)
        pts.append((s * r * math.cos(a), s * r * math.sin(a)))
    return poly(pts) + rect(s * 0.08, s * 0.5, 0, s * 0.45)


def teardrop(s):
    return (f"m 0 {f(-s)} b {f(s*0.2)} {f(-s*0.5)} {f(s*0.55)} {f(-s*0.05)} {f(s*0.55)} {f(s*0.3)} "
            f"b {f(s*0.55)} {f(s*0.65)} {f(s*0.28)} {f(s*0.85)} 0 {f(s*0.85)} "
            f"b {f(-s*0.28)} {f(s*0.85)} {f(-s*0.55)} {f(s*0.65)} {f(-s*0.55)} {f(s*0.3)} "
            f"b {f(-s*0.55)} {f(-s*0.05)} {f(-s*0.2)} {f(-s*0.5)} 0 {f(-s)} ")


def flame(s, lean=0.0):
    t = lean * s
    return (f"m {f(t)} {f(-s)} b {f(t+s*0.15)} {f(-s*0.5)} {f(s*0.55)} {f(-s*0.2)} {f(s*0.45)} {f(s*0.35)} "
            f"b {f(s*0.38)} {f(s*0.75)} {f(s*0.15)} {f(s*0.9)} 0 {f(s*0.9)} "
            f"b {f(-s*0.15)} {f(s*0.9)} {f(-s*0.38)} {f(s*0.75)} {f(-s*0.45)} {f(s*0.35)} "
            f"b {f(-s*0.55)} {f(-s*0.2)} {f(t-s*0.1)} {f(-s*0.45)} {f(t)} {f(-s)} ")


def feather(s):
    """羽毛：弯曲羽片 + 羽轴"""
    body = (f"m 0 {f(-s)} b {f(s*0.32)} {f(-s*0.7)} {f(s*0.34)} {f(s*0.2)} {f(s*0.06)} {f(s*0.75)} "
            f"l {f(-s*0.04)} {f(s*0.75)} b {f(-s*0.3)} {f(s*0.25)} {f(-s*0.28)} {f(-s*0.65)} 0 {f(-s)} ")
    notches = ""
    for k in (-0.35, 0.05, 0.4):
        notches += poly([(s * 0.3, s * k), (s * 0.08, s * (k + 0.1)), (s * 0.3, s * (k + 0.06))])
    return body + stroke([(0, -s * 0.9), (0.02 * s, s * 0.2), (0, s * 1.05)], s * 0.035)


def snowflake(s):
    out = ""
    for i in range(6):
        a = i * math.pi / 3
        arm = [(0, 0), (0, -s)]
        out += stroke(rot(arm, a), s * 0.09)
        for d in (0.45, 0.7):
            b1 = [(0, -s * d), (s * 0.22, -s * (d + 0.2))]
            b2 = [(0, -s * d), (-s * 0.22, -s * (d + 0.2))]
            out += stroke(rot(b1, a), s * 0.07) + stroke(rot(b2, a), s * 0.07)
    return out


def wheat(s):
    """麦穗：茎 + 两列麦粒"""
    out = stroke([(0, s), (s * 0.05, 0), (0, -s)], s * 0.05)
    for i in range(6):
        y = -s * 0.85 + i * s * 0.25
        g = [(0, 0), (s * 0.12, -s * 0.12), (s * 0.1, -s * 0.28), (0, -s * 0.18)]
        out += poly(move(g, s * 0.02, y)) + poly(move([(-x, yy) for x, yy in g], -s * 0.02, y))
    return out


def bird(s, flap=0.0):
    """海鸥式飞鸟；flap∈[-1,1] 控制翅膀上下"""
    up = -s * (0.35 + 0.35 * flap)
    return (f"m {f(-s)} {f(up)} b {f(-s*0.6)} {f(-s*0.35)} {f(-s*0.2)} {f(-s*0.2)} 0 {f(s*0.12)} "
            f"b {f(s*0.2)} {f(-s*0.2)} {f(s*0.6)} {f(-s*0.35)} {f(s)} {f(up)} "
            f"b {f(s*0.6)} {f(-s*0.2)} {f(s*0.2)} {f(-s*0.05)} 0 {f(s*0.3)} "
            f"b {f(-s*0.2)} {f(-s*0.05)} {f(-s*0.6)} {f(-s*0.2)} {f(-s)} {f(up)} ")


def cloud(s):
    return (circle(s * 0.45, -s * 0.45, 0) + circle(s * 0.6, 0, -s * 0.2) + circle(s * 0.45, s * 0.5, 0.05 * s)
            + rect(s * 1.4, s * 0.5, 0, s * 0.2))
