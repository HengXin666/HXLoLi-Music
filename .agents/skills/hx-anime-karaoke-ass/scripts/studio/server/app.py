#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HX ASS studio 服务 (阶段 D, plan.md 3.8). 只用标准库.

用法:
  python3 scripts/studio/server/app.py --project dev/无职转生/オンリー [--port 5199] [--host 127.0.0.1]

运行时直接发 web/dist (vite build 产物), 不需要 node. 开发时 vite dev 把 /api /media /octopus /fonts 代理到这里.
只读: out.ass, 参考 ASS, timing/manifest/arc. 只在收到写请求时写: review.jsonl (POST /api/review), mv.edl.json (PUT /api/edl),
placement.json + 重跑生成器换 out.ass/清单 (POST /api/placement: 单飞, 忙时直接 409; 预设与产物都先落临时目录,
全部成功才原子改名进工程, 失败时工程文件一个都不动).
check_fx_profile 只 import, 不复制, 不修改.
"""
import argparse, base64, hashlib, json, os, re, socket, struct, subprocess, sys, threading, time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote

HERE = os.path.dirname(os.path.abspath(__file__))
STUDIO = os.path.dirname(HERE)
SCRIPTS = os.path.dirname(STUDIO)
SKILL = os.path.dirname(SCRIPTS)
DIST = os.path.join(STUDIO, "web", "dist")
sys.path.insert(0, SCRIPTS)
from assfx import check_fx_profile as CFP  # noqa: E402  只 import
from render.octo_browser import find_octopus  # noqa: E402  与出片同一份定制 libass
sys.path.insert(0, HERE)
from analysis import Analysis  # noqa: E402
from assfx.text import placement as PLC  # noqa: E402  位置公式唯一实现 (前端不复算)

MIME = {".html": "text/html; charset=utf-8", ".js": "application/javascript", ".mjs": "application/javascript",
        ".css": "text/css", ".json": "application/json", ".wasm": "application/wasm", ".svg": "image/svg+xml",
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
        ".mp3": "audio/mpeg", ".flac": "audio/flac", ".m4a": "audio/mp4", ".ogg": "audio/ogg", ".wav": "audio/wav",
        ".mp4": "video/mp4", ".webm": "video/webm", ".ass": "text/plain; charset=utf-8",
        ".ttf": "font/ttf", ".otf": "font/otf", ".woff": "font/woff", ".woff2": "font/woff2", ".ico": "image/x-icon"}


# Agent Notes: studio 服务端 (标准库 HTTP, 只读产物, 只写 review.jsonl / mv.edl.json)
# .agents/notes/implemented/feature/2026-11-09-karaoke-studio.md
def repo_root(start):
    d = os.path.abspath(start)
    while d != "/":
        if os.path.isdir(os.path.join(d, ".git")) or os.path.isdir(os.path.join(d, "static", "music")):
            return d
        d = os.path.dirname(d)
    return os.path.abspath(start)


def ts(x):
    h, m, s = x.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


TAG = re.compile(r"\{[^}]*\}")


def parse_events(text):
    out, fmt = [], None
    for ln, line in enumerate(text.splitlines(), 1):
        if line.startswith("Format:") and fmt is None and "Start" in line:
            fmt = [f.strip() for f in line[7:].split(",")]
        if not line.startswith("Dialogue:"):
            continue
        p = line[9:].lstrip().split(",", 9)
        if len(p) < 10:
            continue
        out.append(dict(ln=ln, layer=int(p[0]), t0=ts(p[1]), t1=ts(p[2]), style=p[3], name=p[4], text=p[9]))
    return out


def family_of(path):
    try:
        from fontTools.ttLib import TTFont
        t = TTFont(path, lazy=True, fontNumber=0)
        names = {}
        for rec in t["name"].names:
            if rec.nameID in (1, 4, 16):
                try:
                    names.setdefault(rec.nameID, []).append(rec.toUnicode())
                except Exception:
                    pass
        return sorted({n for v in names.values() for n in v})
    except Exception:
        return [os.path.splitext(os.path.basename(path))[0]]


class Project:
    def __init__(self, path):
        self.dir = os.path.abspath(path)
        self.root = repo_root(self.dir)
        self.song = os.path.basename(self.dir)
        self.anime = os.path.basename(os.path.dirname(self.dir))
        self._cache = {}
        self.lock = threading.Lock()
        self.gen_lock = threading.Lock()   # 单飞: 同一时刻只跑一个生成器
        self.gen_cmd = [sys.executable]
        self.gen_timeout = 600
        self.job = dict(running=False, ok=None, error=None, preset=None, started=None, finished=None, seq=0, thread=None)
        self.A = Analysis(self)

    # ---- 路径
    def p(self, *a):
        return os.path.join(self.dir, *a)

    def rel(self, path):
        return os.path.relpath(path, self.root)

    def ref_ass(self):
        d = os.path.join(self.root, "static", "music", self.anime)
        if os.path.isdir(d):
            c = sorted(f for f in os.listdir(d) if f.endswith(".ass") and self.song in f)
            if c:
                return os.path.join(d, c[0])
        return None

    def audio(self):
        for c in ("song.mp3", "song.flac", "song.m4a"):
            if os.path.exists(self.p(c)):
                return self.p(c)
        d = os.path.join(self.root, "static", "music", self.anime)
        if os.path.isdir(d):
            for f in sorted(os.listdir(d)):
                if self.song in f and f.lower().endswith((".mp3", ".flac", ".m4a", ".ogg")):
                    return os.path.join(d, f)
        return None

    def video(self):
        f = self.p("source", "ed1_creditless.mp4")
        return f if os.path.exists(f) else None

    def fonts_dir(self):
        for d in (self.p("fonts"), os.path.join(SKILL, "fonts")):
            if os.path.isdir(d):
                return d
        return None

    # ---- 带 mtime 的缓存
    def cached(self, key, path, fn):
        if not path or not os.path.exists(path):
            return None
        m = os.stat(path).st_mtime_ns
        with self.lock:
            hit = self._cache.get(key)
            if hit and hit[0] == m:
                return hit[1]
        v = fn(path)
        with self.lock:
            self._cache[key] = (m, v)
        return v

    def text(self, path):
        return self.cached("txt:" + path, path, lambda p: open(p, encoding="utf-8-sig", errors="replace").read())

    def json(self, path):
        return self.cached("json:" + path, path, lambda p: json.load(open(p, encoding="utf-8")))

    def events(self, which="out"):
        path = self.p("out.ass") if which == "out" else self.ref_ass()
        return self.cached("ev:" + str(path), path, lambda p: parse_events(self.text(p)))

    def profile(self, which="out"):
        path = self.p("out.ass") if which == "out" else self.ref_ass()
        return self.cached("pf:" + str(path), path, lambda p: CFP.profile(self.text(p)))

    def duration(self):
        a = self.audio()

        def probe(p):
            try:
                r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p],
                                   capture_output=True, text=True, timeout=20)
                return float(r.stdout.strip())
            except Exception:
                return None
        d = self.cached("dur", a, probe) if a else None
        if not d:
            ev = self.events("out") or []
            d = max((e["t1"] for e in ev), default=0.0)
        return round(d, 3)

    def video_offset(self):
        sh = self.json(self.p("judge", "shots.json")) or {}
        return float(sh.get("video_offset", 0.0)) if isinstance(sh, dict) else 0.0

    # ---- 资源
    def fonts(self):
        d = self.fonts_dir()
        out = []
        if d:
            for f in sorted(os.listdir(d)):
                if f.lower().endswith((".ttf", ".otf", ".ttc", ".woff2")):
                    fam = self.cached("fam:" + f, os.path.join(d, f), family_of)
                    out.append(dict(file=f, url="/fonts/" + f, families=fam))
        return out

    def edl(self):
        e = self.json(self.p("mv.edl.json"))
        if e:
            return dict(e, source="file")
        v = self.video()
        if not v:
            return dict(version=1, source="none", segments=[])
        # 没有 EDL 文件时的默认: 原画从歌曲 0s 起直放, video_t = song_t + video_offset (judge/shots.json).
        # 视频播完 (约 87s 起 TV 剪辑收尾之后) 监视器自动回到黑底.
        return dict(version=1, source="default", segments=[dict(
            kind="orig", t0=0.0, t1=None, src=self.rel(v), src_t0=self.video_offset())])

    def sections(self):
        arc = self.json(self.p("judge", "arc.json")) or {}
        return arc.get("sections", [])

    def lyrics(self):
        man = self.json(self.p("out.manifest.json")) or {}
        arc = {l["line"]: l for l in (self.json(self.p("judge", "arc.json")) or {}).get("lines", [])}
        ev = self.events("out") or []
        cn = {}
        for e in ev:
            if e["style"] == "CN" and e["name"].startswith("ly:") and e["layer"] == 2:
                m = re.search(r"\\(?:pos|move)\(([-\d.]+),([-\d.]+)", e["text"])
                cn.setdefault(e["name"][3:], {})[(round(float(m.group(1)), 1) if m else 0)] = TAG.sub("", e["text"])
        prof = self.profile("out") or {}
        per = prof.get("per_line", {})
        lines = []
        for u in man.get("units", []):
            if u.get("kind") != "phrase":
                continue
            name = u["name"]
            li = (u.get("lines") or [None])[0]
            a = arc.get(li, {})
            chars = [dict(i=i, ch=c[0], s=c[1], e=c[2], x=c[3], w=c[4]) for i, c in enumerate(u.get("chars", []))]
            cnl = cn.get(name, {})
            lines.append(dict(name=name, line=li, label=u.get("label"), t=u.get("t"), band=u.get("band"),
                              text=a.get("text") or "".join(c["ch"] for c in chars), role=a.get("role"),
                              technique=a.get("technique"), cn="".join(cnl[k] for k in sorted(cnl)),
                              fx=per.get(name, 0), fn=u.get("params", {}).get("fx"), chars=chars))
        lines.sort(key=lambda l: (l["t"] or [0])[0])
        return self.A.lyric_extra(lines)

    def lyrics_cached(self):
        return self.cached("lyrics", self.p("out.ass"), lambda p: self.lyrics())

    def peaks(self, n=4000):
        a = self.audio()

        def run(p):
            try:
                r = subprocess.run(["ffmpeg", "-v", "error", "-i", p, "-ac", "1", "-ar", "4000", "-f", "s16le", "-"],
                                   capture_output=True, timeout=120)
                raw = r.stdout
            except Exception:
                return None
            cnt = len(raw) // 2
            if not cnt:
                return None
            vals = struct.unpack("<%dh" % cnt, raw[:cnt * 2])
            step = max(1, cnt // n)
            pk = [round(max(abs(v) for v in vals[i:i + step]) / 32768, 4) for i in range(0, cnt, step)]
            return dict(rate=4000 / step, peaks=pk)
        return self.cached("peaks", a, run) if a else None

    def review_path(self):
        return getattr(self, "_review", None) or self.p("review.jsonl")

    def reviews(self):
        f = self.review_path()
        if not os.path.exists(f):
            return []
        return [json.loads(l) for l in open(f, encoding="utf-8") if l.strip()]

    def watched(self):
        w = {k: (os.stat(p).st_mtime_ns if p and os.path.exists(p) else 0) for k, p in (
            ("out", self.p("out.ass")), ("edl", self.p("mv.edl.json")), ("review", self.review_path()),
            ("manifest", self.p("out.manifest.json")), ("placement", self.p(PLC.FILE)))}
        w["job"] = self.job["seq"]
        return w

    # ---- 歌词位置预设 (placement.json). 公式全在 assfx/text/placement.py; 这里只读清单 + 调它.
    PREVIEW_NOTE = "近似预览, 跨区域特效不跟随, 真实效果以应用后重跑为准"

    def placement_state(self, cand=None):
        cur = PLC.load(self.dir)
        res = dict(current=cur, default=PLC.DEFAULT, source="file" if os.path.exists(self.p(PLC.FILE)) else "default", enums=dict(v=PLC.V, h=PLC.H, order=PLC.ORDER, gap=list(PLC.GAP)),
                   job={k: v for k, v in self.job.items() if k != "thread"}, note=self.PREVIEW_NOTE, frozen=self.frozen_goods())
        if cand:
            calib = self.json(self.p("calib.json"))
            man = self.json(self.p("out.manifest.json")) or {}
            units = [u for u in man.get("units", []) if u.get("kind") == "phrase"]
            res["candidate"] = cand
            res["lines"] = PLC.preview(cur, cand, calib, units) if calib else []
            res["rows_missing"] = sum(1 for u in units if not u.get("rows"))
        return res

    def frozen_goods(self):
        g = self.json(self.p("review", "accept", "goods.json")) or {}
        return len(g.get("items", [])) if isinstance(g, dict) else 0

    def placement_apply(self, preset):
        """后台线程. 顺序: 预设写到临时目录 -> 生成器经 ASSFX_PLACEMENT 读它, 出到同一临时目录
        -> 全部成功才逐个 os.replace (同一文件系统内原子改名) 到 out.ass / 清单 / placement.json.
        失败时工程里什么都没动: placement.json 保持原样 (原来不存在就仍不存在), out.ass 不被碰."""
        tmpd = self.p(".placement-run")
        err = None
        try:
            os.makedirs(tmpd, exist_ok=True)
            tpre, tout = os.path.join(tmpd, PLC.FILE), os.path.join(tmpd, "out.ass")
            json.dump(preset, open(tpre, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            env = dict(os.environ, ASSFX=SCRIPTS, ASSFX_FONTS=os.path.join(SKILL, "fonts"), ASSFX_PLACEMENT=tpre,
                       PYTHONPATH=SCRIPTS + os.pathsep + os.environ.get("PYTHONPATH", ""))
            r = subprocess.run(self.gen_cmd + [self.p("make_ass.py"), tout], cwd=self.dir, env=env,
                               capture_output=True, text=True, timeout=self.gen_timeout)
            tman = os.path.splitext(tout)[0] + ".manifest.json"
            if r.returncode != 0 or not os.path.exists(tout) or not os.path.exists(tman):
                err = "生成器失败 (exit %s): %s" % (r.returncode, (r.stderr or r.stdout)[-600:].strip())
            else:
                os.replace(tman, self.p("out.manifest.json"))
                os.replace(tout, self.p("out.ass"))
                os.replace(tpre, self.p(PLC.FILE))
        except subprocess.TimeoutExpired:
            err = "生成器超时 (> %ds), 已终止" % self.gen_timeout
        except Exception as e:  # noqa: BLE001
            err = "%s: %s" % (type(e).__name__, e)
        finally:
            try:
                for x in os.listdir(tmpd):
                    os.remove(os.path.join(tmpd, x))
            except OSError:
                pass
            with self.lock:
                self.job.update(running=False, ok=err is None, error=err, finished=time.time(),
                                seq=self.job["seq"] + 1, thread=None)
            self.gen_lock.release()

PROJECT = None


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "hx-studio/0.1"

    def log_message(self, *a):
        pass

    # ---- 输出
    def send_json(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def send_text(self, text, ctype="text/plain; charset=utf-8", etag=True):
        b = text.encode("utf-8")
        tag = '"%s"' % hashlib.sha1(b).hexdigest()[:16]
        if etag and self.headers.get("If-None-Match") == tag:
            self.send_response(304)
            self.send_header("ETag", tag)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.send_header("ETag", tag)
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(b)

    def err(self, code, msg):
        self.send_json(dict(error=msg), code)

    def send_file(self, path, cache="no-cache"):
        if not path or not os.path.isfile(path):
            return self.err(404, "not found")
        size = os.path.getsize(path)
        ctype = MIME.get(os.path.splitext(path)[1].lower(), "application/octet-stream")
        rng = self.headers.get("Range")
        start, end, code = 0, size - 1, 200
        if rng:
            m = re.match(r"bytes=(\d*)-(\d*)", rng)
            if m:
                if m.group(1):
                    start = int(m.group(1))
                    end = int(m.group(2)) if m.group(2) else size - 1
                else:
                    start = max(0, size - int(m.group(2) or 0))
                end = min(end, size - 1)
                if start > end:
                    self.send_response(416)
                    self.send_header("Content-Range", "bytes */%d" % size)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                code = 206
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Cache-Control", cache)
        if code == 206:
            self.send_header("Content-Range", "bytes %d-%d/%d" % (start, end, size))
        self.end_headers()
        if self.command == "HEAD":
            return
        with open(path, "rb") as f:
            f.seek(start)
            left = end - start + 1
            try:
                while left > 0:
                    chunk = f.read(min(1 << 16, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"null")

    # ---- 路由
    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        u = urlparse(self.path)
        path, q = unquote(u.path), {k: v[-1] for k, v in parse_qs(u.query).items()}
        P = PROJECT
        try:
            if path == "/api/project":
                v = P.video()
                return self.send_json(dict(
                    dir=P.rel(P.dir), anime=P.anime, song=P.song, duration=P.duration(),
                    audio=[("/media/" + P.rel(P.audio())) if P.audio() else None],
                    video=("/media/" + P.rel(v)) if v else None,
                    out_ass="/api/ass/out", ref_ass="/api/ass/ref" if P.ref_ass() else None,
                    ref_path=P.rel(P.ref_ass()) if P.ref_ass() else None,
                    fonts=P.fonts(), edl=P.edl(), sections=P.sections(),
                    octopus="/octopus/" if find_octopus() else None))
            if path in ("/api/ass/out", "/api/ass/ref"):
                f = P.p("out.ass") if path.endswith("out") else P.ref_ass()
                if not f or not os.path.exists(f):
                    return self.err(404, "no ass")
                return self.send_text(P.text(f))
            if path == "/api/lyrics":
                return self.send_json(dict(lines=P.lyrics_cached()))
            if path == "/api/clips":
                return self.send_json(dict(clips=P.A.clips() or [], beats=P.A.beats()))
            if path == "/api/explain":
                try:
                    sel = json.loads(q.get("sel", "[]"))
                except ValueError:
                    return self.err(400, "sel 需要 JSON: [{line, from, to}]")
                return self.send_json(dict(items=P.A.explain(sel, P.lyrics_cached())))
            if path == "/api/hit":
                return self.send_json(dict(t=float(q["t"]), events=P.A.hit(float(q["t"]), float(q["x"]), float(q["y"]))))
            if path == "/api/profile":
                which = q.get("which", "out")
                pf = P.profile(which)
                if pf is None:
                    return self.err(404, "no ass")
                res = dict(which=which, step=CFP.STEP, profile=pf)
                ref = P.profile("ref")
                if ref is not None:
                    th = CFP.thresholds(ref, float(q.get("ratio", 0.8)))
                    res["thresholds"] = th
                    res["judge"] = CFP.judge(pf, th)
                return self.send_json(res)
            if path == "/api/events":
                ev = P.events(q.get("which", "out")) or []
                t0, t1 = float(q.get("t0", 0)), float(q.get("t1", 1e9))
                sty, lay = q.get("style"), q.get("layer")
                lim = int(q.get("limit", 5000))
                man = P.json(P.p("out.manifest.json")) or {}
                emit = {u["name"]: list((u.get("emit") or {}).keys()) for u in man.get("units", [])}
                hit = [e for e in ev if e["t1"] > t0 and e["t0"] < t1 and (not sty or e["style"] == sty)
                       and (lay is None or str(e["layer"]) == lay)]
                if q.get("lines"):
                    want = {int(x) for x in q["lines"].split(",") if x.strip()}
                    hit = [e for e in hit if e["ln"] in want]
                raw = q.get("raw") == "1"
                return self.send_json(dict(total=len(hit), events=[dict(e, fns=emit.get(e["name"].split(":")[-1], []),
                                                                        owners=P.A.owners(e),
                                                                        **({"raw": P.A.raw(q.get("which", "out"), e)} if raw else {}))
                                                                    for e in hit[:lim]]))
            if path == "/api/peaks":
                pk = P.peaks()
                return self.send_json(pk or dict(rate=0, peaks=[]))
            if path == "/api/edl":
                return self.send_json(P.edl())
            if path == "/api/review":
                return self.send_json(dict(items=P.reviews()))
            if path == "/api/watch":
                return self.websocket()
            if path == "/api/placement":
                cand = None
                if any(k in q for k in ("v", "h", "order", "gap")):
                    cand = dict(PLC.load(P.dir), **{k: q[k] for k in ("v", "h", "order", "gap") if k in q})
                    bad = [k for k, al in (("v", PLC.V), ("h", PLC.H), ("order", PLC.ORDER), ("gap", tuple(PLC.GAP))) if cand[k] not in al]
                    if bad:
                        return self.err(400, "未知取值: %s" % ", ".join("%s=%s" % (k, cand[k]) for k in bad))
                return self.send_json(P.placement_state(cand))
            if path.startswith("/media/"):
                f = os.path.realpath(os.path.join(P.root, path[len("/media/"):]))
                ok = (f.startswith(P.dir + os.sep) or f.startswith(os.path.join(P.root, "static", "music") + os.sep))
                return self.send_file(f) if ok else self.err(403, "forbidden")
            if path.startswith("/octopus/"):
                d = find_octopus()
                f = os.path.realpath(os.path.join(d, path[len("/octopus/"):])) if d else None
                return self.send_file(f, "max-age=3600") if f and f.startswith(os.path.realpath(d)) else self.err(404, "no")
            if path.startswith("/fonts/"):
                d = P.fonts_dir()
                f = os.path.realpath(os.path.join(d, path[len("/fonts/"):])) if d else None
                return self.send_file(f, "max-age=3600") if f and f.startswith(os.path.realpath(d)) else self.err(404, "no")
            if path.startswith("/api/"):
                return self.err(404, "unknown api")
            # 前端产物
            f = os.path.realpath(os.path.join(DIST, path.lstrip("/")))
            if path == "/" or not os.path.isfile(f) or not f.startswith(os.path.realpath(DIST)):
                f = os.path.join(DIST, "index.html")
                if not os.path.exists(f):
                    return self.send_text("web/dist 不存在: 先 npm --prefix scripts/studio/web run build", etag=False)
            return self.send_file(f, "no-cache" if f.endswith(".html") else "max-age=31536000")
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:  # noqa: BLE001
            return self.err(500, "%s: %s" % (type(e).__name__, e))

    def do_POST(self):
        u = urlparse(self.path)
        if u.path == "/api/placement":
            return self.post_placement()
        if u.path != "/api/review":
            return self.err(404, "unknown api")
        b = self.body() or {}
        need = {"sel", "t0", "t1", "kind"}
        if not isinstance(b, dict) or not need <= set(b):
            return self.err(400, "需要字段 %s" % sorted(need))
        if b["kind"] not in ("bad", "good", "redo", "note"):
            return self.err(400, "kind 只能是 bad/good/redo/note")
        rec = dict(id="r%d" % int(time.time() * 1000), sel=b["sel"], t0=b["t0"], t1=b["t1"], kind=b["kind"],
                   tags=b.get("tags", []), text=b.get("text", ""), frame=b.get("frame"),
                   created=time.strftime("%Y-%m-%dT%H:%M:%S%z"))
        with PROJECT.lock:
            with open(PROJECT.review_path(), "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return self.send_json(rec, 201)

    def post_placement(self):
        P = PROJECT
        b = self.body() or {}
        if not isinstance(b, dict):
            return self.err(400, "需要 {v, h, order, gap}")
        pre = dict(PLC.DEFAULT, **{k: b[k] for k in PLC.DEFAULT if k in b})
        bad = [k for k, al in (("v", PLC.V), ("h", PLC.H), ("order", PLC.ORDER), ("gap", tuple(PLC.GAP))) if pre[k] not in al]
        if bad:
            return self.err(400, "未知取值: %s" % ", ".join("%s=%s" % (k, pre[k]) for k in bad))
        if P.frozen_goods():
            return self.err(409, "有 %d 条冻结的 \"好\": 换位置会让快照过期, 请先走 accept 流程" % P.frozen_goods())
        if not P.gen_lock.acquire(blocking=False):
            return self.err(409, "生成器正在运行, 等它结束再应用")
        with P.lock:
            P.job.update(running=True, ok=None, error=None, preset=pre, started=time.time(), finished=None)
            th = threading.Thread(target=P.placement_apply, args=(pre,), daemon=True)
            P.job["thread"] = th
        th.start()
        return self.send_json(dict(started=True, preset=pre), 202)

    def do_PUT(self):
        u = urlparse(self.path)
        if u.path != "/api/edl":
            return self.err(404, "unknown api")
        b = self.body()
        if not isinstance(b, dict) or not isinstance(b.get("segments"), list):
            return self.err(400, "需要 {segments:[...]}")
        b.pop("source", None)
        tmp = PROJECT.p("mv.edl.json.tmp")
        json.dump(b, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        os.replace(tmp, PROJECT.p("mv.edl.json"))
        return self.send_json(dict(ok=True))

    # ---- 最小 WebSocket (只推不收): out.ass / EDL / review / manifest 变化时推 {"type":"changed","what":[..]}
    def websocket(self):
        key = self.headers.get("Sec-WebSocket-Key")
        if not key or "websocket" not in (self.headers.get("Upgrade") or "").lower():
            return self.err(400, "需要 websocket")
        acc = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
        self.send_response(101)
        self.send_header("Upgrade", "websocket")
        self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept", acc)
        self.end_headers()
        self.close_connection = True

        def frame(obj):
            b = json.dumps(obj).encode()
            hdr = bytes([0x81]) + (bytes([len(b)]) if len(b) < 126 else bytes([126]) + struct.pack(">H", len(b)))
            self.wfile.write(hdr + b)
            self.wfile.flush()
        last = PROJECT.watched()
        try:
            frame(dict(type="hello", state=last))
            self.connection.settimeout(0.5)
            n = 0
            while True:
                try:  # 读掉客户端帧 (close / ping); 断开则退出
                    d = self.connection.recv(1024)
                    if not d or (d[0] & 0x0F) == 0x8:
                        return
                except socket.timeout:
                    pass
                cur = PROJECT.watched()
                ch = [k for k in cur if cur[k] != last.get(k)]
                if ch:
                    last = cur
                    frame(dict(type="changed", what=ch, state=cur))
                n += 1
                if n % 40 == 0:
                    frame(dict(type="ping"))
        except (BrokenPipeError, ConnectionResetError, OSError):
            return


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        if not isinstance(sys.exc_info()[1], (ConnectionResetError, BrokenPipeError)):  # 浏览器断开媒体流是常态
            super().handle_error(request, client_address)


def make_server(project, host="127.0.0.1", port=5199, review=None, gen_cmd=None):
    global PROJECT
    PROJECT = Project(project)
    if gen_cmd:
        PROJECT.gen_cmd = list(gen_cmd)
    if review:
        PROJECT._review = os.path.abspath(review)  # 测试用: 批注写到临时文件, 不碰工程
    srv = Server((host, port), H)
    srv.daemon_threads = True
    return srv


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True, help="工程目录 dev/<番名>/<歌名>")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=5199)
    ap.add_argument("--gen-python", default=sys.executable, help="POST /api/placement 重跑生成器用的解释器 (需 fonttools)")
    a = ap.parse_args(argv)
    srv = make_server(a.project, a.host, a.port, gen_cmd=a.gen_python.split())
    print("hx-studio  http://%s:%d/  工程 %s" % (a.host, a.port, PROJECT.rel(PROJECT.dir)), flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
