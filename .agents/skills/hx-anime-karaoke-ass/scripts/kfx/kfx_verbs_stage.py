"""kfx verbs (3/3): stage verbs, first invented for ときめきアン・ドゥ・トロワ♪ (three girls skipping, counting
1・2・3, a curtsy, tea-table chat, the Magic Vision screen, Nia's fists, the ED's closing じゃんけん).
They only move the glyphs themselves; nothing is drawn beside them. Any later song may use them."""
from kfx_hit import add


def _beat(c):
    return c.P.get('beat', 0) or 0.5


def V_hop(c):
    """蹦: the word skips: each glyph does two quick hops (ぴょんぴょん) with a squash on each landing, one after another."""
    for k, g in enumerate(c.span):
        t = g.a + k * 0.04
        add(g, (t, {}), (t + 0.05, dict(sy=-0.1, sx=0.06)), (t + 0.15, dict(dy=-16, sy=0.06)), (t + 0.25, dict(sy=-0.08, sx=0.05)),
            (t + 0.33, dict(dy=-9)), (t + 0.42, dict(sy=-0.05)), (t + 0.5, {}))


def V_punch(c):
    """拳: I throw a punch with the word: each glyph winds back, shoots forward with a stretch, and the glyph right after
    the word takes the blow and is knocked aside."""
    for k, g in enumerate(c.span):
        a = g.a + k * 0.03
        add(g, (a - 0.1, {}), (a - 0.02, dict(dx=-7, sx=-0.08)), (a + 0.05, dict(dx=14, sx=0.2, sy=-0.06, bl=1.0)),
            (a + 0.16, dict(dx=3)), (a + 0.3, {}))
    gl = c.line.glyphs
    i = gl.index(c.span[-1]) + 1
    if i < len(gl):
        v, a = gl[i], c.span[-1].a + 0.05
        add(v, (a, {}), (a + 0.05, dict(dx=10, rz=6)), (a + 0.14, dict(dx=-3, rz=-2)), (a + 0.28, {}))


def V_curtsy(c):
    """礼: a young lady's curtsy: after it is sung each glyph sinks with bent knees, holds, and rises again."""
    for k, g in enumerate(c.span):
        t = g.b + k * 0.05
        add(g, (t, {}), (t + 0.22, dict(dy=9, sy=-0.14, sx=0.07)), (t + 0.42, dict(dy=9, sy=-0.14, sx=0.07)),
            (t + 0.62, dict(dy=-3, sy=0.03)), (t + 0.75, {}))


def V_clink(c):
    """碰: chatting over tea: neighbouring glyphs lean their heads together in pairs, touch, and spring apart."""
    sp = c.span
    pairs = [sp[i:i + 2] for i in range(0, len(sp), 2)]
    if len(pairs) > 1 and len(pairs[-1]) == 1:
        last = pairs.pop()
        pairs[-1] = pairs[-1] + last
    for pr in pairs:
        if len(pr) == 1:
            g = pr[0]
            add(g, (g.a, {}), (g.a + 0.1, dict(rz=8, dx=3)), (g.a + 0.3, {}))
            continue
        a = pr[-1].a
        for k, g in enumerate(pr):
            s = 1 if k < len(pr) / 2 else -1
            add(g, (a - 0.05, {}), (a + 0.08, dict(dx=6 * s, rz=8 * s)), (a + 0.14, dict(dx=4 * s, rz=5 * s)), (a + 0.32, {}))


def V_tune(c):
    """映: the Magic Vision screen switches on: each glyph collapses to a bright horizontal line and opens back to full size."""
    for k, g in enumerate(c.span):
        a = g.a + k * 0.03
        add(g, (a, {}), (a + 0.05, dict(sy=-0.85, sx=0.25, bl=1.0)), (a + 0.1, dict(sy=-0.85, sx=0.25)),
            (a + 0.22, dict(sy=0.1, sx=-0.05)), (a + 0.32, {}))
        g.glow = max(g.glow, 0.5)


def V_janken(c):
    """猜拳: じゃん・けん・ぽん: the word bobs down twice on the beat like a fist being shaken, and on the third beat pops out big."""
    bt = _beat(c)
    t0 = c.span[0].a
    end = min(g.t_out for g in c.span) - 0.05
    if t0 + bt * 3.2 > end:
        bt = max(0.12, (end - t0) / 3.2)
    for g in c.span:
        add(g, (t0, {}), (t0 + bt * 0.25, dict(dy=8, sy=-0.06)), (t0 + bt * 0.5, {}), (t0 + bt * 1.25, dict(dy=8, sy=-0.06)),
            (t0 + bt * 1.5, {}), (t0 + bt * 2.1, dict(dy=-6, sx=0.22, sy=0.22)), (t0 + bt * 2.6, dict(sx=0.1, sy=0.1)), (t0 + bt * 3.2, {}))


def V_chorus(c):
    """齐舞 (本曲主菜): the ED's 1・2・3 dance: the three girls side by side, paws at their cheeks, stepping left and right
    in time and kicking a heel back. Each counted glyph is one dancer: on its beat it hops and kicks (leans away), and the
    whole 1・2・3 group steps with it to the same side, alternating left / right like the chorus line in the ED.
    齐舞·亮相: on the 3 the whole group crouches, jumps together and lands in a pose: the counted glyphs come down bigger
    and stay leaning in the pose, dust at their feet, the landing bounces the rest of the line. On the last 亮相 of the
    line the dancers open their arms: the line spreads out from the middle (the ED's さぁ)."""
    from kfx_hit import dust
    gl = [g for g in c.line.glyphs if g.kind != 'space']
    marks = '・･!！?？、。'
    allc = [g for g in gl if g.ch not in marks]
    counts = [g for g in c.span if g.kind != 'space' and g.ch not in marks]

    def group_of(g):                                     # the 1・2・3！ cluster this glyph belongs to
        i = gl.index(g)
        a = i
        while a > 0 and gl[a - 1].ch not in '!！':
            a -= 1
        b = i
        while b + 1 < len(gl) and gl[b].ch not in '!！':
            b += 1
        return gl[a:b + 1]

    if '亮相' in c.args:
        G = counts[0]
        grp = group_of(G)
        t = G.a
        s = 1 if allc.index(G) % 2 == 0 else -1
        for h in grp:
            add(h, (t - 0.16, {}), (t - 0.03, dict(dy=6, sy=-0.16, sx=0.08)), (t + 0.13, dict(dy=-20, sy=0.08, sx=-0.04)),
                (t + 0.27, dict(dy=3, sy=-0.12, sx=0.1)), (t + 0.4, {}))
        for h in grp:
            if h.ch in marks and h.ch not in '!！':
                continue
            pose = dict(sx=0.22, sy=0.22, rz=s * 7, dx=s * 3)
            add(h, (t + 0.27, {}), (t + 0.36, dict(sx=0.4, sy=0.4, rz=s * 9)), (t + 0.5, pose), (h.t_out, pose))
        for h in grp:
            dust(c.line.fx, c.name, c.rnd, t + 0.27, h.x, h.y + h.size * 0.62, n=2, spread=24)
        for h in gl:                                     # the landing bounces the rest of the line
            if h in grp:
                continue
            add(h, (t + 0.27, {}), (t + 0.33, dict(dy=4, sy=-0.06)), (t + 0.45, dict(dy=-5)), (t + 0.58, {}))
        if G is allc[-1] or c.span[-1] is gl[-1]:          # arms open
            mid = (gl[0].x + gl[-1].x) / 2
            for h in gl:
                o = dict(dx=(h.x - mid) * 0.06)
                add(h, (t + 0.45, {}), (t + 0.7, o), (h.t_out, o))
        return
    for g in counts:
        k = allc.index(g)
        s = 1 if k % 2 == 0 else -1
        t = g.a
        for h in group_of(g):                            # the chorus line steps to one side together
            add(h, (t, {}), (t + 0.12, dict(dx=s * 7, rz=s * 3)), (t + 0.3, dict(dx=s * 2)), (t + 0.42, {}))
        add(g, (t - 0.04, dict(sy=-0.1, sx=0.06)), (t + 0.11, dict(dy=-15, rz=-s * 11, sy=0.12, sx=0.12)),
            (t + 0.24, dict(dy=2, sy=-0.12, sx=0.1, rz=-s * 3)), (t + 0.36, dict(sx=0.08, sy=0.08)), (g.t_out, dict(sx=0.08, sy=0.08)))
