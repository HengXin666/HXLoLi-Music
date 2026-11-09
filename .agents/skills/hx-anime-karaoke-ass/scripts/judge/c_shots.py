# -*- coding: utf-8 -*-
"""shots.json 判据: 视频元素, 逐镜头. 格式见 shared/judge-formats.md."""
import os

from judge.common import jpath, load_json, nonempty

GAP = 0.5      # 相邻镜头之间允许的空隙 (秒)
CUT_TOL = 0.3  # 镜头起点与 scene-timeline 切点的容差 (秒)


def check(song, res):
    """返回 {镜头 id: (t0, t1)}, 不含无画面段. 没有视频时返回 {}."""
    d, err = load_json(jpath(song.proj, "shots.json"))
    if err:
        res.bad("shots.json", "缺失" if err == "missing" else err)
        return None
    if d.get("source") == "none":
        res.check(nonempty(d.get("reason")), "shots 无视频", "source=none 时要写 reason")
        res.warn("shots 无视频", "没有画面可分析. 下游不能用镜头锚点, 风格表要从原作取证")
        return {}
    shots = d.get("shots") or []
    if not res.check(shots, "shots 数量", "没有镜头"):
        return {}
    out, blind = {}, []
    prev = None
    for s in shots:
        sid = s.get("id") or "?"
        tag = "shots[%s]" % sid
        t0, t1 = s.get("t0"), s.get("t1")
        if not res.check(isinstance(t0, (int, float)) and isinstance(t1, (int, float)) and t0 < t1,
                         tag + " 时间", "t0 < t1 且都是秒数"):
            continue
        res.check(sid not in out and sid not in [b[0] for b in blind], tag + " id", "id 重复")
        if prev is not None:
            res.check(-1e-6 <= t0 - prev <= GAP, tag + " 连续", "与上一镜头之间 %.2fs (重叠或空隙 > %.1fs)" % (t0 - prev, GAP))
        prev = t1
        if s.get("source") == "none":       # 视频只覆盖一部分 (如 TV size ED): 这一段没有画面
            res.check(nonempty(s.get("reason")), tag + " reason", "无画面段要写 reason")
            blind.append((sid, t0, t1))
            continue
        out[sid] = (t0, t1)
        for f in ("color", "subject", "motion"):
            res.check(nonempty(s.get(f)), tag + " " + f, "%s 不能为空" % f)
        res.check(isinstance(s.get("symbols"), list), tag + " symbols", "symbols 要是列表 (可以为空)")
    if blind:
        res.warn("shots 无画面段", "%d 段没有画面 (%s). 这些段不能用镜头锚点, 风格表要从原作取证" % (
            len(blind), ", ".join("%s %.1f-%.1f" % b for b in blind)))
    span = song.song_span()
    allv = list(out.values()) + [(b[1], b[2]) for b in blind]
    if span and allv:
        lo, hi = min(v[0] for v in allv), max(v[1] for v in allv)
        res.check(lo <= span[0] and hi >= span[1], "shots 覆盖",
                  "镜头表 [%.1f, %.1f] 没覆盖歌词区间 [%.1f, %.1f]" % (lo, hi, span[0], span[1]))
    _cuts(song, out, res, float(d.get("video_offset") or 0))
    return out


def _cuts(song, out, res, off=0.0):
    """有 scene-timeline 时, 镜头起点应落在切点附近. 只提示, 人眼分镜可以比自动切点粗."""
    st, _ = load_json(os.path.join(song.proj, "review", "scene-timeline.json"))
    if not st:
        return
    cuts = [x["t0"] + off for x in st.get("shots", []) if x.get("cut")]   # 切点是视频时间, off 换到歌曲时间
    if not cuts:
        return
    far = [sid for sid, (t0, _) in out.items() if min(abs(c - t0) for c in cuts) > CUT_TOL and t0 > min(cuts)]
    if far:
        res.warn("shots 切点", "这些镜头起点离 scene-timeline 切点 > %.1fs: %s" % (CUT_TOL, far))
