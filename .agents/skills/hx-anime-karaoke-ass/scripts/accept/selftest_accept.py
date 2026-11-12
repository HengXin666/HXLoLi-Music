#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验收台第 2 步自测: 在旧版示例 (git 83316ec 的 examples/mushoku_ed1, 由 git archive 导出到临时目录, 不在工作区留副本) 上走一遍追踪, "好" 的冻结, G2 三条核对, issues.

  hx-karaoke accept/selftest_accept.py [--keep]
前提 (旧版示例从 git 历史导出, 见 export_old): 1) 有 git 可执行文件; 2) 本 skill 在 git 工作树里 (不是 zip / 拷贝出来的目录);
3) 提交 83316ec 在本地 (浅克隆会缺, 需 git fetch --unshallow). 三条缺一条, export_old 会在 git 那一步报错退出, 不会静默跳过.
要真字体 (跑生成器), 约 10 次生成器.
"""
import argparse, ast, contextlib, hashlib, io, json, os, re, shutil, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from accept import accept as A                       # noqa: E402
from assfx.layer.trace import source_hashes          # noqa: E402

# 依赖旧版 fx_* 结构 (fx_common / fx_verse* / fx_last, 共用 fx_break). 2026-11-12 示例换成 オンリー 定稿快照后,
# 旧版只留在 git 历史里: 钉死提交, 自测时导出, 不在 skill 里放第二份同曲生成器.
OLD_REV = "83316ec4baae8e9ad23bea69fedc479694f0bab5"
OLD_PATH = ".agents/skills/hx-anime-karaoke-ass/examples/mushoku_ed1"


def export_old(dst):
    """git archive OLD_REV:OLD_PATH -> dst (跳过 out / review / __pycache__, 与原 copytree 的 ignore 一致)."""
    import tarfile
    top = subprocess.run(["git", "-C", HERE, "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True).stdout.strip()
    raw = subprocess.run(["git", "-C", top, "archive", "--format=tar", OLD_REV, OLD_PATH], capture_output=True, check=True).stdout
    with tarfile.open(fileobj=io.BytesIO(raw)) as tf:
        for m in tf.getmembers():
            rel = os.path.relpath(m.name, OLD_PATH)
            if not m.isfile() or rel.startswith("..") or set(rel.split("/")) & {"out", "review", "__pycache__"}:
                continue
            p = os.path.join(dst, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "wb") as fh:
                fh.write(tf.extractfile(m).read())


R = dict(n=0, bad=[])


def ck(ok, name, detail=""):
    R["n"] += 1
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else "  " + str(detail)))
    if not ok:
        R["bad"].append(name)


def run(cmd, P, **kw):
    d = dict.fromkeys(("unit", "chars", "t", "layer", "issue", "note", "action", "tag", "say", "choice", "of", "scope",
                       "declare", "why", "diag", "change", "candidates", "grep", "frame", "id"))
    d.update(status="proposed", open=False, gen="make_ass.py", raw="out.raw.ass", out="out.ass")
    d.update(kw)
    a = argparse.Namespace(**d)
    buf = io.StringIO()
    code = 0
    with contextlib.redirect_stdout(buf):
        try:
            getattr(A, "cmd_" + cmd)(P, a)
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else 1
            print(e.code)
    return code, buf.getvalue()


def sha(p):
    return hashlib.sha1(open(p, "rb").read()).hexdigest()[:12]


def inject(path, fname, line):
    """在函数体开头插一行 (docstring 之后)."""
    src = open(path, encoding="utf-8").read()
    fn = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == fname)
    first = fn.body[0]
    if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and len(fn.body) > 1:
        first = fn.body[1]
    ls = src.split("\n")
    ind = re.match(r"\s*", ls[first.lineno - 1]).group(0)
    ls.insert(first.lineno - 1, ind + line)
    open(path, "w", encoding="utf-8").write("\n".join(ls))


MARK = 'f.doc.ev(0, 1.0, 1.5, "{\\\\pos(1,1)}T", "FX", "fx:" + f.name)'


def main():
    keep = "--keep" in sys.argv
    tmp = tempfile.mkdtemp(prefix="accept_selftest_")
    proj = os.path.join(tmp, "p")
    export_old(proj)
    P = A.Proj(proj)
    t0 = time.time(); c, o = run("init", P); t_on = time.time() - t0
    ck(c == 0, "init 跑生成器", o)
    man = P.man()
    phr = [u for u in man["units"] if u["kind"] == "phrase"]
    ck("code" in man and all(u.get("deps", {}).get("code") for u in phr), "清单: 每个句单元都有 deps.code",
       [u["key"] for u in phr if not u.get("deps", {}).get("code")])
    ck(all(u.get("chars") and u.get("emit") for u in phr), "清单: 句单元有 chars 与 emit")
    cards = [u for u in man["units"] if u["kind"] == "card"]
    # 示例的卡片走工程自己的 card() (不经 G.card), 依赖记在 entry 名下: 改 title() 只影响 card:title
    under = {k for us in man["code"]["entry"].values() for k in us}
    ck(cards and all(u.get("deps", {}).get("code") or u["key"] in under for u in cards),
       "清单: 卡片单元有 deps.code 或归在 entry 函数名下", man["code"]["entry"])
    ck(any(k.endswith(":title") and us == ["card:title"] for k, us in man["code"]["entry"].items()),
       "entry: cards.title 名下只有 card:title", man["code"]["entry"])
    fns = man["code"]["fns"]
    st = source_hashes(proj, list(fns), man["code"]["data_names"])
    ck(all(st[k] == v["h"] for k, v in fns.items()), "源码重算哈希 = 运行时哈希",
       [k for k, v in fns.items() if st[k] != v["h"]])
    # 追踪不改输出
    env = dict(os.environ, ASSFX_TRACE="0")
    off = os.path.join(tmp, "off.ass")
    t0 = time.time()
    subprocess.run([sys.executable, os.path.join(proj, "make_ass.py"), off], cwd=proj, env=env, capture_output=True)
    t_off = time.time() - t0
    ck(sha(off) == sha(P.raw), "追踪开/关输出逐字节相同", (sha(off), sha(P.raw)))
    print("     耗时: 追踪开 %.1fs, 关 %.1fs" % (t_on, t_off))

    uses = {}
    for u in phr:
        for k in u["deps"]["code"]:
            uses.setdefault(k, []).append(u["key"])
    solo = next(k for k, us in uses.items() if len(us) == 1 and ":fx_" in k and "<" not in k)
    shared = next(k for k, us in uses.items() if len(us) >= 2 and k.endswith(":fx_break"))
    u_solo, (u_good, u_other) = uses[solo][0], uses[shared][:2]
    ck(True, "选样: 独用 %s -> %s; 共用 %s -> %s" % (solo, u_solo, shared, uses[shared]))

    # "好"
    c, o = run("good", P, unit=u_good, chars="0-1")
    ck(c == 0 and "冻结 G1" in o, "标 \"好\" (句内 2 个字)", o)
    print("    ", o.strip(), "(本单元共 %d 个事件)" % len(A.S.unit_events(A.AssDoc.load(P.raw), man, u_good)))
    c, o = run("goods", P)
    ck("ok" in o, "\"好\" 状态 ok", o)

    # 1. 独用函数: 预测 = 本单元 (+window), verify 通过
    run("begin", P)
    inject(os.path.join(proj, solo.split(":")[0]), solo.split(":")[1], MARK)
    c, o = run("predict", P)
    pr = A.g2.predict(A.base_man(P), os.path.join(P.base, "src"), proj)
    ck(pr["fns"] == [solo] and u_solo in pr["units"] and len(pr["units"]) <= 2, "改独用函数: 预测只含本单元与下一句", pr)
    c, o = run("verify", P, scope=",".join(pr["units"]))
    ck(c == 0, "改独用函数: verify 通过", o)
    rep = json.loads(o.split("\n")[0])
    ck(rep["changed"] == [u_solo], "改独用函数: 实际只变本单元", rep["changed"])

    # 2. 共用函数碰到 "好": A 与 B 失败, raw 恢复
    before = sha(P.raw)
    inject(os.path.join(proj, shared.split(":")[0]), "fx_break", MARK)
    c, o = run("predict", P, scope=u_other)
    ck("G1" in o and "超出问题范围" in o, "改共用函数: predict 列出波及的 \"好\" 与越界", o)
    c, o = run("verify", P, scope=u_other)
    ck(c == 1 and "FAIL A" in o and "FAIL B" in o, "改共用函数: verify 判 A (碰到好) + B (越界)", o)
    ck(sha(P.raw) == before, "verify 失败后 raw 恢复为基准")
    c, o = run("verify", P, scope=u_other, declare=",".join(uses[shared]), why="test")
    ck(c == 1 and "FAIL A" in o and "FAIL B" not in o, "声明全局也不能豁免 A", o)
    shutil.copytree(os.path.join(P.base, "src"), proj, dirs_exist_ok=True)      # 撤回改动

    # 3. 追踪漏了: 从基准清单删掉依赖, C 失败
    bm = A.base_man(P)
    for u in bm["units"]:
        if u["key"] == u_solo:
            u["deps"]["code"] = [k for k in u["deps"]["code"] if k != solo]
    json.dump(bm, open(os.path.join(P.base, "manifest.json"), "w", encoding="utf-8"), ensure_ascii=False)
    inject(os.path.join(proj, solo.split(":")[0]), solo.split(":")[1], MARK.replace("1.5", "1.6"))
    c, o = run("verify", P, scope=u_solo)
    ck(c == 1 and "FAIL C" in o, "追踪漏依赖: verify 判 C", o)
    shutil.copytree(os.path.join(P.base, "src"), proj, dirs_exist_ok=True)
    run("verify", P, scope="")          # 回到干净基准 (源码已撤回, 应无变化)
    run("begin", P)

    # 4. 单元数据 (PHRASES 一项) 改动: 预测到该句
    mk = os.path.join(proj, "make_ass.py")
    src = open(mk, encoding="utf-8").read()
    idx = next(i for i, u in enumerate(phr) if u["key"] not in (u_good,) and i > 2)
    lines = [l for l in src.split("\n") if l.strip().startswith("dict(label=")]
    new = lines[idx].replace('hl="', 'hl="ink" or "', 1)      # 值变成 "ink", 函数代码不动
    open(mk, "w", encoding="utf-8").write(src.replace(lines[idx], new, 1))
    pr = A.g2.predict(A.base_man(P), os.path.join(P.base, "src"), proj)
    ck(pr["fns"] == [] and phr[idx]["key"] in pr["units"], "改 PHRASES 第 %d 项: 预测到该句, 函数哈希不变" % idx, pr)
    c, o = run("verify", P, scope=",".join(pr["units"]))
    ck(c == 0, "改 PHRASES 一项: verify 通过", o)

    # 5. 输入变了: "好" 标 stale, 构建仍用快照
    tj = os.path.join(proj, "timing.json")
    tm = json.load(open(tj, encoding="utf-8"))
    li = next(u for u in phr if u["key"] == u_good)["lines"][0]
    rows = tm if isinstance(tm, list) else tm.get("chars") or tm.get("timing")
    for r in rows:
        if r.get("line") == li:
            r["s"] = round(r["s"] + 0.03, 3)
            break
    json.dump(tm, open(tj, "w", encoding="utf-8"), ensure_ascii=False)
    P.regen()
    c, o = run("goods", P)
    ck("stale" in o, "改时间后 \"好\" 标 stale", o)
    run("build", P)
    out = open(P.p("out.ass"), encoding="utf-8-sig").read()
    snap = [l for l in open(os.path.join(P.dir, "goods", "G1.ass"), encoding="utf-8-sig").read().split("\n") if l.startswith("Dialogue")]
    ck(snap and all(l in out for l in snap), "stale 时构建仍用快照, 不自动替换")

    # 6. issues
    c, o = run("issue", P, unit=u_other, action="bad", tag="看不清", say="字糊")
    ck(c == 0 and "I1" in o, "issue add bad + 标签")
    c, o = run("issue", P, unit=u_other, action="bad", tag="字太小")
    ck(c == 1, "非法标签拒收 (标签描述症状)")
    c, o = run("where", P, id="I1")
    ck("根因层: 生成" in o and ":" in o and "第" in o, "where: 路由到根因层与函数/源文件", o)
    for k in range(2):
        run("resolve", P, id="I1", diag="d", change="c")
    c, o = run("resolve", P, id="I1", diag="d", change="c")
    ck(c == 1 and "已自动改过" in o, "同一条自动改 2 次后要带候选或转人", o)
    for _ in range(3):        # I1 已是 proposed, 不算未关闭; 另记 3 条
        run("issue", P, unit=u_solo, action="bad", tag="看不清")
    c, o = run("issues", P, open=True)
    ck("出现 3 处" in o, "同标签 3 处提示归并", o)
    c, o = run("issue", P, unit=u_other, action="accept", of="I1")
    ck(c == 0 and P.issues().get("I1")["status"] == "done", "收下 -> 问题关闭")

    # 7. 台子 v3: 层过滤, 多段选区, 候选文件
    from accept import sel as SL
    from assdoc.assdoc import AssDoc
    raw, man = AssDoc.load(P.raw), P.man()
    ly, _ = SL.pick(raw, man, dict(unit=u_other, layer="ly"))
    fx, _ = SL.pick(raw, man, dict(unit=u_other, layer="fx"))
    al, _ = SL.pick(raw, man, dict(unit=u_other))
    ck(ly and fx and len(ly) + len(fx) == len(al) and all(e["name"].startswith("ly:") for e in ly),
       "层过滤: ly + fx = 整句, ly 段只含字层", (len(ly), len(fx), len(al)))
    I = P.issues()
    it = I.add([dict(unit=u_other, chars=[0, 2]), dict(unit=u_solo, chars=None)], "bad", "太吵")
    ck(len(it.get("sels") or []) == 2 and it["sel"]["unit"] == u_other and len(I.sels(it)) == 2, "多段选区: sel = 第一段, sels = 全部")
    c, o = run("resolve", P, id=it["id"], diag="d", change="c", status="need-human", candidates="A,B")
    ck(c == 1 and "没有文件" in o, "候选没有 ASS 文件: resolve 拒收", o)
    os.makedirs(I.cand_dir(it["id"]), exist_ok=True)
    for x in ("A", "B"):
        shutil.copy(P.raw, os.path.join(I.cand_dir(it["id"]), x + ".ass"))
    c, o = run("resolve", P, id=it["id"], diag="d", change="c", status="need-human", candidates="A,B")
    c2, o2 = run("issue", P, unit=u_other, action="pick", choice="C", of=it["id"])
    c3, o3 = run("issue", P, unit=u_other, action="pick", choice="B", of=it["id"])
    ck(c == 0 and c2 == 1 and c3 == 0 and P.issues().get(it["id"])["picked"] == "B", "候选有文件才收; 只能选列出的候选", (o, o2, o3))

    print("\n%d/%d PASS" % (R["n"] - len(R["bad"]), R["n"]))
    if keep:
        print("保留在", tmp)
    else:
        shutil.rmtree(tmp)
    sys.exit(1 if R["bad"] else 0)


if __name__ == "__main__":
    main()
