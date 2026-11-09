# -*- coding: utf-8 -*-
"""concepts.json 判据: 高光句发散. 每个高光 2-3 个不同构想, 选一个, 落选的写理由. 格式见 shared/judge-formats.md."""
import os

from judge.common import jpath, load_json, nonempty


def check(song, res, bar=None, arc=None):
    d, err = load_json(jpath(song.proj, "concepts.json"))
    if err:
        res.bad("concepts.json", "缺失" if err == "missing" else err)
        return None
    hs = {h.get("id"): h for h in d.get("highlights") or []}
    want = [h.get("id") for h in (bar or {}).get("highlights") or []]
    if bar is None:
        res.warn("concepts 覆盖", "bar.json 不可用, 不核对是否每个高光都发散过")
    else:
        miss = [h for h in want if h not in hs]
        res.check(not miss, "concepts 覆盖", "这些高光没有发散稿: %s" % miss)
    arc_tech = _arc_tech(bar, arc)
    for hid, h in hs.items():
        _one(song, hid, h.get("concepts") or [], arc_tech.get(hid), res)
    return d


def _arc_tech(bar, arc):
    """高光 id -> arc.json 里这个高光各句的手法集合."""
    if not bar or not arc:
        return {}
    out = {}
    for r in arc.get("lines") or []:
        if r.get("role") == "highlight" and nonempty(r.get("technique")):
            out.setdefault(r.get("highlight"), set()).add(r["technique"].strip().lower())
    return out


def _one(song, hid, cs, arc_tech, res):
    tag = "concepts[%s]" % hid
    res.check(2 <= len(cs) <= 3, tag + " 数量", "要 2-3 个构想 (现在 %d 个). 只有一个等于没发散" % len(cs))
    chosen = [c for c in cs if c.get("chosen")]
    res.check(len(chosen) == 1, tag + " 选定", "要正好选定 1 个 (现在 %d 个)" % len(chosen))
    techs = [str(c.get("technique", "")).strip().lower() for c in cs]
    res.check(all(techs) and len(set(techs)) == len(techs), tag + " 手法",
              "各构想手法要不同且非空 (现在 %s). 只换参数不算另一个构想" % techs)
    for c in cs:
        cid = c.get("id") or "?"
        ct = "%s.%s" % (tag, cid)
        res.check(nonempty(c.get("idea")), ct + " idea", "构想不能为空")
        res.check(nonempty(c.get("vs_bar")), ct + " vs_bar", "要对照 bar.json 写自评")
        fr = c.get("frames") or []
        miss = [f for f in fr if not os.path.exists(os.path.join(song.proj, f))]
        res.check(fr and not miss, ct + " frames", "要有关键帧 (真渲染器抽帧), 文件要存在. 缺: %s" % (miss or "全部"))
        if not c.get("chosen"):
            res.check(nonempty(c.get("reject_reason")), ct + " 落选理由", "落选构想要写理由")
    if chosen and arc_tech is not None:
        t = str(chosen[0].get("technique", "")).strip().lower()
        res.check(t in arc_tech, tag + " 与 arc 一致",
                  "选定构想的手法 %r 与 arc.json 这个高光的手法 %s 不一致" % (t, sorted(arc_tech)))
