import re
"""kfx build: python3 kfx_build.py <project dir> [--design design.md] [--out out.kfx.ass] [--fonts DIR]
Reads lyrics.txt + timing.json + the design; writes the ASS. Refuses to render a design that fails validation (exit 2).
The only generator of this skill. Golden: examples/mushoku_ed1/kfx must rebuild byte-identical (kfx_test.py)."""
import argparse, os, random, sys
SKILL = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kfx_core import hexrgb, bgr, mix, WHITE, BLACK, ev, dump, ts
from kfx_glyph import render_glyph
import kfx_song as S
import kfx_design as D
import kfx_motif as M
from kfx_verbs import VERBS, Ctx, exit_line

HEADER = """[Script Info]
Title: {title}
ScriptType: v4.00+
WrapStyle: 2
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: JP,{jpf},{jp},&H00FFFFFF,&H000000FF,&H00000000,&H00000000,{jpb},0,0,0,100,100,0,0,1,2,0,5,0,0,0,1
Style: RB,{jpf},{rb},&H00FFFFFF,&H000000FF,&H00000000,&H00000000,{jpb},0,0,0,100,100,0,0,1,1.5,0,5,0,0,0,1
Style: CN,{cnf},{cn},&H00FFFFFF,&H000000FF,&H00000000,&H00000000,{cnb},0,0,0,100,100,1,0,1,2,0,5,0,0,0,1
Style: LAT,Cormorant Garamond Light,{lat},&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,-1,0,0,100,100,0,0,1,2,0,5,0,0,0,1
Style: FX,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def globals_from(d):
    G = {}
    g = d['globals']
    if g.get('拍'):
        b0, bt = g['拍'].split()[:2]
        G['beat0'], G['beat'] = float(b0), float(bt)
    for k, key in (('日文字体', 'jp_font'), ('中文字体', 'cn_font')):
        if g.get(k):
            G[key] = g[k].split()[0]
    if g.get('皮肤'):
        G['skin'] = g['皮肤'].split()[0]
    for k, key in (('整行离场', 'flow_whole'), ('特效跟行', 'fx_clamp')):
        if g.get(k):
            G[key] = 1.0 if g[k].split()[0] in ('是', '1', 'on', 'yes') else 0.0
    for k, key in (('日文字号', 'jp_fs'), ('中文字号', 'cn_fs'), ('行高', 'y'), ('交叠', 'overlap'), ('幅度', 'amp')):
        if g.get(k):
            G[key] = float(g[k].split()[0])
    return G


def cn_events(L, P):
    out = []
    acc = L.color
    dark = mix(acc, BLACK, 0.82)
    t_in, t_out, t_end = getattr(L, 'cn_t', (L.t_in + 0.12, L.t_out, L.t_end))   # flow sets cn_t: the CN lines swap, never overlap
    a, b = L.s, max(g.b for g in L.glyphs)
    x = P['cx']
    y = L.cn_y
    w = len(L.cn) * P['cn_fs'] * 0.75 + 20
    x0, x1 = x - w / 2, x + w / 2
    for lay, tags in ((1, f"\\bord4\\shad0\\1c{bgr(dark)}\\3c{bgr(dark)}\\1a&HFF&\\3a&H80&\\blur4"),
                      (2, f"\\bord1.6\\shad0\\1c&HE8E4E0&\\3c{bgr(mix(dark, BLACK, .4))}\\1a&H40&\\3a&H20&\\blur0.5"),
                      (3, f"\\bord1.8\\shad0\\1c&HFFFFFF&\\3c{bgr(acc)}\\blur0.6")):
        clip = ''
        if lay == 3:
            clip = (f"\\clip({x0:.0f},{y-40:.0f},{x0:.0f},{y+40:.0f})"
                    f"\\t({int((a-t_in)*1000)},{int((b-t_in)*1000)},\\clip({x0:.0f},{y-40:.0f},{x1:.0f},{y+40:.0f}))")
        fade = f"\\fad(250,{int((t_end-t_out)*1000)})"
        out.append(ev(lay, t_in, t_end, 'CN', f'ly:L{L.idx:02d}',
                      f"\\an5\\move({x:.1f},{y+10:.1f},{x:.1f},{y:.1f},0,300){fade}" + tags + clip, L.cn))
    return out


class DesignError(Exception):
    def __init__(self, errs):
        super().__init__('\n'.join(errs))
        self.errs = errs


def check_design(proj, text, fontdir):
    """parse + validate a design against the project's lyrics; returns (design, song lines, globals, errors)"""
    d = D.parse(text)
    lines, P = S.load_song(proj, fontdir, globals_from(d))
    errs = D.validate(d, lines)
    for no, Dl in sorted(d['lines'].items()):
        if Dl['fields'].get('物象'):
            errs += [f'L{no:02d}: {x}' for x in M.check(Dl['fields']['物象'], proj)]
    bp = os.path.join(proj, 'beats.json')
    if os.path.exists(bp):                       # tracked beat grid (kfx_sync.py beats): 卡点 verbs and motifs read it
        import json
        b = json.load(open(bp))
        P['beats'], P['bar0'] = b['beats'], b['bar0']
    return d, lines, P, errs


# Agent Notes: kfx 是本 skill 唯一的生成器; オンリー v2.1 金样必须逐字节重现 (kfx_test.py)
# .agents/notes/implemented/architecture/2026-11-22-karaoke-kfx-single-generator.md
def build(proj, design_path, out_path, fontdir):
    d, lines, P, errs = check_design(proj, open(design_path, encoding='utf-8').read(), fontdir)
    G_ = globals_from(d)
    if errs:
        raise DesignError(errs)
    rnd = random.Random(7)
    skin = S.Skin(G_.get('skin', ''))
    # the area the user keeps (lyric box + 5 %, kfx_check K2), for set pieces to stay inside (kfx_verbs_pop _clip)
    P['box'] = (min(L.x0 for L in lines) - 90, P['y'] - 195, max(L.x1 for L in lines) + 90, max(L.cn_y for L in lines) + 80)
    events = []
    for L in lines:
        Dl = d['lines'][L.idx]
        L.color = hexrgb(Dl['fields']['色'][:7])
        for k, g in enumerate(L.glyphs):
            S.entrance(g, k)
            S.onset(g)
        flat = L.glyphs
        cmap = [k for k, g in enumerate(flat) for _ in g.ch.replace(' ', '')]   # char index -> glyph index
        name = f'fx:L{L.idx:02d}'
        n0 = [len(g.tracks) for g in flat]
        for p in Dl['patches']:
            span = flat[cmap[p['at']]:cmap[p['at'] + p['len'] - 1] + 1]
            for v, args in p['fx']:
                VERBS[v](Ctx(L, span, args, P, rnd, name, p['text']))
        if P['amp'] != 1.0:
            for g, k in zip(flat, n0):
                g.tracks[k:] = [scaled(tr, P['amp']) for tr in g.tracks[k:]]
        exit_line(L, Dl['fields']['出场'].split()[0], rnd)
        for b, args in M.parse(Dl['fields'].get('物象', '')):
            mc = M.MCtx(L, args, P, rnd, name, proj)
            mc.lines = lines
            M.MOTIFS[b](mc)
        for f in getattr(L, 'late', []):          # set pieces drawn where the glyphs really are (kfx_verbs_pop)
            f()
        if G_.get('fx_clamp'):                    # 特效跟行: nothing outlives its line
            L.fx[:] = [dict(e, e=min(e['e'], L.t_end)) for e in L.fx if e['s'] < L.t_end - 0.02]
        for g in L.glyphs:
            events += render_glyph(g, L, skin, f'ly:L{L.idx:02d}')
        events += cn_events(L, P)
        events += L.fx
    bad = [e for L in lines for e in order_errors(L)]
    if bad:
        raise DesignError(bad)
    events.sort(key=lambda e: (e['s'], e['L']))
    title = d['globals'].get('标题', os.path.basename(os.path.abspath(proj)))
    F = P['fonts']
    head = HEADER.format(title=title, jp=int(P['jp_fs']), rb=int(P['rb_fs']), cn=int(P['cn_fs']), lat=int(P['lat_fs']),
                         jpf=F['JP'][1], jpb=-F['JP'][2], cnf=F['CN'][1], cnb=-F['CN'][2])
    open(out_path, 'w', encoding='utf-8-sig').write(head + '\n'.join(dump(e) for e in events) + '\n')
    write_manifest(out_path, lines, design_path)
    return len(events), len(lines)


def order_errors(L, step=1 / 24):
    """字序门禁: 歌词要能读. 任何时刻, 同一行看得见的字从左到右的顺序不许颠倒 (用户 2026-11-23 否决 换位:
    "读着读着发现它逆序了, 这吓不吓人"). 动作可以跳, 可以挤, 不可以让后一个字跑到前一个字左边."""
    from kfx_core import total
    gl = [g for g in L.glyphs if g.kind != 'space']
    t = L.t_in
    while t < L.t_end:
        xs = []
        for g in gl:
            if g.t_in <= t <= g.t_out:
                v = total(g.tracks, t)
                if v.get('am', 0) > -0.5:
                    xs.append((g, g.x + v.get('dx', 0)))
        for (g1, x1), (g2, x2) in zip(xs, xs[1:]):
            if x2 < x1 - 2:
                return [f'L{L.idx:02d}: {t:.2f}s 字序颠倒 ({g1.ch} 跑到了 {g2.ch} 右边); 动作不许改变阅读顺序']
        t += step
    return []


def scaled(tr, amp):
    """幅度: a verb's movement (dx dy rz sx sy) times amp; fades and blur stay."""
    from kfx_core import Track
    return Track([(t, {n: (x * amp if n in ('dx', 'dy', 'rz', 'sx', 'sy') else x) for n, x in v.items()}) for t, v in tr.keys])


# Agent Notes: 验收台左侧歌词 / 设计稿跟随读 out.<x>.manifest.json 的 phrase 单元; kfx 必须同时写它, 否则新工程台子歌词为空
# .agents/notes/implemented/architecture/2026-11-23-kfx-manifest-for-studio.md
def write_manifest(out_path, lines, design_path):
    import json
    units = []
    for L in lines:
        chars = [[g.ch, round(g.a, 3), round(g.b, 3), round(g.x - g.w / 2, 1), round(g.w, 1)] for g in L.glyphs]
        ys = [g.y for g in L.glyphs] or [0]
        units.append(dict(key=f'kfx#{L.idx}', kind='phrase', name=f'L{L.idx:02d}', label=f'L{L.idx:02d}',
                          lines=[L.idx], t=[round(L.t_in, 3), round(L.t_end, 3)],
                          band=[round(L.x0, 1), round(min(ys) - 80, 1), round(L.x1, 1), round(L.cn_y + 40, 1)],
                          chars=chars, cn=L.cn, params=dict(fx='kfx')))
    m = dict(format='hx-assfx-manifest', version=1, generator='kfx_build',
             inputs=dict(design=os.path.basename(design_path)), meta=dict(text_lift=0), units=units)
    mp = re.sub(r'\.ass$', '', out_path) + '.manifest.json'
    with open(mp, 'w', encoding='utf-8') as fh:
        json.dump(m, fh, ensure_ascii=False, indent=1)
    return mp


def default_fonts(proj):
    f = os.path.join(proj, 'fonts')
    return f if os.path.isdir(f) else os.path.join(SKILL, 'fonts')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('proj')
    ap.add_argument('--design', default=None)
    ap.add_argument('--out', default=None)
    ap.add_argument('--fonts', default=None)
    a = ap.parse_args()
    out = a.out or os.path.join(a.proj, 'out.kfx.ass')
    try:
        n, k = build(a.proj, a.design or os.path.join(a.proj, 'design.md'), out, a.fonts or default_fonts(a.proj))
    except DesignError as e:
        print('设计稿没过校验, 不渲染:')
        print('\n'.join('  ' + x for x in e.errs))
        sys.exit(2)
    print(f'{out}: {n} events, {k} lines')
