# -*- coding: utf-8 -*-
"""lines.visual.json 判据: 歌词视觉化, 逐句. 格式见 shared/judge-formats.md."""
from judge.common import jpath, load_json, nonempty


def check(song, res):
    d, err = load_json(jpath(song.proj, "lines.visual.json"))
    if err:
        res.bad("lines.visual.json", "缺失" if err == "missing" else err)
        return None
    rows = d.get("lines") or []
    got = {}
    for r in rows:
        tag = "visual[%s]" % r.get("line")
        e = song.line_ok(r)
        if not res.check(e is None, tag + " 定位", e or ""):
            continue
        if not res.check(r["line"] not in got, tag + " 定位", "同一句出现两次"):
            continue
        got[r["line"]] = r
        _row(r, tag, res)
    miss = [i for i in range(song.n) if i not in got]
    res.check(not miss, "visual 覆盖", "缺这些句: %s. 每句都要分析, 不能只挑好画的" % miss)
    return got


def _row(r, tag, res):
    img = r.get("image") or []
    res.check(img and all(nonempty(x) for x in img), tag + " image",
              "意象要是具体名词或动词的非空列表")
    res.check(nonempty(r.get("mood")), tag + " mood", "情绪不能为空")
    v = r.get("voice") or {}
    res.check(nonempty(v.get("who")) and nonempty(v.get("to")), tag + " voice", "要写谁 (who) 对谁 (to) 唱")
    w = r.get("weight") or []
    res.check(1 <= len(w) <= 2 and all(nonempty(x) and x in r["text"] for x in w), tag + " weight",
              "重字 1-2 个, 每个必须是本句原文里的字或词 (得到 %s)" % w)
    lk = r.get("link") or {}
    res.check(nonempty(lk.get("prev")) and nonempty(lk.get("next")), tag + " link",
              "要写与前句 (prev) 和后句 (next) 的关系. 没有关系写 \"断开\" 并说明")
