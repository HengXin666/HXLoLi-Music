# -*- coding: utf-8 -*-
"""
「縁」= 一条线：全曲贯穿的单一母题（对应曲名 ツナグキズナ = 主动去连 + 羁绊）。

## 为什么是这条线（主题推导，不是从菜单里挑）
三句题眼构成一个论证：
    71.45s 縁がいつか名前変えても   —— 联系会被改名
    80.14s 変わらず呼ぶよ絆と       —— 但我仍旧这样称呼它
   188.65s 微笑んできっと固い縁が   —— 那份缘最终是牢固的
核心主张：**联系不是被发现的，是被命名的。** 同一种东西，你叫它什么，它就是什么。

所以视觉上只做一件事：**同一条线，被命名后从「散」变「结」。**
它必须脱离 MV 也成立 —— 因为「一条线打上结就固定下来」本身就是自洽的小动画。
"""


def _line_pts(p0, p1, sag, n=26, jitter=0.0, rng=None):
    """两点间下垂的线（贝塞尔），可选抖动 —— jitter>0 时线是散的（未被命名）"""
    from assfx import shapes as S
    mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2 + sag
    pts = S.bezier_pts(p0, (p0[0] * 0.5 + mx * 0.5, my), (p1[0] * 0.5 + mx * 0.5, my), p1, n)
    if jitter > 0 and rng is not None:
        pts = [(x, y + rng.uniform(-jitter, jitter)) for x, y in pts]
    return pts


def _knot(cx, cy, r, loops=3.0, turns=2.4, n=64):
    """一个结：把线绕成连续的环（三叶结的二维投影）。

    这是整套设计的支点 —— 「被命名」在视觉上就是「线打成了结」。
    """
    import math
    pts = []
    for i in range(n + 1):
        u = 2 * math.pi * i / n * turns
        x = r * (2 * math.cos(u) + math.cos(loops * u)) / 3.0
        y = r * (2 * math.sin(u) + math.sin(loops * u)) / 3.0
        pts.append((cx + x, cy + y))
    return pts


def _knot_at(cx, cy, r, u_end, turns=2.4, loops=3.0, n=64):
    """结的部分轨迹（u 从 0 到 u_end/2π 圈）—— 用于「逐渐打结」的动画"""
    import math
    pts = []
    total = 2 * math.pi * turns * u_end
    m = max(2, int(n * u_end))
    for i in range(m + 1):
        u = total * i / m
        x = r * (2 * math.cos(u) + math.cos(loops * u)) / 3.0
        y = r * (2 * math.sin(u) + math.sin(loops * u)) / 3.0
        pts.append((cx + x, cy + y))
    return pts


def line_state(f, t0, t1, state, y, x0=None, x1=None, band=None, c="#E0607A",
               c2="#FFB0C4", w=2.6, seed=0):
    """把「线」按 state 发射出来。四种状态构成整首歌的叙事弧。

    state:
      'loose'   散的粒子群（联系未被命名）—— 每颗粒子各自浮沉，彼此不相连
      'thread'  完整的细线（被看见）—— 线的两端还在，中间下垂
      'knotting'线正在被打结 —— 用 knot 的部分轨迹递增，模拟绕的过程
      'knot'    结已成型并收紧变亮 —— 线的形态完全变成结，这是全曲最亮的一帧
    """
    from assfx import shapes as S
    import math
    R = f.rng
    b = band
    if x0 is None: x0 = b[0] + (b[2] - b[0]) * 0.16
    if x1 is None: x1 = b[0] + (b[2] - b[0]) * 0.84
    cx = (x0 + x1) / 2
    span = x1 - x0

    if state == "loose":
        for i in range(22):
            px = x0 + span * i / 21
            py = y + R.uniform(-16, 16)
            dx = R.uniform(-26, 26)
            dy = R.uniform(-22, -4)
            f.shape(4, t0 + R.uniform(0, 0.5), t1,
                    px, py, px + dx, py + dy,
                    draw=S.sparkle(R.uniform(2.4, 5.0)), c1=c,
                    a_peak=R.randint(60, 130), blur=1.4, c3=c2, bord=1.0,
                    fade_in=0.25, fade_out=0.5)
        return

    if state == "thread":
        for k in range(6):
            pts = _line_pts((x0, y), (x1, y), 30 + k * 3, 26, 1.6, R)
            f.shape(6, t0 + k * 0.05, t1, x0, y, draw=S.stroke(pts, w),
                    c1=c, a_peak=40 - k * 5, blur=0.6, c3=c2, bord=1.0,
                    extra=chr(92) * 2 + "be1.6", fade_in=0.3, fade_out=0.5)
        return

    if state == "knotting":
        # 线从两端向中心收，中心处逐渐绕出结
        n_steps = 16
        for i in range(n_steps):
            u = i / n_steps
            tt = t0 + (t1 - t0) * u * 0.8
            kx0 = x0 + (cx - x0) * u
            kx1 = x1 - (x1 - cx) * u
            r0 = 6 + 46 * u
            pts = _knot_at(cx, y, r0, max(0.08, u), n=48)
            f.shape(6, tt, tt + (t1 - t0) * 0.8 / n_steps + 0.05,
                    cx, y, draw=S.stroke(pts, w), c1=c,
                    a_peak=30, blur=0.7, c3=c2, bord=1.0,
                    extra=chr(92) * 2 + "be1.4", fade_in=0.05, fade_out=0.35)
            # 两端余线
            f.shape(5, tt, tt + 0.3, kx0, y, draw=S.stroke(_line_pts((kx0, y), (kx0 + 40 * (1 - u), y), 12, 10), w),
                    c1=c, a_peak=60, blur=0.6, fade_in=0.05, fade_out=0.3)
            f.shape(5, tt, tt + 0.3, kx1, y, draw=S.stroke(_line_pts((kx1, y), (kx1 - 40 * (1 - u), y), 12, 10), w),
                    c1=c, a_peak=60, blur=0.6, fade_in=0.05, fade_out=0.3)
        return

    if state == "knot":
        # 结成型：连续绕动 + 收紧 + 变亮
        r0 = 52
        for i in range(14):
            tt = t0 + i * 0.10
            u = 1.0
            pts = _knot_at(cx, y, r0 - i * 0.6, 1.0 + i * 0.06, n=56)
            a = max(20, 26 - i)
            f.shape(7, tt, tt + 1.1, cx, y, draw=S.stroke(pts, w + 0.10 * i),
                    c1=c, a_peak=a, blur=0.9, c3=c2, bord=1.2,
                    extra=chr(92) * 2 + "be2.0", fade_in=0.06, fade_out=0.45)
            # 结上两颗光点（两个人才成结）
            for sgn in (-1, 1):
                f.shape(5, tt, tt + 0.5, cx + sgn * (r0 - i), y - 18,
                        draw=S.sparkle(4.0), c1="#FFF0E0",
                        a_peak=18, blur=1.2, c3=c2, bord=0.8,
                        extra=chr(92) * 2 + "be1.8", fade_in=0.05, fade_out=0.35)
        return
