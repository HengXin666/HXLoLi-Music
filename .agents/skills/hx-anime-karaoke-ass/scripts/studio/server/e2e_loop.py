#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""看, 挑, 改, 证 闭环的交互验收: "换一个构想 -> 生成候选 -> 挑选 -> 冻结 -> verify 隔离核对" 全程在台上, 真 chromium.

  python3 scripts/studio/server/e2e_loop.py --project dev/<番>/<歌> [--line 4] [--json out.json]

冻结会改工程 (picks.json / goods / out.ass / review.jsonl), 所以在临时目录的工程副本上跑:
  <tmp>/dev/<番>/<歌>/  = 工程的源文件 (不含 review/ out/ stems/ 与视频), 音频按 refpick 规则取来放成 song.mp3
  <tmp>/static -> 仓库的 static (软链, 参考 ASS 照旧按 refpick 选), <tmp>/playlist.json 同理
原工程一个字节都不动 (跑完核对). 用例在 e2e_loop.js.
"""
import argparse, hashlib, json, os, shutil, subprocess, sys, tempfile, threading

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import app  # noqa: E402
import refpick as REF  # noqa: E402
from render.octo_browser import CAND_PW, find_chrome, free_port  # noqa: E402

SKIP_DIRS = {"review", "out", "stems", "__pycache__", ".git", "mv", ".mv-raw", "judge_cache"}
SKIP_EXT = (".mp4", ".mkv", ".webm", ".flac", ".wav")


def tree_sig(d):
    h = hashlib.sha1()
    for dp, dn, fn in sorted(os.walk(d)):
        dn.sort()
        for f in sorted(fn):
            p = os.path.join(dp, f)
            st = os.stat(p)
            h.update(("%s %d %d\n" % (os.path.relpath(p, d), st.st_size, st.st_mtime_ns)).encode())
    return h.hexdigest()


def make_copy(proj, tmp):
    proj = os.path.abspath(proj)
    root = app.repo_root(proj)
    song, anime = os.path.basename(proj), os.path.basename(os.path.dirname(proj))
    dst = os.path.join(tmp, "dev", anime, song)
    for dp, dn, fn in os.walk(proj):
        dn[:] = [x for x in dn if x not in SKIP_DIRS]
        for f in fn:
            if f.lower().endswith(SKIP_EXT) or f.startswith("out.") and f not in ("out.ass", "out.manifest.json", "out.raw.ass", "out.raw.manifest.json"):
                continue
            src = os.path.join(dp, f)
            rel = os.path.relpath(src, proj)
            os.makedirs(os.path.dirname(os.path.join(dst, rel)), exist_ok=True)
            shutil.copy2(src, os.path.join(dst, rel))
    for x in ("static", "playlist.json"):
        if os.path.exists(os.path.join(root, x)):
            os.symlink(os.path.join(root, x), os.path.join(tmp, x))
    if not any(os.path.exists(os.path.join(dst, c)) for c in ("song.mp3", "song.flac", "song.m4a")):
        a = REF.resolve(root, anime, song, proj, "audio")["path"]
        if a:
            shutil.copy(a, os.path.join(dst, "song" + os.path.splitext(a)[1]))
    return dst, root


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--line", type=int, default=4, help="从第几句起找第一句 >= 3 个字的来标 换一个构想")
    ap.add_argument("--json")
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args(argv)
    pw = next((c for c in CAND_PW if c and os.path.exists(os.path.join(c, "node_modules", "playwright"))), None)
    chrome = find_chrome()
    if not pw or not chrome:
        raise SystemExit("找不到 playwright / chromium")
    before = tree_sig(os.path.abspath(a.project))
    tmp = tempfile.mkdtemp(prefix="hxstudio-loop-")
    dst, root = make_copy(a.project, tmp)
    if not os.path.exists(os.path.join(dst, "out.ass")):     # 新歌: 49-generate 之后由 accept init + build 出 out.ass
        acc = os.path.join(os.path.dirname(os.path.dirname(HERE)), "accept", "accept.py")
        for cmd in (["init", "."], ["build", "."]):
            r0 = subprocess.run([sys.executable, acc] + cmd, cwd=dst, capture_output=True, text=True)
            if r0.returncode:
                raise SystemExit("accept %s 失败:\n%s" % (cmd[0], (r0.stdout + r0.stderr)[-2000:]))
    port = free_port()
    srv = app.make_server(dst, "127.0.0.1", port)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    P = app.PROJECT
    cfg = os.path.join(tmp, "cfg.json")
    json.dump(dict(chrome=chrome, url="http://127.0.0.1:%d/" % port, line=a.line, review=P.review_path(),
                   expect_ref=bool(P.ref_ass())), open(cfg, "w"))
    r = subprocess.run(["node", os.path.join(HERE, "e2e_loop.js"), pw, cfg], capture_output=True, text=True, timeout=1500)
    srv.shutdown()
    tail = [l for l in r.stdout.splitlines() if l.startswith("RESULT")]
    if not tail:
        raise SystemExit("node 失败:\n" + r.stdout[-3000:] + r.stderr[-3000:])
    res = json.loads(tail[-1][6:])
    rows = res["results"]
    ok = sum(1 for x in rows if x["ok"])
    for x in rows:
        print("%-4s %-4s %-62s %6dms %s" % (x["id"], "OK" if x["ok"] else "FAIL", x["row"][:62], x["ms"], "" if x["ok"] else x["err"]))
    if res.get("errors"):
        print("页面错误:", res["errors"][:5])
    print("参考 ASS: %s" % (P.rel(P.ref_ass()) if P.ref_ass() else "无"))
    same = tree_sig(os.path.abspath(a.project)) == before
    print("原工程未被改动: %s" % ("是" if same else "否"))
    print("结果: %d/%d 通过" % (ok, len(rows)))
    if a.json:
        json.dump(dict(res, project=a.project, copy=dst), open(a.json, "w"), ensure_ascii=False, indent=1)
    if not a.keep:
        shutil.rmtree(tmp, ignore_errors=True)
    else:
        print("副本留在", dst)
    return 0 if ok == len(rows) and same and not res.get("errors") else 1


if __name__ == "__main__":
    sys.exit(main())
