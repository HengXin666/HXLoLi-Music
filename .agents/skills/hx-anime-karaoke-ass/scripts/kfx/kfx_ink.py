"""Ink boxes of what libass draws, measured from the font files (not guessed from the font size).
A frame, a box, anything that has to sit an even distance from the words must measure the words' ink: CJK glyphs sit
inside their em box with uneven margins, ruby adds height on some lines only, and "size * k" guesses give the uneven
gaps users notice at once (2026-11-23)."""
import os
from functools import lru_cache
from fontTools.ttLib import TTFont
from fontTools.pens.boundsPen import BoundsPen

FONTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'fonts')
FACE = {'JP': 'ShipporiMinchoB1-Bold.ttf', 'RB': 'ShipporiMinchoB1-Bold.ttf', 'LAT': 'CormorantGaramond-Light.ttf', 'CN': 'LXGWWenKai-Medium.ttf'}


@lru_cache(None)
def _font(name):
    f = TTFont(name if os.path.isabs(name) else os.path.join(FONTS, name))
    hh = f['hhea']
    return f, f.getBestCmap(), f.getGlyphSet(), hh.ascent, hh.descent, f['head'].unitsPerEm


SLANT = {'LAT': 0.21}      # styles libass draws as synthetic italic (Italic=-1 on an upright face): x shear per px of height


def ink(ch, fs, cx, cy, face='JP', P=None):
    """ink box (x0, y0, x1, y1) of one character drawn \\an5 at (cx, cy) with font size fs (libass: fs = ascent - descent)."""
    name = P['fonts'][face][0] if P and face in P.get('fonts', {}) else (FACE.get(face) or FACE['JP'])
    f, cmap, gs, asc, desc, upem = _font(os.path.join(P.get('fontdir', FONTS), name) if P else name)
    s = fs / (asc - desc)
    xs0 = ys0 = 1e9
    xs1 = ys1 = -1e9
    adv_total = 0
    boxes = []
    for c in ch:
        g = cmap.get(ord(c))
        if g is None:
            adv_total += upem * 0.5
            continue
        adv = f['hmtx'][g][0]
        bp = BoundsPen(gs)
        gs[g].draw(bp)                             # works for glyf and CFF faces alike
        if bp.bounds:
            x0, y0, x1, y1 = bp.bounds
            boxes.append((adv_total + x0, y0, adv_total + x1, y1))
        adv_total += adv
    if not boxes:
        return None
    left = cx - adv_total * s / 2
    top_line = cy - (asc - desc) * s / 2          # \an5 centres the line box (ascent..descent)
    for x0, y0, x1, y1 in boxes:
        xs0, xs1 = min(xs0, left + x0 * s), max(xs1, left + x1 * s)
        ys0, ys1 = min(ys0, top_line + (asc - y1) * s), max(ys1, top_line + (asc - y0) * s)
    k = SLANT.get(face, 0)
    if k:                                          # the shear pivots on the baseline: tops lean right, descenders left
        base = top_line + asc * s
        xs0, xs1 = xs0 - max(0, ys1 - base) * k, xs1 + max(0, base - ys0) * k
    return xs0, ys0, xs1, ys1


def union(bs):
    bs = [b for b in bs if b]
    return (min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs)) if bs else None


def line_ink(l, P):
    """ink of a line at rest: its glyphs and their ruby; and the ink of its CN line."""
    out = []
    for g in l.glyphs:
        if g.kind == 'space':
            continue
        fs = getattr(g, 'fs', P['jp_fs'])
        out.append(ink(g.ch, fs, g.x, g.y, getattr(g, 'style', 'JP'), P))
        for r in g.rubies:
            out.append(ink(r.ch, P['rb_fs'], g.x + r.ox, g.y + r.oy, 'RB', P))
    cn = ink(l.cn, P['cn_fs'], P['cx'], l.cn_y, 'CN', P) if l.cn else None
    return union(out), cn
