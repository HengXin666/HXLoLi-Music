"""check_fx_profile 测试. 跑法: python3 -m unittest <本文件> -v (仓库根目录下)."""
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import check_fx_profile as cfp  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, *(['..'] * 6)))
REF = os.path.join(ROOT, 'static/music/无职转生/大原ゆい子 - オンリー.ass')
YOSUGA = os.path.join(ROOT, 'static/music/ヨスガノソラ/eufonius - 比翼の羽根 (OP).ass')


# Agent Notes: 特效门禁自测
# .agents/notes/implemented/feature/2026-11-09-karaoke-fx-gate-studio.md
def run(text, ref_text, ratio=0.8):
    p = cfp.profile(text)
    return cfp.judge(p, cfp.thresholds(cfp.profile(ref_text), ratio))


def bad(res):
    return [r['no'] for r in res if r['state'] == 'BAD']


def mutate_fx(text, fn):
    out, i = [], 0
    for l in text.split('\n'):
        if l.startswith('Dialogue:') and l.split(',', 4)[3].strip() == 'FX':
            l = fn(i, l)
            i += 1
            if l is None:
                continue
        out.append(l)
    return '\n'.join(out)


def drop30(i, l):
    return None if i % 10 < 3 else l


def layer0(i, l):
    return re.sub(r'^Dialogue:\s*\d+', 'Dialogue: 0', l)


def sparse(text):
    """由入库参考构造的稀疏样本 (代替旧的 dev/.../out.ass 活文件依赖): FX 只留 1/8 且去掉逐帧件,
    全部压到第 0 层并换成同一种骨架, JP 去掉 \\frz/\\fax/\\frx. 期望除峰值外全部 BAD."""
    out, i = [], 0
    for l in text.split('\n'):
        if l.startswith('Dialogue:'):
            p = l.split(',', 9)
            st = p[3].strip()
            if st == 'FX':
                i += 1
                if i % 8 or cfp.ts(p[2]) - cfp.ts(p[1]) <= cfp.STEPPED_MAX:
                    continue
                p[0] = 'Dialogue: 0'
                p[9] = '{\\p1}m 0 0 l 8 0 8 8{\\p0}'
                l = ','.join(p)
            elif st == 'JP':
                for tg in ('frz', 'fax', 'frx'):
                    l = l.replace('\\' + tg, '\\fsp')
        out.append(l)
    return '\n'.join(out)


SYN = '\n'.join([
    'Dialogue: 2,0:00:01.00,0:00:03.00,JP,ly:p00,0,0,0,,あ',
    'Dialogue: 2,0:00:03.00,0:00:05.00,JP,ly:p01,0,0,0,,い',
    'Dialogue: 5,0:00:01.00,0:00:05.00,FX,fx:p00,0,0,0,,{\\p1}m 0 0 l 10 0 10 10{\\p0}',
    'Dialogue: 0,0:00:03.00,0:00:03.10,FX,fx:p01,0,0,0,,{\\p1}m 0 0 l 99 0{\\p0}',
])


class Synthetic(unittest.TestCase):
    def test_metrics(self):
        p = cfp.profile(SYN)
        self.assertEqual(p['fx_count'], 2)
        self.assertEqual(p['lines'], 2)
        self.assertEqual(p['per_line'], {'p00': 1, 'p01': 1})
        self.assertEqual(p['front'], 1)          # layer 5 > JP 主层 2
        self.assertEqual(p['stepped'], 1)
        self.assertEqual(p['skeletons'], 2)
        self.assertAlmostEqual(p['coverage'], 1.0)

    def test_self_ok(self):
        self.assertEqual(bad(run(SYN, SYN)), [])

    def test_peak_skipped_when_median_fails(self):
        ref = SYN
        thin = SYN.replace('fx:p00', 'fx:pXX')  # p00 掉到 0
        res = {r['no']: r['state'] for r in run(thin, ref)}
        self.assertEqual(res[8], 'SKIP')

    def test_cap_warn_only(self):
        # 第 11 项上限: 超过参考 x CAP_RATIO 报 WARN, 不进结论 (退出码仍 0)
        heavy = SYN + '\n' + '\n'.join(
            f'Dialogue: 5,0:00:01.00,0:00:05.00,FX,fx:p00,0,0,0,,{{\\p1}}m 0 0 l {i} 0 10 10{{\\p0}}' for i in range(4))
        p, ref = cfp.profile(heavy), cfp.profile(SYN)
        c = cfp.caps(p, ref)
        self.assertEqual([r['state'] for r in c], ['WARN'])
        self.assertEqual(cfp.caps(ref, ref)[0]['state'], 'OK')
        self.assertEqual(bad(cfp.judge(p, cfp.thresholds(ref, 0.8))), [])

    def test_input_error(self):
        self.assertEqual(cfp.main(['/nonexistent.ass', '--ref', '/nonexistent.ass']), 2)


@unittest.skipUnless(all(map(os.path.exists, (REF, YOSUGA))), '缺工程文件')
class Real(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ref = cfp.load(REF)

    def test_ref_ok(self):
        self.assertEqual(cfp.main([REF, '--ref', REF]), 0)

    def test_out_bad_9(self):
        res = run(sparse(self.ref), self.ref)
        self.assertEqual(bad(res), [1, 2, 3, 4, 5, 6, 7, 9, 10])
        self.assertEqual({r['no']: r['state'] for r in res}[8], 'SKIP')

    def test_drop30_bad(self):
        self.assertIn(1, bad(run(mutate_fx(self.ref, drop30), self.ref)))

    def test_layer0_bad(self):
        self.assertIn(6, bad(run(mutate_fx(self.ref, layer0), self.ref)))

    def test_yosuga_self_ok(self):
        self.assertEqual(cfp.main([YOSUGA, '--ref', YOSUGA]), 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
