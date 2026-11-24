"""组合式生成 / 形状来源 / 母题来源门禁 / 指纹 的自测. 跑法 (skill 根目录): PYTHONPATH=scripts python3 -m unittest scripts/assfx/tests/test_compose.py -v
反例全在测试里现场构造, 不新增 fixture 文件, 不依赖 dev/ (硬规则 10)."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.abspath(os.path.join(HERE, "..", ".."))
SKILL = os.path.dirname(SCRIPTS)
EX = os.path.join(SKILL, "examples", "mushoku_ed1")
FONTS = os.environ.get("ASSFX_FONTS") or os.path.join(SKILL, "fonts")
sys.path.insert(0, SCRIPTS)

from assfx.layer import ir as IR  # noqa: E402
from assfx.layer import provenance as PV  # noqa: E402
from gate.check_motif_mono import check  # noqa: E402


def _ir(**kw):
    d = {"format": "assfx-ir", "version": 1, "song": "t", "motifs": {
        "a": {"shape": "kit:circle", "role": "main", "grammar": "halo"},
        "b": {"shape": "kit:sparkle", "role": "main", "grammar": "rise"},
        "x": {"shape": "kit:sparkle", "role": "aux", "grammar": "scatter"}},
        "phrases": [{"i": 0, "role": "carrier", "main": "a", "aux": ["x"]}]}
    d.update(kw)
    return d


# Agent Notes: 组合式生成: 设计中间表示 + 形状来源 + 母题来源门禁 + 跨作品指纹
# 
def _gen(ir_path, out):
    """Agent Notes
    .agents/notes/implemented/architecture/2026-11-17-karaoke-compositional-generator.md
    在示例目录的临时副本里跑生成器 (示例本身不动), 返回退出码."""
    env = dict(os.environ, PYTHONPATH=SCRIPTS, ASSFX_FONTS=FONTS)
    return subprocess.run([sys.executable, os.path.join(os.path.dirname(ir_path), "make_ass.py"), out], env=env,
                          cwd=os.path.dirname(ir_path), capture_output=True, text=True)


class TestIR(unittest.TestCase):
    def test_ok(self):
        self.assertEqual(IR.validate(_ir()), [])

    def test_aux_is_main(self):
        d = _ir(); d["phrases"][0]["aux"] = ["b"]
        self.assertTrue(any("一句两套主母题" in e for e in IR.validate(d)))

    def test_typo_key_and_missing_main(self):
        d = _ir(); d["phrases"][0]["mian"] = "a"; d["phrases"][0].pop("main")
        e = IR.validate(d)
        self.assertTrue(any("多余键 mian" in x for x in e) and any("没有主母题" in x for x in e))

    def test_example_ir(self):
        IR.load(os.path.join(EX, "design.ir.json"))


class TestMono(unittest.TestCase):
    def _doc(self, mains, declared="chain"):
        return {"units": [{"key": "k", "i": 29, "declared": declared, "main": mains, "aux": [], "src": {}}]}

    def test_two_mains_fail(self):
        """反例 (known-gaps #14 原样): 旧剑斩函数没删, 新铁链挂在后面."""
        PV.LOG.clear(); PV.begin("k")
        sword = PV.main_motif("sword")(lambda: None); chain = PV.main_motif("chain")(lambda: None)
        sword(); chain(); PV.end()
        r = check({"units": [dict(key="k", i=29, declared="chain", **PV.LOG["k"])]})
        self.assertTrue(any(x[0] == "FAIL" and "2 套主母题" in x[2] for x in r), r)

    def test_declared_mismatch_fail(self):
        self.assertTrue(any(x[0] == "FAIL" for x in check(self._doc(["sword"]))))

    def test_one_main_ok(self):
        self.assertEqual([x for x in check(self._doc(["chain"])) if x[0] == "FAIL"], [])


class TestExampleGenerator(unittest.TestCase):
    """正例: 示例 33 句 0 FAIL; 反例: 把第 29 句的逃生口换成 "旧剑斩 + 铁链" 版本, 门禁必须报."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.ex = os.path.join(self.tmp, "ex")
        shutil.copytree(EX, self.ex, ignore=shutil.ignore_patterns("out", "assets", "__pycache__", "*.ass", "*.json.bak"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_positive_and_negative(self):
        out = os.path.join(self.tmp, "pos.ass")
        r = _gen(os.path.join(self.ex, "design.ir.json"), out)
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        doc = json.load(open(os.path.splitext(out)[0] + ".motifs.json", encoding="utf-8"))
        ir = json.load(open(os.path.join(self.ex, "design.ir.json"), encoding="utf-8"))
        self.assertEqual([x for x in check(doc, ir) if x[0] == "FAIL"], [])
        with open(os.path.join(self.ex, "neg_sword.py"), "w", encoding="utf-8") as fh:
            fh.write("from assfx.layer.provenance import main_motif\nimport fx_main\n\n\n"
                     "@main_motif('sword')\ndef old_sword(f, ph, k):\n    pass\n\n\n"
                     "def fx_sword_cut(f, ph, k):\n    old_sword(f, ph, k)\n    fx_main.p29(f, ph, k)\n")
        for p in ir["phrases"]:
            if p["i"] == 29:
                p["escape"], p["main"] = "neg_sword:fx_sword_cut", "chain"
        json.dump(ir, open(os.path.join(self.ex, "design.ir.json"), "w", encoding="utf-8"), ensure_ascii=False)
        out = os.path.join(self.tmp, "neg.ass")
        r = _gen(os.path.join(self.ex, "design.ir.json"), out)
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        doc = json.load(open(os.path.splitext(out)[0] + ".motifs.json", encoding="utf-8"))
        bad = [x for x in check(doc, ir) if x[0] == "FAIL"]
        self.assertEqual(len(bad), 1, bad)
        self.assertIn("L29", bad[0][1])


class TestSources(unittest.TestCase):
    def test_glyph_exact(self):
        from assfx.draw.glyph import glyph_path
        f = os.path.join(FONTS, "ShipporiMinchoB1-Bold.ttf")
        if not os.path.exists(f):
            self.skipTest("字体未取 (setup/fetch_fonts.py)")
        d, w, h = glyph_path(f, "雪", 80)
        self.assertTrue(d.startswith("m ") and " b " in d)
        self.assertAlmostEqual(h, 80, places=3)

    def test_resolve_prefix(self):
        from assfx.draw.resolve import shape_fn
        self.assertTrue(shape_fn("kit:star:6,0.4")(20).startswith("m"))
        with self.assertRaises(ValueError):
            shape_fn("snowflake")

    def test_frames(self):
        from PIL import Image
        from assfx.draw import frames
        with tempfile.TemporaryDirectory() as d:
            Image.new("RGBA", (200, 100), (255, 0, 0, 255)).save(os.path.join(d, "o.png"))
            seq = frames.prescale(d, "o.png", 0.3, 1.0, 5)
            self.assertEqual([s[2] for s in seq], sorted(s[2] for s in seq))
            self.assertEqual(seq[-1][2:], (200, 100))
            with self.assertRaises(ValueError):
                frames.prescale(d, "o.png", out_dir=os.path.join(SKILL, "scripts", "x"))

            class F:
                evs = []

                def shape(self, *a, **kw):
                    self.evs.append(kw["extra"])
            f = F()
            self.assertEqual(frames.grow(f, 4, 0, 1, 3, 0, 0, seq), 5)
            self.assertFalse(any("\\fsc" in e for e in f.evs))

    def test_legible(self):
        from assfx.draw.legible import below_floor, audit
        self.assertIsNotNone(below_floor({"min_px": 140}, 76, 55))
        self.assertIsNone(below_floor({"min_px": 40}, 76, 55))
        self.assertEqual(audit({"h": {"file": "a.png", "kind": "figurative"}})[0][0], "W")


if __name__ == "__main__":
    unittest.main()
