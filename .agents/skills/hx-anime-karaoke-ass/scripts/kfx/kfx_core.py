"""kfx core: song-agnostic karaoke renderer.

Nothing in this package knows any song. Inputs: lyrics.txt + timing.json (skill format), design.md (kfx format, see kfx_README.md),
fonts. A glyph is drawn through a timeline of additive *contributions* (piecewise-linear keyframes); every layer of
the glyph, its ruby included, is rendered through the same timeline, so whatever a verb does to a glyph, the ruby
follows. A glyph can be split into parts (top / bottom halves) from a time on; each part has its own extra timeline.
"""
import math
from dataclasses import dataclass, field

# ---------------------------------------------------------------- time / colour helpers

def ts(x):
    cs = max(0, int(round(x * 100)))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def hexrgb(h):
    h = h.strip().lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def bgr(rgb):
    r, g, b = rgb
    return f"&H{b:02X}{g:02X}{r:02X}&"


def mix(a, b, k):
    return tuple(round(x * (1 - k) + y * k) for x, y in zip(a, b))


def ahex(v):
    v = max(0, min(255, int(round(v))))
    return f"&H{v:02X}&"


WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

# ---------------------------------------------------------------- contributions

KEYS = ('dx', 'dy', 'sx', 'sy', 'am', 'bl', 'rz')   # rz: degrees, positive = clockwise on screen   # sx/sy/am are deltas (0 = unchanged), am=-1 -> invisible


class Track:
    """piecewise-linear keyframes; value before the first key = first key, after the last = last key."""

    def __init__(self, keys):
        self.keys = sorted(keys, key=lambda k: k[0])

    def at(self, t):
        ks = self.keys
        if t <= ks[0][0]:
            return ks[0][1]
        if t >= ks[-1][0]:
            return ks[-1][1]
        for (t0, v0), (t1, v1) in zip(ks, ks[1:]):
            if t0 <= t <= t1:
                k = 0 if t1 == t0 else (t - t0) / (t1 - t0)
                return {n: v0.get(n, 0) * (1 - k) + v1.get(n, 0) * k for n in set(v0) | set(v1)}
        return ks[-1][1]

    def times(self):
        return [k[0] for k in self.keys]


def kf(*pairs):
    """kf((t, {dy: 3}), (t2, {})) -> Track. missing keys are 0."""
    return Track(list(pairs))


def total(tracks, t):
    v = dict.fromkeys(KEYS, 0.0)
    for tr in tracks:
        for n, x in tr.at(t).items():
            v[n] += x
    return v


# ---------------------------------------------------------------- data

@dataclass
class Ruby:
    ch: str
    ox: float          # offset from the glyph centre
    oy: float
    a: float
    b: float
    w: float = 22.0


@dataclass
class Glyph:
    ch: str
    kind: str
    x: float
    y: float
    w: float
    size: float
    a: float
    b: float
    style: str = 'JP'
    rubies: list = field(default_factory=list)
    tracks: list = field(default_factory=list)
    pieces: list = field(default_factory=list)   # [{t, poly, rpoly, trs}] the glyph broken into parts from t on
    tint: object = None            # rgb fill when sung (highlight)
    glow: float = 0.0              # extra sung glow 0..1
    dim: list = field(default_factory=list)   # [(t, rgb)] fill becomes rgb from t (erase etc.)
    t_in: float = 0.0
    t_out: float = 0.0
    t_end: float = 0.0


@dataclass
class Line:
    idx: int
    text: str
    cn: str
    glyphs: list
    s: float
    e: float
    color: tuple = (255, 255, 255)
    t_in: float = 0.0
    t_out: float = 0.0
    t_end: float = 0.0
    cn_y: float = 0.0
    fx: list = field(default_factory=list)    # extra events (dicts)


# ---------------------------------------------------------------- event emit

def ev(layer, t0, t1, style, name, tags, text):
    return dict(L=layer, s=t0, e=t1, st=style, n=name, tx='{' + tags + '}' + text)


def dump(e):
    return f"Dialogue: {e['L']},{ts(e['s'])},{ts(e['e'])},{e['st']},{e['n']},0,0,0,,{e['tx']}"


# ---------------------------------------------------------------- glyph rendering

def _segments(g, extra_times):
    T = {g.t_in, g.t_end}
    for tr in g.tracks:
        T.update(tr.times())
    T.update(extra_times)
    T = sorted({round(t, 2) for t in T if g.t_in - 1e-6 <= t <= g.t_end + 1e-6})   # centiseconds: no gaps
    out = []
    for t0, t1 in zip(T, T[1:]):
        out.append((t0, t1))
    return out


def _clip_rect(cx, cy, rel, sx, sy):
    x0, y0, x1, y1 = rel
    return (cx + x0 * sx, cy + y0 * sy, cx + x1 * sx, cy + y1 * sy)


def _isect(r1, r2):
    if r1 is None:
        return r2
    if r2 is None:
        return r1
    return (max(r1[0], r2[0]), max(r1[1], r2[1]), min(r1[2], r2[2]), min(r1[3], r2[3]))



def clip_poly(poly, nx, ny, c):
    """Sutherland-Hodgman: keep nx*x+ny*y <= c."""
    out = []
    n = len(poly)
    for k in range(n):
        p, q = poly[k], poly[(k + 1) % n]
        fp, fq = nx * p[0] + ny * p[1] - c, nx * q[0] + ny * q[1] - c
        if fp <= 0:
            out.append(p)
        if (fp < 0) != (fq < 0) and fp != fq:
            k_ = fp / (fp - fq)
            out.append((p[0] + (q[0] - p[0]) * k_, p[1] + (q[1] - p[1]) * k_))
    return out


