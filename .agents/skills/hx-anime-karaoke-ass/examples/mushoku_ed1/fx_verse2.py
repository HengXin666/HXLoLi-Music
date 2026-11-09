# -*- coding: utf-8 -*-
"""各句特效 (二番): 间奏之后到晚餐的 p10 到 p21."""
from scene import *  # noqa: F401,F403
from fx_common import fx_break, fx_glitch, fx_magic_guard  # noqa: F401


def fx_sword_heal(f, ph, k):
    R = f.rng
    for c in find(ph, "目"):
        f.shape(7, c["s"], c["s"] + 0.4, c["x"] - 40, JY - 30, c["x"] + 40, JY + 20, S.slash(150, 16), "#FFFFFF", a_peak=0, blur=1,
                c3="#9EC4FF", bord=1.5, fade_in=0.03, fade_out=0.3, extra="\\frz-35\\fscx40\\t(0,150,\\fscx100)", accel=0.5)
        f.burst(c["s"] + 0.1, c["x"], JY, 6, ["#FFFFFF", "#FFE8A0"], speed=(40, 90), life=(0.3, 0.6), size=(1.5, 3))
    for c in find(ph, "歯"):
        f.burst(c["s"], c["x"], JY, 12, ["#FFE8A0", "#FFFFFF", "#FFC040"], draw_fn=lambda r: S.sparkle(r * 2.5), speed=(40, 100),
                life=(0.4, 0.8), size=(2, 4), spin=True)
    to = seq(ph, "尖")
    if to:
        c = to[0]
        for j in range(5):
            f.shape(6, c["s"] + j * 0.04, c["s"] + 0.6, c["x"] + (j - 2) * 16, JY + 30, c["x"] + (j - 2) * 22, JY - 30,
                    S.poly([(0, -30), (6, 10), (-6, 10)]), "#DDE6FF", a_peak=40, blur=0.8, fade_in=0.05, fade_out=0.4)
    t0 = 91.5   # 塞妮丝的治愈魔法
    for _ in range(16):
        t = R.uniform(t0, k.t_out); x = R.uniform(f.b[0] + 30, f.b[2] - 30)
        f.shape(0 if R.random() < 0.5 else 6, t, t + 1.4, x, f.b[3] - 20, x + R.uniform(-10, 10), f.b[1] + 30, S.healing_cross(R.uniform(5, 9)),
                R.choice(["#9CFFB0", "#C8FFD0", "#6EE890"]), a_peak=R.randint(40, 110), blur=1.4, fade_in=0.3, fade_out=0.7,
                c3="#40D070", bord=2, a3=160)
    f.glow(0, t0, k.t_end, mid(ph.chars), JY + 10, (f.b[2] - f.b[0]) / 2 - 100, 50, "#60D080", a_peak=215, blur=24, fade_in=0.6)


def fx_birds(f, ph, k):
    R = f.rng
    for i in range(5):
        t = 94.3 + i * 0.22; L = R.uniform(1.6, 2.2)
        y0 = R.uniform(f.b[1] + 20, JY - 30); s = R.uniform(9, 15)
        f.shape(7 if i % 2 else 0, t, t + L, f.b[0] + 20, y0, f.b[2] - 20, y0 - R.uniform(0, 25), S.bird(s, 0.3), "#FFFFFF", a_peak=R.randint(20, 70),
                blur=0.8, fade_in=0.3, fade_out=0.4, c3="#2A4A70", bord=1, a3=150, extra=sway(int(L / 0.28), 280, 45, tag="fscy"))
    nai = seq(ph, "ない")
    if nai:
        x = nai[-1]["x"] + 50
        for j in range(3):    # 说不出口的“……”
            f.shape(6, nai[-1]["s"] + 0.2 + j * 0.15, ph.e + 0.4, x + j * 16, JY + 14, draw=S.circle(4), c1="#FFFFFF", a_peak=60, blur=0.8,
                    fade_in=0.1, fade_out=0.3, extra=flicker(4, 400, 200, 60))
    for c in ph.chars:
        f.burst(c["s"], c["x"], JY - 16, 2, ["#E0F4FF", "#FFFFFF"], speed=(20, 50), up=0.8, size=(2, 3.5))


def fx_tears_theory(f, ph, k):
    R = f.rng
    for c in find(ph, "悲"):
        for j in range(3):
            x = c["x"] + R.uniform(-18, 18)
            f.shape(6, c["s"] + j * 0.25, c["s"] + j * 0.25 + 1.0, x, JY + 20, x, f.b[3] - 22, S.teardrop(8), "#BFE4FF", a_peak=40, blur=0.8,
                    c3="#5AA0E8", bord=1, a3=120, fade_in=0.15, fade_out=0.3, accel=1.8)
    th_ = seq(ph, "セオリー")
    if th_:
        a, b = span(th_); t = th_[0]["s"]; y = JY + 36
        f.shape(5, t, k.t_out + 0.3, (a + b) / 2, y, draw=S.stroke([(0, 0), ((b - a) * 0.5, -3), (b - a, 0)], 3, taper=True), c1="#FFFFFF",
                a_peak=60, blur=0.6, fade_in=0.05, fade_out=0.4,
                extra=f"\\clip({a:.0f},{y-20:.0f},{a:.0f},{y+20:.0f})\\t(0,{ms(th_[-1]['e']-t)},\\clip({a:.0f},{y-20:.0f},{b:.0f},{y+20:.0f}))")
    it = seq(ph, "イタイ")
    if it:
        cx = mid(it); t = it[0]["s"]
        f.shape(0, t, k.t_out + 0.3, cx, JY, draw=S.heart(66), c1="#FF7A9A", a_peak=150, blur=5, fade_in=0.2, fade_out=0.4,
                extra="\\fscx70\\fscy70\\t(0,300,0.5,\\fscx100\\fscy100)" + sway(6, 160, 5))
        f.shape(6, it[1]["s"], k.t_out + 0.3, cx, JY - 4, draw=S.crack(R, 90, 3.5, 2), c1="#401020", a_peak=40, blur=0.6, fade_in=0.02,
                fade_out=0.4, extra="\\frz-70")
    # 99-102 家的暖光
    f.glow(0, 99.0, k.t_end, mid(ph.chars), JY + 10, (f.b[2] - f.b[0]) / 2 - 120, 48, "#FFC890", a_peak=215, blur=26, fade_in=0.8)


def fx_candle_book(f, ph, k):
    R = f.rng
    a, b = span(ph.chars); cx = (a + b) / 2
    bk_y = JY + 20
    t0 = k.t_in + 0.2
    f.shape(0, t0, k.t_end, cx, bk_y, draw=S.book(150), c1="#FFE2B0", a_peak=175, blur=1.2, fade_in=0.6, fade_out=0.6,
            c3="#FFB04A", bord=2, a3=180, extra="\\fscy70\\t(0,600,\\fscy100)")
    sh = seq(ph, "失っていいような")
    for i, c in enumerate(sh[::2]):     # 翻页：书页绕书脊翻到左侧
        t = c["s"]
        f.shape(0, t, t + 0.6, cx + 50, bk_y - 6, cx - 50, bk_y - 6, S.page(90), "#FFF2D8", a_peak=150, blur=1, fade_in=0.05, fade_out=0.2,
                extra="\\t(0,550,\\fry180)")
    for sx in (a - 50, b + 50):
        f.shape(6, t0, k.t_end, sx, JY - 4, draw=S.candle_flame(24), c1="#FFD27A", a_peak=10, blur=1.5, c3=FIRE, bord=3, a3=80,
                fade_in=0.5, fade_out=0.6, extra=sway(int((k.t_end - t0) / 0.3), 300, 8) + "\\fscy100")
        f.glow(0, t0, k.t_end, sx, JY - 4, 38, 42, "#FFB04A", a_peak=170, blur=16, fade_in=0.5, fade_out=0.6,
               extra=flicker(int((k.t_end - t0) / 0.25), 250, 190, 150))
    mi = seq(ph, "未来")
    if mi:
        for c in mi:
            f.burst(c["s"], c["x"], JY - 10, 6, ["#FFE8B0", "#FFFFFF", "#FFC860"], speed=(20, 60), up=1.2, size=(2, 4), life=(0.8, 1.4))
        f.pulse(6, mi[0]["s"], mid(mi), JY - 34, S.sparkle(30), "#FFFFFF", dur=1.0, s0=20, s1=100, a0=0, blur=0.8, extra="\\t(\\frz90)")


def fx_roxy_forest(f, ph, k):
    R = f.rng
    lat = ph.chars[0]
    hx, hy = lat["x"] - lat["w"] / 2 + 10, f.b[1] + 40
    t0, t1 = 109.5, 112.6
    f.shape(7, t0, t1, hx, hy - 30, hx, hy, S.witch_hat(34), "#3A4A9A", a_peak=30, blur=0.8, c3="#9EB8FF", bord=1.5, a3=60,
            fade_in=0.2, fade_out=0.4, t_move=(0, 450), extra="\\frz-40\\t(0,450,0.5,\\frz-12)" + sway(4, 700, 5))
    for c in ph.chars[1:]:
        if c["s"] < 113.4:
            f.burst(c["s"], c["x"], JY - 10, 5, ["#9ED8FF", "#46C8FF", "#FFFFFF"], draw_fn=lambda r: S.teardrop(r * 1.6), speed=(30, 70),
                    up=0.5, size=(3, 5), life=(0.5, 0.9), spin=True)
            f.pulse(0, c["s"], c["x"], JY + 34, S.ripple(40, 2), "#9ED8FF", dur=0.8, s0=40, s1=120, a0=100, blur=1)
    # 114 林间光：斜射光柱
    for i in range(7):
        t = 113.4 + i * 0.12; x = R.uniform(f.b[0] + 80, f.b[2] - 80)
        f.shape(0, t, k.t_end, x, (f.b[1] + f.b[3]) / 2, draw=S.rect(R.uniform(14, 34), f.b[3] - f.b[1] - 70), c1="#FFF6D0",
                a_peak=R.randint(190, 220), blur=10, fade_in=0.6, fade_out=0.6, extra="\\frz-18")
    f.drift(113.4, k.t_end, 12, ["#FFF6D0", "#E0FFD0"], S.circle, vx=(-6, 6), vy=(-10, 6), size=(1.5, 3), a=(40, 120), spin=False)


def fx_break_wheat(f, ph, k):
    fx_break(f, ph, k, "#FFB42E", ["#FFE6A0", "#FFD060", "#FFFFFF"], "#FFE0E0")
    R = f.rng
    for side in (0, 1):
        for j in range(4):
            x = (f.b[0] + 26 + j * 22) if side == 0 else (f.b[2] - 26 - j * 22)
            f.shape(0, 116.6 + j * 0.1, k.t_end, x, f.b[3] - 60, draw=S.wheat(R.uniform(42, 56)), c1="#F0C050", a_peak=90, blur=0.8,
                    fade_in=0.6, fade_out=0.6, extra="\\org(%.1f,%.1f)" % (x, f.b[3] - 10) + sway(int((k.t_end - 116.6) / 1.2), 1200, 6))
    f.drift(116.6, k.t_end, 20, ["#FFD878", "#FFE8B0", "#FFC040"], S.circle, vx=(10, 30), vy=(-18, -4), size=(1.8, 3.5), a=(40, 130), spin=False)


def fx_glitch_teal(f, ph, k):
    fx_glitch(f, ph, k, "#FF3A5A", "#1FF2E0", ["#FF3A3A", "#FFFFFF", "#1FD2C0"])
    R = f.rng
    for t in (124.5, seq(ph, "見境")[0]["s"] if seq(ph, "見境") else 125):   # 瑞杰路德额上的“红眼”
        x = R.uniform(f.b[0] + 80, f.b[2] - 80)
        f.pulse(6, t, x, f.b[1] + 36, S.eye_ring(26), "#FF2A2A", dur=0.9, s0=80, s1=120, a0=30, blur=1.2)


def fx_hide_map(f, ph, k):
    R = f.rng
    f.pulse(6, 127.6, f.b[0] + 70, JY - 20, S.eye_ring(30), "#FF2A2A", dur=1.2, s0=70, s1=110, a0=20, blur=1.2)
    for n in range(2):
        chs = seq(ph, "隠したい", n)
        if not chs:
            continue
        a, b = span(chs); t = chs[0]["s"]; d = max(0.5, chs[-1]["e"] - t)
        f.shape(7, t, t + d + 0.3, a - 20, JY - 4, b + 20, JY - 4, S.veil(120, 96, 4, 6), "#0A1030", a_peak=90, blur=6,
                fade_in=0.1, fade_out=0.3, t_move=(0, ms(d)))
    sb = seq(ph, "全てを")
    t0 = sb[0]["s"] - 0.3 if sb else 129.0
    a, b = f.b[0] + 30, f.b[2] - 30
    for i in range(9):     # 129 蓝色地图：经纬网格
        x = a + (b - a) * i / 8
        f.shape(0, t0 + i * 0.03, k.t_end, x, (f.b[1] + f.b[3]) / 2, draw=S.rect(1.6, f.b[3] - f.b[1] - 40), c1="#6E8CFF", a_peak=170,
                blur=0.6, fade_in=0.4, fade_out=0.5)
    for j in range(4):
        y = f.b[1] + 20 + (f.b[3] - f.b[1] - 40) * j / 3
        f.shape(0, t0 + j * 0.05, k.t_end, (a + b) / 2, y, draw=S.rect(b - a, 1.6), c1="#6E8CFF", a_peak=170, blur=0.6, fade_in=0.4, fade_out=0.5)
    f.shape(6, t0, k.t_end, b - 60, JY - 10, draw=S.compass(40), c1="#BCD0FF", a_peak=60, blur=0.8, fade_in=0.4, fade_out=0.5,
            extra="\\frz-30\\t(0,800,0.4,\\frz12)\\t(800,1600,\\frz0)")


def fx_bolt_tears(f, ph, k):
    R = f.rng
    for c in seq(ph, "背負う"):
        for j in range(2):
            x = R.uniform(f.b[0] + 40, f.b[2] - 40); t = c["s"] + j * 0.06
            f.shape(7, t, t + 0.18, x, (f.b[1] + f.b[3]) / 2, draw=S.bolt(R, f.b[3] - f.b[1] - 50, 5), c1="#E8FCFF", a_peak=0, blur=0.8,
                    c3="#34D8FF", bord=2.5, a3=60, fade_in=0.01, fade_out=0.1, extra=flicker(1, 120, 180, 0))
        f.glow(0, c["s"], c["s"] + 0.3, c["x"], JY, 70, 60, "#34D8FF", a_peak=150, blur=20, fade_in=0.02, fade_out=0.25)
    ki = seq(ph, "決めた")
    if ki:
        f.floor_spin(0, ki[0]["s"], ki[0]["s"] + 1.6, mid(ki), JY + 36, S.rune_ring(150, rng=R), "#7CE8FF", deg_per_s=60, a_peak=60,
                     blur=0.8, fade_in=0.2, fade_out=0.9, grow=0.6)
    # 138 爆炎
    cx = mid(ph.chars)
    f.burst(138.0, cx, JY + 20, 16, ["#FFB347", "#FF6A1F", "#FFE0A0"], speed=(60, 160), up=0.5, life=(0.5, 1.0), size=(2, 4.5), glow="#FF5A10")
    f.glow(0, 138.0, 138.6, cx, JY + 10, 200, 60, "#FF7A2A", a_peak=150, blur=26, fade_in=0.05, fade_out=0.5)
    for c in seq(ph, "涙"):
        for j in range(4):
            x = c["x"] + R.uniform(-20, 20)
            f.shape(6, c["s"] + j * 0.15, c["s"] + j * 0.15 + 0.9, x, JY + 18, x, f.b[3] - 22, S.teardrop(8), "#C8F6FF", a_peak=30,
                    blur=0.8, c3="#34D8FF", bord=1.2, a3=100, fade_in=0.1, fade_out=0.3, accel=1.8)
        f.pulse(0, c["s"] + 0.8, c["x"], f.b[3] - 26, S.ripple(40, 2), "#9EEFFF", dur=0.9, s0=30, s1=130, a0=80, blur=1)


def fx_snow_rise(f, ph, k):
    R = f.rng
    f.drift(k.t_in, 145.2, 34, ["#FFFFFF", "#E8F6FF"], S.snowflake, vx=(-10, 14), vy=(10, 28), size=(5, 9), a=(20, 110), blur=(0.5, 1.2))
    for c in seq(ph, "背伸び"):
        f.burst(c["s"], c["x"], JY + 20, 4, ["#FFFFFF", "#CDEBFF"], speed=(15, 40), up=1.6, size=(2, 3.5), life=(0.7, 1.1))
    se = seq(ph, "世界")
    if se:
        t = se[0]["s"]
        f.glow(0, t, k.t_end, mid(ph.chars), JY + 16, (f.b[2] - f.b[0]) / 2 - 90, 55, "#FFC878", a_peak=190, blur=28, fade_in=0.9)
        f.shape(0, t, k.t_end, mid(se), JY - 10, draw=S.sunburst(9, 110, 7, 150), c1="#FFE0A0", a_peak=185, blur=3, fade_in=0.6,
                fade_out=0.5, extra="\\fscx40\\fscy40\\t(0,900,0.5,\\fscx100\\fscy100)")


def fx_flowers(f, ph, k):
    R = f.rng
    cols = ["#FF5AAE", "#FF8AC8", "#FFE04A", "#FFFFFF", "#FFB0D8"]
    f.drift(k.t_in, k.t_end, 30, cols, lambda s: S.sakura(s) if R.random() < 0.5 else S.petal(s), vx=(15, 50), vy=(-12, 12),
            size=(6, 10), a=(10, 90), blur=(0.5, 1.2))
    for c in ph.chars:
        f.burst(c["s"], c["x"], JY - 10, 2, cols, draw_fn=S.petal, speed=(30, 70), up=0.6, size=(4, 6), spin=True)
    for key, cc in (("ため？", "#FF5AAE"), ("自分", "#FFE04A")):
        chs = seq(ph, key)
        if chs:
            t = chs[-1]["s"]; x = chs[-1]["x"] if key == "ため？" else mid(chs)
            f.shape(0, t, k.t_out + 0.3, x, JY, draw=S.flower(56), c1=cc, a_peak=130, blur=2, fade_in=0.2, fade_out=0.4,
                    extra="\\fscx10\\fscy10\\frz-60\\t(0,600,0.5,\\fscx100\\fscy100\\frz0)")


def fx_dinner_flip(f, ph, k):
    R = f.rng
    f.drift(k.t_in, k.t_end, 22, ["#FFD090", "#FFE8C0", "#FFB060"], S.circle, vx=(-6, 6), vy=(-14, -4), size=(2, 4.5), a=(60, 150),
            spin=False, blur=(1.5, 3), glow="#FF9B4A")
    f.glow(0, k.t_in, k.t_end, mid(ph.chars), JY + 12, (f.b[2] - f.b[0]) / 2 - 100, 50, "#FF9B4A", a_peak=215, blur=26, fade_in=1.0)
    ur = seq(ph, "裏側")
    if ur:
        x = ur[-1]["x"] + 80; t = ur[0]["s"]
        f.shape(6, t, k.t_out + 0.3, x, JY - 6, draw=S.heart(30), c1="#FF8A9A", a_peak=40, blur=1, fade_in=0.2, fade_out=0.4,
                c3="#FFD0D8", bord=1.5, a3=80, extra=f"\\t(0,{ms(k.t_out-t)},\\fry{360*int((k.t_out-t)/1.2)})")
    wa = seq(ph, "わからない")
    for c in wa:
        f.text(6, c["s"], c["s"] + 0.9, c["x"] + 12, RBY, "?", "LAT", 66, f"\\bord0\\shad0\\1c{col('#FFE0B0')}\\blur0.8\\fscx55\\fscy55"
               f"\\alpha&HFF&\\t(0,150,\\alpha&H50&)\\t(500,900,\\alpha&HFF&)", x1=c["x"] + 26, y1=RBY - 26)
