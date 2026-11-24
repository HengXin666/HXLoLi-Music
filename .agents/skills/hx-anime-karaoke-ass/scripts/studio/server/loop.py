# -*- coding: utf-8 -*-
"""看, 挑, 改, 证: 台上的候选闭环 (契约: steps/5-verify/12-station/index.md "候选闭环", impl/cands.md).

接口 (app.py 转来):
  GET  /api/loop                 标注 + 处理状态 + 每条问题的候选 + 构想记录 + 当前对比对象 + 后台任务
  GET  /api/ass/cand?issue=I1&c=A  候选的整首预览 ASS (= 当前 out.ass 换掉本单元)
  GET  /api/ass/prev             上一版 out.ass (accept build 前留下的)
  POST /api/loop/cmp    {kind: ref|prev|cand|auto, issue?, c?}   对比对象 (监视器 "参考" 那一路换成它)
  POST /api/loop/cands  {review: 标注 id, n?}   intake 这条标注 -> 只重跑单元出 2-3 个候选 (后台, 单飞)
  POST /api/loop/pick   {issue, c}             选中 -> picks.json -> 整首重跑 -> G2 + 隔离核对 -> 冻结 (后台, 单飞)
后台任务与 /api/placement 共用一把生成器锁: 同一时刻只跑一个生成器. 结果写进 job, 页面经 /api/watch 的 accept/cmp 变化重取.
没有参考 ASS 时, 对比对象自动退到上一版; 没有上一版就只有候选可比. 门禁阈值只认参考 ASS 本身 (app.py profile trueref).
"""
import json
import os
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(os.path.dirname(HERE))
ACCEPT = os.path.join(SCRIPTS, "accept", "accept.py")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)
from accept import reviewlog as RL  # noqa: E402

JOB = dict(running=False, kind=None, ok=None, error=None, out="", started=None, finished=None, seq=0, arg=None)


def adir(P):
    return P.p("review", "accept")


def cand_dir(P, iid):
    return os.path.join(adir(P), "cands", iid)


def prev_path(P):
    f = os.path.join(adir(P), "prev.ass")
    return f if os.path.exists(f) else None


def cand_path(P, iid, c):
    if not iid or not c or "/" in iid or ".." in iid or c not in "ABC":
        return None
    f = os.path.join(cand_dir(P, iid), c + ".ass")
    return f if os.path.exists(f) else None


def cmp_target(P):
    """{kind, path, label, auto}. 用户选过且文件还在就用它, 否则自动: 参考 > 上一版 > 无."""
    c = P.cmp or {}
    k = c.get("kind")
    if k == "ref" and P.ref_ass():
        return dict(kind="ref", path=P.ref_ass(), label="参考", auto=False)
    if k == "prev" and prev_path(P):
        return dict(kind="prev", path=prev_path(P), label="上一版", auto=False)
    if k == "cand":
        f = cand_path(P, c.get("issue"), c.get("c"))
        if f:
            return dict(kind="cand", path=f, label="候选 %s (%s)" % (c["c"], c["issue"]), auto=False, issue=c["issue"], c=c["c"])
    if P.ref_ass():
        return dict(kind="ref", path=P.ref_ass(), label="参考", auto=True)
    if prev_path(P):
        return dict(kind="prev", path=prev_path(P), label="上一版", auto=True)
    return dict(kind="none", path=None, label="无", auto=True)


def cmp_info(P):
    t = cmp_target(P)
    opts = []
    if P.ref_ass():
        opts.append(dict(kind="ref", label="参考"))
    if prev_path(P):
        opts.append(dict(kind="prev", label="上一版"))
    for iid, rec in cands_all(P).items():
        if rec.get("state") == "open":
            opts += [dict(kind="cand", issue=iid, c=x["id"], label="候选 %s (%s)" % (x["id"], iid)) for x in rec["items"]]
    return dict(kind=t["kind"], label=t["label"], auto=t["auto"], path=P.rel(t["path"]) if t["path"] else None,
                issue=t.get("issue"), c=t.get("c"), options=opts)


def _j(path):
    try:
        return json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        return None


def issues(P):
    d = _j(os.path.join(adir(P), "issues.json")) or {}
    return d.get("items", [])


def cands_all(P):
    out = {}
    root = os.path.join(adir(P), "cands")
    st = {it["id"]: it for it in issues(P)}
    if not os.path.isdir(root):
        return out
    for iid in sorted(os.listdir(root)):
        rec = _j(os.path.join(root, iid, "cands.json"))
        if not rec:
            continue
        it = st.get(iid) or {}
        rec["state"] = "picked" if it.get("picked") else ("open" if it.get("status") == "proposed" else it.get("status"))
        rec["picked"] = it.get("picked")
        for x in rec["items"]:
            x["url"] = "/api/ass/cand?issue=%s&c=%s" % (iid, x["id"])
        out[iid] = rec
    return out


def ideas(P):
    f = os.path.join(adir(P), "ideas.jsonl")
    if not os.path.exists(f):
        return []
    return [json.loads(l) for l in open(f, encoding="utf-8") if l.strip()]


def stamp(P):
    """accept 侧状态的变化戳 (issues / goods / picks / cands / 后台任务)."""
    fs = [os.path.join(adir(P), x) for x in ("issues.json", "goods.json", "picks.json", "ideas.jsonl", "state.json")]
    v = [os.stat(f).st_mtime_ns if os.path.exists(f) else 0 for f in fs]
    c = os.path.join(adir(P), "cands")
    if os.path.isdir(c):
        v.append(os.stat(c).st_mtime_ns)
        v += [os.stat(os.path.join(c, d)).st_mtime_ns for d in os.listdir(c)]
    return "%d:%d" % (hash(tuple(v)) & 0xffffffff, JOB["seq"])


def state(P):
    """看, 挑, 改, 证 面板的数据: 每条标注 + 处理状态 + 改动, 候选, 构想记录, 对比对象.

    Agent Notes: .agents/notes/implemented/feature/2026-11-17-karaoke-station-loop.md
    """
    items, bad = P.reviews()
    st = {it["id"]: it for it in issues(P)}
    by_rev = {it.get("review"): it for it in st.values() if it.get("review")}
    rows = []
    for r in items:
        it = by_rev.get(r["id"])
        rows.append(dict(id=r["id"], kind=r["kind"], tags=r.get("tags") or [], text=r.get("text") or "", t0=r["t0"], t1=r["t1"],
                         sel=r["sel"], status=r.get("status"), status_src=r.get("status_src"), issue=r.get("issue") or (it or {}).get("id"),
                         changes=r.get("changes") or []))
    # 没有标注来源的问题 (selfreview --handoff 写进来的需人判, 或 agent 用 accept issue 记的): 也列出来, 状态同样可查
    man = P.man()
    us = {u["key"]: u for u in man.get("units", [])}
    for it in st.values():
        if it.get("review") or it.get("action") not in ("bad", "another"):
            continue
        u = us.get((it.get("sel") or {}).get("unit")) or {}
        t = u.get("t") or [0, 0]
        rows.append(dict(id="issue:" + it["id"], kind="redo" if it["action"] == "another" else "bad", tags=[it["tag"]] if it.get("tag") else [],
                         text=it.get("say") or "", t0=t[0], t1=t[1], sel=[], status=it["status"], status_src=it.get("from") or "accept",
                         issue=it["id"], changes=RL.change_log(it)))
    return dict(accept=os.path.exists(os.path.join(adir(P), "state.json")), reviews=rows, bad_lines=bad,
                cands=cands_all(P), ideas=ideas(P), cmp=cmp_info(P), job=dict(JOB),
                picks=(_j(os.path.join(adir(P), "picks.json")) or {}).get("units", {}))


# ------------------------------------------------------------------ 后台 (调 accept.py, 不在服务进程里改工程)
def _accept(P, *args, timeout=900):
    env = dict(os.environ, ASSFX=SCRIPTS, PYTHONPATH=SCRIPTS + os.pathsep + os.environ.get("PYTHONPATH", ""),
               ACCEPT_REVIEW=P.review_path())
    env.setdefault("ASSFX_FONTS", os.path.join(os.path.dirname(SCRIPTS), "fonts"))
    r = subprocess.run(P.gen_cmd + [ACCEPT] + list(args), cwd=P.dir, env=env, capture_output=True, text=True, timeout=timeout)
    return r.returncode, (r.stdout + r.stderr)


def _run(P, kind, arg, steps):
    out, err = [], None
    try:
        for args in steps(P):
            code, o = _accept(P, *args)
            out.append("$ accept.py %s\n%s" % (" ".join(args), o.strip()[-2500:]))
            if code:
                err = (o.strip().splitlines() or ["accept 失败"])[-1][:400]
                break
    except subprocess.TimeoutExpired:
        err = "accept 超时"
    except Exception as e:  # noqa: BLE001
        err = "%s: %s" % (type(e).__name__, e)
    finally:
        JOB.update(running=False, ok=err is None, error=err, out="\n".join(out)[-6000:], finished=time.time(), seq=JOB["seq"] + 1)
        if kind == "pick" and err is None:     # 选完: 候选不再可比, 对比对象回到自动
            P.cmp = None
            P.cmp_seq += 1
        P.gen_lock.release()


def start(h, P, kind, arg, steps):
    if not P.gen_lock.acquire(blocking=False):
        return h.err(409, "生成器正在运行, 等它结束")
    JOB.update(running=True, kind=kind, ok=None, error=None, out="", started=time.time(), finished=None, arg=arg)
    threading.Thread(target=_run, args=(P, kind, arg, steps), daemon=True).start()
    return h.send_json(dict(started=True, kind=kind, arg=arg), 202)


def _ensure_init(P):
    return [] if os.path.exists(os.path.join(adir(P), "state.json")) else [["init", "."], ["build", "."]]


def get(h, P, path, q):
    if path == "/api/loop":
        return h.send_json(state(P))
    if path == "/api/ass/prev":
        f = prev_path(P)
        return h.send_text(P.text(f)) if f else h.err(404, "没有上一版 (accept build 过一次才有)")
    if path == "/api/ass/cand":
        f = cand_path(P, q.get("issue"), q.get("c"))
        return h.send_text(P.text(f)) if f else h.err(404, "没有这个候选")
    return h.err(404, "unknown api")


def post(h, P, path):
    b = h.body() or {}
    if not isinstance(b, dict):
        return h.err(400, "需要 JSON 对象")
    if path == "/api/loop/cmp":
        k = b.get("kind")
        if k == "auto":
            P.cmp = None
        elif k == "ref" and P.ref_ass() or k == "prev" and prev_path(P):
            P.cmp = dict(kind=k)
        elif k == "cand" and cand_path(P, b.get("issue"), b.get("c")):
            P.cmp = dict(kind="cand", issue=b["issue"], c=b["c"])
        else:
            return h.err(400, "没有这个对比对象: %s" % json.dumps(b, ensure_ascii=False))
        P.cmp_seq += 1
        return h.send_json(dict(cmp=cmp_info(P), ref_ass="/api/ass/ref" if P.cmp_ass() else None,
                                ref_path=P.rel(P.cmp_ass()) if P.cmp_ass() else None))
    if path == "/api/loop/cands" and b.get("issue"):      # 没有标注来源的问题 (自审需人判): 直接按 issue 出候选
        iid = str(b["issue"])
        if iid not in {it["id"] for it in issues(P)}:
            return h.err(400, "没有这条问题: %s" % iid)
        n = str(int(b.get("n", 3)))
        return start(h, P, "cands", dict(issue=iid), lambda P: iter([["cands", ".", iid, "--n", n]]))
    if path == "/api/loop/cands":
        rid = b.get("review")
        recs = {r["id"]: r for r in RL.records(P.review_path())}
        r = recs.get(rid)
        if not r:
            return h.err(400, "没有这条标注: %s" % rid)
        if r.get("kind") not in ("redo", "bad"):
            return h.err(400, "只有 换一个构想 / 不行 的标注出候选")
        n = str(int(b.get("n", 3)))

        def steps(P):
            yield from _ensure_init(P)
            yield ["intake", "."]
            iid = (next((it for it in issues(P) if it.get("review") == rid), None) or {}).get("id")
            if not iid:
                raise RuntimeError("标注 %s 没有落到单元上 (看 review.jsonl 的 status)" % rid)
            JOB["arg"] = dict(review=rid, issue=iid)
            yield ["cands", ".", iid, "--n", n]
        return start(h, P, "cands", dict(review=rid), steps)
    if path == "/api/loop/pick":
        iid, c = b.get("issue"), b.get("c")
        if not cand_path(P, iid, c):
            return h.err(400, "没有候选 %s/%s" % (iid, c))
        return start(h, P, "pick", dict(issue=iid, c=c), lambda P: iter([["pick", ".", iid, "--choice", c]]))
    return h.err(404, "unknown api")
