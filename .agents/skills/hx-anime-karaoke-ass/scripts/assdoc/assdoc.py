# -*- coding: utf-8 -*-
"""ASS 的最小读写: 头部原样保留, band 登记行单独解析, 事件逐条成 dict.

为什么不复用 validate_ass.load_ass: 它只读不写, 且丢掉了头部原文.
预览台要把事件原样写回, 未改动的事件必须逐字不变 (Start/End 原串保留).

性能 (L7, 9131 事件工程): 时间串解析带记忆 (写回时判"改没改"不再重解析),
事件行一次 split 直接拆字段, 整份解析结果按全文缓存 (预览台每次构建都重读 raw 与锁快照,
内容没变就只拷贝事件 dict, 不逐条重解析). 输出与旧实现逐字节相同, 判据见 check_l7_perf.py.
"""
import re
from collections import OrderedDict

BAND_RE = re.compile(r";\s*assfx-band:\s*(\S+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)")
FIELDS = ("Layer", "Start", "End", "Style", "Name", "MarginL", "MarginR", "MarginV", "Effect", "Text")

_PT = {}                 # 时间串 -> 秒; 同一串的结果恒定, 记下来写回时直接查
_PT_MAX = 400000
_DOCS = OrderedDict()    # 全文 -> None (只见过一次) | (head, fmt, events, bands) 母本; 母本只发拷贝
_DOCS_MAX = 8


def pt(s):
    v = _PT.get(s)
    if v is None:
        if len(s) == 10 and s[1] == ":" and s[4] == ":":     # 常见的 h:mm:ss.cc, 切片即 split 的三段
            v = int(s[0]) * 3600 + int(s[2:4]) * 60 + float(s[5:])
        else:
            h, m, r = s.strip().split(":")
            v = int(h) * 3600 + int(m) * 60 + float(r)
        if len(_PT) >= _PT_MAX:
            _PT.clear()
        _PT[s] = v
    return v


def ts(t):
    """与 assfx.base.core.ts 同口径 (h:mm:ss.cc)."""
    cs = int(round(max(0.0, t) * 100))
    h, cs = divmod(cs, 360000); m, cs = divmod(cs, 6000); s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def parse_event(line):
    kind, rest = line.split(":", 1)
    v = rest.lstrip().split(",", 9)
    if len(v) < 10:
        raise KeyError("Text")       # 与旧实现 (dict(zip) 后取 Text) 同类报错
    L, S, E, st, nm, ml, mr, mv, ef, tx = v
    return dict(kind=kind.strip(), layer=int(L), S=S, E=E, s=pt(S), e=pt(E), style=st, name=nm,
                margins=(ml, mr, mv), effect=ef, text=tx)


def _keep(orig, t):
    """原串对应的时间与当前时间差 < 5ms 就用原串 (逐字不变), 否则重新格式化."""
    p = _PT.get(orig)
    if p is None:
        p = pt(orig)
    return orig if abs(p - t) < 0.005 else ts(t)


# Agent Notes: 未改动的事件按原串写回, 保证逐字节不变 (原 scripts/station/ 预览台的约定)
# .agents/notes/implemented/feature/2026-11-06-karaoke-preview-station.md
def event_line(ev):
    """改过时间的事件重新格式化; 没改过的用原串, 保证逐字不变."""
    m = ev["margins"]
    return (f"{ev['kind']}: {ev['layer']},{_keep(ev['S'], ev['s'])},{_keep(ev['E'], ev['e'])},"
            f"{ev['style']},{ev['name']},{m[0]},{m[1]},{m[2]},{ev['effect']},{ev['text']}")


def _parse_raw(text):
    # parse_event 内联进循环: 9000+ 行时函数调用与 dict(zip) 本身就是大头
    head, events, bands, fmt, sec = [], [], {}, None, None
    ptg, append = _PT.get, events.append
    for line in text.splitlines():
        c = line[:1]
        if c == "[":
            sec = line.strip()
        if sec == "[Events]":
            if (c == "D" and line.startswith("Dialogue:")) or (c == "C" and line.startswith("Comment:")):
                kind, rest = line.split(":", 1)
                v = rest.lstrip().split(",", 9)
                if len(v) < 10:
                    raise KeyError("Text")
                L, S, E, st, nm, ml, mr, mv, ef, tx = v
                s = ptg(S)
                if s is None:
                    s = pt(S)
                e = ptg(E)
                if e is None:
                    e = pt(E)
                # 键序与 parse_event 一致, 末尾 o = 文件内次序 (排序时破同刻平局)
                append({"kind": kind.strip(), "layer": int(L), "S": S, "E": E, "s": s, "e": e,
                        "style": st, "name": nm, "margins": (ml, mr, mv), "effect": ef, "text": tx,
                        "o": len(events)})
            elif c == "F" and line.startswith("Format:"):
                fmt = line
            continue
        if c == ";":
            m = BAND_RE.match(line)
            if m:
                bands[m.group(1)] = [float(x) for x in m.groups()[1:]]
        head.append(line)
    if fmt is None:
        fmt = "Format: " + ", ".join(FIELDS)
    return head, fmt, events, bands


class AssDoc:
    """head: [Events] 之前的所有行 (含 band 行); bands: name -> [x0,y0,x1,y1,t0,t1]."""

    def __init__(self, head, fmt, events, bands):
        self.head, self.fmt, self.events, self.bands = head, fmt, events, bands

    @classmethod
    def load(cls, path):
        with open(path, encoding="utf-8-sig") as f:
            return cls.parse(f.read())

    @classmethod
    def parse(cls, text):
        hit = _DOCS.get(text, False)
        if not hit:
            # 第一次见: 解析结果直接交出去 (省一遍拷贝, 一次性读的文件不付缓存代价);
            # 第二次见同一全文才留母本, 之后只拷贝不解析
            res = _parse_raw(text)
            _DOCS[text] = None if hit is False else res
            _DOCS.move_to_end(text)
            if len(_DOCS) > _DOCS_MAX:
                _DOCS.popitem(last=False)
            if hit is False:
                return cls(*res)
            hit = res
        else:
            _DOCS.move_to_end(text)
        head, fmt, events, bands = hit
        # 事件 dict 的值全是不可变对象 (str/int/float/tuple), 浅拷贝即与重新解析等价
        return cls(list(head), fmt, [dict(e) for e in events], {k: list(v) for k, v in bands.items()})

    def text(self):
        out, known = [], set()
        for line in self.head:
            m = BAND_RE.match(line) if line[:1] == ";" else None
            if m:
                name = m.group(1)
                known.add(name)
                b = self.bands.get(name)
                if b is None:
                    continue
                if [float(x) for x in m.groups()[1:]] != list(b):
                    line = f"; assfx-band: {name} " + " ".join(_num(v) for v in b)
            out.append(line)
        # 新出现的 band (只在锁快照里有) 补在 Script Info 末尾
        extra = [f"; assfx-band: {n} " + " ".join(_num(v) for v in b)
                 for n, b in self.bands.items() if n not in known]
        if extra:
            i = next((k for k, l in enumerate(out) if l.startswith("[") and k > 0), len(out))
            while i > 0 and not out[i - 1].strip():
                i -= 1
            out[i:i] = extra
        # 只按 (厘秒起点, 原文件次序) 排: 生成器按未取整的起点排过序, 再按层号重排会打乱同厘秒的事件,
        # 让"什么都没改"也产生 diff. 这样未改动的 raw 原样写回, 逐字节不变
        evs = sorted(self.events, key=lambda e: (round(e["s"] * 100), e.get("o", 0)))
        out += ["[Events]", self.fmt]
        ptg = _PT.get
        for ev in evs:                       # event_line 内联: 未改时间的事件只做一次查表
            S, E, s, e = ev["S"], ev["E"], ev["s"], ev["e"]
            p = ptg(S)
            if p is None:
                p = pt(S)
            if not abs(p - s) < 0.005:
                S = ts(s)
            p = ptg(E)
            if p is None:
                p = pt(E)
            if not abs(p - e) < 0.005:
                E = ts(e)
            m = ev["margins"]
            out.append(f"{ev['kind']}: {ev['layer']},{S},{E},{ev['style']},{ev['name']},"
                       f"{m[0]},{m[1]},{m[2]},{ev['effect']},{ev['text']}")
        return "\n".join(out) + "\n"

    def write(self, path):
        with open(path, "w", encoding="utf-8-sig") as f:
            f.write(self.text())
        return len(self.events)


def _num(v):
    return repr(round(float(v), 2))
