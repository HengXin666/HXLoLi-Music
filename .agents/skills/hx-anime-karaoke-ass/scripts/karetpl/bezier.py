# -*- coding: utf-8 -*-
"""贝塞尔等速采样  原程序 `bezier_n_uniform_speed` 的 Python 等价实现。

为什么需要：ASS 没有"沿路径运动"的语法。原程序把曲线按**弧长**均匀采样成若干点，
每点放一颗静止半透明的粒子，靠视觉暂留连成线（实测某成品 30328 次 \\move 里
28113 次起点=终点，就是这个手法）。

表的索引是 **1-based**（Lua 表从 1 开始）。写成 0-based 会整体错位 
实测 `meteor` 全为 0，爆发段不展开。
"""
import math


GAUSS_X = [
    -0.9931285991850940, -0.9639719272779130, -0.9122344282513260, -0.8391169718222180,
    -0.7463319064601500, -0.6360536807265150, -0.5108670019508270, -0.3737060887154190,
    -0.2277858511416450, -0.0765265211334973, 0.0765265211334973, 0.2277858511416450,
    0.3737060887154190, 0.5108670019508270, 0.6360536807265150, 0.7463319064601500,
    0.8391169718222180, 0.9122344282513260, 0.9639719272779130, 0.9931285991850940,
]
GAUSS_W = [
    0.0176140071391521, 0.0406014298003689, 0.0626720483341090, 0.0832767415767047,
    0.1019301198172400, 0.1181945319615180, 0.1316886384491760, 0.1420961093183820,
    0.1491729864726030, 0.1527533871307250, 0.1527533871307250, 0.1491729864726030,
    0.1420961093183820, 0.1316886384491760, 0.1181945319615180, 0.1019301198172400,
    0.0832767415767047, 0.0626720483341090, 0.0406014298003689, 0.0176140071391521,
]

def _combin(n, k):
    return math.comb(n, k)


def comp_arg(a, b):
    if a > 0:
        return math.atan(b / a)
    if a < 0 and b != 0:
        return math.pi * abs(b) / b + math.atan(b / a)
    if a < 0 and b == 0:
        return math.pi
    if a == 0 and b != 0:
        return math.pi * (abs(b) / b) / 2
    return 0.0


def _v(tbl, i1):
    """1-based 取值：Lua 的表从 1 开始，原程序传进来的是 1-based table。"""
    if isinstance(tbl, dict):
        return tbl.get(i1, tbl.get(i1 - 1, 0.0))
    return tbl[i1 - 1]


def bezier_position(tbl, t):
    """Bernstein 多项式；tbl 是 1-based（tbl[1] 是起点）。"""
    n = _n_of(tbl)
    return sum(_v(tbl, i + 1) * _combin(n, i) * (t ** i) * ((1 - t) ** (n - i))
               for i in range(n + 1))


def _n_of(tbl):
    if isinstance(tbl, dict):
        ints = [k for k in tbl if isinstance(k, int)]
        return (max(ints) if ints else 1) - 1
    return len(tbl) - 1


def bezier_n_derivatives(tbl, t):
    """一阶导数；tbl 是 1-based。"""
    n = _n_of(tbl)
    der = 0.0
    for i in range(1, n):
        der += (_combin(n, i) * _v(tbl, i + 2) * ((1 - t) ** (n - i - 1))
                * (t ** (i - 1)) * (i - n * t))
    der -= _v(tbl, 1) * n * ((1 - t) ** (n - 1))
    der += _v(tbl, n + 1) * n * (t ** (n - 1))
    return der


def bezier_n_speed(x_tbl, y_tbl, t):
    dx = bezier_n_derivatives(x_tbl, t)
    dy = bezier_n_derivatives(y_tbl, t)
    return math.hypot(dx, dy), dx, dy


def bezier_n_length(x_tbl, y_tbl, t):
    ln = 0.0
    for gx, gw in zip(GAUSS_X, GAUSS_W):
        ct = gx * t * 0.5 + t * 0.5
        v, _, _ = bezier_n_speed(x_tbl, y_tbl, ct)
        ln += gw * t * v / 2
    return ln


def bezier_n_t_at_percent(x_tbl, y_tbl, pct):
    length = bezier_n_length(x_tbl, y_tbl, 1)
    s = length * pct / 100
    a = pct / 100
    if a == 0 or a == 1:
        return a
    k = 0
    while True:
        k += 1
        b = a
        a = a - (bezier_n_length(x_tbl, y_tbl, a) - s) / bezier_n_speed(x_tbl, y_tbl, a)[0]
        if abs(a - b) < 0.00001 or k >= 5000:
            break
    return a


def bezier_n_uniform_speed(x_tbl, y_tbl, particle_width, a=1):
    length = bezier_n_length(x_tbl, y_tbl, 1)
    max_n = math.ceil(length / particle_width) + 1
    pos = []
    for i in range(1, max_n + 1):
        u = (i - 1) / (max_n - 1)
        t_r = bezier_n_t_at_percent(x_tbl, y_tbl, 100 * (u ** a))
        _, vx, vy = bezier_n_speed(x_tbl, y_tbl, t_r)
        _, vx1, vy1 = bezier_n_speed(x_tbl, y_tbl, u)
        deg = 0.0 if (vx == 0 and vy == 0) else math.degrees(comp_arg(vx, vy))
        deg1 = 0.0 if (vx1 == 0 and vy1 == 0) else math.degrees(comp_arg(vx1, vy1))
        pos.append(dict(x=bezier_position(x_tbl, t_r), y=bezier_position(y_tbl, t_r),
                        x1=bezier_position(x_tbl, u), y1=bezier_position(y_tbl, u),
                        deg=-deg, deg1=-deg1))
    return pos


# ----------------------------------------------------------------- 文本度量
