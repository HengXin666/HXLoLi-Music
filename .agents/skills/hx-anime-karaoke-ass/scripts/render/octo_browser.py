# -*- coding: utf-8 -*-
"""渲染器环境: 定制版 libass / chromium / playwright 的探测，以及承载它的浏览器页面.

为什么单独一个模块: 这些是**环境事实**(这台机器上那份 wasm 在哪、chromium 在哪)与
浏览器侧的胶水(页面 + 本地静态服务), 与"给哪些时刻出图"的编排无关. 探测顺序与
有效性判定写在 CAND_OCTOPUS 的注释里  改它之前先看那段.

渲染器探测顺序(2026-10-03 用户要求: 一律用这份模改版 libass, 不许用系统 libass):
  ① 环境变量(显式覆盖)
  ② skill 自己的 assets/octopus  软链, 指向 HX-Ass-Skill 里的副本
  ③ 直接从 HXLoLi 取(软链断了时的兜底)
判定有效: 必须同时有 libass/libass.wasm 与 subtitles-octopus.js.
"""
import http.server
import os
import re
import socket
import threading


HERE = os.path.dirname(os.path.abspath(__file__))
# 渲染器只认这份模改版 libass(不许用系统 libass), 探测顺序: ① 环境变量 ② skill 的
# assets/octopus(软链到 HX-Ass-Skill 的副本, 两级软链是为了不重复存 10MB 二进制)
# ③ 直接从 HXLoLi 取(软链断了时的兜底). 判定有效 = 同时有 libass/libass.wasm
# 与 subtitles-octopus.js。
# 能力边界(实测): `\moves3` 可用; `\moves4` 本机这份 wasm 未实现(事件完全不动).
_SKILL = os.path.dirname(os.path.dirname(HERE))
_SKILL_OCTO = os.path.join(_SKILL, "assets", "octopus")
CAND_OCTOPUS = [
    os.environ.get("ASSFX_OCTOPUS_DIR", ""),
    _SKILL_OCTO,
    "/data/nvme0_p4/command/Github/HX-Ass-Skill/hx-ass-skill/assets/octopus",
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
// 字体与图片写进 Worker FS 之后必须 setTrack 重载才生效  这是主站的做法
// (HX-LoLis/HXLoLi/src/components/MusicPlayer/AssLyrics.tsx: 写 FS -> setTrack(subContent)).
// 只 writeFile 不重载, libass 仍用 fallback 字体, 症状是满屏豆腐块(实测踩过).
window.__reload=function(text){ window.__inst.setTrack(text); return true; };
window.__at=function(t){ var i=window.__inst;
  // 只走两跳: 目标前 0.05s -> 目标. 不要逐帧推进 
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
