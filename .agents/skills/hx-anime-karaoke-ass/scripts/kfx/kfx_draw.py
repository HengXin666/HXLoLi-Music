"""kfx verbs: generic actions the singer ("我") does to words. Each verb works at two scales where it makes sense:
the glyph scale (each glyph, when sung) and the line scale (once, across the span or the line).
A verb gets ctx: line, span (glyphs), args (list of '·' params), P (globals), seed. It mutates glyph timelines and
appends drawing events to line.fx. No verb knows any song."""
import math, random
from kfx_core import kf, ev, bgr, mix, WHITE, BLACK, hexrgb

# ---------------------------------------------------------------- shapes (ASS drawing, origin top-left)

def crescent(w, h):
    return (f"m 0 {h:.1f} b {w*.25:.1f} 0 {w*.75:.1f} 0 {w:.1f} {h:.1f} "
            f"b {w*.75:.1f} {h*.42:.1f} {w*.25:.1f} {h*.42:.1f} 0 {h:.1f}")

def oval(w, h):
    k = 0.552
    rx, ry = w / 2, h / 2
    return (f"m {rx:.1f} 0 b {rx+rx*k:.1f} 0 {w:.1f} {ry-ry*k:.1f} {w:.1f} {ry:.1f} "
            f"b {w:.1f} {ry+ry*k:.1f} {rx+rx*k:.1f} {h:.1f} {rx:.1f} {h:.1f} "
            f"b {rx-rx*k:.1f} {h:.1f} 0 {ry+ry*k:.1f} 0 {ry:.1f} b 0 {ry-ry*k:.1f} {rx-rx*k:.1f} 0 {rx:.1f} 0")

def ring(w, h, t):
    return oval(w, h) + ' ' + _shift(oval(w - 2 * t, h - 2 * t), t, t, rev=True)

def _shift(d, dx, dy, rev=False):
    toks = d.split()
    out = []
    i = 0
    while i < len(toks):
        tk = toks[i]
        if tk in 'mlb':
            out.append(tk); i += 1; continue
        out.append(f"{float(tk)+dx:.1f}"); out.append(f"{float(toks[i+1])+dy:.1f}"); i += 2
    return ' '.join(out)

def drop(w, h):
    return f"m {w/2:.1f} 0 b {w*.8:.1f} {h*.42:.1f} {w:.1f} {h*.6:.1f} {w:.1f} {h*.74:.1f} b {w:.1f} {h*.92:.1f} {w*.78:.1f} {h:.1f} {w/2:.1f} {h:.1f} b {w*.22:.1f} {h:.1f} 0 {h*.92:.1f} 0 {h*.74:.1f} b 0 {h*.6:.1f} {w*.2:.1f} {h*.42:.1f} {w/2:.1f} 0"

def petal(w, h):
    return f"m 0 {h/2:.1f} b {w*.3:.1f} 0 {w*.8:.1f} 0 {w:.1f} {h/2:.1f} b {w*.8:.1f} {h:.1f} {w*.3:.1f} {h:.1f} 0 {h/2:.1f}"

def leaf(w, h):
    return f"m 0 {h/2:.1f} b {w*.35:.1f} {-h*.1:.1f} {w*.75:.1f} 0 {w:.1f} {h/2:.1f} b {w*.75:.1f} {h:.1f} {w*.35:.1f} {h*1.1:.1f} 0 {h/2:.1f} m {w*.1:.1f} {h/2:.1f} l {w*.95:.1f} {h*.48:.1f} {w*.95:.1f} {h*.52:.1f} {w*.1:.1f} {h/2:.1f}"

def star4(r):
    k = r * 0.22
    return f"m {r:.1f} 0 l {r+k:.1f} {r-k:.1f} {2*r:.1f} {r:.1f} {r+k:.1f} {r+k:.1f} {r:.1f} {2*r:.1f} {r-k:.1f} {r+k:.1f} 0 {r:.1f} {r-k:.1f} {r-k:.1f}"

def rect(w, h, r=0):
    if r <= 0:
        return f"m 0 0 l {w:.1f} 0 {w:.1f} {h:.1f} 0 {h:.1f}"
    return (f"m {r:.1f} 0 l {w-r:.1f} 0 b {w:.1f} 0 {w:.1f} 0 {w:.1f} {r:.1f} l {w:.1f} {h-r:.1f} "
            f"b {w:.1f} {h:.1f} {w:.1f} {h:.1f} {w-r:.1f} {h:.1f} l {r:.1f} {h:.1f} b 0 {h:.1f} 0 {h:.1f} 0 {h-r:.1f} "
            f"l 0 {r:.1f} b 0 0 0 0 {r:.1f} 0")

def drape(w, h):
    """a cloth laid over the words: soft top fold, wavy hem."""
    n = max(2, int(w / 60))
    d = f"m 0 {h*.18:.1f} b {w*.3:.1f} 0 {w*.7:.1f} 0 {w:.1f} {h*.15:.1f} l {w:.1f} {h*.8:.1f}"
    for k in range(n, 0, -1):
        xa, xb = w * k / n, w * (k - 1) / n
        d += f" b {xa-(xa-xb)*.3:.1f} {h:.1f} {xb+(xa-xb)*.3:.1f} {h*.7:.1f} {xb:.1f} {h*.85:.1f}"
    return d

def arc_r(w, h, t):
    """mirror of arc: concave left."""
    return (f"m 0 0 b {w*1.4:.1f} {h*.2:.1f} {w*1.4:.1f} {h*.8:.1f} 0 {h:.1f} "
            f"b {w*1.25-t:.1f} {h*.78:.1f} {w*1.25-t:.1f} {h*.22:.1f} 0 0")

def arc(w, h, t):
    """open bracket-like arc, concave right."""
    return (f"m {w:.1f} 0 b {-w*.4:.1f} {h*.2:.1f} {-w*.4:.1f} {h*.8:.1f} {w:.1f} {h:.1f} "
            f"b {t-w*.25:.1f} {h*.78:.1f} {t-w*.25:.1f} {h*.22:.1f} {w:.1f} 0")

def shape_ev(layer, t0, t1, x, y, draw, tags, name='fx'):
    return ev(layer, t0, t1, 'FX', name, f"\\an7\\pos({x:.1f},{y:.1f})\\bord0\\shad0" + tags + "\\p1", draw + "{\\p0}")

def shape_mv(layer, t0, t1, a, b, draw, tags, mv=(0, None), name='fx', an=5):
    m1 = '' if mv[1] is None else f",{int(mv[0])},{int(mv[1])}"
    return ev(layer, t0, t1, 'FX', name,
              f"\\an{an}\\move({a[0]:.1f},{a[1]:.1f},{b[0]:.1f},{b[1]:.1f}{m1})\\bord0\\shad0" + tags + "\\p1", draw + "{\\p0}")

def ms(x):
    return int(round(x * 1000))

# ---------------------------------------------------------------- verb context

class Ctx:
    def __init__(self, line, span, args, P, rnd, name, span_text):
        self.line, self.span, self.args, self.P, self.rnd, self.name, self.text = line, span, args, P, rnd, name, span_text
        self.col = line.color
        self.light = mix(line.color, WHITE, 0.55)

    def arg(self, k, d=None):
        return self.args[k] if len(self.args) > k else d

    def glyph_by_text(self, sub, last=True):
        """index into line glyphs where `sub` ends (for '·到<词>')."""
        cmap = [k for k, g in enumerate(self.line.glyphs) for _ in g.ch.replace(' ', '')]
        t = ''.join(g.ch.replace(' ', '') for g in self.line.glyphs)
        p = t.rfind(sub) if last else t.find(sub)
        return None if p < 0 else cmap[p + len(sub) - 1]

# ---------------------------------------------------------------- glyph-scale building blocks
