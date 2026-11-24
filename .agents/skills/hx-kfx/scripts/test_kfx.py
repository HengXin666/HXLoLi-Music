"""hx-kfx v2 smoke tests (stdlib unittest; run in scripts/: python -m unittest test_kfx -v)."""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import kfx_build as build
import kfx_check as check

REPO = Path(__file__).resolve().parents[4]
FONTS = REPO / "static/music/无职转生/fonts"
EXAMPLE = REPO / ".agents/skills/hx-kfx/assets/mushoku-only.direction.kfx.json"

LYRICS = """# test
00:01.000 | [愛|あい]のイロハ | 爱的入门
00:03.000 | {(If you do)|いふ} [貴方|あなた]だけ？ | 唯有你？
00:05.000 | [壊|こわ]したい | 想要破坏
"""


def _timing():
    rows = []
    spec = [[["あ", "い"], ["の"], ["い"], ["ろ"], ["は"]],
            [["い", "ふ"], ["あ", "な", "た"], ["だ"], ["け"]],
            [["こ", "わ"], ["し"], ["た"], ["い"]]]
    t = 1.0
    for li, units in enumerate(spec):
        for ui, morae in enumerate(units):
            for mi, m in enumerate(morae):
                rows.append(dict(line=li, unit=ui, mora=mi, text=m, s=round(t, 3), e=round(t + 0.25, 3)))
                t += 0.25
        t += 0.2
    return rows


def _project(td: Path) -> Path:
    p = td / "proj"
    p.mkdir()
    (p / "lyrics.txt").write_text(LYRICS, encoding="utf-8")
    (p / "timing.json").write_text(json.dumps(_timing(), ensure_ascii=False), encoding="utf-8")
    d = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    for f in d["fonts"].values():
        f["file"] = str(FONTS / Path(f["file"]).name)
    d.pop("title_card", None)
    d.pop("final_hold", None)
    secs = d["sections"]
    keep = [dict(secs[0], lines=[0, 0]), dict(secs[1], lines=[1, 1]), dict(secs[3], lines=[2, 2])]
    d["sections"] = keep
    d["moments"] = [dict(line=1, kind="red_thread", why="t"), dict(line=1, kind="tilt", units=[3], why="t"),
                    dict(line=2, kind="cracks", units=[0], why="t")]
    (p / "direction.kfx.json").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    return p


class KfxTest(unittest.TestCase):
    def setUp(self):
        self.td = Path(tempfile.mkdtemp())
        self.p = _project(self.td)

    def tearDown(self):
        shutil.rmtree(self.td)

    def test_build_is_reproducible_and_passes_gates(self):
        """the gates G1-G5 must hold on any project the engine builds,
        and the same inputs must give byte-identical output."""
        self.assertEqual(build.main([str(self.p)]), 0)
        a = (self.p / "out.kfx.ass").read_bytes()
        self.assertEqual(build.main([str(self.p)]), 0)
        self.assertEqual(a, (self.p / "out.kfx.ass").read_bytes())
        for name, ok, msg in check.gates(self.p, self.p / "out.kfx.ass", self.p / "direction.kfx.json"):
            self.assertTrue(ok, f"{name}: {msg}")
        text = a.decode("utf-8-sig")
        self.assertIn("唯有", text)
        self.assertIn(",RB,", text)
        man = json.loads((self.p / "out.kfx.manifest.json").read_text(encoding="utf-8"))
        self.assertEqual([u["cn"] for u in man["units"]], ["爱的入门", "唯有你？", "想要破坏"])

    def test_bad_direction_is_rejected(self):
        d = json.loads((self.p / "direction.kfx.json").read_text(encoding="utf-8"))
        d["sections"][0]["palette"]["base"] = "#303030"   # unsung text too dark
        del d["sections"][1]["why"]
        (self.p / "direction.kfx.json").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        self.assertEqual(build.main([str(self.p)]), 2)

    def test_unit_mismatch_is_rejected(self):
        (self.p / "lyrics.txt").write_text(LYRICS.replace("[壊|こわ]したい", "[壊|こわ]したいな"), encoding="utf-8")
        with self.assertRaises(SystemExit):
            build.build(self.p, self.p / "direction.kfx.json", self.p / "out.kfx.ass")


if __name__ == "__main__":
    unittest.main()
