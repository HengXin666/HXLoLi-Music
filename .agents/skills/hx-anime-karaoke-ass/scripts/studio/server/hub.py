#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验收台多工程: 一个服务同时挂所有歌 (dev/<番>/<歌>), 每首歌一个地址 /s/<番>/<歌>/.

为什么: 以前一首歌一个端口一个进程 (5398 ときめき, 5399 ろりこん ...), 并行做几首歌要起几个台子,
改了 kfx 动作表还要逐个重启. 现在一个进程, 首页列出全部工程; 生成器在子进程里跑 (代码改了下一次就生效, 不用重启).

工程发现规则 (只看两层, 和 skill 的 dev/<番>/<歌> 约定一致):
  有 design.md / out.kfx.ass / out.ass / studio.json 之一的目录算工程; 名字以 _ 开头的目录和 review/octotmp 跳过.
台子看哪份成品: studio.json 的 "ass" > 有 design.md 时 out.kfx.ass > out.ass.
"""
import json, os, re, threading, time
from urllib.parse import quote

SKIP = {"review", "octotmp", "scratch", "backup"}
MARK = ("design.md", "out.kfx.ass", "out.ass", "studio.json")


# Agent Notes: 验收台多工程 + 实时重建 (哪首歌看哪份成品)
# .agents/notes/implemented/feature/2026-11-24-karaoke-studio-multi.md
def pick_ass(d):
    try:
        m = json.load(open(os.path.join(d, "studio.json"), encoding="utf-8"))
        if isinstance(m, dict) and isinstance(m.get("ass"), str):
            return m["ass"]
    except (OSError, ValueError):
        pass
    if os.path.exists(os.path.join(d, "design.md")):
        return "out.kfx.ass"
    return "out.ass"


def url_of(anime, song):
    return "/s/%s/%s" % (quote(anime, safe=""), quote(song, safe=""))


class Registry:
    """dev/ 下的全部工程. Project 懒加载, 同一首歌全进程只有一个 Project (锁, 缓存, 生成器单飞都在它身上)."""

    def __init__(self, root, factory):
        self.root = os.path.abspath(root)
        self.factory = factory      # (dir, ass) -> Project
        self.lock = threading.Lock()
        self.cache = {}             # (anime, song) -> Project
        self._scan_at = 0
        self._list = []
        self.code_sig = lambda: 0   # app 注入: 生成器代码最新 mtime (ns)

    def scan(self, force=False):
        if not force and time.time() - self._scan_at < 3:
            return self._list
        out = []
        dev = os.path.join(self.root, "dev")
        for a in sorted(os.listdir(dev)) if os.path.isdir(dev) else []:
            da = os.path.join(dev, a)
            if a.startswith(("_", ".")) or a in SKIP or not os.path.isdir(da):
                continue
            for s in sorted(os.listdir(da)):
                ds = os.path.join(da, s)
                if s.startswith(("_", ".")) or s in SKIP or not os.path.isdir(ds):
                    continue
                if any(os.path.exists(os.path.join(ds, m)) for m in MARK):
                    out.append((a, s, ds))
        self._list, self._scan_at = out, time.time()
        return out

    # ---- 发布库: static/music/<番>/*.ass, 只读看 (学人做的, 对比老版本)
    def static_list(self):
        out = []
        sm = os.path.join(self.root, "static", "music")
        for a in sorted(os.listdir(sm)) if os.path.isdir(sm) else []:
            da = os.path.join(sm, a)
            if not os.path.isdir(da) or a == "fonts":
                continue
            for f in sorted(os.listdir(da)):
                if f.endswith(".ass"):
                    out.append((a, f[:-4], os.path.join(da, f)))
        return out

    @staticmethod
    def kind_of(path):
        """来源判据 (与 shared/reference-library.md 一致): 只读文件头 256 KB."""
        try:
            head = open(path, encoding="utf-8-sig", errors="replace").read(262144)
        except OSError:
            return "?", False
        tpl = bool(re.search(r"^Comment:[^\n]*,(?:template|code) ", head, re.M))
        title = ""
        for ln in head.splitlines()[:30]:
            if ln.startswith("Title:"):
                title = ln[6:].strip()
        if "hx-kara" in head[:4000]:
            k = "AI hx-kara"
        elif "assfx-band" in head[:6000]:
            k = "AI assfx"
        elif title.endswith("kfx") or "kfx3" in title:
            k = "AI kfx"
        elif "Aegisub" in head[:4000] or tpl:
            k = "人做 (Aegisub)"
        else:
            k = "AI 生成"
        return k, tpl

    def get(self, anime, song):
        if anime.startswith("static:"):
            a = anime[len("static:"):]
            f = os.path.realpath(os.path.join(self.root, "static", "music", a, song + ".ass"))
            if not f.startswith(os.path.join(self.root, "static", "music") + os.sep) or not os.path.isfile(f):
                return None
            with self.lock:
                p = self.cache.get((anime, song))
                if not p:
                    p = self.cache[(anime, song)] = self.factory(f, None)
                return p
        with self.lock:
            p = self.cache.get((anime, song))
            # 成品换了 (out.ass -> out.kfx.ass, 工程用 kfx 重做) 时不能继续用旧 Project: 它还在读已经移走的文件,
            # /api/ass/out 404, 监视器 libass "Failed to start a track" (用户 2026-11-24 罪恶王冠). 换一个新的.
            if p and (p.out_name == pick_ass(p.p("")) or not os.path.isdir(p.p(""))):
                return p
            if p:
                self.cache.pop((anime, song), None)
        for a, s, d in self.scan():
            if (a, s) == (anime, song):
                with self.lock:
                    p = self.cache.get((anime, song))
                    if not p:
                        p = self.factory(d, pick_ass(d))
                        self.cache[(anime, song)] = p
                return p
        self.scan(force=True)
        for a, s, d in self._list:
            if (a, s) == (anime, song):
                return self.get(anime, song)
        return None

    def summary(self):
        """首页用: 每首歌的成品, 大小, 最近一次生成, 设计稿问题数, 谁在看."""
        rows = []
        for a, s, d in self.scan(force=True):
            ass = pick_ass(d)
            f = os.path.join(d, ass)
            st = os.stat(f) if os.path.exists(f) else None
            with self.lock:
                p = self.cache.get((a, s))
            auto = (p.auto if p else None) or {}
            rows.append(dict(
                anime=a, song=s, url=url_of(a, s) + "/", ass=ass, kfx=os.path.exists(os.path.join(d, "design.md")),
                size_mb=round(st.st_size / 1e6, 1) if st else None,
                mtime=time.strftime("%m-%d %H:%M", time.localtime(st.st_mtime)) if st else None,
                mtime_ts=st.st_mtime if st else 0,
                viewers=p.viewers if p else 0,
                building=bool(p and p.gen_lock.locked()),
                last_build=auto.get("result"),
                stale=bool(st and os.path.exists(os.path.join(d, "design.md")) and
                           max(os.stat(os.path.join(d, "design.md")).st_mtime_ns, self.code_sig()) > st.st_mtime_ns),
                last_build_at=time.strftime("%H:%M:%S", time.localtime(auto["at"])) if auto.get("at") else None,
            ))
        rows.sort(key=lambda r: -r["mtime_ts"])
        return rows

    def static_summary(self):
        rows = []
        for a, s, f in self.static_list():
            st = os.stat(f)
            k, tpl = self.kind_of(f)
            stem = os.path.join(os.path.dirname(f), s)
            rows.append(dict(anime=a, song=s, url=url_of("static:" + a, s) + "/", kind=k, template=tpl,
                             draft=s.startswith("_") or "预览" in s,
                             audio=any(os.path.exists(stem + e) for e in (".flac", ".mp3", ".m4a", ".ogg", ".wav")),
                             size_mb=round(st.st_size / 1e6, 1), mtime=time.strftime("%Y-%m-%d", time.localtime(st.st_mtime))))
        return rows




def INDEX():
    """首页 (每次现读, 改了 html 不用重启)."""
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "hub_index.html"), encoding="utf-8") as f:
        return f.read()
