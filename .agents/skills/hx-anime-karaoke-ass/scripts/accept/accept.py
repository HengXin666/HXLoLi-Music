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
  accept.py build PROJ                              out.ass = 冻结快照(raw)
"""
import argparse, json, os, shutil, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from accept import g2, sel as S                       # noqa: E402
from accept.goods import Goods                        # noqa: E402
from accept.issues import Issues                      # noqa: E402
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
        env.pop("ASSFX_OVERRIDES", None); env.pop("ASSFX_TRACE", None)
        r = subprocess.run([sys.executable, self.p(self.need()["gen"]), out or self.raw], cwd=self.proj, env=env,
                           capture_output=True, text=True)
        if r.returncode:
            raise SystemExit("生成器失败:\n" + r.stdout[-1500:] + r.stderr[-1500:])

    def goods(self):
        return Goods(self.dir)

    def issues(self):
        return Issues(self.dir)


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


def cmd_issue(P, a):
    man = P.man()
    S.pick(AssDoc.load(P.raw), man, sel_of(a))         # 选区要能落到清单单元上
    it = P.issues().add(sel_of(a), a.action, a.tag, a.say or "", a.frame, a.choice, a.of)
    print("记下 %s: %s %s %s" % (it["id"], a.action, a.tag or "", S.label(it["sel"], man)))
    if a.action == "good":
        cmd_good(P, argparse.Namespace(**dict(vars(a), issue=it["id"], note=a.say)))


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
    print("基准已存. 现有 \"好\":", [(g["id"], g["sel"]["unit"]) for g in P.goods().items] or "无")


def base_man(P):
    p = os.path.join(P.base, "manifest.json")
    if not os.path.exists(p):
        raise SystemExit("没有基准: 改代码前先跑 accept.py begin")
    return json.load(open(p, encoding="utf-8"))


def cmd_predict(P, a):
    pr = g2.predict(base_man(P), os.path.join(P.base, "src"), P.proj)
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
    pred = g2.predict(bm, os.path.join(P.base, "src"), P.proj)
    old = AssDoc.load(os.path.join(P.base, "raw.ass"))
    scope = [k for k in (a.scope or "").split(",") if k]
    declared = [k for k in (a.declare or "").split(",") if k]
    if declared and not a.why:
        raise SystemExit("--declare 要写 --why (为什么必须全局改)")
    P.regen()
    new, nm = AssDoc.load(P.raw), P.man()
    fail, rep = g2.verify(old, bm, new, nm, pred, scope, declared, P.goods())
    print(json.dumps(rep, ensure_ascii=False))
    if fail:
        shutil.copy(P.raw, os.path.join(P.base, "fail.ass"))
        shutil.copy(os.path.join(P.base, "raw.ass"), P.raw)
        shutil.copy(os.path.join(P.base, "manifest.json"), manifest_path(P.raw))
        for f in fail:
            print("FAIL", f)
        print("raw 已恢复为基准; 这次的输出留在 review/accept/base/fail.ass")
        sys.exit(1)
    if declared:
        print("全局改动已声明: %s. 理由: %s. 这些句子要全部重跑自审" % (declared, a.why))
    cmd_build(P, a)
    cmd_begin(P, a)        # 通过后新输出成为下一次的基准


def cmd_resolve(P, a):
    it = P.issues().resolve(a.id, a.diag, a.change, a.status, a.candidates.split(",") if a.candidates else None)
    print("%s -> %s (第 %d 次)" % (it["id"], it["status"], it["tries"]))


def cmd_build(P, a):
    raw, man = AssDoc.load(P.raw), P.man()
    G = P.goods()
    doc = G.apply(raw, man)
    doc.write(P.p(P.need()["out"]))
    bad = {k: v for k, v in G.status(raw, man).items() if v[0] != "ok"}
    print("构建 %s: %d 个事件, %d 条 \"好\"%s" % (P.st["out"], len(doc.events), len(G.items),
                                         "; 需要看: %s" % bad if bad else ""))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd")
    ap.add_argument("proj")
    ap.add_argument("id", nargs="?")
    for k in ("--gen", "--raw", "--out"):
        ap.add_argument(k, default={"--gen": "make_ass.py", "--raw": "out.raw.ass", "--out": "out.ass"}[k])
    for k in ("--unit", "--chars", "--t", "--layer", "--issue", "--note", "--action", "--tag", "--say", "--choice",
              "--of", "--scope", "--declare", "--why", "--diag", "--change", "--candidates", "--grep"):
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
