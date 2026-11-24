"""kfx verbs: the verb table (design word -> function), line exits. Verb bodies live in kfx_verbs_cut / kfx_verbs_body."""
import math, random
from kfx_core import kf, ev, bgr, mix, WHITE, BLACK, hexrgb
from kfx_draw import *
from kfx_draw import _shift
from kfx_hit import *
from kfx_glyph import hp_poly
from kfx_core import Track
from kfx_verbs_cut import *
from kfx_verbs_body import *
from kfx_verbs_stage import *
from kfx_verbs_pop import POP_VERBS
from kfx_verbs_gc import GC_VERBS
from kfx_draw import Ctx
from kfx_motif import V_burst

VERBS = {
    '斩': V_cut, '大斩': V_bigcut, '撕': V_tear, '裂': V_crack, '顿': V_jolt, '亮': V_highlight, '盖': V_cover,
    '擦': V_erase, '缚': V_bind, '抱': V_embrace, '护': V_ward, '伸': V_reach, '落': V_fall, '溢': V_overflow,
    '飘': V_drift, '照': V_glow, '余韵': V_echo, '踮': V_tiptoe, '跳': V_dance, '星': V_star,
    '推': V_shove, '拉': V_pull, '压': V_press, '弹': V_bounce, '坠': V_drop, '起': V_lift, '握': V_grip, '刺': V_pierce,
    '敲': V_knock, '吹': V_blow, '冻': V_freeze, '融': V_melt, '心跳': V_heart, '倾': V_tilt, '拂': V_sweep, '牵': V_link,
    '印': V_stamp,
    '蹦': V_hop, '拳': V_punch, '礼': V_curtsy, '碰': V_clink, '映': V_tune, '猜拳': V_janken, '齐舞': V_chorus, '迸': V_burst,
    **POP_VERBS, **GC_VERBS,
}
ATMOS = {'照', '星', '飘', '迸'}
WEAK = ATMOS | {'亮'}           # do not count toward the per-line minimum          # no subject: never the only thing on a line

# ---------------------------------------------------------------- exits (five)

def exit_line(line, kind, rnd):
    n = len(line.glyphs)
    for k, g in enumerate(line.glyphs):
        t0, t1 = g.t_out, g.t_end
        if kind == '升':
            g.tracks.append(kf((t0, {}), (t1, dict(dy=-26, sy=0.25, sx=-0.1, am=-1, bl=3))))
        elif kind == '沉':
            g.tracks.append(kf((t0, {}), (t1, dict(dy=22, sy=-0.35, sx=0.1, am=-1, bl=2))))
        elif kind == '散':
            ang = rnd.uniform(0, 2 * math.pi)
            g.tracks.append(kf((t0, {}), (t1, dict(dx=math.cos(ang) * 30, dy=math.sin(ang) * 18, am=-1, bl=5, sx=0.2, sy=0.2))))
        elif kind == '碎':
            if not g.pieces:
                up, lo = cut_planes(rnd.uniform(-15, 15), 0)
                g.pieces = [piece(t0, [up], [], ruby_planes=[up]), piece(t0, [lo], [])]
            for j, pc in enumerate(g.pieces):
                s = -1 if j % 2 == 0 else 1
                pc['trs'].append(kf((t0, {}), (t1, dict(dx=s * rnd.uniform(8, 18), dy=rnd.uniform(-10, 30), rz=s * rnd.uniform(6, 18)))))
            g.tracks.append(kf((t0, {}), (t1, dict(am=-1, bl=1.5))))
        elif kind == '化':
            g.tracks.append(kf((t0, {}), (t1, dict(sx=0.35, sy=0.35, am=-1, bl=8))))
        else:
            g.tracks.append(kf((t0, {}), (t1, dict(am=-1))))


EXITS = {'升', '沉', '散', '碎', '化'}


if __name__ == '__main__':
    import sys
    if '--list' in sys.argv:
        for k, f in VERBS.items():
            print(f'{k}\t' + ' '.join((f.__doc__ or '').split()))
        print('出场\t' + ' '.join(sorted(EXITS)))
