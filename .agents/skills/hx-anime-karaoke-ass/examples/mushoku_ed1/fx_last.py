# -*- coding: utf-8 -*-
"""各句特效 (末段): p22 到 p29, 收在 fx_only_you."""
from scene import *  # noqa: F401,F403
from fx_common import fx_break, fx_glitch, fx_magic_guard  # noqa: F401


def fx_break_water(f, ph, k):
    R = f.rng
    for c in find(ph, "壊"):
        f.burst(c["s"], c["x"], JY, 12, ["#C8F6FF", "#46C8FF", "#FFFFFF"], draw_fn=lambda r: S.teardrop(r * 1.5), speed=(50, 120),
                up=0.4, size=(3, 6), life=(0.5, 1.0), spin=True, glow="#1E90FF")
        for j in range(2):
            f.pulse(0, c["s"] + j * 0.18, c["x"], JY + 36, S.ripple(70, 2.5), "#9EEFFF", dur=1.0, s0=30, s1=140, a0=60, blur=1)
    f.drift(k.t_in, k.t_end, 26, ["#C8F6FF", "#9EE0FF"], lambda s: S.ring(s, 1.3), vx=(-6, 6), vy=(-30, -12), size=(4, 9), a=(40, 130),
            spin=False, blur=(0.5, 1))
    mo = seq(ph, "戻れない")
    if mo:
        f.pulse(0, mo[0]["s"], mid(mo), JY + 36, S.ripple(160, 3), "#9EEFFF", dur=1.6, s0=20, s1=110, a0=50, blur=1)


def fx_embrace(f, ph, k):
    R = f.rng
    a, b = span(ph.chars); cx = mid(ph.chars)
    da = seq(ph, "抱きしめ")
    t = da[0]["s"] if da else ph.s + 2
    rr = 90
    for sgn, a0, a1 in ((-1, 110, 250), (1, -70, 70)):
        x0 = cx + sgn * ((b - a) / 2 + 20); x1 = cx + sgn * ((b - a) / 2 - 30)
        f.shape(6, t - 0.2, k.t_out + 0.4, x0, JY - 2, x1, JY - 2, S.arc(rr, a0, a1, 5), "#FFC0D0", a_peak=40, blur=1.4, c3="#FF7A9A",
                bord=2, a3=100, fade_in=0.3, fade_out=0.4, t_move=(0, 700), extra="\\fscy80")
    f.glow(0, t, k.t_end, cx, JY + 6, (b - a) / 2 + 30, 55, "#FF9AB0", a_peak=205, blur=26, fade_in=0.8)
    for key in ("強", "抱"):
        for c in find(ph, key):
            f.burst(c["s"], c["x"], JY - 16, 5, ["#FF9AB0", "#FFD0DC", "#FFFFFF"], draw_fn=lambda r: S.heart(r * 2), speed=(25, 60),
                    up=1.0, size=(3, 5), life=(0.8, 1.4))


def fx_eraser(f, ph, k):
    R = f.rng
    ya = seq(ph, "優しさ")
    if ya:
        f.glow(0, ya[0]["s"], k.t_end, mid(ya), JY, 110, 48, "#C8FFD8", a_peak=200, blur=20, fade_in=0.5)
    ke = seq(ph, "消し去って")
    if ke:
        a, b = span(ke); t0 = ke[0]["s"]; t1 = ke[-1]["e"]
        f.shape(7, t0, t1 + 0.3, a - 10, JY - 8, b + 10, JY - 8, S.rect(34, 70), "#F4FFF6", a_peak=60, blur=2, c3="#9EE6B8", bord=2,
                a3=120, fade_in=0.1, fade_out=0.3, t_move=(0, ms(t1 - t0)), extra="\\frz-12")
        for i in range(int((t1 - t0) / 0.06)):
            tt = t0 + i * 0.06; x = a + (b - a) * (tt - t0) / (t1 - t0)
            f.shape(6, tt, tt + 0.8, x, JY + 20, x + R.uniform(-15, 15), JY + R.uniform(35, 60), S.circle(R.uniform(1.5, 3)), "#F4FFF6",
                    a_peak=R.randint(40, 120), blur=1, fade_in=0.05, fade_out=0.6)
        # 被擦过的字短暂变淡
        for c in ke:
            f.text(6, c["s"] + 0.05, c["s"] + 0.6, c["x"], JY, c["ch"], "JP", 84,
                   f"\\bord6\\shad0\\1c{col('#0A1A12')}\\3c{col('#0A1A12')}\\blur6\\alpha&HFF&\\t(0,120,\\alpha&H70&)\\t(250,550,\\alpha&HFF&)")


def fx_overflow(f, ph, k):
    R = f.rng
    for c in find(ph, "悲"):
        for j in range(3):
            x = c["x"] + R.uniform(-15, 15)
            f.shape(6, c["s"] + j * 0.2, c["s"] + j * 0.2 + 1.0, x, JY + 20, x, f.b[3] - 22, S.teardrop(7), "#FFF0C8", a_peak=40, blur=0.8,
                    c3="#FFB43C", bord=1, a3=120, fade_in=0.1, fade_out=0.3, accel=1.8)
    af = seq(ph, "溢れ出る")
    for c in af:
        f.burst(c["s"], c["x"], JY, 12, ["#FFE8A0", "#FFD060", "#FFFFFF"], speed=(30, 90), up=1.3, size=(2, 4), life=(0.8, 1.5), glow="#FFB43C")
        for j in range(2):
            x = c["x"] + R.uniform(-20, 20)
            f.shape(6, c["s"] + 0.1 + j * 0.2, c["s"] + 1.3, x, JY + 22, x, f.b[3] - 20, S.teardrop(6), "#FFE8A0", a_peak=40, blur=1,
                    fade_in=0.1, fade_out=0.4, accel=1.6, extra="\\frz180")
    om = seq(ph, "思い")
    if om:
        f.glow(0, om[0]["s"], k.t_end, mid(ph.chars), JY + 8, (f.b[2] - f.b[0]) / 2 - 90, 55, "#FFB43C", a_peak=190, blur=28, fade_in=0.8)
        f.pulse(6, om[0]["s"], om[-1]["x"] + 50, JY - 36, S.sparkle(30), "#FFFFFF", dur=1.4, s0=20, s1=100, a0=0, blur=0.8, extra="\\t(\\frz90)")


def fx_chains(f, ph, k):
    R = f.rng
    a, b = f.b[0] + 40, f.b[2] - 40
    n1 = seq(ph, "逃げない"); ji = seq(ph, "ジレンマ"); ka = seq(ph, "から")
    t_end_chain = ka[0]["s"] + 0.15 if ka else ph.e
    n_links = int((b - a) / (13 * 1.45))
    for j, (t, y, rz) in enumerate(((n1[0]["s"], JY - 6, -4), (seq(ph, "逃げたくない")[0]["s"] if seq(ph, "逃げたくない") else n1[0]["s"] + 1, JY + 14, 3))):
        ch = S.chain(n_links, 13)
        f.shape(0, t, t_end_chain, (a + b) / 2, y, draw=ch, c1="#B8B0D8", a_peak=120, blur=0.8, c3="#302848", bord=1, a3=120, fade_in=0.05,
                fade_out=0.05, extra=f"\\frz{rz}\\clip({a-30:.0f},{y-60:.0f},{a-30:.0f},{y+60:.0f})\\t(0,500,\\clip({a-30:.0f},{y-60:.0f},{b+30:.0f},{y+60:.0f}))" +
                (f"\\t({ms(ji[0]['s']-t)},{ms(ji[-1]['e']-t)},\\fscx94)" if ji else ""))
    if ka:   # 挣断锁链
        t = ka[0]["s"] + 0.1
        for i in range(24):
            x = R.uniform(a, b)
            f.shape(7, t, t + R.uniform(0.6, 1.0), x, JY + R.uniform(-10, 16), x + R.uniform(-40, 40), JY + R.uniform(10, 40),
                    S.chain_link(R.uniform(8, 12)) if i % 3 else S.shard(R, 8), "#B8B0D8", a_peak=R.randint(20, 80), blur=0.8,
                    fade_in=0.02, fade_out=0.6, extra=f"\\frz{R.randint(0,360)}\\t(\\frz{R.randint(-200,200)})")
        f.pulse(5, t, mid(ph.chars), JY, S.ellipse_ring(200, 60, 3), "#9A8CFF", dur=0.6, s0=50, s1=120, a0=40, blur=1.5)
    for j in range(3):
        y = R.uniform(JY - 10, JY + 60); w = R.uniform(260, 400)
        f.shape(0, k.t_in + j * 0.3, k.t_end, f.b[0] + w / 2, y, f.b[2] - w / 2, y, S.veil(w, 40, 3, 5), "#C0C4D8", a_peak=205, blur=14,
                fade_in=0.8, fade_out=0.7)


def fx_glitch_cyan(f, ph, k):
    fx_glitch(f, ph, k, "#FF3A8A", "#2EF2E0", ["#2EF2E0", "#E0FFFF", "#6A8C90"])


def fx_finale(f, ph, k):
    R = f.rng
    fx_magic_guard(f, ph, k, big=True)
    cx = mid(ph.chars)
    # 204 火球横穿
    t = 204.0
    f.shape(7, t, t + 0.9, f.b[0] + 40, JY - 30, f.b[2] - 40, JY - 30, S.circle(14), "#FFE0A0", a_peak=0, blur=3, c3=FIRE, bord=8, a3=60,
            fade_in=0.1, fade_out=0.2, alpha_t="")
    for i in range(18):
        tt = t + i * 0.045; x = f.b[0] + 40 + (f.b[2] - f.b[0] - 80) * (tt - t) / 0.9
        f.shape(6, tt, tt + 0.6, x, JY - 30, x - R.uniform(10, 40), JY - 30 + R.uniform(-15, 15), S.flame(R.uniform(8, 14)), R.choice([FIRE, "#FFB347"]),
                a_peak=60, blur=2, fade_in=0.02, fade_out=0.5, extra="\\frz-90")
    for i in range(6):   # 205.5-207 天空弧光
        tt = 205.5 + i * 0.25
        f.shape(6, tt, tt + 0.9, cx + R.uniform(-250, 250), JY - 30, draw=S.arc(180, 200, 340, 4), c1=R.choice(["#FFD090", "#A8E8FF", "#FFFFFF"]),
                a_peak=40, blur=1.2, fade_in=0.1, fade_out=0.6, extra="\\fscy30")
    # 208.5 塞妮丝拥抱鲁迪：暖光
    f.glow(0, 208.5, k.t_end, cx, JY + 10, (f.b[2] - f.b[0]) / 2 - 100, 55, "#FFB870", a_peak=190, blur=28, fade_in=0.8)
    for c in seq(ph, "教えてくれた"):
        f.burst(c["s"], c["x"], JY - 10, 5, ["#FFD090", "#A8E8FF", "#FFFFFF"], speed=(25, 70), up=1.0, size=(2, 4))


def fx_only_you(f, ph, k):
    R = f.rng
    a, b = span(ph.chars); cx = mid(ph.chars)
    f.glow(0, k.t_in, k.t_end, cx, JY + 8, (b - a) / 2 + 50, 55, "#6F9CFF", a_peak=205, blur=26, fade_in=1.0, fade_out=1.0)
    hx, hy = a - 40, f.b[1] + 44
    f.shape(7, 213.0, k.t_out + 0.6, hx, hy - 20, hx, hy, S.witch_hat(32), "#3A4A9A", a_peak=30, blur=0.8, c3="#9EB8FF", bord=1.5, a3=60,
            fade_in=0.3, fade_out=0.6, t_move=(0, 500), extra="\\frz-30\\t(0,500,0.5,\\frz-10)" + sway(4, 900, 4))
    ke = find(ph, "け")[0]
    x, y = ke["x"] + 50, JY - 38
    f.shape(7, ke["s"], k.t_out + 1.0, x, y, draw=S.star(5, 22, 9), c1="#FFF3C0", a_peak=0, blur=0.8, c3="#FFC040", bord=2, a3=60,
            fade_in=0.15, fade_out=1.0, extra="\\fscx10\\fscy10\\t(0,350,0.5,\\fscx120\\fscy120)\\t(350,700,\\fscx95\\fscy95)\\t(\\frz144)")
    f.glow(6, ke["s"], k.t_out + 1.0, x, y, 30, 30, "#FFD27A", a_peak=110, blur=12, fade_in=0.2, fade_out=1.0)
    f.drift(k.t_in, k.t_end, 12, ["#FFFFFF", "#E0E8FF"], S.feather, vx=(8, 24), vy=(6, 16), size=(10, 14), a=(30, 110),
            extra_fn=lambda R: sway(4, 900, 25))
    for c in ph.chars:
        f.burst(c["s"], c["x"], JY - 20, 4, ["#FFF3C0", "#FFFFFF", "#9EB8FF"], draw_fn=S.sparkle, speed=(20, 60), up=1.0, size=(4, 7), spin=True)
