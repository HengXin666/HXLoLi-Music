#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HX ASS studio 服务 (阶段 D, plan.md 3.8). 只用标准库.

用法:
  python3 scripts/studio/server/app.py --project dev/<番>/<歌> [--port 5199] [--host 127.0.0.1]

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
import refpick as REF  # noqa: E402  参考 ASS / 音频: 只认明确来源, 不挑
import hub as HUB  # noqa: E402  多工程: 一个服务挂全部歌, 每首 /s/<番>/<歌>/
import loop as LOOP  # noqa: E402  看, 挑, 改, 证: 对比对象 / 候选 / 挑选冻结 / 标注状态 (调 accept)
from assdoc import design as DESIGN  # noqa: E402  设计稿 design.md: 先写设计稿再渲染 (格式见 kfx/kfx_README.md)

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
    """字体文件的名字表. families: nameID 1/4/16 (给前端 availableFonts 建索引, 与旧行为一致);
    match: libass 按名字找字体时真正比对的那几个 (族名 1, 全名 4, PostScript 名 6), 小写去重;
    regular: 是不是常规字重 (同族多字重时 availableFonts 索引优先指向它); ok: 名字表解析成功没有.
    注意 nameID 16 (排版族名, 如 'Cormorant Garamond') 不在 match 里: libass 不认它, ASS 写这个名字会落到后备字体."""
    stem = os.path.splitext(os.path.basename(path))[0]
    try:
        from fontTools.ttLib import TTFont
        t = TTFont(path, lazy=True, fontNumber=0)
        names = {}
        for rec in t["name"].names:
            if rec.nameID in (1, 2, 4, 6, 16):
                try:
                    names.setdefault(rec.nameID, []).append(rec.toUnicode())
                except Exception:
                    pass
        fam = sorted({n for i in (1, 4, 16) for n in names.get(i, [])})
        match = sorted({n.strip().lower() for i in (1, 4, 6) for n in names.get(i, []) if n.strip()})
        sub = {n.strip().lower() for n in names.get(2, [])}
        try:
            w = t["OS/2"].usWeightClass
        except Exception:
            w = 400
        return dict(families=fam or [stem], match=match, regular=bool(sub & {"regular", "normal", "book", "roman"}) and w <= 500, ok=bool(match))
    except Exception:
        return dict(families=[stem], match=[], regular=False, ok=False)


FN_TAG = re.compile(r"\\fn([^\\}]*)")


def used_fonts(text):
    """ASS 实际会用到的字体名 -> {uses, line(首见行号), via(style 名或 '\\fn')}.
    Style 只算被 Dialogue 引用到的 (没事件用的 Style 不会去找字体); \\fn 扫全部 Dialogue 文本, Comment 不渲染不算.
    '@' 前缀 (竖排) 去掉再比, 与 libass 一致; 空 \\fn 是回到 Style 字体, 不算新名字."""
    styles, sfmt, efmt, used = {}, None, None, {}
    sec = ""
    for ln, line in enumerate(text.splitlines(), 1):
        st = line.strip()
        if st.startswith("["):
            sec = st.lower()
            continue
        if st.startswith("Format:"):
            f = [x.strip().lower() for x in st[7:].split(",")]
            if "styles" in sec:
                sfmt = f
            elif "events" in sec:
                efmt = f
            continue
        if st.startswith("Style:") and "styles" in sec:
            f = sfmt or ["name", "fontname"]
            p = [x.strip() for x in st[6:].split(",", len(f) - 1)]
            if len(p) >= 2 and "name" in f and "fontname" in f:
                styles[p[f.index("name")]] = (p[f.index("fontname")], ln)
            continue
        if not st.startswith("Dialogue:"):
            continue
        f = efmt or ["layer", "start", "end", "style", "name", "marginl", "marginr", "marginv", "effect", "text"]
        p = st[9:].lstrip().split(",", len(f) - 1)
        if len(p) < len(f):
            continue
        sty = p[f.index("style")].strip() if "style" in f else ""
        names = []
        if sty in styles:
            names.append((styles[sty][0], "style " + sty))
        elif sty.lstrip("*") in styles:
            names.append((styles[sty.lstrip("*")][0], "style " + sty))
        for m in FN_TAG.finditer(p[-1]):
            if m.group(1).strip():
                names.append((m.group(1), "\\fn"))
        for n, via in names:
            k = n.strip().lstrip("@").strip()
            if not k:
                continue
            u = used.setdefault(k, dict(name=k, uses=0, line=ln, via=set()))
            u["uses"] += 1
            u["via"].add(via)
    for u in used.values():
        u["via"] = sorted(u["via"])
    return used


class Project:
    def __init__(self, path):
        self.dir = os.path.abspath(path)
        self.out_name = "out.ass"   # --ass: 台子看的成品; kfx 生成器的产物是 out.kfx.ass
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
        self.cmp = None          # 台上选的对比对象 {"kind": ref|prev|cand, "issue", "c"}; None = 自动
        self.cmp_seq = 0
        self.viewers = 0         # 正在看这首的浏览器数 (/api/watch 连接)
        self.auto = None         # 最近一次重建 {sig, at, result}; 设计稿或 kfx 代码比成品新时自动重建
        self._dcache = None      # 设计稿解析缓存 (设计稿 mtime, 代码签名) -> dict

    # ---- 路径
    def p(self, *a):
        return os.path.join(self.dir, *a)

    def out(self):
        return self.p(self.out_name)

    def kfx(self):
        """kfx 模式: 成品不是 out.ass, 位置与特效全由 design.md 决定, 台上不重跑旧生成器."""
        return self.out_name != "out.ass"

    def rel(self, path):
        return os.path.relpath(path, self.root)

    def resolved(self, kind):
        # 原来取 "文件名含歌名" 的 sorted()[0]: "_" 前缀排在假名前, 静默选错. 规则见 refpick.py; 按相关 mtime 缓存
        d = os.path.join(self.root, "static", "music", self.anime)
        sig = tuple(os.stat(f).st_mtime_ns if os.path.exists(f) else 0 for f in (self.p(REF.FILE), os.path.join(self.root, "playlist.json"), d))
        with self.lock:
            hit = self._cache.get("ref:" + kind)
            if hit and hit[0] == sig:
                return hit[1]
        v = REF.resolve(self.root, self.anime, self.song, self.dir, kind)
        with self.lock:
            self._cache["ref:" + kind] = (sig, v)
        return v

    def ref_ass(self):
        return self.resolved("ass")["path"]

    def ref_info(self):
        r = self.resolved("ass")

        def dlg(p):
            return sum(1 for l in self.text(p).splitlines() if l.startswith("Dialogue:"))
        return dict(source=r["source"], error=r["error"], err_kind=r["err_kind"], set_at=r["set_at"],
                    candidates=[dict(path=self.rel(c), dialogues=self.cached("dlg:" + c, c, dlg),
                                     mtime=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.stat(c).st_mtime)))
                                for c in r["candidates"]])

    def audio(self):
        for c in ("song.mp3", "song.flac", "song.m4a"):
            if os.path.exists(self.p(c)):
                return self.p(c)
        return self.resolved("audio")["path"]

    META = "studio.json"   # 工程元数据: {"video": "相对工程目录的片源", "video_offset": 秒}; 不写则按 skill 约定找

    def meta(self):
        m = self.json(self.p(self.META))
        return m if isinstance(m, dict) else {}

    def video(self):
        """片源: studio.json 的 video > 01-source 契约的 base.mp4 (时间轴唯一基准). 不再有某首歌专属的默认文件名."""
        v = self.meta().get("video")
        for f in ([self.p(v)] if v else []) + [self.p("base.mp4")]:
            if os.path.isfile(f):
                return f
        return None

    def man_path(self):
        """台子读的单元清单: out.ass 旁的 out.manifest.json; v3 工程没有它时用 accept 的 raw 清单."""
        f = re.sub(r"\.ass$", "", self.out()) + ".manifest.json"
        if os.path.exists(f) or self.kfx():
            return f
        st = self.json(self.p("review", "accept", "state.json")) or {}
        raw = self.p(st.get("raw") or "out.raw.ass")
        return re.sub(r"\.ass$", "", raw) + ".manifest.json"

    def man(self):
        return self.json(self.man_path()) or {}

    def text_lift(self):
        """字层抬高量 (assfx Doc.TEXT_LIFT): 清单 meta.text_lift; 老清单没有就按 out.ass 里 ly: 事件的最小层号推.
        原来写死 0 (只对 TEXT_LIFT=0 的工程成立), 缺省 20 的工程振假名 / 字框 / 中文全读不到."""
        m = (self.man().get("meta") or {}).get("text_lift")
        if isinstance(m, int):
            return m
        ly = [e["layer"] for e in (self.events("out") or []) if e["name"].startswith("ly:")]
        return min(ly) if ly else 0

    def body_layer(self):
        """字身层 (JP/RB/CN 正文所在层) = text_lift + 2 (anim.py 字层 0..4, 2 为正文)."""
        return self.text_lift() + 2

    def cmp_ass(self):
        """对比对象 (监视器 "参考" 那一路): 用户在台上选的 (参考 / 上一版 / 候选) > 参考 ASS > 上一版. 规则在 loop.py."""
        return LOOP.cmp_target(self)["path"]

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
        path = self.out() if which == "out" else self.cmp_ass()
        return self.cached("ev:" + str(path), path, lambda p: parse_events(self.text(p)))

    def profile(self, which="out"):
        # which: out / ref (= 对比对象, 可能是上一版或候选) / trueref (= 参考 ASS 本身, 门禁阈值只从它来)
        path = self.out() if which == "out" else self.ref_ass() if which == "trueref" else self.cmp_ass()
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
        if "video_offset" in self.meta():
            return float(self.meta()["video_offset"])
        sh = self.json(self.p("judge", "shots.json")) or {}
        return float(sh.get("video_offset", 0.0)) if isinstance(sh, dict) else 0.0

    # ---- 资源
    def _font_names(self):
        """fonts 目录每个文件的名字表. 每个文件按 (路径, mtime) 缓存, 首屏之后只剩 listdir + stat, 不再读 ttf."""
        d = self.fonts_dir()
        out = []
        if d:
            for f in sorted(os.listdir(d)):
                if f.lower().endswith((".ttf", ".otf", ".ttc", ".woff2")):
                    fp = os.path.join(d, f)
                    out.append((f, self.cached("fam:" + fp, fp, family_of)))
        return out

    def fallback_font(self):
        """后备字体 (ASS 里写了本机没有的字体时用). 默认是 Liberation Sans, 没有中日文字形, 会画成方块;
        人做的老 ASS 用 方正/FOT 之类的商用字体, 本仓库没有, 所以给一个能显示中日文的后备."""
        for d in (os.path.join(self.root, "static", "music", "fonts"), os.path.join(SKILL, "fonts")):
            for n in ("NotoSansSC-Regular.ttf", "LXGWWenKai-Medium.ttf"):
                if os.path.exists(os.path.join(d, n)):
                    return "/fonts/" + n
        return None

    def fonts(self):
        return [dict(file=f, url="/fonts/" + f, families=n["families"], regular=n["regular"]) for f, n in self._font_names()]

    def fonts_missing(self):
        """out.ass 用到、但 fonts 目录里没有哪个文件的族名/全名/PostScript 名对得上的字体 (忽略大小写).
        libass 遇到这种会拿后备字体画: 能显示, 但字形和出片可能不同. 不是 fatal.
        ASS 扫描按 out.ass 的 mtime 缓存; 比对是集合查找, 很便宜."""
        path = self.out()
        used = self.cached("usedfonts:" + path, path, lambda p: used_fonts(self.text(p))) or {}
        names = self._font_names()
        have = {m for _, n in names for m in n["match"]}
        return [dict(u) for k, u in sorted(used.items()) if k.lower() not in have]

    def fonts_unparsed(self):
        """名字表读不出来的字体文件 (fontTools 缺失 / 文件坏). 它们参与不了比对, 可能让 fonts_missing 误报, 一并告诉前端."""
        return [f for f, n in self._font_names() if not n["ok"]]

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
        if not os.path.exists(self.out()):   # 还没有成品 (只有设计稿)
            return []
        man = self.man()
        arc = {l["line"]: l for l in (self.json(self.p("judge", "arc.json")) or {}).get("lines", [])}
        ev = self.events("out") or []
        # 中文按 x 拼; 只认静止的 \pos 事件 (入场 / 退场 \move 的位置偏开, 会把每个字重复拼一遍), 某句没有 \pos 才用 \move 终点
        cn, cnm = {}, {}
        body = self.body_layer()
        for e in ev:
            if e["style"] == "CN" and e["name"].startswith("ly:") and e["layer"] == body:
                mv = re.search(r"\\move\([-\d.]+,[-\d.]+,([-\d.]+),([-\d.]+)", e["text"])
                m = mv or re.search(r"\\pos\(([-\d.]+),([-\d.]+)", e["text"])
                (cnm if mv else cn).setdefault(e["name"][3:], {})[(round(float(m.group(1)), 1) if m else 0)] = TAG.sub("", e["text"])
        for k, v in cnm.items():
            cn.setdefault(k, v)
        try:
            prof = self.profile("out") or {}
        except ValueError:   # 不是本 skill 格式 (没有 JP 层) 的 ASS
            prof = {}
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
                              technique=a.get("technique"), cn="".join(cnl[k] for k in sorted(cnl)) or u.get("cn", ""),
                              fx=per.get(name, 0), fn=u.get("params", {}).get("fx"), chars=chars))
        if not lines:
            # 老工程没有单元清单 (out.manifest.json): 用 timing.json 的逐字时间拼歌词面板, 中文按 ly:pNN 从成品里取
            lines = timing_lines(self, cn)
        lines.sort(key=lambda l: (l["t"] or [0])[0])
        return self.A.lyric_extra(lines) if lines else lines

    def lyrics_cached(self):
        return self.cached("lyrics", self.out(), lambda p: self.lyrics()) or []

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

    REVIEW_KINDS = ("bad", "good", "redo", "note")

    @staticmethod
    def review_bad(rec):
        # 前端按这几个字段画 (r.sel.some / t0 t1 / kind 着色): 服务端放过而前端抛 = 两边校验不一致, 一律算坏行
        if not isinstance(rec, dict):
            return "不是对象 (%s)" % type(rec).__name__
        if not isinstance(rec.get("sel"), list):
            return "缺 sel 或 sel 不是列表"
        for k in ("t0", "t1"):
            if not isinstance(rec.get(k), (int, float)) or isinstance(rec.get(k), bool):
                return "%s 不是数字" % k
        if rec.get("kind") not in Project.REVIEW_KINDS:
            return "kind 不认识: %r" % (rec.get("kind"),)
        return None

    def reviews(self):
        """读 review.jsonl. 一行坏不拖累别的行: 好行照常返回, 坏行进 bad_lines (行号从 1 起, 带原因和开头片段).
        逐行按字节拆, 每行单独解码, 所以一行不是 UTF-8 也只坏这一行."""
        f = self.review_path()
        if not os.path.exists(f):
            return [], []
        with open(f, "rb") as fh:
            raw = fh.read()
        items, bad = [], []
        for no, b in enumerate(raw.split(b"\n"), 1):
            if not b.strip():
                continue
            head = b[:60].decode("utf-8", "replace")
            try:
                rec = json.loads(b.decode("utf-8"))
            except UnicodeDecodeError as e:
                bad.append(dict(line=no, error="不是 UTF-8: %s" % e.reason, head=head))
                continue
            except ValueError as e:
                bad.append(dict(line=no, error="JSON 读不出: %s" % e, head=head))
                continue
            why = self.review_bad(rec)
            if why:
                bad.append(dict(line=no, error=why, head=head))
            else:
                if "status" not in rec:   # 老记录没有 status: 按 open/noted 显示, 并标明是推定的 (accept sync 会写实)
                    rec = dict(rec, status="noted" if rec.get("kind") == "note" else "open", status_src="default")
                items.append(rec)
        return items, bad

    def append_review(self, rec):
        """原子追加: 原文件字节原样搬 (坏行一个字节都不改) + 新记录 -> 同目录临时文件 -> fsync -> os.replace.
        唯一的改动: 原文件末尾没有换行时补一个 "\n" 作为分隔, 否则新记录会粘到末行上, 两条一起坏;
        末行本身的字节不变, 仍是同一行号. 失败时删临时文件, 原文件不动, 抛 OSError 给调用方报错."""
        f = self.review_path()
        old = b""
        if os.path.exists(f):
            with open(f, "rb") as fh:
                old = fh.read()
        sep = b"\n" if old and not old.endswith(b"\n") else b""
        data = old + sep + (json.dumps(rec, ensure_ascii=False) + "\n").encode("utf-8")
        tmp = "%s.tmp-%d-%d" % (f, os.getpid(), threading.get_ident())
        try:
            with open(tmp, "wb") as fh:
                fh.write(data)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, f)
        except BaseException:
            try:
                os.remove(tmp)
            except OSError:
                pass
            raise

    def watched(self):
        w = {k: (os.stat(p).st_mtime_ns if p and os.path.exists(p) else 0) for k, p in (
            ("out", self.out()), ("edl", self.p("mv.edl.json")), ("review", self.review_path()),
            ("manifest", self.man_path()), ("placement", self.p(PLC.FILE)),
            ("ref", self.p(REF.FILE)), ("playlist", os.path.join(self.root, "playlist.json")),
            ("prev", self.p("review", "accept", "prev.ass")), ("design", self.p("design.md")))}
        w["job"] = self.job["seq"]
        w["accept"] = LOOP.stamp(self)
        w["cmp"] = self.cmp_seq
        return w

    # ---- 设计稿 design.md (唯一的真相: 先改设计稿再渲染). 只在 PUT /api/design 时写
    def design(self):
        f = self.p("design.md")
        if not os.path.exists(f):
            return dict(exists=False, path=self.rel(f), raw="", lines=[], errors=[], **{"global": []})
        raw = open(f, encoding="utf-8").read()
        key = (os.stat(f).st_mtime_ns, code_sig())
        if self._dcache and self._dcache[0] == key:
            d = json.loads(self._dcache[1])
        else:
            d = design_cli(self.dir, "parse")
            self._dcache = (key, json.dumps(d))
        # mtime 给字符串: ns 时间戳超过 2^53, JSON 数字到浏览器会丢精度, 回传后永远对不上 (以前每次保存都 409)
        d.update(exists=True, path=self.rel(f), raw=raw, mtime=str(os.stat(f).st_mtime_ns))
        if self.auto and self.auto.get("result") and not self.auto["result"].get("ok"):
            d.setdefault("errors", []).insert(0, "自动重建失败 (%s), 监视器里还是上一版: %s" % (
                time.strftime("%H:%M:%S", time.localtime(self.auto["at"])), "; ".join(map(str, self.auto["result"].get("errors", [])[:3]))))
        return d

    def design_put(self, b):
        f = self.p("design.md")
        raw = open(f, encoding="utf-8").read() if os.path.exists(f) else ""
        if b.get("mtime") is not None and os.path.exists(f) and str(b["mtime"]).strip() not in (str(os.stat(f).st_mtime_ns), ""):
            raise ValueError("设计稿在别处改过了, 先刷新再改")
        if "key" in b:
            new = DESIGN.replace_section(raw, b["key"], b["body"])
        else:
            new = b["raw"]
        DESIGN.parse(new)  # 解析不崩才落盘; 校验问题照样存, 前端显示
        tmp = f + ".tmp"
        open(tmp, "w", encoding="utf-8").write(new)
        os.replace(tmp, f)
        return self.design_rebuild()

    # Agent Notes: 设计稿保存即重建 out.kfx.ass, 监视器靠 /api/watch 的 out mtime 自动重载
    # .agents/notes/implemented/architecture/2026-11-22-karaoke-kfx-single-generator.md
    def design_rebuild(self):
        """保存后照设计稿重建成品 (kfx_build, 约 1-2 s). 设计稿不过校验时旧成品不动, 错误显示在面板顶上."""
        if self.out_name != DESIGN.OUT:
            d = self.design()
            d["errors"].insert(0, "没有重建: 验收台在看 %s; 用 --ass %s 启动才会保存即重建" % (self.out_name, DESIGN.OUT))
            return d
        if not self.gen_lock.acquire(blocking=False):
            raise ValueError("生成器正在运行, 等它结束再保存")
        try:
            r = design_cli(self.dir, "build")
            self.auto = dict(sig=self.build_sig(), at=time.time(), result=r)
        finally:
            self.gen_lock.release()
        d = self.design()
        d["build"] = r
        if not r["ok"]:
            d["errors"].insert(0, "没有重建: 设计稿有 %d 处问题, 监视器里还是上一版" % len(r["errors"]))
        return d

    def build_sig(self):
        f = self.p("design.md")
        return (os.stat(f).st_mtime_ns if os.path.exists(f) else 0, code_sig())

    def maybe_autobuild(self):
        """设计稿或 kfx 代码比成品新就在后台重建 (只在有人看这首时由 /api/watch 调). 同一签名失败过不重试, 免得刷屏."""
        if self.out_name != DESIGN.OUT or not os.path.exists(self.p("design.md")):
            return
        sig = self.build_sig()
        if self.auto and self.auto.get("sig") == sig:
            return
        out = self.out()
        om = os.stat(out).st_mtime_ns if os.path.exists(out) else 0
        # 设计稿改了: 自动重建. 只是 kfx 代码改了: 默认不自动 (几首歌共用 kfx, 做 A 歌改的代码不能悄悄改掉已认可的 B 歌成品),
        # 首页标「待重建」, 点一下用最新代码重建. 正在做的歌可在 studio.json 写 "auto_rebuild": "all" 让代码一改也自动重建; "off" 全关.
        mode = (self.meta().get("auto_rebuild") or "design").lower()
        use_code = mode == "all"
        newest = max(sig[0], sig[1]) if use_code else sig[0]
        if mode == "off" or (om and om >= newest):
            self.auto = dict(sig=sig, at=self.auto["at"] if self.auto else 0, result=(self.auto or {}).get("result"))
            return
        if not self.gen_lock.acquire(blocking=False):
            return

        def run():
            try:
                r = design_cli(self.dir, "build")
            except Exception as e:  # noqa: BLE001
                r = dict(ok=False, events=0, ms=0, errors=["%s: %s" % (type(e).__name__, e)])
            finally:
                self.gen_lock.release()
            self.auto = dict(sig=sig, at=time.time(), result=r)
            self._dcache = None
        self.auto = dict(sig=sig, at=time.time(), result=None)
        threading.Thread(target=run, daemon=True).start()

    # ---- 歌词位置预设 (placement.json). 公式全在 assfx/text/placement.py; 这里只读清单 + 调它.
    PREVIEW_NOTE = "近似预览, 跨区域特效不跟随, 真实效果以应用后重跑为准"

    def placement_state(self, cand=None):
        cur = PLC.load(self.dir)
        res = dict(current=cur, default=PLC.DEFAULT, source="file" if os.path.exists(self.p(PLC.FILE)) else "default", enums=dict(v=PLC.V, h=PLC.H, order=PLC.ORDER, gap=list(PLC.GAP)),
                   job={k: v for k, v in self.job.items() if k != "thread"}, note=self.PREVIEW_NOTE, frozen=self.frozen_goods())
        if cand:
            calib = self.json(self.p("calib.json"))
            man = self.man()
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
                os.replace(tout, self.out())
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

KARA = re.compile(r"\\k[fo]?(\d+)", re.I)


def karaoke_lines(P):
    """没有清单 (manifest) 时的歌词面板: 读 ASS 里 Effect=karaoke 的原句 (Aegisub 模板的源句, 人做的 ASS 都留着).
    中文行 (样式名含 CN/CH/中) 按时间并到同时段的日文行上."""
    jp, cn, cnk = [], [], []
    for ln in P.text(P.out()).splitlines():
        if not ln.startswith(("Comment:", "Dialogue:")):
            continue
        p = ln.split(":", 1)[1].lstrip().split(",", 9)
        if len(p) < 10 or "karaoke" not in p[8].lower():
            continue
        t0, t1, sty, text = ts(p[1]), ts(p[2]), p[3], p[9]
        plain = re.sub(r"\|<?[^|{\s]*", "", TAG.sub("", text.replace("}", "} "))).replace(" ", "").strip() if "|" in text else TAG.sub("", text).strip()
        if not plain:
            continue
        is_cn = bool(re.search(r"cn|ch|中|zh", sty, re.I) and not re.search(r"jp", sty, re.I))
        if is_cn:
            cn.append((t0, t1, plain))
        chars, t = [], t0
        for m in re.finditer(r"\{([^}]*)\}([^{]*)", text if text.startswith("{") else "{}" + text):
            k = KARA.search(m.group(1))
            d = int(k.group(1)) / 100.0 if k else 0.0
            syl = re.sub(r"\|<?[^|{]*$", "", m.group(2)) if "|" in m.group(2) else m.group(2)   # Aegisub 振假名写法 漢|<かん
            if syl:
                chars.append(dict(i=len(chars), ch=syl, s=round(t, 3), e=round(t + d, 3), x=0, w=0))
            t += d
        (cnk if is_cn else jp).append(dict(t0=t0, t1=t1, text=plain, chars=chars))
    if not jp:            # 只留了中文源句 (Bravely You): 中文当主行
        jp, cn = cnk, []
    if not jp:
        return event_lines(P)
    jp.sort(key=lambda x: x["t0"])
    out = []
    for i, L in enumerate(jp):
        c = [x[2] for x in cn if x[0] < L["t1"] and x[1] > L["t0"]]
        out.append(dict(name="k%03d" % i, line=i, label=None, t=[L["t0"], L["t1"]], band=None, text=L["text"], role=None,
                        technique=None, cn=c[0] if c else "", fx=0, fn=None, chars=L["chars"]))
    return out


def event_lines(P):
    """没有清单也没有 karaoke 源句的成品 (AI 第一代 assfx / 其他脚本生成): 从事件拼歌词面板.
    取日文 / 中文样式里事件最多的那一层; 事件名是 ly:pNN 就按名字分句, 否则按开始时间聚句 (同句字的开始时间相同或相差很小).
    字按 \\pos 的 x 排, 同一个字在 20 px 内重复出现 (多层描边 / 光晕) 只留一个."""
    ev = [e for e in (P.events("out") or []) if TAG.sub("", e["text"]).strip() and "\\p1" not in e["text"]]
    isjp = lambda s: bool(re.search(r"jp", s, re.I)) and not re.search(r"furi|glow|rb|title", s, re.I)
    iscn = lambda s: bool(re.search(r"cn|ch", s, re.I)) and not re.search(r"furi", s, re.I)

    def collect(pred):
        es = [e for e in ev if pred(e["style"])]
        if not es:
            return []
        cnt = {}
        for e in es:
            cnt[e["layer"]] = cnt.get(e["layer"], 0) + 1
        L = max(cnt, key=cnt.get)
        es = sorted((e for e in es if e["layer"] == L), key=lambda e: e["t0"])
        groups, byname = [], {}
        for e in es:
            nm = re.match(r"(?:ly:)?([Lp]\d+)", e["name"])
            if nm:
                g = byname.get(nm.group(1))
                if g is None:
                    g = byname[nm.group(1)] = dict(key=nm.group(1), ev=[])
                    groups.append(g)
            elif groups and groups[-1]["key"].startswith("t") and e["t0"] - groups[-1]["ev"][0]["t0"] < 0.35:
                g = groups[-1]
            else:
                g = dict(key="t%d" % len(groups), ev=[])
                groups.append(g)
            g["ev"].append(e)
        out = []
        for g in groups:
            ch = []
            evs = g["ev"]
            if any("\\pos(" in e["text"] for e in evs):   # 有静止位置就不用入场/退场的 \\move (起止点偏开, 会把字记两遍)
                evs = [e for e in evs if "\\pos(" in e["text"]]
            for e in evs:
                m = re.search(r"\\pos\(([-\d.]+),", e["text"]) or re.search(r"\\move\([-\d.]+,[-\d.]+,([-\d.]+),", e["text"])
                ch.append((float(m.group(1)) if m else 0.0, TAG.sub("", e["text"]).strip(), e["t0"], e["t1"]))
            ch.sort()
            xs = sorted({round(c[0]) for c in ch})
            gaps = sorted(b - a for a, b in zip(xs, xs[1:]) if b - a > 4)
            near = max(20, 0.8 * gaps[int(len(gaps) * 0.75)]) if gaps else 20   # 同一个字在不到一个字距内重复 = 描边 / 光晕 / 抖动层
            keep = []
            for c in ch:
                if any(k[1] == c[1] and abs(k[0] - c[0]) < near for k in keep[-3:]):
                    continue
                keep.append(c)
            out.append(dict(key=g["key"], t0=min(e["t0"] for e in g["ev"]), t1=max(e["t1"] for e in g["ev"]), ch=keep))
        return out

    jp, cn = collect(isjp), collect(iscn)
    lines = []
    for i, u in enumerate(sorted(jp, key=lambda u: u["t0"])):
        chars = [dict(i=j, ch=c[1], s=c[2], e=c[3], x=c[0], w=0) for j, c in enumerate(u["ch"])]
        best = max(cn, key=lambda c: min(c["t1"], u["t1"]) - max(c["t0"], u["t0"]), default=None)
        ok = best and min(best["t1"], u["t1"]) - max(best["t0"], u["t0"]) > 0
        name = u["key"] if not u["key"].startswith("t") else "e%03d" % i
        lines.append(dict(name=name, line=i, label=None, t=[u["t0"], u["t1"]], band=None, text="".join(c["ch"] for c in chars),
                          role=None, technique=None, cn="".join(c[1] for c in best["ch"]) if ok else "", fx=0, fn=None, chars=chars))
    return lines


def timing_lines(P, cn):
    t = P.json(P.p("timing.json"))
    if not isinstance(t, list):
        return []
    by = {}
    for u in t:
        if isinstance(u, dict) and "line" in u and "s" in u:
            by.setdefault(u["line"], []).append(u)
    out = []
    for li in sorted(by):
        us = sorted(by[li], key=lambda u: (u.get("unit", 0), u.get("mora", 0)))
        name = "p%02d" % li
        chars = [dict(i=i, ch=u.get("text", ""), s=u["s"], e=u.get("e", u["s"]), x=0, w=0) for i, u in enumerate(us)]
        c = cn.get(name, {})
        out.append(dict(name=name, line=li, label=None, t=[us[0]["s"], us[-1].get("e", us[-1]["s"])], band=None,
                        text="".join(x["ch"] for x in chars), role=None, technique=None,
                        cn="".join(c[k] for k in sorted(c)), fx=0, fn=None, chars=chars))
    return out


class StaticProject(Project):
    """发布库里的一份 ASS (static/music/<番>/<文件>.ass): 只读地看 (学人做的, 对比老版本). 没有工程目录, 设计稿, 视频.
    批注写到 dev/review/static/<番>/<歌>.review.jsonl, 不往发布目录写东西."""

    def __init__(self, ass):
        super().__init__(os.path.dirname(ass))
        self.out_name = os.path.basename(ass)
        self.anime = os.path.basename(self.dir)
        self.song = os.path.splitext(self.out_name)[0]
        self.static = True
        self._review = os.path.join(self.root, "dev", "review", "static", self.anime, self.song + ".review.jsonl")

    def kfx(self):
        return True

    def audio(self):
        stem = os.path.join(self.dir, self.song)
        for ext in (".flac", ".mp3", ".m4a", ".ogg", ".wav"):
            if os.path.exists(stem + ext):
                return stem + ext
        return None

    def video(self):
        return None

    def append_review(self, rec):
        os.makedirs(os.path.dirname(self._review), exist_ok=True)
        return super().append_review(rec)

    def lyrics(self):
        k = super().lyrics()
        if k:
            return k
        k = karaoke_lines(self)
        try:
            return self.A.lyric_extra(k) if k else k
        except Exception:  # noqa: BLE001  人做的 ASS 没有本 skill 的字层, 位置信息补不出来: 只给文字与时间
            return k


CODE_DIRS = (os.path.join(SCRIPTS, "kfx"), os.path.join(SCRIPTS, "assdoc"))


def code_sig():
    """生成器代码签名 = kfx/ assdoc/ 下 .py 的最新 mtime. 变了就说明动作表/生成器改过, 设计稿要重解析/重建."""
    m = 0
    for d in CODE_DIRS:
        try:
            for n in os.listdir(d):
                if n.endswith(".py"):
                    m = max(m, os.stat(os.path.join(d, n)).st_mtime_ns)
        except OSError:
            pass
    return m


GEN_PY = [sys.executable]
_CLI = r"""
import json, sys, os
sys.path.insert(0, sys.argv[1])
from assdoc import design as D
proj, mode = sys.argv[2], sys.argv[3]
if mode == "build":
    r = D.rebuild(proj)
else:
    f = os.path.join(proj, D.FILE)
    r = D.parse(open(f, encoding="utf-8").read(), proj=proj)
sys.stdout.write("\n@@JSON@@" + json.dumps(r, ensure_ascii=False, default=str))
"""


def design_cli(proj, mode):
    """设计稿解析 / 重建放子进程: 每次都是磁盘上最新的 kfx 代码 (以前在台子进程里 import 一次, 改了动作表要重启台子)."""
    r = subprocess.run(GEN_PY + ["-c", _CLI, SCRIPTS, proj, mode], capture_output=True, text=True, timeout=600)
    i = r.stdout.rfind("@@JSON@@")
    if r.returncode != 0 or i < 0:
        tail = (r.stderr or r.stdout).strip().splitlines()[-6:]
        if mode == "build":
            return dict(ok=False, events=0, ms=0, errors=["生成器崩了: " + " | ".join(tail)])
        return dict(lines=[], errors=["设计稿解析崩了: " + " | ".join(tail)], **{"global": []})
    return json.loads(r.stdout[i + len("@@JSON@@"):])


_TLS = threading.local()
DEFAULT = None      # 单工程模式 (--project) 的工程
REG = None          # 多工程模式 (--root) 的登记表


class _Current:
    """PROJECT = 这次请求的工程 (线程局部). 多工程时由 /s/<番>/<歌>/ 前缀决定, 单工程时就是 --project."""

    def __getattr__(self, k):
        p = getattr(_TLS, "p", None) or DEFAULT
        if p is None:
            raise LookupError("没有选工程: 从首页进入某首歌 (/s/<番>/<歌>/)")
        return getattr(p, k)

    def __setattr__(self, k, v):
        setattr(getattr(_TLS, "p", None) or DEFAULT, k, v)


PROJECT = _Current()


def cur():
    """这次请求的工程本体 (不是代理): 要交给别的线程的一律用它."""
    p = getattr(_TLS, "p", None) or DEFAULT
    if p is None:
        raise LookupError("没有选工程")
    return p
URL_HEADS = ("/api/", "/media/", "/fonts/", "/octopus/")


def _prefixed(o, pfx):
    if isinstance(o, str):
        return pfx + o if o.startswith(URL_HEADS) else o
    if isinstance(o, list):
        return [_prefixed(x, pfx) for x in o]
    if isinstance(o, dict):
        return {k: _prefixed(v, pfx) for k, v in o.items()}
    return o


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "hx-studio/0.1"

    def log_message(self, *a):
        pass

    # ---- 输出
    def send_json(self, obj, code=200):
        if getattr(self, "pfx", ""):
            obj = _prefixed(obj, self.pfx)
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

    def route(self):
        """多工程: /s/<番>/<歌>/... 选工程并去掉前缀; 返回 False = 已经回了 (首页 / 列表 / 404)."""
        _TLS.p, self.pfx = None, ""
        raw = urlparse(self.path)
        if raw.path.startswith("/s/"):
            parts = raw.path.split("/", 4)          # ['', 's', 番, 歌, rest]
            if len(parts) < 4 or not REG:
                self.err(404, "没有这个工程")
                return False
            p = REG.get(unquote(parts[2]), unquote(parts[3]))
            if p is None:
                self.err(404, "没有这个工程: %s/%s" % (unquote(parts[2]), unquote(parts[3])))
                return False
            _TLS.p = p
            self.pfx = "/s/%s/%s" % (parts[2], parts[3])
            rest = "/" + (parts[4] if len(parts) > 4 else "")
            self.path = rest + (("?" + raw.query) if raw.query else "")
            return True
        if REG and DEFAULT is None:
            if raw.path in ("/", "/index.html"):
                self.send_text(HUB.INDEX(), "text/html; charset=utf-8", etag=False)
                return False
            if raw.path == "/api/projects":
                self.send_json(dict(projects=REG.summary()))
                return False
            if raw.path == "/api/library":
                self.send_json(dict(library=REG.static_summary()))
                return False
            if raw.path.startswith("/api/") or raw.path.startswith(("/media/", "/fonts/")):
                self.err(404, "先选工程: 地址要带 /s/<番>/<歌>/")
                return False
        return True

    def do_GET(self):
        if not self.route():
            return
        u = urlparse(self.path)
        path, q = unquote(u.path), {k: v[-1] for k, v in parse_qs(u.query).items()}
        P = getattr(_TLS, "p", None) or DEFAULT   # 多工程首页下取静态资源 (/assets /octopus) 时没有工程
        try:
            if path == "/api/project":
                v = P.video()
                return self.send_json(dict(
                    dir=P.rel(P.dir), anime=P.anime, song=P.song, duration=P.duration(),
                    audio=[("/media/" + P.rel(P.audio())) if P.audio() else None],
                    video=("/media/" + P.rel(v)) if v else None,
                    out_ass="/api/ass/out", ref_ass="/api/ass/ref" if P.cmp_ass() else None,
                    ref_path=P.rel(P.cmp_ass()) if P.cmp_ass() else None, ref=P.ref_info(), cmp=LOOP.cmp_info(P),
                    audio_error=None if P.audio() else P.resolved("audio")["error"],
                    fonts=P.fonts(), fonts_missing=P.fonts_missing(), fonts_unparsed=P.fonts_unparsed(), edl=P.edl(), sections=P.sections(),
                    octopus="/octopus/" if find_octopus() else None, fallback_font=P.fallback_font(),
                    static=bool(getattr(P, "static", False))))
            if path in ("/api/ass/out", "/api/ass/ref"):
                f = P.out() if path.endswith("out") else P.cmp_ass()
                if not f or not os.path.exists(f):
                    return self.err(404, "no ass")
                return self.send_text(P.text(f))
            if path == "/api/imgrefs":
                # \\1img 引用清单 (小 JSON). 以前前端为了找贴图把整份 ASS (10-20 MB) 再下一遍再扫
                f = P.out() if q.get("which", "out") == "out" else P.cmp_ass()
                refs = P.cached("img:" + str(f), f, lambda x: sorted({r.strip() for r in re.findall(r"\\[1-4]img\(([^)]+)\)", P.text(x))
                                                                    if r.strip() and not r.strip().startswith("data:") and "!" not in r and "$" not in r})) if f else None
                return self.send_json(dict(refs=refs or []))
            if path == "/api/lyrics":
                return self.send_json(dict(lines=P.lyrics_cached()))
            if path == "/api/design":
                return self.send_json(P.design())
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
                try:
                    pf = P.profile(which)
                except ValueError as e:   # 不是本 skill 格式的 ASS (发布库里人做的), 没有 JP/CN 层: 没有画像, 不算服务错误
                    return self.err(404, "没有特效画像: %s" % e)
                if pf is None:
                    return self.err(404, "no ass")
                res = dict(which=which, step=CFP.STEP, profile=pf)
                ref = P.profile("trueref")
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
                man = P.man()
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
                items, bad = P.reviews()
                return self.send_json(dict(items=items, bad_lines=bad))
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
            if path.startswith(("/api/img/out/", "/api/img/ref/")):
                # \\1img 贴图: 按 ASS 所在目录解析 (同 render_octopus.py), 前端取回后写进 worker 虚拟 FS
                which = path[len("/api/img/"):len("/api/img/") + 3]
                a = P.out() if which == "out" else P.cmp_ass()
                if not a:
                    return self.err(404, "no ass")
                d = os.path.realpath(os.path.dirname(a))
                f = os.path.realpath(os.path.join(d, path[len("/api/img/out/"):]))
                ok = f.startswith(d + os.sep) and os.path.isfile(f)
                return self.send_file(f) if ok else self.err(404, "no image")
            if path.startswith("/media/"):
                f = os.path.realpath(os.path.join(P.root, path[len("/media/"):]))
                ok = (f.startswith(P.dir + os.sep) or f.startswith(os.path.join(P.root, "static", "music") + os.sep))
                return self.send_file(f) if ok else self.err(403, "forbidden")
            if path.startswith("/octopus/"):
                d = find_octopus()
                f = os.path.realpath(os.path.join(d, path[len("/octopus/"):])) if d else None
                return self.send_file(f, "max-age=3600") if f and f.startswith(os.path.realpath(d)) else self.err(404, "no")
            if path.startswith("/fonts/"):
                name = path[len("/fonts/"):]
                for d in (P.fonts_dir(), os.path.join(P.root, "static", "music", "fonts"), os.path.join(SKILL, "fonts")):
                    f = os.path.realpath(os.path.join(d, name)) if d else None
                    if f and f.startswith(os.path.realpath(d) + os.sep) and os.path.isfile(f):
                        return self.send_file(f, "max-age=3600")
                return self.err(404, "no")
            if path.startswith("/api/loop") or path.startswith("/api/ass/cand") or path == "/api/ass/prev":
                return LOOP.get(self, P, path, q)
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
        if not self.route():
            return
        u = urlparse(self.path)
        if u.path == "/api/rebuild":   # 首页的「重建」: 照设计稿重建一次 (子进程, 最新代码)
            P = cur()
            if not P.gen_lock.acquire(blocking=False):
                return self.err(409, "生成器正在运行")
            try:
                r = design_cli(P.dir, "build")
                P.auto = dict(sig=P.build_sig(), at=time.time(), result=r)
            finally:
                P.gen_lock.release()
            return self.send_json(r, 200 if r.get("ok") else 400)
        if u.path == "/api/placement":
            return self.post_placement()
        if u.path == "/api/ref":
            return self.post_ref()
        if u.path.startswith("/api/loop/"):
            return LOOP.post(self, cur(), u.path)
        if u.path != "/api/review":
            return self.err(404, "unknown api")
        b = self.body() or {}
        need = {"sel", "t0", "t1", "kind"}
        if not isinstance(b, dict) or not need <= set(b):
            return self.err(400, "需要字段 %s" % sorted(need))
        if b["kind"] not in Project.REVIEW_KINDS:
            return self.err(400, "kind 只能是 bad/good/redo/note")
        rec = dict(id="r%d" % int(time.time() * 1000), sel=b["sel"], t0=b["t0"], t1=b["t1"], kind=b["kind"],
                   tags=b.get("tags", []), text=b.get("text", ""), frame=b.get("frame"),
                   created=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                   # 处理状态: 提出时 open (批注 noted); accept intake/sync 回写 issue 与 changes (accept/reviewlog.py)
                   status="noted" if b["kind"] == "note" else "open", changes=[])
        why = Project.review_bad(rec)
        if why:  # 写进去也只会变成坏行: 直接拒, 不落盘
            return self.err(400, "标注字段不对: %s" % why)
        try:
            with PROJECT.lock:
                PROJECT.append_review(rec)
        except OSError as e:
            return self.err(500, "标注没写进去: %s" % e)
        return self.send_json(rec, 201)

    def post_ref(self):
        # 界面里点「用这份」: 只接受候选; 写 ref.json 并留指定时间. {"ass": null} 清除手动指定
        P = cur()
        b = self.body()
        if not isinstance(b, dict) or "ass" not in b or not (b["ass"] is None or isinstance(b["ass"], str)):
            return self.err(400, "需要 {ass: 候选路径 或 null}")
        try:
            with P.lock:
                REF.choose(P.root, P.anime, P.song, P.dir, "ass", b["ass"])
        except ValueError as e:
            return self.err(400, str(e))
        return self.send_json(dict(ref_ass="/api/ass/ref" if P.cmp_ass() else None,
                                   ref_path=P.rel(P.cmp_ass()) if P.cmp_ass() else None, ref=P.ref_info(), cmp=LOOP.cmp_info(P)))

    def post_placement(self):
        P = cur()
        b = self.body() or {}
        if not isinstance(b, dict):
            return self.err(400, "需要 {v, h, order, gap}")
        pre = dict(PLC.DEFAULT, **{k: b[k] for k in PLC.DEFAULT if k in b})
        bad = [k for k, al in (("v", PLC.V), ("h", PLC.H), ("order", PLC.ORDER), ("gap", tuple(PLC.GAP))) if pre[k] not in al]
        if bad:
            return self.err(400, "未知取值: %s" % ", ".join("%s=%s" % (k, pre[k]) for k in bad))
        if P.kfx():
            return self.err(409, "kfx 模式: 版式写在 design.md 的 全局 里, 在设计稿面板改完保存即重建")
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
        if not self.route():
            return
        u = urlparse(self.path)
        if u.path == "/api/design":
            b = self.body()
            if not isinstance(b, dict) or not (("key" in b and isinstance(b.get("body"), str)) or isinstance(b.get("raw"), str)):
                return self.err(400, "需要 {key, body} (改一节) 或 {raw} (整份)")
            try:
                with PROJECT.lock:
                    return self.send_json(PROJECT.design_put(b))
            except (KeyError, ValueError) as e:
                return self.err(409 if "别处" in str(e) else 400, str(e).strip("'"))
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
        P = getattr(_TLS, "p", None) or DEFAULT
        last = P.watched()
        P.viewers += 1
        try:
            P.maybe_autobuild()
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
                if n % 2 == 0:
                    P.maybe_autobuild()
                cur = P.watched()
                ch = [k for k in cur if cur[k] != last.get(k)]
                if ch:
                    last = cur
                    frame(dict(type="changed", what=ch, state=cur))
                n += 1
                if n % 40 == 0:
                    frame(dict(type="ping"))
        except (BrokenPipeError, ConnectionResetError, OSError):
            return
        finally:
            P.viewers -= 1


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        if not isinstance(sys.exc_info()[1], (ConnectionResetError, BrokenPipeError)):  # 浏览器断开媒体流是常态
            super().handle_error(request, client_address)


def make_server(project, host="127.0.0.1", port=5199, review=None, gen_cmd=None, ass="out.ass", root=None):
    global DEFAULT, REG
    if gen_cmd:
        GEN_PY[:] = list(gen_cmd)
    if root and not project:   # 多工程
        def factory(d, a):
            if a is None:            # 发布库: d 是 ASS 文件本身
                return StaticProject(d)
            p = Project(d)
            p.out_name = a
            if gen_cmd:
                p.gen_cmd = list(gen_cmd)
            return p
        DEFAULT, REG = None, HUB.Registry(root, factory)
        REG.code_sig = code_sig
        srv = Server((host, port), H)
        srv.daemon_threads = True
        return srv
    DEFAULT = Project(project)
    PROJECT.out_name = ass
    if gen_cmd:
        PROJECT.gen_cmd = list(gen_cmd)
    if review:
        PROJECT._review = os.path.abspath(review)  # 测试用: 批注写到临时文件, 不碰工程
    srv = Server((host, port), H)
    srv.daemon_threads = True
    return srv


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", help="只看一首: 工程目录 dev/<番名>/<歌名>. 不给就是多工程 (--root)")
    ap.add_argument("--root", default=None, help="多工程: 仓库根 (默认按本文件位置找). 首页列出 dev/<番>/<歌> 全部工程")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=5199)
    ap.add_argument("--gen-python", default=sys.executable, help="POST /api/placement 重跑生成器用的解释器 (需 fonttools)")
    ap.add_argument("--ass", default="out.ass",
                    help="台子看的成品 (工程内文件名). hx-kfx v2: --ass out.kfx.ass, 清单读 out.kfx.manifest.json")
    a = ap.parse_args(argv)
    root = a.root or (None if a.project else repo_root(HERE))
    srv = make_server(a.project, a.host, a.port, gen_cmd=a.gen_python.split(), ass=a.ass, root=root)
    if DEFAULT is not None:
        print("hx-studio  http://%s:%d/  工程 %s" % (a.host, a.port, PROJECT.rel(PROJECT.dir)), flush=True)
    else:
        print("hx-studio  http://%s:%d/  多工程 %d 首 (%s/dev)" % (a.host, a.port, len(REG.scan(True)), REG.root), flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
