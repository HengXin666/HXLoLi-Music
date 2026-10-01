# -*- coding: utf-8 -*-
"""
矢量绘图库（ASS \\p1 绘图代码）。所有图形以 (0,0) 为中心附近构造；配合 \\an5\\pos 使用时
libass 会把绘图包围盒中心放在 \\pos 点，旋转也绕该点。

命名约定：函数返回绘图字符串；尺寸参数 s/r 为像素（\\p1 下 1 单位 = 1px，再乘 \\fscx/\\fscy）。
镂空：外轮廓顺时针 + 内轮廓逆时针（libass 非零环绕规则）。
"""
import math, random, re

K = 0.5523


def f(v):
    return f"{v:.1f}".rstrip("0").rstrip(".") if abs(v) < 1e5 else str(int(v))


def poly(pts, close=True):
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


# ---------------------------------------------------------------- 基本形
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


# ---------------------------------------------------------------- 破坏 / 战斗
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
    """洛琪希的魔女帽：宽帽檐 + 弯折的尖顶"""
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
    """瑞杰路德额头宝石般的“红眼”环：杏仁形眼 + 瞳"""
    return (f"m {f(-r)} 0 b {f(-r*0.5)} {f(-r*0.62)} {f(r*0.5)} {f(-r*0.62)} {f(r)} 0 "
            f"b {f(r*0.5)} {f(r*0.62)} {f(-r*0.5)} {f(r*0.62)} {f(-r)} 0 "
            + ellipse(r * 0.8, r * 0.36, ccw=True) + circle(r * 0.28))


def compass(s):
    out = ring(s, s * 0.06)
    out += poly([(0, -s * 0.92), (s * 0.12, 0), (0, s * 0.92), (-s * 0.12, 0)])
    out += poly([(-s * 0.92, 0), (0, -s * 0.1), (s * 0.92, 0), (0, s * 0.1)])
    return out


# ---------------------------------------------------------------- 工具
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
    代替 \\frx 倾斜——libass 透视距离只有 ~312px，大图形用 \\frx 会严重畸变甚至翻到镜头后。"""
    r = math.radians(angle); cs, sn = math.cos(r), math.sin(r)
    return affine(d, cs, -sn, sn * squash, cs * squash)


def bbox(d):
    """绘图坐标包围盒 (x0, y0, x1, y1)"""
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


# ================================================================ 田园 / 夏日 / 羁绊（ヨスガノソラ OP）
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
    """比翼：左右一对翅膀（中间可留 gap）"""
    return affine(wing(s, spread), 1, 0, 0, 1, gap / 2, 0) + affine(wing(s, spread), -1, 0, 0, 1, -gap / 2, 0)


def rabbit(s):
    """兔子玩偶剪影（穹的兔子）：圆脸 + 两只垂耳 + 小身体"""
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
    """鸟居（天女目神社）"""
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
    """波子汽水瓶（颈部收腰 + 玻璃珠）"""
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


# ================================================================ 运动会 / 部落 / 元气（ピンキージョーンズ ED）
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
    """あんパン（圆面包 + 顶部芝麻点）"""
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
