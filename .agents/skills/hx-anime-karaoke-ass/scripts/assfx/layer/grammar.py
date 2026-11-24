# -*- coding: utf-8 -*-
"""组合法: 一个母题 (形状) 按一种语法铺进一句. 母题管 "画什么", 语法管 "怎么出现", 两者正交, 换一个就是另一种语言.

所有语法都守三条 (不越界, 不压字, 层号有意义):
  * 只经 FX 发射 (band 夹取由 FX.shape 负责);
  * 画在字前面的只有短命小件 (<= 24px, <= 0.9s), 并标 Effect=over (母题压字门禁的显式豁免与兜底);
  * 大件一律画在字后面 (layer 0, 背景线), 或放在字墨迹框左右两侧的余量里 (frame / stamp).
签名统一: g(f, ph, k, shape, col, size, n, times) -> 发出的事件数. times 是本句的时刻列表 (按 clock 取, 见 compose.py).
"""
from assfx.base.core import al  # noqa: F401  (语法里写 \\alpha 时用)

OVER_PX, OVER_S = 24, 0.9


def _ink(ph):
    return ph.ink                       # (x0, y0, x1, y1) 三行墨迹的并集


def _mid(ph):
    x0, y0, x1, y1 = _ink(ph)
    return (x0 + x1) / 2, (y0 + y1) / 2


def halo(f, ph, k, shape, col, size, n, times):
    """主母题放大成一枚, 垫在整句后面慢慢显出 (背景线, layer 0)."""
    cx, cy = _mid(ph)
    s = min(size * 3.2, (ph.band[3] - ph.band[1]) * 0.9)
    f.shape(0, k.t_in, k.t_end, cx, cy, draw=shape(s), c1=col, a_peak=175, blur=6, fade_in=0.6, fade_out=0.6,
            extra="\\fscx90\\fscy90\\t(0,%d,\\fscx100\\fscy100)" % int((k.t_end - k.t_in) * 1000))
    return 1


def orbit(f, ph, k, shape, col, size, n, times):
    """n 个小母题绕句中心转半圈 (layer 0, 在字后). 半径取墨迹框半高, 不会甩出 band (FX.shape 再夹一次)."""
    cx, cy = _mid(ph)
    x0, y0, x1, y1 = _ink(ph)
    r = max(24.0, (y1 - y0) / 2 + size / 2)
    for j in range(n):
        a0 = 360.0 * j / max(1, n)
        f.orbit(0, k.t_in, k.t_end, cx, cy, r, r, shape(size), c1=col, a_peak=120, turns=0.0,
                n=12, arc0=a0, arc1=a0 + 180.0, be=1.0)
    return n


def rise(f, ph, k, shape, col, size, n, times):
    """每个时刻从字下方升起一个小件, 到字上方消失 (字前, 小而短 -> over)."""
    x0, y0, x1, y1 = _ink(ph)
    sz = min(size, OVER_PX)
    sent = 0
    for t in times[::max(1, len(times) // max(1, n))][:n]:
        x = f.rng.uniform(x0, x1)
        f.shape(7, t, t + OVER_S, x, y1 + 6, x + f.rng.uniform(-12, 12), y0 - 6, draw=shape(sz), c1=col, a_peak=60,
                blur=0.8, fade_in=0.08, fade_out=0.5, effect="over")
        sent += 1
    return sent


def fall(f, ph, k, shape, col, size, n, times):
    """母题从上往下飘 (雪 / 花瓣 / 灰), 整句持续 (字后, layer 0)."""
    f.drift(k.t_in, k.t_end, n, [col], shape, vx=(-12, 12), vy=(14, 34), size=(size * 0.6, size), a=(40, 120), layer=0)
    return n


def scatter(f, ph, k, shape, col, size, n, times):
    """每个时刻在被唱到的字边迸出两颗 (字前, 小而短 -> over)."""
    import math
    cy = (ph.chars[0].get("y") or _mid(ph)[1]) if ph.chars else _mid(ph)[1]
    cs = [c for c in ph.chars if c.get("kind") != "punct"]
    sent = 0
    for c in cs[::max(1, len(cs) // max(1, n))][:n]:
        for _ in range(2):
            a = f.rng.uniform(0, 2 * math.pi)
            f.shape(8, c["s"], c["s"] + 0.6, c["x"], cy, c["x"] + math.cos(a) * 26, cy + math.sin(a) * 18,
                    draw=shape(min(size * 0.5, 14)), c1=col, a_peak=40, blur=0.6, fade_in=0.04, fade_out=0.4,
                    effect="over")
            sent += 1
    return sent


def trail(f, ph, k, shape, col, size, n, times):
    """一串母题沿字带上沿, 跟着唱到的位置往右铺 (字后, layer 0)."""
    x0, y0, x1, y1 = _ink(ph)
    cs = [c for c in ph.chars if c.get("kind") != "punct"]
    step = max(1, len(cs) // max(1, n))
    for c in cs[::step][:n]:
        f.shape(0, c["s"], k.t_end, c["x"], y0 - 4, draw=shape(size * 0.8), c1=col, a_peak=150, blur=2,
                fade_in=0.25, fade_out=0.5)
    return len(cs[::step][:n])


def frame(f, ph, k, shape, col, size, n, times):
    """左右各一枚 (镜像), 落在墨迹框外侧的余量里, 像括号把整句框住."""
    x0, y0, x1, y1 = _ink(ph)
    cy = (y0 + y1) / 2
    gap = 8 + size / 2 + 4
    for x, mir in ((x0 - gap, "\\fscx-100"), (x1 + gap, "")):
        f.shape(3, k.t_in, k.t_end, x, cy, draw=shape(size), c1=col, a_peak=60, blur=1.0, fade_in=0.4, fade_out=0.5,
                extra=mir)
    return 2


def stamp(f, ph, k, shape, col, size, n, times):
    """句首在左侧余量盖一枚, 随第一个强拍脉冲一次 (主母题的 "署名")."""
    x0, y0, x1, y1 = _ink(ph)
    t = times[0] if times else ph.s
    x = x0 - 8 - size / 2 - 4
    f.shape(3, k.t_in, k.t_end, x, (y0 + y1) / 2, draw=shape(size), c1=col, a_peak=40, blur=0.8, fade_in=0.3, fade_out=0.5)
    f.shape(0, t, t + 0.6, x, (y0 + y1) / 2, draw=shape(size * 1.6), c1=col, a_peak=150, blur=6, fade_in=0.05, fade_out=0.5)
    return 2


GRAMMAR = dict(halo=halo, orbit=orbit, rise=rise, fall=fall, scatter=scatter, trail=trail, frame=frame, stamp=stamp)
