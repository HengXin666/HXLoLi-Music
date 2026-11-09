#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""自审自测: 用 judge 自测的 6 句玩具工程 + 4 个干扰工程, ffmpeg 出帧. 盲审结论由本脚本按场景写入.

  hx-karaoke selfreview/selftest_selfreview.py [--keep]
"""
import json, os, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from judge import selftest_judge as J      # noqa: E402
from selfreview import budget as B         # noqa: E402

N_OK = [0]
FAILS = []


def ck(cond, name, info=""):
    print("%s %s%s" % ("PASS" if cond else "FAIL", name, ("  " + str(info)[:300]) if not cond and info else ""))
    (N_OK.__setitem__(0, N_OK[0] + 1) if cond else FAILS.append(name))


def sr(*a):
    r = subprocess.run([sys.executable, os.path.join(HERE, "selfreview.py")] + list(a), capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


BOX = "{\\an7\\pos(100,100)\\p1}m 0 0 l 1600 0 1600 800 0 800{\\p0}"


def ass(proj, tag="", box=None):
    """box: 给这一句加一个满屏方块 (测最满帧)."""
    ev = "".join("Dialogue: 0,0:00:%05.2f,0:00:%05.2f,Default,,0,0,0,,{\\an5\\pos(960,540)}%s%s\n"
                 % (t, t + 2.5, J.TXT[i], tag if i == 0 else "") for i, t in enumerate(J.T0))
    if box is not None:
        ev += "Dialogue: 1,0:00:%05.2f,0:00:%05.2f,Default,,0,0,0,,%s\n" % (J.T0[box], J.T0[box] + 2.5, BOX)
    open(os.path.join(proj, "out.ass"), "w", encoding="utf-8").write(
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\n\n[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, "
        "MarginV, Encoding\nStyle: Default,Sans,60,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,5,0,0,0,1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n" + ev)


def make(root, name):
    proj = os.path.join(root, "a", name)
    J.write(proj, J.base())
    ass(proj)
    return proj


def verdict(proj, n, rows, picks=None):
    """rows: {line: (says, points_to, readable, style, vs_bar)}. picks: {hl id: True(对)/False(错)}."""
    rd = os.path.join(proj, "judge", "review", "r%d" % n)
    key = json.load(open(os.path.join(rd, "key.json"), encoding="utf-8"))
    pk = json.load(open(os.path.join(rd, "intent", "packet.json"), encoding="utf-8"))
    arc = json.load(open(os.path.join(proj, "judge", "arc.json"), encoding="utf-8"))
    rest = {r["line"] for r in arc["lines"] if r.get("role") == "rest"}
    out = []
    for r in pk["lines"]:
        i = r["line"]
        good = ("", [], True, True, None) if i in rest else ("意象", ["意象%d" % i], True, True, "reach")
        says, pts, rd_, st, vb = rows.get(i, good)
        out.append(dict(line=i, says=says, points_to=pts, readable=rd_, style=st, vs_bar=vb))
    json.dump(dict(lines=out), open(os.path.join(rd, "intent", "verdict.json"), "w", encoding="utf-8"), ensure_ascii=False)
    ans = []
    for q, k in key["unique"].items():
        good = (picks or {}).get(k["hl"], True)
        ans.append(dict(q=q, pick=k["answer"] if good else next(c for c in "ABCDE" if c != k["answer"]), why="-"))
    json.dump(dict(answers=ans), open(os.path.join(rd, "unique", "verdict.json"), "w", encoding="utf-8"), ensure_ascii=False)
    return pk


def st_of(proj):
    return json.load(open(os.path.join(proj, "judge", "review", "state.json"), encoding="utf-8"))


def scen_a(root):
    p = make(root, "song")
    c, o = sr("round", p, "--renderer", "ffmpeg")
    rd = os.path.join(p, "judge", "review", "r1")
    pk = json.load(open(os.path.join(rd, "intent", "packet.json"), encoding="utf-8"))
    uq = json.load(open(os.path.join(rd, "unique", "packet.json"), encoding="utf-8"))
    ck(c == 0 and len(pk["lines"]) == 6, "第 1 轮审全部 6 句", o)
    nf = sum(len(r["frames"]) for r in pk["lines"])
    ck(nf == 12, "高光句 3 帧, 其他 1 帧 (共 12)", nf)
    ck(all(os.path.getsize(os.path.join(rd, "intent", f)) > 0 for r in pk["lines"] for f in r["frames"]), "帧文件真实落盘")
    ck(len(uq["questions"]) == 3 and all(len(q["cards"]) == 5 for q in uq["questions"]), "专属性 3 题, 每题 5 张作品卡")
    blob = open(os.path.join(rd, "intent", "packet.json"), encoding="utf-8").read() + json.dumps(uq, ensure_ascii=False)
    ck(not any(w in blob for w in ("构想", "star-burst", "feather-sweep", "anchors", "answer")), "盲审包里没有剧本与答案")
    ck(not os.path.exists(os.path.join(rd, "intent", "key.json")), "答案不在盲审包目录里")
    verdict(p, 1, {1: ("", [], True, True, None), 2: ("字后有光环", ["光环"], True, True, None),
                   3: ("意象", ["意象3"], True, True, "below")}, {"h3": False})
    c, o = sr("score", p)
    s = st_of(p)["lines"]
    got = {i: s[str(i)]["status"] for i in range(6)}
    ck(got == {0: "pass", 1: "fix", 2: "fix", 3: "fix", 4: "fix", 5: "pass"}, "第 1 轮: 读错/说不出/没到参照/认不出本作都判不过", got)
    ck("盲审读成" in o and "说不出" in o and "认成" in o and "留白句" in o, "不过的句写明原因", o)
    ass(p, "x")                      # 改第 0 句的事件: 已过的句指纹变了, 要复审
    c, o = sr("round", p, "--renderer", "ffmpeg")
    pk2 = json.load(open(os.path.join(p, "judge", "review", "r2", "intent", "packet.json"), encoding="utf-8"))
    ck(sorted(r["line"] for r in pk2["lines"]) == [0, 1, 2, 3, 4], "第 2 轮增量: 没过的 + 指纹变了的, 第 5 句不重抽", o)
    verdict(p, 2, {3: ("意象", ["意象3"], True, True, "below")})
    c, o = sr("score", p)
    S = st_of(p)
    ck(S["stop"] and "高光句" in S["stop"] and S["lines"]["3"]["status"] == "human", "高光句两轮不过: 停, 转人", S["stop"])
    c, o = sr("round", p, "--renderer", "ffmpeg")
    ck(c == 1 and "已结束" in o, "停了以后不再开轮次", o)
    c, o = sr("gate", p, "--handoff")
    iss = json.load(open(os.path.join(p, "review", "accept", "issues.json"), encoding="utf-8"))
    ck(c == 0 and [it["status"] for it in iss["items"]] == ["need-human"] and iss["items"][0]["sel"]["line"] == 3,
       "gate 过, 需人判写进验收台 issues", o)
    ck("没到参照水平" in iss["items"][0]["say"], "需人判附盲审意见", iss["items"][0]["say"])


def scen_b(root):
    p = make(root, "merge")
    sr("round", p, "--renderer", "ffmpeg")
    verdict(p, 1, {i: ("意象" if i != 2 else "", ["意象%d" % i] if i != 2 else [], True, False, "reach") for i in (0, 1, 2)})
    c, o = sr("score", p)
    s = st_of(p)
    ck([s["lines"][str(i)]["status"] for i in (0, 1, 2)] == ["upstream"] * 3 and all(s["lines"][str(i)]["tries"] == 0 for i in (0, 1, 2)),
       "同一判据 3 句不过: 归并为上游问题, 不占单句次数", s["lines"]["0"])
    ck("style.json" in o and "归并" in o, "归并指到风格表", o)


def scen_c(root):
    p = make(root, "anchor")
    bad = {1: ("下雨", ["雨"], True, True, None)}
    for n in (1, 2):
        sr("round", p, "--renderer", "ffmpeg")
        verdict(p, n, bad)
        sr("score", p)
    ck(st_of(p)["lines"]["1"]["status"] == "reanchor", "单句两轮不过: 换锚点")
    c, o = sr("round", p, "--renderer", "ffmpeg")
    ck(c != 0 and "锚点没变" in o, "锚点没变就拒绝开下一轮 (只调数值不算)", o)
    arc_p = os.path.join(p, "judge", "arc.json")
    arc = json.load(open(arc_p, encoding="utf-8"))
    arc["lines"][1]["anchors"] = [{"kind": "motif", "ref": "星辰"}]
    json.dump(arc, open(arc_p, "w", encoding="utf-8"), ensure_ascii=False)
    c, o = sr("round", p, "--renderer", "ffmpeg")
    ck(c == 0, "换了锚点后可以开第 3 轮", o)
    verdict(p, 3, {1: ("下雨", ["雨"], True, True, None)})
    sr("score", p)
    S = st_of(p)
    ck(S["lines"]["1"]["status"] == "human" and S["stop"] == "done", "第 3 轮不过: 需人判, 其余全过即结束", S["stop"])


def scen_d(root):
    p = make(root, "ratio")
    bad = {1: ("", [], True, True, None), 5: ("", [], True, True, None)}
    for n in (1, 2):
        sr("round", p, "--renderer", "ffmpeg")
        verdict(p, n, bad)
        sr("score", p)
    S = st_of(p)
    ck(S["stop"] and "待校准" in S["stop"], "第 2 轮后不过超过 20%: 停 (待校准)", S["stop"])
    p2 = make(root, "miss")
    sr("round", p2, "--renderer", "ffmpeg")
    verdict(p2, 1, {})
    vp = os.path.join(p2, "judge", "review", "r1", "intent", "verdict.json")
    v = json.load(open(vp, encoding="utf-8"))
    v["lines"] = v["lines"][1:]
    json.dump(v, open(vp, "w", encoding="utf-8"), ensure_ascii=False)
    c, o = sr("score", p2)
    ck(c != 0 and "漏了" in o, "盲审漏句: 拒绝打分", o)


def scen_e(root):
    """最满 3 帧: 落在普通句给 WARN (不判不过); 都在高光句给 OK."""
    got = []
    for name, box in (("full_bad", 1), ("full_ok", 0)):
        p = make(root, name)
        ass(p, box=box)
        sr("round", p, "--renderer", "ffmpeg")
        verdict(p, 1, {})
        c, o = sr("score", p)
        sc = json.load(open(os.path.join(p, "judge", "review", "r1", "score.json"), encoding="utf-8"))["fullest"]
        got.append((c, sc["level"], sc["top"][0]["line"], st_of(p)["lines"]["1"]["status"], "全曲最满帧" in o))
    ck(got == [(0, "WARN", 1, "pass", True), (0, "OK", 0, "pass", True)],
       "全曲最满 3 帧: 普通句最满给 WARN 不判不过, 都在高光句给 OK", got)


def unit_rounds():
    st = B.new_state(20, set())
    for _ in range(4):
        if st["stop"]:
            break
        B.apply(st, {i: dict(style=False) for i in (0, 1, 2)} | {i: dict(style=True) for i in range(3, 20) if st["round"] == 0}, {})
    ck(st["round"] == 4 and "轮用完" in (st["stop"] or ""), "全局 4 轮用完: 停", st["stop"])


def unit_rest():
    """留白句 (arc role=rest): 盲审读成空白算过; 读出特效算不过."""
    from selfreview import score as SC

    class C:
        arc = {5: dict(role="rest", anchors=[])}
        def anchor_words(self, i):
            return []
    ok, _ = SC.intent_ok(C(), 5, dict(says="", points_to=[]))
    ck(ok, "留白句读成空白: 过")
    ok, _ = SC.intent_ok(C(), 5, dict(says="字后有光环", points_to=["光环"]))
    ck(not ok, "留白句被读出特效: 不过")


def main():
    keep = "--keep" in sys.argv
    root = tempfile.mkdtemp(prefix="selfreview-")
    for k in range(4):
        d = os.path.join(root, "a", "decoy%d" % k)
        os.makedirs(d)
        open(os.path.join(d, "anime.elements.md"), "w", encoding="utf-8").write("| **元素%d甲** | 2 |\n| **元素%d乙** | 2 |\n" % (k, k))
    for f in (scen_a, scen_b, scen_c, scen_d, scen_e):
        f(root)
    unit_rounds()
    unit_rest()
    print("\n%d/%d PASS" % (N_OK[0], N_OK[0] + len(FAILS)))
    print("临时目录: %s" % root) if keep else shutil.rmtree(root, ignore_errors=True)
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
