#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""自审 (用户看到之前): 增量抽帧, 两个盲审, 按预算自动重写. 规则见 steps/5-verify/16-blind-review/impl/self-review.md.

  selfreview.py round PROJ [--renderer octopus|ffmpeg] [--fontsdir D] [--decoy-root DIR ..]
      开一轮: 定要审的句 (没过的 + 指纹变了的), 抽帧, 写 rN/intent 与 rN/unique 两份盲审包
  selfreview.py score PROJ
      读本轮两份盲审结论, 判五项, 按预算给每句下一步 (fix / reanchor / human / upstream)
  selfreview.py status PROJ
  selfreview.py gate PROJ [--handoff]
      过关条件: 全部句通过, 或剩下的都是 "需人判". --handoff 把需人判写进验收台 issues (排最前)
退出码: 0 = 通过或命令成功, 1 = 没过, 2 = 用法错误.
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from selfreview import budget as B, packet as PK, score as SC   # noqa: E402
from selfreview.rv import Ctx                                     # noqa: E402


# Agent Notes: v3 判断链: 自审打分
# .agents/notes/implemented/feature/2026-11-09-karaoke-fx-gate-studio.md
def state(C, create=False):
    st = C.load_state()
    if st is None:
        if not create:
            raise SystemExit("还没开过自审. 先跑 selfreview.py round")
        st = B.new_state(C.song.n, C.hl)
        st["hash"] = {}
        st["open_round"] = None
    return st


def cmd_round(C, a):
    st = state(C, create=True)
    if st["stop"]:
        print("自审已结束: %s. 跑 gate" % st["stop"])
        return 1
    if st["open_round"]:
        raise SystemExit("第 %d 轮还没打分. 先跑 selfreview.py score" % st["open_round"])
    only_num = B.check_reanchor(st, C.arc)
    if only_num:
        raise SystemExit("这些句要换锚点重写, 但 arc.json 里锚点没变 (只调数值不算): %s" % only_num)
    cur = C.line_hash()
    lines = PK.lines_to_review(C, st, st["hash"], cur)
    if not lines:
        print("没有要审的句")
        return 0
    n = st["round"] + 1
    roots = a.decoy_root or [os.path.dirname(os.path.dirname(C.proj))]
    rows, qs = PK.build(C, n, lines, a.renderer, roots, a.fontsdir, cur)
    st["open_round"] = n
    C.save_state(st)
    nf = sum(len(r["frames"]) for r in rows)
    print("第 %d 轮: 审 %d 句, %d 帧, 专属性题 %d 道 (高光句 %d 句)" % (n, len(rows), nf, len(qs), len(set(lines) & C.hl)))
    print("意图盲审包: %s" % C.p("r%d" % n, "intent"))
    print("专属性盲审包: %s" % C.p("r%d" % n, "unique"))
    print("各开一个新鲜子代理, prompt 照抄 self-review.md. 结论写回各自目录的 verdict.json")
    return 0


def cmd_score(C, a):
    st = state(C)
    n = st["open_round"]
    if not n:
        raise SystemExit("没有待打分的轮次. 先跑 selfreview.py round")
    res, why = SC.score(C, n)
    key = json.load(open(os.path.join(C.rdir(n), "key.json"), encoding="utf-8"))
    out = B.apply(st, res, C.arc)
    for i in res:
        st["hash"][str(i)] = key["hash"].get(str(i))
    st["open_round"] = None
    C.save_state(st)
    tell = {"pass": "过", "fix": "原构想内修", "reanchor": "换锚点重写构想 (arc.json 的锚点必须变)",
            "human": "需人判, 不再碰", "upstream": "等上游修改"}
    for i, act, fc in out:
        print("L%02d %-9s %s%s" % (i, act, tell[act], ("  [%s] %s" % (",".join(fc), "; ".join(why[i]))) if fc else ""))
    for u in st["upstream"]:
        if u["round"] == st["round"]:
            print("归并: %s 在 %d 句不过 -> 改 %s 一次: %s" % (u["criterion"], len(u["lines"]), u["file"], u["todo"]))
    print("第 %d 轮: 过 %d / 审 %d" % (st["round"], sum(1 for x in out if x[1] == "pass"), len(out)))
    if st["stop"]:
        print("停: %s. 跑 gate" % st["stop"])
    return 0


def cmd_status(C, a):
    st = state(C)
    cnt = {}
    for L in st["lines"].values():
        cnt[L["status"]] = cnt.get(L["status"], 0) + 1
    print("轮次 %d / %d, 待打分 %s, 停: %s" % (st["round"], B.ROUNDS, st["open_round"], st["stop"]))
    print("  " + ", ".join("%s %d" % kv for kv in sorted(cnt.items())))
    return 0


def cmd_gate(C, a):
    st = state(C)
    left = [int(k) for k, L in st["lines"].items() if L["status"] not in ("pass", "human")]
    hum = B.humans(st)
    if st["open_round"] or left:
        print("FAIL 还没审完: 未过 %s, 待打分轮 %s" % (left, st["open_round"]))
        return 1
    print("PASS 自审结束 (%s). 需人判 %d 句: %s" % (st["stop"], len(hum), hum))
    if a.handoff and hum:
        handoff(C, st, hum)
    return 0


def handoff(C, st, hum):
    """需人判写进验收台 issues, status=need-human, 附最后一轮的盲审意见. 候选 (2 个) 在台子那一步生成."""
    from accept.issues import Issues
    from assdoc.spec import load_manifest
    man = load_manifest(C.proj) or {}
    iss = Issues(os.path.join(C.proj, "review", "accept"))
    have = {(it.get("sel") or {}).get("unit") for it in iss.items if it["status"] == "need-human"}
    for i in hum:
        last = max((r for r in range(1, st["round"] + 1) if os.path.exists(os.path.join(C.rdir(r), "score.json"))
                    and str(i) in json.load(open(os.path.join(C.rdir(r), "score.json"), encoding="utf-8"))["why"]), default=None)
        why = json.load(open(os.path.join(C.rdir(last), "score.json"), encoding="utf-8"))["why"][str(i)] if last else []
        for u in C.units_of(i, man) or [None]:
            if u in have:
                continue
            it = iss.add(dict(unit=u, line=i), "bad", say="自审: " + "; ".join(why))
            it["status"] = "need-human"
            it["from"] = "self-review"
    iss.save()
    print("已写进验收台 issues: %d 句需人判 (台子打开时排最前, 每条要配 2 个候选)" % len(hum))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("round", "score", "status", "gate"))
    ap.add_argument("proj")
    ap.add_argument("--ass", default="out.ass")
    ap.add_argument("--renderer", choices=("octopus", "ffmpeg"), default="octopus")
    ap.add_argument("--fontsdir")
    ap.add_argument("--decoy-root", action="append")
    ap.add_argument("--handoff", action="store_true")
    a = ap.parse_args()
    C = Ctx(a.proj, a.ass)
    return dict(round=cmd_round, score=cmd_score, status=cmd_status, gate=cmd_gate)[a.cmd](C, a)


if __name__ == "__main__":
    sys.exit(main())
