# -*- coding: utf-8 -*-
"""破坏/战斗与魔法/学识: 硬边、放射、同心环一类"有攻击性/仪式感"的母题."""
import math
import random
import re

from assfx.draw.kit.prims import K, f, poly, rot, move, scale   # noqa: F401
from assfx.draw.kit.nature import (arc, bezier_pts, circle, ellipse, ellipse_ring, flame,   # noqa: F401
                              rect, ring, star, stroke)
from assfx.draw.kit.prims import translate as _translate   # noqa: F401


def shard(rng, s):
    n = rng.randint(3, 5)
    angs = sorted(rng.uniform(0, 2 * math.pi) for _ in range(n))
    return poly([(s * rng.uniform(0.45, 1.0) * math.cos(a), s * rng.uniform(0.45, 1.0) * math.sin(a)) for a in angs])


def crack(rng, L, w, branches=3):
    """裂纹：主干折线 + 分叉（全部是细三角条）"""
    pts = [(-L / 2, 0)]
    n = 7
    for i in range(1, n + 1):
        pts.append((-L / 2 + L * i / n, rng.uniform(-L * 0.07, L * 0.07)))
    out = stroke(pts, w, taper=True)
    for _ in range(branches):
        i = rng.randint(1, n - 1); x, y = pts[i]
        a = rng.uniform(-2.3, -0.8) if rng.random() < 0.5 else rng.uniform(0.8, 2.3)
        l = L * rng.uniform(0.1, 0.22)
        out += stroke([(x, y), (x + l * 0.5 * math.cos(a) + rng.uniform(-3, 3), y + l * 0.5 * math.sin(a)),
                       (x + l * math.cos(a), y + l * math.sin(a))], w * 0.7, taper=True)
    return out


def bolt(rng, L, w):
    pts = [(0, -L / 2)]
    for i in range(1, 6):
        pts.append((rng.uniform(-L * 0.15, L * 0.15), -L / 2 + L * i / 6))
    pts.append((0, L / 2))
    return stroke(pts, w, taper=True)


def slash(L, th):
    """刀光：弯月形"""
    return (f"m {f(-L/2)} 0 b {f(-L/4)} {f(-th)} {f(L/4)} {f(-th)} {f(L/2)} 0 "
            f"b {f(L/4)} {f(-th*0.45)} {f(-L/4)} {f(-th*0.45)} {f(-L/2)} 0 ")


def sword(L):
    w = L * 0.045
    blade = poly([(-w, -L * 0.28), (-w, L * 0.42), (0, L * 0.5), (w, L * 0.42), (w, -L * 0.28)])
    guard = rect(L * 0.26, L * 0.035, 0, -L * 0.3)
    grip = rect(w * 1.3, L * 0.16, 0, -L * 0.4)
    pommel = circle(w * 1.2, 0, -L * 0.49)
    return blade + guard + grip + pommel


def chain_link(s, w=None):
    w = w or s * 0.16
    return ellipse(s, s * 0.55) + ellipse(s - w, s * 0.55 - w, ccw=True)


def chain(n, s, gap=None):
    """一串交错的链环（水平），返回绘图"""
    gap = gap or s * 1.45
    out = ""
    x0 = -(n - 1) * gap / 2
    for i in range(n):
        if i % 2 == 0:
            out += _translate(chain_link(s), x0 + i * gap, 0)
        else:
            out += _translate(ellipse(s * 1.05, s * 0.2) + ellipse(s * 0.8, s * 0.07, ccw=True), x0 + i * gap, 0)
    return out


def shield(s):
    return (f"m 0 {f(-s)} b {f(s*0.4)} {f(-s*0.75)} {f(s*0.75)} {f(-s*0.8)} {f(s*0.85)} {f(-s*0.8)} "
            f"b {f(s*0.9)} {f(s*0.1)} {f(s*0.5)} {f(s*0.7)} 0 {f(s)} "
            f"b {f(-s*0.5)} {f(s*0.7)} {f(-s*0.9)} {f(s*0.1)} {f(-s*0.85)} {f(-s*0.8)} "
            f"b {f(-s*0.75)} {f(-s*0.8)} {f(-s*0.4)} {f(-s*0.75)} 0 {f(-s)} ")


# ---------------------------------------------------------------- 魔法 / 学识
def magic_circle(r, rng=None, spokes=6):
    """魔法阵：外双环 + 刻度 + 六芒星 + 内环（全部为镂空笔画）"""
    out = ring(r, r * 0.035) + ring(r * 0.88, r * 0.02)
    for i in range(48):
        a = math.radians(i * 7.5)
        l = r * (0.07 if i % 4 else 0.12)
        out += stroke([((r * 0.94) * math.cos(a), (r * 0.94) * math.sin(a)), ((r * 0.94 - l) * math.cos(a), (r * 0.94 - l) * math.sin(a))], r * 0.012)
    tri = [(r * 0.78 * math.cos(math.radians(-90 + i * 120)), r * 0.78 * math.sin(math.radians(-90 + i * 120))) for i in range(4)]
    out += stroke(tri, r * 0.02) + stroke(rot(tri, math.pi), r * 0.02)
    out += ring(r * 0.42, r * 0.02)
    for i in range(spokes):
        a = math.radians(i * 360 / spokes + 30)
        out += circle(r * 0.045, r * 0.6 * math.cos(a), r * 0.6 * math.sin(a))
    return out


def rune_ring(r, n=24, w=None, rng=None):
    """符文环：一圈长短不一的弧段"""
    rng = rng or random.Random(3)
    w = w or r * 0.06
    out = ""
    a = 0
    while a < 360:
        l = rng.uniform(4, 14)
        out += arc(r, a, a + l, w, n=3)
        a += l + rng.uniform(3, 9)
    return out


def healing_cross(s):
    t = s * 0.34
    return poly([(-t, -s), (t, -s), (t, -t), (s, -t), (s, t), (t, t), (t, s), (-t, s), (-t, t), (-s, t), (-s, -t), (-t, -t)])


def witch_hat(s):
    """魔女帽：宽帽檐 + 弯折的尖顶"""
    brim = ellipse(s, s * 0.22, 0, s * 0.35)
    cone = (f"m {f(-s*0.45)} {f(s*0.32)} b {f(-s*0.35)} {f(-s*0.2)} {f(-s*0.1)} {f(-s*0.7)} {f(s*0.25)} {f(-s*0.85)} "
            f"b {f(s*0.45)} {f(-s*0.95)} {f(s*0.6)} {f(-s*0.75)} {f(s*0.7)} {f(-s*0.62)} "
            f"b {f(s*0.45)} {f(-s*0.68)} {f(s*0.2)} {f(-s*0.55)} {f(s*0.12)} {f(-s*0.35)} "
            f"b {f(s*0.2)} {f(-s*0.1)} {f(s*0.35)} {f(s*0.15)} {f(s*0.45)} {f(s*0.32)} ")
    return brim + cone


def book(s, open_=1.0):
    """摊开的书：两页弧形 + 书脊"""
    h = s * 0.62; lift = s * 0.12 * open_
    L = (f"m 0 {f(-h*0.4)} b {f(-s*0.35)} {f(-h*0.4-lift*2)} {f(-s*0.7)} {f(-h*0.5-lift)} {f(-s)} {f(-h*0.45)} "
         f"l {f(-s)} {f(h*0.55)} b {f(-s*0.7)} {f(h*0.5-lift)} {f(-s*0.35)} {f(h*0.55-lift*2)} 0 {f(h*0.62)} ")
    R = (f"m 0 {f(-h*0.4)} l 0 {f(h*0.62)} b {f(s*0.35)} {f(h*0.55-lift*2)} {f(s*0.7)} {f(h*0.5-lift)} {f(s)} {f(h*0.55)} "
         f"l {f(s)} {f(-h*0.45)} b {f(s*0.7)} {f(-h*0.5-lift)} {f(s*0.35)} {f(-h*0.4-lift*2)} 0 {f(-h*0.4)} ")
    return L + R


def page(s):
    return (f"m 0 {f(-s*0.7)} b {f(s*0.3)} {f(-s*0.8)} {f(s*0.6)} {f(-s*0.75)} {f(s*0.8)} {f(-s*0.72)} "
            f"l {f(s*0.8)} {f(s*0.7)} b {f(s*0.6)} {f(s*0.65)} {f(s*0.3)} {f(s*0.7)} 0 {f(s*0.8)} ")


def candle_flame(s):
    return flame(s) + ellipse(s * 0.18, s * 0.35, 0, s * 0.35, ccw=True)


def thread(p0, p1, sag, w):
    """两点间下垂的线（红线/缘）"""
    mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2 + sag
    pts = bezier_pts(p0, (p0[0] * 0.5 + mx * 0.5, my), (p1[0] * 0.5 + mx * 0.5, my), p1, 24)
    return stroke(pts, w)


def sunburst(n, L, w, spread=140, a0=-90):
    """扇形光芒：n 条细长三角从同一点向外辐射（spread 为总张角，a0 为中心方向，-90=向上）"""
    out = ""
    for i in range(n):
        a = math.radians(a0 - spread / 2 + spread * i / max(1, n - 1))
        tip = (L * math.cos(a), L * math.sin(a)); nx, ny = -math.sin(a) * w / 2, math.cos(a) * w / 2
        out += poly([(nx * 0.2, ny * 0.2), (tip[0] + nx, tip[1] + ny), (tip[0] - nx, tip[1] - ny), (-nx * 0.2, -ny * 0.2)])
    return out


def ripple(rx, w):
    return ellipse_ring(rx, rx * 0.28, w)


def veil(w, h, waves=5, amp=6):
    """半透明面纱：上下沿波浪的横条"""
    top = [(-w / 2 + w * i / 40, -h / 2 + amp * math.sin(i / 40 * waves * 2 * math.pi)) for i in range(41)]
    bot = [(-w / 2 + w * i / 40, h / 2 + amp * math.sin(i / 40 * waves * 2 * math.pi + 1.3)) for i in range(40, -1, -1)]
    return poly(top + bot)


def gear_ring(r, teeth=16):
    pts = []
    for i in range(teeth * 4):
        a = i * 2 * math.pi / (teeth * 4)
        rr = r if (i // 2) % 2 == 0 else r * 0.86
        pts.append((rr * math.cos(a), rr * math.sin(a)))
    return poly(pts) + ellipse(r * 0.7, r * 0.7, ccw=True)


def eye_ring(r):
    """眼环：杏仁形眼 + 瞳（可作"注视/觉醒"母题）"""
    return (f"m {f(-r)} 0 b {f(-r*0.5)} {f(-r*0.62)} {f(r*0.5)} {f(-r*0.62)} {f(r)} 0 "
            f"b {f(r*0.5)} {f(r*0.62)} {f(-r*0.5)} {f(r*0.62)} {f(-r)} 0 "
            + ellipse(r * 0.8, r * 0.36, ccw=True) + circle(r * 0.28))


def compass(s):
    out = ring(s, s * 0.06)
    out += poly([(0, -s * 0.92), (s * 0.12, 0), (0, s * 0.92), (-s * 0.12, 0)])
    out += poly([(-s * 0.92, 0), (0, -s * 0.1), (s * 0.92, 0), (0, s * 0.1)])
    return out
