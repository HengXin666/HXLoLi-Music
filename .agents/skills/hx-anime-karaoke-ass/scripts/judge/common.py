# -*- coding: utf-8 -*-
"""判断档产物的共用读取与结果收集.

产物都在 proj/judge/ 下. 格式见 shared/judge-formats.md.
句子用 line 序号 (与 timing.json 的 line 相同) + text (原文去掉注音) 定位.
text 对不上时判 FAIL: 歌词改过, 产物要重做.
"""
import contextlib, io, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

OK, WARN, BAD = "PASS", "WARN", "FAIL"
ELEM_RE = re.compile(r"\|\s*\*\*([^|*]+)\*\*\s*\|\s*(\d+)\s*\|")
HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
EVENT_KINDS = ("onset", "sub", "section", "beat", "mora", "silence")
TS_RE = re.compile(r"^(?:(\d+):)?(\d+(?:\.\d+)?)$")


class Res:
    """收集 (级别, 项, 说明). 只要有 FAIL, 退出码就是 1."""

    def __init__(self):
        self.rows = []

    def add(self, lvl, item, msg=""):
        self.rows.append((lvl, item, msg))

    def ok(self, item, msg=""):
        self.add(OK, item, msg)

    def warn(self, item, msg):
        self.add(WARN, item, msg)

    def bad(self, item, msg):
        self.add(BAD, item, msg)

    def check(self, cond, item, msg):
        """cond 为真记 PASS, 否则记 FAIL 并带上 msg. 返回 cond."""
        self.add(OK if cond else BAD, item, "" if cond else msg)
        return bool(cond)

    def failed(self):
        return [r for r in self.rows if r[0] == BAD]

    def show(self, quiet=False):
        for lvl, item, msg in self.rows:
            if quiet and lvl == OK:
                continue
            print("%s %s%s" % (lvl, item, ("  " + msg) if msg else ""))


def load_json(path):
    """返回 (数据, 错误). 文件不存在时错误为 'missing'."""
    if not os.path.exists(path):
        return None, "missing"
    try:
        return json.load(open(path, encoding="utf-8")), None
    except Exception as exc:
        return None, "JSON 解析失败: %s" % exc


def jpath(proj, name):
    return os.path.join(proj, "judge", name)


def ts(v):
    """时间戳转秒. 接受数字, "83.2", "1:23", "1:23.5". 不合法返回 None."""
    if isinstance(v, (int, float)):
        return float(v)
    m = TS_RE.match(str(v).strip()) if v is not None else None
    if not m:
        return None
    return int(m.group(1) or 0) * 60 + float(m.group(2))


class Song:
    """一首歌的基础事实: 句子原文, 每句时间, 番剧元素名, 音乐事件."""

    def __init__(self, proj):
        self.proj = proj
        self.texts = self._texts()
        self.spans = self._spans()
        self.elements = self._elements()
        self.events = self._events()

    def _texts(self):
        from assfx.base.lyrics import load
        with contextlib.redirect_stdout(io.StringIO()):     # lyrics lint 的提示不进判据输出
            lines = load(os.path.join(self.proj, "lyrics.txt"))
        return ["".join(u["surf"] for u in ln["units"]) for ln in lines]

    def _spans(self):
        rows, err = load_json(os.path.join(self.proj, "timing.json"))
        out = {}
        for r in rows or []:
            s, e = out.get(r["line"], (r["s"], r["e"]))
            out[r["line"]] = (min(s, r["s"]), max(e, r["e"]))
        return out

    def _elements(self):
        p = os.path.join(self.proj, "anime.elements.md")
        if not os.path.exists(p):
            return {}
        return {m.group(1).strip(): int(m.group(2)) for m in ELEM_RE.finditer(open(p, encoding="utf-8").read())}

    def _events(self):
        """音乐事件, 按类型分: onset / sub / section / beat (来自 review/music-events.json),
        mora (人声音拍起点, 来自 timing.json). 没有事件表时 section 退回 grid.json 段落起点."""
        ev = {"mora": sorted(r["s"] for r in (load_json(os.path.join(self.proj, "timing.json"))[0] or []))}
        d, _ = load_json(os.path.join(self.proj, "review", "music-events.json"))
        self.has_events = isinstance(d, dict)
        if self.has_events:
            for k, src in (("onset", "onset"), ("sub", "sub"), ("section", "section"), ("beat", "grid")):
                ev[k] = sorted(float(x["t"] if isinstance(x, dict) else x) for x in d.get(src) or [])
        else:
            g, _ = load_json(os.path.join(self.proj, "grid.json"))
            ev["section"] = [float(s[0]) for s in (g or {}).get("segments", [])]
        return ev

    def gaps(self, min_len=1.0):
        """句间静默 [(t0, t1)], 长度 >= min_len 秒."""
        sp = sorted(self.spans.values())
        return [(a[1], b[0]) for a, b in zip(sp, sp[1:]) if b[0] - a[1] >= min_len]

    def event_ok(self, kind, t, tol=0.08):
        """返回 (True/False/None, 说明). None = 本工程没有事件表, 这一类事件无从核对 (判据按 FAIL 处理)."""
        if kind == "silence":
            hit = any(g0 - tol <= t <= g1 + tol for g0, g1 in self.gaps())
            return hit, "" if hit else "t=%.2f 不在任何 >=1s 的句间静默里" % t
        lst = self.events.get(kind)
        if not lst:
            return None, ("没有事件表 (review/music-events.json), 只许绑 section / mora / silence, 不许绑 %s" % kind
                          if not self.has_events else "事件表里没有 %s 事件" % kind)
        near = min(abs(x - t) for x in lst)
        return near <= tol, "" if near <= tol else "t=%.2f 离最近的 %s 事件 %.2fs (容差 %.2fs)" % (t, kind, near, tol)

    @property
    def n(self):
        return len(self.texts)

    def song_span(self):
        if not self.spans:
            return None
        return min(s for s, _ in self.spans.values()), max(e for _, e in self.spans.values())

    def line_ok(self, row):
        """row 带 line 与 text. 返回错误说明, 无错返回 None."""
        i = row.get("line") if isinstance(row, dict) else None
        if not isinstance(i, int) or not 0 <= i < self.n:
            return "line=%r 不是有效句序号 (0..%d)" % (i, self.n - 1)
        if row.get("text") != self.texts[i]:
            return "line %d 的 text 与歌词不符 (歌词: %s). 歌词改过时要重做这一句" % (i, self.texts[i])
        return None


def nonempty(v):
    return isinstance(v, str) and v.strip() != ""


def skeleton(proj):
    """打印每句的 line + text, 供填 lines.visual.json 与 arc.json 时复制, 不手抄原文."""
    song = Song(proj)
    rows = [{"line": i, "text": t} for i, t in enumerate(song.texts)]
    print(json.dumps(rows, ensure_ascii=False, indent=1))
