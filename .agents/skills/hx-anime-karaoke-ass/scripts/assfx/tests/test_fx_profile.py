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
OUT = os.path.join(ROOT, 'dev/无职转生/オンリー/out.ass')
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

    def test_input_error(self):
        self.assertEqual(cfp.main(['/nonexistent.ass', '--ref', '/nonexistent.ass']), 2)


@unittest.skipUnless(all(map(os.path.exists, (REF, OUT, YOSUGA))), '缺工程文件')
class Real(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ref = cfp.load(REF)

    def test_ref_ok(self):
        self.assertEqual(cfp.main([REF, '--ref', REF]), 0)

    def test_out_bad_9(self):
        res = run(cfp.load(OUT), self.ref)
        self.assertEqual(bad(res), [1, 2, 3, 4, 5, 6, 7, 9, 10])
        self.assertEqual(cfp.main([OUT, '--ref', REF]), 1)

    def test_drop30_bad(self):
        self.assertIn(1, bad(run(mutate_fx(self.ref, drop30), self.ref)))

    def test_layer0_bad(self):
        self.assertIn(6, bad(run(mutate_fx(self.ref, layer0), self.ref)))

    def test_yosuga_self_ok(self):
        self.assertEqual(cfp.main([YOSUGA, '--ref', YOSUGA]), 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
