# -*- coding: utf-8 -*-
"""arc.json 判据: 全曲剧本. 强度预算 + 每句角色/构想/锚点 + 句间状态. 格式见 shared/judge-formats.md.

只查能机械证伪的: 覆盖, 锚点能指到上游产物, 有对比, 有留白, 高光手法不重复.
构想写得好不好不在这里判, 由自审盲审 (意图还原) 判.
"""
from judge.common import EVENT_KINDS, jpath, load_json, nonempty, ts

ROLES = ("highlight", "carrier", "rest")
CONTRAST = 0.4    # 段落强度预算的极差下限: 惊艳来自对比
REST_BUDGET = 0.3  # 预算不高于它的段落算留白段
NEAR = 1.0        # 锚点 (镜头/事件) 与句子时间的容差 (秒)


def check(song, res, bar=None, visual=None, shots=None):
    d, err = load_json(jpath(song.proj, "arc.json"))
    if err:
        res.bad("arc.json", "缺失" if err == "missing" else err)
        return None
    secs = _sections(song, d.get("sections") or [], res)
    rows = _lines(song, d.get("lines") or [], res, visual or {}, shots)
    if secs and rows:
        has_rest = any(r.get("role") == "rest" for r in rows.values()) or any(b <= REST_BUDGET for b in secs.values())
        res.check(has_rest, "arc 留白", "没有留白: 既没有 role=rest 的句, 也没有预算 <= %.1f 的段" % REST_BUDGET)
    _highlights(rows, bar, res)
    return d


def _sections(song, secs, res):
    """返回 {段 id: 预算}. 段要按顺序连续地切分全部句子."""
    order, out = [], {}
    for s in secs:
        sid = s.get("id") or "?"
        b = s.get("budget")
        res.check(isinstance(b, (int, float)) and 0 <= b <= 1, "arc.sections[%s] budget" % sid, "budget 要在 0..1")
        res.check(nonempty(s.get("why")), "arc.sections[%s] why" % sid, "要写为什么给这个强度")
        res.check(sid not in out, "arc.sections[%s] id" % sid, "id 重复")
        out[sid] = b if isinstance(b, (int, float)) else 0
        order += list(s.get("lines") or [])
    res.check(order == list(range(song.n)), "arc.sections 切分",
              "各段 lines 按顺序拼起来必须正好是 0..%d (现在是 %s)" % (song.n - 1, order))
    if out:
        spread = max(out.values()) - min(out.values())
        res.check(spread >= CONTRAST, "arc 强度对比",
                  "段落预算极差 %.2f < %.1f. 每段都差不多强等于没有高光" % (spread, CONTRAST))
    return out


def _lines(song, rows, res, visual, shots):
    got = {}
    for r in rows:
        tag = "arc[%s]" % r.get("line")
        e = song.line_ok(r)
        if not res.check(e is None and r.get("line") not in got, tag + " 定位", e or "同一句出现两次"):
            continue
        i = r["line"]
        got[i] = r
        res.check(r.get("role") in ROLES, tag + " role", "role 只能是 %s" % "/".join(ROLES))
        res.check(nonempty(r.get("idea")), tag + " idea", "构想不能为空: 观众看到什么, 为什么")
        res.check(nonempty(r.get("technique")), tag + " technique", "手法标签不能为空 (用来查高光手法重复)")
        anchors = r.get("anchors") or []
        res.check(anchors, tag + " anchors", "至少一个锚点 (motif / image / shot / event)")
        for a in anchors:
            why = _anchor(song, i, a, visual, shots)
            if why == "skip":
                res.warn(tag + " anchor", "shots.json 还没有, 镜头锚点暂不核对")
            else:
                res.check(why is None, tag + " anchor", why or "")
        if i > 0:
            th = r.get("thread") or {}
            res.check(th.get("mode") in ("carry", "break") and nonempty(th.get("state")), tag + " thread",
                      "要写与上一句的状态传递: mode=carry 写传什么, mode=break 写为什么断")
    miss = [i for i in range(song.n) if i not in got]
    res.check(not miss, "arc 覆盖", "缺这些句: %s" % miss)
    return got


def _anchor(song, i, a, visual, shots):
    """返回 None (有效), 'skip' (无法核对), 或错误说明."""
    kind, ref = a.get("kind"), a.get("ref")
    span = song.spans.get(i)
    if kind == "motif":
        return None if ref in song.elements else "母题 %r 不在 anime.elements.md" % ref
    if kind == "image":
        imgs = (visual.get(i) or {}).get("image") or []
        return None if ref in imgs else "意象 %r 不在 lines.visual.json 这一句的 image 里 %s" % (ref, imgs)
    if kind == "shot":
        if shots is None:
            return "skip"
        if ref not in shots:
            return "镜头 %r 不在 shots.json" % ref
        t0, t1 = shots[ref]
        if span and (t1 < span[0] - NEAR or t0 > span[1] + NEAR):
            return "镜头 %s [%.1f, %.1f] 与本句 [%.1f, %.1f] 不重叠" % (ref, t0, t1, span[0], span[1])
        return None
    if kind == "event":
        ref = ref or {}
        k, t = ref.get("kind"), ts(ref.get("t"))
        if k not in EVENT_KINDS or t is None:
            return "event 锚点要有 kind (%s) 与 t" % "/".join(EVENT_KINDS)
        if span and not span[0] - NEAR <= t <= span[1] + NEAR:
            return "事件 t=%.2f 不在本句 [%.1f, %.1f] 附近" % (t, span[0], span[1])
        hit, why = song.event_ok(k, t)
        return None if hit else why
    return "未知锚点类型 %r" % kind


def _highlights(rows, bar, res):
    if bar is None:
        res.warn("arc 高光", "bar.json 不可用, 高光对应关系暂不核对")
        return
    want = {i: h.get("id") for h in bar.get("highlights") or [] for i in h.get("lines") or []}
    for i, r in rows.items():
        is_h = r.get("role") == "highlight"
        if i in want:
            res.check(is_h and r.get("highlight") == want[i], "arc[%d] 高光" % i,
                      "bar 把这句定为高光 %s, arc 要写 role=highlight, highlight=%s" % (want[i], want[i]))
        elif is_h:
            res.bad("arc[%d] 高光" % i, "role=highlight 但不在 bar.json 的任何高光时刻里")
    tech = {}
    for i, r in rows.items():
        if i in want and nonempty(r.get("technique")):
            tech.setdefault(want[i], set()).add(r["technique"].strip().lower())
    hs = sorted(tech)
    for a in range(len(hs)):
        for b in range(a + 1, len(hs)):
            dup = tech[hs[a]] & tech[hs[b]]
            res.check(not dup, "arc 高光手法 %s/%s" % (hs[a], hs[b]), "两个高光用了同一手法 %s" % sorted(dup))
