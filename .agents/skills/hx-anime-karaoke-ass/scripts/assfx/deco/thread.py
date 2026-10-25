# -*- coding: utf-8 -*-
"""
两根线的一生  全曲唯一的视觉系统（繋ぐ + 絆）。

## 主题推导（不是从菜单里挑意境）
三句题眼构成一个论证：
    71.45s  縁がいつか名前変えても    联系会被改名
    80.14s  変わらず呼ぶよ絆と        但我仍旧这样称呼它
   188.65s  微笑んできっと固い縁が    那份缘最终是牢固的
主张：**联系不是被发现的，是被命名的。**

## 视觉系统
全曲只有【两根线】。它们的关系就是这首歌在讲的事：
    sep    分离  各自漂动（失去双亲后的两人）
    near   靠近  被彼此吸引
    twist  缠绕  成为一股（不被命名，只是缠着）
    tied   打结  被命名了，所以固定下来  <- 全曲终点
    loose  拆散  名字被拿走的瞬间
    sink   下沉  一起沉进水里（水下段）

这套东西**脱离 MV 也成立**：两根线靠近→缠绕→分离→再聚→打结，
本身就是完整叙事。MV 只是让它在对应的画面里发生。
"""


def _wave(y, x0, x1, cx_off, amp, phase, n=30):
    """一条水平波动的线"""
    import math
    pts = []
    for i in range(n + 1):
        u = i / n
        x = x0 + (x1 - x0) * u
        # 两端收敛到 0 振幅，中间最大  像一根被拉住的绳
        k = math.sin(math.pi * u)
        yy = y + cx_off + amp * k * math.sin(2 * math.pi * (u * 1.5 + phase))
        pts.append((x, yy))
    return pts


def _braid_pts(x0, x1, y, gap, twist, n=60):
    """两根线缠绕：各自绕中心轴转，gap 决定分开程度，twist 决定绕了几圈。

    返回 ([线A的点], [线B的点])。gap 趋近 0 时两线重合，就是「成为一股」。
    """
    import math
    A, B = [], []
    for i in range(n + 1):
        u = i / n
        x = x0 + (x1 - x0) * u
        # 缠绕包络：中间捆得紧，两端松开（像真的绳结）
        env = math.sin(math.pi * u) ** 0.6
        ang = 2 * math.pi * twist * u
        r = gap * env
        A.append((x, y + r * math.sin(ang)))
        B.append((x, y - r * math.sin(ang)))
    return A, B


def _knot_pts(cx, cy, r, turns=2.2, loops=3.0, n=72):
    """一个结（三叶结的二维投影）"""
    import math
    pts = []
    for i in range(n + 1):
        u = 2 * math.pi * turns * i / n
        x = r * (2 * math.cos(u) + math.cos(loops * u)) / 3.0
        y = r * (2 * math.sin(u) + math.sin(loops * u)) / 3.0
        pts.append((cx + x, cy + y))
    return pts


def two_threads(f, t0, t1, state, band, y=None, sep=None, colors=None, w=3.4,
                twist=2.0, alpha=18, fade_in=0.35, fade_out=0.6, seg=7, glow_c=None):
    """发射「两根线」的某个状态。这是全曲唯一的主力函数。

    state: sep / near / twist / tied / loose / sink
    sep:   两线的纵向距离（px）。sep 大 = 离得远。
    alpha: 0=完全不透明，255=透明。默认 18（很实，确保看得见）。
    """
    from assfx.draw import shapes as S
    import math
    R = f.rng
    b = band
    x0 = b[0] + (b[2] - b[0]) * 0.10
    x1 = b[0] + (b[2] - b[0]) * 0.90
    cx = (x0 + x1) / 2
    if y is None:
        y = (b[1] + b[3]) / 2
    if sep is None:
        sep = 74
    c = colors or ("#FF6E8C", "#7EC8F0")      # 暖红 + 冷蓝：两人的对位
    cg = glow_c or "#FFD0DC"
    # ---- sep：分离，各自漂动 ----
    if state == "sep":
        for k, (yy, cc) in enumerate(((y - sep / 2, c[0]), (y + sep / 2, c[1]))):
            for j in range(seg):
                tt = t0 + j * (t1 - t0) / seg
                te = tt + (t1 - t0) / seg + 0.15
                ph = R.uniform(0, 1)
                pts = _wave(yy, x0 + R.uniform(-30, 30), x1 + R.uniform(-30, 30),
                            0, 16, ph)
                f.shape(2 + k, tt, te, x0, yy, draw=S.stroke(pts, w), c1=cc,
                        a_peak=alpha, blur=0.8, c3=cg, bord=1.1,
                        extra=chr(92) * 2 + "be1.6", fade_in=fade_in, fade_out=fade_out)
        return
    # ---- near：靠近 ----
    if state == "near":
        for k in range(3):
            u = k / 3
            s = sep * (1 - 0.55 * u)
            tt = t0 + u * (t1 - t0) * 0.7
            te = t1 if k == 2 else tt + (t1 - t0) * 0.45
            for kk, cc in enumerate(c):
                yy = y + (s / 2) * (1 if kk else -1)
                pts = _wave(yy, x0, x1, 0, 14, 0.3 * k)
                f.shape(2 + kk, tt, te, x0, yy, draw=S.stroke(pts, w), c1=cc,
                        a_peak=alpha, blur=0.8, c3=cg, bord=1.1,
                        extra=chr(92) * 2 + "be1.6", fade_in=fade_in, fade_out=fade_out)
        return
    # ---- twist：缠绕 ----
    if state == "twist":
        for j in range(seg):
            tt = t0 + j * (t1 - t0) / seg
            te = tt + (t1 - t0) / seg + 0.12
            gap = 46 - j * 4
            if gap < 12: gap = 12
            A, B = _braid_pts(x0, x1, y, gap, twist)
            f.shape(2, tt, te, x0, y, draw=S.stroke(A, w), c1=c[0],
                    a_peak=alpha, blur=0.8, c3=cg, bord=1.1,
                    extra=chr(92) * 2 + "be1.6", fade_in=0.12, fade_out=0.4)
            f.shape(3, tt, te, x0, y, draw=S.stroke(B, w), c1=c[1],
                    a_peak=alpha, blur=0.8, c3=cg, bord=1.1,
                    extra=chr(92) * 2 + "be1.6", fade_in=0.12, fade_out=0.4)
        # 缠绕点上加两颗光点（两个人才成结）
        for i in range(seg // 2 + 1):
            tt = t0 + i * (t1 - t0) / max(1, seg // 2)
            u = (tt - t0) / max(0.1, t1 - t0)
            xx = x0 + (x1 - x0) * u
            env = math.sin(math.pi * u) ** 0.6
            f.shape(5, tt, tt + 0.5, xx, y - 34 * env,
                    draw=S.sparkle(4.6), c1=cg, a_peak=14, blur=1.4, c3=c[0], bord=0.9,
                    extra=chr(92) * 2 + "be1.8", fade_in=0.06, fade_out=0.35)
            f.shape(5, tt, tt + 0.5, xx, y + 34 * env,
                    draw=S.sparkle(4.6), c1=cg, a_peak=14, blur=1.4, c3=c[1], bord=0.9,
                    extra=chr(92) * 2 + "be1.8", fade_in=0.06, fade_out=0.35)
        return
    # ---- tied：打成结（全曲终点）----
    if state == "tied":
        r0 = min(78, (b[3] - b[1]) * 0.34)
        n_k = 18
        for i in range(n_k):
            tt = t0 + i * (t1 - t0) / n_k
            te = tt + (t1 - t0) / n_k + 0.15
            u = i / n_k
            r = r0 * (0.55 + 0.45 * u)
            pts = _knot_pts(cx, y, r, turns=2.2 + u * 0.8)
            f.shape(4, tt, te, cx, y, draw=S.stroke(pts, w + u * 0.6), c1=c[0],
                    a_peak=alpha, blur=0.9, c3=cg, bord=1.2,
                    extra=chr(92) * 2 + "be2.0", fade_in=0.10, fade_out=0.4)
        # 结上的两点：仍在，且更亮
        for i in range(9):
            tt = t0 + i * (t1 - t0) / 9
            for sgn in (-1, 1):
                f.shape(6, tt, tt + 0.6, cx + sgn * (r0 + 8), y,
                        draw=S.sparkle(5.4), c1="#FFF4E8", a_peak=10, blur=1.6,
                        c3=c[0] if sgn < 0 else c[1], bord=1.0,
                        extra=chr(92) * 2 + "be2.0", fade_in=0.06, fade_out=0.4)
        return
    # ---- loose：拆散 ----
    if state == "loose":
        for i in range(30):
            u = i / 29
            px = x0 + (x1 - x0) * u
            for kk, cc in enumerate(c):
                py = y + (1 if kk else -1) * R.uniform(6, 26)
                dx = R.uniform(-40, 40)
                dy = R.uniform(-34, -8) if kk == 0 else R.uniform(8, 34)
                f.shape(4, t0 + R.uniform(0, 0.8), t1,
                        px, py, px + dx, py + dy,
                        draw=S.sparkle(R.uniform(2.6, 5.4)), c1=cc,
                        a_peak=R.randint(30, 90), blur=1.4, c3=cg, bord=1.0,
                        extra=chr(92) * 2 + "be1.8", fade_in=0.2, fade_out=0.5)
        return
    # ---- sink：下沉 ----
    if state == "sink":
        for j in range(seg):
            tt = t0 + j * (t1 - t0) / seg
            te = tt + (t1 - t0) / seg + 0.2
            u = j / seg
            yy = y - 40 + 90 * u
            for kk, cc in enumerate(c):
                pts = _wave(yy + (12 if kk else -12), x0, x1, 0, 12 + 8 * u, 0.4 * j)
                f.shape(2 + kk, tt, te, x0, yy, draw=S.stroke(pts, w * (1 - 0.3 * u)),
                        c1=cc, a_peak=alpha + int(70 * u), blur=1.0 + u, c3=cg, bord=1.1,
                        extra=chr(92) * 2 + "be1.8", fade_in=0.15, fade_out=0.5)
        return
