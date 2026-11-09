# -*- coding: utf-8 -*-
"""自审的重写预算. 规则见 steps/5-verify/16-blind-review/impl/self-review.md.

数字是起始值. 做完两首后按实测调整, 写回本步契约.

单句 (一轮 = 这句被审一次):
  第 1 次不过 -> fix       在原构想内修
  第 2 次不过 -> reanchor  换锚点重写构想. 只调数值不算
  第 3 次不过 -> human     标 "需人判", 不再碰
全局: 合计最多 ROUNDS 轮 (含第 1 轮).
归并: 同一判据在一轮里 MERGE 句以上不过 -> 上游问题. 改风格表或剧本一次, 这些句不占单句次数.
停下转人 (任一):
  1. 第 2 轮后, 不过的句超过全曲 STOP_RATIO (待校准, 不是 hard rule)
  2. 任一高光句两轮不过
  3. ROUNDS 轮用完
"""

ROUNDS = 4
LINE_MAX = 3
MERGE = 3
STOP_RATIO = 0.2          # 待校准: 头几轮可能只是正常学习曲线
CRITERIA = ("intent", "readable", "style", "vs_bar", "unique")
# 判据 -> (MERGE 句以上不过时改一次的上游产物, 做法)
UPSTREAM = {
    "intent": ("judge/arc.json", "构想读不出: 查这些句的锚点与 lines.visual"),
    "readable": ("judge/style.json", "全局的对比或字号规则不对"),
    "style": ("judge/style.json", "风格表没管住画风: 修 palette, line, banned"),
    "vs_bar": ("judge/bar.json", "定标或高光选句不对"),
    "unique": ("judge/arc.json", "高光没锚在本作上: 锚点换成本作 motif 或镜头"),
}
ACTION = {1: "fix", 2: "reanchor"}


def new_state(n, highlights):
    return dict(format="self-review", version=1, round=0, n=n, stop=None, upstream=[],
                lines={str(i): dict(tries=0, status="pending", fails=[], anchors=None,
                                    highlight=i in highlights) for i in range(n)})


def anchor_key(arc_line):
    """一句的锚点, 转成可比较的值. 用来查 reanchor 后锚点真的变了."""
    a = (arc_line or {}).get("anchors") or []
    return sorted(repr(sorted(x.items())) if isinstance(x, dict) else repr(x) for x in a)


def check_reanchor(st, arc_lines):
    """reanchor 的句, 锚点必须已经变了. 返回只调了数值的句."""
    bad = []
    for k, L in st["lines"].items():
        if L["status"] == "reanchor" and L["anchors"] is not None and anchor_key(arc_lines.get(int(k))) == L["anchors"]:
            bad.append(int(k))
    return bad


def apply(st, scored, arc_lines):
    """scored: 本轮审过的句 {line: {判据: True/False}}. 原地更新 st. 返回 [(line, 下一步, 不过的判据)]."""
    if st["stop"]:
        raise SystemExit("自审已停 (%s). 打开验收台" % st["stop"])
    st["round"] += 1
    fails = {i: [c for c, ok in r.items() if ok is False] for i, r in scored.items()}
    count = {}
    for i, fc in fails.items():
        for c in fc:
            count.setdefault(c, []).append(i)
    up = {c: sorted(ls) for c, ls in count.items() if len(ls) >= MERGE}
    out = []
    for c, ls in sorted(up.items()):
        st["upstream"].append(dict(round=st["round"], criterion=c, lines=ls, file=UPSTREAM[c][0], todo=UPSTREAM[c][1]))
    for i in sorted(scored):
        L = st["lines"][str(i)]
        fc = fails[i]
        L["fails"].append(dict(round=st["round"], failed=fc))
        if not fc:
            L["status"] = "pass"
            out.append((i, "pass", []))
            continue
        own = [c for c in fc if c not in up]
        if not own:                           # 只有归并的判据不过: 不占单句次数
            L["status"] = "upstream"
            out.append((i, "upstream", fc))
            continue
        L["tries"] += 1
        L["status"] = ACTION.get(L["tries"], "human")
        if L["status"] == "reanchor":
            L["anchors"] = anchor_key(arc_lines.get(i))
        out.append((i, L["status"], fc))
    _stop(st)
    return out


def _stop(st):
    open_ = [int(k) for k, L in st["lines"].items() if L["status"] not in ("pass", "human")]
    hl2 = [int(k) for k, L in st["lines"].items() if L["highlight"] and L["tries"] >= 2 and L["status"] != "pass"]
    failed = [int(k) for k, L in st["lines"].items() if L["status"] not in ("pass", "pending")]
    if not open_:
        st["stop"] = "done"
    elif hl2:
        st["stop"] = "高光句 %s 两轮不过" % hl2
    elif st["round"] >= 2 and len(failed) > STOP_RATIO * st["n"]:
        st["stop"] = "第 %d 轮后 %d/%d 句不过 (> %d%%, 待校准)" % (
            st["round"], len(failed), st["n"], STOP_RATIO * 100)
    elif st["round"] >= ROUNDS:
        st["stop"] = "%d 轮用完" % ROUNDS
    if st["stop"] and st["stop"] != "done":
        for k in open_:
            st["lines"][str(k)]["status"] = "human"


def todo(st):
    """下一轮要审的句: 没过也没转人的."""
    return sorted(int(k) for k, L in st["lines"].items() if L["status"] not in ("pass", "human"))


def humans(st):
    return sorted(int(k) for k, L in st["lines"].items() if L["status"] == "human")
