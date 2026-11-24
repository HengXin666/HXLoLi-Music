#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验收台的命令行 (v3): "好" 的冻结, G2 改代码核对, issues 读写. 规则见 steps/5-verify/12-station/impl/.

  accept.py init PROJ [--gen make_ass.py --raw out.raw.ass --out out.ass]
  accept.py units PROJ [--grep 文字]                列出单元, 句单元带字下标
  accept.py good PROJ --unit K [--chars 2-5] [--t 10.5-12] [--issue I3] [--note ..]
  accept.py goods PROJ                              每条 "好" 的状态 (ok / touched / stale)
  accept.py unfreeze PROJ G2
  accept.py issue PROJ --unit K --action bad [--tag 看不清] [--say ..] [--chars ..] [--t ..] [--frame 12.3]
  accept.py issues PROJ [--open]                    列出问题与根因层; 同标签 3 处以上提示归并
  accept.py where PROJ I3                           问题 -> 单元, 函数, 源文件, 剧本条目, 波及的 "好"
  accept.py begin PROJ                              改代码前: 存基准 (raw + 清单 + 工程 .py)
  accept.py predict PROJ [--scope K1,K2]            改代码后, 重跑前: 预测影响集与波及的 "好"
  accept.py verify PROJ --scope K1,K2 [--declare K3 --why ..]   重跑生成器 + 三条硬核对, 通过才构建
  accept.py resolve PROJ I3 --diag .. --change .. [--status proposed|need-human|..] [--candidates A,B]
  accept.py build PROJ                              out.ass = 冻结快照(raw); 旧 out.ass 留作 review/accept/prev.ass (台子 "对比上一版")
  accept.py intake PROJ                             review.jsonl 里还没挂问题的标注 -> issues (bad/redo/good), 回写状态
  accept.py sync PROJ                               按 issues 回写 review.jsonl 每条标注的 status 与 changes
  accept.py cands PROJ I3 [--n 3]                   换一个构想: 只重跑本单元出 2-3 个候选 (cands/I3/A.ass ..)
  accept.py pick PROJ I3 --choice B                 选中 B: 写 picks.json -> 整首重跑 -> G2 三条 + 隔离核对 -> 冻结; 未选进构想记录
  accept.py ideas PROJ [--unit K]                   构想记录 (未选中的候选)
"""
import argparse, json, os, shutil, subprocess, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from accept import cands as C, g2, reviewlog as RL, sel as S   # noqa: E402
from accept.goods import Goods                        # noqa: E402
from accept.issues import Issues, ROUTE               # noqa: E402
from assdoc.assdoc import AssDoc                      # noqa: E402
from assdoc.spec import load_manifest, manifest_path  # noqa: E402

SUB = os.path.join("review", "accept")
SKIP = ("review", "out", "stems", "__pycache__", ".git")


class Proj:
    def __init__(self, proj):
        self.proj = os.path.abspath(proj)
        self.dir = os.path.join(self.proj, SUB)
        self.base = os.path.join(self.dir, "base")
        sp = os.path.join(self.dir, "state.json")
        self.st = json.load(open(sp, encoding="utf-8")) if os.path.exists(sp) else None

    def p(self, rel):
        return os.path.join(self.proj, rel)

    def need(self):
        if not self.st:
            raise SystemExit("先跑 accept.py init %s" % self.proj)
        return self.st

    def save(self):
        os.makedirs(self.dir, exist_ok=True)
        json.dump(self.st, open(os.path.join(self.dir, "state.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    @property
    def raw(self):
        return self.p(self.need()["raw"])

    def man(self, raw=None):
        m = load_manifest(raw or self.raw)
        if m is None:
            raise SystemExit("raw 旁没有清单, 先跑生成器 (accept.py verify 或直接跑一次)")
        return m

    def regen(self, out=None):
        env = dict(os.environ)
        env.setdefault("ASSFX", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        env.pop("ASSFX_OVERRIDES", None); env.pop("ASSFX_TRACE", None); env.pop("ASSFX_ONLY", None)
        if os.path.exists(C.picks_path(self.dir)):        # 台上选中的候选参数: 生成器的真输入 (cands.py)
            env["ASSFX_OVERRIDES"] = C.picks_path(self.dir)
        r = subprocess.run([sys.executable, self.p(self.need()["gen"]), out or self.raw], cwd=self.proj, env=env,
                           capture_output=True, text=True)
        if r.returncode:
            raise SystemExit("生成器失败:\n" + r.stdout[-1500:] + r.stderr[-1500:])

    def goods(self):
        return Goods(self.dir)

    def issues(self):
        return Issues(self.dir)

    def review_path(self):
        return RL.path_of(self.proj)

    def sync(self):
        """issues 的状态回写到 review.jsonl (挂了 issue 的标注)."""
        return RL.sync(self.review_path(), self.issues())


# Agent Notes: 逐单元验收 (v3 判断链的 accept 段)
# .agents/notes/implemented/feature/2026-11-09-karaoke-fx-gate-studio.md
def rng(s, typ):
    if not s:
        return None
    a, b = s.split("-", 1) if typ is int else s.rsplit("-", 1)
    return [typ(a), typ(b) + (1 if typ is int else 0)]      # 字下标写闭区间 2-5, 存成半开 [2, 6)


def sel_of(a):
    return dict(unit=a.unit, chars=rng(a.chars, int), t=rng(a.t, float), layer=getattr(a, "layer", None))


def copy_src(src, dst):
    if os.path.exists(dst):
        shutil.rmtree(dst)
    for dp, dn, fn in os.walk(src):
        dn[:] = [d for d in dn if d not in SKIP]
        for f in fn:
            if f.endswith(".py"):
                rel = os.path.relpath(os.path.join(dp, f), src)
                os.makedirs(os.path.dirname(os.path.join(dst, rel)), exist_ok=True)
                shutil.copy2(os.path.join(dp, f), os.path.join(dst, rel))


def cmd_init(P, a):
    P.st = dict(format="accept-state", version=1, gen=a.gen, raw=a.raw, out=a.out)
    P.save()
    if not os.path.exists(P.raw) or load_manifest(P.raw) is None:
        P.regen()
    print("init ok:", P.st)


def cmd_units(P, a):
    for u in P.man()["units"]:
        lab = u.get("label") or u["name"]
        if a.grep and a.grep not in lab and a.grep not in "".join(c[0] for c in u.get("chars") or []):
            continue
        cs = " ".join("%d%s" % (j, c[0]) for j, c in enumerate(u.get("chars") or []))
        print("%-22s %-6s %7.2f-%7.2f  %s%s" % (u["key"], u["kind"], u["t"][0], u["t"][1], lab[:30], ("\n" + " " * 24 + cs) if cs else ""))


def cmd_good(P, a):
    raw, man = AssDoc.load(P.raw), P.man()
    g, clash = P.goods().mark(raw, man, sel_of(a), a.issue, a.note or "")
    print("冻结 %s: %s, %d 个事件, 实际范围 %s" % (g["id"], S.label(g["sel"], man), g["n"],
                                           "整句" if g["cover"] == "all" else "字 %s" % g["cover"]))
    if clash:
        print("WARN 同一单元已有 \"好\": %s" % clash)


def cmd_goods(P, a):
    G = P.goods()
    raw, man = AssDoc.load(P.raw), P.man()
    for gid, (s, m) in G.status(raw, man).items():
        g = G.get(gid)
        print("%-4s %-8s %s %s %s" % (gid, s, S.label(g["sel"], man), "整句" if g["cover"] == "all" else g["cover"], m))
    if not G.items:
        print("(没有 \"好\")")


def cmd_unfreeze(P, a):
    g = P.goods().remove(a.id)
    print("撤掉 \"好\" %s (%s)" % (g["id"], g["sel"]["unit"]))


def cmd_issue(P, a):
    man = P.man()
    S.pick(AssDoc.load(P.raw), man, sel_of(a))         # 选区要能落到清单单元上
    it = P.issues().add(sel_of(a), a.action, a.tag, a.say or "", a.frame, a.choice, a.of)
    print("记下 %s: %s %s %s" % (it["id"], a.action, a.tag or "", S.label(it["sel"], man)))
    if a.action == "good":
        cmd_good(P, argparse.Namespace(**dict(vars(a), issue=it["id"], note=a.say)))
    P.sync()


def cmd_issues(P, a):
    I = P.issues()
    man = P.man()
    for it in I.items:
        if a.open and it["status"] not in ("open", "fixing", "need-human"):
            continue
        layer = I.route(it)[0] if it["action"] in ("bad", "another") else "-"
        print("%-4s %-10s %-7s %-6s %-6s %s %s" % (it["id"], it["status"], it["action"], it.get("tag") or "", layer,
                                                  S.label(it["sel"], man), it.get("say") or ""))
    for t, ids in I.merged().items():
        print("WARN 标签 %s 出现 %d 处 (%s): 按全局问题处理, 改风格表或剧本" % (t, len(ids), ",".join(ids)))


def cmd_where(P, a):
    I = P.issues(); it = I.get(a.id)
    man = P.man(); u = S.units(man).get(it["sel"]["unit"]) or {}
    layer, art, how = I.route(it)
    print("问题 %s: %s %s\n根因层: %s  先看: %s  做法: %s" % (it["id"], it["action"], it.get("tag") or "", layer, art or "-", how))
    fns = (man.get("code") or {}).get("fns", {})
    print("单元 %s, 发出事件的函数:" % u.get("key"))
    for k, d in sorted((u.get("emit") or {}).items(), key=lambda kv: -kv[1]["n"]):
        f = fns.get(k) or {}
        print("  %-40s %4d 个事件, 层 %s, %s 第 %s 行" % (k, d["n"], d["layers"], f.get("file", "库"), f.get("line", "-")))
    print("deps.code:", (u.get("deps") or {}).get("code"))
    arc = os.path.join(P.proj, "judge", "arc.json")
    if os.path.exists(arc) and u.get("lines"):
        rows = [r for r in json.load(open(arc, encoding="utf-8")).get("lines", []) if r.get("line") in u["lines"]]
        for r in rows:
            print("剧本 line %s: %s / %s / %s" % (r.get("line"), r.get("role"), r.get("technique"), r.get("idea")))
    hit = P.goods().units_hit([u.get("key")] + list((u.get("deps") or {}).get("window") or []))
    print("同单元或下一句的 \"好\":", [g["id"] for g in hit] or "无")


def cmd_begin(P, a):
    os.makedirs(P.base, exist_ok=True)
    shutil.copy(P.raw, os.path.join(P.base, "raw.ass"))
    shutil.copy(manifest_path(P.raw), os.path.join(P.base, "manifest.json"))
    copy_src(P.proj, os.path.join(P.base, "src"))
    bp = os.path.join(P.base, C.PICKS)
    if os.path.exists(C.picks_path(P.dir)):
        shutil.copy(C.picks_path(P.dir), bp)
    elif os.path.exists(bp):
        os.remove(bp)
    print("基准已存. 现有 \"好\":", [(g["id"], g["sel"]["unit"]) for g in P.goods().items] or "无")


def base_man(P):
    p = os.path.join(P.base, "manifest.json")
    if not os.path.exists(p):
        raise SystemExit("没有基准: 改代码前先跑 accept.py begin")
    return json.load(open(p, encoding="utf-8"))


def cmd_predict(P, a):
    pr = g2.predict(base_man(P), os.path.join(P.base, "src"), P.proj, P.base, P.dir)
    print("改了的函数:", pr["fns"] or "无")
    for w in pr["why"]:
        print("  ", w)
    print("预测影响集 (%d):" % len(pr["units"]), pr["units"])
    hit = P.goods().units_hit(pr["units"])
    print("波及的 \"好\":", ["%s(%s)" % (g["id"], g["sel"]["unit"]) for g in hit] or "无")
    scope = set(a.scope.split(",")) if a.scope else set()
    if scope and set(pr["units"]) - scope:
        print("WARN 影响集超出问题范围: %s. 默认分叉共用函数; 确要全局改就在 verify 时 --declare 并写 --why"
              % sorted(set(pr["units"]) - scope))
    return pr


def cmd_verify(P, a):
    bm = base_man(P)
    pred = g2.predict(bm, os.path.join(P.base, "src"), P.proj, P.base, P.dir)
    old = AssDoc.load(os.path.join(P.base, "raw.ass"))
    scope = [k for k in (a.scope or "").split(",") if k]
    declared = [k for k in (a.declare or "").split(",") if k]
    if declared and not a.why:
        raise SystemExit("--declare 要写 --why (为什么必须全局改)")
    P.regen()
    new, nm = AssDoc.load(P.raw), P.man()
    fail, rep = g2.verify(old, bm, new, nm, pred, scope, declared, P.goods())
    extra = getattr(a, "check", None)
    if not fail and extra:
        fail += extra(new, nm)                        # pick 的隔离核对: 整首输出的本单元 == 候选快照
    print(json.dumps(rep, ensure_ascii=False))
    if fail:
        restore(P)
        for f in fail:
            print("FAIL", f)
        print("raw 已恢复为基准; 这次的输出留在 review/accept/base/fail.ass")
        if getattr(a, "soft", False):
            return fail, rep
        sys.exit(1)
    if declared:
        print("全局改动已声明: %s. 理由: %s. 这些句子要全部重跑自审" % (declared, a.why))
    cmd_build(P, a)
    cmd_begin(P, a)        # 通过后新输出成为下一次的基准
    return [], rep


def restore(P):
    shutil.copy(P.raw, os.path.join(P.base, "fail.ass"))
    shutil.copy(os.path.join(P.base, "raw.ass"), P.raw)
    shutil.copy(os.path.join(P.base, "manifest.json"), manifest_path(P.raw))
    bp = os.path.join(P.base, C.PICKS)
    if os.path.exists(bp):
        shutil.copy(bp, C.picks_path(P.dir))
    elif os.path.exists(C.picks_path(P.dir)):
        os.remove(C.picks_path(P.dir))


def cmd_resolve(P, a):
    it = P.issues().resolve(a.id, a.diag, a.change, a.status, a.candidates.split(",") if a.candidates else None)
    print("%s -> %s (第 %d 次)" % (it["id"], it["status"], it["tries"]))
    P.sync()


def cmd_build(P, a):
    raw, man = AssDoc.load(P.raw), P.man()
    G = P.goods()
    doc = G.apply(raw, man)
    out = P.p(P.need()["out"])
    if os.path.exists(out):                           # 上一版: 台子没有参考 ASS 时的对比对象
        shutil.copy(out, os.path.join(P.dir, "prev.ass"))
    doc.write(out)
    om = manifest_path(out)                           # 台子读 out 旁的清单; 与 raw 同一份
    if os.path.abspath(om) != os.path.abspath(manifest_path(P.raw)):
        shutil.copy(manifest_path(P.raw), om)
    for k, why in C.stale_picks(P.dir, man):
        print("WARN pick 过期: %s %s. 台上重看这一句再选" % (k, why))
    bad = {k: v for k, v in G.status(raw, man).items() if v[0] != "ok"}
    print("构建 %s: %d 个事件, %d 条 \"好\"%s" % (P.st["out"], len(doc.events), len(G.items),
                                         "; 需要看: %s" % bad if bad else ""))


def cmd_intake(P, a):
    """review.jsonl -> issues. 每条只收一次 (回写 issue id); note 记 noted. 好 = 冻结 (同 issue --action good)."""
    man = P.man()
    I = P.issues()
    have = {it.get("review") for it in I.items}
    patches = {}
    for r in RL.records(P.review_path()):
        if r["id"] in have or r.get("issue"):
            continue
        if r.get("kind") == "note":
            if "status" not in r:
                patches[r["id"]] = dict(status="noted", changes=[])
            continue
        sels = RL.sel_of(man, r)
        if not sels:
            patches[r["id"]] = dict(status="dropped", changes=[dict(status="dropped", what="选区落不到清单单元上 (歌词改过?)")])
            continue
        act = RL.KIND2ACTION[r["kind"]]
        tag = next((t for t in r.get("tags") or [] if t in ROUTE), None) if act == "bad" else None
        say = r.get("text") or " ".join(t for t in r.get("tags") or [] if t != tag)
        it = I.add(sels if len(sels) > 1 else sels[0], act, tag, say, r.get("frame"))
        it["review"] = r["id"]
        I.save()
        if act == "good":
            raw = AssDoc.load(P.raw)
            for s in I.sels(it):
                P.goods().mark(raw, man, s, it["id"], say)
        print("收下标注 %s -> %s %s %s" % (r["id"], it["id"], act, S.label(it["sel"], man)))
    RL.update(P.review_path(), patches)
    print("回写 %d 行" % P.sync())


def cmd_sync(P, a):
    print("回写 %d 行" % P.sync())


def cmd_cands(P, a):
    rec = C.generate(P, a.id, int(a.n or 3))
    print("候选 %s: %s (%.1fs, 只重跑单元 %s)" % (a.id, [c["id"] for c in rec["items"]], rec["secs"], rec["unit"]))
    if rec["siblings"]:
        print("注意: 重复歌词, 同文字的单元还有 %s; 候选只改 %s" % (rec["siblings"], rec["unit"]))
    P.sync()


def cmd_pick(P, a):
    """选中候选: picks.json 写参数 -> verify (整首重跑, G2 三条 + 隔离核对) -> 冻结 "好" -> 未选进构想记录."""
    rec = C.load(P, a.id)
    c = next((x for x in rec["items"] if x["id"] == a.choice), None)
    if c is None:
        raise SystemExit("%s 没有候选 %s (有 %s)" % (a.id, a.choice, [x["id"] for x in rec["items"]]))
    I = P.issues()
    it = I.get(a.id)
    key = rec["unit"]
    hit = P.goods().units_hit([key])
    if hit:
        raise SystemExit("A: 单元 %s 已有 \"好\" %s, 先 accept.py unfreeze 再选" % (key, [g["id"] for g in hit]))
    man = P.man()
    u = S.units(man).get(key) or {}
    if u.get("fp") != rec.get("fp"):
        raise SystemExit("候选生成后本句输入变了 (fp 不同): 重新生成候选")
    cmd_begin(P, a)
    pk = C.load_picks(P.dir)
    pk.setdefault("units", {})[key] = dict(params=c["params"], fp=u.get("fp"), label=u.get("label"),
                                           issue=a.id, cand=c["id"], why=c["why"], at=time.strftime("%Y-%m-%d %H:%M:%S"))
    C.save_picks(P.dir, pk)
    want = S.lines(AssDoc.load(os.path.join(I.cand_dir(a.id), c["id"] + ".unit.ass")).events)

    def iso(new, nm):
        got = S.lines(S.pick(new, nm, dict(unit=key))[0])
        if got != want:
            return ["隔离核对: 整首重跑的 %s 与候选 %s 只重跑单元的输出不同 (%d vs %d 行). 单元间有隐式状态, 修追踪" %
                    (key, c["id"], len(got), len(want))]
        return []
    va = argparse.Namespace(**dict(vars(a), scope=key, declare="", why=None, check=iso, soft=True))
    fail, rep = cmd_verify(P, va)
    I = P.issues()
    it = I.get(a.id)
    if fail:
        I.resolve(a.id, "选 %s 后 G2 未过" % c["id"], "; ".join(fail)[:300], "need-human")
        I.get(a.id)["history"][-1]["g2"] = dict(ok=False, fail=fail)
        I.save()
        P.sync()
        print("PICK FAIL")
        sys.exit(1)
    g, _ = P.goods().mark(AssDoc.load(P.raw), P.man(), dict(unit=key), a.id, "选中候选 %s" % c["id"])
    cmd_build(P, a)
    cmd_begin(P, a)
    left = C.record_ideas(P, rec, c["id"], it)
    it = I.get(a.id)
    it["picked"] = c["id"]
    I.resolve(a.id, "选中候选 %s (%s)" % (c["id"], c["why"]), "picks.json[%s] = %s; 冻结 %s" % (key, json.dumps(c["params"], ensure_ascii=False), g["id"]), "done")
    h = I.get(a.id)["history"][-1]
    h.update(picked=c["id"], good=g["id"], ideas=left,
             g2=dict(ok=True, changed=rep["changed"], predicted=rep["predicted"], scope=rep["scope"], isolation="ok"))
    I.save()
    P.sync()
    print("PICK OK %s -> %s, 冻结 %s, 构想记录 %s. G2: changed=%s" % (a.id, c["id"], g["id"], left, rep["changed"]))


def cmd_ideas(P, a):
    for x in C.ideas(P.dir, a.unit):
        print("%s %s %-8s %s %s" % (x["issue"], x["cand"], x["unit"], x["why"], x["file"]))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd")
    ap.add_argument("proj")
    ap.add_argument("id", nargs="?")
    for k in ("--gen", "--raw", "--out"):
        ap.add_argument(k, default={"--gen": "make_ass.py", "--raw": "out.raw.ass", "--out": "out.ass"}[k])
    for k in ("--unit", "--chars", "--t", "--layer", "--issue", "--note", "--action", "--tag", "--say", "--choice",
              "--of", "--scope", "--declare", "--why", "--diag", "--change", "--candidates", "--grep", "--n"):
        ap.add_argument(k)
    ap.add_argument("--frame", type=float)
    ap.add_argument("--status", default="proposed")
    ap.add_argument("--open", action="store_true")
    a = ap.parse_args()
    fn = globals().get("cmd_" + a.cmd)
    if fn is None:
        raise SystemExit("没有命令 %s. 看 --help" % a.cmd)
    P = Proj(a.proj)
    if a.cmd != "init":
        P.need()
    fn(P, a)


if __name__ == "__main__":
    main()
