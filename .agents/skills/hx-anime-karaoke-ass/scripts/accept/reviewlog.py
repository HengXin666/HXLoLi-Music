# -*- coding: utf-8 -*-
"""review.jsonl 的处理状态 (台子写标注, accept 回写状态). 格式见 steps/5-verify/12-station/index.md "标注记到哪里".

台子 POST /api/review 追加一行, 带 status="open", changes=[]. accept 侧:
  intake  每条还没挂 issue 的标注 -> issues.json 一条 (bad/redo/good), 回写 issue 与 status; note 只记 "noted"
  sync    按 issues.json 的状态与 history 回写每条标注的 status 与 changes (诊断 / 改了什么 / 候选 / 选了哪个 / G2)
回写只改目标行: 其它行 (含坏行) 字节原样; 临时文件 + os.replace, 与台子 append_review 同一套原子写法.
"""
import json
import os

STATUS = ("open", "fixing", "proposed", "done", "need-human", "dropped", "noted")
KIND2ACTION = dict(bad="bad", redo="another", good="good")


def path_of(proj):
    """台子在测试里把标注写到临时文件 (e2e), 经 ACCEPT_REVIEW 告诉 accept; 平时就是工程的 review.jsonl."""
    return os.environ.get("ACCEPT_REVIEW") or os.path.join(proj, "review.jsonl")


def read(path):
    """[(行字节, 记录或 None)]. 坏行 rec=None, 原样保留."""
    if not os.path.exists(path):
        return []
    out = []
    raw = open(path, "rb").read()
    parts = raw.split(b"\n")
    if parts and parts[-1] == b"":
        parts.pop()
    for b in parts:
        try:
            rec = json.loads(b.decode("utf-8")) if b.strip() else None
        except (UnicodeDecodeError, ValueError):
            rec = None
        out.append((b, rec if isinstance(rec, dict) else None))
    return out


def write(path, rows):
    data = b"".join((json.dumps(r, ensure_ascii=False).encode("utf-8") if r is not None and changed else b) + b"\n"
                    for b, r, changed in rows)
    tmp = "%s.tmp-%d" % (path, os.getpid())
    with open(tmp, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def records(path):
    return [r for _, r in read(path) if r is not None and r.get("id")]


def status_of(rec):
    """没有 status 字段的老记录按 open 算 (可查: 台子与 accept 都这样读)."""
    s = rec.get("status")
    return s if s in STATUS else ("noted" if rec.get("kind") == "note" else "open")


def update(path, patches):
    """patches: {记录 id: {字段: 值}}. 只改这些行. 返回改了几行."""
    rows, n = [], 0
    for b, r in read(path):
        p = patches.get(r.get("id")) if r else None
        if p:
            new = dict(r, **p)
            ch = new != r
            n += ch
            rows.append((b, new, ch))
        else:
            rows.append((b, r, False))
    if n:
        write(path, rows)
    return n


def unit_of(man, line):
    """台子 sel 的 line 是 arc 行号 = 句单元 lines[0] (studio app.py lyrics())."""
    for u in man.get("units", []):
        if u.get("kind") == "phrase" and (u.get("lines") or [None])[0] == line:
            return u
    return None


def sel_of(man, rec):
    """标注选区 -> accept 选区列表 [{unit, chars}]. 找不到单元的段跳过."""
    out = []
    for s in rec.get("sel") or []:
        u = unit_of(man, s.get("line"))
        if not u:
            continue
        n = len(u.get("chars") or [])
        a, b = int(s.get("from", 0)), int(s.get("to", n - 1))
        whole = a <= 0 and b >= n - 1
        out.append(dict(unit=u["key"], chars=None if whole else [a, b + 1], t=None, layer=None))
    return out


def change_log(it):
    """issue 的 history -> 标注的 changes (按时间)."""
    out = [dict(at=it.get("at"), status="open", what="提出 (%s)" % it.get("action"), issue=it["id"])]
    for h in it.get("history") or []:
        d = dict(at=h.get("at"), status=h.get("status"), what=h.get("change"), diag=h.get("diag"), issue=it["id"])
        for k in ("candidates", "picked", "g2", "good", "ideas"):
            if h.get(k):
                d[k] = h[k]
        out.append(d)
    return out


def sync(path, issues):
    """按 issues 回写挂了 issue 的标注. 返回改了几行."""
    by = {it.get("review"): it for it in issues.items if it.get("review")}
    patches = {}
    for r in records(path):
        it = by.get(r["id"])
        if it:
            patches[r["id"]] = dict(status=it["status"], issue=it["id"], changes=change_log(it))
        elif "status" not in r:
            patches[r["id"]] = dict(status=status_of(r), changes=r.get("changes") or [])
    return update(path, patches)
