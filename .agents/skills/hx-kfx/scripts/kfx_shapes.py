"""Vector motifs as ASS drawing paths.

Every shape is drawn inside the box (0,0)-(2r,2r) (or its own w,h) so that
\\an5\\pos(x,y) is its real centre and \\frz spins it in place.
Holes are drawn with the opposite winding (libass fills non-zero).
"""
from __future__ import annotations

import math


def _n(v: float) -> str:
    s = f"{v:.1f}"
    return s[:-2] if s.endswith(".0") else s


def poly(pts, close=True) -> str:
    head = f"m {_n(pts[0][0])} {_n(pts[0][1])} l "
    return head + " ".join(f"{_n(x)} {_n(y)}" for x, y in pts[1:])


def _rot(pts, a, cx, cy):
    c, s = math.cos(a), math.sin(a)
    return [(cx + (x - cx) * c - (y - cy) * s, cy + (x - cx) * s + (y - cy) * c) for x, y in pts]


def circle(r: float, cx=None, cy=None, ccw=False) -> str:
    cx = r if cx is None else cx
    cy = r if cy is None else cy
    k = 0.5523 * r
    if not ccw:
        return (f"m {_n(cx)} {_n(cy - r)} b {_n(cx + k)} {_n(cy - r)} {_n(cx + r)} {_n(cy - k)} {_n(cx + r)} {_n(cy)} "
                f"b {_n(cx + r)} {_n(cy + k)} {_n(cx + k)} {_n(cy + r)} {_n(cx)} {_n(cy + r)} "
                f"b {_n(cx - k)} {_n(cy + r)} {_n(cx - r)} {_n(cy + k)} {_n(cx - r)} {_n(cy)} "
                f"b {_n(cx - r)} {_n(cy - k)} {_n(cx - k)} {_n(cy - r)} {_n(cx)} {_n(cy - r)}")
    return (f"m {_n(cx)} {_n(cy - r)} b {_n(cx - k)} {_n(cy - r)} {_n(cx - r)} {_n(cy - k)} {_n(cx - r)} {_n(cy)} "
            f"b {_n(cx - r)} {_n(cy + k)} {_n(cx - k)} {_n(cy + r)} {_n(cx)} {_n(cy + r)} "
            f"b {_n(cx + k)} {_n(cy + r)} {_n(cx + r)} {_n(cy + k)} {_n(cx + r)} {_n(cy)} "
            f"b {_n(cx + r)} {_n(cy - k)} {_n(cx + k)} {_n(cy - r)} {_n(cx)} {_n(cy - r)}")


def mote(r=4.0) -> str:
    return circle(r)


def sparkle(r=10.0) -> str:
    """four-point star with concave sides (light glint)."""
    c, k = r, r * 0.18
    return (f"m {_n(c)} 0 b {_n(c + k)} {_n(c - k)} {_n(c + k)} {_n(c - k)} {_n(2 * c)} {_n(c)} "
            f"b {_n(c + k)} {_n(c + k)} {_n(c + k)} {_n(c + k)} {_n(c)} {_n(2 * c)} "
            f"b {_n(c - k)} {_n(c + k)} {_n(c - k)} {_n(c + k)} 0 {_n(c)} "
            f"b {_n(c - k)} {_n(c - k)} {_n(c - k)} {_n(c - k)} {_n(c)} 0")


def snowflake(r=11.0) -> str:
    """six arms, each with a pair of side barbs."""
    parts = []
    c = r
    arm = [(c - r * 0.07, c), (c - r * 0.07, c - r), (c + r * 0.07, c - r), (c + r * 0.07, c)]
    barb = [(c - r * 0.05, c - r * 0.55), (c - r * 0.38, c - r * 0.82), (c - r * 0.31, c - r * 0.89),
            (c + r * 0.0, c - r * 0.66)]
    barb2 = [(x if i in (0, 3) else 2 * c - x, y) for i, (x, y) in enumerate(barb)]
    barb2 = [(2 * c - x, y) for x, y in barb]
    for i in range(6):
        a = i * math.pi / 3
        parts.append(poly(_rot(arm, a, c, c)))
        parts.append(poly(_rot(barb, a, c, c)))
        parts.append(poly(_rot(barb2[::-1], a, c, c)[::-1]))
    return " ".join(parts)


def leaf(r=12.0) -> str:
    """almond leaf with a slight asymmetric belly; tip at the top."""
    w, h = r * 1.1, r * 2
    return (f"m {_n(w / 2)} 0 b {_n(w * 1.05)} {_n(h * 0.3)} {_n(w * 0.95)} {_n(h * 0.75)} {_n(w / 2)} {_n(h)} "
            f"b {_n(w * 0.02)} {_n(h * 0.72)} {_n(-w * 0.05)} {_n(h * 0.3)} {_n(w / 2)} 0")


def petal(r=10.0) -> str:
    """rounded petal with a notch at the top (cherry/flower-field petal)."""
    w, h = r * 1.4, r * 2
    m = w / 2
    return (f"m {_n(m)} {_n(h * 0.16)} b {_n(m + w * 0.12)} 0 {_n(w)} {_n(h * 0.04)} {_n(w)} {_n(h * 0.42)} "
            f"b {_n(w)} {_n(h * 0.75)} {_n(m + w * 0.1)} {_n(h)} {_n(m)} {_n(h)} "
            f"b {_n(m - w * 0.1)} {_n(h)} 0 {_n(h * 0.75)} 0 {_n(h * 0.42)} "
            f"b 0 {_n(h * 0.04)} {_n(m - w * 0.12)} 0 {_n(m)} {_n(h * 0.16)}")


def droplet(r=8.0) -> str:
    """teardrop, point up."""
    w, h = r * 1.5, r * 2.2
    m = w / 2
    return (f"m {_n(m)} 0 b {_n(m + w * 0.15)} {_n(h * 0.3)} {_n(w)} {_n(h * 0.5)} {_n(w)} {_n(h * 0.7)} "
            f"b {_n(w)} {_n(h * 0.9)} {_n(m + w * 0.25)} {_n(h)} {_n(m)} {_n(h)} "
            f"b {_n(m - w * 0.25)} {_n(h)} 0 {_n(h * 0.9)} 0 {_n(h * 0.7)} "
            f"b 0 {_n(h * 0.5)} {_n(m - w * 0.15)} {_n(h * 0.3)} {_n(m)} 0")


def ember(r=6.0) -> str:
    """slim flame-tongue diamond."""
    return poly([(r * 0.5, 0), (r, r * 1.3), (r * 0.5, r * 2.6), (0, r * 1.3)])


def shard(r=12.0, seed=0) -> str:
    """irregular glass/ice shard (deterministic by seed)."""
    import random
    rnd = random.Random(seed)
    n = rnd.choice([3, 4])
    pts = []
    for i in range(n):
        a = i * 2 * math.pi / n + rnd.uniform(-0.35, 0.35)
        d = r * rnd.uniform(0.55, 1.0)
        pts.append((r + d * math.cos(a), r + d * math.sin(a)))
    return poly(pts)


def ring(r=200.0, width=3.0, ticks=24, tick_len=10.0, inner=0.78) -> str:
    """magic circle: outer band, inner band, rune ticks between (ring holes via ccw)."""
    out = [circle(r, r, r), circle(r - width, r, r, ccw=True),
           circle(r * inner, r, r), circle(r * inner - width * 0.8, r, r, ccw=True)]
    for i in range(ticks):
        a = i * 2 * math.pi / ticks
        rr = r - width - 4
        L = tick_len if i % 3 else tick_len * 2.2
        bar = [(r - 1.2, r - rr), (r + 1.2, r - rr), (r + 1.2, r - rr + L), (r - 1.2, r - rr + L)]
        out.append(poly(_rot(bar, a, r, r)))
    # hexagram between the two bands
    tri_r = r * inner - 6
    for off in (0, math.pi / 3):
        tri = [(r + tri_r * math.cos(off + k * 2 * math.pi / 3 - math.pi / 2),
                r + tri_r * math.sin(off + k * 2 * math.pi / 3 - math.pi / 2)) for k in range(3)]
        for a, b in zip(tri, tri[1:] + tri[:1]):
            out.append(_bar(a, b, 1.4))
    return " ".join(out)


def _bar(a, b, t):
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dy) or 1
    nx, ny = -dy / L * t, dx / L * t
    return poly([(a[0] + nx, a[1] + ny), (b[0] + nx, b[1] + ny), (b[0] - nx, b[1] - ny), (a[0] - nx, a[1] - ny)])


def crack(length=220.0, seed=0, t=1.6) -> tuple[str, float, float]:
    """jagged crack with two side branches; returns (path, w, h)."""
    import random
    rnd = random.Random(seed)
    pts = [(0.0, 30.0)]
    x = 0.0
    while x < length:
        x += rnd.uniform(14, 30)
        pts.append((min(x, length), 30 + rnd.uniform(-14, 14)))
    parts = [_bar(a, b, t * rnd.uniform(0.7, 1.2)) for a, b in zip(pts, pts[1:])]
    for k in rnd.sample(range(1, len(pts) - 1), min(2, len(pts) - 2)):
        a = pts[k]
        b = (a[0] + rnd.uniform(10, 26), a[1] + rnd.choice([-1, 1]) * rnd.uniform(12, 22))
        parts.append(_bar(a, b, t * 0.6))
    return " ".join(parts), length, 60.0


def thread(length=800.0, amp=6.0, t=1.4, waves=2.0) -> tuple[str, float, float]:
    """the red string: a gentle sine with constant thickness."""
    n = 64
    top, bot = [], []
    for i in range(n + 1):
        x = length * i / n
        y = 20 + amp * math.sin(i / n * waves * 2 * math.pi)
        top.append((x, y - t))
        bot.append((x, y + t))
    return poly(top + bot[::-1]), length, 40.0


def ray(length=520.0, w0=10.0, w1=70.0) -> tuple[str, float, float]:
    """soft light shaft (trapezoid), narrow end at the top."""
    m = w1 / 2
    return poly([(m - w0 / 2, 0), (m + w0 / 2, 0), (w1, length), (0, length)]), w1, length


def rect(w: float, h: float) -> str:
    return poly([(0, 0), (w, 0), (w, h), (0, h)])


MOTIFS = {
    "mote": lambda r, seed=0: mote(r * 0.4),
    "sparkle": lambda r, seed=0: sparkle(r),
    "snow": lambda r, seed=0: snowflake(r),
    "leaf": lambda r, seed=0: leaf(r),
    "petal": lambda r, seed=0: petal(r),
    "droplet": lambda r, seed=0: droplet(r * 0.8),
    "ember": lambda r, seed=0: ember(r * 0.55),
    "shard": lambda r, seed=0: shard(r, seed),
}
