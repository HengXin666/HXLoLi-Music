"""kfx verbs (1/2): cutting and pushing verbs."""
import math, random
from kfx_core import kf, ev, bgr, mix, WHITE, BLACK, hexrgb
from kfx_draw import *
from kfx_draw import _shift
from kfx_hit import *
from kfx_glyph import hp_poly
from kfx_core import Track


def V_cut(c):
    """斩: when a glyph has been sung my blade comes down on it. Wind-up (the glyph braces), a heavy swing whose trail
    is thick at the end, a flash on impact, the blow shakes the whole line, the glyph is hacked along the stroke: the
    upper part is knocked along the swing and stays crooked, the lower part is slammed down, and the corner the edge
    leaves is hacked off and falls away. Consecutive glyphs are struck forehand / backhand. ·离 = the parts keep drifting
    apart until the line leaves (there is no going back)."""
    drift = '离' in c.args
    for k, g in enumerate(c.span):
        if has_pieces(g):
            continue
        hit = g.b
        sgn = 1 if k % 2 == 0 else -1
        th = sgn * (34 + c.rnd.uniform(-6, 6))
        r = math.radians(th)
        d = (math.cos(r), math.sin(r))
        n_ = (-d[1], d[0])
        # wind-up: brace away from the blow
        add(g, (hit - 0.14, {}), (hit - 0.02, dict(dx=-d[0] * 3, dy=-d[1] * 3 - 2, rz=-sgn * 3, sy=0.04)), (hit, {}))
        # the swing
        L = g.size * 1.6
        S = (g.x - d[0] * L - n_[0] * 6, g.y - d[1] * L - n_[1] * 6)
        E = (g.x + d[0] * L * 1.15, g.y + d[1] * L * 1.15)
        slash(c.line.fx, c.name, hit, S, E, c.col, th=17, bulge=sgn * 12)
        flash(c.line.fx, c.name, hit, (g.x, g.y), d, c.col, size=g.size * 0.9)
        sparks(c.line.fx, c.name, c.rnd, hit + 0.02, (g.x + d[0] * g.w * .45, g.y + d[1] * g.w * .45), d, c.col)
        shake_line(c.line, hit, g.x, d, amp=7)
        # the glyph is hacked
        off = c.rnd.uniform(-4, 4)
        up, lo = cut_planes(th, off)
        k_ = g.w * 0.42                              # the tip the edge takes off
        tip = (-d[0], -d[1], -k_)                    # d.p >= k  -> chunk
        keep = (d[0], d[1], k_)
        until = g.t_end
        dd = 1.0 if not drift else 1.0
        top_settle = dict(dx=d[0] * 7, dy=d[1] * 7 + 2, rz=sgn * 5)
        bot_settle = dict(dx=-d[0] * 2, dy=4, rz=-sgn * 2)
        if drift:
            top_tr = kf((hit, {}), (hit + 0.06, dict(dx=d[0] * 15, dy=d[1] * 15 + 4, rz=sgn * 9)), (hit + 0.38, top_settle),
                        (until, dict(dx=d[0] * 22, dy=d[1] * 22 - 6, rz=sgn * 9)))
            bot_tr = kf((hit, {}), (hit + 0.06, dict(dx=-d[0] * 4, dy=6, rz=-sgn * 3)), (hit + 0.38, bot_settle),
                        (until, dict(dx=-d[0] * 10, dy=12, rz=-sgn * 4)))
        else:
            top_tr = impulse(hit, dict(dx=d[0] * 15, dy=d[1] * 15 + 4, rz=sgn * 9), top_settle, until)
            bot_tr = impulse(hit, dict(dx=-d[0] * 4, dy=6, rz=-sgn * 3), bot_settle, until)
        chunk_tr = kf((hit, {}), (hit + 0.08, dict(dx=d[0] * 26, dy=d[1] * 26 + 2, rz=sgn * 14)),
                      (hit + 0.7, dict(dx=d[0] * 80, dy=d[1] * 80 + 70, rz=sgn * 38, am=-1)))
        g.pieces += [piece(hit, [up, keep], [top_tr], ruby_planes=[up] if sgn > 0 else [up]),
                     piece(hit, [lo], [bot_tr]),
                     piece(hit, [up, tip], [chunk_tr])]
        # the wound: the fill of a hacked glyph takes the blade's colour
        g.dim.append((hit, mix(c.col, WHITE, 0.4)))
        # the seam glows a moment along the cut
        sx_, sy_ = g.x + n_[0] * off, g.y + n_[1] * off
        c.line.fx.append(ev(7, hit, hit + 0.5, 'FX', c.name, f"\\an7\\pos(0,0)\\bord0\\shad0\\1c{bgr(mix(c.col, WHITE, .6))}\\blur1.5"
                            f"\\t(100,500,\\alpha&HFF&)\\p1",
                            poly_d(blade_pts((sx_ - d[0] * g.w * .6, sy_ - d[1] * g.w * .6), (sx_ + d[0] * g.w * .6, sy_ + d[1] * g.w * .6), 4, 0)) + "{\\p0}"))


def V_bigcut(c):
    """大斩·到<词>: one swing across the line, from the first glyph to the end word. The line braces first, the arc sweeps
    left to right, each glyph is hacked along the same stroke as the edge passes it (glyphs already hacked are knocked
    again), the end of the swing throws sparks and the whole line shakes."""
    end = c.arg(0)
    gl = c.line.glyphs
    j = c.glyph_by_text(end) if end else gl.index(c.span[-1])
    j = gl.index(c.span[-1]) if j is None else j
    t = (gl[j + 1].a if j + 1 < len(gl) else gl[j].b + 0.12)
    sweep = 0.2
    t0 = t - sweep
    x0, x1 = gl[0].x - gl[0].w / 2 - 70, gl[j].x + gl[j].w / 2 + 70
    y = gl[0].y
    slope = math.radians(9)
    d = (math.cos(slope), math.sin(slope))
    # brace
    for g in gl[:j + 1]:
        add(g, (t0 - 0.2, {}), (t0, dict(dx=-6, rz=-2.5, sy=0.05)), (t0 + 0.05, {}))
    S = (x0, y - math.tan(slope) * (x1 - x0) / 2)
    E = (x1, y + math.tan(slope) * (x1 - x0) / 2)
    slash(c.line.fx, c.name, t, S, E, c.col, th=30, bulge=-22, reveal=sweep, life=0.5)
    for g in gl[:j + 1]:
        tt = t0 + sweep * (g.x - x0) / (x1 - x0)
        tt = max(tt, g.b)
        yl = S[1] + (E[1] - S[1]) * (g.x - x0) / (x1 - x0) - g.y      # the stroke's height at this glyph
        if has_pieces(g):
            for pc in g.pieces:
                pc['trs'].append(kf((tt, {}), (tt + 0.05, dict(dx=10, dy=3)), (tt + 0.3, dict(dx=4, dy=1)), (g.t_end, dict(dx=4, dy=1))))
            continue
        up, lo = cut_planes(math.degrees(slope), yl * math.cos(slope))
        g.pieces += [piece(tt, [up], [impulse(tt, dict(dx=16, dy=3, rz=4), dict(dx=8, dy=1, rz=2.5), g.t_end)], ruby_planes=[up]),
                     piece(tt, [lo], [impulse(tt, dict(dx=-3, dy=6, rz=-1.5), dict(dx=-1, dy=3, rz=-0.8), g.t_end)])]
        g.dim.append((tt, mix(c.col, WHITE, 0.4)))
    sparks(c.line.fx, c.name, c.rnd, t, (x1 - 40, E[1]), d, c.col, n=14, spread=40, speed=(80, 170), life=0.55)
    flash(c.line.fx, c.name, t, (x1 - 50, E[1]), d, c.col, size=110, life=0.22)
    shake_line(c.line, t, x1, d, amp=10, fall=600)


# ---------------------------------------------------------------- other breaks

def V_tear(c):
    """撕: I tear the sung glyph down the middle along a ragged line; the halves are pulled apart and hang crooked,
    a few shreds fall from the tear."""
    for g in c.span:
        if has_pieces(g):
            continue
        t = g.b
        H = 420
        zig = [(0, -H)]
        n = 7
        for k in range(n + 1):
            yy = -g.size * 0.8 + 1.6 * g.size * k / n
            zig.append(((4 if k % 2 else -4) + c.rnd.uniform(-2, 2), yy))
        zig.append((0, H))
        left = [(-H, -H)] + zig + [(-H, H)]
        right = [(H, -H)] + zig + [(H, H)]
        g.pieces += [dict(t=t, poly=left, rpoly=left, trs=[impulse(t, dict(dx=-10, rz=-7), dict(dx=-6, rz=-4), g.t_end, t_settle=0.45)]),
                     dict(t=t, poly=right, rpoly=None, trs=[impulse(t, dict(dx=10, rz=8, dy=2), dict(dx=6, rz=5, dy=2), g.t_end, t_settle=0.45)])]
        for k in range(3):
            a = (g.x + c.rnd.uniform(-3, 3), g.y + c.rnd.uniform(-g.size * .4, g.size * .4))
            b = (a[0] + c.rnd.uniform(-18, 18), a[1] + c.rnd.uniform(50, 80))
            c.line.fx.append(shape_mv(6, t, t + 0.8, a, b, rect(4, 7), f"\\1c{bgr(c.light)}\\blur0.5\\t(0,800,\\frz{c.rnd.choice([-60,60])})\\t(400,800,\\alpha&HFF&)", (0, 800)))


def V_crack(c):
    """裂: the sung glyph cracks into three shards around a point; the shards jump apart and stay fractured."""
    for g in c.span:
        if has_pieces(g):
            continue
        t = g.b
        o = (c.rnd.uniform(-6, 6), c.rnd.uniform(-6, 6))
        angs = [c.rnd.uniform(-20, 20) - 90, c.rnd.uniform(-20, 20) + 30, c.rnd.uniform(-20, 20) + 150]
        rays = [(math.cos(math.radians(a)), math.sin(math.radians(a))) for a in angs]
        for k in range(3):
            r1, r2 = rays[k], rays[(k + 1) % 3]
            # wedge between r1 and r2 (counter-clockwise in screen = increasing angle)
            p1 = (-r1[1], r1[0])      # left normal of r1
            p2 = (r2[1], -r2[0])
            planes = [(-p1[0], -p1[1], -(-p1[0] * o[0] - p1[1] * o[1])), (-p2[0], -p2[1], -(-p2[0] * o[0] - p2[1] * o[1]))]
            planes = [(-p1[0], -p1[1], -p1[0] * o[0] * -1 * -1 - p1[1] * o[1] * -1 * -1)]
            # keep points q with p1.(q-o) >= 0 and p2.(q-o) >= 0
            planes = [(-p1[0], -p1[1], -(p1[0] * o[0] + p1[1] * o[1])), (-p2[0], -p2[1], -(p2[0] * o[0] + p2[1] * o[1]))]
            mid = (r1[0] + r2[0], r1[1] + r2[1])
            m = math.hypot(*mid) or 1
            mid = (mid[0] / m, mid[1] / m)
            g.pieces.append(dict(t=t, poly=hp_poly(planes), rpoly=hp_poly(planes) if mid[1] < -0.3 else None,
                                 trs=[impulse(t, dict(dx=mid[0] * 9, dy=mid[1] * 9, rz=(k - 1) * 5), dict(dx=mid[0] * 4, dy=mid[1] * 4, rz=(k - 1) * 3), g.t_end)]))
        if not any(p['rpoly'] for p in g.pieces):
            g.pieces[0]['rpoly'] = hp_poly([(0, 1, 0)])
        flash(c.line.fx, c.name, t, (g.x + o[0], g.y + o[1]), (0, 1), c.col, size=g.size * 0.5, life=0.12)


# ---------------------------------------------------------------- body verbs (the singer moves the words)

def V_shove(c):
    """推: I shove the first word; the push runs down the span like a row of bodies, each knocked over a little."""
    t0 = c.span[0].a
    for k, g in enumerate(c.span):
        t = t0 + k * 0.055
        add(g, (t, {}), (t + 0.07, dict(dx=10, rz=6)), (t + 0.24, dict(dx=-2, rz=-1.5)), (t + 0.4, {}))
    g = c.span[0]
    dust(c.line.fx, c.name, c.rnd, t0, g.x - g.w / 2, g.y + g.size * 0.6, n=3)


def V_pull(c):
    """拉: I pull each sung glyph toward the next word; it stretches and snaps back."""
    for g in c.span:
        a = g.a
        add(g, (a, {}), (a + 0.12, dict(sx=0.24, dx=7)), (a + 0.2, dict(sx=-0.06, dx=-1)), (a + 0.32, {}))


def V_press(c):
    """压: I press the sung glyph down flat; dust puffs out at its feet; it stays a little crushed."""
    for g in c.span:
        a = g.a
        add(g, (a, {}), (a + 0.06, dict(sy=-0.24, sx=0.1, dy=9)), (a + 0.3, dict(sy=-0.06, dy=2)), (g.t_out, dict(sy=-0.06, dy=2)))
        dust(c.line.fx, c.name, c.rnd, a + 0.05, g.x, g.y + g.size * 0.62, n=4, spread=28)


def V_bounce(c):
    """弹: the sung glyph springs up and lands with a squash."""
    for g in c.span:
        a = g.a
        add(g, (a, {}), (a + 0.05, dict(sy=-0.12, sx=0.08)), (a + 0.2, dict(dy=-24, sy=0.08, sx=-0.05)),
            (a + 0.36, dict(sy=-0.1, sx=0.08)), (a + 0.48, {}))


def V_drop(c):
    """坠: the sung glyph drops with its weight, lands with a thud and stays low."""
    for g in c.span:
        b = g.b
        add(g, (b, {}), (b + 0.15, dict(dy=16)), (b + 0.22, dict(dy=11, sy=-0.08, sx=0.05)), (b + 0.32, dict(dy=13)), (g.t_out, dict(dy=13)))
        dust(c.line.fx, c.name, c.rnd, b + 0.15, g.x, g.y + g.size * 0.62 + 16, n=2, spread=22)


def V_lift(c):
    """起: the sung glyph is lifted and held up."""
    for g in c.span:
        add(g, (g.a, {}), (g.a + 0.35, dict(dy=-11)), (g.t_out, dict(dy=-11)))
        g.glow = max(g.glow, 0.5)


def V_grip(c):
    """握: I grip the word; each sung glyph is squeezed narrow, shudders twice, and is let go."""
    for g in c.span:
        a = g.a
        add(g, (a, {}), (a + 0.08, dict(sx=-0.2, sy=0.05)), (a + 0.38, dict(sx=-0.16)), (a + 0.43, dict(sx=-0.13, dx=1.8)),
            (a + 0.48, dict(sx=-0.16, dx=-1.8)), (a + 0.53, dict(sx=-0.14)), (max(g.b, a + 0.55) + 0.2, {}))


def V_pierce(c):
    """刺: an unseen thrust runs through the span from the left; every glyph recoils as it passes (no line drawn)."""
    sp = c.span
    t = sp[0].a
    xa, xb = sp[0].x - sp[0].w / 2 - 160, sp[-1].x + sp[-1].w / 2 + 50
    dur = 0.14
    for g in sp:
        tt = t - dur + dur * (g.x - xa) / (xb - xa)
        add(g, (tt, {}), (tt + 0.05, dict(dx=7, rz=4)), (tt + 0.3, {}))


