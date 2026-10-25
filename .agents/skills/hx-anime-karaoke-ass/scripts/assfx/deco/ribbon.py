# -*- coding: utf-8 -*-
"""
丝带系统  全曲唯一的视觉母题，铺在【背景层】与【字幕左右两侧】。

## 为什么改到背景层（原实现的错误）
最初把丝带塞进 band（字幕外扩 5% 的窄条），结果只能画出 240px 高的小玩意，
既看不出编织感、又被字幕压住  用户原话"画的内容本身就是垃圾"。
正确做法：丝带是**背景**，贯穿整个画面宽度，跟字幕是两个独立图层。
字幕仍在 band 内（validate_ass 照旧校验），丝带单独登记 band。

## 主题（不是从菜单里挑意境）
繋ぐ（主动去连）+ 絆。三句题眼构成论证：
    71.45s 縁がいつか名前変えても  ->  80.14s 変わらず呼ぶよ絆と  ->  188.65s 微笑んできっと固い縁が
主张：**联系不是被发现的，是被命名的。**

## 视觉语言
两条丝带，一暖一冷（两人的对位）。它们的关系就是歌在讲的事：
    sep    分离漂动   near  靠近   twist  编织成一股
    tied   打成结（终点）   loose  拆散   sink  一起下沉

## 手法的来源
参考 Aegisub 481 Examples 的专业做法：不是"画一个大图形"，
而是**把音节奇偶分组（fxgroup.A/B），每组派生一长串小元素**，
每颗元素用 random 决定位置/大小/旋转/时序  密集交织感由此而来。
本模块沿用这个思路：一次调用铺出一整条丝带（30+ 段）。
"""

import math

BS = chr(92)   # ASS 标签的反斜杠


def _ribbon(y0, y1, x0, x1, amp, freq, phase, n=34, taper=True):
    """一条丝带的中心线：从左到右，纵向在 y0..y1 之间游走。
    amp 是波动幅度，freq 是波数，phase 控制起点。
    taper=True 时两端收窄到 0  让丝带像是"被拉出来的"，不是凭空摆在画面里。
    """
    pts = []
    for i in range(n + 1):
        u = i / n
        x = x0 + (x1 - x0) * u
        env = math.sin(math.pi * u) if taper else 1.0
        yy = y0 + (y1 - y0) * u + amp * env * math.sin(2 * math.pi * (freq * u + phase))
        pts.append((x, yy))
    return pts


def _thicken(pts, w0, w1):
    """把中心线加粗成带（上下各偏移半个宽度） 比单线更像丝带"""
    from assfx.draw import shapes as S
    return S.stroke(pts, (w0 + w1) / 2)


def ribbon(f, t0, t1, state, band_full, y=None, sep=150, colors=None,
           w=9.0, alpha=26, twist=2.4, seg=30, fade_in=0.5, fade_out=0.9,
           x_frac=(0.02, 0.98), wave=46, beads=True):
    """铺一条（或两条）丝带。这是全曲唯一的主力函数。

    band_full: 画面级 band（整幅或整条横带），丝带在这里游走。
    sep:  两线的纵向间距（<0 表示已合成一股）。
    alpha: 星形粒子透明度（0 最实）。丝带本体用更实的 alpha。
    beads: 是否在丝带上撒珠光点（跟随音节的"呼吸"）。
    """
    from assfx.draw import shapes as S
    R = f.rng
    W0, W1 = band_full[0], band_full[2]
    Y0, Y1 = band_full[1], band_full[3]
    x0 = W0 + (W1 - W0) * x_frac[0]
    x1 = W0 + (W1 - W0) * x_frac[1]
    if y is None:
        y = (Y0 + Y1) / 2
    c = colors or ("#FF6E8C", "#7EC8F0")
    cg = "#FFF0F4"
    d = max(0.1, t1 - t0)

    def emit_line(pts, tt, te, cc, ww, aa, bo=1.3):
        f.shape(1, tt, te, x0, y, draw=S.stroke(pts, ww), c1=cc,
                a_peak=aa, blur=1.1, c3=cg, bord=bo,
                extra=BS * 2 + "be2.4", fade_in=fade_in, fade_out=fade_out)

    if state == "sep":
        for k, cc in enumerate(c):
            yy = y + (sep / 2) * (1 if k else -1)
            for j in range(seg):
                u = j / seg
                tt = t0 + u * d * 0.55
                te = min(t1, tt + d * 0.6)
                pts = _ribbon(yy, yy + (10 if k else -10), x0, x1,
                              wave, 1.4, 0.22 * j + k * 0.5, 30)
                emit_line(pts, tt, te, cc, w, alpha + 6)
        return

    if state == "near":
        for k, cc in enumerate(c):
            for j in range(seg // 2):
                u = j / (seg // 2)
                s = sep * (1 - 0.7 * u)
                yy = y + (s / 2) * (1 if k else -1)
                tt = t0 + u * d * 0.5
                te = min(t1, tt + d * 0.6)
                pts = _ribbon(yy, yy + (8 if k else -8), x0, x1, wave, 1.2, 0.3 * j, 28)
                emit_line(pts, tt, te, cc, w, alpha + 6)
        return

    if state == "twist":
        for j in range(seg):
            u = j / seg
            tt = t0 + u * d * 0.6
            te = min(t1, tt + d * 0.62)
            gap = max(16, sep * (1 - 0.78 * u))
            A, B = _braid(x0, x1, y, gap, twist, 44)
            emit_line(A, tt, te, c[0], w, alpha)
            emit_line(B, tt, te, c[1], w, alpha)
        return

    if state == "tied":
        r0 = min((W1 - W0) * 0.20, (Y1 - Y0) * 0.42)
        cx = (x0 + x1) / 2
        n_k = 20
        for i in range(n_k):
            u = i / n_k
            tt = t0 + u * d * 0.7
            te = min(t1, tt + d * 0.72)
            r = r0 * (0.5 + 0.5 * u)
            pts = _knot(cx, y, r, turns=2.4 + u * 1.0)
            emit_line(pts, tt, te, c[0], w + u * 1.4, alpha, bo=1.5)
        # 尾端两条仍向两侧伸出（结的两端）
        for k, cc in enumerate(c):
            sgn = -1 if k == 0 else 1
            pts = _ribbon(y, y + sgn * 14, x0 if sgn < 0 else cx, cx if sgn < 0 else x1,
                          wave * 0.6, 0.9, 0.1, 16)
            emit_line(pts, t0 + d * 0.3, t1, cc, w * 0.8, alpha + 10)
        return

    if state == "loose":
        for i in range(52):
            u = i / 51
            px = x0 + (x1 - x0) * u
            k = i % 2
            py = y + (1 if k else -1) * R.uniform(24, 90)
            dx = R.uniform(-70, 70)
            dy = (R.uniform(-70, -20) if k else R.uniform(20, 70))
            f.shape(4, t0 + R.uniform(0, 1.0), t1,
                    px, py, px + dx, py + dy,
                    draw=S.sparkle(R.uniform(5, 11)), c1=c[k],
                    a_peak=R.randint(20, 70), blur=1.8, c3=cg, bord=1.2,
                    extra=BS * 2 + "be2.2", fade_in=0.3, fade_out=0.7)
        return

    if state == "sink":
        for j in range(seg // 2):
            u = j / (seg // 2)
            tt = t0 + u * d * 0.6
            te = min(t1, tt + d * 0.65)
            yy = Y0 + (Y1 - Y0) * (0.18 + 0.72 * u)
            for k, cc in enumerate(c):
                pts = _ribbon(yy + (26 if k else -26), yy + (34 if k else -34),
                              x0, x1, wave * 0.7, 1.0, 0.3 * j, 26)
                emit_line(pts, tt, te, cc, w * (1 - 0.35 * u), alpha + int(80 * u))
        return


def _braid(x0, x1, y, gap, twist, n=44):
    """两条丝带编织：每颗元素绕中心轴摆动"""
    A, B = [], []
    for i in range(n + 1):
        u = i / n
        x = x0 + (x1 - x0) * u
        env = math.sin(math.pi * u) ** 0.55
        ang = 2 * math.pi * twist * u
        r = gap * env
        A.append((x, y + r * math.sin(ang)))
        B.append((x, y - r * math.sin(ang)))
    return A, B


def _knot(cx, cy, r, turns=2.4, loops=3.0, n=88):
    """一个结（三叶结的二维投影）"""
    pts = []
    for i in range(n + 1):
        u = 2 * math.pi * turns * i / n
        x = r * (2 * math.cos(u) + math.cos(loops * u)) / 3.0
        y = r * (2 * math.sin(u) + math.sin(loops * u)) / 3.0
        pts.append((cx + x, cy + y))
    return pts


def side_ribbons(f, t0, t1, band_full, colors=None, n=14, alpha=40, w=7.0):
    """字幕【左右两侧】的垂落丝带  不挡字，只做边框感。
    用画面高度的 1/3 作为长度，从上方垂下。"""
    from assfx.draw import shapes as S
    R = f.rng
    W0, W1, Y0, Y1 = band_full[0], band_full[2], band_full[1], band_full[3]
    c = colors or ("#FF6E8C", "#7EC8F0")
    for side in (0, 1):
        xb = W0 + (W1 - W0) * (0.035 if side == 0 else 0.965)
        for i in range(n):
            sgn = -1 if side == 0 else 1
            x = xb + sgn * R.uniform(6, 54)
            ytop = Y0 + R.uniform(0, (Y1 - Y0) * 0.3)
            L = (Y1 - Y0) * R.uniform(0.28, 0.52)
            pts = _ribbon(ytop, ytop + L, x, x + sgn * R.uniform(4, 22),
                          R.uniform(8, 20), 0.7, R.uniform(0, 1), 16)
            f.shape(1, t0 + R.uniform(0, 0.6), t1, x, ytop,
                    draw=S.stroke(pts, w * R.uniform(0.5, 1.0)),
                    c1=c[side], a_peak=alpha + R.randint(-10, 20), blur=1.4, c3="#FFF0F4",
                    bord=1.1, extra=BS * 2 + "be2.0", fade_in=0.45, fade_out=0.8)