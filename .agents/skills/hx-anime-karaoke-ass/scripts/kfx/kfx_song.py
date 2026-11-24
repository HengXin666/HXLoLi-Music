"""kfx3: song loading, layout, skin, schedule. Song-agnostic: every number comes from design globals or defaults."""
import os, re
from fontTools.ttLib import TTFont
import kfx_lyrics as LM
from kfx_core import Glyph, Ruby, Line, hexrgb, bgr, mix, WHITE, BLACK, kf

FONTS = {
    'JP': ('ShipporiMinchoB1-Bold.ttf', 'Shippori Mincho B1', 1),
    'RB': ('ShipporiMinchoB1-Bold.ttf', 'Shippori Mincho B1', 1),
    'CN': ('LXGWWenKai-Medium.ttf', 'LXGW WenKai Medium', 0),
    'LAT': ('CormorantGaramond-Light.ttf', 'Cormorant Garamond Light', 0),
}


def song_fonts(fontdir, G):
    """per-song faces: design globals 日文字体 / 中文字体 name a font file in the fonts dir; the family is read from it.
    The face is part of the song's look (a Mincho suits a ballad, a round pop face suits a comic song), so it is a
    design choice, not a constant. Default = the faces the golden sample was made with."""
    F = dict(FONTS)
    for key, sts in (('jp_font', ('JP', 'RB')), ('cn_font', ('CN',))):
        fn = G.get(key)
        if fn:
            nm = TTFont(os.path.join(fontdir, fn))['name']
            fam = nm.getDebugName(1) or nm.getDebugName(4)
            for st in sts:
                F[st] = (fn, fam, 0)
    return F


class Metrics:
    def __init__(self, fontdir, fonts=None):
        self.f = {}
        for st, (fn, _, _) in (fonts or FONTS).items():
            t = TTFont(os.path.join(fontdir, fn))
            o = t['OS/2']
            self.f[st] = (t.getBestCmap(), t['hmtx'], t['head'].unitsPerEm, o.usWinAscent + o.usWinDescent)

    def width(self, st, text, fs):
        cmap, hmtx, upem, h = self.f[st]
        w = 0
        for c in text:
            gn = cmap.get(ord(c))
            w += hmtx[gn][0] if gn else upem
        return w / h * fs


DEFAULT = dict(jp_fs=86, rb_fs=34, cn_fs=48, lat_fs=74, y=905, cn_dy=76, rb_dy=-56, gap=0.42, maxw=1640,
               enter=0.55, exit=0.55, hold=0.35, handover=0.12, beat0=0.0, beat=0.0, cx=960,
               overlap=0.0, amp=1.0, flow_whole=0.0)


def load_song(proj, fontdir, G):
    P = dict(DEFAULT)
    P.update({k: v for k, v in G.items() if k in DEFAULT})
    P['fonts'] = song_fonts(fontdir, G)
    P['fontdir'] = fontdir
    M = Metrics(fontdir, P['fonts'])
    src = LM.load(os.path.join(proj, 'lyrics.txt'), os.path.join(proj, 'timing.json'))
    lines = []
    for ln in src:
        gl = []
        fs = P['jp_fs']
        widths = []
        for g in ln.glyphs:
            if g.kind == 'space':
                widths.append(fs * 0.69 * P['gap'])
            elif g.kind == 'latin':
                widths.append(M.width('LAT', g.ch, P['lat_fs']) + 10)
            else:
                widths.append(M.width('JP', g.ch, fs))
        tot = sum(widths)
        sc = min(1.0, P['maxw'] / tot) if tot else 1
        x = P['cx'] - tot * sc / 2
        for g, w in zip(ln.glyphs, widths):
            w *= sc
            if g.kind != 'space':
                st = 'LAT' if g.kind == 'latin' else 'JP'
                size = (P['lat_fs'] if st == 'LAT' else fs) * sc
                G_ = Glyph(g.ch, g.kind, x + w / 2, P['y'], w, size * 0.69, g.a, g.b, style=st)
                G_.fs = size
                n = len(g.rubies)
                for k, r in enumerate(g.rubies):
                    rw = P['rb_fs'] * 0.69
                    ox = (k - (n - 1) / 2) * rw
                    G_.rubies.append(Ruby(r.ch, ox, P['rb_dy'] * sc, r.a, r.b, rw))
                gl.append(G_)
            x += w
        L = Line(ln.idx, ''.join(g.ch.replace(' ', '') for g in ln.glyphs if g.kind != 'space'), ln.cn, gl, ln.s, ln.e)
        L.raw_text = ln.text
        L.cn_y = P['y'] + P['cn_dy']
        L.x0 = P['cx'] - tot * sc / 2
        L.x1 = P['cx'] + tot * sc / 2
        lines.append(L)
    schedule(lines, P)
    if P['overlap'] > 0:
        flow(lines, P)
    return lines, P


# Agent Notes: 快歌行间几乎无空隙, 单行轮换时新行只能在开唱时才出现; overlap>0 时逐字让位 (仍是单行, 见 flow)
# .agents/notes/implemented/architecture/2026-11-23-kfx-two-rows-and-stage-verbs.md
def flow(lines, P):
    """fast songs, still one row: every glyph of the next line enters `overlap` s before it is sung; the old line's glyphs
    standing where it lands step out just before (left glyphs, sung first, leave first)."""
    lead, ex = P['overlap'], 0.3
    for i in range(len(lines) - 1):
        A, B = lines[i], lines[i + 1]
        if B.s - max(g.b for g in A.glyphs) > lead + 0.6:
            continue                                    # enough gap: the normal hand-over already works
        for g in A.glyphs:
            hit = [h.a for h in B.glyphs if h.kind != 'space' and abs(h.x - g.x) < (h.w + g.w) / 2 + 12]
            if hit:
                g.t_out = max(g.b + 0.08, min(g.t_out, min(hit) - lead - ex))
                g.t_end = g.t_out + ex
        if P.get('flow_whole'):
            # 整行离场: the old line leaves as one, on the moment the first glyph had to step aside (left first by a hair),
            # so no glyph of it is left standing beside the new line (用户 2026-11-24: 消失时间没对齐, 残留在那里)
            # a sustained last note may not hold the old line on screen into the new one: by the new line's first
            # note everything of the old line is on its way out (the wipe of a long tail is nearly full by then)
            fa = min(h.a for h in B.glyphs if h.kind != 'space')
            lim = fa - 0.45
            # it holds whole until its last glyph is sung (never thins out while it is still being sung), then goes
            t0 = min(lim, max(max(g.b for g in A.glyphs) + 0.08, fa - lead - ex))
            for k, g in enumerate(A.glyphs):
                g.t_out = max(t0 + min(0.08, 0.008 * k), min(g.a + 0.12, fa - 0.05))
                g.t_end = g.t_out + ex
        A.t_out = min(g.t_out for g in A.glyphs)
        A.t_end = max(g.t_end for g in A.glyphs)
        for h in B.glyphs:
            old = [g.t_end for g in A.glyphs if abs(h.x - g.x) < (h.w + g.w) / 2 + 12]
            h.t_in = max([h.a - lead] + old)
        if P.get('flow_whole'):
            # ... and the new line comes in whole, as the old one's last glyph starts to leave (a cross-fade, never a
            # line that builds itself up glyph by glyph and looks half missing)
            # 用户 2026-11-24 01:14 "02:28 从这里开始就有点跟不上": in the fast part the two lines stood half-faded on top of
            # each other for the whole hand-over. The new line now waits until the old one is gone.
            tin = max(fa - lead, min(g.t_out for g in A.glyphs) + ex)
            for k, h in enumerate(B.glyphs):
                h.t_in = tin + min(0.12, 0.012 * k)
        B.t_in = min(h.t_in for h in B.glyphs)
        sw = max(B.t_in, A.cn_t[0] + 0.3 if hasattr(A, 'cn_t') else A.t_in + 0.4)
        A.cn_t = (getattr(A, 'cn_t', (A.t_in + 0.12,))[0], sw - 0.15, sw)
        B.cn_t = (sw, B.t_out, B.t_end)


def schedule(lines, P):
    """one line on screen at a time; the old line has left before the next first syllable."""
    for i, L in enumerate(lines):
        last_b = max(g.b for g in L.glyphs)
        nxt = lines[i + 1].s if i + 1 < len(lines) else last_b + 3
        L.t_exit_dur = P['exit']
        t_out = min(last_b + P['hold'], nxt - P['handover'] - P['exit'])
        if t_out < last_b:                       # tight: shorten the exit, never cut the singing
            t_out = last_b
            L.t_exit_dur = max(0.2, nxt - P['handover'] - last_b)
        L.t_out = t_out
        L.t_end = t_out + L.t_exit_dur
        prev_end = lines[i - 1].t_end if i else 0
        L.t_in = max(prev_end, L.s - P['enter'] - 0.25)
        n = len(L.glyphs)
        for k, g in enumerate(L.glyphs):
            g.t_in = L.t_in + min(0.25, 0.022 * k)
            g.t_out = L.t_out + min(0.25, 0.018 * k)
            g.t_end = g.t_out + L.t_exit_dur * 0.8
            L.t_end = max(L.t_end, g.t_end)


# ---------------------------------------------------------------- skin
class Skin:
    """unsung = pale ink with a dark edge; singing fills the glyph from the bottom (the feeling fills the word);
    sung = white (or the highlight tint) with the line colour edge and a soft line-colour glow."""

    def __init__(self, kind=''):
        self.kind = kind

    def glyph_layers(self, g, line):
        if self.kind == '贴纸':
            return self.sticker(g, line)
        if self.kind == '跟色':
            return self.follow(g, line)
        acc = line.color
        dark = mix(acc, BLACK, 0.82)
        def L(is_rb):
            k = 0.6 if is_rb else 1.0
            bold = g.glow
            return [
                (1, lambda t, c: f"\\bord{6 * k:.1f}\\shad0\\1c{bgr(dark)}\\3c{bgr(dark)}", 'all'),
                (2, lambda t, c: f"\\bord{2.4 * k:.1f}\\shad0\\1c{bgr((244, 241, 236))}\\3c{bgr(mix(dark, BLACK, .4))}", 'pale'),
                (3, lambda t, c: f"\\bord{(6 + 4 * bold) * k:.1f}\\shad0\\1c{bgr(acc)}\\3c{bgr(acc)}", 'sung'),
                (4, lambda t, c: f"\\bord{2.6 * k:.1f}\\shad0\\1c{bgr(c)}\\3c{bgr(acc)}", 'sung'),
            ]
        return L

    def follow(self, g, line):
        """皮肤 跟色: the default skin (white when sung, line colour edge and glow), except that a glyph given its own
        colour (糖果, 警, 大字) takes an edge and glow of the same hue, a shade darker. No white rims anywhere
        (用户 2026-11-24: 白色作为描边或边框不好看; 红字配蓝边难看)."""
        acc = line.color
        dark = mix(acc, BLACK, 0.82)
        tinted = lambda c: sum(c) < 560          # a strong own colour, not white or 亮's pale tint
        def L(is_rb):
            k = 0.6 if is_rb else 1.0
            bold = g.glow
            return [
                (1, lambda t, c: f"\\bord{6 * k:.1f}\\shad0\\1c{bgr(dark)}\\3c{bgr(dark)}", 'all'),
                (2, lambda t, c: f"\\bord{2.4 * k:.1f}\\shad0\\1c{bgr((244, 241, 236))}\\3c{bgr(mix(dark, BLACK, .4))}", 'pale'),
                (3, lambda t, c: f"\\bord{(6 + 4 * bold) * k:.1f}\\shad0\\1c{bgr(c if tinted(c) else acc)}\\3c{bgr(c if tinted(c) else acc)}", 'sung'),
                (4, lambda t, c: f"\\bord{2.6 * k:.1f}\\shad0\\1c{bgr(c)}\\3c{bgr(mix(c, BLACK, 0.3) if tinted(c) else acc)}", 'sung'),
            ]
        return L

    def sticker(self, g, line):
        """皮肤 贴纸 (a telop PV's look): sung glyphs are filled with the line colour (or their tint) inside a thick white
        rim and a dark outer edge, like a sticker; unsung glyphs are pale with a dark edge. Every coloured fill sits on
        white, so a tint never meets the line colour edge to edge (用户 2026-11-24: 红字配蓝边, 太难看)."""
        acc = line.color
        ink = (42, 30, 58)
        hl = mix(acc, WHITE, 0.62)                # 亮's pale tint: on a sticker the highlight is the full colour
        def L(is_rb):
            k = 0.6 if is_rb else 1.0
            return [
                (1, lambda t, c: f"\\bord{9 * k:.1f}\\shad0\\1c{bgr(ink)}\\3c{bgr(ink)}", 'all'),
                (3, lambda t, c: f"\\bord{2.4 * k:.1f}\\shad0\\1c{bgr((244, 241, 236))}\\3c{bgr(ink)}", 'pale'),
                (4, lambda t, c: f"\\bord{(5.5 + 1.5 * g.glow) * k:.1f}\\shad0\\1c&HFFFFFF&\\3c&HFFFFFF&", 'sung'),
                (5, lambda t, c: f"\\bord{1.2 * k:.1f}\\shad0\\1c{bgr(acc if c in (WHITE, hl) else c)}\\3c&HFFFFFF&", 'sung'),
            ]
        return L

    def alphas(self, layer, is_rb):
        if self.kind == '贴纸':
            return {1: (0x30, 0x30), 3: (0x10, 0x10), 4: (0, 0), 5: (0, 0)}[layer]
        return {1: (255, 0x78), 2: (0x48, 0x10), 3: (255, 0x88), 4: (0, 0)}[layer]

    def blur(self, layer, is_rb):
        if self.kind == '贴纸':
            return {1: 2.5, 3: 0.6, 4: 0.8, 5: 0.5}[layer]
        return {1: 6, 2: 0.6, 3: 7, 4: 0.9}[layer]


def entrance(g, k):
    t = g.t_in
    g.tracks.append(kf((t, dict(dy=16, am=-1, bl=4, sy=0.12)), (t + 0.28, {})))


def onset(g):
    """the moment a glyph is sung: a small press (not a pop)."""
    a = g.a
    g.tracks.append(kf((a - 0.001, {}), (a + 0.04, dict(dy=3, sx=0.05, sy=0.05)), (a + 0.24, {})))
