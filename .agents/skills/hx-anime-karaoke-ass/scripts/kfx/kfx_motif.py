# -*- coding: utf-8 -*-
"""kfx motif (物象): small things from the show that live next to a line, and move on the beat.

Why: a karaoke line whose only effect is the letters bouncing reads as "trim" with no subject. One or two things
from the show (the tea-party cup, the sky whale, Nia's rose) give a line its picture; keeping them small and
locked to the beat grid makes the whole song feel 卡点: every bob, puff and petal lands on a beat, the bar's first
beat a little harder, so after two bars the eye predicts the next one, and that regularity is what feels good.

Rules every motif here follows (and any new one must):
  * time comes from the beat grid (beats.json from kfx_sync.py beats), never from free seconds. impact ON the beat,
    wind-up before it, settle after it. downbeat (小节头) = bigger than the other beats.
  * stays inside the lyric box + 5% (kfx_check K2); sits beside the line or in the band above the ruby, never on a glyph.
  * small: an object is at most ~70 px; particles 10-20 px. one or two motifs per line, and most lines have none.
  * something does it: the cup steams, the whale breathes and spouts, the petals fall from somewhere.

design.md, per line:   - 物象: 伴 茶杯 汽 | 洒 瓣
  伴 <art> [<particle>]   sits beside the line (left, or right if no room); bobs every beat, hops onto every downbeat,
                          puffs one <particle> per beat (two on the downbeat), alternating left/right.
  游 <art> [<particle>]   glides across the band above the line from right to left over the line, breathes on every
                          beat; on each downbeat it spouts <particle>s.
  伴 ... 右|左|定          side to sit on; 定 = no hop (a light or a meter: only pulses on the beat), centred on the line.
  拍 场记板               a clapperboard snaps shut on the line's first downbeat (M_clap).
  框 魔晶板 [L<n>]        the climax framed on the show's screen: opens one step per count, follows the sung line's width
                          landing every change on a downbeat, closes on the downbeat after L<n> (see M_frame).
  洒 <particle>           on beats 1 and 3 of every bar a <particle> drops from the band above the line, at x positions
                          that walk across the line in order (so the pattern is learnable), fluttering as it falls.
Patch verb (in 补丁):   迸[·三色]  each counted glyph of the span bursts a fan of 星 exactly on its beat.
"""
import math, re
from kfx_core import ev, bgr, mix, WHITE
import kfx_art as A

BOX = (266, 723, 1641, 1059)       # lyric box + 5% at 1080p (kfx_check K2); motifs must stay inside


# Agent Notes: 物象 / 卡点拍网格 / 字慢自查, 规则见 note
# .agents/notes/implemented/architecture/2026-11-23-kfx-motifs-beats-sync.md
def beat_list(P):
    b = P.get('beats')
    if b:
        return b
    b0, bt = P.get('beat0', 0.0), P.get('beat', 0) or 0.5
    return [b0 + k * bt for k in range(int(400 / bt))]


def is_down(P, k):
    return (k - P.get('bar0', 0)) % 4 == 0


def beats_in(P, t0, t1):
    B = beat_list(P)
    return [(k, t) for k, t in enumerate(B) if t0 <= t < t1]


def beat_index(P, t):
    B = beat_list(P)
    return min(range(len(B)), key=lambda k: abs(B[k] - t))


def snap(P, t, tol=0.08):
    """the beat nearest t if it is within tol, else t: impacts of sung glyphs land on the beat when they are near one."""
    B = beat_list(P)
    k = beat_index(P, t)
    return B[k] if abs(B[k] - t) <= tol else t


def ms(x):
    return int(round(x * 1000))


def put(fx, name, art, k, t0, t1, head, tail='', layer=0):
    """one event per colour layer of art; head = position/alignment tags, tail = animation tags."""
    for rgb, d in art.paths(k):
        fx.append(ev(layer, t0, t1, 'FX', name, f"{head}\\bord0\\shad0\\1c{bgr(rgb)}{tail}\\p3", d + "{\\p0}"))


class MCtx:
    def __init__(self, line, args, P, rnd, name, proj):
        self.line, self.args, self.P, self.rnd, self.name, self.proj = line, args, P, rnd, name, proj

    def art(self, n, tint=None):
        return A.get(n, self.proj, tint)


def _jp_bottom(c):
    return c.P['y'] + c.P['jp_fs'] * 0.45


def _side_x(c, w, want='左'):
    L = c.line
    xl = L.x0 - 22 - w / 2
    xr = L.x1 + 22 + w / 2
    okl, okr = xl - w / 2 >= BOX[0] + 4, xr + w / 2 <= BOX[2] - 4
    if want == '右' and okr or not okl and okr:
        return xr, 1
    if okl:
        return xl, -1
    return min(xr, BOX[2] - 4 - w / 2), 1


def M_sit(c):
    """伴: the prop sits beside the line on the beat."""
    L, P = c.line, c.P
    opts = [a for a in c.args if a in ('左', '右', '定')]
    names = [a for a in c.args if a not in opts]
    art = c.art(names[0])
    part = c.art(names[1]) if len(names) > 1 else None
    hop = '定' not in opts
    k = 1.0
    w, h = art.w * k, art.h * k
    cx, side = _side_x(c, w, '右' if '右' in opts else '左')
    yb = _jp_bottom(c) if h < 50 else min(BOX[3] - 4, c.P['y'] + h / 2)
    if not hop:
        yb = c.P['y'] + h / 2                      # a light / a meter sits centred on the line
    B = beat_list(P)
    # arrive on the last downbeat before the line is sung (or the beat before, if that one is too early)
    ks = [i for i, t in enumerate(B) if L.t_in - 0.2 <= t <= L.s]
    kin = ([i for i in ks if is_down(P, i)] or ks or [beat_index(P, L.s)])[0]
    kout = next((i for i, t in enumerate(B) if t >= L.t_out), len(B) - 1)
    t_in, t_out = B[kin], B[kout]
    head = f"\\an2\\pos({cx:.1f},{yb:.1f})"
    # drop in: from 24 px above, landing exactly on the beat with a squash
    for rgb, d in art.paths(k):
        c_ = bgr(rgb)
        L.fx.append(ev(0, t_in - 0.22, t_in, 'FX', c.name, f"\\an2\\move({cx:.1f},{yb - 24:.1f},{cx:.1f},{yb:.1f})\\bord0\\shad0\\1c{c_}\\fad(150,0)\\p3", d + "{\\p0}"))
    for i in range(kin, kout):
        t, t2 = B[i], B[i + 1]
        down = is_down(P, i)
        nxt_down = is_down(P, i + 1)
        sq = "\\fscx112\\fscy86" if down else "\\fscx105\\fscy95"
        tail = f"\\t(0,60,{sq})\\t(60,{ms(min(0.26, t2 - t))},\\fscx100\\fscy100)"
        if hop and nxt_down and i + 1 < kout:  # wind up: rise in the half beat before the downbeat, land on it
            mid = (t + t2) / 2
            put(L.fx, c.name, art, k, t, mid, head, tail)
            for rgb, d in art.paths(k):
                L.fx.append(ev(0, mid, t2, 'FX', c.name, f"\\an2\\move({cx:.1f},{yb:.1f},{cx:.1f},{yb - 10:.1f})\\bord0\\shad0\\1c{bgr(rgb)}\\p3", d + "{\\p0}"))
        else:
            put(L.fx, c.name, art, k, t, t2, head, tail)
        if part is not None:
            n = 2 if down else 1
            for j in range(n):
                s = (1 if (i + j) % 2 else -1)
                x0 = cx + s * (4 + 5 * j)
                y0 = yb - h * 0.85
                life = 0.9 if down else 0.7
                rise = 44 if down else 30
                x1 = x0 + s * 10
                L.fx.append(_particle(part, t + 0.02 * j, life, (x0, y0), (x1, y0 - rise), c.name,
                                      grow=(55, 110 if down else 90), a0=0x30 if down else 0x60))
    # leave: hop up and fade on the first beat after the line goes
    for rgb, d in art.paths(k):
        L.fx.append(ev(0, t_out, t_out + 0.3, 'FX', c.name, f"\\an2\\move({cx:.1f},{yb:.1f},{cx:.1f},{yb - 16:.1f})\\bord0\\shad0\\1c{bgr(rgb)}\\fad(0,240)\\p3", d + "{\\p0}"))


def _particle(art, t, life, a, b, name, grow=(60, 100), a0=0x30, flutter=0, layer=1):
    """one single-layer particle (its first layer only) moving a->b, growing, fading out."""
    rgb, d = art.paths(1.0)[0]
    fl = ''
    if flutter:
        step = ms(life / max(1, flutter))
        fl = ''.join(f"\\t({j * step},{(j + 1) * step},\\fscx{(30 if j % 2 == 0 else grow[1])})" for j in range(flutter))
    return ev(layer, t, t + life, 'FX', name,
              f"\\an5\\move({a[0]:.1f},{a[1]:.1f},{b[0]:.1f},{b[1]:.1f})\\bord0\\shad0\\1c{bgr(rgb)}\\alpha&H{a0:02X}&"
              f"\\fscx{grow[0]}\\fscy{grow[0]}\\t(0,{ms(life * 0.4)},\\fscx{grow[1]}\\fscy{grow[1]}){fl}"
              f"\\t({ms(life * 0.45)},{ms(life)},\\alpha&HFF&)\\p3", d + "{\\p0}")


def M_glide(c):
    """游: the art crosses the band above the line, breathing on each beat, spouting on each downbeat."""
    L, P = c.line, c.P
    art = c.art(c.args[0])
    part = c.art(c.args[1]) if len(c.args) > 1 else None
    k = min(1.0, 62 / art.h)
    w, h = art.w * k, art.h * k
    yb = c.P['y'] + c.P['rb_dy'] - c.P['rb_fs'] * 0.6        # bottom of the band = just above the ruby
    yb = min(yb, BOX[1] + h + 2 + 40)
    B = beat_list(P)
    bl = [i for i, t in enumerate(B) if L.t_in <= t <= L.t_out]
    if len(bl) < 2:
        return
    cl = A.cloud(w * 0.8, 14)                                # hides the edge where the frame cut the picture
    # swims head first: the traced picture faces right, so it crosses left -> right
    x_a = max(L.x0 - 40, BOX[0] + 4 + w / 2)
    x_b = min(L.x1 + 40, BOX[2] - 4 - w / 2)
    n = len(bl) - 1

    def X(j):
        return x_a + (x_b - x_a) * j / n
    for j in range(n):
        i = bl[j]
        t, t2 = B[i], B[i + 1]
        down = is_down(P, i)
        br = "\\fscx104\\fscy93" if down else "\\fscx101\\fscy97"
        fade = "\\fad(200,0)" if j == 0 else ("\\fad(0,200)" if j == n - 1 else '')
        tail = f"\\t(0,70,{br})\\t(70,{ms(min(0.3, t2 - t))},\\fscx100\\fscy100){fade}"
        for rgb, d in art.paths(k):
            L.fx.append(ev(0, t, t2, 'FX', c.name, f"\\an2\\move({X(j):.1f},{yb:.1f},{X(j + 1):.1f},{yb:.1f})\\bord0\\shad0\\1c{bgr(rgb)}{tail}\\p3", d + "{\\p0}"))
        for rgb, d in cl.paths(1.0):
            L.fx.append(ev(1, t, t2, 'FX', c.name, f"\\an2\\move({X(j):.1f},{yb + 8:.1f},{X(j + 1):.1f},{yb + 8:.1f})\\bord0\\shad0\\1c{bgr(rgb)}\\alpha&H20&{fade}\\p3", d + "{\\p0}"))
        if part is not None and down:
            hx = X(j) + w * 0.38                     # head end (it swims leftward, the picture faces right: spout behind the head)
            for m in range(3):
                ang = math.radians(-90 + (m - 1) * 28)
                L.fx.append(_particle(part, t, 0.6, (hx, yb - h * 0.9), (hx + 26 * math.cos(ang), yb - h * 0.9 + 26 * math.sin(ang)), c.name, grow=(50, 100)))


def M_scatter(c):
    """洒: beats 1 and 3 of each bar drop a particle; drop points walk across the line in order."""
    L, P = c.line, c.P
    part = c.art(c.args[0])
    top = BOX[1] + 14
    bot = c.P['y'] + c.P['rb_dy'] - 4
    xs = [L.x0 + (L.x1 - L.x0) * f for f in (0.12, 0.62, 0.37, 0.87)]
    m = 0
    for i, t in beats_in(P, L.t_in, L.t_out):
        ph = (i - P.get('bar0', 0)) % 4
        if ph not in (0, 2):
            continue
        x = xs[m % 4]
        s = 1 if m % 2 else -1
        life = 1.6
        L.fx.append(_particle(part, t, life, (x, top), (x + s * 18, bot), c.name, grow=(80 if ph == 0 else 65, 100 if ph == 0 else 85),
                              a0=0x10, flutter=4))
        m += 1


def V_burst(c):
    """迸 (verb): each counted glyph bursts a small fan of stars exactly on its beat (snapped when close)."""
    from kfx_hit import add
    pal = [(236, 238, 248), (246, 200, 70), (226, 64, 80)] if '三色' in c.args else [mix(c.line.color, WHITE, .5)]
    st = A.get('星')
    gl = [g for g in c.span if g.kind != 'space' and g.ch not in '・･!！?？、。']
    for n, g in enumerate(gl):
        t = snap(c.P, g.a)
        col = pal[n % len(pal)]
        art = A.get('星', None, col)
        for m in range(5):
            ang = math.radians(-90 + (m - 2) * 32)
            r = c.rnd.uniform(34, 50)
            a = (g.x, g.y - g.size * 0.35)
            b = (a[0] + r * math.cos(ang), max(BOX[1] + 8, a[1] + r * math.sin(ang)))
            c.line.fx.append(_particle(art, t, 0.42, a, b, c.name, grow=(40, 95), a0=0x00, layer=6))


def screen_outline(x0, y0, x1, y1, r=16, step=12):
    """points around a rounded rectangle, clockwise from the top-left corner's end, about `step` px apart."""
    pts = []
    segs = [((x0 + r, y0), (x1 - r, y0)), ((x1, y0 + r), (x1, y1 - r)), ((x1 - r, y1), (x0 + r, y1)), ((x0, y1 - r), (x0, y0 + r))]
    corners = [(x1 - r, y0 + r, -90), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180)]
    for (a, b), (cx, cy, a0) in zip(segs, corners):
        n = max(1, int(math.hypot(b[0] - a[0], b[1] - a[1]) / step))
        pts += [(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n) for i in range(n)]
        m = max(2, int(r * math.pi / 2 / step))
        pts += [(cx + r * math.cos(math.radians(a0 + 90 * i / m)), cy + r * math.sin(math.radians(a0 + 90 * i / m))) for i in range(m)]
    return pts


def _rrect(x0, y0, x1, y1, r, n=8):
    p = []
    for cx, cy, a0 in ((x1 - r, y0 + r, -90), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180)):
        p += [(cx + r * math.cos(math.radians(a0 + 90 * i / n)), cy + r * math.sin(math.radians(a0 + 90 * i / n))) for i in range(n + 1)]
    return p


def _poly(p, rev=False):
    p = p[::-1] if rev else p
    return 'm ' + ' '.join((f'{x:.1f} {y:.1f}' if i != 1 else f'l {x:.1f} {y:.1f}') for i, (x, y) in enumerate(p))


def _circle(cx, cy, r, n=28):
    return [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)) for i in range(n)]


def _hexa(cx, cy, r, rot=0):
    return [(cx + r * math.cos(math.radians(60 * i + rot)), cy + r * math.sin(math.radians(60 * i + rot))) for i in range(6)]


def _bar(p, q, w):
    dx, dy = q[0] - p[0], q[1] - p[1]
    L = math.hypot(dx, dy) or 1
    nx, ny = -dy / L * w / 2, dx / L * w / 2
    return [(p[0] + nx, p[1] + ny), (q[0] + nx, q[1] + ny), (q[0] - nx, q[1] - ny), (p[0] - nx, p[1] - ny)]


def _spiral(cx, cy, r, turns=1.4, w=2.2, n=40):
    out, inn = [], []
    for i in range(n + 1):
        u = i / n
        a = math.pi * 2 * turns * u
        rr = r * (1 - 0.8 * u)
        ww = w * (1 - 0.5 * u)
        out.append((cx + (rr + ww / 2) * math.cos(a), cy + (rr + ww / 2) * math.sin(a)))
        inn.append((cx + (rr - ww / 2) * math.cos(a), cy + (rr - ww / 2) * math.sin(a)))
    return out + inn[::-1]


RIM, GOLD, HI, BROWN, PALE = (128, 80, 20), (232, 184, 64), (255, 236, 150), (112, 66, 24), (250, 214, 110)


def _corner():
    """top-left corner of the ED's gold magic-vision frame (ED 1:48): a medallion with a hexagon lattice and a ring of
    dots, a scroll curl under it, a leaf flourish on the top bar. local coords, 0..64; (rgb, [polygons]) from back to front."""
    return [
        (RIM, [_circle(22, 22, 19.5, 36), _spiral(13, 49, 8, 1.3, 4.4)]),
        (GOLD, [_circle(22, 22, 17.5, 36), _spiral(13, 49, 8, 1.3, 2.6)]),
        (PALE, [_circle(20.5, 20, 13, 28)]),
        (RIM, [_circle(22, 22, 15.2, 30)[:0] or _hexa(22, 22, 11.5, 30)]),
        (GOLD, [_hexa(22, 22, 9.2, 30)]),
        (BROWN, [_hexa(22, 22, 6.6, 30)]),
        (GOLD, [_bar((22 + 3.4 * math.cos(math.radians(60 * i + 30)), 22 + 3.4 * math.sin(math.radians(60 * i + 30))),
                     (22 + 8.4 * math.cos(math.radians(60 * i + 30)), 22 + 8.4 * math.sin(math.radians(60 * i + 30))), 1.6) for i in range(6)]
         + [_hexa(22, 22, 3.6, 30)]),
        (BROWN, [_hexa(22, 22, 2.0, 30)]),
        (HI, [_circle(22 + 14.6 * math.cos(2 * math.pi * k / 12), 22 + 14.6 * math.sin(2 * math.pi * k / 12), 1.15, 8) for k in range(12)]
         + [[(40, 6), (47, 2.5), (55, 4), (49, 6.2), (44, 9)], [(41, 8), (47, 11), (53, 9.6), (47, 12.6)]]),
    ]


def _xf(poly, x0, y0, sx, sy):
    return [(x0 + sx * x, y0 + sy * y) for x, y in poly]


def screen_layers(x0, y0, x1, y1):
    """the 魔晶板 (magic-vision screen) of the ED, drawn: thin bevelled gold edges (dark rim, gold, a highlight line)
    and the four ornate corners mirrored from one. absolute coordinates, \\p1, back to front."""
    e = 5.0
    def band(off, w):
        return _poly(_rrect(x0 + off, y0 + off, x1 - off, y1 - off, 10)) + ' ' + _poly(_rrect(x0 + off + w, y0 + off + w, x1 - off - w, y1 - off - w, 9), rev=True)
    layers = [(RIM, band(-1, e + 2)), (GOLD, band(0, e)), (HI, band(1.2, 1.2))]
    corners = [(x0 - 6, y0 - 6, 1, 1), (x1 + 6, y0 - 6, -1, 1), (x0 - 6, y1 + 6, 1, -1), (x1 + 6, y1 + 6, -1, -1)]
    for rgb, polys in _corner():
        d = []
        for cx, cy, sx, sy in corners:
            for p in polys:
                q = _xf(p, cx, cy, sx * 0.82, sy * 0.82)
                rev = (sx * sy) < 0                      # mirrored once -> keep the winding the same
                d.append(_poly(q, rev=rev))
        layers.append((rgb, ' '.join(d)))
    gem = (120, 220, 90)
    cx = (x0 + x1) / 2
    layers.append((RIM, _poly([(cx - 15, y1), (cx - 9, y1 - 7), (cx + 9, y1 - 7), (cx + 15, y1), (cx + 9, y1 + 7), (cx - 9, y1 + 7)])))
    layers.append((gem, _poly([(cx - 12, y1), (cx - 7.5, y1 - 5), (cx + 7.5, y1 - 5), (cx + 12, y1), (cx + 7.5, y1 + 5), (cx - 7.5, y1 + 5)])))
    layers.append(((220, 255, 200), _poly([(cx - 6, y1 - 3.4), (cx + 2, y1 - 3.4), (cx - 1, y1 - 1), (cx - 8, y1 - 1)])))
    return layers


def _rect(xa, ya, xb, yb):
    return [(xa, ya), (xb, ya), (xb, yb), (xa, yb)]


BAR = 5.0      # gold bar thickness


def _hbar(XA, XB, inward):
    """horizontal bar at local y=0 reaching `inward` (+1 down / -1 up), spanning XA..XB; (rgb, drawing) back to front"""
    e, s = BAR, inward
    def r(a, b, xa=XA, xb=XB):
        return _poly(_rect(xa, min(s * a, s * b), xb, max(s * a, s * b)))
    return [(RIM, r(-1, e + 1)), (GOLD, r(0, e)), (HI, r(1.2, 2.4))]


def _vbar(YA, YB, inward):
    e, s = BAR, inward
    def r(a, b):
        return _poly(_rect(min(s * a, s * b), YA, max(s * a, s * b), YB))
    return [(RIM, r(-1, e + 1)), (GOLD, r(0, e)), (HI, r(1.2, 2.4))]


def _corner_at(sx, sy):
    """one ornate corner with its frame corner at local (0,0); sx/sy = +1 for the top-left orientation"""
    return [(rgb, ' '.join(_poly(_xf(p, -6 * sx, -6 * sy, sx * 0.82, sy * 0.82), rev=(sx * sy) < 0) for p in polys))
            for rgb, polys in _corner()]


def _gem():
    y = -2.5
    return [(RIM, _poly([(-12, y), (-7, y - 5.5), (7, y - 5.5), (12, y), (7, y + 5.5), (-7, y + 5.5)])),
            ((120, 220, 90), _poly([(-9.5, y), (-5.8, y - 4), (5.8, y - 4), (9.5, y), (5.8, y + 4), (-5.8, y + 4)])),
            ((220, 255, 200), _poly([(-4.8, y - 2.6), (1.6, y - 2.6), (-0.8, y - 0.8), (-6.4, y - 0.8)]))]


PH, RATIO, CN_GAP = 46.0, 0.7, 6.0


def frame_rect(l, P, ph=PH, ratio=RATIO, cn_gap=CN_GAP):
    """the frame around one line, measured on INK (kfx_ink), the way a lower-third box is built: text ink + padding.
    Horizontal padding ph, vertical ph*ratio (type looks bottom-heavy with equal numbers; 0.6-0.75 is the usual optical
    ratio). M_frame first steps the CN lines down to make room; if the bottom would still reach the CN line, BOTH
    paddings shrink together so the text stays centred.
    Returns the outer rectangle (x0, y0, x1, y1) and the paddings."""
    from kfx_ink import line_ink
    (ix0, iy0, ix1, iy1), cn = line_ink(l, P)
    pv = ph * ratio
    if cn:
        pv = min(pv, cn[1] - cn_gap - BAR - iy1)
    ph = min(ph, pv / ratio) if pv < ph * ratio else ph
    return (ix0 - ph - BAR, iy0 - pv - BAR, ix1 + ph + BAR, iy1 + pv + BAR), (ix0, iy0, ix1, iy1), ph, pv


def M_frame(c):
    """框 魔晶板 [L<n>]: the climax is shown on the show's magic-vision screen (ED 1:48 gold frame), built the way
    lower-third boxes are (box = text ink + padding; see frame_rect):
      - the frame is the screen ONE LINE is shown on: the line's ink at rest + even padding on every side (vertical =
        0.7 x horizontal, the optical ratio), so the gaps look the same all round; it keeps still while the line is sung;
      - opens over the beat before the first word as a cascade: corners pop in (small overshoot), the bars draw out
        from the middle to meet them, the gem lights last; on the beat each next line starts it
        eases (last ~0.3 s) to that line's box, in width AND height (ruby lines are taller); stays until L<n> is sung;
      - each beat the gold brightens and settles; on each downbeat a light runs along the bars (top left->right, bottom
        back) and the corners nod; nothing flickers, nothing spins;
      - closes (faster than it came, ease-in) on the first beat after the last word, before the next line appears: the
        bars run back to the middle, the corners fold away;
      - reviews itself: raises if the paddings are uneven, the frame moves while a line is sung, or it touches the CN line.
    Built from parts so size changes are smooth: four corners that \\move, four bars \\move-d and revealed by \\clip."""
    L, P = c.line, c.P
    B = beat_list(P)
    lines = {l.idx: l for l in getattr(c, 'lines', [L])}
    upto = next((int(a[1:]) for a in c.args if re.match(r'^L\d+$', a)), L.idx)
    on_air = [lines[j] for j in range(L.idx, upto + 1) if j in lines]
    near = lambda t: min(B, key=lambda b: abs(b - t))
    first_a = lambda l: min(g.a for g in l.glyphs if g.kind != 'space')
    # make room: the frame needs its full padding under the words, so the CN lines of the lines on air step down
    # (all by the same amount, so the CN never jumps between them). Motifs run before a line's CN is emitted.
    from kfx_ink import line_ink
    need = 0.0
    for l in on_air:
        ink_, cn = line_ink(l, P)
        if cn:
            need = max(need, (ink_[3] + PH * RATIO + BAR + CN_GAP) - cn[1])
    if need > 0:
        for l in on_air:
            l.cn_y += need
    starts = []
    for n, l in enumerate(on_air):
        t = max([b for b in B if b <= first_a(l) + 0.03] or [near(first_a(l))]) if n == 0 else near(first_a(l))
        R, ink, ph, pv = frame_rect(l, P)
        # self review: even paddings, clear of CN
        assert abs((ink[0] - R[0]) - (R[2] - ink[2])) < 0.5 and abs((ink[1] - R[1]) - (R[3] - ink[3])) < 0.5, f'框 L{l.idx}: 留白不均'
        assert abs(pv - PH * RATIO) < 0.5, f'框 L{l.idx}: 竖向留白被压缩 (中文太近)'
        if starts and t <= starts[-1][0] + 0.05:
            starts[-1] = (starts[-1][0], R)
        else:
            starts.append((t, R))
    T_on = starts[0][0]
    bl = (B[-1] - B[0]) / max(1, len(B) - 1)
    R0 = starts[0][1]
    cx0, cy0 = (R0[0] + R0[2]) / 2, (R0[1] + R0[3]) / 2
    prev = lines.get(on_air[0].idx - 1)        # the screen turns on once the line before has left, not over it
    t_prev = max((getattr(g, 't_out', 0) for g in prev.glyphs), default=0) if prev else 0
    T_in = min(max(T_on - bl, t_prev), T_on - 0.25)
    keys = [(T_in, (cx0 - 24, R0[1], cx0 + 24, R0[3]), False)]
    t_last = max(g.b for g in on_air[-1].glyphs)
    nxt = lines.get(on_air[-1].idx + 1)
    t_next = min(g.t_in for g in nxt.glyphs) if nxt else t_last + 2
    Tc = next((t for t in B if t > t_last + 0.05), t_last + 0.4)
    if Tc > t_next:
        Tc = max([t for t in B if t_last < t <= t_next] or [max(t_last + 0.1, t_next)])
    cur = R0
    for t in [t for t in B if T_on - 0.05 <= t < Tc - 0.05]:
        for ts_, R in starts:
            if abs(ts_ - t) < 0.05:
                cur = R
        keys.append((t, cur, True))
    keys.append((Tc, cur, True))
    for k, (ts_, R) in enumerate(starts):
        te = starts[k + 1][0] if k + 1 < len(starts) else Tc
        assert all(kk[1] == R for kk in keys if ts_ <= kk[0] <= te - 0.05), f'框: 唱一句时框在变'
    XA = min(k[1][0] for k in keys) - 30
    XB = max(k[1][2] for k in keys) + 30
    YA = min(k[1][1] for k in keys) - 30
    YB = max(k[1][3] for k in keys) + 30
    parts = {'t': _hbar(XA, XB, 1), 'b': _hbar(XA, XB, -1), 'l': _vbar(YA, YB, 1), 'r': _vbar(YA, YB, -1),
             'tl': _corner_at(1, 1), 'tr': _corner_at(-1, 1), 'bl': _corner_at(1, -1), 'br': _corner_at(-1, -1), 'g': _gem()}
    lay = {'t': 3, 'b': 3, 'l': 3, 'r': 3, 'tl': 4, 'tr': 4, 'bl': 4, 'br': 4, 'g': 5}

    def place(p, R):
        """(move x, move y, clip rect) of part p for frame R"""
        x0, y0, x1, y1 = R
        return {'t': (0, y0, (x0, 0, x1, 1080)), 'b': (0, y1, (x0, 0, x1, 1080)),
                'l': (x0, 0, (0, y0, 1920, y1)), 'r': (x1, 0, (0, y0, 1920, y1)),
                'tl': (x0, y0, None), 'tr': (x1, y0, None), 'bl': (x0, y1, None), 'br': (x1, y1, None),
                'g': ((x0 + x1) / 2, y1, None)}[p]

    def lerp(Ra, Rb, u):
        return tuple(a + (b - a) * u for a, b in zip(Ra, Rb))

    CORNERS = ('tl', 'tr', 'bl', 'br')
    BARS = ('t', 'b', 'l', 'r')

    def put(p, t0, t1, Ra, Rb, extra='', alpha='\\alpha&H00&', clip=None):
        """one piece of part p. clip=(rect_a, rect_b, accel) overrides the bar reveal (wipes)."""
        d = ms(t1 - t0)
        (xa, ya, ca), (xb, yb, cb) = place(p, Ra), place(p, Rb)
        tg = f"\\an7\\move({xa:.1f},{ya:.1f},{xb:.1f},{yb:.1f},0,{d})" if (xa, ya) != (xb, yb) else f"\\an7\\pos({xa:.1f},{ya:.1f})"
        acc = 1
        if clip:
            ca, cb, acc = clip
        if ca:
            tg += f"\\clip({ca[0]:.0f},{ca[1]:.0f},{ca[2]:.0f},{ca[3]:.0f})"
            if ca != cb:
                tg += f"\\t(0,{d},{acc},\\clip({cb[0]:.0f},{cb[1]:.0f},{cb[2]:.0f},{cb[3]:.0f}))"
        for rgb, dr in parts[p]:
            L.fx.append(ev(lay[p], t0, t1, 'FX', c.name, f"{tg}\\bord0\\shad0\\1c{bgr(rgb)}{alpha}{extra}\\p1", dr + "{\\p0}"))

    def shrink(p, R, u):
        """bar reveal rect at fraction u (0 = a point at the bar's middle, 1 = the full bar)"""
        x0, y0, x1, y1 = R
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        hw, hh = (x1 - x0) / 2 * u, (y1 - y0) / 2 * u
        return (cx - hw, 0, cx + hw, 1080) if p in ('t', 'b') else (0, cy - hh, 1920, cy + hh)

    def hold(t0, t1, R, downbeat, beat):
        for p in parts:
            ex = ''
            if p in CORNERS and downbeat:          # the corners give a small nod on the downbeat
                ex = "\\fscx114\\fscy114\\t(0,240,0.6,\\fscx100\\fscy100)"
            if p == 'g' and (downbeat or beat):
                ex = f"\\blur{2.5 if downbeat else 1.2}\\t(0,260,\\blur0)"
            put(p, t0, t1, R, R, ex)
        if beat:                                   # gold brightens and settles
            k = .55 if downbeat else .22
            for p in ('t', 'b', 'l', 'r'):
                (_, _, ca) = place(p, R)
                for rgb, dr in parts[p][1:]:
                    xx, yy, _ = place(p, R)
                    L.fx.append(ev(lay[p] + 1, t0, min(t1, t0 + 0.3), 'FX', c.name,
                                   f"\\an7\\pos({xx:.1f},{yy:.1f})\\clip({ca[0]:.0f},{ca[1]:.0f},{ca[2]:.0f},{ca[3]:.0f})\\bord0\\shad0"
                                   f"\\1c{bgr(WHITE)}\\alpha&H{int(255 * (1 - k)):02X}&\\t(0,300,0.7,\\alpha&HFF&)\\p1", dr + "{\\p0}"))
        if downbeat:                               # a light runs along the top bar (left to right) and back along the bottom
            x0, y0, x1, y1 = R
            dur = min(t1 - t0, 0.5)
            sh = _poly([(0, 0), (34, 0), (26, BAR), (-8, BAR)])
            for yy, xa, xb, s_ in ((y0, x0 + 14, x1 - 48, 1), (y1 - BAR, x1 - 48, x0 + 14, -1)):
                L.fx.append(ev(6, t0, t0 + dur, 'FX', c.name,
                               f"\\an7\\move({xa:.1f},{yy:.1f},{xb:.1f},{yy:.1f})\\blur1.6\\bord0\\shad0\\1c{bgr(WHITE)}"
                               f"\\alpha&H30&\\t({ms(dur * 0.6)},{ms(dur)},\\alpha&HFF&)\\p1", sh + "{\\p0}"))

    def slide(t0, t1, Ra, Rb):
        STEPS = 4
        for k in range(STEPS):                     # ease-out: fast, then settles onto the beat
            u0, u1 = k / STEPS, (k + 1) / STEPS
            e0, e1 = 1 - (1 - u0) ** 2, 1 - (1 - u1) ** 2
            ra, rb = lerp(Ra, Rb, e0), lerp(Ra, Rb, e1)
            for p in parts:
                put(p, t0 + (t1 - t0) * u0, t0 + (t1 - t0) * u1, ra, rb)

    def intro(t0, t1, R):
        """cascade (stagger, don't slam): corners pop in with a small overshoot, then the bars draw out from the middle
        to meet them (ease-out), then the gem."""
        d = t1 - t0
        tc = min(0.3, d * 0.45)
        tb0, tb1 = t0 + d * 0.25, t1
        for p in CORNERS:
            put(p, t0, t0 + tc, R, R, f"\\fscx20\\fscy20\\t(0,{ms(tc * 0.65)},0.6,\\fscx118\\fscy118)\\t({ms(tc * 0.65)},{ms(tc)},\\fscx100\\fscy100)",
                f"\\alpha&HFF&\\t(0,{ms(tc * 0.5)},\\alpha&H00&)")
            put(p, t0 + tc, t1, R, R)
        for p in BARS:
            put(p, tb0, tb1, R, R, clip=(shrink(p, R, 0.0), shrink(p, R, 1.0), 0.5))
        tg = t1 - min(0.18, d * 0.3)
        put('g', tg, t1, R, R, f"\\fscx30\\fscy30\\blur3\\t(0,{ms(t1 - tg)},0.6,\\fscx100\\fscy100\\blur0)",
            f"\\alpha&HFF&\\t(0,{ms((t1 - tg) * 0.6)},\\alpha&H00&)")

    def outro(t0, t1, R):
        """out faster than in, ease-in: the bars run back to the middle, then the corners fold away."""
        d = t1 - t0
        for p in BARS:
            put(p, t0, t0 + d * 0.7, R, R, clip=(shrink(p, R, 1.0), shrink(p, R, 0.0), 2.0))
        put('g', t0, t0 + d * 0.5, R, R, '', f"\\alpha&H00&\\t(0,{ms(d * 0.5)},\\alpha&HFF&)")
        for p in CORNERS:
            put(p, t0, t1, R, R, f"\\t({ms(d * 0.4)},{ms(d)},2,\\fscx40\\fscy40)",
                f"\\alpha&H00&\\t({ms(d * 0.4)},{ms(d)},\\alpha&HFF&)")

    for n, ((ta, Ra, _), (tb, Rb, _)) in enumerate(zip(keys, keys[1:])):
        d = tb - ta
        if d <= 0.01:
            continue
        down = any(abs(B[i] - ta) < 0.03 and is_down(P, i) for i in range(len(B)))
        if n == 0:
            intro(ta, tb, Rb)
            continue
        if n == len(keys) - 2:
            fo = min(0.32, d * 0.7)
            if d - fo > 0.01:
                hold(ta, tb - fo, Ra, down, True)
            outro(tb - fo, tb, Ra)
            continue
        mv = min(0.3, d * 0.6) if Ra != Rb else 0
        if d - mv > 0.01:
            hold(ta, tb - mv, Ra, down, True)
        if mv > 0:
            slide(tb - mv, tb, Ra, Rb)


def M_clap(c):
    """拍 场记板: the clapperboard of the ED's filming set (2番: PROD. NIA LISTON OP, TAKE.1). It slides in beside the
    line, the stick opens on the beat before the line's first downbeat and snaps shut ON that downbeat (the board jolts,
    a few white sparks), holds while the line is sung, and slides out. The clap is the most 卡点 object there is."""
    L, P = c.line, c.P
    B = beat_list(P)
    kd = next((i for i, t in enumerate(B) if t >= L.s - 0.12 and is_down(P, i)), beat_index(P, L.s))
    T = B[kd]
    T0 = B[max(0, kd - 1)]
    t_in, t_out = T0 - 0.3, max(T + 0.6, L.t_out)
    W, H = 70, 46
    cx, side = _side_x(c, W, '左')
    x0, y0 = cx - W / 2, c.P['y'] - H / 2 + 6
    body = [(x0, y0 + 10), (x0 + W, y0 + 10), (x0 + W, y0 + H), (x0, y0 + H)]
    lines_ = ' '.join(_poly([(x0 + 6, y0 + 18 + 9 * i), (x0 + W - 6, y0 + 18 + 9 * i), (x0 + W - 6, y0 + 19.5 + 9 * i), (x0 + 6, y0 + 19.5 + 9 * i)]) for i in range(3))
    hx, hy = x0, y0 + 10                                  # hinge
    stick = [(x0, y0), (x0 + W, y0), (x0 + W, y0 + 9), (x0, y0 + 9)]
    stripes = ' '.join(_poly([(x0 + 14 * i, y0 + 9), (x0 + 14 * i + 7, y0), (x0 + 14 * i + 14, y0), (x0 + 14 * i + 7, y0 + 9)]) for i in range(5))
    slide_in = f"\\fad(200,250)"
    # board (fixed), jolts on the clap
    jolt = f"\\t({ms(T - t_in)},{ms(T - t_in + 0.05)},\\fscx104\\fscy96)\\t({ms(T - t_in + 0.05)},{ms(T - t_in + 0.2)},\\fscx100\\fscy100)"
    for rgb, d in (((40, 52, 46), _poly(body)), ((232, 232, 226), lines_)):
        L.fx.append(ev(3, t_in, t_out, 'FX', c.name, f"\\an7\\pos(0,0)\\org({hx:.0f},{hy:.0f}){slide_in}\\bord0\\shad0\\1c{bgr(rgb)}{jolt}\\p1", d + "{\\p0}"))
    # stick: closed -> opens (-24 deg) over the beat before -> snaps shut on T
    rot = (f"\\frz0\\t({ms(T0 - t_in)},{ms(T0 - t_in + 0.2)},\\frz24)"
           f"\\t({ms(T - t_in - 0.06)},{ms(T - t_in)},\\frz0)")
    for rgb, d in (((236, 236, 236), _poly(stick)), ((206, 30, 44), stripes)):
        L.fx.append(ev(4, t_in, t_out, 'FX', c.name, f"\\an7\\pos(0,0)\\org({hx:.0f},{hy:.0f}){slide_in}\\bord0\\shad0\\1c{bgr(rgb)}{rot}\\p1", d + "{\\p0}"))
    # the snap: short white strokes off the far end of the stick
    ex, ey = x0 + W + 4, y0 + 6
    for m_ in range(3):
        a = math.radians(-40 + m_ * 30)
        p1 = (ex + 4 * math.cos(a), ey + 4 * math.sin(a))
        p2 = (ex + 16 * math.cos(a), ey + 16 * math.sin(a))
        nx, ny = -math.sin(a) * 1.2, math.cos(a) * 1.2
        L.fx.append(ev(5, T, T + 0.22, 'FX', c.name, f"\\an7\\pos(0,0)\\bord0\\shad0\\1c&HFFFFFF&\\blur0.6\\t(80,220,\\alpha&HFF&)\\p1",
                       _poly([(p1[0] + nx, p1[1] + ny), (p2[0] + nx, p2[1] + ny), (p2[0] - nx, p2[1] - ny), (p1[0] - nx, p1[1] - ny)]) + "{\\p0}"))


MOTIFS = {'伴': M_sit, '游': M_glide, '洒': M_scatter, '框': M_frame, '拍': M_clap}


def parse(field):
    out = []
    for part in field.replace('｜', '|').split('|'):
        toks = part.split()
        if toks:
            out.append((toks[0], toks[1:]))
    return out


def check(field, proj):
    errs = []
    for b, args in parse(field):
        if b not in MOTIFS:
            errs.append(f'物象 {b}: 只认 {" ".join(MOTIFS)}')
            continue
        if not args:
            errs.append(f'物象 {b}: 要写画什么')
        for a in args:
            if b == '拍':
                if a != '场记板':
                    errs.append('物象 拍: 目前只有 场记板')
                continue
            if b in ('伴',) and a in ('左', '右', '定'):
                continue
            if b == '框':
                if re.match(r'^L\d+$', a):
                    continue
                if a != '魔晶板':
                    errs.append('物象 框: 目前只有 魔晶板')
                continue
            try:
                A.get(a, proj)
            except KeyError:
                errs.append(f'物象 {b} {a}: 没有这个图 (画在 kfx_art.DRAWN, 或描进 <工程>/art/{a}.json)')
    return errs
