"""kfx verbs: invented for 罪恶王冠 OP2 「The Everlasting Guilty Crown」 (EGOIST, 2026-11-24). Any later song may use them,
but they come from this show, so a song that is not about it should not.

    晶    the theme object (every line): a cluster of the Apocalypse Virus crystal stands at each end of the sentence
    虚空  the main course (胸の中にある x4): the Void is drawn out of the word, the King's power
    王冠  the title (支配, 罪): the guilty crown is drawn above the word and put on it
    差    いのり's red (差し色): one word in the blue world turns her red

Sources: the show (Lost Christmas: Tokyo overgrown with violet hexagonal crystals; Shu reaching into Inori's chest and
pulling out her Void, a crystal sword, in ribbons of light), the lyric 「真実はあなたの胸の中にある」, the official
header line "THE RIGHT TO USE MY FRIEND AS A WEAPON. THAT IS THE SINFUL CROWN I SHALL ADORN." (guilty-crown.jp).
All three are drawn where the glyphs really are (late callbacks, after every verb, the amplitude and the exit) and are
clipped to the box the user keeps (lyric box + 5 %). No flashing, no spinning, nothing drawn across a glyph."""
import math
from kfx_core import ev, bgr, mix, WHITE, BLACK, kf
from kfx_hit import add, poly_d, sparks, flash, shake_line, piece, has_pieces
from kfx_draw import ms
from kfx_verbs_pop import _at, _box, _late, _clip, _real

VIOLET = (150, 96, 255)


def _bars(c, t0, t1):
    """bar heads (tracked beat grid, beats.json) inside [t0, t1)."""
    b = c.P.get('beats') or []
    b0 = c.P.get('bar0', 0)
    return [t for k, t in enumerate(b) if (k - b0) % 4 == 0 and t0 <= t < t1]


def _beat_after(c, t, min_gap=0.0):
    for x in c.P.get('beats') or []:
        if x >= t + min_gap:
            return x
    return t + min_gap + (c.P.get('beat', 0) or 0.35)


def _roof(c, g):
    """the highest y anything may reach above this line: the user's crop keeps the lyric box (ruby top) + 54 px
    (kfx_check K2); P['box'] is looser at the top, so set pieces that rise above the rubies use this instead."""
    rb = min((r.oy for r in g.rubies), default=-g.size * 0.5 - 30)
    return g.y + rb - 22 - 40


def _crystal(w, h):
    """one hexagonal prism seen from the side, base at the bottom: (silhouette, ridge highlight). Local coords, top-left 0,0."""
    sil = [(w / 2, 0), (w, h * 0.22), (w, h), (0, h), (0, h * 0.22)]
    ridge = [(w / 2, 1.5), (w * 0.6, h * 0.24), (w * 0.6, h - 1), (w * 0.5, h - 1), (w * 0.5, h * 0.24)]
    return sil, ridge


# Agent Notes: 罪恶王冠 的 4 个动作 (晶 虚空 王冠 差) 出自这部番; 上沿守 K2 (注音上方 40 px), 只画在缝里/句子两端/注音之上
# .agents/notes/implemented/feature/2026-11-24-kfx-guilty-crown-verbs.md
def V_crystal(c):
    """晶 (主题物件, 每句都有): 这一句的两枚书挡. 句子两端各立一簇结晶 = アポカリプスウイルス (失落的圣诞之后东京长满的
    紫色六棱晶, 这部番的病根). 开唱前一拍从句子两端的基线长出: 主晶先, 两枚小晶接着 (级联, ease-out); 唱的时候每个小节头
    晶体亮一下再回落 (卡点, 不闪); 行出场那一刻结晶碎成几片落下淡出 (崩壊). 晶体只在句子两端, 不碰字, 不在画面里飘.
    放在这一行第一个补丁上即可 (作用于整行)."""
    L = c.line
    if getattr(L, 'crystal', False):
        return
    L.crystal = True
    gl = _real(L.glyphs)

    def late():
        ta = min(g.a for g in gl)
        tb = max(g.b for g in gl)
        bt = c.P.get('beat', 0) or 0.69
        x0, x1, y, h = _box(gl, (ta + tb) / 2)
        size = max(g.size for g in gl)
        base = y + size * 0.44
        to, te = min(g.t_out for g in gl), L.t_end
        tg = max(L.t_in, ta - bt)
        fill = mix(c.col, VIOLET, 0.45)
        hi = mix(fill, WHITE, 0.62)
        dark = mix(fill, BLACK, 0.55)
        cl = _clip(c)
        bars = _bars(c, ta, to)
        for side in (-1, 1):
            ex = x0 - 26 if side < 0 else x1 + 26
            parts = ((0.0, 1.0, 0.0), (side * size * 0.2, 0.62, side * 17), (-side * size * 0.17, 0.46, -side * 12))
            for k, (dx, sc, ang) in enumerate(parts):
                w, hh = size * 0.27 * (0.85 + 0.15 * sc), size * 1.08 * sc
                bx = ex + side * w * 0.4 + dx
                sil, ridge = _crystal(w, hh)
                g0 = ms(tg - tg + 0.07 * k)
                g1 = g0 + 300
                grow = f"\\fscy0\\t({g0},{g1},0.55,\\fscy100)"
                life = to - tg
                pulse = ''
                for tb_ in bars:
                    p0 = ms(tb_ - tg)
                    pulse += f"\\t({p0},{p0+70},\\1c{bgr(hi)}\\alpha&H28&)\\t({p0+70},{p0+460},\\1c{bgr(fill)}\\alpha&H58&)"
                common = f"\\an2\\pos({bx:.1f},{base:.1f})\\frz{-ang:.1f}\\shad0{cl}"
                L.fx.append(ev(0, tg, to, 'FX', c.name, common + f"\\bord0\\1c{bgr(fill)}\\alpha&H58&\\blur0.8{grow}{pulse}\\p1",
                               poly_d(sil) + "{\\p0}"))
                L.fx.append(ev(0, tg, to, 'FX', c.name, common + f"\\bord1.6\\1a&HFF&\\3c{bgr(hi)}\\3a&H30&\\blur0.6{grow}\\p1",
                               poly_d(sil) + "{\\p0}"))
                L.fx.append(ev(0, tg, to, 'FX', c.name, common + f"\\bord0\\1c{bgr(mix(hi, WHITE, .5))}\\alpha&H50&\\blur0.4{grow}\\p1",
                               poly_d(ridge) + "{\\p0}"))
                # 碎: the crystal splits in three and the shards drop with the line's exit
                dur = max(0.2, te - to)
                for j in range(3):
                    y0, y1 = hh * j / 3, hh * (j + 1) / 3
                    sh = [(0, y1), (w, y1), (w, y0 + 4), (w * 0.5, y0), (0, y0 + 4)]
                    cx = bx - w / 2
                    sy = base - hh
                    pts = [(cx + px, sy + py) for px, py in sh]
                    mx = sum(p[0] for p in pts) / len(pts)
                    my = sum(p[1] for p in pts) / len(pts)
                    loc = [(px - mx, py - my) for px, py in pts]
                    rot = side * c.rnd.uniform(25, 70)
                    fall = (side * c.rnd.uniform(8, 26), c.rnd.uniform(20, 46))
                    rz0 = -ang
                    L.fx.append(ev(0, to, to + dur, 'FX', c.name,
                                   f"\\an7\\move({mx:.1f},{my:.1f},{mx+fall[0]:.1f},{my+fall[1]:.1f})\\org({mx:.1f},{my:.1f})\\frz{rz0:.1f}"
                                   f"\\bord1\\shad0\\1c{bgr(fill)}\\3c{bgr(hi)}\\alpha&H58&\\blur0.6{cl}"
                                   f"\\t(0,{ms(dur)},0.7,\\frz{rz0+rot:.1f}\\alpha&HFF&)\\p1", poly_d(loc) + "{\\p0}"))
    _late(L, late)


def _sword(S, bw, col_blade, col_hilt):
    """the Void sword, hilt up, tip down, length S; local coords, top centre at (0, 0)."""
    gh = S * 0.24          # pommel + grip + guard
    pom = [(0, 0), (bw * 0.55, bw * 0.55), (0, bw * 1.1), (-bw * 0.55, bw * 0.55)]
    grip = [(-bw * 0.28, bw * 1.0), (bw * 0.28, bw * 1.0), (bw * 0.28, gh - bw * 0.7), (-bw * 0.28, gh - bw * 0.7)]
    gw = bw * 2.3
    guard = [(-gw, gh - bw * 0.9), (-bw * 0.5, gh - bw * 0.55), (bw * 0.5, gh - bw * 0.55), (gw, gh - bw * 0.9),
             (bw * 1.0, gh), (-bw * 1.0, gh)]
    blade = [(-bw, gh), (bw, gh), (bw, S - bw * 2.2), (0, S), (-bw, S - bw * 2.2)]
    ridge = [(-bw * 0.12, gh + 2), (bw * 0.12, gh + 2), (bw * 0.12, S - bw * 2.4), (0, S - bw * 0.8), (-bw * 0.12, S - bw * 2.4)]
    return [(blade, col_blade, '&H48&'), (ridge, mix(col_blade, WHITE, .8), '&H20&'), (guard, col_hilt, '&H10&'),
            (grip, mix(col_hilt, BLACK, .3), '&H10&'), (pom, col_hilt, '&H10&')]


def V_void(c):
    """虚空 (本曲主菜, 「胸の中にある」 x4): 从这个字里把 ヴォイド 拔出来 = 王の能力: 樱满集把手伸进祈的胸口, 在交错的光带里
    拉出一把结晶的剑. 唱到这个字时它从中间竖着分开 (两半连着注音各退半个剑宽, 两边的字一起让位, 字序不变), 缝里亮起;
    剑柄先、剑身后, 剑从缝里被拉出来升到字上方, 两条光带绕着它交错上升; 拉出的那一拍 (下一拍) 晶屑向上迸出, 整行一震.
    剑留在缝里直到行出场, 出场时碎成晶片. ·大 = 终段: 剑更长更宽, 光带更亮."""
    L = c.line
    g = _real(c.span)[0]
    if has_pieces(g):
        return
    big = '大' in c.args
    a = g.a
    bt = c.P.get('beat', 0) or 0.69
    t_full = _beat_after(c, a, 0.42)
    G = g.size * (0.62 if big else 0.52)         # each half steps aside this far: the gap is wide enough to hold the sword
    gl = _real(L.glyphs)
    hold = min(x.t_out for x in gl)
    # the split: left and right halves, each with its half of the ruby
    lp, rp = (1.0, 0.0, 0.0), (-1.0, 0.0, 0.0)          # keep n.p <= off: x <= 0 (left half) | x >= 0 (right half)
    open_ = lambda s: kf((a - 0.02, {}), (a + 0.1, dict(dx=s * G * 1.15, rz=s * 2.5)), (a + 0.3, dict(dx=s * G, rz=s * 1.5)),
                         (g.t_end, dict(dx=s * G, rz=s * 1.5)))
    g.pieces += [piece(a, [lp], [open_(-1)], ruby_planes=[lp]), piece(a, [rp], [open_(1)], ruby_planes=[rp])]
    g.dim.append((a, mix(c.col, WHITE, 0.5)))
    for o in gl:                                 # the rest of the line makes room, order kept
        if o is g:
            continue
        s = -1 if o.x < g.x else 1
        add(o, (a - 0.02, {}), (a + 0.14, dict(dx=s * G)), (o.t_end, dict(dx=s * G)))

    def late():
        x, y, sx, sy = _at(g, a + 0.4)
        box = c.P.get('box', (0, 0, 1920, 1080))
        roof = _roof(c, g)
        tip = y + g.size * 0.36
        top = max(roof + 6, y - g.size * 0.5 - (150 if big else 118))
        S = tip - top
        bw = G * 0.42
        blade = mix(mix(c.col, VIOLET, 0.3), WHITE, 0.4)
        hilt = mix(INORI, BLACK, 0.2)                # いのり's red on the hilt
        edge = mix(mix(c.col, VIOLET, .5), BLACK, 0.45)   # dark rim: the sword reads on a white picture too
        cl = f"\\clip({x-G*2.4:.0f},{roof:.0f},{x+G*2.4:.0f},{tip+1:.0f})"
        capped = f"\\clip({box[0]:.0f},{roof:.0f},{box[2]:.0f},{box[3]:.0f})"
        te = L.t_end
        dur_out = max(0.2, te - hold)
        # the slit glows in the gap
        sw = G * 0.55
        sh = g.size * 1.15
        slit = poly_d([(sw / 2, 0), (sw, sh * 0.3), (sw, sh * 0.7), (sw / 2, sh), (0, sh * 0.7), (0, sh * 0.3)])   # a lens of light, not a box
        L.fx.append(ev(0, a - 0.02, hold, 'FX', c.name,
                       f"\\an5\\pos({x:.1f},{y:.1f})\\bord0\\shad0\\1c{bgr(mix(c.col, WHITE, .6))}\\blur9\\alpha&HFF&\\fscx10"
                       f"\\t(0,140,\\fscx100\\alpha&H40&)\\t({ms(t_full-a)},{ms(t_full-a+0.4)},\\alpha&H90&){_clip(c)}\\p1", slit + "{\\p0}"))
        # the sword rises out of the slit, hilt first
        parts = _sword(S, bw, blade, hilt)
        rise0, rise1 = a + 0.06, t_full
        mv = f"\\an7\\move({x:.1f},{tip+2:.1f},{x:.1f},{top:.1f},0,{ms(rise1-rise0)})"
        # coloured glow behind the whole sword, then a dark rim, then the parts
        L.fx.append(ev(0, rise0, hold, 'FX', c.name, mv + f"\\bord{bw*0.9:.1f}\\shad0\\1c{bgr(c.col)}\\3c{bgr(c.col)}\\alpha&H70&\\blur{bw*0.8:.1f}{cl}\\p1",
                       ' '.join(poly_d(p) for p, _, _ in parts[:1] + parts[2:]) + "{\\p0}"))
        L.fx.append(ev(0, rise0, hold, 'FX', c.name, mv + f"\\bord2.2\\shad0\\1a&HFF&\\3c{bgr(edge)}\\blur0.6{cl}\\p1",
                       ' '.join(poly_d(p) for p, _, _ in parts[:1] + parts[2:]) + "{\\p0}"))
        for pts, col, al in parts:
            L.fx.append(ev(0, rise0, hold, 'FX', c.name,
                           f"\\an7\\move({x:.1f},{tip+2:.1f},{x:.1f},{top:.1f},0,{ms(rise1-rise0)})\\bord0\\shad0\\1c{bgr(col)}\\alpha{al}\\blur0.5{cl}\\p1",
                           poly_d(pts) + "{\\p0}"))
        L.fx.append(ev(0, rise0, hold, 'FX', c.name,
                       f"\\an7\\move({x:.1f},{tip+2:.1f},{x:.1f},{top:.1f},0,{ms(rise1-rise0)})\\bord1.4\\shad0\\1a&HFF&\\3c&HFFFFFF&\\3a&H40&\\blur0.8{cl}\\p1",
                       poly_d(parts[0][0]) + "{\\p0}"))
        # two ribbons of light twist up around it (inside the gap, never over a glyph)
        amp = G * 0.75
        for ph in (0.0, math.pi):
            n = 28
            ctr = [(x + amp * math.sin(ph + 5.0 * k / n * math.pi), tip - S * k / n) for k in range(n + 1)]
            w = 1.6 if not big else 2.2
            left = [(px - w, py) for px, py in ctr]
            right = [(px + w, py) for px, py in ctr][::-1]
            reveal = f"\\clip({x-G*2:.0f},{tip:.0f},{x+G*2:.0f},{tip+2:.0f})\\t(0,{ms(rise1-rise0)},\\clip({x-G*2:.0f},{top-4:.0f},{x+G*2:.0f},{tip+2:.0f}))"
            L.fx.append(ev(1, rise0, rise1 + 0.45, 'FX', c.name,
                           f"\\an7\\pos(0,0)\\bord0\\shad0\\1c{bgr(mix(c.col, WHITE, .75))}\\blur1.2\\alpha&H30&{reveal}"
                           f"\\t({ms(rise1-rise0)},{ms(rise1-rise0+0.45)},\\alpha&HFF&)\\p1", poly_d(left + right) + "{\\p0}"))
        # drawn out: crystal chips burst up from the hilt, the line is jolted
        n0 = len(L.fx)
        sparks(L.fx, c.name, c.rnd, t_full, (x, top + S * 0.18), (0, -1), mix(c.col, VIOLET, .3), n=12 if big else 9,
               spread=55, speed=(70, 150), life=0.5)
        flash(L.fx, c.name, t_full, (x, top + S * 0.24), (1, 0), mix(c.col, WHITE, .5), size=G * 3.2, life=0.18)
        for e in L.fx[n0:]:                      # chips fly up: keep them under the roof of the user's crop
            e['tx'] = e['tx'].replace('{', '{' + capped, 1)
        shake_line(L, t_full, x, (0, 1), amp=6 if big else 4.5, fall=500)
        # leaves with the line: the sword breaks into chips
        for k in range(5):
            yy = top + S * (k + 0.5) / 5
            pc = [(-bw, -S / 10), (bw, -S / 12), (bw * 0.7, S / 10), (-bw * 0.8, S / 11)]
            L.fx.append(ev(0, hold, hold + dur_out, 'FX', c.name,
                           f"\\an7\\move({x:.1f},{yy:.1f},{x+c.rnd.uniform(-30,30):.1f},{yy+c.rnd.uniform(20,60):.1f})\\org({x:.1f},{yy:.1f})"
                           f"\\bord1\\shad0\\1c{bgr(blade)}\\3c&HFFFFFF&\\alpha&H40&\\blur0.6{_clip(c)}"
                           f"\\t(0,{ms(dur_out)},\\frz{c.rnd.choice((-1,1))*c.rnd.uniform(30,90):.0f}\\alpha&HFF&)\\p1", poly_d(pc) + "{\\p0}"))
    _late(L, late)


def V_crown(c):
    """王冠: 罪の王冠 (题名, 官方题辞 "THE SINFUL CROWN I SHALL ADORN"). 唱这个词时, 词的注音上方用晶线画出一顶三尖的王冠
    (从左到右一笔画完, 在一拍里), 画成后王冠落下一点 "戴" 到词上, 词被压得一沉再回; 王冠留到行出场, 随行淡出.
    王冠在注音之上, 不碰字."""
    L = c.line
    span = _real(c.span)
    a = span[0].a
    bt = c.P.get('beat', 0) or 0.69
    t_on = _beat_after(c, a, 0.25)
    for g in span:
        add(g, (t_on - 0.02, {}), (t_on + 0.06, dict(dy=6, sy=-0.06)), (t_on + 0.3, {}))

    def late():
        x0, x1, y, h = _box(span, a + 0.2)
        cx = (x0 + x1) / 2
        size = max(g.size for g in span)
        W = min(max(x1 - x0, size * 1.4), size * 2.6)
        H = size * 0.8
        roof = min(_roof(c, g) for g in span)
        yb = max(roof + H + 4, y - size * 0.5 - 44)        # bottom of the crown: above the rubies, under the roof
        pts = [(-W / 2, 0), (-W / 2, -H * 0.7), (-W * 0.25, -H * 0.3), (0, -H), (W * 0.25, -H * 0.3), (W / 2, -H * 0.7), (W / 2, 0)]
        band = pts + [(W / 2, H * 0.16), (-W / 2, H * 0.16)]
        P = [(cx + px, yb + py) for px, py in band]
        hold = min(g.t_out for g in _real(L.glyphs))
        te = L.t_end
        col = (236, 196, 106)                       # gold, the only gold in the song: the crown itself
        draw = t_on - a
        rv = f"\\clip({cx-W/2-8:.0f},{yb-H-12:.0f},{cx-W/2-8:.0f},{yb+H:.0f})\\t(0,{ms(draw)},\\clip({cx-W/2-8:.0f},{yb-H-12:.0f},{cx+W/2+8:.0f},{yb+H:.0f}))"
        drop = f"\\t({ms(draw)},{ms(draw+0.1)},\\fscy96)"
        dark = mix(mix(c.col, VIOLET, .4), BLACK, 0.5)
        for tags in (f"\\bord5\\1c{bgr(c.col)}\\3c{bgr(c.col)}\\alpha&H80&\\blur6",      # glow
                     f"\\bord0\\1c{bgr(col)}\\alpha&H30&\\blur0.6",                          # body
                     f"\\bord2.4\\1a&HFF&\\3c{bgr(dark)}\\blur0.5",                           # dark rim: reads on white
                     f"\\bord1\\1a&HFF&\\3c{bgr(mix(col, WHITE, .7))}\\blur0.3"):
            L.fx.append(ev(6, a, te, 'FX', c.name,
                           f"\\an7\\move(0,-10,0,0,{ms(draw)},{ms(draw+0.08)})\\shad0{tags}{rv}{drop}"
                           f"\\t({ms(hold-a)},{ms(te-a)},\\alpha&HFF&){_clip(c)}\\p1", poly_d(P) + "{\\p0}"))
        # three gems on the points, lit one by one as the stroke reaches them
        for k, (px, py) in enumerate([pts[1], pts[3], pts[5]]):
            tk = a + draw * (k + 1) / 3.2
            gem = f"m 0 -9 l 7 0 0 9 -7 0"
            L.fx.append(ev(6, tk, te, 'FX', c.name,
                           f"\\an5\\pos({cx+px:.1f},{yb+py-4:.1f})\\bord0\\shad0\\1c{bgr(INORI)}\\bord1.2\\3c{bgr(mix(INORI, BLACK, .5))}\\blur0.4\\fscx40\\fscy40"
                           f"\\t(0,120,\\fscx100\\fscy100)\\t({ms(hold-tk)},{ms(te-tk)},\\alpha&HFF&){_clip(c)}\\p1", gem + "{\\p0}"))
    _late(L, late)


INORI = (232, 50, 74)


def V_accent(c):
    """差 (差し色): 楪いのり 的红. 荒木监督: 第 1 话开头整体是青色调, いのり 是唯一的差し色, 在青的世界里她的红要跳出来
    (guilty-crown.jp 访谈). 全曲的行色是冷青, 只有这个词唱到时变成 いのり 的红, 并轻轻抬起一点; 别的字不变.
    一首歌只给少数词 (她的歌, 心, 爱, 泪)."""
    for g in _real(c.span):
        g.tint = INORI
        add(g, (g.a - 0.02, {}), (g.a + 0.1, dict(dy=-5, sx=0.06, sy=0.06)), (g.a + 0.3, dict(dy=-2)), (g.t_out, dict(dy=-2)))


GC_VERBS = {'晶': V_crystal, '虚空': V_void, '王冠': V_crown, '差': V_accent}
