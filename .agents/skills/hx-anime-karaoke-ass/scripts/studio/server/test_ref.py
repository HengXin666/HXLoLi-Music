# -*- coding: utf-8 -*-
"""refpick 单测: 临时目录造 static/music + playlist.json, 不碰仓库里的真实产物.
   python3 test_ref.py   (只用标准库 unittest)"""
import json, os, shutil, tempfile, unittest
import refpick as R

A, SONG = "番", "ろりこん"
OK = "ちぃむ - ろりこん.ass"        # playlist 发布的那份
US = "_ちぃむ - ろりこん.ass"       # "_" 前缀: 码点 95 排在假名前, 旧逻辑 sorted()[0] 会选它


class Ref(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.d = os.path.join(self.root, "static", "music", A)
        self.pdir = os.path.join(self.root, "dev", A, SONG)
        os.makedirs(self.d)
        os.makedirs(self.pdir)

    def tearDown(self):
        shutil.rmtree(self.root)

    def put(self, *names):
        for n in names:
            open(os.path.join(self.d, n), "w").write("Dialogue: x\n")

    def playlist(self, *urls):
        json.dump([dict(assUrl=u) for u in urls], open(os.path.join(self.root, "playlist.json"), "w"), ensure_ascii=False)

    def r(self):
        return R.resolve(self.root, A, SONG, self.pdir, "ass")

    def name(self, r):
        return os.path.basename(r["path"]) if r["path"] else None

    # ---- 修复证据 (旧 ref_ass 会失败)
    def test_playlist_beats_sort_order(self):
        self.put(US, OK)
        self.playlist("/static/music/%s/%s" % (A, OK))
        r = self.r()
        self.assertEqual((r["source"], self.name(r)), ("playlist", OK))

    def test_ambiguous_picks_nothing(self):
        self.put(US, OK)
        r = self.r()
        self.assertEqual((r["source"], r["path"]), ("ambiguous", None))
        self.assertIn("2 份候选", r["error"])
        self.assertEqual(len(r["candidates"]), 2)

    def test_playlist_outside_candidates_is_error(self):
        self.put(OK)
        os.makedirs(os.path.join(self.root, "static", "music", "别的"))
        open(os.path.join(self.root, "static", "music", "别的", OK), "w").write("")
        self.playlist("/static/music/别的/%s" % OK)
        r = self.r()
        self.assertEqual((r["source"], r["path"]), ("error", None))
        self.assertIn("跨目录", r["error"])

    def test_playlist_missing_file_is_error(self):
        self.put(OK)
        self.playlist("/static/music/%s/%s" % (A, "ろりこん v2.ass"))
        self.assertEqual(self.r()["source"], "error")

    def test_playlist_two_hits_is_ambiguous(self):
        self.put(US, OK)
        self.playlist("/static/music/%s/%s" % (A, OK), "/static/music/%s/%s" % (A, US))
        r = self.r()
        self.assertEqual((r["source"], r["path"]), ("ambiguous", None))

    def test_manual_wins_and_records_time(self):
        self.put(US, OK)
        self.playlist("/static/music/%s/%s" % (A, OK))
        R.choose(self.root, A, SONG, self.pdir, "ass", "static/music/%s/%s" % (A, US))
        r = self.r()
        self.assertEqual((r["source"], self.name(r)), ("manual", US))
        self.assertTrue(r["set_at"])
        R.choose(self.root, A, SONG, self.pdir, "ass", None)   # 清除 -> 回到 playlist, ref.json 删掉
        self.assertEqual(self.r()["source"], "playlist")
        self.assertFalse(os.path.exists(os.path.join(self.pdir, R.FILE)))

    def test_manual_missing_file_is_error_no_fallback(self):
        self.put(OK)
        json.dump(dict(ass="static/music/%s/gone.ass" % A), open(os.path.join(self.pdir, R.FILE), "w"))
        r = self.r()
        self.assertEqual((r["source"], r["path"]), ("error", None))

    # ---- 防回归护栏 (改前改后都过, 不算修复证据)
    def test_choose_rejects_non_candidate(self):
        self.put(OK)
        with self.assertRaises(ValueError):
            R.choose(self.root, A, SONG, self.pdir, "ass", "static/music/%s/other.ass" % A)

    def test_unique_guard(self):
        self.put(OK)
        r = self.r()
        self.assertEqual((r["source"], self.name(r)), ("unique", OK))

    def test_none_guard(self):
        self.assertEqual(self.r()["source"], "none")


if __name__ == "__main__":
    unittest.main(verbosity=1)
