# -*- coding: utf-8 -*-
"""卡片: 标题 / 序章 / 间奏 / 片尾. 卡片接入清单 (salt + 统一旋钮)."""
from scene import *  # noqa: F401,F403


# ======================================================================== 卡片（标题/序章/间奏/片尾）
def card(name, t0, t1, items, fx_fn=None, seed=0):
    """items: [(text, style, fs, metric, x, y, delay, kind)]；band = 文字墨迹 + 5%"""
    xs0, ys0, xs1, ys1 = [], [], [], []
    for text, st, fs, M, x, y, dl, _ in items:
        w = M.width(text, fs, 0) * 1.05; h = M.em(fs)
        xs0.append(x - w / 2); xs1.append(x + w / 2); ys0.append(y - h * 0.62); ys1.append(y + h * 0.62)
    band = doc.band(name, min(xs0) - 96, min(ys0) - 54, max(xs1) + 96, max(ys1) + 54, t0, t1)
    for text, st, fs, M, x, y, dl, kind in items:
        ta = t0 + dl
        sh = "\\bord7\\shad0\\1a&HFF&\\3c&H100804&\\3a&H60&\\blur9"
        lk = "\\bord1.6\\shad0\\3c&H201008&\\3a&H40&\\blur0.8"
        for layer, look in ((1, sh), (2, lk)):
            if kind == "wipe":
                w = M.width(text, fs, 0) * 1.1
                doc.ev(layer, ta, t1, f"{{\\an5\\pos({x},{y}){look}\\clip({x-w/2:.0f},{y-80},{x-w/2:.0f},{y+80})\\t(0,900,0.6,\\clip({x-w/2:.0f},{y-80},{x+w/2:.0f},{y+80}))"
                                      f"\\t({ms(t1-ta)-700},{ms(t1-ta)},\\alpha&HFF&\\blur8)}}{text}", st, "card:" + name)
            else:
                doc.ev(layer, ta, t1, f"{{\\an5\\move({x},{y+14},{x},{y},0,900){look}\\alpha&HFF&\\blur6\\t(0,900,0.6,\\blur{0.8 if layer==2 else 9})"
                                      f"\\t(0,700,\\1a&H{'FF' if layer==1 else '00'}&\\3a&H{'60' if layer==1 else '40'}&)\\t({ms(t1-ta)-700},{ms(t1-ta)},\\alpha&HFF&\\blur8)}}{text}",
                       st, "card:" + name)
    p = G.card_unit(name, t0, t1, band)          # 卡片接入清单: salt + 统一旋钮
    f = FX(doc, name, band, derive(seed, p["salt"]) if p["salt"] else seed, knobs=p["knobs"])
    if fx_fn:
        fx_fn(f, band)
    return band


def title():
    T0, T1 = 0.35, 6.2
    items = [("TVアニメ『無職転生 ～異世界行ったら本気だす～』エンディングテーマ", "CARD", 28, MJ, 960, 400, 0.2, "fade"),
             ("オンリー", "TITLE", 128, MJ, 960, 510, 0.5, "wipe"),
             ("Only", "TLAT", 58, ML, 960, 612, 1.1, "fade"),
             ("唯一", "CARDCN", 34, MC, 960, 668, 1.3, "fade"),
             ("作詞・作曲・歌　大原ゆい子", "CARD", 28, MJ, 960, 720, 1.6, "fade")]

    def fx(f, b):
        R = f.rng
        f.shape(0, T0 + 0.6, T1, 960, 510, draw=S.ring(170, 2), c1="#FFE6C0", a_peak=150, blur=1, fade_in=0.6, fade_out=0.6,
                extra="\\fscx40\\fscy40\\t(0,1400,0.5,\\fscx100\\fscy100)\\fscy100")
        f.pulse(0, T0 + 0.5, 960, 510, S.ring(170, 3), "#FFD090", dur=1.6, s0=20, s1=130, a0=60, blur=2)
        f.drift(T0 + 0.8, T1, 12, ["#FFFFFF", "#FFF0D8"], S.feather, vx=(10, 30), vy=(8, 20), size=(12, 18), a=(30, 110),
                extra_fn=lambda R: sway(4, 900, 25))
        for i in range(7):
            f.pulse(6, T0 + 1.0 + i * 0.5, R.uniform(b[0] + 60, b[2] - 60), R.uniform(b[1] + 40, b[3] - 40), S.sparkle(18), "#FFF4D8",
                    dur=0.9, s0=20, s1=100, a0=20, blur=0.8, extra="\\t(\\frz90)")
    card("title", T0, T1 + 0.2, items, fx, 1)


def prologue():
    T0, T1 = 10.8, 18.0
    items = [("二度目の人生　今度こそ本気で生きる", "PRO", 54, MJ, 960, 905, 0.0, "wipe"),
             ("第二次的人生　这一次一定要全力以赴地活下去", "PROCN", 40, MC, 960, 975, 0.6, "fade")]

    def fx(f, b):
        R = f.rng
        f.pulse(0, T0 + 0.2, 960, 930, S.ellipse_ring(420, 70, 2), "#FFE0B0", dur=1.8, s0=30, s1=105, a0=80, blur=1.5)
        for i in range(6):
            f.pulse(6, T0 + 1.0 + i * 0.8, R.uniform(b[0] + 60, b[2] - 60), R.uniform(b[1] + 30, b[3] - 30), S.sparkle(16), "#FFF4D8",
                    dur=1.0, s0=20, s1=100, a0=20, blur=0.8, extra="\\t(\\frz90)")
        for _ in range(26):     # 16.5-18 风暴中的船：斜雨
            t = R.uniform(16.4, 17.9); x = R.uniform(b[0] + 30, b[2] - 30)
            f.shape(7, t, t + 0.35, x, b[1] + 20, x - 40, b[3] - 20, S.rect(1.6, 36), "#D8E4F0", a_peak=R.randint(60, 140), blur=0.6,
                    fade_in=0.05, fade_out=0.1, extra="\\frz-20")
    card("pro", T0, T1, items, fx, 2)


def interlude():
    T0, T1 = 80.2, 88.2
    items = [("この世界で出会った　大切な人たちへ", "PRO", 54, MJ, 960, 905, 0.0, "wipe"),
             ("致在这个世界相遇的　每一个重要的人", "PROCN", 40, MC, 960, 975, 0.6, "fade")]

    def fx(f, b):
        f.drift(T0, T1, 26, ["#FFD060", "#FFB040", "#F0C050", "#FFE090"], S.leaf, vx=(10, 40), vy=(8, 24), size=(6, 10), a=(20, 100),
                extra_fn=lambda R: sway(4, 800, 30))
        for sx in (b[0] + 60, b[2] - 60):   # 84 烛光
            f.shape(6, 83.8, T1, sx, 905, draw=S.candle_flame(24), c1="#FFD27A", a_peak=10, blur=1.5, c3=FIRE, bord=3, a3=80,
                    fade_in=0.5, fade_out=0.6, extra=sway(12, 300, 8))
            f.glow(0, 83.8, T1, sx, 905, 36, 40, "#FFB04A", a_peak=170, blur=16, fade_in=0.5, fade_out=0.6)
    card("mid", T0, T1, items, fx, 3)


def outro():
    T0, T1 = 218.4, 227.4
    items = [("オンリー", "TITLE", 96, MJ, 960, 870, 0.0, "wipe"),
             ("Only　—　唯一", "CARDCN", 34, MC, 960, 958, 0.6, "fade"),
             ("作詞・作曲・歌　大原ゆい子", "CARD", 28, MJ, 960, 1010, 1.0, "fade")]

    def fx(f, b):
        R = f.rng
        f.drift(T0, T1, 16, ["#FFFFFF", "#FFF0D8"], S.feather, vx=(8, 24), vy=(6, 16), size=(12, 16), a=(30, 110),
                extra_fn=lambda R: sway(4, 900, 25))
        for i in range(8):
            f.pulse(6, T0 + 0.8 + i * 0.9, R.uniform(b[0] + 50, b[2] - 50), R.uniform(b[1] + 30, b[3] - 30), S.sparkle(16), "#FFF4D8",
                    dur=1.0, s0=20, s1=100, a0=20, blur=0.8, extra="\\t(\\frz90)")
    card("out", T0, T1, items, fx, 4)
