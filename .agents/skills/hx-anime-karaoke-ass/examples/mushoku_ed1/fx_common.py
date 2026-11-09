# -*- coding: utf-8 -*-
"""共用特效: 破碎 (fx_break) / 故障 (fx_glitch) / 魔力护盾 (fx_magic_guard).
多句换色复用, 各句的 fx_break_red / fx_glitch_teal 等只是传入不同的颜色.
fx_magic_guard 本身也是第 8 句 (p07) 的配方."""
from scene import *  # noqa: F401,F403


def fx_break(f, ph, k, pal, shard_cols, slash_col):
    R = f.rng
    for c in find(ph, "壊"):
        f.shape(6, c["s"], c["s"] + 0.9, c["x"], JY, draw=S.crack(R, 130, 4.5, 3), c1="#FFFFFF", a_peak=0, blur=0.6, c3=pal, bord=1.5,
                fade_in=0.02, fade_out=0.5, extra=f"\\frz{R.uniform(-25,25):.0f}\\clip({c['x']-70:.0f},{JY-70},{c['x']-70:.0f},{JY+70})\\t(0,120,\\clip({c['x']-70:.0f},{JY-70},{c['x']+70:.0f},{JY+70}))")
        f.burst(c["s"] + 0.05, c["x"], JY, 10, shard_cols, draw_fn=lambda r: S.shard(R, r * 2.6), speed=(50, 120), up=-0.5,
                size=(3, 6), life=(0.6, 1.1), spin=True, blur=(0.4, 1.0), a=(0, 40))
        f.pulse(5, c["s"], c["x"], JY, S.ring(44, 3), pal, dur=0.45, s0=50, s1=150, a0=40, blur=1.5)
    kk = seq(ph, "貴方のためなら")
    if kk:
        a, b = span(kk)
        t = kk[0]["s"]
        f.shape(7, t, t + 0.45, a, JY - 10, b, JY - 4, S.slash(b - a, 22), slash_col, a_peak=0, blur=1.5, fade_in=0.05, fade_out=0.3,
                extra="\\frz-6\\fscx40\\t(0,220,\\fscx100)", accel=0.5)
        f.burst(t + 0.25, b - 10, JY - 6, 10, ["#FFFFFF", slash_col, "#FFE0A0"], speed=(40, 100), life=(0.3, 0.7), size=(1.5, 3))


def fx_glitch(f, ph, k, c_a, c_b, extra_cols):
    R = f.rng
    for c in ph.chars:
        if c["kind"] == "punct":
            continue
        for dx, cc in ((-7, c_a), (7, c_b)):
            f.text(5, c["s"], c["s"] + 0.16, c["x"] + dx, JY, c["ch"], c["style"], 84 if c["style"] == "JP" else 66,
                   f"\\bord0\\shad0\\blur0.6\\1c{col(cc)}\\alpha&H50&\\t(60,160,\\alpha&HFF&)")
    for _ in range(int((ph.e - ph.s) * 5)):
        t = R.uniform(k.t_in + 0.3, ph.e); w = R.uniform(60, 320); h = R.uniform(2, 5)
        f.shape(7, t, t + R.uniform(0.06, 0.16), R.uniform(f.b[0] + w / 2, f.b[2] - w / 2), R.uniform(f.b[1] + 10, f.b[3] - 10),
                draw=S.rect(w, h), c1=R.choice([c_a, c_b, "#FFFFFF"]), a_peak=R.randint(60, 140), blur=0.5, fade_in=0.01, fade_out=0.02)
    ms_ = seq(ph, "見境")
    if ms_:
        t = ms_[0]["s"]; cx = mid(ms_)
        f.burst(t, cx, JY + 10, 14, extra_cols, draw_fn=lambda r: S.shard(R, r * 2.2), speed=(40, 110), up=-0.3,
                size=(3, 6), life=(0.6, 1.2), spin=True, blur=(0.5, 1.2), a=(0, 50))
        f.pulse(5, t, cx, JY, S.ellipse_ring(90, 40, 3), c_b, dur=0.6, s0=40, s1=130, a0=60, blur=1)


def fx_magic_guard(f, ph, k, big=False):
    R = f.rng
    a, b = span(ph.chars); cx = (a + b) / 2
    r = min((b - a) / 2 + 70, 520) if big else min((b - a) / 2 + 40, 420)
    ma = find(ph, "守")
    t0 = ma[0]["s"] - 0.1
    yy = JY + 38
    dur_ms = ms(k.t_end - t0)
    mc = S.magic_circle(r)
    f.floor_spin(0, t0, k.t_end, cx, yy, mc, "#7CC8FF", deg_per_s=-22 if big else -16, a_peak=110, blur=1.0, fade_in=0.5, fade_out=0.6)
    f.shape(0, t0, k.t_end, cx, yy, draw=S.flat(S.circle(r * 0.9)), c1="#2A7CFF", a_peak=200, blur=24, fade_in=0.6, fade_out=0.6)
    f.floor_spin(0, t0 + 0.3, k.t_end, cx, yy, S.rune_ring(r * 0.62, rng=R), "#BDE6FF", deg_per_s=26, a_peak=120, blur=0.8,
                 fade_in=0.5, fade_out=0.6, grow=0)
    for c in ma:
        f.pulse(5, c["s"], cx, yy, S.flat(S.ring(r, r * 0.03)), "#9ED8FF", dur=0.8, s0=60, s1=110, a0=60, blur=1.5)
        f.burst(c["s"], c["x"], JY + 20, 6, ["#BDE6FF", "#7CC8FF", "#FFFFFF"], speed=(20, 60), up=1.2, size=(2, 3.5))
    sb = seq(ph, "全て")
    if sb:
        t = sb[0]["s"]; x = mid(sb)
        f.shape(6, t, k.t_out + 0.3, x, JY + 20, x, JY - 22, S.circle(12), "#9ED8FF", a_peak=30, blur=6, fade_in=0.3, fade_out=0.4,
                c3="#3FA0FF", bord=6, a3=120, t_move=(0, 900))
        f.shape(7, t, k.t_out + 0.3, x, JY + 20, x, JY - 22, S.sparkle(14), "#FFFFFF", a_peak=0, blur=0.6, fade_in=0.3, fade_out=0.4,
                t_move=(0, 900), extra="\\t(\\frz270)")
