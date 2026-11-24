#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""阶段 E 交互验收: plan 3.5 (歌词面板) / 3.6 (右键菜单) / 3.7 (时间线轨) 的每一行操作, 真 chromium + playwright.

  python3 scripts/studio/server/e2e_ui.py --project dev/<番>/<歌> [--json out.json]

服务在本进程内起 (线程), 批注写到临时文件 (不碰工程的 review.jsonl), 跑完即停. 用例在 e2e_ui.js.
"""
import argparse, json, os, subprocess, sys, tempfile, threading

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import app  # noqa: E402
from render.octo_browser import CAND_PW, find_chrome, free_port  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--json")
    ap.add_argument("--js", default="e2e_ui.js")
    ap.add_argument("--only", default="")
    ap.add_argument("--shots", default="")
    a = ap.parse_args(argv)
    pw = next((c for c in CAND_PW if c and os.path.exists(os.path.join(c, "node_modules", "playwright"))), None)
    chrome = find_chrome()
    if not pw or not chrome:
        raise SystemExit("找不到 playwright / chromium")
    tmp = tempfile.mkdtemp(prefix="hxstudio-e2e-")
    proj_review = os.path.join(os.path.abspath(a.project), "review.jsonl")
    before = os.path.getsize(proj_review) if os.path.exists(proj_review) else None
    port = free_port()
    srv = app.make_server(a.project, "127.0.0.1", port, review=os.path.join(tmp, "review.jsonl"))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    cfg = os.path.join(tmp, "cfg.json")
    json.dump(dict(chrome=chrome, url="http://127.0.0.1:%d/" % port, tmp=tmp, project=os.path.abspath(a.project), only=[x for x in a.only.split(",") if x], shots=a.shots), open(cfg, "w"))
    r = subprocess.run(["node", os.path.join(HERE, a.js), pw, cfg], capture_output=True, text=True, timeout=1500)
    srv.shutdown()
    for l in r.stdout.splitlines():
        if l.startswith("PROBE"):
            print(l)
    tail = [l for l in r.stdout.splitlines() if l.startswith("RESULT")]
    if not tail:
        raise SystemExit("node 失败:\n" + r.stdout[-3000:] + r.stderr[-3000:])
    res = json.loads(tail[-1][6:])
    rows = res.get("results", [])
    ok = sum(1 for x in rows if x["ok"])
    for x in rows:
        print("%-4s %-4s %-62s %5dms %s" % (x["id"], "OK" if x["ok"] else "FAIL", x["row"][:62], x["ms"], "" if x["ok"] else x["err"]))
    if res.get("shots"):
        print("SHOTS", json.dumps(res["shots"], ensure_ascii=False))
    if res.get("fatal"):
        print("FATAL:", res["fatal"][:2000])
    if res.get("errors"):
        print("页面错误:", res["errors"][:5])
    after = os.path.getsize(proj_review) if os.path.exists(proj_review) else None
    print("工程 review.jsonl 未被测试改动: %s" % ("是" if before == after else "否 (%s -> %s)" % (before, after)))
    print("结束时 scrollHeight/innerHeight: %s" % res.get("scroll"))
    print("结果: %d/%d 通过" % (ok, len(rows)))
    if a.json:
        json.dump(res, open(a.json, "w"), ensure_ascii=False, indent=1)
    return 0 if ok == len(rows) and not res.get("fatal") else 1


if __name__ == "__main__":
    sys.exit(main())
