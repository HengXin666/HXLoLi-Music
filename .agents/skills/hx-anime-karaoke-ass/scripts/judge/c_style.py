# -*- coding: utf-8 -*-
"""style.json 判据: 风格表. 每条都要指向一条证据 (原作或 MV 的具体画面). 格式见 shared/judge-formats.md."""
from judge.common import HEX_RE, jpath, load_json, nonempty


def check(song, res, shots=None):
    d, err = load_json(jpath(song.proj, "style.json"))
    if err:
        res.bad("style.json", "缺失" if err == "missing" else err)
        return None
    ev = {}
    for e in d.get("evidence") or []:
        ok = nonempty(e.get("id")) and nonempty(e.get("what")) and nonempty(e.get("where"))
        res.check(ok, "style.evidence[%s]" % e.get("id"), "要有 id, what, where (镜头 id / 集数+时间 / url)")
        if ok:
            ev[e["id"]] = e
    res.check(len(ev) >= 3, "style.evidence 数量", "证据只有 %d 条, 至少 3 条" % len(ev))
    if shots:
        bad = [e["id"] for e in ev.values() if e["where"].startswith("shot:") and e["where"][5:] not in shots]
        res.check(not bad, "style.evidence 镜头", "引用了 shots.json 里没有的镜头: %s" % bad)
    pal = d.get("palette") or []
    res.check(len(pal) >= 3, "style.palette 数量", "色板至少 3 色")
    for p in pal:
        res.check(nonempty(p.get("name")) and HEX_RE.match(str(p.get("hex", ""))) and p.get("from") in ev,
                  "style.palette[%s]" % p.get("name"), "要有 name, hex (#RRGGBB), from (证据 id)")
    mot = d.get("motion") or []
    res.check(len(mot) >= 2, "style.motion 数量", "运动词汇至少 2 条")
    for m in mot:
        res.check(nonempty(m.get("word")) and m.get("from") in ev, "style.motion[%s]" % m.get("word"),
                  "要有 word 与 from (证据 id)")
    for f in ("line", "texture"):
        res.check(nonempty(d.get(f)), "style." + f, "%s 不能为空" % f)
    ban = d.get("banned") or []
    res.check(ban and all(nonempty(b.get("what")) and nonempty(b.get("why")) for b in ban), "style.banned",
              "禁用项至少 1 条, 每条写 what 与 why")
    return d
