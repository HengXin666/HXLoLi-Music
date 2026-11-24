#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""暂停回归验收: 点暂停后监视器的 video 必须停 (paused=true, currentTime 1.5s 内不前进), 真 chromium + playwright.

  python3 scripts/studio/server/e2e_pause.py --project dev/<番>/<歌> [--rounds 5]

有音频 (song.mp3) 走 audio 时钟, 没有走静音墙钟 (silentAt), 两条路径都应通过. 服务在本进程内起, 不写工程文件.
退出码 0 全过 / 1 有未过 / 2 环境缺失.
"""
import argparse, json, os, subprocess, sys, tempfile, threading

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import app  # noqa: E402
from render.octo_browser import CAND_PW, find_chrome, free_port  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--rounds", type=int, default=5)
    a = ap.parse_args(argv)
    pw = next((c for c in CAND_PW if c and os.path.exists(os.path.join(c, "node_modules", "playwright"))), None)
    if not pw:
        print("找不到 playwright"); return 2
    tmp = tempfile.mkdtemp(prefix="hxstudio-pause-")
    port = free_port()
    srv = app.make_server(a.project, "127.0.0.1", port, review=os.path.join(tmp, "review.jsonl"))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    cfg = os.path.join(tmp, "cfg.json")
    json.dump(dict(chrome=find_chrome(), url="http://127.0.0.1:%d/" % port, rounds=a.rounds), open(cfg, "w"))
    r = subprocess.run(["node", os.path.join(HERE, "e2e_pause.js"), pw, cfg], capture_output=True, text=True, timeout=300)
    srv.shutdown()
    tail = [l for l in r.stdout.splitlines() if l.startswith("RESULT")]
    if not tail:
        print("node 失败:\n" + r.stdout[-2000:] + r.stderr[-2000:]); return 2
    res = json.loads(tail[-1][6:])
    for x in res.get("res", []):
        print("round %d %-4s 播放中 ct=%.3f paused=%s | 暂停后150ms ct=%.3f paused=%s | 1650ms ct=%.3f paused=%s"
              % (x["round"], "OK" if x["ok"] else "FAIL", x["play"]["ct"], x["play"]["paused"],
                 x["a150"]["ct"], x["a150"]["paused"], x["a1650"]["ct"], x["a1650"]["paused"]))
    if res.get("err"):
        print(res["err"])
    print("总判定: " + ("PASS" if res.get("ok") else "FAIL"))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
