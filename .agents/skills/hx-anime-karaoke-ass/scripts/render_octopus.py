#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow"]
# ///
"""用**真正的**渲染器出图: HXLoLi 定制版 libass (SubtitlesOctopus / WASM).

## 为什么需要它 (这不是重复造轮子, 是唯一能正确出图的路径)

本机有两个渲染器, 能力不同:

| 渲染器 | 位置 | VSFilterMod 扩展标签 |
|---|---|---|
| 系统 libass 9.x | `/usr/lib/libass.so.9` (ffmpeg 的 `subtitles=` 滤镜用它) | **不支持** |
| **HXLoLi 定制版** | `HX-LoLis/HXLoLi/static/music/ass-worker/libass/libass.wasm` | **支持** `\1img` `\2img` `\3img` `\4img` `\distort` `\fsvp` `\fsc` `\pbo` `\rnd` `\frs` |

实测(2026-10-03): 同一份写了 `\1img(tipi.png)\p1` 的 ass,
系统 ffmpeg 渲染出**纯色白块**(静默退化成填充色, 不报错),
定制版渲染出**真实图片纹理**。所以用 ffmpeg 截图来判定"图片层能不能做"会得到完全错误的结论。

这正是 step 14 抽帧目检必须走这个脚本的原因 —— 目检用的渲染器必须和观众实际看到的一致。

## 两个必知规格 (实测)

1. **`\1img` 的纹理按绘制矩形平铺。** 矩形尺寸 = 图片尺寸时正好显示一次;
   矩形更大就会铺成 N×M 张(实测 300×240 矩形 + 105×84 图 = 铺了 9 张)。
   所以写 `\1img` 时必须先读图片真实尺寸, 用它生成矩形。
2. **图片路径相对于 ass 文件所在目录**, 且必须先写进 worker 虚拟 FS。
   没写进去时报错是 `[vsfiltermod] Failed to load image: X (can't fopen)` ——
   这条报错**只在控制台**, 不写 FS 的话画面上什么都没有, 也不会让渲染失败。

用法:
  hx-karaoke render_octopus.py <ass> --out shot.png --time 12.5 [--dir <ass 所在目录>]
  hx-karaoke render_octopus.py <ass> --out dir/ --times 58,60,62,64 --width 1920
  hx-karaoke render_octopus.py <ass> --probe          # 只检查: 渲染器在哪/图片能不能找到/字体缺哪些

依赖: playwright (chromium) + pillow + node. 位置自动探测, 可用环境变量覆盖:
  ASSFX_OCTOPUS_DIR   定制版 wasm/js 所在目录 (默认自动找 HX-LoLis/HXLoLi)
  ASSFX_PLAYWRIGHT    playwright 包所在目录 (默认自动找)
  ASSFX_CHROME        chromium 可执行文件
"""
import argparse, base64, http.server, json, mimetypes, os, re, shutil, socket, subprocess, sys, tempfile, threading

HERE = os.path.dirname(os.path.abspath(__file__))
CAND_OCTOPUS = [
    os.environ.get("ASSFX_OCTOPUS_DIR", ""),
    "/data/nvme0_p4/command/Github/HX-LoLis/HXLoLi/static/music/ass-worker",
    os.path.expanduser("~/HXLoLis/HXLoLi/static/music/ass-worker"),
]
CAND_PW = [
    os.environ.get("ASSFX_PLAYWRIGHT", ""),
    "/data/nvme0_p4/img-to-react/web",
]


def find_octopus():
    for d in CAND_OCTOPUS:
        if d and os.path.exists(os.path.join(d, "libass", "libass.wasm")) \
                and os.path.exists(os.path.join(d, "subtitles-octopus.js")):
            return d
    return None


def find_chrome():
    env = os.environ.get("ASSFX_CHROME")
    if env and os.path.exists(env):
        return env
    base = os.path.expanduser("~/.cache/ms-playwright")
    if not os.path.isdir(base):
        return None
    best = None
    for d in sorted(os.listdir(base)):
        p = os.path.join(base, d, "chrome-linux64", "chrome")
        if os.path.exists(p):
            best = p
    return best


PAGE = r"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
html,body{margin:0;padding:0;background:#000;overflow:hidden} #c{position:absolute;left:0;top:0}
</style></head><body><canvas id="c"></canvas>
<script src="subtitles-octopus.js"></script>
<script>
window.__ready=false; window.__err=null; window.__logs=[];
var _err=console.error; console.error=function(){ window.__logs.push('E:'+[].join.call(arguments,' ')); _err.apply(console,arguments); };
window.__init=function(o){
  // canvas 的 width/height 属性必须显式设置: 不设就是默认 300x150, 出图会被裁成那个尺寸
  var cv=document.getElementById('c'); cv.width=o.w; cv.height=o.h;
  return new Promise(function(res,rej){
  try{
    window.__inst=new SubtitlesOctopus({
      canvas:cv, subUrl:o.subUrl,
      workerUrl:'subtitles-octopus-worker.js', legacyWorkerUrl:'subtitles-octopus-worker-legacy.js',
      fonts:o.fonts||[], availableFonts:o.availableFonts||{},
      onReady:function(){ window.__ready=true; res('ready'); },
      onError:function(e){ window.__err=String(e&&e.message||e); rej(window.__err); }
    });
  }catch(e){ window.__err=String(e); rej(window.__err); }
});};
window.__write=function(name,b64){ var bin=atob(b64); var u=new Uint8Array(bin.length);
  for(var i=0;i<bin.length;i++)u[i]=bin.charCodeAt(i); window.__inst.writeFile(name,u); return u.length; };
// 字体与图片写进 Worker FS 之后必须 setTrack 重载才生效 —— 这是主站的做法
// (HX-LoLis/HXLoLi/src/components/MusicPlayer/AssLyrics.tsx: 写 FS -> setTrack(subContent)).
// 只 writeFile 不重载, libass 仍用 fallback 字体, 症状是满屏豆腐块(实测踩过).
window.__reload=function(text){ window.__inst.setTrack(text); return true; };
window.__at=function(t){ var i=window.__inst;
  // 只走两跳: 目标前 0.05s -> 目标. 不要逐帧推进 ——
  // 实测按 1/8 秒从 0 走到 194s 要 1556 次渲染, 会把 libass 的字形缓存挤爆,
  // 之后所有文字渲染成"豆腐块"(看起来像字体缺失, 其实是缓存淘汰)。
  // 两跳足以让 \t 的插值取到正确时刻(renderer 按时间差决定重绘)。
  i.setCurrentTime(Math.max(0, t - 0.05));
  i.setCurrentTime(t);
  return true; };
window.__grab=function(){ return document.getElementById('c').toDataURL('image/png'); };
</script></body></html>
"""


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def serve(root, port):
    class H(Quiet):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=root, **k)

        def guess_type(self, path):
            ext = os.path.splitext(path)[1].lower()
            return {".wasm": "application/wasm", ".js": "application/javascript",
                    ".ass": "text/plain; charset=utf-8", ".ttf": "font/ttf",
                    ".woff2": "font/woff2", ".png": "image/png",
                    ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}.get(ext, super().guess_type(path))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def probe(ass_path):
    ok = True
    oct_dir = find_octopus()
    print("定制版渲染器:", oct_dir or "**未找到** (设 ASSFX_OCTOPUS_DIR)")
    ok &= bool(oct_dir)
    if oct_dir:
        w = os.path.join(oct_dir, "libass", "libass.wasm")
        with open(w, "rb") as f:
            blob = f.read()
        tags = [t.decode() for t in re.findall(rb"[1-4]img", blob)]
        print("  wasm 内 VSFilterMod 标签:", sorted(set(x for x in tags)), "(系统 libass 为 0 个)")
    ch = find_chrome()
    print("chromium:", ch or "**未找到** (设 ASSFX_CHROME)")
    ok &= bool(ch)
    d = os.path.dirname(os.path.abspath(ass_path))
    txt = open(ass_path, encoding="utf-8-sig", errors="replace").read()
    imgs = []
    for m in re.finditer(r"\\[1-4]img\(([^)]+)\)", txt):
        rel = m.group(1).strip()
        if rel.startswith("data:") or "!" in rel or "$" in rel:
            continue
        if rel not in imgs:
            imgs.append(rel)
    print(f"\\1img 引用 {len(imgs)} 个:")
    for rel in imgs:
        p = os.path.join(d, rel)
        state = "OK" if os.path.exists(p) else "**缺失**"
        size = ""
        if os.path.exists(p):
            try:
                from PIL import Image
                size = " %s" % (Image.open(p).size,)
            except Exception:
                pass
        print(f"  [{state}] {rel}{size}")
        ok &= os.path.exists(p)
        if imgs.count(rel) == 0 and rel == "":
            ok = False
    # 字体
    fonts = sorted(set(re.findall(r"^Style: [^,]+,([^,]+),", txt, re.M)))
    print("字体:", ", ".join(fonts))
    return 0 if ok else 1


def render(ass_path, out, times, width, height, fonts_dir=None, scale=None):
    from PIL import Image
    oct_dir, chrome, pw = find_octopus(), find_chrome(), None
    for c in CAND_PW:
        if c and os.path.exists(os.path.join(c, "node_modules", "playwright")):
            pw = c
            break
    if not oct_dir:
        raise SystemExit("找不到定制版渲染器; 用 ASSFX_OCTOPUS_DIR 指到 .../ass-worker")
    if not chrome:
        raise SystemExit("找不到 chromium; 用 ASSFX_CHROME 指到可执行文件")
    if not pw:
        raise SystemExit("找不到 playwright; 用 ASSFX_PLAYWRIGHT 指到装了 playwright 的目录")

    # 临时工作区必须回收: 每个含 wasm + legacy worker ≈ 105MB.
    # 实测教训(2026-10-03): 不清理时跑 52 次就积到 5.1GB, 把 /tmp(tmpfs, 8GB)写满,
    # 之后**连 shell 都无法写输出**(报 `UNKNOWN: unknown error, write`).
    # 用一个可复用的固定目录 + 结束时清空, 比每次 mkdtemp 更省。
    work = os.path.join(tempfile.gettempdir(), "hxocto-work")
    if os.path.isdir(work):
        shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work, exist_ok=True)
    for f in ("subtitles-octopus.js", "subtitles-octopus-worker.js",
              "subtitles-octopus-worker-legacy.js", "subtitles-octopus-worker.wasm",
              "default.ttf", "default.woff2"):
        s = os.path.join(oct_dir, f)
        if os.path.exists(s):
            shutil.copy(s, work)
    os.makedirs(os.path.join(work, "libass"), exist_ok=True)
    for f in os.listdir(os.path.join(oct_dir, "libass")):
        shutil.copy(os.path.join(oct_dir, "libass", f), os.path.join(work, "libass"))
    open(os.path.join(work, "page.html"), "w", encoding="utf-8").write(PAGE)
    shutil.copy(ass_path, os.path.join(work, "sub.ass"))

    adir = os.path.dirname(os.path.abspath(ass_path))
    img_payload = {}
    txt = open(ass_path, encoding="utf-8-sig", errors="replace").read()
    for m in re.finditer(r"\\[1-4]img\(([^)]+)\)", txt):
        rel = m.group(1).strip()
        if rel.startswith("data:") or "!" in rel or "$" in rel:
            continue
        src = os.path.join(adir, rel)
        if os.path.exists(src) and rel not in img_payload:
            img_payload[rel] = base64.b64encode(open(src, "rb").read()).decode()

    # 字体: 既写 FS(供 libass 按名取用), 也通过 availableFonts 注册
    font_payload = {}
    avail = {}
    def _family_of(ttf_path):
        """读字体文件的真实族名. ASS 里写的必须是这个, 不是文件名 ——
        实测 'LXGW WenKai Medium' 与文件里的 '霞鹜文楷 Medium' 不一致, libass 找不到就回落,
        症状是满屏豆腐块(而系统 ffmpeg 有自己的字体回退, 会掩盖这个问题)."""
        try:
            from fontTools.ttLib import TTFont
            t0 = TTFont(ttf_path)
            for rec in t0["name"].names:
                if rec.nameID == 1:
                    try:
                        return rec.toUnicode()
                    except Exception:
                        pass
        except Exception:
            pass
        return os.path.splitext(os.path.basename(ttf_path))[0]
    fdir = fonts_dir or os.path.join(os.path.dirname(HERE), "fonts")
    if os.path.isdir(fdir):
        for f in sorted(os.listdir(fdir)):
            if f.lower().endswith((".ttf", ".otf", ".ttc")):
                fp = os.path.join(fdir, f)
                font_payload["fonts/" + f] = base64.b64encode(open(fp, "rb").read()).decode()
                avail[_family_of(fp)] = "fonts/" + f

    port = free_port()
    srv = serve(work, port)

    # 配置走文件, 不走 argv: 字体+图片的 base64 有几百 KB, argv 会触发
    # OSError: [Errno 7] Argument list too long (实测)
    cfg_path = os.path.join(work, "_cfg.json")
    json.dump(dict(chrome=chrome, w=width, h=height, url=f"http://127.0.0.1:{port}/page.html",
                   imgs=img_payload, fonts=font_payload, times=times, wait=420,
                   out_dir=work, subText=txt, avail=avail), open(cfg_path, "w"))

    script = r"""
const fs = require('fs');
const path = require('path');
const { createRequire } = require('node:module');
const req = createRequire(process.argv[2] + '/x.js');
const { chromium } = req('playwright');
(async () => {
  const cfg = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
  const b = await chromium.launch({ executablePath: cfg.chrome,
      args: ['--no-sandbox','--disable-gpu','--disable-dev-shm-usage'] });
  const p = await b.newPage({ viewport: { width: cfg.w, height: cfg.h } });
  const logs = [];
  p.on('console', m => logs.push(m.type()[0] + ':' + m.text().slice(0, 300)));
  p.on('pageerror', e => logs.push('P:' + String(e).slice(0, 300)));
  await p.goto(cfg.url);
  try { await p.evaluate(o => window.__init(o), { subUrl: "/sub.ass", w: cfg.w, h: cfg.h }); }
  catch (e) { console.log('RESULT' + JSON.stringify({ ok:false, err:String(e), logs })); await b.close(); return; }
  await p.waitForTimeout(900);
  for (const [name, b64] of Object.entries(cfg.imgs)) await p.evaluate(([n,d]) => window.__write(n,d), [name, b64]);
  for (const [name, b64] of Object.entries(cfg.fonts)) await p.evaluate(([n,d]) => window.__write(n,d), [name, b64]);
  // 写完之后必须重载 track, 否则 libass 还在用 fallback 字体/找不到图片(满屏豆腐块)
  if (cfg.subText && (Object.keys(cfg.imgs).length || Object.keys(cfg.fonts).length)) {
    await p.evaluate(txt => window.__reload(txt), cfg.subText);
    await p.waitForTimeout(cfg.wait);
  }
  // 帧直接写盘, 不经过 stdout: 一次 1920x1080 PNG 的 base64 约 1MB, 多帧会撑爆管道
  const saved = [];
  let idx = 0;
  for (const t of cfg.times) {
    await p.evaluate(tt => window.__at(tt), t);
    await p.waitForTimeout(cfg.wait);
    const data = await p.evaluate(() => window.__grab());
    const f = path.join(cfg.out_dir, 'frame' + String(idx++).padStart(3,'0') + '.png');
    fs.writeFileSync(f, Buffer.from(data.split(',')[1], 'base64'));
    saved.push([t, f]);
  }
  console.log('RESULT' + JSON.stringify({ ok:true, shots: saved, logs }));
  await b.close();
})().catch(e => { console.log('RESULT' + JSON.stringify({ ok:false, err:String(e) })); process.exit(1); });
"""
    sp = os.path.join(work, "_shot.js")
    open(sp, "w", encoding="utf-8").write(script)
    r = subprocess.run(["node", sp, pw, cfg_path], capture_output=True, text=True, timeout=600)
    srv.shutdown()
    # 先把结果帧挪出 work 再删目录(帧在 work 里)
    tail = [l for l in r.stdout.splitlines() if l.startswith("RESULT")]
    if not tail:
        raise SystemExit("渲染失败, node 输出:\n" + r.stdout[-2000:] + r.stderr[-2000:])
    res = json.loads(tail[-1][len("RESULT"):])
    if not res.get("ok"):
        raise SystemExit("渲染失败: %s\nlogs: %s" % (res.get("err"), res.get("logs")))
    bad = [l for l in res.get("logs", []) if "can't fopen" in l or l.startswith("P:") or l.startswith("e:")]
    for l in bad:
        print("[renderer] " + l)

    single = len(times) == 1 and not out.endswith("/") and not os.path.isdir(out)
    if single:
        dst = out
        d0 = os.path.dirname(os.path.abspath(dst))
        if d0:
            os.makedirs(d0, exist_ok=True)
    else:
        target = out if (out.endswith("/") or os.path.isdir(out)) else out.rstrip("/") + "/"
        os.makedirs(target, exist_ok=True)
    for t, src in res["shots"]:
        dst = out if single else os.path.join(
            out if (out.endswith("/") or os.path.isdir(out)) else out.rstrip("/") + "/",
            f"{t:08.2f}.png")
        shutil.copy(src, dst)
        im = Image.open(dst).convert("RGBA")
        import numpy as _np
        a = _np.asarray(im).astype(int)
        # canvas 是透明的: 必须自己合成到黑底再量, 否则读图工具会把透明区渲染成白色,
        # 得到"整帧发白但非黑像素只有 14%"这种自相矛盾的数(实测踩过)
        rgb = a[:, :, :3] * (a[:, :, 3:4] / 255.0)
        lit = int((rgb.sum(axis=2) > 20).sum())
        Image.fromarray(rgb.astype("uint8")).save(dst)
        print(f"  t={t:8.2f}s  {im.size[0]}x{im.size[1]}  亮像素 {lit:7d} -> {dst}")
    shutil.rmtree(work, ignore_errors=True)
    print("渲染器: HXLoLi 定制版 libass (VSFilterMod 支持)")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ass")
    ap.add_argument("--out")
    ap.add_argument("--time", type=float)
    ap.add_argument("--times")
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--fontsdir")
    ap.add_argument("--probe", action="store_true")
    a = ap.parse_args()
    if a.probe:
        return probe(a.ass)
    times = [float(x) for x in a.times.split(",")] if a.times else ([a.time] if a.time is not None else [0.0])
    out = a.out or (os.path.splitext(a.ass)[0] + "_shots")
    return render(a.ass, out, times, a.width, a.height, a.fontsdir)


if __name__ == "__main__":
    raise SystemExit(main())
