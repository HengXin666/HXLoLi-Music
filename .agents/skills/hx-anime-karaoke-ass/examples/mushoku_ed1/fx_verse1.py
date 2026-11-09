# -*- coding: utf-8 -*-
"""各句特效 (一番): 间奏卡片之前的 p00 到 p09."""
from scene import *  # noqa: F401,F403
from fx_common import fx_break, fx_glitch, fx_magic_guard  # noqa: F401


def fx_birth(f, ph, k):
    a, b = span(ph.chars); cx = (a + b) / 2
    f.glow(0, k.t_in, k.t_end, cx, JY + 10, (b - a) / 2 + 30, 58, "#FFC9A0", a_peak=205, blur=26, fade_in=0.8, fade_out=0.8)
    ai = find(ph, "愛")[0]
    for dly, a0 in ((0, 70), (0.28, 110)):
        f.pulse(0, ai["s"] + dly, ai["x"], JY, S.heart(62), "#FF8CA0", dur=1.1, s0=40, s1=135, a0=a0, blur=5)
    f.shape(0, ai["s"], k.t_out, ai["x"], JY - 4, draw=S.heart(40), c1="#FF9CB0", a_peak=170, blur=8, fade_in=0.4, fade_out=0.5,
            extra=sway(8, 900, 5) + "\\fscx90\\fscy90")
    for c in ph.chars:
        f.burst(c["s"], c["x"], JY - 26, 2, ["#FFB6C4", "#FFD6C0", "#FFFFFF"], draw_fn=lambda r: S.heart(r * 1.9),
                speed=(25, 55), up=0.9, size=(3, 5), life=(0.8, 1.3))
    for c in seq(ph, "イロハ"):   # 爱的 ABC：小小的 い・ろ・は 从字上飘起
        g = {"イ": "い", "ロ": "ろ", "ハ": "は"}[c["ch"]]
        f.text(6, c["s"], c["s"] + 1.2, c["x"] + 18, RBY - 6, g, "RB", 34,
               f"\\bord0\\shad0\\1c{col('#FFB0A0')}\\blur1\\alpha&HFF&\\t(0,200,\\alpha&H40&)\\t(600,1200,\\alpha&HFF&)\\fscx70\\fscy70",
               x1=c["x"] + 40, y1=RBY - 30)
    f.drift(k.t_in, k.t_end, 18, ["#FFE3C8", "#FFD2B0", "#FFFFFF"], S.circle, vx=(-8, 8), vy=(-22, -8), size=(2, 4),
            a=(60, 150), spin=False, blur=(1, 2.5))


def fx_grasp(f, ph, k):
    te = find(ph, "手")[0]; nai = seq(ph, "ない")
    t_break = nai[0]["s"] if nai else ph.e - 0.5
    R = f.rng
    for i in range(10):     # 夕光汇聚到“手”
        x0 = R.uniform(f.b[0] + 30, f.b[2] - 30); y0 = R.choice([f.b[1] + 20, f.b[3] - 20])
        t0 = te["s"] - 0.25 + i * 0.03
        f.shape(7, t0, te["s"] + 0.45, x0, y0, te["x"], JY - 6, S.circle(R.uniform(2.5, 4.5)), "#FFD27A", a_peak=40,
                fade_in=0.15, fade_out=0.15, blur=1.5, c3=FIRE, bord=2, accel=0.6)
    f.shape(0, te["s"] + 0.3, t_break + 0.1, te["x"], JY - 4, draw=S.circle(22), c1="#FFC060", a_peak=90, blur=12,
            fade_in=0.3, fade_out=0.1, extra=flicker(6, 500, 150, 90))
    f.shape(6, te["s"] + 0.3, t_break + 0.1, te["x"], JY - 4, draw=S.sparkle(16), c1="#FFF6D8", a_peak=30, blur=0.8,
            fade_in=0.3, fade_out=0.1, extra="\\t(\\frz180)")
    # “得不到”：光球从指间滑落碎开
    cx = te["x"]
    f.shape(6, t_break, t_break + 0.9, cx, JY - 4, cx + 30, f.b[3] - 30, S.circle(9), "#FFC060", a_peak=40, blur=4, fade_in=0.05, fade_out=0.6, accel=1.8)
    f.burst(t_break + 0.35, cx + 25, f.b[3] - 40, 12, ["#FFD27A", "#FFB04A", "#FFF0C0"], speed=(40, 110), up=0.3, life=(0.5, 1.0))
    for c in seq(ph, "いれいれ"):
        f.pulse(5, c["s"], c["x"], JY, S.ring(34, 2.5), "#FFD090", dur=0.5, s0=60, s1=120, a0=90, blur=1)


def fx_campfire(f, ph, k):
    R = f.rng
    ki = seq(ph, "貴方")[0]["s"]
    x0, x1 = f.b[0] + 20, f.b[2] - 20
    for _ in range(46):     # 篝火余烬
        t = R.uniform(k.t_in, ki); L = R.uniform(1.0, 2.0); x = R.uniform(x0, x1)
        f.shape(0 if R.random() < 0.5 else 7, t, t + L, x, f.b[3] - 15, x + R.uniform(-30, 30), f.b[1] + 20, S.circle(R.uniform(1.8, 3.5)),
                R.choice(["#FFB347", "#FF7A2A", "#FFD27A"]), a_peak=R.randint(0, 60), fade_in=0.2, fade_out=0.6, blur=1.2,
                c3="#FF5A10", bord=1.5, extra=flicker(int(L / 0.2), 200, 120, 20))
    for c in seq(ph, "戦い"):
        for j in range(3):
            fx_ = c["x"] + (j - 1) * 20
            f.shape(0, c["s"] + j * 0.05, c["s"] + 1.3, fx_, JY + 30, fx_, JY - 8, S.flame(R.uniform(24, 34), R.uniform(-0.2, 0.2)),
                    R.choice([FIRE, "#FFB347"]), a_peak=90, blur=3, fade_in=0.15, fade_out=0.8, extra="\\fscy70\\t(0,600,\\fscy115)" + sway(3, 400, 6))
    for c in seq(ph, "疲れ果てた"):    # 疲惫：字下沉般的暗影
        f.shape(0, c["s"], c["s"] + 0.8, c["x"], JY + 6, c["x"], JY + 22, S.ellipse(30, 10), "#000000", a_peak=140, blur=8, fade_in=0.1, fade_out=0.6)
    for j in range(4):      # 36s 雾：“想要你”在雾中
        y = R.uniform(JY - 20, JY + 60); w = R.uniform(260, 420)
        f.shape(0, ki - 0.4 + j * 0.25, k.t_end, f.b[0] + w / 2, y, f.b[2] - w / 2, y + R.uniform(-10, 10), S.veil(w, 40, 3, 5),
                "#D8DCE8", a_peak=195, blur=14, fade_in=0.8, fade_out=0.7)
    for c in seq(ph, "欲しい"):
        f.pulse(5, c["s"], c["x"], JY, S.ring(40, 2), "#FFE0C0", dur=0.8, s0=50, s1=140, a0=110, blur=1.5)


def fx_autumn(f, ph, k):
    f.drift(k.t_in, k.t_end, 26, ["#E8402E", "#FF7A3A", "#C8201E", "#FFA040"], S.maple, vx=(25, 70), vy=(-5, 20),
            size=(8, 14), a=(20, 90), blur=(0.6, 1.4))
    lat = ph.chars[0]
    f.shape(6, lat["s"], lat["s"] + 1.4, lat["x"] + lat["w"] / 2 - 10, JY - 30, draw=S.sparkle(22), c1="#FFF0E0", a_peak=20, blur=0.8,
            fade_in=0.1, fade_out=0.9, extra="\\fscx30\\fscy30\\t(0,300,\\fscx110\\fscy110)\\t(\\frz90)")
    kw = seq(ph, "怖くない")
    if kw:
        cx = mid(kw)
        f.shape(0, kw[0]["s"], k.t_out + 0.3, cx, JY, draw=S.shield(58), c1="#8C1A10", a_peak=150, blur=4, fade_in=0.3, fade_out=0.5,
                extra="\\fscx60\\fscy60\\t(0,400,0.6,\\fscx100\\fscy100)")
        f.shape(0, kw[0]["s"], k.t_out + 0.3, cx, JY, draw=S.shield(58), c1="#FF6A4A", a_peak=255, a3=90, c3="#FF6A4A", bord=2.5, blur=2,
                fade_in=0.3, fade_out=0.5, extra="\\1a&HFF&\\fscx60\\fscy60\\t(0,400,0.6,\\fscx100\\fscy100)")
        f.pulse(5, kw[2]["s"], cx, JY, S.shield(58), "#FFB090", dur=0.7, s0=100, s1=150, a0=120, blur=3)


def fx_promise(f, ph, k):
    R = f.rng
    lat = ph.chars[0]; se = seq(ph, "背中"); ma = seq(ph, "任せて")
    xa = lat["x"] + lat["w"] / 2 - 20; xb = ma[-1]["x"]
    y = JY + 40
    # Agent Notes: 卡拉OK skill 通用化  去掉单次制作的事实与清单式铺陈
    # 
    th = S.thread((0, 0), (xb - xa, 0), 16, 3)
    t0 = lat["s"]; t1 = ma[-1]["s"] + 0.2
    f.shape(5, t0, k.t_out + 0.3, (xa + xb) / 2, y, draw=th, c1="#FF3B4A", a_peak=30, blur=1.2, c3="#FF7080", bord=1.2, a3=120,
            fade_in=0.05, fade_out=0.5, extra=f"\\clip({xa-4:.0f},{y-40:.0f},{xa-4:.0f},{y+40:.0f})\\t(0,{ms(t1-t0)},\\clip({xa-4:.0f},{y-40:.0f},{xb+8:.0f},{y+40:.0f}))")
    f.pulse(6, ma[-1]["s"] + 0.15, xb, y + 4, S.heart(16), "#FF4A5A", dur=0.8, s0=80, s1=160, a0=20, blur=1)
    f.shape(6, ma[-1]["s"] + 0.15, k.t_out + 0.3, xb, y + 4, draw=S.heart(12), c1="#FF4A5A", a_peak=20, blur=0.8, fade_in=0.1, fade_out=0.4)
    if se:
        cx = mid(se)
        for sgn in (-1, 1):
            f.shape(0, se[0]["s"], k.t_out + 0.2, cx, JY, draw=S.sword(118), c1="#E8EEF6", a_peak=150, blur=1.2, c3="#FFFFFF", bord=0,
                    fade_in=0.25, fade_out=0.4, extra=f"\\frz{sgn*70}\\t(0,350,0.5,\\frz{sgn*38})")
        f.pulse(5, se[0]["s"] + 0.32, cx, JY - 30, S.sparkle(26), "#FFFFFF", dur=0.6, s0=40, s1=110, a0=10, blur=0.8)
    f.drift(k.t_in, k.t_end, 14, ["#B8E08A", "#8CCB6A", "#E6F5C0"], S.leaf, vx=(15, 45), vy=(-15, 10), size=(5, 8), a=(30, 110))


def fx_break_red(f, ph, k):
    fx_break(f, ph, k, "#FF2E4A", ["#FFFFFF", "#FFD0D6", "#FF4A5A"], "#FFE8E8")


def fx_glitch_violet(f, ph, k):
    fx_glitch(f, ph, k, "#FF2A6A", "#2AE8FF", ["#9A8C80", "#6E6258", "#C0B4A8"])   # 岩石魔像的碎石


def fx_fire_water(f, ph, k):
    R = f.rng
    a, b = span(ph.chars); cx = (a + b) / 2
    rx = (b - a) / 2 + 50; ry = 42
    t0, t1 = k.t_in + 0.2, k.t_out + 0.3
    n = int((t1 - t0) / 0.1)
    for which, ph0, cc, glow in ((0, 0.0, "#FFB060", FIRE), (1, math.pi, "#A8E8FF", WATER)):
        for i in range(n):
            ta = t0 + i * 0.1; a0 = ph0 + i * 0.22; a1 = a0 + 0.22
            p0 = (cx + rx * math.cos(a0), JY + 4 + ry * math.sin(a0)); p1 = (cx + rx * math.cos(a1), JY + 4 + ry * math.sin(a1))
            front = math.sin(a0) > 0
            f.shape(7 if front else 0, ta, ta + 0.1, p0[0], p0[1], p1[0], p1[1], S.circle(9), cc, a_peak=0, blur=2, fade_in=0.0,
                    fade_out=0.0, c3=glow, bord=6, a3=100, alpha_t="")
            if i % 2 == 0:
                f.shape(0, ta, ta + 0.7, p0[0], p0[1], p0[0] + R.uniform(-8, 8), p0[1] + R.uniform(-12, 4), S.circle(R.uniform(2, 4)), glow,
                        a_peak=60, blur=1.5, fade_in=0.02, fade_out=0.6)
    # 70.5-72 天空弧光
    for i in range(5):
        t = 70.5 + i * 0.3
        f.shape(6, t, t + 0.9, cx + R.uniform(-150, 150), JY - 30, draw=S.arc(160, 200, 340, 4), c1=R.choice(["#FFD090", "#A8E8FF", "#FFFFFF"]),
                a_peak=40, blur=1.2, fade_in=0.1, fade_out=0.6, extra=f"\\fscy35\\clip({a-60:.0f},{JY-120},{a-60:.0f},{JY+60})\\t(0,500,\\clip({a-60:.0f},{JY-120},{b+60:.0f},{JY+60}))")


def fx_sylphie_tree(f, ph, k):
    a, b = span(ph.chars); cx = (a + b) / 2
    f.glow(0, k.t_in, k.t_end, cx, JY + 6, (b - a) / 2 + 40, 55, "#FFAA66", a_peak=200, blur=28, fade_in=1.0, fade_out=1.0)
    f.drift(k.t_in, k.t_end, 16, ["#9ED870", "#C8EE90", "#7CC060"], S.leaf, vx=(10, 30), vy=(8, 22), size=(6, 9), a=(30, 110),
            extra_fn=lambda R: sway(4, 700, 30))
    ke = find(ph, "け")[0]
    x, y = ke["x"] + 48, JY - 40
    f.shape(7, ke["s"], k.t_out + 0.8, x, y, draw=S.sparkle(30), c1="#FFFFFF", a_peak=0, blur=0.8, c3="#FFD090", bord=1.5, a3=60,
            fade_in=0.15, fade_out=0.8, extra="\\fscx10\\fscy10\\t(0,300,0.5,\\fscx120\\fscy120)\\t(300,600,\\fscx90\\fscy90)" +
            "".join(f"\\t({600+i*700},{950+i*700},\\fscx115\\fscy115)\\t({950+i*700},{1300+i*700},\\fscx90\\fscy90)" for i in range(4)))
    f.glow(6, ke["s"], k.t_out + 0.8, x, y, 26, 26, "#FFD090", a_peak=120, blur=10, fade_in=0.2, fade_out=0.8)
    for c in ph.chars:
        f.burst(c["s"], c["x"], JY - 20, 3, ["#FFE0B0", "#FFFFFF", "#C8EE90"], speed=(20, 50), up=0.9, size=(2, 3.5))
