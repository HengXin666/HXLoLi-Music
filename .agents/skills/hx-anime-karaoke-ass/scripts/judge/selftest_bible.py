#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_bible 自测: 造一个 4 句的玩具工程. 合格版必须 0 FAIL, 每个坏版必须在指定项上 FAIL.

  hx-karaoke judge/selftest_bible.py [--keep]
"""
import copy, json, os, shutil, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from judge.check_bible import run     # noqa: E402
from judge import blind_bible          # noqa: E402

LYR = ["[星|ほし]を[見|み]た", "[剣|けん]を[抜|ぬ]く", "きみの[声|こえ]", "さよなら"]
TXT = ["星を見た", "剣を抜く", "きみの声", "さよなら"]
GEN = '''def fx_star(f, ph, k):
    put(f, "crown_gem")


def fx_blade(f, ph, k):
    put(f, "silver_blade")


PHRASES = [
    dict(lines=[0], fx="star"),
    dict(lines=[1], fx="blade"),
]
'''


def R(src, q="原文摘句"):
    return {"src": src, "quote": q}


def base():
    syms = [
        {"id": "gem", "name": "王冠宝石", "kind": "token", "unique": 3, "unique_why": "只此一部", "form": "额前红宝石",
         "refs": [R("O"), R("C1"), R("C2")]},
        {"id": "blade", "name": "银之剑", "kind": "token", "unique": 2, "unique_why": "专名", "form": "银剑", "refs": [R("O")]},
        {"id": "voice", "name": "念话", "kind": "ability", "unique": 2, "unique_why": "专设", "form": "无声的环",
         "refs": [R("P")]},
        {"id": "tower", "name": "白塔", "kind": "world", "unique": 2, "unique_why": "专名", "form": "白塔",
         "refs": [R("C1"), R("C2"), R("C3")]},
        {"id": "rain", "name": "雨", "kind": "line", "unique": 0, "form": "雨滴", "refs": [R("C1")]},
        {"id": "fire", "name": "火", "kind": "line", "unique": 1, "form": "火苗", "refs": [R("C2")]},
        {"id": "leaf", "name": "叶", "kind": "line", "unique": 0, "form": "落叶", "refs": [R("V")]},
    ]
    src = [{"id": "O", "type": "official", "name": "官网", "url": "https://a"},
           {"id": "P", "type": "original", "name": "原作", "url": "https://b"},
           {"id": "C1", "type": "community", "name": "百科", "url": "https://c"},
           {"id": "C2", "type": "community", "name": "博客", "url": "https://d"},
           {"id": "C3", "type": "community", "name": "问答", "url": "https://e"},
           {"id": "V", "type": "screen", "name": "画面"}]
    ch = lambda n, sym: {"name": n, "aliases": [], "temperament": ["静"], "motion": "慢", "type_mood": "细明朝",   # noqa: E731
                         "colors": [{"hex": "#112233", "what": "发色", "symbol": sym}]}
    d = {"symbols.json": {"version": 1, "work": {"title": "玩具物语", "aliases": ["Toy Tale"]}, "sources": src, "symbols": syms},
         "characters.json": {"version": 1, "characters": [ch("アリス", "gem"), ch("ボブ", "blade")]},
         "scenes.json": {"version": 1, "scenes": [
             {"id": "sc1", "what": "加冕", "where": "第1话", "symbols": ["gem"], "refs": [R("O")]},
             {"id": "sc2", "what": "拔剑", "where": "第2话", "symbols": ["blade"], "refs": [R("P")]}],
             "quotes": [{"id": "q1", "text": "剣を抜け", "speaker": "アリス", "refs": [R("P")], "echo": [{"line": 1, "how": "同一动作"}]}]},
         "lyric-map.json": {"version": 1, "lines": [
             {"line": 0, "text": TXT[0], "basis": "direct", "plot": "加冕夜", "refs": ["gem", "sc1"]},
             {"line": 1, "text": TXT[1], "basis": "direct", "plot": "拔剑", "refs": ["blade", "q1"]},
             {"line": 2, "text": TXT[2], "basis": "inferred", "plot": "念话", "refs": ["voice"]},
             {"line": 3, "text": TXT[3], "basis": "none", "why": "告别, 不对位"}]}}
    dirA = {"id": "A", "name": "王冠", "chosen": True, "motifs": ["gem", "blade", "tower", "rain"], "motion": "上升",
            "palette": [{"hex": "#112233", "from": "アリス"}, {"hex": "#445566", "from": "tower"}], "type_mood": "细明朝",
            "climax": {"lines": [1], "motifs": ["blade"], "treatment": "剑光"},
            "swap_test": {"swap_to": "别的番", "holds": False, "why": "宝石与剑只在本作"}, "reject_reason": ""}
    dirB = {"id": "B", "name": "通用", "chosen": False, "motifs": ["rain", "fire", "leaf"], "motion": "飘落",
            "palette": [{"hex": "#778899", "from": "rain"}, {"hex": "#AABBCC", "from": "fire"}], "type_mood": "楷体",
            "climax": {"lines": [1], "motifs": ["fire"], "treatment": "火"},
            "swap_test": {"swap_to": "任意番", "holds": True, "why": "通用件"}, "reject_reason": "不专属"}
    d["directions.json"] = {"version": 1, "directions": [dirA, dirB]}
    d["landing.json"] = {"version": 1, "gen": ["gen.py"], "items": [
        {"symbol": "gem", "fx": "fx_star", "lines": [0], "marker": '"crown_gem"', "what": "额前红宝石"},
        {"symbol": "blade", "fx": "fx_blade", "lines": [1], "marker": '"silver_blade"', "what": "银剑"},
        {"symbol": "tower", "fx": "fx_star", "lines": [0], "marker": "put(f", "what": "白塔"}]}
    return d


def write(proj, d):
    os.makedirs(os.path.join(proj, "bible"), exist_ok=True)
    open(os.path.join(proj, "lyrics.txt"), "w", encoding="utf-8").write(
        "".join("00:%02d.000 | %s | 译\n" % (10 + i * 4, l) for i, l in enumerate(LYR)))
    tl = [{"line": i, "unit": 0, "mora": 0, "text": "x", "s": 10.0 + i * 4, "e": 12.0 + i * 4} for i in range(4)]
    json.dump(tl, open(os.path.join(proj, "timing.json"), "w"))
    json.dump({"characters": [{"name": "アリス"}, {"name": "ボブ"}]}, open(os.path.join(proj, "anime.background.json"), "w"))
    open(os.path.join(proj, "gen.py"), "w", encoding="utf-8").write(GEN)
    for f, v in d.items():
        json.dump(v, open(os.path.join(proj, "bible", f), "w", encoding="utf-8"), ensure_ascii=False)


def mut(fn):
    d = base()
    fn(d)
    return d


S = lambda d, i: d["symbols.json"]["symbols"][i]     # noqa: E731
D = lambda d, i: d["directions.json"]["directions"][i]   # noqa: E731
L = lambda d, i: d["landing.json"]["items"][i]       # noqa: E731
CASES = [
    ("只有社区来源却标专属", "symbol[blade] 防误传", lambda d: S(d, 1).update(refs=[R("C1")])),
    ("unique=3 来源不足", "symbol[gem] A 级", lambda d: S(d, 0).update(refs=[R("O")])),
    ("只有画面证据却标专属", "symbol[leaf] 仅画面", lambda d: S(d, 6).update(unique=2, unique_why="x")),
    ("引用缺摘句", "symbol[gem] 引用", lambda d: S(d, 0)["refs"].append({"src": "O"})),
    ("角色查无此人", "character[ゾロ] 实名", lambda d: d["characters.json"]["characters"][0].update(name="ゾロ")),
    ("颜色不指向符号", "character[アリス] 色彩", lambda d: d["characters.json"]["characters"][0]["colors"][0].update(symbol="nope")),
    ("逐句对位漏句", "lyric-map 覆盖", lambda d: d["lyric-map.json"]["lines"].pop()),
    ("对位引用不存在的 id", "lyric-map[2] 对位", lambda d: d["lyric-map.json"]["lines"][2].update(refs=["ghost"])),
    ("只发散一套", "directions 数量", lambda d: d["directions.json"]["directions"].pop()),
    ("选定方向换番名仍成立", "direction[A] 专属", lambda d: D(d, 0).update(motifs=["rain", "fire", "leaf", "gem"])),
    ("自评与机械检查矛盾", "direction[B] 自评一致", lambda d: D(d, 1)["swap_test"].update(holds=False)),
    ("高潮没用专属母题", "direction[A] 专属", lambda d: D(d, 0)["climax"].update(motifs=["rain"])),
    ("两套方向只换参数", "directions[A~B] 差异", lambda d: D(d, 1).update(motifs=D(d, 0)["motifs"], motion="上升")),
    ("落地函数不存在", "landing[gem@fx_ghost] 函数", lambda d: L(d, 0).update(fx="fx_ghost")),
    ("marker 不在函数体里", "landing[gem@fx_star] marker", lambda d: L(d, 0).update(marker='"silver_blade"')),
    ("函数没绑到所写的句", "landing[blade@fx_blade] 绑定", lambda d: L(d, 1).update(lines=[2])),
    ("专属落地不足 3 条", "landing 专属落地", lambda d: d["landing.json"]["items"].pop()),
]


def main():
    root = tempfile.mkdtemp(prefix="selftest_bible_")
    fails = 0
    good = os.path.join(root, "good")
    write(good, base())
    res, chain = run(good)
    bad = res.failed()
    print("%s 合格版 0 FAIL%s" % ("ok  " if not bad else "FAIL", "" if not bad else ": %s" % bad[:3]))
    fails += bool(bad)
    for k, (name, want, fn) in enumerate(CASES):
        p = os.path.join(root, "bad%02d" % k)
        write(p, mut(fn))
        got = [r for r in run(p)[0].failed() if r[1].startswith(want)]
        print("%s %s -> %s" % ("ok  " if got else "FAIL", name, want))
        fails += not got
    # 盲审: 没有答卷只报 WARN; 有答卷时计分 (未标定只报 WARN)
    os.makedirs(os.path.join(good, "bible", "blind"), exist_ok=True)
    json.dump({"rounds": [{"packet": "real", "guess": "玩具物语 的片尾"}, {"packet": "real", "guess": "Toy Tale"},
                          {"packet": "real", "guess": "别的"}, {"packet": "decoy", "guess": "不知道"}]},
              open(os.path.join(good, "bible", "blind", "answers.json"), "w", encoding="utf-8"), ensure_ascii=False)
    sc = blind_bible.score(good)
    ok = sc == {"real": (2, 3), "decoy": (0, 1)}
    print("%s 盲审计分 %s" % ("ok  " if ok else "FAIL", sc))
    fails += not ok
    pk = blind_bible.build(__import__("judge.bible_io", fromlist=["Bible"]).Bible(good), good)
    leak = [w for w in ("玩具物语", "アリス", "王冠宝石") if w in pk]
    print("%s 盲审包去名 %s" % ("ok  " if not leak else "FAIL", leak or ""))
    fails += bool(leak)
    if "--keep" in sys.argv:
        print("工程留在 %s" % root)
    else:
        shutil.rmtree(root)
    print("\n%s: %d 项失败" % ("FAILED" if fails else "PASSED", fails))
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
