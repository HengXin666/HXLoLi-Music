"""kfx glyph: cut pieces and per-glyph rendering (all layers through one timeline)."""
import math
from kfx_core import *
from kfx_core import _segments, _clip_rect, _isect


def hp_poly(planes, R=420):
    poly = [(-R, -R), (R, -R), (R, R), (-R, R)]
    for nx, ny, c in planes:
        poly = clip_poly(poly, nx, ny, c)
    return poly


def _xf(px, py, sx, sy, rot):
    r = math.radians(rot)
    x, y = px * sx, py * sy
    return x * math.cos(r) - y * math.sin(r), x * math.sin(r) + y * math.cos(r)


def _wrect(f, kind, hw):
    """left-to-right wipe: the sung part is left of the edge."""
    edge = -hw - 3 + (2 * hw + 6) * f
    if kind == 'sung':
        return (-hw - 60, -260, edge, 260)
    return (edge, -260, hw + 60, 260)


def render_glyph(g, line, skin, name):
    out = []
    H = g.size
    wipe_times = [g.a, g.b] + [r.a for r in g.rubies] + [r.b for r in g.rubies] + [d[0] for d in g.dim]
    t_cut = min([p['t'] for p in g.pieces], default=None)
    if t_cut is not None:
        wipe_times.append(t_cut)
    segs = _segments(g, wipe_times)

    def fill_frac(t, a, b):
        if t <= a:
            return 0.0
        if t >= b:
            return 1.0
        return (t - a) / (b - a)

    def fill_rgb(t):
        c = g.tint or WHITE
        for t0, rgb in g.dim:
            if t >= t0 - 1e-6:
                c = rgb
        return c

    layers = skin.glyph_layers(g, line)
    end = round(t_cut, 2) if t_cut is not None else g.t_end
    items = [(g.ch, g.style, 0.0, 0.0, g.a, g.b, False, g.w / 2)]
    for r in g.rubies:
        items.append((r.ch, 'RB', r.ox, r.oy, r.a, r.b, True, r.w / 2))
    for (t0, t1) in segs:
        if t0 >= end - 1e-6:
            continue
        va, vb = total(g.tracks, t0), total(g.tracks, t1)
        dur = int(round((t1 - t0) * 1000))
        sxa, sya, sxb, syb = 1 + va['sx'], 1 + va['sy'], 1 + vb['sx'], 1 + vb['sy']
        ama, amb = max(0, 1 + va['am']), max(0, 1 + vb['am'])
        if ama <= 0.003 and amb <= 0.003:
            continue
        pa = (g.x + va['dx'], g.y + va['dy'])
        pb = (g.x + vb['dx'], g.y + vb['dy'])
        for (ch, st, ox, oy, a, b, is_rb, hw) in items:
            oxa, oya = _xf(ox, oy, sxa, sya, va['rz'])
            oxb, oyb = _xf(ox, oy, sxb, syb, vb['rz'])
            ca = (pa[0] + oxa, pa[1] + oya)
            cb = (pb[0] + oxb, pb[1] + oyb)
            for (layer, base_tags, kind) in layers(is_rb):
                fa_, fb_ = fill_frac(t0, a, b), fill_frac(t1, a, b)
                if kind == 'sung' and fb_ <= 0:
                    continue
                if kind == 'pale' and fa_ >= 1:
                    continue
                clip = ''
                if kind in ('sung', 'pale') and not (kind == 'sung' and fa_ >= 1) and not (kind == 'pale' and fb_ <= 0):
                    A = _clip_rect(ca[0], ca[1], _wrect(fa_, kind, hw), sxa, sya)
                    B = _clip_rect(cb[0], cb[1], _wrect(fb_, kind, hw), sxb, syb)
                    clip = '\\clip(%d,%d,%d,%d)' % tuple(round(v) for v in A)
                    if any(abs(p - q) > 0.5 for p, q in zip(A, B)):
                        clip += f'\\t(0,{dur},\\clip(%d,%d,%d,%d))' % tuple(round(v) for v in B)
                tags = base_tags(t0, fill_rgb(t0))
                a1, a3 = skin.alphas(layer, is_rb)
                al = f"\\1a{ahex(255 - (255 - a1) * ama)}\\3a{ahex(255 - (255 - a3) * ama)}"
                tal = f"\\1a{ahex(255 - (255 - a1) * amb)}\\3a{ahex(255 - (255 - a3) * amb)}"
                blur = skin.blur(layer, is_rb)
                bl = f"\\blur{blur + va['bl']:.2f}"
                tbl = f"\\blur{blur + vb['bl']:.2f}" if abs(vb['bl'] - va['bl']) > 0.01 else ''
                rot = f"\\org({ca[0]:.1f},{ca[1]:.1f})\\frz{-va['rz']:.2f}" if abs(va['rz']) > 0.01 or abs(vb['rz']) > 0.01 else ''
                trot = f"\\frz{-vb['rz']:.2f}" if rot else ''
                trans = f"\\t(0,{dur},\\fscx{sxb*100:.1f}\\fscy{syb*100:.1f}{trot}{tal}{tbl})"
                gtags = (f"\\an5\\move({ca[0]:.1f},{ca[1]:.1f},{cb[0]:.1f},{cb[1]:.1f},0,{dur})"
                         f"\\fscx{sxa*100:.1f}\\fscy{sya*100:.1f}{rot}")
                out.append(ev(layer + (20 if is_rb else 0), t0, t1, st, name, gtags + tags + al + bl + clip + trans, ch))
    if g.pieces:
        out += render_pieces(g, line, skin, name, items, layers, fill_rgb)
    return out


def render_pieces(g, line, skin, name, items, layers, fill_rgb, fps=30.0):
    """each piece is drawn in short static steps (vector clips cannot move), merged where the pose holds still."""
    out = []
    for pc in g.pieces:
        def pose(t):
            v = total(g.tracks + pc['trs'], t)
            return v
        T = [round(pc['t'], 2)]
        t = T[0]
        tend = round(g.t_end, 2)
        while t < tend - 1e-6:
            step = 1 / fps if t < pc['t'] + 0.5 else 1 / 15.0      # dense through the blow, lighter afterwards
            t = round(min(tend, t + step), 2)
            if t > T[-1]:
                T.append(t)
        steps = []
        s0 = T[0]
        p0 = pose(s0)
        for t in T[1:]:
            p = pose(t)
            moved = (abs(p['dx'] - p0['dx']) > 0.6 or abs(p['dy'] - p0['dy']) > 0.6 or abs(p['rz'] - p0['rz']) > 0.4
                     or abs(p['am'] - p0['am']) > 0.02 or abs(p['sx'] - p0['sx']) > 0.006 or abs(p['sy'] - p0['sy']) > 0.006
                     or any(abs(t - d[0]) < 0.5 / fps for d in g.dim))
            if moved or t >= tend - 1e-6:
                steps.append((s0, t, pose(s0)))
                s0, p0 = t, pose(t)
        for (t0, t1, v) in steps:
            am = max(0, 1 + v['am'])
            if am <= 0.003:
                continue
            sx, sy, rz = 1 + v['sx'], 1 + v['sy'], v['rz']
            cx, cy = g.x + v['dx'], g.y + v['dy']
            for (ch, st, ox, oy, a, b, is_rb, hw) in items:
                poly = pc['rpoly'] if is_rb else pc['poly']
                if poly is None or len(poly) < 3:
                    continue
                pts = [_xf(px, py, sx, sy, rz) for px, py in poly]
                cl = 'm ' + ' '.join(f"{cx+x:.0f} {cy+y:.0f}" if k != 1 else f"l {cx+x:.0f} {cy+y:.0f}"
                                     for k, (x, y) in enumerate(pts))
                ox2, oy2 = _xf(ox, oy, sx, sy, rz)
                px_, py_ = cx + ox2, cy + oy2
                for (layer, base_tags, kind) in layers(is_rb):
                    if kind == 'pale':
                        continue
                    tags = base_tags(t0, fill_rgb(t0))
                    a1, a3 = skin.alphas(layer, is_rb)
                    al = f"\\1a{ahex(255 - (255 - a1) * am)}\\3a{ahex(255 - (255 - a3) * am)}"
                    blur = skin.blur(layer, is_rb) + v['bl']
                    out.append(ev(layer + (20 if is_rb else 0), t0, t1, st, name,
                                  f"\\an5\\pos({px_:.1f},{py_:.1f})\\org({px_:.1f},{py_:.1f})\\frz{-rz:.2f}"
                                  f"\\fscx{sx*100:.1f}\\fscy{sy*100:.1f}" + tags + al + f"\\blur{blur:.2f}\\clip({cl})", ch))
    return out
