"""kfx hit: glyph-scale building blocks shared by verbs (cuts, impulses, blades, sparks)."""
import math, random
from kfx_core import kf, ev, bgr, mix, WHITE, BLACK, hexrgb
from kfx_draw import *
from kfx_glyph import hp_poly
from kfx_core import Track


def poly_d(pts):
    return 'm ' + ' '.join((f"{x:.1f} {y:.1f}" if k != 1 else f"l {x:.1f} {y:.1f}") for k, (x, y) in enumerate(pts))


def add(g, *pairs):
    g.tracks.append(kf(*pairs))


def has_pieces(g):
    return bool(g.pieces)


def cut_planes(theta, off):
    """the cut line at angle theta (deg, screen) through the point off*normal; returns (upper, lower) half-planes."""
    r = math.radians(theta)
    nx, ny = -math.sin(r), math.cos(r)          # normal pointing down-ish
    return (nx, ny, off), (-nx, -ny, -off)


def piece(t, planes, trs, ruby_planes=None):
    return dict(t=t, poly=hp_poly(planes), rpoly=hp_poly(ruby_planes) if ruby_planes is not None else None, trs=trs)


def impulse(t, peak, settle, hold_until, t_peak=0.06, t_settle=0.38):
    """hit -> peak pose fast, then settle to a resting pose that stays."""
    return kf((t, {}), (t + t_peak, peak), (t + t_settle, settle), (hold_until, settle))


def shake_line(line, t, x, d, amp=7.0, fall=320.0):
    """the blow travels through the whole line: every glyph is jolted along d, the near ones more, damped."""
    for g in line.glyphs:
        a = amp * math.exp(-abs(g.x - x) / fall)
        if a < 0.6:
            continue
        add(g, (t, {}), (t + 0.04, dict(dx=d[0] * a, dy=d[1] * a)), (t + 0.1, dict(dx=-d[0] * a * .45, dy=-d[1] * a * .45)),
            (t + 0.17, dict(dx=d[0] * a * .18, dy=d[1] * a * .18)), (t + 0.27, {}))


def blade_pts(S, E, th, bulge):
    """a slash: thin at both ends, thick in the middle, bowed by bulge along the normal."""
    dx, dy = E[0] - S[0], E[1] - S[1]
    L = math.hypot(dx, dy) or 1
    nx, ny = -dy / L, dx / L
    top, bot = [], []
    N = 14
    for k in range(N + 1):
        u = k / N
        cx = S[0] + dx * u + nx * bulge * math.sin(math.pi * u)
        cy = S[1] + dy * u + ny * bulge * math.sin(math.pi * u)
        w = th * (math.sin(math.pi * u) ** 0.6) * (0.35 + 0.65 * u)   # heavier toward the end of the swing
        top.append((cx + nx * w / 2, cy + ny * w / 2))
        bot.append((cx - nx * w / 2, cy - ny * w / 2))
    return top + bot[::-1]


def slash(fx, name, t, S, E, col, th=14, bulge=10, reveal=0.06, life=0.32, glow=True, ghost=True):
    """the blade's trail, drawn in screen coordinates; it is revealed along its length in `reveal` seconds."""
    xs = [S[0], E[0]]
    x0, x1 = min(xs) - 40, max(xs) + 40
    y0, y1 = min(S[1], E[1]) - 80, max(S[1], E[1]) + 80
    ltr = E[0] >= S[0]
    c0 = f"\\clip({x0:.0f},{y0:.0f},{x0 if ltr else x1:.0f},{y1:.0f})" if ltr else f"\\clip({x1:.0f},{y0:.0f},{x1:.0f},{y1:.0f})"
    c1 = f"\\t(0,{ms(reveal)},\\clip({x0:.0f},{y0:.0f},{x1:.0f},{y1:.0f}))"
    if not ltr:
        c0 = f"\\clip({x1:.0f},{y0:.0f},{x1:.0f},{y1:.0f})"
    t0 = t - reveal
    layers = []
    if glow:
        layers.append((6, th * 2.2, f"\\1c{bgr(col)}\\blur9\\alpha&H70&"))
    layers += [(7, th, f"\\1c{bgr(mix(col, WHITE, .45))}\\blur1.4\\alpha&H10&"), (8, th * .32, "\\1c&HFFFFFF&\\blur0.6")]
    for lay, w, tags in layers:
        fx.append(ev(lay, t0, t + life, 'FX', name, f"\\an7\\pos(0,0)\\bord0\\shad0{tags}{c0}{c1}"
                     f"\\t({ms(reveal+0.05)},{ms(reveal+life)},\\alpha&HFF&\\blur4)\\p1", poly_d(blade_pts(S, E, w, bulge)) + "{\\p0}"))
    if ghost:
        dx, dy = E[0] - S[0], E[1] - S[1]
        L = math.hypot(dx, dy) or 1
        o = (dy / L * 9, -dx / L * 9)
        G = [(S[0] + o[0], S[1] + o[1]), (E[0] + o[0], E[1] + o[1])]
        fx.append(ev(6, t0 + 0.03, t + life * 0.8, 'FX', name, f"\\an7\\pos(0,0)\\bord0\\shad0\\1c{bgr(mix(col, WHITE, .3))}\\blur2\\alpha&HA0&{c0}{c1}"
                     f"\\t({ms(reveal)},{ms(life*0.8)},\\alpha&HFF&)\\p1", poly_d(blade_pts(G[0], G[1], th * .7, bulge)) + "{\\p0}"))


def sparks(fx, name, rnd, t, at, d, col, n=8, spread=28, speed=(60, 120), life=0.42):
    ang0 = math.atan2(d[1], d[0])
    for k in range(n):
        a = ang0 + math.radians(rnd.uniform(-spread, spread))
        v = rnd.uniform(*speed)
        b = (at[0] + math.cos(a) * v, at[1] + math.sin(a) * v + 26)
        L = rnd.uniform(9, 18)
        dr = (math.cos(a) * L, math.sin(a) * L)
        shape = poly_d([(0, 0), (dr[0] + dr[1] * .08, dr[1] - dr[0] * .08), (dr[0] * 1.06, dr[1] * 1.06), (dr[0] - dr[1] * .08, dr[1] + dr[0] * .08)])
        fx.append(ev(8, t, t + life, 'FX', name, f"\\an7\\move({at[0]:.1f},{at[1]:.1f},{b[0]:.1f},{b[1]:.1f})\\bord0\\shad0"
                     f"\\1c{bgr(mix(col, WHITE, .6))}\\blur0.6\\t({ms(life*.45)},{ms(life)},\\alpha&HFF&)\\p1", shape + "{\\p0}"))


def flash(fx, name, t, at, d, col, size=60, life=0.16):
    """impact: a short bright streak across the hit point, along the blow."""
    a = math.atan2(d[1], d[0])
    ca, sa = math.cos(a), math.sin(a)
    pts = [(-size * ca, -size * sa), (-5 * sa, 5 * ca), (size * ca, size * sa), (5 * sa, -5 * ca)]
    for lay, tags in ((8, "\\1c&HFFFFFF&\\blur1"), (7, f"\\1c{bgr(col)}\\blur6\\alpha&H40&")):
        fx.append(ev(lay, t, t + life, 'FX', name, f"\\an7\\pos({at[0]:.1f},{at[1]:.1f})\\bord0\\shad0{tags}"
                     f"\\fscx40\\fscy40\\t(0,{ms(life*.4)},\\fscx120\\fscy120)\\t({ms(life*.4)},{ms(life)},\\alpha&HFF&)\\p1",
                     poly_d(pts) + "{\\p0}"))


def dust(fx, name, rnd, t, x, y, n=4, spread=30, col=(220, 214, 205)):
    for k in range(n):
        s = -1 if k % 2 else 1
        a = (x + rnd.uniform(-8, 8), y)
        b = (a[0] + s * rnd.uniform(spread * .5, spread), y + rnd.uniform(-10, 2))
        fx.append(shape_mv(5, t, t + 0.5, a, b, oval(8, 5), f"\\1c{bgr(col)}\\blur2\\alpha&H70&\\t(0,500,\\alpha&HFF&\\fscx200\\fscy160)", (0, 500)))


# ---------------------------------------------------------------- 斩 / 大斩: a heavy blade, not a knife on a board

