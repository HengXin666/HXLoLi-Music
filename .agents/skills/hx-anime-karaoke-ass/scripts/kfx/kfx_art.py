# -*- coding: utf-8 -*-
"""kfx art: the things from the show that a motif carries (物象), drawn as ASS vector layers.

Two sources, one format. An Art is a list of (rgb, path) layers in pixel units of a box w x h, origin top-left;
every layer is written with the box's corners as moves ("m 0 0 m w h"), so all layers share one bbox and line up
under any \\an / \\fsc (libass aligns a drawing by its bbox).
  * drawn here, in code (茶杯 汽 瓣 心 星 ...): small props whose shape is simple; colours picked from the show's frames.
  * traced from a frame of the show (鲸 ...): `uv run kfx_art.py trace <cut.png> <工程>/art/<名>.json --h 120`
    (cut.png = an RGBA cut-out, background removed; vtracer turns it into colour layers). The project's art/ folder is
    looked up first, so each song keeps its own pictures and the code stays song-free.
Why vectors and not \\1img: \\1img only renders in the patched libass (studio/site); ffmpeg previews and kfx_check would
not see it, and a picture the check cannot see is a picture nobody verified.
"""
import json, math, os


class Art:
    def __init__(self, w, h, layers, name=''):
        self.w, self.h, self.layers, self.name = w, h, layers, name

    def paths(self, k=1.0):
        """layers scaled by k, as \\p3 path text (x4 precision), each anchored on the shared bbox."""
        W, H = self.w * k * 4, self.h * k * 4
        out = []
        for rgb, d in self.layers:
            toks = d.split()
            o = [f'm 0 0 m {W:.0f} {H:.0f}']
            for t in toks:
                try:
                    o.append(f'{float(t) * k * 4:.0f}')
                except ValueError:
                    o.append(t)
            out.append((rgb, ' '.join(o)))
        return out


def _pts(pts):
    return 'm ' + ' '.join((f'{x:.2f} {y:.2f}' if i != 1 else f'l {x:.2f} {y:.2f}') for i, (x, y) in enumerate(pts))


def _ellipse(cx, cy, rx, ry, n=28, a0=0, a1=360):
    return [(cx + rx * math.cos(math.radians(a0 + (a1 - a0) * i / n)), cy + ry * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


def teacup():
    """白瓷金边茶杯 + 托碟 (ED 茶会那桌: 白杯, 金口沿)."""
    W, H = 52, 36
    gold, white, shade, tea = (236, 196, 92), (250, 248, 244), (214, 210, 222), (176, 98, 46)
    saucer = _ellipse(26, 32, 25, 4)
    body = [(8, 9)] + [(26 + 18 * math.cos(math.radians(a)), 10 + 18 * math.sin(math.radians(a))) for a in range(0, 181, 12)][::-1][::-1]
    body = [(8, 10)] + [(26 - 18 * math.cos(math.radians(a)), 10 + 19 * math.sin(math.radians(a)) * 0.95) for a in range(0, 181, 10)] + [(44, 10)]
    handle_o = _ellipse(45, 18, 7, 6, 18, -90, 90)
    handle_i = _ellipse(45, 18, 3.6, 3, 18, 90, -90)
    rim = _ellipse(26, 10, 18, 3.6)
    tea_s = _ellipse(26, 10.6, 15.5, 2.6)
    shade_p = [(9, 11)] + [(26 - 17 * math.cos(math.radians(a)), 11 + 16 * math.sin(math.radians(a))) for a in range(0, 91, 10)] + [(22, 20)]
    band = [(12, 19), (40, 19), (39, 21.5), (13, 21.5)]
    return Art(W, H, [(shade, _pts(saucer)), (gold, _pts(_ellipse(26, 31, 22, 2.6))), (white, _pts(body)),
                      (white, _pts(handle_o + handle_i)), (shade, _pts(shade_p)), (gold, _pts(band)),
                      (gold, _pts(rim)), (tea, _pts(tea_s))], '茶杯')


def wisp():
    """一缕热气: 细 S 形, 下粗上细."""
    pts_l, pts_r = [], []
    for i in range(13):
        u = i / 12
        y = 30 - 30 * u
        x = 6 + 4 * math.sin(u * math.pi * 1.6)
        w = 2.4 * (1 - u) + 0.4
        pts_l.append((x - w, y))
        pts_r.append((x + w, y))
    return Art(12, 30, [((255, 255, 255), _pts(pts_l + pts_r[::-1]))], '汽')


def petal(rgb=(206, 40, 62), dark=(150, 22, 44)):
    """一片蔷薇花瓣 (尼娅发饰的红蔷薇)."""
    out = [(7 + 7 * math.sin(math.radians(a)) * (1 - 0.35 * math.cos(math.radians(a))), 9 - 9 * math.cos(math.radians(a))) for a in range(0, 361, 15)]
    inner = [(7 + 3 * math.sin(math.radians(a)), 12 - 5 * math.cos(math.radians(a))) for a in range(0, 361, 30)]
    return Art(14, 18, [(rgb, _pts(out)), (dark, _pts(inner))], '瓣')


def heart(rgb=(244, 120, 160)):
    pts = []
    for i in range(41):
        t = math.pi * 2 * i / 40
        x = 16 * math.sin(t) ** 3
        y = -(13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t))
        pts.append((x * 0.55 + 9, y * 0.55 + 9))
    hi = [(5 + 1.8 * math.cos(math.radians(a)), 6 + 1.2 * math.sin(math.radians(a))) for a in range(0, 361, 30)]
    return Art(18, 18, [(rgb, _pts(pts)), ((255, 236, 244), _pts(hi))], '心')


def star(rgb=(255, 236, 150)):
    pts = []
    for i in range(8):
        r = 8 if i % 2 == 0 else 2.2
        a = math.radians(i * 45 - 90)
        pts.append((8 + r * math.cos(a), 8 + r * math.sin(a)))
    return Art(16, 16, [(rgb, _pts(pts))], '星')


def poppy(rgb=(250, 176, 40)):
    """花冠上的小黄花 (ED 花田那场, 蕾莉亚的花冠)."""
    pts = []
    for i in range(61):
        a = math.radians(i * 6)
        r = 7 + 1.6 * math.cos(5 * a)
        pts.append((9 + r * math.cos(a), 9 + r * math.sin(a)))
    c = _ellipse(9, 9, 2.4, 2.4, 12)
    return Art(18, 18, [(rgb, _pts(pts)), ((236, 110, 30), _pts(c))], '花')


def cloud(w=60, h=22):
    """一团云 (ED 天空鲸那场的积云): 几个圆鼓包 + 平底."""
    bumps = [(0.18, 0.62, 0.2), (0.38, 0.42, 0.28), (0.62, 0.45, 0.26), (0.82, 0.62, 0.2)]
    layers = []
    for col, dy in (((214, 228, 246), 1.5), ((255, 255, 255), 0)):
        d = []
        for bx, by, br in bumps:
            d.append(_pts(_ellipse(bx * w, by * h + dy, min(br * w, bx * w, (1 - bx) * w), min(br * w * 0.9, by * h), 20)))
        d.append(_pts([(0.1 * w, 0.62 * h + dy), (0.9 * w, 0.62 * h + dy), (0.92 * w, h * 0.98 + dy * 0), (0.08 * w, h * 0.98)]))
        layers.append((col, ' '.join(d)))
    return Art(w, h, layers, '云')


def rec():
    """取景框右边的红色录制灯 (ED 开头/结尾那几句, 画面套在魔晶板取景框里, 右侧一颗红灯)."""
    glow = _ellipse(14, 14, 14, 14, 28)
    dot = _ellipse(14, 14, 8, 8, 24)
    hi = _ellipse(11.5, 11, 2.6, 2, 12)
    return Art(28, 28, [((150, 20, 30), _pts(glow)), ((236, 40, 48), _pts(dot)), ((255, 190, 190), _pts(hi))], '录')


def ruler():
    """取景框左边的刻度尺 (ED: 竖排刻度, 1.7 / 2.4)."""
    d = [_pts([(10, 0), (12, 0), (12, 70), (10, 70)])]
    for i in range(8):
        y = 2 + i * 9.5
        L = 9 if i % 4 == 0 else 5
        d.append(_pts([(10 - L, y), (10, y), (10, y + 1.6), (10 - L, y + 1.6)]))
    return Art(14, 72, [((236, 232, 226), ' '.join(d))], '尺')


DRAWN = {'录': rec, '尺': ruler, '云': cloud, '茶杯': teacup, '汽': wisp, '瓣': petal, '心': heart, '星': star, '花': poppy}


def get(name, proj=None, tint=None):
    """art by name: the project's traced art/<name>.json first, then the drawn props."""
    if proj:
        p = os.path.join(proj, 'art', name + '.json')
        if os.path.exists(p):
            d = json.load(open(p, encoding='utf-8'))
            return Art(d['w'], d['h'], [(tuple(c), s) for c, s in d['layers']], name)
    if name not in DRAWN:
        raise KeyError(name)
    return DRAWN[name](tint) if tint is not None and name in ('瓣', '心', '星', '花') else DRAWN[name]()


def trace(png, out, H=120, colors=10, speckle=10):
    """cut-out PNG -> colour layers (vtracer), scaled so the art is H px tall. Keeps big layers first (stacked)."""
    import vtracer
    from PIL import Image
    from svgelements import SVG, Path, Move, Line, Close, CubicBezier, QuadraticBezier
    im = Image.open(png).convert('RGBA')
    im = im.crop(im.getbbox())
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    tmp_png, tmp_svg = out + '.tmp.png', out + '.tmp.svg'
    # work at ~3x the final size: finer than that is invisible on screen and only multiplies layers (= events).
    # colours are first cut to `colors` (median cut) so one flat colour region -> one layer; alpha is made hard.
    s = min(1.0, H * 3 / im.height)
    im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)
    a = im.getchannel('A').point(lambda v: 255 if v > 110 else 0)
    q = im.convert('RGB').quantize(colors, method=Image.Quantize.MEDIANCUT).convert('RGBA')
    q.putalpha(a)
    q.save(tmp_png)
    vtracer.convert_image_to_svg_py(tmp_png, tmp_svg, colormode='color', hierarchical='stacked', mode='spline',
                                    filter_speckle=speckle, color_precision=8, layer_difference=4,
                                    corner_threshold=60, length_threshold=4.0, splice_threshold=45, path_precision=2)
    doc = SVG.parse(tmp_svg)
    k = H / float(doc.height)
    layers = []
    for e in doc.elements():
        if not isinstance(e, Path) or e.fill is None or e.fill.value is None or (e.fill.alpha is not None and e.fill.alpha < 128):
            continue
        d = []
        for sg in e:
            if isinstance(sg, Move):
                d.append(f'm {sg.end.x * k:.2f} {sg.end.y * k:.2f}')
            elif isinstance(sg, (Line, Close)) and sg.end is not None:
                d.append(f'l {sg.end.x * k:.2f} {sg.end.y * k:.2f}')
            elif isinstance(sg, CubicBezier):
                d.append(f'b {sg.control1.x * k:.2f} {sg.control1.y * k:.2f} {sg.control2.x * k:.2f} {sg.control2.y * k:.2f} {sg.end.x * k:.2f} {sg.end.y * k:.2f}')
            elif isinstance(sg, QuadraticBezier):
                c1 = sg.start + (sg.control - sg.start) * 2 / 3
                c2 = sg.end + (sg.control - sg.end) * 2 / 3
                d.append(f'b {c1.x * k:.2f} {c1.y * k:.2f} {c2.x * k:.2f} {c2.y * k:.2f} {sg.end.x * k:.2f} {sg.end.y * k:.2f}')
        if d:
            layers.append(([e.fill.red, e.fill.green, e.fill.blue], ' '.join(d)))
    json.dump(dict(w=round(doc.width * k, 1), h=H, layers=layers, src=os.path.basename(png)), open(out, 'w', encoding='utf-8'))
    for f in (tmp_png, tmp_svg):
        os.remove(f)
    print(f'{out}: {len(layers)} layers, {doc.width * k:.0f}x{H}')


def scenes(proj, video='base.mp4', cols=8, w=320):
    """物象从画面来: 每一行歌词唱到一半时的那一帧, 排成一张图 (review/scenes.jpg), 帧上标行号和秒数.
    先看这张图再挑物象: 一样东西只放在画面里正出现它、或歌词点名它的那几行 (用户 2026-11-23: 茶杯 "只是过路的",
    不是番剧的氛围; 同一个东西反复出现 "太重复了")."""
    import subprocess, tempfile
    m = json.load(open(os.path.join(proj, 'out.kfx.manifest.json'), encoding='utf-8'))
    tmp = tempfile.mkdtemp()
    font = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'fonts')
    ff = next((os.path.join(font, f) for f in sorted(os.listdir(font)) if f.lower().endswith(('.ttf', '.otf'))), None) if os.path.isdir(font) else None
    for k, u in enumerate(m['units']):
        t = (u['t'][0] + u['t'][1]) / 2
        lab = f"{u['name']} {t:.0f}s"
        dt = f",drawtext=text='{lab}':x=6:y=6:fontsize=26:fontcolor=white:box=1:boxcolor=black@0.6" + (f":fontfile='{ff}'" if ff else '')
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{t:.2f}', '-i', os.path.join(proj, video), '-frames:v', '1',
                        '-vf', f'scale={w}:-2{dt}', os.path.join(tmp, f'{k:03d}.png')], check=True)
    n = len(m['units'])
    rows = (n + cols - 1) // cols
    out = os.path.join(proj, 'review', 'scenes.jpg')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', os.path.join(tmp, '%03d.png'), '-vf', f'tile={cols}x{rows}', '-frames:v', '1', '-q:v', '4', out], check=True)
    print(out, n, 'lines')


if __name__ == '__main__':
    import sys
    a = sys.argv[1:]
    if a and a[0] == 'scenes':
        scenes(a[1])
    elif a and a[0] == 'trace':
        H = int(a[a.index('--h') + 1]) if '--h' in a else 120
        C = int(a[a.index('--colors') + 1]) if '--colors' in a else 6
        trace(a[1], a[2], H, C)
    else:
        print(__doc__)
