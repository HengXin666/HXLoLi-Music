"""kfx verbs (4/4): pop-telop verbs, first invented for ろりこんでよかった～ (猫飴's PV: the lyric IS the picture, in
fat rainbow telops set on a slant, one word blown up huge, red police warnings, cheeks puffed, モキュモキュ).
They only move and colour the glyphs themselves; nothing is drawn beside them. Any later song may use them."""
import math
from kfx_hit import add
from kfx_core import hexrgb

RAINBOW = ['#FF3D9E', '#FF7A3D', '#FFC119', '#5FC22A', '#22C3E6', '#6E8BFF', '#B46BFF']   # the PV's telop colours


def _ramp(n):
    cs = [hexrgb(c) for c in RAINBOW]
    out = []
    for k in range(n):
        u = (k / max(1, n - 1)) * (len(cs) - 1)
        i = min(int(u), len(cs) - 2)
        f = u - i
        out.append(tuple(int(round(a + (b - a) * f)) for a, b in zip(cs[i], cs[i + 1])))
    return out


def _real(gl):
    return [g for g in gl if g.kind != 'space']


def V_telop(c):
    """虹 (本曲主菜): the line becomes the PV's rainbow telop (84 s / 145 s / 181 s "ロリコンで良かったわ").
    One beat before it is sung the whole line tilts up to the right (the PV sets every telop on a slant) and stays so;
    each glyph is stamped in on its own note, big then settling a size up, in the PV's rainbow from pink to violet;
    on the last note the whole line gives one "ドン" together. The words stay in order and level along the slant,
    so they are read like a sign, not scattered."""
    L = c.line
    gl = _real(L.glyphs)
    span = _real(c.span)
    th = 6.5
    mid = (gl[0].x + gl[-1].x) / 2
    bt = c.P.get('beat', 0) or 0.4
    t0 = min(g.a for g in gl)
    cols = dict(zip(map(id, gl), _ramp(len(gl))))                # the rainbow runs over the whole line, whatever the groups
    first = not getattr(L, 'telop', False)
    if first:                                           # once per line, however many groups carry 虹
        L.telop = True
        grow = 0.16 * sum(g.w for g in gl) / 2          # room for the glyphs a size up: spread from the middle
        half = max(1, (gl[-1].x - gl[0].x) / 2)
        for g in gl:                                    # the slant (whole line, so the baseline stays straight)
            pose = dict(rz=th, dy=-(g.x - mid) * math.tan(math.radians(th)), dx=(g.x - mid) / half * grow * 0.9)
            add(g, (t0 - bt, {}), (t0 - bt * 0.35, pose), (g.t_out, pose))
    for g in span:
        g.tint = cols[id(g)]
        a = g.a
        add(g, (a - 0.03, {}), (a + 0.06, dict(sx=0.5, sy=0.5, dy=-6)), (a + 0.17, dict(sx=0.1, sy=0.1, dy=1)),
            (a + 0.26, dict(sx=0.16, sy=0.16)), (g.t_out, dict(sx=0.16, sy=0.16)))
    if span[-1] is gl[-1]:                              # the final ドン on the last note of the line
        tl = gl[-1].a
        for g in gl:
            add(g, (tl, {}), (tl + 0.07, dict(sx=0.12, sy=0.12)), (tl + 0.24, {}))


def V_bigword(c):
    """大字[·青/粉/绿/黄][·大]: one word is blown up like the PV's giant 「1番」 (67 s): on its note it swells to a big size and stays;
    the rest of the line steps aside on both sides to make room, so nothing overlaps."""
    L = c.line
    gl = _real(L.glyphs)
    span = _real(c.span)
    k = 0.7 if '大' in c.args else 0.5
    wid = sum(g.w for g in span)
    cx = sum(g.x for g in span) / len(span)
    push = wid * k / 2
    t = span[0].a
    col = hexrgb({'青': '#22C3E6', '粉': '#FF3D9E', '绿': '#5FC22A', '黄': '#FFC119'}.get(next((a for a in c.args if a != '大'), '青'), '#22C3E6'))
    for g in gl:
        if g in span:
            o = dict(sx=k, sy=k, dx=(g.x - cx) * k, dy=-6)
            g.tint = col
            add(g, (t - 0.02, {}), (t + 0.09, dict(sx=k + 0.25, sy=k + 0.25, dx=(g.x - cx) * (k + 0.25), dy=-10)),
                (t + 0.24, o), (g.t_out, o))
        else:
            o = dict(dx=-push if g.x < cx else push)
            add(g, (t - 0.02, {}), (t + 0.12, o), (g.t_out, o))


def V_warn(c):
    """警: the PV's red police warning (「職務質問されるぞ！」 72 s): the words turn signal red when sung and the whole
    line is shoved left-right twice like a whistle blast, then holds still. No flashing."""
    L = c.line
    span = _real(c.span)
    for g in span:
        g.tint = hexrgb('#FF2E4A')
    t = span[0].a
    for g in _real(L.glyphs):
        add(g, (t, {}), (t + 0.05, dict(dx=-8)), (t + 0.11, dict(dx=7)), (t + 0.17, dict(dx=-4)), (t + 0.24, dict(dx=2)),
            (t + 0.32, {}))
    for g in span:
        add(g, (g.a - 0.02, {}), (g.a + 0.05, dict(sx=0.22, sy=0.22)), (g.a + 0.18, {}))


def V_puff(c):
    """鼓: cheeks puffed (ホッペタを膨らませて): each glyph fills up round, wider and taller, holds a moment
    with its breath, then lets it out."""
    for k, g in enumerate(_real(c.span)):
        t = g.a
        add(g, (t, {}), (t + 0.18, dict(sx=0.24, sy=0.16)), (t + 0.45, dict(sx=0.26, sy=0.18)), (t + 0.56, dict(sx=-0.05, sy=-0.04)),
            (t + 0.66, {}))


def V_knead(c):
    """揉: モキュモキュ, kneading the face: each glyph is squeezed flat then tall, twice, on the beat, like a cheek
    pinched between fingers."""
    bt = c.P.get('beat', 0) or 0.375
    for k, g in enumerate(_real(c.span)):
        t = g.a
        add(g, (t, {}), (t + bt * 0.25, dict(sx=0.22, sy=-0.2)), (t + bt * 0.5, dict(sx=-0.14, sy=0.16)),
            (t + bt * 0.75, dict(sx=0.12, sy=-0.1)), (t + bt, {}))


POP_VERBS = {'虹': V_telop, '大字': V_bigword, '警': V_warn, '鼓': V_puff, '揉': V_knead}


# ---------------------------------------------------------------- big moves (v2, 2026-11-24)
# The user, on v1: "为什么不能有类似于砍刀这种级别的特效呢? ... 字在跳跃 就是特效吗?" A song needs set pieces the size of
# オンリー's 大斩, each one a thing from the PV or the lyric that happens TO the words. Rules these keep:
#  - drawn in screen coordinates at where the glyphs really are at that moment (late: computed after every verb, the
#    amplitude scale and the exit have been applied), so nothing is left standing where a glyph used to be;
#  - every piece ends inside its line (by the line's t_end at the latest, usually on the exit itself) and leaves with
#    the line, so nothing is left behind when the words have gone;
#  - no flashing, no spinning, nothing drawn through a glyph.
from kfx_core import total, ev, bgr, mix, WHITE, BLACK
from kfx_hit import poly_d, shake_line, sparks, flash, dust, slash
from kfx_draw import ms, shape_mv, oval


def _at(g, t):
    v = total(g.tracks, t)
    return g.x + v['dx'], g.y + v['dy'], 1 + v['sx'], 1 + v['sy']


def _clip(c):
    """the lyric box grown by the 5 % the user's crop allows (kfx_check K2); every set piece is clipped to it, so a big
    move is big inside the picture the user keeps, never cut off at its edge by accident."""
    b = c.P.get('box')
    return '' if not b else '\\clip(%d,%d,%d,%d)' % tuple(round(v) for v in b)


def _late(L, f):
    if not hasattr(L, 'late'):
        L.late = []
    L.late.append(f)


def _hex(cx, cy, r, rot=0.0):
    return [(cx + r * math.cos(math.radians(60 * k + rot)), cy + r * math.sin(math.radians(60 * k + rot))) for k in range(6)]


def _box(span, t):
    ps = [(_at(g, t), g) for g in span]
    x0 = min(p[0] - g.w * p[2] / 2 for p, g in ps)
    x1 = max(p[0] + g.w * p[2] / 2 for p, g in ps)
    y = sum(p[1] for p, g in ps) / len(ps)
    h = max(g.size * p[3] for p, g in ps)
    return x0, x1, y, h


def _shape(fx, layer, t0, t1, name, pts_list, tags):
    d = ' '.join(poly_d(p) for p in pts_list)
    fx.append(ev(layer, t0, t1, 'FX', name, f"\\an7\\pos(0,0)\\bord0\\shad0{tags}\\p1", d + "{\\p0}"))


def V_focus(c):
    """集中: manga focus lines (集中線) rush in toward the word when it is sung, the classic "this one!" shot of a
    telop PV: wedges from the screen edge point at the word from above and both sides (never across the lyric row,
    never through a glyph), hold while the word is held, and are gone on the next beat."""
    L, span = c.line, _real(c.span)
    t = span[0].a
    bt = c.P.get('beat', 0) or 0.375

    def late():
        x0, x1, y, h = _box(span, t + 0.2)
        cx = (x0 + x1) / 2
        r0x, r0y = (x1 - x0) / 2 + 70, h * 0.9 + 40
        wed, glo = [], []
        n = 44
        for k in range(n):
            a = math.radians(-180 + 360 * k / n + c.rnd.uniform(-2.5, 2.5))
            if math.sin(a) > -0.42:     # only from above: never across the lyric row, the rubies' sides or the subtitle
                continue
            r_in = 1.0 + (0.35 if k % 3 == 0 else 0.0) + c.rnd.uniform(0, 0.25)
            ix, iy = cx + math.cos(a) * r0x * r_in, y + math.sin(a) * r0y * r_in
            ox, oy = cx + math.cos(a) * 1500, y + math.sin(a) * 1500
            w = c.rnd.uniform(6, 15)
            nx, ny = -math.sin(a) * w, math.cos(a) * w
            wed.append([(ix, iy), (ox + nx, oy + ny), (ox - nx, oy - ny)])
            glo.append([(ix, iy), (ox + nx * 2.4, oy + ny * 2.4), (ox - nx * 2.4, oy - ny * 2.4)])
        t1 = min(span[-1].b + bt, L.t_out)
        life = t1 - t
        # manga lines are ink on paper: a white halo so they read on any picture, an ink core, and the line colour
        _shape(L.fx, 0, t - 0.02, t1, c.name, glo,
               _clip(c) + f"\\1c&HFFFFFF&\\blur4\\alpha&HFF&\\t(0,60,\\alpha&H50&)\\t({ms(life*0.6)},{ms(life)},\\alpha&HFF&)")
        _shape(L.fx, 0, t - 0.02, t1, c.name, wed,
               _clip(c) + f"\\1c&H3A1E2A&\\blur0.6\\alpha&HFF&\\t(0,60,\\alpha&H18&)\\t({ms(life*0.6)},{ms(life)},\\alpha&HFF&)")
        _shape(L.fx, 0, t - 0.02, t1, c.name, wed,
               _clip(c) + f"\\1c{bgr(c.col)}\\blur7\\alpha&HFF&\\t(0,60,\\alpha&H80&)\\t({ms(life*0.6)},{ms(life)},\\alpha&HFF&)")
        shake_line(L, t, cx, (0, 1), amp=9, fall=500)
    _late(L, late)


def V_hexcut(c):
    """六角: the PV's hexagon cut-in (48 s 口紅, 54 s ヒール, 57 s 大人): a hexagon slams open behind the word in the
    line colour with a white rim, a second rim bursts out from it, and on the beat after the word it snaps shut."""
    L, span = c.line, _real(c.span)
    t = span[0].a
    bt = c.P.get('beat', 0) or 0.375

    def late():
        x0, x1, y, h = _box(span, t + 0.25)
        cx = (x0 + x1) / 2
        r = (x1 - x0) / 2 + 40
        ry = h * 0.8 + 14                      # flat: it must not reach the subtitle under the line
        t1 = min(max(span[-1].b + bt * 1.5, t + 0.9), L.t_out)
        life = t1 - t
        hexp = poly_d([(r + r * math.cos(math.radians(60 * k)) * (1 if k % 3 == 0 else 0.86), ry + ry * math.sin(math.radians(60 * k)) / 0.866) for k in range(6)])
        pop = f"\\fscx30\\fscy30\\t(0,90,\\fscx112\\fscy112)\\t(90,190,\\fscx100\\fscy100)\\t({ms(life-0.12)},{ms(life)},\\fscx20\\fscy20\\alpha&HFF&)"
        L.fx.append(ev(0, t - 0.02, t1, 'FX', c.name, f"\\an5\\pos({cx:.1f},{y:.1f})\\bord0\\shad0\\1c{bgr(c.col)}\\alpha&H38&\\blur1{pop}\\p1", hexp + "{\\p0}"))
        L.fx.append(ev(0, t - 0.02, t1, 'FX', c.name, f"\\an5\\pos({cx:.1f},{y:.1f})\\bord7\\shad0\\1a&HFF&\\3c&HFFFFFF&\\blur0.8{pop}\\p1", hexp + "{\\p0}"))
        # the burst rim: opens past the panel and fades within half a second
        L.fx.append(ev(0, t + 0.04, t + 0.5, 'FX', c.name, f"\\an5\\pos({cx:.1f},{y:.1f})\\bord4\\shad0\\1a&HFF&\\3c{bgr(mix(c.col, WHITE, .5))}\\blur1"
                       f"\\fscx100\\fscy100\\t(0,460,\\fscx150\\fscy150\\alpha&HFF&)\\p1", hexp + "{\\p0}"))
    _late(L, late)


def V_bolt(c):
    """电: バリバリ, crackling: on each sung glyph a jagged bolt strikes from above onto it, the glyph is jolted and
    glows electric for a moment. White core, coloured glow, gone in a fifth of a second."""
    L, span = c.line, _real(c.span)
    for k, g in enumerate(span):
        add(g, (g.a, {}), (g.a + 0.04, dict(dy=5, sx=0.12, sy=-0.08)), (g.a + 0.1, dict(dx=-3)), (g.a + 0.16, dict(dx=2)), (g.a + 0.26, {}))

    def late():
        for k, g in enumerate(span):
            x, y, sx, sy = _at(g, g.a)
            top = y - g.size * sy * 0.7
            pts, xx = [], x + c.rnd.uniform(-60, 60)
            ys = [top - 190 + 190 * j / 7 for j in range(8)]
            path = [(xx + (x - xx) * j / 7 + (c.rnd.uniform(-22, 22) if 0 < j < 7 else 0), yy) for j, yy in enumerate(ys)]
            for w, tags in ((9, f"\\1c{bgr(c.col)}\\blur6\\alpha&H40&"), (3.5, "\\1c&HFFFFFF&\\blur0.7")):
                left = [(px - w, py) for px, py in path]
                right = [(px + w * 0.4, py) for px, py in path][::-1]
                _shape(L.fx, 7, g.a - 0.02, g.a + 0.2, c.name, [left + right], _clip(c) + tags + "\\t(80,200,\\alpha&HFF&)")
            flash(L.fx, c.name, g.a, (x, top), (0, 1), c.col, size=40, life=0.16)
    _late(L, late)


def V_tape(c):
    """封: the police cordon (職務質問 / 任意同行): a yellow-and-black KEEP OUT tape is slapped across behind the line
    from left to right as the word is sung, the line shudders, and the tape stays while the line is held. When the line
    leaves the tape is torn in two and both ends drop away with it. ·拖 = the line is then dragged off to the right
    (任意同行: taken along)."""
    L, span = c.line, _real(c.span)
    t = span[0].a
    drag = '拖' in c.args
    if drag:
        for g in L.glyphs:
            add(g, (g.t_out - 0.02, {}), (g.t_end, dict(dx=160, rz=-3)))

    def late():
        gl = _real(L.glyphs)
        x0, x1, y, h = _box(gl, t + 0.1)
        bx = c.P.get('box', (0, 0, 1920, 1080))
        x0, x1 = max(x0 - 120, bx[0] + 4), min(x1 + 120, bx[2] - 4)
        hh = 46
        th = math.radians(-3)
        cy = y + 4

        def P(x, yy):
            return (cx0 + (x - cx0) * math.cos(th) - (yy - cy) * math.sin(th), cy + (x - cx0) * math.sin(th) + (yy - cy) * math.cos(th))
        cx0 = (x0 + x1) / 2
        band = [P(x0, cy - hh / 2), P(x1, cy - hh / 2), P(x1, cy + hh / 2), P(x0, cy + hh / 2)]
        stripes = []
        s = x0 + 40
        while s < x1 - 40:
            stripes.append([P(s, cy - hh / 2), P(s + 26, cy - hh / 2), P(s + 26 - 30, cy + hh / 2), P(s - 30, cy + hh / 2)])
            s += 64
        t_end = L.t_end
        to = min(g.t_out for g in gl)
        rv = 0.14
        clip0 = f"\\clip({x0-40:.0f},{cy-200:.0f},{x0-40:.0f},{cy+200:.0f})\\t(0,{ms(rv)},\\clip({x0-40:.0f},{cy-200:.0f},{x1+40:.0f},{cy+200:.0f}))"
        # stage 1: slapped on from left to right, stays while the line holds
        for pts, tags in (([band], "\\1c&H19C8FF&\\alpha&H18&\\blur0.6"), (stripes, "\\1c&H1A1A22&\\alpha&H18&\\blur0.4")):
            d = ' '.join(poly_d(p) for p in pts)
            L.fx.append(ev(0, t - rv, to, 'FX', c.name, f"\\an7\\pos(0,0)\\bord0\\shad0{tags}{clip0}\\p1", d + "{\\p0}"))
        # stage 2: torn in the middle, the halves drop and turn away with the line's exit
        dur = max(0.15, t_end - to)
        for side in (-1, 1):
            cl = (f"\\clip({x0-60:.0f},{cy-300:.0f},{cx0:.0f},{cy+300:.0f})" if side < 0 else f"\\clip({cx0:.0f},{cy-300:.0f},{x1+60:.0f},{cy+300:.0f})")
            org = (x0, cy) if side < 0 else (x1, cy)
            for pts, tags in (([band], "\\1c&H19C8FF&\\alpha&H18&\\blur0.6"), (stripes, "\\1c&H1A1A22&\\alpha&H18&\\blur0.4")):
                d = ' '.join(poly_d(p) for p in pts)
                L.fx.append(ev(0, to, to + dur, 'FX', c.name, f"\\an7\\pos(0,0)\\org({org[0]:.0f},{org[1]:.0f})\\bord0\\shad0{tags}{cl}"
                               f"\\t(0,{ms(dur)},\\frz{side*14}\\alpha&HFF&)\\p1", d + "{\\p0}"))
        shake_line(L, t, (x0 + x1) / 2, (1, 0), amp=8, fall=900)
    _late(L, late)


def V_flatten(c):
    """平: つるペタ / まな板, pressed flat: on the last sung glyph of the span the whole line is slammed flat (half its
    height, a little wider), dust puffs out at both ends, and it springs back up with a wobble."""
    L, span = c.line, _real(c.span)
    t = span[-1].a + 0.02
    for g in _real(L.glyphs):
        add(g, (t, {}), (t + 0.05, dict(sy=-0.32, sx=0.12, dy=g.size * 0.16)), (t + 0.22, dict(sy=-0.28, sx=0.1, dy=g.size * 0.14)),
            (t + 0.32, dict(sy=0.12, sx=-0.05, dy=-4)), (t + 0.42, dict(sy=-0.05)), (t + 0.5, {}))

    def late():
        gl = _real(L.glyphs)
        x0, x1, y, h = _box(gl, t + 0.06)
        base = y + h * 0.35
        dust(L.fx, c.name, c.rnd, t + 0.03, x0, base, n=4, spread=50)
        dust(L.fx, c.name, c.rnd, t + 0.03, x1, base, n=4, spread=50)
        for e in L.fx[-8:]:
            e['e'] = min(e['e'], L.t_end)
    _late(L, late)


def V_rush(c):
    """电车: the commuter train rushes past: speed streaks race right to left above and below the line and the words
    are swept along, leaning back into the wind, then settle."""
    L, span = c.line, _real(c.span)
    t, t1 = span[0].a, span[-1].b
    for g in span:
        add(g, (t, {}), (t + 0.1, dict(dx=-10, rz=-3)), (t1, dict(dx=-6, rz=-2)), (t1 + 0.25, {}))

    def late():
        gl = _real(L.glyphs)
        x0, x1, y, h = _box(gl, t)
        n = 12
        for k in range(n):
            s = t + (t1 + 0.15 - t) * k / n
            yy = y + (-1 if k % 2 else 1) * (h * 0.85 + c.rnd.uniform(6, 34))
            ln = c.rnd.uniform(140, 320)
            L.fx.append(shape_mv(0, s, s + 0.28, (x1 + 260, yy), (x0 - 260, yy), f"m 0 0 l {ln:.0f} 0 {ln:.0f} 3 0 3",
                                 _clip(c) + f"\\1c&HFFFFFF&\\alpha&H50&\\blur1", (0, 280), name=c.name))
    _late(L, late)


def V_seal(c):
    """章·<字>: the ticket inspector's stamp (子供料金 = child fare, 小): a red round seal with the character in it is
    slammed down beside the end of the word, tilted, the word dips under the blow; it stays while the line is held and
    leaves with it."""
    L, span = c.line, _real(c.span)
    ch = c.arg(0, '小')
    t = span[-1].a
    for g in span:
        add(g, (t, {}), (t + 0.05, dict(dy=4, sy=-0.08)), (t + 0.2, {}))

    def late():
        x, y, sx, sy = _at(span[-1], t + 0.1)
        gl = _real(L.glyphs)
        sx_ = [_at(g, t + 0.1)[0] for g in span]
        X = (min(sx_) + max(sx_)) / 2 + 30     # over the word, above its rubies: stamped on the ticket, never on a glyph
        R = 40
        Y = y - span[-1].size * 0.5 - 56 - R
        to = min(g.t_out for g in gl)
        dur = max(0.15, L.t_end - to)
        circ = f"m {R} 0 b {R*1.55:.0f} 0 {R*2} {R*0.45:.0f} {R*2} {R} b {R*2} {R*1.55:.0f} {R*1.55:.0f} {R*2} {R} {R*2} b {R*0.45:.0f} {R*2} 0 {R*1.55:.0f} 0 {R} b 0 {R*0.45:.0f} {R*0.45:.0f} 0 {R} 0"
        pop = f"\\fscx170\\fscy170\\alpha&HFF&\\t(0,80,\\fscx100\\fscy100\\alpha&H10&)"
        for e in (ev(6, t, to + dur, 'FX', c.name, f"\\an5\\pos({X:.1f},{Y:.1f})\\frz14\\bord5\\shad0\\1a&HFF&\\3c&H3A2EFF&\\blur0.8{pop}\\t({ms(to-t)},{ms(to-t+dur)},\\alpha&HFF&)\\p1", circ + "{\\p0}"),
                  ev(6, t, to + dur, 'JP', c.name, f"\\an5\\pos({X:.1f},{Y+2:.1f})\\frz14\\fs50\\bord0\\shad0\\1c&H3A2EFF&\\blur0.5{pop}\\t({ms(to-t)},{ms(to-t+dur)},\\alpha&HFF&)", ch)):
            L.fx.append(e)
    _late(L, late)


def V_rainbow(c):
    """虹桥 (主菜的另一半): a rainbow is drawn over the slanted telop from left to right exactly as the glyphs are stamped
    in (it reaches each end when that glyph is sung), sits there while the line holds, and fades out with the exit;
    on the last note the ドン sends a white ring out from the middle of the line. Never crosses a glyph: it arcs
    above the top of the line."""
    L = c.line
    gl = _real(L.glyphs)
    th = math.radians(6.5)

    def late():
        ta, tb = gl[0].a, gl[-1].a
        x0, x1, y, h = _box(gl, tb + 0.3)
        mid = (x0 + x1) / 2
        x0, x1 = x0 - 50, x1 + 50
        R0 = h * 0.85 + 30
        bw = 6
        top_y = c.P.get('box', (0, 0, 0, 0))[1] + 8
        # how high may the arch rise: the top band, slanted, must stay inside the box at its highest point
        hi = min(min(y - R0 - 7 * bw - (x - mid) * math.tan(th) for x in (x0 - 50, x1 + 50)), y - R0 - 7 * bw)
        rise = max(14, min(110, hi - top_y))
        cols = ['#FF3D9E', '#FF7A3D', '#FFC119', '#5FC22A', '#22C3E6', '#6E8BFF', '#B46BFF']
        to, te = min(g.t_out for g in gl), L.t_end

        def P(x, yy):          # rotate about the line centre so the arc follows the slant (right side up)
            dx, dy = x - mid, yy - y
            return (mid + dx * math.cos(th) + dy * math.sin(th), y - dx * math.sin(th) + dy * math.cos(th))
        clip0 = f"\\clip({x0-60:.0f},0,{x0-60:.0f},1080)\\t(0,{ms(tb-ta+0.05)},\\clip({x0-60:.0f},0,{x1+60:.0f},1080))"
        for k, col in enumerate(cols):
            off = k * bw
            top, bot = [], []
            N = 30
            for j in range(N + 1):
                u = j / N
                xx = x0 + (x1 - x0) * u
                arch = rise * math.sin(math.pi * u)
                top.append(P(xx, y - R0 - arch - off - 9 * (1 - abs(2 * u - 1)) * 0))
                bot.append(P(xx, y - R0 - arch - off + bw))
            L.fx.append(ev(0, ta - 0.05, te, 'FX', c.name, f"\\an7\\pos(0,0)\\bord0\\shad0\\1c{bgr(hexrgb(col))}\\alpha&H40&\\blur1{clip0}"
                           f"\\t({ms(to-ta+0.05)},{ms(te-ta+0.05)},\\alpha&HFF&)\\p1", poly_d(top + bot[::-1]) + "{\\p0}"))
        # ドン: a white ring from the middle of the line
        cx, cy = mid, y
        ring = f"m 0 0 b 0 -80 160 -80 160 0 b 160 80 0 80 0 0"
        L.fx.append(ev(1, tb, min(tb + 0.45, te), 'FX', c.name, f"\\an5\\pos({cx:.1f},{cy:.1f})\\bord6\\shad0\\1a&HFF&\\3c&HFFFFFF&\\blur1.5"
                       f"\\fscx60\\fscy60\\t(0,450,\\fscx{int((x1-x0)/160*110)}\\fscy260\\3a&HFF&\\bord1)\\p1", ring + "{\\p0}"))
        shake_line(L, tb, cx, (0, 1), amp=10, fall=900)
    _late(L, late)


def V_heart(c):
    """爱: ありがとう, the one honest word of the song: a heart opens out from behind the word, warm, and dissolves
    before the line leaves."""
    L, span = c.line, _real(c.span)
    t = span[0].a

    def late():
        x0, x1, y, h = _box(span, t + 0.2)
        cx = (x0 + x1) / 2
        heart = "m 50 90 b 10 60 0 40 0 25 b 0 5 20 -5 35 0 b 43 3 48 10 50 15 b 52 10 57 3 65 0 b 80 -5 100 5 100 25 b 100 40 90 60 50 90"
        k = min(2.3, max(1.4, (x1 - x0) / 100 * 0.9))
        life = max(0.6, min(1.6, L.t_out - t))
        for lay, tags in ((0, f"\\bord0\\1c{bgr(c.col)}\\alpha&H48&\\blur3"), (0, "\\bord6\\1a&HFF&\\3c&HFFFFFF&\\blur1")):
            L.fx.append(ev(lay, t, t + life, 'FX', c.name, f"\\an5\\pos({cx:.1f},{y:.1f})\\shad0{tags}{_clip(c)}\\fscx{int(k*60)}\\fscy{int(k*60)}"
                           f"\\t(0,{ms(life*0.35)},\\fscx{int(k*125)}\\fscy{int(k*125)})\\t({ms(life*0.55)},{ms(life)},\\fscx{int(k*150)}\\fscy{int(k*150)}\\alpha&HFF&)\\p1",
                           heart + "{\\p0}"))
    _late(L, late)


def V_sigh(c):
    """叹: はぁあ, a puff of breath: a little cloud is blown out of the end of the word, drifts up and thins away."""
    L, span = c.line, _real(c.span)
    t = span[-1].a

    def late():
        x, y, sx, sy = _at(span[-1], t + 0.1)
        x += span[-1].w / 2 + 30
        life = min(1.2, L.t_end - t)
        cloud = "m 20 40 b 0 40 0 15 22 15 b 25 0 50 -3 58 12 b 70 2 92 10 88 28 b 100 32 98 50 82 50 l 25 50 b 10 52 5 42 20 40"
        L.fx.append(shape_mv(0, t, t + life, (x, y), (x + 70, y - 60), cloud,
                             f"\\1c&HFFFFFF&\\alpha&H60&\\blur3\\fscx50\\fscy50\\t(0,{ms(life)},\\fscx140\\fscy140\\alpha&HFF&)",
                             (0, ms(life)), name=c.name))
    _late(L, late)


def V_pop(c):
    """破: the puffed cheeks burst: on the last sung glyph every puffed glyph snaps small and back, and a white ring
    pops out of each."""
    L, span = c.line, _real(c.span)
    t = span[-1].b
    for g in span:
        add(g, (t, {}), (t + 0.05, dict(sx=-0.2, sy=-0.2)), (t + 0.18, dict(sx=0.06, sy=0.06)), (t + 0.28, {}))

    def late():
        for g in span:
            x, y, sx, sy = _at(g, t)
            r = g.w * 0.55
            ring = f"m 0 {r:.0f} b 0 0 {2*r:.0f} 0 {2*r:.0f} {r:.0f} b {2*r:.0f} {2*r:.0f} 0 {2*r:.0f} 0 {r:.0f}"
            L.fx.append(ev(6, t, t + 0.3, 'FX', c.name, f"\\an5\\pos({x:.1f},{y:.1f})\\bord3\\shad0\\1a&HFF&\\3c&HFFFFFF&\\blur0.8"
                           f"\\fscx60\\fscy60\\t(0,300,\\fscx150\\fscy150\\alpha&HFF&)\\p1", ring + "{\\p0}"))
    _late(L, late)


def V_stomp(c):
    """踏: high heels stomping: each sung glyph comes down hard, and a shock ring spreads flat on the floor under it."""
    L, span = c.line, _real(c.span)
    for g in span:
        add(g, (g.a - 0.06, {}), (g.a - 0.02, dict(dy=-10)), (g.a + 0.03, dict(dy=5, sy=-0.1, sx=0.06)), (g.a + 0.16, {}))

    def late():
        for g in span:
            x, y, sx, sy = _at(g, g.a + 0.03)
            fy = y + g.size * 0.62
            ring = "m 0 10 b 0 0 100 0 100 10 b 100 20 0 20 0 10"
            L.fx.append(ev(0, g.a + 0.02, g.a + 0.34, 'FX', c.name, f"\\an5\\pos({x:.1f},{fy:.1f})\\bord3\\shad0\\1a&HFF&\\3c{bgr(mix(c.col, WHITE, .5))}\\blur1"
                           f"\\fscx40\\fscy60\\t(0,320,\\fscx130\\fscy110\\alpha&HFF&)\\p1", ring + "{\\p0}"))
    _late(L, late)


POP_VERBS.update({'集中': V_focus, '六角': V_hexcut, '电': V_bolt, '封': V_tape, '平': V_flatten, '电车': V_rush,
                  '章': V_seal, '虹桥': V_rainbow, '爱': V_heart, '叹': V_sigh, '破': V_pop, '踏': V_stomp})


def V_boom(c):
    """爆: the manga "ドン!" balloon: a spiky burst slams open behind the giant word, yellow with an ink edge like a
    printed effect, pushes the word up a hair, holds while the word holds and snaps shut on the beat after. Kept above
    the subtitle (it never reaches the Chinese line)."""
    L, span = c.line, _real(c.span)
    t = span[0].a
    bt = c.P.get('beat', 0) or 0.375

    def late():
        x0, x1, y, h = _box(span, t + 0.25)
        cx = (x0 + x1) / 2
        cy = y - 18
        rx = (x1 - x0) / 2 + 115
        ry = min(h * 0.95 + 44, (L.cn_y - 34) - cy)
        n = 16
        pts = []
        for k in range(2 * n):
            a = math.pi * k / n
            r = 1.0 if k % 2 == 0 else (0.62 + 0.1 * c.rnd.random())
            pts.append((rx + math.cos(a) * rx * r, ry + math.sin(a) * ry * r))
        d = poly_d(pts)
        t1 = min(max(span[-1].b + bt, t + 0.8), L.t_out)
        life = t1 - t
        pop = (f"\\fscx20\\fscy20\\t(0,80,\\fscx118\\fscy118)\\t(80,180,\\fscx100\\fscy100)"
               f"\\t({ms(life-0.12)},{ms(life)},\\fscx10\\fscy10\\alpha&HFF&)")
        L.fx.append(ev(0, t - 0.02, t1, 'FX', c.name, f"\\an5\\pos({cx:.1f},{cy:.1f})\\bord4\\shad0\\1c&H4AE1FF&\\3c&H3A1E2A&\\1a&H28&\\3a&H20&\\blur0.8{pop}\\p1", d + "{\\p0}"))
        L.fx.append(ev(0, t + 0.03, t + 0.45, 'FX', c.name, f"\\an5\\pos({cx:.1f},{cy:.1f})\\bord3\\shad0\\1a&HFF&\\3c&HFFFFFF&\\blur1"
                       f"\\t(0,420,\\fscx135\\fscy125\\alpha&HFF&)\\p1", d + "{\\p0}"))
        shake_line(L, t, cx, (0, 1), amp=9, fall=500)
    _late(L, late)


POP_VERBS['爆'] = V_boom


# ---------------------------------------------------------------- manga marks (v3, 2026-11-24: "物象, 特效和意象都可以再多一点")
# Small printed manga signs that a telop PV puts on words: the speech balloon, the anger mark 💢, the "!?", a glint,
# squeeze arrows. Each one is attached to its word (drawn where the word really is), pops in on the note, and is gone
# with the line at the latest. None crosses a glyph.

def _pop(life, k=1.0):
    return (f"\\fscx{int(20*k)}\\fscy{int(20*k)}\\t(0,70,\\fscx{int(115*k)}\\fscy{int(115*k)})\\t(70,160,\\fscx{int(100*k)}\\fscy{int(100*k)})"
            f"\\t({ms(max(0.2, life - 0.15))},{ms(life)},\\fscx{int(60*k)}\\fscy{int(60*k)}\\alpha&HFF&)")


def V_balloon(c):
    """吹出: a manga speech balloon pops up around the words someone says (君 の いつもこう言うの, 「かわいい」,
    ちゃん付け): a white rounded balloon with a tail, behind the words, holding until the line leaves."""
    L, span = c.line, _real(c.span)
    t = span[0].a

    def late():
        x0, x1, y, h = _box(span, t + 0.2)
        rub = any(g.rubies for g in span)
        top = y - h * 0.62 - (40 if rub else 6)
        bot = min(y + h * 0.58, L.cn_y - 32)
        w, hh = (x1 - x0) + 44, bot - top
        r = hh / 2
        cx, cy = (x0 + x1) / 2, (top + bot) / 2
        d = (f"m {r} 0 l {w-r} 0 b {w} 0 {w} 0 {w} {r} l {w} {hh-r} b {w} {hh} {w} {hh} {w-r} {hh} "
             f"l {w*0.3+16:.0f} {hh} l {w*0.18:.0f} {hh+18} l {w*0.24:.0f} {hh} l {r} {hh} b 0 {hh} 0 {hh} 0 {hh-r} l 0 {r} b 0 0 0 0 {r} 0")
        t1 = min(g.t_out for g in _real(L.glyphs))
        life = max(0.3, t1 + 0.2 - t)
        L.fx.append(ev(2, t - 0.03, t - 0.03 + life, 'FX', c.name, f"\\an5\\pos({cx:.1f},{cy + 9:.1f})\\bord3\\shad0\\1c&HFFFFFF&\\3c&H3A1E2A&"
                       f"\\1a&H0C&\\3a&H00&\\blur0.6{_pop(life)}\\p1", d + "{\\p0}"))
    _late(L, late)


def V_anger(c):
    """怒: the manga anger mark (💢) pops at the top right of the word and throbs twice on the beat, red with a white
    edge: なによ, 悔しい, ふーんだ."""
    L, span = c.line, _real(c.span)
    t = span[0].a
    bt = c.P.get('beat', 0) or 0.375

    def late():
        x0, x1, y, h = _box(span, t + 0.1)
        X, Y = x1 - 6, y - h * 0.62 - 26 - (32 if span[-1].rubies else 0)   # above the word's end, never on a neighbour
        parts = []
        for q in range(4):
            a0 = math.radians(45 + 90 * q)
            ox, oy = math.cos(a0) * 15, math.sin(a0) * 15
            arc = []
            for j in range(7):
                a = a0 + math.pi + math.radians(-48 + 96 * j / 6)
                arc.append((ox + math.cos(a) * 12, oy + math.sin(a) * 12))
            inner = [(ox + math.cos(math.atan2(py - oy, px - ox)) * 5.5, oy + math.sin(math.atan2(py - oy, px - ox)) * 5.5) for px, py in arc]
            parts.append(poly_d([(p[0] + 30, p[1] + 30) for p in arc + inner[::-1]]))
        d = ' '.join(parts)
        t1 = min(t + bt * 4, min(g.t_out for g in _real(L.glyphs)))
        life = max(0.3, t1 - t)
        thr = ''.join(f"\\t({ms(bt*k)},{ms(bt*k+0.06)},\\fscx125\\fscy125)\\t({ms(bt*k+0.06)},{ms(bt*k+0.2)},\\fscx100\\fscy100)" for k in (1, 2) if bt * k + 0.2 < life - 0.15)
        L.fx.append(ev(6, t, t + life, 'FX', c.name, f"\\an5\\pos({X:.1f},{Y:.1f})\\frz-12\\bord3\\shad0\\1c&H4A28F0&\\3c&HFFFFFF&\\blur0.4"
                       f"{_pop(life, 1.5)}{thr.replace('125', '185').replace('fscx100', 'fscx150').replace('fscy100', 'fscy150')}\\p1", d + "{\\p0}"))
    _late(L, late)


def V_gasp(c):
    """惊: a red "!?" jumps up over the right of the word (え?, the moment she is caught out)."""
    L, span = c.line, _real(c.span)
    t = span[0].a

    def late():
        x0, x1, y, h = _box(span, t + 0.1)
        X, Y = (x0 + x1) / 2 + 14, y - h * 0.62 - 34
        t1 = min(g.t_out for g in _real(L.glyphs))
        life = max(0.3, t1 - t)
        L.fx.append(ev(6, t, t + life, 'JP', c.name, f"\\an5\\pos({X:.1f},{Y:.1f})\\frz-10\\fs64\\bord3\\shad0\\1c&H4A28F0&\\3c&HFFFFFF&\\blur0.4{_pop(life)}", "!?"))
    _late(L, late)


def V_glint(c):
    """闪: a single glint, the anime "キラッ": a four-point star opens on the top corner of the last glyph of the word
    as it is sung and closes again in a third of a second. Once; not a flicker."""
    L, span = c.line, _real(c.span)
    g = span[-1]

    def late():
        x, y, sx, sy = _at(g, g.a + 0.05)
        X, Y = x + g.w * sx * 0.42, y - g.size * sy * 0.55
        r = 32
        st = star4(r)
        for lay, tags in ((6, f"\\1c{bgr(c.col)}\\blur5\\alpha&H40&"), (7, "\\1c&HFFFFFF&\\blur0.5")):
            L.fx.append(ev(lay, g.a, g.a + 0.5, 'FX', c.name, f"\\an5\\pos({X:.1f},{Y:.1f})\\bord0\\shad0{tags}"
                           f"\\fscx0\\fscy0\\t(0,140,\\fscx130\\fscy130)\\t(140,500,\\fscx0\\fscy0)\\p1", st + "{\\p0}"))
    _late(L, late)


def V_squeeze(c):
    """挤: コンパクト / モキュモキュ: two fat arrows push in on the word from both sides on the note, the word is
    squeezed narrow while they press, then they let go."""
    L, span = c.line, _real(c.span)
    t, t1 = span[0].a, span[-1].b
    for g in span:
        add(g, (t, {}), (t + 0.08, dict(sx=-0.16, sy=0.06)), (t1, dict(sx=-0.12, sy=0.05)), (t1 + 0.15, {}))
    gl = _real(c.line.glyphs)
    mid = (gl[0].x + gl[-1].x) / 2
    for g in gl:                                   # the press closes the line in from both ends
        k = (mid - g.x) / max(1, (gl[-1].x - gl[0].x) / 2)
        add(g, (t, {}), (t + 0.08, dict(dx=k * 12)), (t1, dict(dx=k * 9)), (t1 + 0.15, {}))

    def late():
        x0, x1, y, h = _box(_real(L.glyphs), t + 0.08)    # outside the whole line: an arrow never sits on a glyph
        life = max(0.35, min(t1 + 0.2, min(g.t_out for g in _real(L.glyphs))) - t)
        arr = "m 0 0 l 22 16 l 0 32 l 8 16"
        for side, X0, X1 in ((1, x0 - 64, x0 - 30), (-1, x1 + 64, x1 + 30)):
            fr = '' if side > 0 else '\\frz180'
            L.fx.append(ev(6, t, t + life, 'FX', c.name, f"\\an5\\move({X0:.1f},{y:.1f},{X1:.1f},{y:.1f},0,90){fr}\\bord2\\shad0\\1c{bgr(c.col)}\\3c&HFFFFFF&"
                           f"\\blur0.4\\alpha&HFF&\\t(0,60,\\alpha&H00&)\\t({ms(life-0.12)},{ms(life)},\\alpha&HFF&)\\p1", arr + "{\\p0}"))
    _late(L, late)


from kfx_draw import star4
POP_VERBS.update({'吹出': V_balloon, '怒': V_anger, '惊': V_gasp, '闪': V_glint, '挤': V_squeeze})


# ---------------------------------------------------------------- loli things (v4, 2026-11-24 01:01)
# The user: "你直接仅分析这个歌曲去做吧, 我希望有点萝莉的元素", "这个 MV 没啥用". So these come from the song alone: a girl
# taken for a child (つるペタ, 子供料金, 小ちゃくて) who answers "ロリコンで良かったわ". The things a child is given (a hair
# bow, a swirl lollipop, a bottle of milk to grow taller, candy colours) are put ON her words, small, popping on the
# note and bobbing on the beat, and they leave with the line. Text effects that are not jumps: jelly letters that
# wobble when squeezed, a police light that sweeps across the letters.
CANDY = ['#FF4FA3', '#22C2A8', '#FFAA14', '#9B63FF']

BOW = ("m 32 18 l 6 3 b 0 0 0 36 6 33 l 32 18 m 32 18 l 58 3 b 64 0 64 36 58 33 l 32 18 "
       "m 30 21 l 21 42 l 28 42 l 33 23 m 34 21 l 43 42 l 36 42 l 31 23 m 25 18 b 25 9 39 9 39 18 b 39 27 25 27 25 18")
HEART = "m 50 90 b 10 60 0 40 0 25 b 0 5 20 -5 35 0 b 43 3 48 10 50 15 b 52 10 57 3 65 0 b 80 -5 100 5 100 25 b 100 40 90 60 50 90"
BOTTLE = "m 5 15 l 5 46 b 5 50 9 53 13 53 l 25 53 b 29 53 33 50 33 46 l 33 15 l 26 7 l 26 3 l 12 3 l 12 7 l 5 15"
CAP = "m 11 0 l 27 0 l 27 6 l 11 6"
LABEL = "m 5 24 l 33 24 l 33 38 l 5 38"


def _bob(life, bt, k=100, amp=12):
    """pop in, then a small nod on every beat, then shrink away at the end of its life."""
    s = f"\\fscx{int(k*0.2)}\\fscy{int(k*0.2)}\\t(0,80,\\fscx{int(k*1.2)}\\fscy{int(k*1.2)})\\t(80,170,\\fscx{k}\\fscy{k})"
    n = 1
    while bt * n + 0.2 < life - 0.2:
        a = bt * n
        s += f"\\t({ms(a)},{ms(a+0.05)},\\fscx{int(k*(1+amp/100))}\\fscy{int(k*(1-amp/200))})\\t({ms(a+0.05)},{ms(a+0.2)},\\fscx{k}\\fscy{k})"
        n += 1
    return s + f"\\t({ms(max(0.2, life-0.16))},{ms(life)},\\fscx{int(k*0.3)}\\fscy{int(k*0.3)}\\alpha&HFF&)"


def _thing(c, L, t, life, X, Y, layers, rot=0, k=100):
    bt = c.P.get('beat', 0) or 0.375
    for lay, tags, d in layers:
        L.fx.append(ev(lay, t, t + life, 'FX', c.name, f"\\an5\\pos({X:.1f},{Y:.1f})\\frz{rot}\\shad0{tags}{_clip(c)}{_bob(life, bt, k)}\\p1", d + "{\\p0}"))


def _life(L, t, cap=None):
    t1 = min(g.t_out for g in _real(L.glyphs))
    return max(0.35, min(t1, t + cap) - t if cap else t1 - t)


def _ink():
    return "\\1c&H3A1E2A&\\3c&H3A1E2A&\\bord5\\blur1.2\\alpha&H50&"


def V_bow(c):
    """蝶结: a hair bow (リボン) pops onto the top right of the word's first glyph, like a bow in a little girl's hair,
    and nods on every beat until the line leaves."""
    L, span = c.line, _real(c.span)
    g, t = span[0], span[0].a
    col = hexrgb(CANDY[0]) if c.col is None else c.col

    def late():
        x, y, sx, sy = _at(g, t + 0.1)
        X = x + g.w * sx * 0.5 + 8                      # off the glyph's top right corner, clear of its ruby
        Y = y - g.size * sy * 0.5 - 14 - (40 if g.rubies else 0)
        _thing(c, L, t, _life(L, t), X, Y, [(6, _ink(), BOW), (7, f"\\1c{bgr(hexrgb('#FF4FA3'))}\\3c&HFFFFFF&\\bord2.5\\blur0.4", BOW)], rot=18, k=80)
    _late(L, late)


def V_lolly(c):
    """糖: a swirl lollipop (ペロペロキャンディ) pops up just after the last glyph of the word, stick down, leaning a
    little, and nods on the beat: what you give a child, given to the one who says ロリコンで良かった."""
    L, span = c.line, _real(c.span)
    t = span[-1].a

    def late():
        x0, x1, y, h = _box(span, t + 0.1)
        R = 30
        ring = []
        for k in range(130):                            # a spiral band, white over the candy colour
            a = k / 129 * math.pi * 5.2
            r = 3 + (R - 4) * k / 129
            ring.append((R + math.cos(a) * r, R + math.sin(a) * r))
        inner = [(R + (p[0] - R) * 0.62, R + (p[1] - R) * 0.62) for p in ring]
        sw = poly_d(ring + inner[::-1])
        disc = f"m 0 {R} b 0 {-R*0.1:.0f} {2*R} {-R*0.1:.0f} {2*R} {R} b {2*R} {R*2.1:.0f} 0 {R*2.1:.0f} 0 {R}"
        stick = f"m {R-3} {2*R-2} l {R+3} {2*R-2} l {R+3} {2*R+36} l {R-3} {2*R+36}"
        X, Y = x1 + R + 18, y - 14
        layers = [(6, _ink(), disc + ' ' + stick), (7, "\\1c&HFFFFFF&\\3c&HFFFFFF&\\bord2\\blur0.3", stick),
                  (7, f"\\1c{bgr(hexrgb('#FF4FA3'))}\\3c&HFFFFFF&\\bord3\\blur0.4", disc), (8, "\\1c&HFFFFFF&\\bord0\\blur0.4\\alpha&H10&", sw)]
        _thing(c, L, t, _life(L, t), X, Y, layers, rot=-14, k=100)
    _late(L, late)


def V_milk(c):
    """牛奶: a little bottle of milk (to grow taller) pops up over the end of the word, つるペタ / 大人には / 小ちゃく."""
    L, span = c.line, _real(c.span)
    t = span[-1].a

    def late():
        x0, x1, y, h = _box(span, t + 0.1)
        X = x1 + 2
        Y = y - h * 0.62 - 30 - (30 if span[-1].rubies else 0)
        _thing(c, L, t, _life(L, t), X, Y, [(6, _ink(), BOTTLE + ' ' + CAP), (7, "\\1c&HFFFFFF&\\3c&HFFFFFF&\\bord2\\blur0.3", BOTTLE),
                                            (8, f"\\1c{bgr(hexrgb('#22A8E8'))}\\bord0\\blur0.3", CAP + ' ' + LABEL)], rot=12, k=115)
    _late(L, late)


def V_lilheart(c):
    """小心: a small candy heart pops over the word (スキ, 君) and beats with the song until the line leaves."""
    L, span = c.line, _real(c.span)
    t = span[0].a

    def late():
        x0, x1, y, h = _box(span, t + 0.1)
        X = (x0 + x1) / 2 + 6
        Y = y - h * 0.62 - 22 - (32 if any(g.rubies for g in span) else 0)
        _thing(c, L, t, _life(L, t), X, Y, [(6, _ink(), HEART), (7, f"\\1c{bgr(hexrgb('#FF4FA3'))}\\3c&HFFFFFF&\\bord3.5\\blur0.4", HEART)], rot=-8, k=34)
    _late(L, late)


def V_siren(c):
    """警灯: a police light goes round over the words (職務質問, 任意同行): a red glow sweeps left to right behind the
    letters, then a blue one back, twice, between the letters' dark edge and their fill. A sweep, never a flash."""
    L, span = c.line, _real(c.span)
    t = span[0].a
    gl = _real(L.glyphs)

    def late():
        x0, x1, y, h = _box(gl, t + 0.1)
        W = 150
        H = h * 0.95
        band = f"m 0 {H/2:.0f} b 0 0 {W} 0 {W} {H/2:.0f} b {W} {H:.0f} 0 {H:.0f} 0 {H/2:.0f}"     # a soft oval of light
        clip = '\\clip(%d,%d,%d,%d)' % (x0 - 16, y - h * 1.2, x1 + 16, y + h * 1.2)       # ends only; no hard top/bottom edge
        sw = 0.42
        for k in range(4):
            a = t + k * sw
            red = k % 2 == 0
            col = '#FF2E4A' if red else '#2E7BFF'
            xa, xb = (x0 - W, x1 + W) if red else (x1 + W, x0 - W)
            if a + sw > L.t_out:
                break
            L.fx.append(ev(2, a, a + sw, 'FX', c.name, f"\\an5\\move({xa:.1f},{y:.1f},{xb:.1f},{y:.1f})\\bord0\\shad0\\1c{bgr(hexrgb(col))}"
                           f"\\blur22\\alpha&H50&{clip}\\p1", band + "{\\p0}"))
    _late(L, late)


def V_jelly(c):
    """果冻: each glyph is a jelly sweet: on its note it is squashed flat, then wobbles tall-flat-tall, less each time,
    and sets. Not a jump: the glyph stays where it is and only its shape wobbles."""
    for g in _real(c.span):
        a = g.a
        add(g, (a - 0.02, {}), (a + 0.07, dict(sx=0.24, sy=-0.24, dy=4)), (a + 0.17, dict(sx=-0.14, sy=0.18, dy=-3)),
            (a + 0.27, dict(sx=0.08, sy=-0.09, dy=1)), (a + 0.37, dict(sx=-0.03, sy=0.04)), (a + 0.47, {}))


def V_candy(c):
    """糖果 (本曲主菜, v4): ロリコンで良かったわ, said three times. Each glyph drops onto its note like a sweet poured
    into a jar, squashes and wobbles like jelly, and takes a candy colour (pink, mint, lemon, grape in turn);
    on the last note the whole line bounces once together. With 蝶结 on the first word and 糖 on the last."""
    L = c.line
    gl = _real(L.glyphs)
    cols = {id(g): hexrgb(CANDY[k % 4]) for k, g in enumerate(gl)}
    for g in _real(c.span):
        g.tint = cols[id(g)]
        a = g.a
        add(g, (a - 0.1, {}), (a - 0.02, dict(dy=-26, sx=-0.08, sy=0.12)), (a + 0.06, dict(dy=3, sx=0.3, sy=-0.26)),
            (a + 0.16, dict(dy=-4, sx=-0.12, sy=0.16)), (a + 0.26, dict(sx=0.06, sy=-0.06)), (a + 0.36, {}))
    if _real(c.span)[-1] is gl[-1]:
        tl = gl[-1].a
        for g in gl:
            add(g, (tl, {}), (tl + 0.08, dict(dy=-12, sx=0.1, sy=0.1)), (tl + 0.26, {}))


POP_VERBS.update({'蝶结': V_bow, '糖': V_lolly, '牛奶': V_milk, '小心': V_lilheart, '警灯': V_siren, '果冻': V_jelly, '糖果': V_candy})


# ---------------------------------------------------------------- one-off things (v5, 2026-11-24 01:14)
# The user, on v4: "我不希望你的一些元素被复用, 希望你每次都是新的"; "黄色作为字体颜色, 白色作为描边或边框, 不好看".
# So every thing drawn in this song is drawn once: a library of small objects, each taken from the words of its own
# line (コンパクト -> a compact, 同い年 -> a birthday cake, アヒル -> a duck ...), each used by one line only (the
# design script asserts it). They are filled flat with a thin dark edge of their own hue: no white rims.
def _C(cx, cy, r):
    return _E(cx, cy, r, r)


def _E(cx, cy, rx, ry):
    k = 0.5523
    return (f"m {cx} {cy-ry} b {cx+rx*k:.1f} {cy-ry} {cx+rx} {cy-ry*k:.1f} {cx+rx} {cy} b {cx+rx} {cy+ry*k:.1f} {cx+rx*k:.1f} {cy+ry} {cx} {cy+ry} "
            f"b {cx-rx*k:.1f} {cy+ry} {cx-rx} {cy+ry*k:.1f} {cx-rx} {cy} b {cx-rx} {cy-ry*k:.1f} {cx-rx*k:.1f} {cy-ry} {cx} {cy-ry}")


def _R(x0, y0, x1, y1):
    return f"m {x0} {y0} l {x1} {y0} l {x1} {y1} l {x0} {y1}"


def _P(*pts):
    return poly_d(list(pts))


def _ARC(cx, cy, r0, r1, a0=0, a1=360, n=36):
    o = [(cx + r1 * math.cos(math.radians(a0 + (a1 - a0) * k / n)), cy + r1 * math.sin(math.radians(a0 + (a1 - a0) * k / n))) for k in range(n + 1)]
    i = [(cx + r0 * math.cos(math.radians(a0 + (a1 - a0) * k / n)), cy + r0 * math.sin(math.radians(a0 + (a1 - a0) * k / n))) for k in range(n + 1)]
    return poly_d(o + i[::-1])


def _star(cx, cy, r, k=0.45):
    return poly_d([(cx + (r if j % 2 == 0 else r * k) * math.sin(math.radians(36 * j)), cy - (r if j % 2 == 0 else r * k) * math.cos(math.radians(36 * j))) for j in range(10)])


def _spiral(cx, cy, R, turns=2.6, w=0.45):
    o = [(cx + math.cos(a) * r, cy + math.sin(a) * r) for k in range(120) for a, r in [(k / 119 * math.pi * 2 * turns, 2 + R * k / 119)]]
    i = [(cx + (x - cx) * w, cy + (y - cy) * w) for x, y in o]
    return poly_d(o + i[::-1])


DROP = "m 32 0 b 32 0 10 28 10 42 b 10 56 20 64 32 64 b 44 64 54 56 54 42 b 54 28 32 0 32 0"
# name: (parts [(fill hex, path)], what it is, where it sits: 'up' over the word's end / 'end' after the word)
ICONS = {
    '粉饼': ([('#FF8FB8', _E(32, 34, 28, 24)), ('#CFE6FF', _E(32, 34, 19, 15)), ('#E0A94A', _R(27, 8, 37, 12))], 'コンパクト: a compact', 'up'),
    '鸭': ([('#FFD45C', _E(36, 44, 26, 15)), ('#FFD45C', _C(20, 24, 13)), ('#FF8A1E', _P((6, 22), (-8, 27), (6, 31))), ('#2A1E3A', _C(17, 21, 2.6))], 'アヒル唇: a duck', 'up'),
    '书包': ([('#E8264E', _R(8, 10, 56, 62)), ('#B81A3A', _R(8, 10, 56, 32)), ('#E0A94A', _R(28, 28, 36, 38))], '大人には見えない: a school bag (ランドセル)', 'up'),
    '手提包': ([('#FF5F9E', _P((10, 26), (54, 26), (60, 60), (4, 60))), ('#C83A78', _ARC(32, 26, 10, 14, 180, 360))], '大人のおんな: a handbag', 'up'),
    '蛋糕': ([('#FFE1EA', _R(8, 32, 56, 60)), ('#FF7FAE', _R(6, 26, 58, 36)), ('#8FC8FF', _R(29, 8, 35, 26)), ('#FF9A2E', _E(32, 4, 4, 6))], '同い年: a birthday cake', 'up'),
    '王冠': ([('#F2B33A', _P((4, 56), (4, 20), (18, 36), (32, 8), (46, 36), (60, 20), (60, 56))), ('#FF4F8E', _C(32, 44, 5)), ('#4FB8FF', _C(16, 46, 4)), ('#4FB8FF', _C(48, 46, 4))], 'モデル: a crown', 'up'),
    '旗': ([('#A8754C', _R(6, 0, 10, 64)), ('#C9B8FF', _P((10, 4), (56, 16), (10, 30)))], '諦めてる: a little flag of surrender (lilac, not white)', 'up'),
    '口红': ([('#3A2E5A', _R(18, 36, 46, 64)), ('#E0A94A', _R(21, 24, 43, 38)), ('#E8264E', _P((22, 24), (22, 9), (42, 0), (42, 24)))], 'お化粧: a lipstick', 'up'),
    '领带': ([('#3A6BD8', _P((26, 0), (38, 0), (41, 8), (32, 14), (23, 8))), ('#3A6BD8', _P((27, 12), (37, 12), (46, 52), (32, 64), (18, 52))), ('#7FA6FF', _P((30, 22), (36, 22), (38, 30), (28, 30)))], '大人な君: a necktie', 'up'),
    '戒指': ([('#E0A94A', _ARC(32, 42, 15, 20)), ('#A8E2FF', _P((32, 2), (42, 12), (32, 24), (22, 12)))], '似合う女: a ring', 'up'),
    '奖牌': ([('#3A6BD8', _P((14, 0), (28, 0), (38, 28), (24, 28))), ('#E8264E', _P((36, 0), (50, 0), (40, 28), (26, 28))), ('#F2B33A', _C(32, 44, 18)), ('#FFD98A', _star(32, 44, 10))], 'そのままが1番: a first-place medal', 'up'),
    '奖杯': ([('#F2B33A', _P((12, 4), (52, 4), (46, 30), (32, 38), (18, 30))), ('#F2B33A', _R(29, 36, 35, 50)), ('#C98A2A', _R(18, 50, 46, 60)), ('#F2B33A', _ARC(12, 16, 6, 10, 90, 270)), ('#F2B33A', _ARC(52, 16, 6, 10, -90, 90))], '1番スキ: a trophy', 'up'),
    '公文包': ([('#8A5634', _R(6, 18, 58, 56)), ('#6A3F22', _ARC(32, 18, 8, 12, 180, 360)), ('#E0A94A', _R(28, 30, 36, 38))], '会社に行けば: a briefcase', 'up'),
    '眼镜': ([('#3A2E5A', _ARC(18, 32, 11, 15)), ('#3A2E5A', _ARC(46, 32, 11, 15)), ('#3A2E5A', _R(29, 29, 35, 33)), ('#CFE6FF', _C(18, 32, 11)), ('#CFE6FF', _C(46, 32, 11))], '出来る女: glasses', 'up'),
    '熊': ([('#C98B5A', _C(14, 16, 10)), ('#C98B5A', _C(50, 16, 10)), ('#C98B5A', _C(32, 36, 22)), ('#F3D2B0', _E(32, 45, 10, 8)), ('#2A1E3A', _C(24, 32, 3)), ('#2A1E3A', _C(40, 32, 3)), ('#2A1E3A', _C(32, 41, 3))], 'かわいい: a teddy bear', 'up'),
    '泪': ([('#7FCBFF', DROP)], '悔しい: a tear', 'up'),
    '蒸汽': ([('#FF9CC2', _C(14, 50, 9)), ('#FF9CC2', _C(30, 32, 12)), ('#FF9CC2', _C(50, 14, 14))], 'うーん もぉ: puffs of steam from a pout', 'up'),
    '星': ([('#FFC94A', _star(32, 34, 30))], 'だけど君は (2): a star', 'up'),
    '头巾': ([('#E8264E', _R(0, 22, 56, 38)), ('#E8264E', _P((52, 26), (64, 14), (66, 22))), ('#E8264E', _P((52, 34), (66, 44), (60, 50)))], '頑張ってる: a headband (ハチマキ)', 'up'),
    '唇': ([('#FF3A6A', _E(32, 28, 24, 9)), ('#E8264E', _E(32, 40, 21, 9))], 'アヒルみたいな唇: lips', 'up'),
    '放大镜': ([('#CFE6FF', _C(26, 26, 15)), ('#3A2E5A', _ARC(26, 26, 15, 20)), ('#3A2E5A', _P((39, 41), (44, 36), (64, 56), (59, 61)))], '見つめてる (2): a magnifying glass', 'up'),
    '糖纸': ([('#22C2A8', _E(32, 32, 17, 13)), ('#7FE3D0', _P((16, 32), (0, 20), (0, 44))), ('#7FE3D0', _P((48, 32), (64, 20), (64, 44)))], 'chorus 2: a wrapped sweet', 'end'),
    '冰淇淋': ([('#E8B060', _P((18, 34), (46, 34), (32, 70))), ('#FF9CC2', _C(32, 26, 15)), ('#B98CFF', _C(32, 8, 10))], 'chorus 3: an ice cream', 'end'),
    '身高尺': ([('#FFC2D6', _R(22, 0, 42, 70)), *[('#3A2E5A', _R(22, y, 32 if y % 14 else 36, y + 2)) for y in range(6, 66, 7)]], '小ちゃくて: a height chart', 'up'),
    '砧板': ([('#E9C08A', _R(0, 20, 66, 48)), ('#B98A50', _R(0, 44, 66, 48)), ('#7A5A3A', _C(56, 30, 4))], 'まな板: a cutting board', 'up'),
    '香水': ([('#C9A6FF', _R(14, 26, 50, 62)), ('#E9DEFF', _R(26, 16, 38, 26)), ('#E0A94A', _R(22, 4, 42, 16))], 'セクシーな人: a perfume bottle', 'up'),
    '信封': ([('#FFC9DD', _R(4, 14, 60, 54)), ('#FF8DB8', _P((4, 14), (32, 38), (60, 14))), ('#E8264E', _C(32, 36, 5))], '付き合ったら: a love letter', 'up'),
    '漩涡': ([('#9B63FF', _spiral(32, 32, 28))], '何言って: a dizzy swirl', 'up'),
    '音符': ([('#FF5F9E', _E(20, 52, 12, 9)), ('#FF5F9E', _R(28, 4, 32, 52)), ('#FF5F9E', _P((32, 4), (50, 14), (50, 24), (32, 14)))], 'いつもこう言うの (3): a note, the words he always sings', 'up'),
    '创可贴': ([('#F0BE8C', _R(0, 20, 64, 44)), ('#FFE2C8', _R(24, 20, 40, 44))], '頑張ってるのに (3): a sticking plaster', 'up'),
    '警帽': ([('#23356E', _R(8, 18, 56, 40)), ('#11182E', _P((2, 40), (62, 40), (52, 50), (12, 50))), ('#F2B33A', _C(32, 29, 5))], '職務質問 (2): a police cap', 'up'),
    '气球': ([('#FF4F6A', _E(32, 26, 20, 25)), ('#C8304A', _P((28, 50), (36, 50), (32, 56))), ('#7A5A6A', _R(31, 56, 33, 76))], 'ホッペタを膨らませて: a balloon', 'up'),
}


def V_icon(c):
    """物·<名>: one small thing from this line's words (ICONS), popping in on the word's last note, nodding on the beat
    and leaving with the line. 'up' things sit over the end of the word, clear of its ruby; 'end' things stand just
    after it. Flat fills with a thin dark edge of their own colour, a soft dark rim under all: no white."""
    L, span = c.line, _real(c.span)
    name = c.args[0]
    parts, _, where = ICONS[name]
    t = span[-1].a

    def late():
        x0, x1, y, h = _box(span, t + 0.1)
        if where == 'end':
            X, Y = x1 + 40, y - 6
        else:
            X = x1 - 4
            Y = y - h * 0.55 - 28 - (24 if any(g.rubies for g in span) else 0)
        allp = ' '.join(p for _, p in parts)
        layers = [(6, "\\1c&H2A1E2A&\\3c&H2A1E2A&\\bord4\\blur1.5\\alpha&H60&", allp)]
        for col, p in parts:
            rgb = hexrgb(col)
            layers.append((7, f"\\1c{bgr(rgb)}\\3c{bgr(mix(rgb, BLACK, 0.45))}\\bord1.4\\blur0.4", p))
        _thing(c, L, t, _life(L, t), X, Y, layers, rot=10 if where == "up" else -8, k=110)
    _late(L, late)


PALETTES = {'落': ['#FF4FA3', '#22B8A0', '#9B63FF', '#FF6B5A'], '浮': ['#2FA8F0', '#FF5F9E', '#7A5BFF', '#18B89A'],
            '浪': ['#E8366E', '#B05BFF', '#FF7A45', '#2E9BE8']}


def V_candy2(c):
    """糖果·落/浮/浪 (本曲主菜, v5): the three ロリコンで良かったわ are each new.
    落: each glyph drops onto its note like a sweet poured into a jar, squashes and wobbles like jelly.
    浮: each glyph rises from below on its note like a bubble of soda, stretched tall, and pops to size.
    浪: each note sends a wave along the line: the sung glyph jumps, its sung neighbours bob after it, smaller.
    Each in its own candy colours (never yellow), every glyph's edge in its own hue; one bounce together on the last note."""
    L = c.line
    gl = _real(L.glyphs)
    kind = next((a for a in c.args if a in PALETTES), '落')
    pal = PALETTES[kind]
    cols = {id(g): hexrgb(pal[k % 4]) for k, g in enumerate(gl)}
    for g in _real(c.span):
        g.tint = cols[id(g)]
        a = g.a
        if kind == '落':
            add(g, (a - 0.1, {}), (a - 0.02, dict(dy=-26, sx=-0.08, sy=0.12)), (a + 0.06, dict(dy=3, sx=0.3, sy=-0.26)),
                (a + 0.16, dict(dy=-4, sx=-0.12, sy=0.16)), (a + 0.26, dict(sx=0.06, sy=-0.06)), (a + 0.36, {}))
        elif kind == '浮':
            add(g, (a - 0.1, {}), (a - 0.02, dict(dy=22, sx=-0.18, sy=0.22)), (a + 0.08, dict(dy=-8, sx=0.2, sy=0.2)),
                (a + 0.2, dict(dy=2, sx=-0.04, sy=-0.04)), (a + 0.32, {}))
        else:
            k = gl.index(g)
            for j, h in enumerate(gl[max(0, k - 3):k + 1][::-1]):
                amp = [16, 9, 5, 2][j]
                add(h, (a + 0.04 * j, {}), (a + 0.04 * j + 0.08, dict(dy=-amp, sx=amp / 100, sy=amp / 100)), (a + 0.04 * j + 0.22, {}))
    if _real(c.span)[-1] is gl[-1]:
        tl = gl[-1].a
        for g in gl:
            add(g, (tl, {}), (tl + 0.08, dict(dy=-12, sx=0.1, sy=0.1)), (tl + 0.26, {}))


POP_VERBS.update({'物': V_icon, '糖果': V_candy2})
