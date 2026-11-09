# -*- coding: utf-8 -*-
"""bar.json 判据: 定标. 格式见 shared/judge-formats.md 的 bar 一节."""
from judge.common import EVENT_KINDS, jpath, load_json, nonempty, ts

TIERS = ("A", "B", "C")


def check(song, res, shots=None):
    d, err = load_json(jpath(song.proj, "bar.json"))
    if err:
        res.bad("bar.json", "缺失" if err == "missing" else err)
        return None
    _events_decl(song, d, res)
    _refs(d, res)
    _highlights(song, d, res, shots)
    return d


def _events_decl(song, d, res):
    """新工程必须有事件表. 只有 grid 的老工程要在 bar.json 写 "events": "missing", 高光只许绑 section/mora/silence."""
    if song.has_events:
        res.check(d.get("events") != "missing", "bar.events", "事件表存在, 不要写 events: missing")
    else:
        res.check(d.get("events") == "missing", "bar.events",
                  "没有 review/music-events.json. 新工程先跑 music_events.py (40 步); 只有 grid 的老工程写 \"events\": \"missing\"")


def _refs(d, res):
    refs = d.get("refs") or []
    searched = d.get("searched") or []
    res.check(len(searched) >= 1 and all(nonempty(s.get("where")) and nonempty(s.get("query")) for s in searched),
              "bar.searched", "每条检索要写 where 与 query. 没找到也要记, 它决定能否下降层级")
    res.check(len(refs) >= 3, "bar.refs 数量", "参照只有 %d 个, 至少 3 个 (不够就往下一层补)" % len(refs))
    cnt = {t: sum(1 for r in refs if r.get("tier") == t) for t in TIERS}
    bad_tier = [r.get("id") for r in refs if r.get("tier") not in TIERS]
    res.check(not bad_tier, "bar.refs 层级", "tier 只能是 A/B/C: %s" % bad_tier)
    # 上一层不够 3 个才往下补
    res.check(not cnt["B"] or cnt["A"] < 3, "bar.refs 层级顺序", "A 层已有 %d 个, 不该再用 B 层" % cnt["A"])
    res.check(not cnt["C"] or cnt["A"] + cnt["B"] < 3, "bar.refs 层级顺序",
              "A+B 层已有 %d 个, 不该再用 C 层" % (cnt["A"] + cnt["B"]))
    if not cnt["A"]:
        res.check(len(searched) >= 2, "bar.searched", "没有 A 层参照时至少记 2 次检索, 证明找过")
    for r in refs:
        rid = r.get("id") or "?"
        ms = r.get("moments") or []
        good = nonempty(r.get("title")) and nonempty(r.get("why")) and ms and all(
            ts(m.get("t")) is not None and nonempty(m.get("what")) and nonempty(m.get("technique")) for m in ms)
        res.check(good, "bar.refs[%s]" % rid, "要有 title, why, 以及 >=1 个带时间戳 t / what / technique 的 moment")


def _highlights(song, d, res, shots):
    hs = d.get("highlights") or []
    res.check(3 <= len(hs) <= 6, "bar.highlights 数量", "高光时刻 %d 个, 要求 3-6 个. 参照层级下降时也不许减少" % len(hs))
    seen, ids = set(), set()
    ref_ids = {r.get("id") for r in d.get("refs") or []}
    for h in hs:
        hid = h.get("id") or "?"
        tag = "bar.highlights[%s]" % hid
        res.check(hid not in ids, tag + " id", "id 重复")
        ids.add(hid)
        lines = h.get("lines") or []
        okl = lines and all(isinstance(i, int) and 0 <= i < song.n for i in lines)
        res.check(okl, tag + " lines", "lines 要是有效句序号的非空列表")
        res.check(not (set(lines) & seen), tag + " lines", "与其他高光时刻共用句子 %s" % sorted(set(lines) & seen))
        seen |= set(lines)
        for f in ("reaction", "unique"):
            res.check(nonempty(h.get(f)), tag + " " + f, "%s 不能为空 (观众反应 / 只有这首歌能做的元素)" % f)
        res.check(set(h.get("refs") or []) <= ref_ids, tag + " refs", "引用了不存在的参照")
        _event(song, h, tag, lines if okl else [], res)
        _anchor(song, h.get("anchor") or {}, tag, res, shots)


def _event(song, h, tag, lines, res):
    ev = h.get("music_event") or {}
    kind, t = ev.get("kind"), ts(ev.get("t"))
    if not res.check(kind in EVENT_KINDS and t is not None, tag + " music_event",
                     "要有 kind (%s) 与 t" % "/".join(EVENT_KINDS)):
        return
    if lines and song.spans:
        s0 = min(song.spans[i][0] for i in lines if i in song.spans)
        s1 = max(song.spans[i][1] for i in lines if i in song.spans)
        res.check(s0 - 2 <= t <= s1 + 2, tag + " music_event",
                  "t=%.2f 不在这几句的时间 [%.2f, %.2f] 附近 (±2s)" % (t, s0, s1))
    hit, why = song.event_ok(kind, t)
    res.check(bool(hit), tag + " music_event", why)


def _anchor(song, a, tag, res, shots):
    """高光的专属元素必须落到番剧元素表或镜头表上."""
    if a.get("motif"):
        res.check(a["motif"] in song.elements, tag + " anchor",
                  "母题 %r 不在 anime.elements.md (现有: %s)" % (a["motif"], ", ".join(sorted(song.elements)) or "无"))
    elif a.get("shot"):
        if shots is None:
            res.warn(tag + " anchor", "shots.json 还没有, 镜头锚点暂不核对")
        else:
            res.check(a["shot"] in shots, tag + " anchor", "镜头 %r 不在 shots.json" % a["shot"])
    else:
        res.bad(tag + " anchor", "要有 motif (番剧元素) 或 shot (镜头 id). 没有锚点的高光换到别的歌也成立")
