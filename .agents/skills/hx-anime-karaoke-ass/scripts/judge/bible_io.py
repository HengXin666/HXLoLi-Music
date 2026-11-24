# -*- coding: utf-8 -*-
"""作品设计圣经的共用读取. 产物在 proj/bible/, 格式见 steps/3-anime-bg/11-design-bible/impl/formats.md.

专属度 unique 0..3 的口径:
  3 = 只在这部作品成立 (专有名词或专属设定, 换番名就说不通)
  2 = 本作赋予了专门含义, 但形状在别处也常见 (例: 普通的红眼, 在本作是某类人的标志)
  1 = 题材通用 (剑, 魔法阵, 火光)
  0 = 任何作品都成立 (花, 心, 泪)
来源类型只有四种: official (官方设定, 官网, 主创访谈) / original (原作原文) /
community (百科, 博客, 问答, 媒体报道) / screen (只有画面证据).
"""
import json, os, re

from judge.common import load_json

FILES = ("symbols.json", "characters.json", "scenes.json", "lyric-map.json", "directions.json", "landing.json")
SRC_TYPES = ("official", "original", "community", "screen")
FIRST_HAND = ("official", "original")
HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def bpath(proj, name):
    return os.path.join(proj, "bible", name)


def load(proj, name):
    return load_json(bpath(proj, name))


def nonempty(v):
    return isinstance(v, str) and v.strip() != ""


class Bible:
    """一首歌的圣经: 来源表, 符号表, 角色, 名场面, 台词, 逐句对位. 缺的文件记在 errors."""

    def __init__(self, proj):
        self.proj = proj
        self.errors = {}
        self.data = {}
        for f in FILES:
            d, err = load(proj, f)
            self.data[f] = d if isinstance(d, dict) else {}
            if err:
                self.errors[f] = err
            elif not isinstance(d, dict):
                self.errors[f] = "顶层要是 JSON 对象"
        sy = self.data["symbols.json"]
        self.work = sy.get("work") or {}
        self.sources = {s.get("id"): s for s in sy.get("sources") or [] if isinstance(s, dict)}
        self.symbols = {s.get("id"): s for s in sy.get("symbols") or [] if isinstance(s, dict)}
        sc = self.data["scenes.json"]
        self.scenes = {s.get("id"): s for s in sc.get("scenes") or [] if isinstance(s, dict)}
        self.quotes = {s.get("id"): s for s in sc.get("quotes") or [] if isinstance(s, dict)}
        self.chars = [c for c in self.data["characters.json"].get("characters") or [] if isinstance(c, dict)]

    # ---------------- 来源与专属度
    def ref_sources(self, refs):
        """refs -> 有效来源 id 的去重列表 (按出现顺序)."""
        out = []
        for r in refs or []:
            sid = r.get("src") if isinstance(r, dict) else None
            if sid in self.sources and sid not in out:
                out.append(sid)
        return out

    def types_of(self, refs):
        return {self.sources[s].get("type") for s in self.ref_sources(refs)}

    def n_sources(self, sym):
        return len(self.ref_sources(sym.get("refs")))

    def screen_only(self, sym):
        t = self.types_of(sym.get("refs"))
        return not t or t == {"screen"}

    def unique(self, sid):
        """符号的有效专属度: 只有画面证据的符号最多算 1 (只学形状, 不编语义)."""
        s = self.symbols.get(sid)
        if not s:
            return 0
        u = s.get("unique") if isinstance(s.get("unique"), int) else 0
        return min(u, 1) if self.screen_only(s) else u

    def exclusive(self, sid):
        return self.unique(sid) >= 2

    # ---------------- 名字
    def char_names(self):
        out = []
        for c in self.chars:
            out += [n for n in [c.get("name")] + list(c.get("aliases") or []) if nonempty(n)]
        return out

    def proper_nouns(self):
        """盲审要涂掉的词: 番名与别名, 角色名, 符号名与别名. 长的先涂, 免得涂掉一半."""
        words = [self.work.get("title")] + list(self.work.get("aliases") or []) + self.char_names()
        for k, s in self.symbols.items():
            if self.exclusive(k):           # 通用符号 (羽毛, 雨) 的名字不涂, 涂了反而像在藏线索
                words += [s.get("name")] + list(s.get("aliases") or [])
        words = {w.strip() for w in words if nonempty(w) and len(w.strip()) >= 2}
        return sorted(words, key=len, reverse=True)

    def known_id(self, rid):
        return rid in self.symbols or rid in self.scenes or rid in self.quotes


def background_names(proj):
    """anime.background.json 里的角色名 (日文名与中文名)."""
    d, _ = load_json(os.path.join(proj, "anime.background.json"))
    out = []
    for c in (d or {}).get("characters") or []:
        out += [n for n in (c.get("name"), c.get("name_cn")) if nonempty(n)]
    return out


def name_hit(name, pool):
    """名字对得上: 相等, 或一方包含另一方 (日文全名与简称). 至少 2 个字."""
    n = (name or "").strip()
    return len(n) >= 2 and any(n == p or n in p or (len(p) >= 2 and p in n) for p in pool)


def dump(obj):
    return json.dumps(obj, ensure_ascii=False, indent=1)
