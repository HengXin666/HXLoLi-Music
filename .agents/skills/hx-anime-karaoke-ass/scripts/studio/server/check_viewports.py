#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""阶段 D 验收: 3 视口 x DPR 1/1.5/2 = 9 种组合, 真 chromium (playwright) 打开新台子.

每种组合量:
  - 页面滚动条: documentElement/body 的 scrollHeight == innerHeight, scrollWidth == innerWidth
  - 任何元素出现原生滚动条 (offsetWidth-clientWidth>0 或 offsetHeight-clientHeight>0 且可滚)
  - 除 [data-scroll-ok] 两处外, 任何元素内部溢出可滚
  - 每块 canvas[data-hidpi]: canvas.width == round(CSS 宽 x DPR) (允许 devicePixelContentBox 的 ±1 取整差), 高同理
  - 时间线文字: DOM 文字层 (不在画布上), 统计数量与字号
  - libass 就绪, 并在一句歌词中间 (工程数据里第一句起点 >= 20s 的句; 原来写死 42s, 只对 オンリー 成立) 取监视器画布非透明像素数 (说明定制 libass 真在画)
用法:
  python3 scripts/studio/server/check_viewports.py --project dev/<番>/<歌> [--shots <dir>] [--json out.json]
服务在本进程内起 (线程), 跑完即停; 不常驻.
"""
import argparse, json, os, subprocess, sys, tempfile, threading

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import app  # noqa: E402
from render.octo_browser import CAND_PW, find_chrome, free_port  # noqa: E402

VIEWPORTS = [(1280, 720), (1920, 1080), (2560, 1440)]
DPRS = [1, 1.5, 2]

NODE = r"""
const fs = require('fs');
const { createRequire } = require('node:module');
const req = createRequire(process.argv[2] + '/x.js');
const { chromium } = req('playwright');
(async () => {
  const cfg = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
  const b = await chromium.launch({ executablePath: cfg.chrome, args: ['--no-sandbox', '--disable-dev-shm-usage', '--autoplay-policy=no-user-gesture-required'] });
  const rows = [];
  for (const [w, h] of cfg.viewports) for (const dpr of cfg.dprs) {
    const ctx = await b.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: dpr });
    const p = await ctx.newPage();
    const logs = [];
    p.on('pageerror', e => logs.push('P:' + String(e).slice(0, 200)));
    p.on('console', m => { if (m.type() === 'error') logs.push('E:' + m.text().slice(0, 200)); });
    await p.goto(cfg.url, { waitUntil: 'load' });
    await p.waitForFunction(() => document.body.dataset.ready, null, { timeout: 30000 });
    await p.waitForFunction(() => /就绪|失败|无/.test(document.querySelector('header')?.textContent || ''), null, { timeout: 30000 }).catch(() => {});
    await p.evaluate(() => new Promise(r => setTimeout(r, 400)));
    // 定位到 cfg.t (一句歌词中间) 并等 libass 出帧
    await p.evaluate(() => { const a = document.querySelector('[data-testid=play]'); return a ? 1 : 0; });
    await p.mouse.click(0, 0).catch(() => {});
    await p.evaluate(async () => {
      const lane = document.querySelector('[data-hidpi=timeline-static]');
      return !!lane;
    });
    const r = await p.evaluate(async (seekT) => {
      // 通过时间线换算点击 seek 太绕: 直接走 window.__clock 不存在, 用音频元素
      const audios = [...document.querySelectorAll('audio')];
      return audios.length;
    }, cfg.t);
    const m = await p.evaluate(async () => {
      const de = document.documentElement, bd = document.body;
      const page = { iw: innerWidth, ih: innerHeight, dsh: de.scrollHeight, dsw: de.scrollWidth, bsh: bd.scrollHeight, bsw: bd.scrollWidth };
      const native = [], overflow = [];
      for (const el of document.querySelectorAll('*')) {
        const cs = getComputedStyle(el);
        const sbw = el.offsetWidth - el.clientWidth - (parseFloat(cs.borderLeftWidth) + parseFloat(cs.borderRightWidth));
        const sbh = el.offsetHeight - el.clientHeight - (parseFloat(cs.borderTopWidth) + parseFloat(cs.borderBottomWidth));
        const scrollable = /(auto|scroll)/.test(cs.overflowY + cs.overflowX);
        if (scrollable && (sbw > 0.5 || sbh > 0.5)) native.push(el.className || el.tagName);
        const over = el.scrollHeight > el.clientHeight + 1 || el.scrollWidth > el.clientWidth + 1;
        if (over && scrollable && !el.hasAttribute('data-scroll-ok')) overflow.push(String(el.className || el.tagName));
      }
      const canv = [...document.querySelectorAll('canvas[data-hidpi]')].map(c => {
        const r = c.getBoundingClientRect();
        const ew = r.width * devicePixelRatio, eh = r.height * devicePixelRatio;
        return { id: c.dataset.hidpi, css: [+r.width.toFixed(2), +r.height.toFixed(2)], px: [c.width, c.height],
                 ok: Math.abs(c.width - ew) <= 1 && Math.abs(c.height - eh) <= 1 };
      });
      const texts = [...document.querySelectorAll('section *')].filter(e => e.childNodes.length === 1 && e.firstChild.nodeType === 3 && e.textContent.trim());
      const fs = [...new Set(texts.map(e => getComputedStyle(e).fontSize))];
      const header = document.querySelector('header')?.textContent || '';
      return { page, native, overflow, canv, tlText: texts.length, tlFont: fs, header };
    });
    // seek cfg.t: 点击时间线对应位置
    const seek = await p.evaluate(async () => {
      const lane = document.querySelector('[data-hidpi=timeline-static]').parentElement;
      const r = lane.getBoundingClientRect();
      return { x: r.left, y: r.top, w: r.width, h: r.height };
    });
    const dur = await p.evaluate(() => { const t = document.querySelector('[data-testid=play]')?.parentElement?.textContent || ''; return t; });
    const mm = /\/ (\d+):(\d+)/.exec(dur);
    const total = mm ? (+mm[1]) * 60 + (+mm[2]) : 230;
    await p.mouse.click(seek.x + seek.w * (cfg.t / total), seek.y + 60);
    await p.evaluate(() => new Promise(r => setTimeout(r, 1500)));
    const ink = await p.evaluate(() => {
      const c = document.querySelector('canvas[data-hidpi=monitor]');
      try { const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; let n = 0; for (let i = 3; i < d.length; i += 4) if (d[i] > 16) n++; return n; }
      catch (e) { return -1; }
    });
    const vid = await p.evaluate(() => { const v = document.querySelector('video'); return v ? { src: v.currentSrc.split('/').pop(), vis: v.style.visibility, ready: v.readyState } : null; });
    const shot = cfg.shots ? `${cfg.shots}/vp_${w}x${h}@${dpr}.png` : null;
    if (shot) await p.screenshot({ path: shot });
    rows.push({ w, h, dpr, ...m, ink, vid, logs, shot });
    await ctx.close();
  }
  console.log('RESULT' + JSON.stringify(rows));
  await b.close();
})().catch(e => { console.log('RESULT' + JSON.stringify({ err: String(e) })); process.exit(1); });
"""


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--shots")
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    pw = next((c for c in CAND_PW if c and os.path.exists(os.path.join(c, "node_modules", "playwright"))), None)
    chrome = find_chrome()
    if not pw or not chrome:
        raise SystemExit("找不到 playwright / chromium")
    port = free_port()
    srv = app.make_server(a.project, "127.0.0.1", port)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    if a.shots:
        os.makedirs(a.shots, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="hxstudio-")
    cfg = os.path.join(tmp, "cfg.json")
    lines = [l for l in app.PROJECT.lyrics_cached() if l.get("t")]
    pick = next((l for l in lines if l["t"][0] >= 20), lines[0] if lines else None)
    t = round((pick["t"][0] + pick["t"][1]) / 2, 2) if pick else 42.0
    print("取样时刻 %.2fs (%s)" % (t, pick and pick.get("label")))
    json.dump(dict(chrome=chrome, url="http://127.0.0.1:%d/" % port, viewports=VIEWPORTS, dprs=DPRS, t=t,
                   shots=os.path.abspath(a.shots) if a.shots else None), open(cfg, "w"))
    js = os.path.join(tmp, "run.js")
    open(js, "w").write(NODE)
    r = subprocess.run(["node", js, pw, cfg], capture_output=True, text=True, timeout=900)
    srv.shutdown()
    tail = [l for l in r.stdout.splitlines() if l.startswith("RESULT")]
    if not tail:
        raise SystemExit("node 失败:\n" + r.stdout[-3000:] + r.stderr[-3000:])
    rows = json.loads(tail[-1][6:])
    if isinstance(rows, dict):
        raise SystemExit("node 失败: %s" % rows)
    bad = 0
    print("%-11s %-4s %-22s %-6s %-6s %-40s %-8s %s" % ("视口", "DPR", "scrollH/innerH  W", "原生条", "溢出", "canvas 像素 = CSS x DPR", "libass", "时间线文字"))
    for x in rows:
        pg = x["page"]
        noscroll = pg["dsh"] <= pg["ih"] and pg["dsw"] <= pg["iw"] and pg["bsh"] <= pg["ih"] and pg["bsw"] <= pg["iw"]
        cv_ok = all(c["ok"] for c in x["canv"])
        ok = noscroll and not x["native"] and not x["overflow"] and cv_ok and x["ink"] > 0
        bad += not ok
        cvs = " ".join("%s:%dx%d" % (c["id"].replace("timeline-", "tl-"), *c["px"]) for c in x["canv"])
        print("%-11s %-4s %-22s %-6s %-6s %-40s %-8s %d 处 %s  %s" % (
            "%dx%d" % (x["w"], x["h"]), x["dpr"], "%d/%d %d/%d" % (pg["dsh"], pg["ih"], pg["dsw"], pg["iw"]),
            len(x["native"]), len(x["overflow"]), cvs + (" OK" if cv_ok else " BAD"), "ink %d" % x["ink"],
            x["tlText"], "/".join(x["tlFont"]), "OK" if ok else "BAD"))
        for k in ("native", "overflow", "logs"):
            if x[k]:
                print("    %s: %s" % (k, x[k][:6]))
    print("结果: %d/%d 组合通过" % (len(rows) - bad, len(rows)))
    if a.json:
        json.dump(rows, open(a.json, "w"), ensure_ascii=False, indent=1)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
