#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_judge 自测: 造一个 6 句的玩具工程. 合格版必须 0 FAIL, 每个坏版必须在指定项上 FAIL.

  hx-karaoke judge/selftest_judge.py [--keep]
"""
import copy, json, os, shutil, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from judge.check_judge import run   # noqa: E402

LYR = ["[空|そら]を[見|み]た", "[雨|あめ]が[降|ふ]る", "きみの[声|こえ]", "[走|はし]れ", "[光|ひかり]の[中|なか]", "さよなら"]
TXT = ["空を見た", "雨が降る", "きみの声", "走れ", "光の中", "さよなら"]
T0 = [10.0, 14.0, 18.0, 24.0, 28.0, 34.0]     # 每句起点, 每句 2.5s; 20.5-24.0 有 3.5s 静默


def base():
    tl = []
    for i, t in enumerate(T0):
        tl += [{"line": i, "unit": 0, "mora": 0, "text": "x", "s": t, "e": t + 1.2},
               {"line": i, "unit": 1, "mora": 0, "text": "y", "s": t + 1.2, "e": t + 2.5}]
    ev = {"onset": [10.5, 18.3, 28.0], "sub": [24.0], "section": [0.0, 24.0], "grid": [10.0, 10.2]}
    sh = {"version": 1, "shots": [
        {"id": "s1", "t0": 0, "t1": 20, "color": "蓝灰", "subject": "天空", "motion": "静", "symbols": ["云"]},
        {"id": "s2", "t0": 20, "t1": 40, "color": "金", "subject": "少女", "motion": "左->右", "symbols": []}]}
    vis = {"version": 1, "lines": [
        {"line": i, "text": TXT[i], "image": ["意象%d" % i], "mood": "情绪", "voice": {"who": "我", "to": "你"},
         "weight": [TXT[i][0]], "link": {"prev": "承接", "next": "推进"}} for i in range(6)]}
    hl = lambda hid, ln, k, t, a: {"id": hid, "lines": ln, "music_event": {"kind": k, "t": t},   # noqa: E731
                                   "reaction": "屏息", "unique": "只此一首", "anchor": a, "refs": ["r1"]}
    bar = {"version": 1, "searched": [{"where": "bilibili", "query": "曲名 卡拉OK", "found": 3}],
           "refs": [{"id": "r%d" % k, "tier": "A", "title": "参照%d" % k, "why": "同曲",
                     "moments": [{"t": "1:23", "what": "字碎成光", "technique": "粒子化"}]} for k in (1, 2, 3)],
           "highlights": [hl("h1", [0], "onset", 10.5, {"motif": "星辰"}),
                          hl("h2", [3], "silence", 22.0, {"shot": "s2"}),
                          hl("h3", [4], "onset", 28.0, {"motif": "羽毛"})]}
    ev_id = [{"id": "e%d" % k, "what": "画面", "where": "shot:s%d" % (k % 2 + 1)} for k in (1, 2, 3)]
    sty = {"version": 1, "evidence": ev_id, "line": "细线", "texture": "水彩",
           "palette": [{"name": "c%d" % k, "hex": "#11223%d" % k, "from": "e1"} for k in (1, 2, 3)],
           "motion": [{"word": "飘", "from": "e2"}, {"word": "坠", "from": "e3"}],
           "banned": [{"what": "霓虹", "why": "原作是水彩"}]}
    role = ["highlight", "carrier", "rest", "highlight", "highlight", "carrier"]
    hid = {0: "h1", 3: "h2", 4: "h3"}
    tech = {0: "star-burst", 3: "silence-drop", 4: "feather-sweep"}
    arc = {"version": 1, "sections": [{"id": "A", "lines": [0, 1, 2], "budget": 0.3, "why": "铺垫"},
                                      {"id": "B", "lines": [3, 4, 5], "budget": 0.9, "why": "爆发"}],
           "lines": [{"line": i, "text": TXT[i], "role": role[i], "idea": "构想", "technique": tech.get(i, "ink"),
                      "anchors": [{"kind": "image", "ref": "意象%d" % i}], "highlight": hid.get(i),
                      "thread": {"mode": "carry", "state": "颜色"}} for i in range(6)]}
    con = {"version": 1, "highlights": [
        {"id": h, "concepts": [{"id": "c1", "idea": "甲", "technique": tech[i], "vs_bar": "达到", "chosen": True,
                                "frames": ["judge/frames/%s_c1.png" % h]},
                               {"id": "c2", "idea": "乙", "technique": "other-" + h, "vs_bar": "不如", "chosen": False,
                                "reject_reason": "太像通用图形", "frames": ["judge/frames/%s_c2.png" % h]}]}
        for i, h in hid.items()]}
    return dict(tl=tl, ev=ev, shots=sh, visual=vis, bar=bar, style=sty, arc=arc, concepts=con)


def write(proj, d):
    os.makedirs(os.path.join(proj, "judge", "frames"), exist_ok=True)
    os.makedirs(os.path.join(proj, "review"), exist_ok=True)
    with open(os.path.join(proj, "lyrics.txt"), "w", encoding="utf-8") as f:
        f.write("".join("00:%02d.000 | %s | 中\n" % (int(T0[i]), LYR[i]) for i in range(6)))
    with open(os.path.join(proj, "anime.elements.md"), "w", encoding="utf-8") as f:
        f.write("| 元素 | 来源数 |\n|---|---|\n| **星辰** | 4 |\n| **羽毛** | 3 |\n")
    dump = lambda p, o: json.dump(o, open(os.path.join(proj, p), "w", encoding="utf-8"), ensure_ascii=False)  # noqa: E731
    dump("timing.json", d["tl"])
    if d["ev"] is not None:
        dump("review/music-events.json", d["ev"])
    for k in ("shots", "visual", "bar", "style", "arc", "concepts"):
        name = "lines.visual.json" if k == "visual" else k + ".json"
        dump("judge/" + name, d[k])
    for h in ("h1", "h2", "h3"):
        for c in ("c1", "c2"):
            open(os.path.join(proj, "judge", "frames", "%s_%s.png" % (h, c)), "wb").close()


def mutate(d, fn):
    d = copy.deepcopy(d)
    fn(d)
    return d


CASES = [  # (说明, 改法, 期望 FAIL 的项名前缀)
    ("参照不足 3 个", lambda d: d["bar"]["refs"].pop(), "bar.refs 数量"),
    ("A 层够了还用 C 层", lambda d: d["bar"]["refs"].append(dict(d["bar"]["refs"][0], id="r9", tier="C")), "bar.refs 层级顺序"),
    ("高光只有 2 个", lambda d: d["bar"]["highlights"].pop(), "bar.highlights 数量"),
    ("高光没有锚点", lambda d: d["bar"]["highlights"][0].pop("anchor"), "bar.highlights[h1] anchor"),
    ("母题不在元素表", lambda d: d["bar"]["highlights"][0].update(anchor={"motif": "盾"}), "bar.highlights[h1] anchor"),
    ("音乐事件对不上", lambda d: d["bar"]["highlights"][0]["music_event"].update(t=11.4), "bar.highlights[h1] music_event"),
    ("静默不在句间", lambda d: d["bar"]["highlights"][1]["music_event"].update(t=25.0), "bar.highlights[h2] music_event"),
    ("没有事件表也没声明", lambda d: d.update(ev=None), "bar.events"),
    ("声明缺事件表却绑 onset", lambda d: (d.update(ev=None), d["bar"].update(events="missing")), "bar.highlights[h1] music_event"),
    ("有事件表却声明缺失", lambda d: d["bar"].update(events="missing"), "bar.events"),
    ("歌词原文对不上", lambda d: d["visual"]["lines"][2].update(text="きみの声!"), "visual[2] 定位"),
    ("漏一句视觉分析", lambda d: d["visual"]["lines"].pop(), "visual 覆盖"),
    ("重字不在句内", lambda d: d["visual"]["lines"][0].update(weight=["海"]), "visual[0] weight"),
    ("镜头有空隙", lambda d: d["shots"]["shots"][1].update(t0=21), "shots[s2] 连续"),
    ("无画面段没写 reason", lambda d: d["shots"]["shots"].__setitem__(1, {"id": "s2", "t0": 20, "t1": 40, "source": "none"}), "shots[s2] reason"),
    ("锚到无画面段", lambda d: d["shots"]["shots"].__setitem__(1, {"id": "s2", "t0": 20, "t1": 40, "source": "none", "reason": "TV size"}), "bar.highlights[h2] anchor"),
    ("镜头没覆盖歌词", lambda d: d["shots"]["shots"][1].update(t1=30), "shots 覆盖"),
    ("色板缺证据", lambda d: d["style"]["palette"][0].update({"from": "e9"}), "style.palette[c1]"),
    ("没有禁用项", lambda d: d["style"].update(banned=[]), "style.banned"),
    ("段落没切分全部句", lambda d: d["arc"]["sections"][1]["lines"].pop(), "arc.sections 切分"),
    ("强度没有对比", lambda d: d["arc"]["sections"][0].update(budget=0.8), "arc 强度对比"),
    ("没有留白", lambda d: (d["arc"]["sections"][0].update(budget=0.5), d["arc"]["sections"][1].update(budget=1.0),
                           d["arc"]["lines"][2].update(role="carrier")), "arc 留白"),
    ("锚点意象不在分析里", lambda d: d["arc"]["lines"][1]["anchors"][0].update(ref="海"), "arc[1] anchor"),
    ("事件锚点离句子太远", lambda d: d["arc"]["lines"][1]["anchors"].append(
        {"kind": "event", "ref": {"kind": "sub", "t": 24.0}}), "arc[1] anchor"),
    ("两个高光同一手法", lambda d: d["arc"]["lines"][4].update(technique="star-burst"), "arc 高光手法"),
    ("高光句未标 highlight", lambda d: d["arc"]["lines"][0].update(role="carrier"), "arc[0] 高光"),
    ("缺句间状态", lambda d: d["arc"]["lines"][3].pop("thread"), "arc[3] thread"),
    ("只有一个构想", lambda d: d["concepts"]["highlights"][0]["concepts"].pop(), "concepts[h1] 数量"),
    ("落选没理由", lambda d: d["concepts"]["highlights"][0]["concepts"][1].pop("reject_reason"), "concepts[h1].c2 落选理由"),
    ("构想手法相同", lambda d: d["concepts"]["highlights"][0]["concepts"][1].update(technique="star-burst"), "concepts[h1] 手法"),
    ("选定稿与 arc 不一致", lambda d: d["concepts"]["highlights"][0]["concepts"][0].update(technique="xx"), "concepts[h1] 与 arc 一致"),
    ("缺关键帧", lambda d: d["concepts"]["highlights"][0]["concepts"][0].update(frames=["judge/frames/none.png"]), "concepts[h1].c1 frames"),
]


def main():
    keep = "--keep" in sys.argv
    root = tempfile.mkdtemp(prefix="judge_selftest_")
    good, fails = base(), 0
    write(os.path.join(root, "good"), good)
    res = run(os.path.join(root, "good"))
    bad = res.failed()
    print("%s 合格版 0 FAIL%s" % ("PASS" if not bad else "FAIL", "" if not bad else ": %s" % bad))
    fails += bool(bad)
    for k, (name, fn, want) in enumerate(CASES):
        p = os.path.join(root, "c%02d" % k)
        write(p, mutate(good, fn))
        got = [r for r in run(p).failed() if r[1].startswith(want)]
        print("%s %s -> FAIL %s" % ("PASS" if got else "FAIL", name, want))
        fails += not got
    if not keep:
        shutil.rmtree(root)
    else:
        print("保留在", root)
    print("\n%d/%d PASS" % (len(CASES) + 1 - fails, len(CASES) + 1))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
