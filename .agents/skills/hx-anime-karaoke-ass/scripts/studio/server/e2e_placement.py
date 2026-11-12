#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""歌词位置预设 (PlacementPanel / 监视器近似预览 / POST /api/placement) 的交互验收, 真 chromium + playwright.

  python3 scripts/studio/server/e2e_placement.py --project dev/无职转生/オンリー --gen-python "uv run -q --with fonttools --with pillow --with numpy python" [--json out.json]

会重跑生成器, 所以不在工程里跑: 先把工程的生成器输入 + out.ass/清单 + song.mp3 + judge/ 拷到临时目录,
服务指向这份拷贝 (工程的 out.ass / placement.json 全程不碰, 结束时核对 sha). 用例在 e2e_placement.js.
"""
import argparse, hashlib, json, os, shutil, subprocess, sys, tempfile, threading

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import app  # noqa: E402
from render.octo_browser import CAND_PW, find_chrome, free_port  # noqa: E402

KEEP_EXT = (".py", ".json", ".txt", ".md")
KEEP = ("out.ass", "song.mp3", "song.flac", "song.m4a")


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest() if os.path.exists(p) else None


def sandbox(src, dst):
    for f in os.listdir(src):
        p = os.path.join(src, f)
        if os.path.isfile(p) and (f in KEEP or (f.endswith(KEEP_EXT) and f != "review.jsonl")):
            shutil.copy2(p, os.path.join(dst, f))
    if os.path.isdir(os.path.join(src, "judge")):
        shutil.copytree(os.path.join(src, "judge"), os.path.join(dst, "judge"))
    # 2026-11-13: out.ass 用 \\1img 引用 assets/ 下的图; studio 逐张注入, 缺图时 octo=partial (不算 ready).
    # 沙盒不带图, 测试就会卡在等 ready, 所以把图一起带上 (MV 抠图源 mv/ 和实验图 _exp/ 不需要).
    if os.path.isdir(os.path.join(src, "assets")):
        shutil.copytree(os.path.join(src, "assets"), os.path.join(dst, "assets"), ignore=shutil.ignore_patterns("mv", "_exp"))
    # 歌名/番名要与原工程一致 (参考 ASS 按它找): 拷贝放在 <tmp>/<番名>/<歌名>


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--gen-python", required=True, help="跑生成器的解释器命令 (需 fonttools)")
    ap.add_argument("--json")
    ap.add_argument("--only", default="")
    ap.add_argument("--shots", default="")
    a = ap.parse_args(argv)
    pw = next((c for c in CAND_PW if c and os.path.exists(os.path.join(c, "node_modules", "playwright"))), None)
    chrome = find_chrome()
    if not pw or not chrome:
        raise SystemExit("找不到 playwright / chromium")
    src = os.path.abspath(a.project)
    guard = {f: sha(os.path.join(src, f)) for f in ("out.ass", "out.manifest.json", "placement.json")}
    tmp = tempfile.mkdtemp(prefix="hxstudio-place-")
    proj = os.path.join(tmp, os.path.basename(os.path.dirname(src)), os.path.basename(src))
    os.makedirs(proj)
    sandbox(src, proj)
    port = free_port()
    srv = app.make_server(proj, "127.0.0.1", port, review=os.path.join(tmp, "review.jsonl"), gen_cmd=a.gen_python.split())
    app.PROJECT.root = app.repo_root(src)          # 参考 ASS / static 仍按原仓库找
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    cfg = os.path.join(tmp, "cfg.json")
    json.dump(dict(chrome=chrome, url="http://127.0.0.1:%d/" % port, tmp=tmp, proj=proj,
                   only=[x for x in a.only.split(",") if x], shots=a.shots), open(cfg, "w"))
    r = subprocess.run(["node", os.path.join(HERE, "e2e_placement.js"), pw, cfg], capture_output=True, text=True, timeout=1500)
    srv.shutdown()
    tail = [l for l in r.stdout.splitlines() if l.startswith("RESULT")]
    if not tail:
        raise SystemExit("node 失败:\n" + r.stdout[-3000:] + r.stderr[-3000:])
    res = json.loads(tail[-1][6:])
    rows = res.get("results", [])
    ok = sum(1 for x in rows if x["ok"])
    for x in rows:
        print("%-4s %-4s %-64s %6dms %s" % (x["id"], "OK" if x["ok"] else "FAIL", x["row"][:64], x["ms"], "" if x["ok"] else x["err"]))
        if x.get("info"):
            print("      ", json.dumps(x["info"], ensure_ascii=False))
    if res.get("fatal"):
        print("FATAL:", res["fatal"][:2000])
    if res.get("errors"):
        print("页面错误:", res["errors"][:5])
    after = {f: sha(os.path.join(src, f)) for f in guard}
    print("工程 out.ass / 清单 / placement.json 未被测试改动: %s" % ("是" if after == guard else "否 %s" % after))
    print("结束时 scrollHeight/innerHeight: %s" % res.get("scroll"))
    print("结果: %d/%d 通过" % (ok, len(rows)))
    if a.json:
        json.dump(res, open(a.json, "w"), ensure_ascii=False, indent=1)
    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if ok == len(rows) and not res.get("fatal") and after == guard else 1


if __name__ == "__main__":
    sys.exit(main())
