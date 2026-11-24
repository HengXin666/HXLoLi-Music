# -*- coding: utf-8 -*-
"""候选 (换一个构想 -> 2-3 个候选 -> 挑选 -> 冻结). 规则见 steps/5-verify/12-station/impl/cands.md.

  review/accept/picks.json            选中的参数 (assfx-overrides v1). accept 重跑生成器时经 ASSFX_OVERRIDES 喂回,
                                      所以选中者是生成器的真输出, 不是贴上去的补丁
  review/accept/cands/<I>/cands.json  这条问题的候选: 参数, 事件数, 行哈希, 跳过的提案与原因
  review/accept/cands/<I>/<X>.unit.ass  候选 X 的本单元事件 (只重跑本单元得到)
  review/accept/cands/<I>/<X>.ass       台子预览用: 当前 out.ass 把本单元换成候选 X
  review/accept/cands/<I>/before.ass    生成候选时的 out.ass
  review/accept/ideas.jsonl           未选中的候选 (构想记录): 参数 + 单元快照, 以后可以再拿出来

候选只重跑本单元 (ASSFX_ONLY): 出入场规划仍按全部句算, 种子按单元 key 派生, 所以和整首跑逐行相同.
pick 时整首重跑一次, 用 G2 三条 + "整首输出的本单元 == 候选快照" (隔离核对) 证明这一点, 不相等就不放行.
提案顺序: 换特效配方 (不同构想) 在前, 同配方换 salt (同构想重抽) 在后; 跳过当前参数与构想记录里出现过的参数.
重复歌词: 单元 key = sha(句子文字)#出现次序. 同文字的兄弟单元 key 不同, 种子也不同; picks 里记下 fp 与 label,
歌词增删让次序挪位时 fp 对不上, accept 报 "pick 过期" 而不是静默套到另一句上.
"""
import hashlib
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time

from accept import sel as S
from assdoc.assdoc import AssDoc
from assdoc.spec import load_manifest
from assfx.layer import overrides as OV

LETTERS = "ABC"
MAX_TRY = 8          # 最多试几个提案凑满 n 个
PICKS = "picks.json"
IDEAS = "ideas.jsonl"


# ------------------------------------------------------------------ picks.json
def picks_path(adir):
    return os.path.join(adir, PICKS)


def load_picks(adir):
    p = picks_path(adir)
    if not os.path.exists(p):
        return dict(format="assfx-overrides", version=1, units={})
    return json.load(open(p, encoding="utf-8"))


def save_picks(adir, d):
    os.makedirs(adir, exist_ok=True)
    tmp = picks_path(adir) + ".tmp"
    json.dump(d, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, picks_path(adir))


def picks_params(d):
    return {k: dict(v.get("params") or {}) for k, v in (d.get("units") or {}).items()}


def stale_picks(adir, man):
    """picks 里 fp 与当前清单对不上的单元 (歌词/时间变了, 或重复歌词的次序挪位)."""
    us = S.units(man)
    out = []
    for k, v in (load_picks(adir).get("units") or {}).items():
        u = us.get(k)
        if u is None:
            out.append((k, "单元不在清单里"))
        elif v.get("fp") and u.get("fp") != v["fp"]:
            out.append((k, "输入指纹变了 (%s -> %s)" % (v.get("label"), u.get("label"))))
    return out


# ------------------------------------------------------------------ 提案
def siblings(man, key):
    """同一句子文字的其它单元 (重复歌词)."""
    base = key.split("#")[0]
    return [u["key"] for u in man["units"] if u["kind"] == "phrase" and u["key"] != key and u["key"].split("#")[0] == base]


def ideas(adir, unit=None):
    p = os.path.join(adir, IDEAS)
    if not os.path.exists(p):
        return []
    out = [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
    return [x for x in out if unit is None or x.get("unit") == unit]


def proposals(man, key, cur, seen, tries=0):
    """[(参数, 说明)]. cur = 本单元当前覆盖值; seen = 不再提的参数集合 (json 串)."""
    u = S.units(man)[key]
    fx = (u.get("params") or {}).get("fx") or ""
    recipes = sorted((man.get("presets") or {}).get("recipes") or {})
    used = {(x.get("params") or {}).get("fx") for x in man["units"] if x["kind"] == "phrase"}
    rnd = random.Random(int(hashlib.sha1(("%s|%d" % (key, tries)).encode()).hexdigest()[:8], 16))
    other = [r for r in recipes if r != fx]
    rnd.shuffle(other)
    # 别句没用过的配方优先 (换构想而不是照搬邻句)
    other.sort(key=lambda r: r in used)
    out = []
    for r in other:
        p = dict(cur, fx=r)
        p.pop("salt", None)
        out.append((p, "换特效配方 %s -> %s" % (fx or "无", r)))
    base_salt = int(cur.get("salt", 0))
    for s in range(1, 12):
        p = dict(cur, salt=base_salt + s)
        out.append((p, "同配方 %s 重抽 (salt %d)" % (fx or "无", base_salt + s)))
    # 交错: 配方, 配方, salt, 配方, ...  保证 3 个候选里至少一个是 "同构想重抽"
    fxs, salts = [x for x in out if "fx" in x[0] and x[0].get("fx") != cur.get("fx")], [x for x in out if "salt" in x[0] and x[0].get("fx") == cur.get("fx")]
    mixed = []
    while fxs or salts:
        mixed += fxs[:2]; fxs = fxs[2:]
        mixed += salts[:1]; salts = salts[1:]
    return [(p, why) for p, why in mixed if json.dumps(p, sort_keys=True) not in seen]


# ------------------------------------------------------------------ 生成
def _run(P, overrides, only, out, timeout=600):
    env = dict(os.environ)
    env.setdefault("ASSFX", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    env.pop("ASSFX_TRACE", None)
    env["ASSFX_OVERRIDES"] = overrides
    if only:
        env["ASSFX_ONLY"] = only
    else:
        env.pop("ASSFX_ONLY", None)
    r = subprocess.run([sys.executable, P.p(P.need()["gen"]), out], cwd=P.proj, env=env, capture_output=True,
                       text=True, timeout=timeout)
    return r.returncode, (r.stderr or r.stdout)[-800:]


def unit_doc(doc, man, key):
    evs, _ = S.pick(doc, man, dict(unit=key))
    u = S.units(man)[key]
    bands = {u["name"]: doc.bands[u["name"]]} if u["name"] in doc.bands else {}
    return AssDoc(["[Script Info]"], doc.fmt, [dict(e) for e in evs], bands)


def swap(base_doc, base_man, key, udoc):
    """base 里把单元 key 的事件换成 udoc 的. 返回新 AssDoc."""
    doc = AssDoc(list(base_doc.head), base_doc.fmt, [dict(e) for e in base_doc.events], dict(base_doc.bands))
    cur, _ = S.pick(doc, base_man, dict(unit=key))
    drop = {id(e) for e in cur}
    doc.events = [e for e in doc.events if id(e) not in drop] + [dict(e) for e in udoc.events]
    doc.bands.update(udoc.bands)
    return doc


def lines_sha(doc):
    return hashlib.sha1("\n".join(S.lines(doc.events)).encode("utf-8")).hexdigest()[:12]


def generate(P, iid, n=3, log=print):
    """给问题 iid (单元必须是句单元) 生成 n 个候选. 返回 cands.json 的内容.

    Agent Notes: .agents/notes/implemented/feature/2026-11-17-karaoke-station-loop.md
    """
    I = P.issues()
    it = I.get(iid)
    man = P.man()
    key = it["sel"]["unit"]
    us = S.units(man)
    if key not in us or us[key]["kind"] != "phrase":
        raise SystemExit("%s 的单元 %s 不是句单元: 候选只对句单元生成" % (iid, key))
    n = max(2, min(3, int(n)))
    adir = P.dir
    pk = load_picks(adir)
    cur = dict(((pk.get("units") or {}).get(key) or {}).get("params") or {})
    seen = {json.dumps(cur, sort_keys=True)} | {json.dumps(x["params"], sort_keys=True) for x in ideas(adir, key)}
    cdir = I.cand_dir(iid)
    old = os.path.join(cdir, "cands.json")
    if os.path.exists(old):           # 上一轮的候选没选就又要: 也算构想记录, 不再重复
        for c in json.load(open(old, encoding="utf-8")).get("items", []):
            seen.add(json.dumps(c["params"], sort_keys=True))
    if os.path.isdir(cdir):
        shutil.rmtree(cdir)
    os.makedirs(cdir)
    raw = AssDoc.load(P.raw)
    out_p = P.p(P.need()["out"])
    base = AssDoc.load(out_p) if os.path.exists(out_p) else raw
    shutil.copy(out_p if os.path.exists(out_p) else P.raw, os.path.join(cdir, "before.ass"))
    cur_sha = lines_sha(unit_doc(raw, man, key))
    schema = (man.get("schema") or {}).get("phrase") or []
    pools = man.get("presets") or {}
    items, skipped, shas = [], [], {cur_sha}
    t0 = time.time()
    tmp = tempfile.mkdtemp(prefix="accept_cand_")
    try:
        for params, why in proposals(man, key, cur, seen, it.get("tries", 0))[:MAX_TRY]:
            if len(items) >= n:
                break
            err = OV.check(key, params, schema, params.get("fx"), pools)
            if err:
                skipped.append(dict(params=params, why=why, error=err))
                continue
            ov = os.path.join(tmp, "ov.json")
            units = {k: dict(v) for k, v in (pk.get("units") or {}).items()}
            units[key] = dict(params=params)
            json.dump(dict(format="assfx-overrides", version=1, units=units), open(ov, "w", encoding="utf-8"), ensure_ascii=False)
            cout = os.path.join(tmp, "c.ass")
            ts = time.time()
            try:
                code, msg = _run(P, ov, key, cout)
            except subprocess.TimeoutExpired:
                code, msg = 1, "超时"
            if code or not os.path.exists(cout):
                skipped.append(dict(params=params, why=why, error="生成器失败: " + msg.strip().splitlines()[-1] if msg.strip() else "生成器失败"))
                continue
            cm = load_manifest(cout)
            ud = unit_doc(AssDoc.load(cout), cm, key)
            sha = lines_sha(ud)
            if not ud.events or sha in shas:
                skipped.append(dict(params=params, why=why, error="输出与当前或已有候选相同" if ud.events else "没有事件"))
                continue
            shas.add(sha)
            c = LETTERS[len(items)]
            ud.write(os.path.join(cdir, c + ".unit.ass"))
            swap(base, man, key, ud).write(os.path.join(cdir, c + ".ass"))
            items.append(dict(id=c, params=params, why=why, n=len(ud.events), sha=sha, secs=round(time.time() - ts, 2),
                              fx=params.get("fx") or (us[key].get("params") or {}).get("fx")))
            log("候选 %s: %s, %d 个事件, %.1fs" % (c, why, len(ud.events), time.time() - ts))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    rec = dict(format="accept-cands", version=1, issue=iid, unit=key, label=us[key].get("label"), fp=us[key].get("fp"),
               base_params=cur, base_sha=cur_sha, siblings=siblings(man, key), items=items, skipped=skipped,
               secs=round(time.time() - t0, 2), at=time.strftime("%Y-%m-%d %H:%M:%S"), only_unit=True)
    json.dump(rec, open(os.path.join(cdir, "cands.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if len(items) < 2:
        raise SystemExit("只凑出 %d 个候选 (要 2-3 个). 跳过的提案: %s" % (len(items), json.dumps(skipped, ensure_ascii=False)[:600]))
    I.resolve(iid, "换一个构想: 只重跑单元 %s 出 %d 个候选 (%.1fs)" % (key, len(items), rec["secs"]),
              "; ".join("%s=%s" % (c["id"], c["why"]) for c in items) + ". 等台上挑选",
              "proposed", [c["id"] for c in items])
    return rec


def load(P, iid):
    p = os.path.join(P.issues().cand_dir(iid), "cands.json")
    if not os.path.exists(p):
        raise SystemExit("%s 没有候选: 先 accept.py cands %s %s" % (iid, P.proj, iid))
    return json.load(open(p, encoding="utf-8"))


def record_ideas(P, rec, chosen, issue):
    """未选中的候选进构想记录 (单元快照搬进 ideas/, 不随 cands 目录删掉)."""
    os.makedirs(os.path.join(P.dir, "ideas"), exist_ok=True)
    cdir = P.issues().cand_dir(rec["issue"])
    out = []
    with open(os.path.join(P.dir, IDEAS), "a", encoding="utf-8") as fh:
        for c in rec["items"]:
            if c["id"] == chosen:
                continue
            rel = os.path.join("ideas", "%s-%s.unit.ass" % (rec["issue"], c["id"]))
            shutil.copy(os.path.join(cdir, c["id"] + ".unit.ass"), os.path.join(P.dir, rel))
            x = dict(issue=rec["issue"], unit=rec["unit"], label=rec["label"], cand=c["id"], params=c["params"], why=c["why"],
                     sha=c["sha"], file=rel, chosen=chosen, at=time.strftime("%Y-%m-%d %H:%M:%S"), review=issue.get("review"))
            fh.write(json.dumps(x, ensure_ascii=False) + "\n")
            out.append(c["id"])
    return out
