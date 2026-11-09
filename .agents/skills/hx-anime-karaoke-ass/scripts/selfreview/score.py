# -*- coding: utf-8 -*-
"""读两份盲审结论, 按剧本与答案判每句的五项: intent / readable / style / vs_bar / unique.

intent/verdict.json:
  {"lines": [{"line": 3, "says": "字像被橡皮擦掉", "points_to": ["学ぶ", "橡皮"],
              "readable": true, "style": true, "vs_bar": "reach", "note": "..."}]}
  says       盲审说这句特效指向什么. 说不出写 "" . 说不出 = 没意义
  points_to  它认为特效指向的词 (歌词里的词, 画面里的东西, 音乐上的点)
  vs_bar     只有高光句写: reach / below
unique/verdict.json:
  {"answers": [{"q": "Q1", "pick": "C", "why": "..."}]}
"""
import json, os, re

from judge.common import load_json

EVENT_WORDS = {
    "onset": ("起音", "鼓点", "重音", "打击", "onset", "hit"),
    "beat": ("节拍", "拍子", "鼓点", "卡点", "beat"),
    "sub": ("低音", "贝斯", "鼓", "sub", "bass"),
    "section": ("段落", "副歌", "进副歌", "转段", "section", "chorus"),
    "mora": ("唱", "字", "音节", "逐字", "mora"),
    "silence": ("停顿", "静默", "空白", "间奏", "silence"),
}
EMPTY = ("", "说不出", "不知道", "看不出", "?", "-")


def _hit(words, said):
    """锚点词与盲审说法的匹配: 任一锚点词出现在说法里, 或说法里的词 (>=2 字) 出现在锚点词里."""
    blob = " ".join(said)
    for w in words:
        if w and w in blob:
            return w
        for s in said:
            if len(s) >= 2 and s in w:
                return w
    return None


def intent_ok(C, i, row):
    says = (row.get("says") or "").strip()
    pts = [p.strip() for p in row.get("points_to") or [] if isinstance(p, str) and p.strip()]
    if (C.arc.get(i) or {}).get("role") == "rest":
        # 留白句: 剧本要求不加特效. 盲审读成空白才对; 读出了东西说明留白没做到 (两个方向都判).
        if says in EMPTY and not pts:
            return True, "留白句: 盲审读成空白, 与剧本一致"
        return False, "留白句: 盲审读成 %s, 剧本要求空白" % (says or pts)
    if says in EMPTY and not pts:
        return False, "盲审说不出这句指向什么"
    words = C.anchor_words(i)
    for a in (C.arc.get(i) or {}).get("anchors") or []:
        if a.get("kind") == "event" and isinstance(a.get("ref"), dict):
            words += list(EVENT_WORDS.get(a["ref"].get("kind"), ()))
    if not words:
        return False, "剧本这句没有可还原的锚点"
    w = _hit(words, [says] + pts)
    if w:
        return True, "还原到 %s" % w
    return False, "盲审读成 %s, 剧本锚点是 %s" % (says or pts, words[:4])


def read_verdicts(C, n):
    rd = C.rdir(n)
    key, err = load_json(os.path.join(rd, "key.json"))
    if err:
        raise SystemExit("第 %d 轮没有 key.json (%s). 先跑 selfreview.py round" % (n, err))
    iv, err = load_json(os.path.join(rd, "intent", "verdict.json"))
    if err:
        raise SystemExit("第 %d 轮缺意图盲审结论 intent/verdict.json (%s)" % (n, err))
    uv, uerr = load_json(os.path.join(rd, "unique", "verdict.json"))
    if key["unique"] and uerr:
        raise SystemExit("第 %d 轮缺专属性盲审结论 unique/verdict.json (%s)" % (n, uerr))
    return key, iv, uv or {"answers": []}


def fullest(C, n, k=3):
    """全曲最满 k 帧是否都在高光句. 每句取它最近一轮的帧 (增量轮只重抽改过的句). 先只给 WARN, 不判不过."""
    rounds = sorted(int(m.group(1)) for m in (re.match(r"r(\d+)$", d) for d in os.listdir(C.dir)) if m)
    by_line = {}                     # line -> 最近一轮的帧
    for r in (r for r in rounds if r <= n):
        frames = (load_json(os.path.join(C.rdir(r), "key.json"))[0] or {}).get("frames") or []
        for i in {f["line"] for f in frames}:
            by_line[i] = [f for f in frames if f["line"] == i]
    rows = [f for fs in by_line.values() for f in fs]
    top = sorted(rows, key=lambda f: (-f["lit"], f["t"]))[:k]
    if not top:
        return dict(level="SKIP", top=[], msg="没有亮像素记录 (旧轮次的 key.json 没有 frames)")
    off = [f for f in top if f["line"] not in C.hl]
    desc = ", ".join("L%02d t=%.2f 亮像素 %d %s" % (f["line"], f["t"], f["lit"], "高光" if f["line"] in C.hl else "非高光")
                     for f in top)
    if not C.hl:
        return dict(level="WARN", top=top, msg="bar.json 没有高光句. 最满 %d 帧: %s" % (len(top), desc))
    if off:
        return dict(level="WARN", top=top, msg="最满 %d 帧有 %d 帧不在高光句: %s. 惊艳来自对比, 查这些句的强度预算"
                    % (len(top), len(off), desc))
    return dict(level="OK", top=top, msg="最满 %d 帧都在高光句: %s" % (len(top), desc))


def score(C, n):
    """返回 ({line: {criterion: bool}}, {line: [说明]})."""
    key, iv, uv = read_verdicts(C, n)
    rows = {r.get("line"): r for r in iv.get("lines", []) if isinstance(r, dict)}
    miss = [i for i in key["lines"] if i not in rows]
    if miss:
        raise SystemExit("意图盲审漏了这些句: %s. 让它补齐, 不要自己填" % miss)
    res, why = {}, {}
    for i in key["lines"]:
        r = rows[i]
        ok, msg = intent_ok(C, i, r)
        res[i] = dict(intent=ok, readable=r.get("readable") is True, style=r.get("style") is True)
        why[i] = [msg]
        if r.get("readable") is not True:
            why[i].append("看不清")
        if r.get("style") is not True:
            why[i].append("不像同一部作品")
        if i in C.hl:
            res[i]["vs_bar"] = r.get("vs_bar") == "reach"
            if not res[i]["vs_bar"]:
                why[i].append("没到参照水平")
        if r.get("note"):
            why[i].append("盲审: %s" % r["note"])
    ans = {a.get("q"): a for a in uv.get("answers", []) if isinstance(a, dict)}
    for q, k in key["unique"].items():
        a = ans.get(q)
        if a is None:
            raise SystemExit("专属性盲审漏了 %s" % q)
        ok = a.get("pick") == k["answer"]
        for i in k["lines"]:
            if i in res:
                res[i]["unique"] = ok
                if not ok:
                    why[i].append("专属性: 盲审认成 %s, 不是本作 (%s). 判套用, 重写" % (a.get("pick"), a.get("why", "")))
    full = fullest(C, n)
    print("%s 全曲最满帧: %s" % (full["level"], full["msg"]))
    json.dump(dict(round=n, result={str(i): r for i, r in res.items()}, why={str(i): w for i, w in why.items()}, fullest=full),
              open(os.path.join(C.rdir(n), "score.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return res, why
