"""kfx verbs (2/2): body, prop and atmosphere verbs."""
import math, random
from kfx_core import kf, ev, bgr, mix, WHITE, BLACK, hexrgb
from kfx_draw import *
from kfx_draw import _shift
from kfx_hit import *
from kfx_glyph import hp_poly
from kfx_core import Track
from kfx_verbs_cut import *


def V_knock(c):
    """敲: I knock on the glyph from above; it squashes and bounces back (no ring drawn)."""
    for g in c.span:
        a = g.a
        add(g, (a, {}), (a + 0.04, dict(dy=5, sy=-0.15, sx=0.08)), (a + 0.18, dict(dy=-3)), (a + 0.3, {}))


def V_blow(c):
    """吹: a wind I breathe pushes the words; they lean with it and stay leaning (no streaks drawn)."""
    for g in c.span:
        add(g, (g.a, {}), (g.a + 0.3, dict(rz=-7, dx=5)), (g.a + 0.7, dict(rz=-3, dx=3)), (g.t_out, dict(rz=-3, dx=3)))


def V_freeze(c):
    """冻: the sung glyph freezes: its fill turns to ice, frost spikes grow on its edges, it shivers once and goes rigid."""
    ice = (210, 236, 255)
    for g in c.span:
        b = g.b
        g.dim.append((b, ice))
        add(g, (b, {}), (b + 0.04, dict(dx=1.5)), (b + 0.08, dict(dx=-1.5)), (b + 0.12, {}))
        for k in range(4):
            ang = c.rnd.uniform(0, 2 * math.pi)
            p = (g.x + math.cos(ang) * g.w * 0.48, g.y + math.sin(ang) * g.size * 0.6)
            c.line.fx.append(shape_mv(9, b + k * 0.05, g.t_out + 0.2, p, p, star4(6),
                                      f"\\1c&HFFF4E8&\\blur0.6\\alpha&HFF&\\fscx20\\fscy20\\frz{c.rnd.uniform(0,45):.0f}"
                                      f"\\t(0,200,\\alpha&H20&\\fscx100\\fscy100)\\t({ms(g.t_out-b-k*.05)},{ms(g.t_out-b-k*.05+0.2)},\\alpha&HFF&)"))


def V_melt(c):
    """融: the sung glyph sags as if softening and drips from its bottom."""
    for g in c.span:
        b = g.b
        add(g, (b, {}), (b + 0.8, dict(sy=0.12, dy=6, sx=-0.04)), (g.t_out, dict(sy=0.12, dy=6, sx=-0.04)))
        for k in range(2):
            x = g.x + c.rnd.uniform(-g.w / 3, g.w / 3)
            y = g.y + g.size * 0.6
            c.line.fx.append(shape_mv(6, b + 0.2 + k * 0.25, b + 1.3 + k * 0.25, (x, y), (x, y + 34), drop(7, 11),
                                      f"\\1c{bgr(c.light)}\\blur0.6\\alpha&H30&\\fscy60\\t(0,300,\\fscy130)\\t(700,1100,\\alpha&HFF&)", (0, 1100)))


def V_heart(c):
    """心跳: the word beats twice like a heart as it is sung, then lies still."""
    for g in c.span:
        a = g.a
        add(g, (a, {}), (a + 0.08, dict(sx=0.11, sy=0.11)), (a + 0.18, {}), (a + 0.28, dict(sx=0.06, sy=0.06)), (a + 0.42, {}))
        g.glow = max(g.glow, 0.4)


def V_tilt(c):
    """倾: the sung glyph tips over with its weight and stays tipped."""
    for k, g in enumerate(c.span):
        b = g.b
        s = 1 if k % 2 == 0 else -1
        add(g, (b, {}), (b + 0.2, dict(rz=12 * s, dx=3 * s)), (b + 0.32, dict(rz=8 * s, dx=2 * s)), (b + 0.42, dict(rz=10 * s, dx=2.5 * s)),
            (g.t_out, dict(rz=10 * s, dx=2.5 * s)))


def V_sweep(c):
    """拂: I brush the word aside; it is swept left and slides back."""
    for g in c.span:
        a = g.a
        add(g, (a, {}), (a + 0.12, dict(dx=-11, rz=-6)), (a + 0.45, dict(dx=2, rz=1)), (a + 0.6, {}))


def V_link(c):
    """牵: each glyph is tugged toward the middle of the span when it is sung (no thread drawn)."""
    sp = c.span
    x0, x1 = sp[0].x - sp[0].w / 2, sp[-1].x + sp[-1].w / 2
    w = x1 - x0
    cx = (x0 + x1) / 2
    for g in sp:
        k = (cx - g.x) / max(1, w / 2)
        add(g, (g.b, {}), (g.b + 0.12, dict(dx=k * 6, rz=k * 2)), (g.b + 0.4, dict(dx=k * 3)), (g.t_out, dict(dx=k * 3)))


def V_stamp(c):
    """印: I press the word like a seal; the glyph is pushed in and a soft seal mark in the line colour flashes
    under it and fades."""
    for g in c.span:
        a = g.a
        add(g, (a, {}), (a + 0.05, dict(sx=-0.08, sy=-0.08, dy=2)), (a + 0.2, {}))
        w, h = g.w + 8, g.size * 1.25
        life = min(0.7, g.t_out - a)
        c.line.fx.append(shape_mv(0, a, a + life, (g.x, g.y), (g.x, g.y), ring(w, h, 4) if False else rect(w, h, 8),
                                  f"\\1c{bgr(c.col)}\\blur6\\alpha&HFF&\\fscx135\\fscy135\\t(0,90,\\alpha&HB0&\\fscx100\\fscy100)"
                                  f"\\t(150,{ms(life)},\\alpha&HFF&)"))


def V_embrace(c):
    """抱: I hold the words: as they are sung they are drawn toward the middle of the span and pressed together, warmed
    by the line colour; when the last one is sung the whole span is squeezed once."""
    sp = c.span
    x0, x1 = sp[0].x - sp[0].w / 2, sp[-1].x + sp[-1].w / 2
    cx = (x0 + x1) / 2
    t1 = sp[-1].b
    for g in sp:
        k = (cx - g.x) / max(1, (x1 - x0) / 2)
        add(g, (g.a, {}), (g.a + 0.3, dict(dx=k * 10, sx=-0.06, rz=k * 3)), (g.t_out, dict(dx=k * 10, sx=-0.06, rz=k * 3)))
        add(g, (t1, {}), (t1 + 0.12, dict(dx=k * 5, sx=-0.06, sy=0.05)), (t1 + 0.35, {}))
        g.glow = max(g.glow, 0.7)
        g.tint = g.tint or mix(c.col, WHITE, 0.7)



def V_jolt(c):
    """顿: the sung glyph takes a hit and shakes sideways once."""
    for g in c.span:
        a = g.a
        g.tracks.append(kf((a, {}), (a + 0.05, dict(dx=-5)), (a + 0.11, dict(dx=4)), (a + 0.17, dict(dx=-2)), (a + 0.24, {})))


def V_highlight(c):
    """亮: the verb. Sung fill takes the line colour's light tint and a stronger glow until it leaves."""
    for g in c.span:
        g.tint = mix(c.col, WHITE, 0.62)
        g.glow = 1.0


def V_cover(c):
    """盖: covered glyphs are pressed down and dimmed as they are sung (no cloth band drawn over them)."""
    for g in c.span:
        g.tracks.append(kf((g.a, {}), (g.a + 0.25, dict(dy=5, am=-0.35)), (g.t_out, dict(dy=5, am=-0.35))))


def V_erase(c):
    """擦: an eraser follows the singing across the span; erased glyphs turn ashen and shed dust."""
    sp = c.span
    y = sp[0].y
    h = sp[0].size * 0.9
    ash = (120, 116, 112)
    keys = [(sp[0].a - 0.08, sp[0].x - sp[0].w / 2 - 20)] + [(g.b, g.x + g.w / 2) for g in sp]
    for (ta, xa), (tb, xb) in zip(keys, keys[1:]):
        c.line.fx.append(shape_mv(7, ta, tb, (xa, y - 4), (xb, y - 4), rect(20, h * 0.8, 5),
                                  f"\\1c&HF4F4F4&\\blur0.8\\alpha&H40&"))
        c.line.fx.append(shape_mv(7, ta, tb, (xa, y - 4 - h * 0.28), (xb, y - 4 - h * 0.28), rect(26, h * 0.42, 6),
                                  f"\\1c{bgr(c.col)}\\blur0.8\\alpha&H20&"))
    c.line.fx.append(shape_mv(7, keys[-1][0], keys[-1][0] + 0.35, (keys[-1][1], y - 4), (keys[-1][1] + 20, y - 30),
                              rect(26, h, 6), "\\1c&HF4F4F4&\\blur0.8\\t(\\alpha&HFF&)"))
    for g in sp:
        g.dim.append((g.b, ash))
        g.tracks.append(kf((g.b, {}), (g.b + 0.3, dict(am=-0.45)), (g.t_out, dict(am=-0.45))))
        for k in range(5):
            a = (g.x + c.rnd.uniform(-g.w / 2, g.w / 2), y + h / 2)
            b = (a[0] + c.rnd.uniform(-10, 10), a[1] + c.rnd.uniform(25, 45))
            c.line.fx.append(shape_mv(6, g.b, g.b + 0.6, a, b, rect(3, 3), "\\1c&HD8D8D8&\\t(300,600,\\alpha&HFF&)", (0, 600)))


def V_bind(c):
    """缚: each glyph is squeezed as if bound when sung. ·断 = at the end it bursts free (no chain drawn)."""
    sp = c.span
    t_break = sp[-1].b if '断' in c.args else None
    t_end = t_break or sp[-1].t_out
    for g in sp:
        g.tracks.append(kf((g.a, {}), (g.a + 0.06, dict(sx=-0.12, sy=0.04)), (g.a + 0.3, dict(sx=-0.04)), (t_end, dict(sx=-0.04))))
        if t_break:
            g.tracks.append(kf((t_break, {}), (t_break + 0.08, dict(sx=0.14, sy=0.1)), (t_break + 0.35, dict(sx=0.04))))


def V_ward(c):
    """护: each sung glyph is lifted and a spark rises from it; ·大 = the whole line is lifted at the end (no arc drawn)."""
    sp = c.span
    y = sp[0].y + sp[0].size * 0.62
    for g in sp:
        c.line.fx.append(shape_mv(4, g.a, g.a + 0.6, (g.x, y), (g.x, y - 22), rect(2, 14),
                                  f"\\1c{bgr(c.light)}\\blur1\\alpha&H30&\\t(200,600,\\alpha&HFF&)", (0, 600)))
        g.tracks.append(kf((g.a, {}), (g.a + 0.25, dict(dy=-5)), (g.t_out, dict(dy=-5))))
    if '大' in c.args:
        t = sp[-1].b
        for g in c.line.glyphs:
            g.tracks.append(kf((t, {}), (t + 0.4, dict(dy=-6)), (g.t_out, dict(dy=-6))))


def V_reach(c):
    """伸: the word leans out to meet what reaches for it (no line drawn)."""
    for g in c.span:
        g.tracks.append(kf((g.a, {}), (g.a + 0.2, dict(dx=-4)), (g.t_out, dict(dx=-4))))


def V_fall(c):
    """落: a drop falls from the sung glyph."""
    for g in c.span[-2:] if len(c.span) > 2 else c.span:
        t = g.b
        c.line.fx.append(shape_mv(6, t, t + 0.9, (g.x, g.y + g.size * 0.45), (g.x, g.y + g.size * 1.4), drop(10, 16),
                                  f"\\1c{bgr(c.light)}\\blur0.8\\alpha&H20&\\t(500,900,\\alpha&HFF&)", (0, 900)))


def V_overflow(c):
    """溢: the word overflows; drops rise off every sung glyph and spill outward."""
    for g in c.span:
        for k in range(6):
            t = g.a + k * 0.05
            a = (g.x + c.rnd.uniform(-g.w / 3, g.w / 3), g.y - g.size * 0.3)
            b = (a[0] + c.rnd.uniform(-40, 40), a[1] - c.rnd.uniform(40, 80))
            c.line.fx.append(shape_mv(6, t, t + 0.8, a, b, drop(7, 10),
                                      f"\\1c{bgr(c.light)}\\blur0.6\\alpha&H30&\\t(400,800,\\alpha&HFF&)", (0, 800)))


def V_drift(c):
    """飘·<花瓣|叶|雪>: a few pieces pass through the span at glyph height while it is sung."""
    kind = c.arg(0, '花瓣')
    sp = c.span
    x0, x1 = sp[0].x - sp[0].w, sp[-1].x + sp[-1].w
    for k in range(7):
        t = sp[0].a + (sp[-1].b - sp[0].a) * k / 7
        y = sp[0].y + c.rnd.uniform(-30, 30)
        a = (x0 - 30 + c.rnd.uniform(0, 40), y - 20)
        b = (x1 + c.rnd.uniform(0, 60), y + c.rnd.uniform(10, 40))
        draw = {'花瓣': petal(16, 9), '叶': leaf(20, 10), '雪': oval(5, 5)}.get(kind, petal(16, 9))
        col = {'雪': (250, 250, 255)}.get(kind, c.light)
        c.line.fx.append(shape_mv(6, t, t + 1.4, a, b, draw, f"\\1c{bgr(col)}\\blur0.6\\alpha&H30&\\t(1000,1400,\\alpha&HFF&)"))


def V_glow(c):
    """照: soft colour light behind the span (atmosphere only, no subject)."""
    sp = c.span
    for g in sp:
        c.line.fx.append(ev(0, g.a, g.t_out + 0.2, g.style, c.name,
                            f"\\an5\\pos({g.x:.1f},{g.y:.1f})\\bord10\\shad0\\blur16\\1a&HFF&\\3c{bgr(c.col)}\\3a&HFF&"
                            f"\\t(0,300,\\3a&H90&)\\t({ms(g.t_out-g.a)},{ms(g.t_out-g.a+0.2)},\\3a&HFF&)", g.ch))


def V_echo(c):
    """余韵·<上|下|扩>: a pale copy leaves the sung glyph upward / downward / growing, and fades."""
    d = c.arg(0, '上')
    for g in c.span:
        t = g.b
        dy = {'上': -36, '下': 30}.get(d, 0)
        sc = '\\fscx140\\fscy140' if d == '扩' else ''
        c.line.fx.append(ev(5, t, t + 0.8, g.style, c.name,
                            f"\\an5\\move({g.x:.1f},{g.y:.1f},{g.x:.1f},{g.y+dy:.1f},0,800)\\bord0\\shad0\\1c{bgr(c.light)}"
                            f"\\alpha&H70&\\blur1\\t(0,800,0.8,\\alpha&HFF&\\blur4{sc})", g.ch))


def V_tiptoe(c):
    """踮: after it is sung the span keeps rising onto its toes and settling, glyph by glyph, until it leaves."""
    per = 0.56
    for k, g in enumerate(c.span):
        t = g.b + 0.05 + k * 0.07
        keys = [(t, {})]
        up = True
        while t + per / 2 < g.t_out - 0.05:
            t += per / 2
            keys.append((t, dict(dy=-9, sy=0.04) if up else {}))
            up = not up
        keys.append((g.t_out, {}))
        g.tracks.append(kf(*keys))


def V_dance(c):
    """跳: on the beat the span hops, neighbours in counter-phase, until it leaves."""
    b0, bt = c.P.get('beat0', 0), c.P.get('beat', 0) or 0.5
    for k, g in enumerate(c.span):
        start = g.b
        t = b0 + math.ceil((start - b0) / bt) * bt
        keys = [(start, {})]
        n = 0
        while t + bt <= g.t_out:
            s = (1 if (n + k) % 2 == 0 else -1)
            keys.append((t + bt * 0.25, dict(dy=-10 * s)))
            keys.append((t + bt * 0.5, {}))
            t += bt
            n += 1
        keys.append((g.t_out, {}))
        g.tracks.append(kf(*keys))


def V_star(c):
    """星: one small four-point star lights beside the word (atmosphere)."""
    g = c.span[-1]
    x, y = g.x + g.w / 2 + 10, g.y - g.size * 0.6
    c.line.fx.append(shape_mv(5, g.a, g.t_out + 0.2, (x, y), (x, y - 6), star4(9),
                              f"\\1c&HFFFFFF&\\blur0.8\\alpha&HFF&\\fscx40\\fscy40\\t(0,250,\\alpha&H10&\\fscx100\\fscy100)"
                              f"\\t({ms(g.t_out-g.a)},{ms(g.t_out-g.a+0.2)},\\alpha&HFF&)"))


