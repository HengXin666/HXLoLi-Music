# -*- coding: utf-8 -*-
"""阶段 E 的服务端分析: 歌词逐字信息 (振假名/词/字框), 时间线片段, 选区说明 (explain), 监视器命中 (hit).

全部只读: out.ass, 参考 ASS, out.manifest.json, timing.json, judge/arc.json, review/music-events.json.
fx 函数归属: manifest 每个单元只记 emit[fn] = {n, layers, t}, 不记逐条. 所以单条事件的归属按
"层号在 fn 的 layers 里 且 起点在 fn 的时间窗里" 求候选; 只有一个候选时是确定的, 多个时列出候选并标 ambiguous.
"""
import json, os, re, sys

from assfx.base import geom  # noqa: E402  只 import (库已冻结)

TAG = re.compile(r"\{[^}]*\}")
POS = re.compile(r"\\(?:pos|move)\(\s*([-\d.]+)\s*,\s*([-\d.]+)")
TEXT_STYLES = {"JP": "jp", "RB": "rb", "CN": "cn", "LAT": "jp"}
CARD_STYLES = {"CARD", "CARDCN", "TITLE", "TLAT", "PRO", "PROCN"}
FX_LAYERS = list(range(9))


def track_of(e):
    """事件 -> 时间线轨 id"""
    st = e["style"]
    if st == "FX":
        if e["name"].startswith("card:") or e["name"] in ("fx:title", "fx:pro", "fx:mid", "fx:out"):
            return "card"
        return "fx%d" % max(0, min(8, e["layer"]))
    if st in TEXT_STYLES:
        return TEXT_STYLES[st]
    if st in CARD_STYLES:
        return "card"
    return "other"


def unit_of(e):
    n = e["name"]
    return n.split(":", 1)[1] if ":" in n else n


def styles(text):
    out = {}
    for line in text.splitlines():
        if line.startswith("Style:"):
            p = [x.strip() for x in line[6:].split(",")]
            try:
                out[p[0]] = dict(font=p[1], fs=float(p[2]), bord=float(p[16]), an=int(p[18]))
            except (IndexError, ValueError):
                pass
    return out


class Analysis:
    def __init__(self, P):
        self.P = P

    # ---------- 基础数据
    def manifest(self):
        return self.P.json(self.P.p("out.manifest.json")) or {}

    def units(self):
        return {u["name"]: u for u in self.manifest().get("units", [])}

    def code(self):
        return (self.manifest().get("code") or {}).get("fns", {})

    def arc(self):
        a = self.P.json(self.P.p("judge", "arc.json")) or {}
        return {l["line"]: l for l in a.get("lines", [])}, a.get("sections", [])

    def music(self):
        for f in (self.P.p("review", "music-events.json"), self.P.p("judge", "music-events.json"),
                  self.P.p("music-events.json")):
            m = self.P.json(f)
            if m:
                return m
        return {}

    def ass_lines(self, which):
        path = self.P.p("out.ass") if which == "out" else self.P.ref_ass()
        if not path:
            return []
        return self.P.cached("lines:" + path, path, lambda p: self.P.text(p).splitlines())

    def raw(self, which, e):
        L = self.ass_lines(which)
        return L[e["ln"] - 1] if 0 < e["ln"] <= len(L) else ""

    # ---------- fx 归属
    def owners(self, e):
        u = self.units().get(unit_of(e))
        if not u:
            return []
        c = []
        for fn, em in (u.get("emit") or {}).items():
            t = em.get("t") or [-1e9, 1e9]
            if e["layer"] in (em.get("layers") or []) and t[0] - 0.02 <= e["t0"] <= t[1] + 0.02:
                c.append(fn)
        return c

    def fn_src(self, fn):
        if fn == "<lib>":
            return dict(file="assfx/layer/gen.py", line=None, note="库字层 (Karaoke 预设)")
        c = self.code().get(fn)
        return dict(file=c["file"], line=c["line"]) if c else dict(file=fn.split(":")[0], line=None)

    # ---------- 歌词: 振假名 / 词 / 字框 / 参考条数
    def lyric_extra(self, lines):
        P = self.P
        ev = P.events("out") or []
        st = styles(P.text(P.p("out.ass")))
        timing = P.json(P.p("timing.json")) or []
        rb, jpy = {}, {}
        for e in ev:
            if e["layer"] != 2 or not e["name"].startswith("ly:"):
                continue
            m = POS.search(e["text"])
            if not m:
                continue
            nm = e["name"][3:]
            x, y = float(m.group(1)), float(m.group(2))
            if e["style"] == "RB":
                rb.setdefault(nm, {}).setdefault((round(x, 1), TAG.sub("", e["text"])), (x, y, e["t0"]))
            elif e["style"] == "JP":
                jpy.setdefault(nm, []).append(y)
        refpf = P.profile("ref") or {}
        rper = refpf.get("per_line", {})
        fs_jp = st.get("JP", {}).get("fs", 84)
        fs_rb = st.get("RB", {}).get("fs", 34)
        for l in lines:
            nm = l["name"]
            ys = sorted(jpy.get(nm, []))
            l["jp_y"] = ys[len(ys) // 2] if ys else None
            l["fs"] = fs_jp
            l["ref_fx"] = rper.get(nm, 0)
            # 振假名: RB 字按 x 落到字宽里
            items = sorted((g[0], k[1]) for k, g in rb.get(nm, {}).items())
            for c in l["chars"]:
                c["ruby"] = "".join(txt for gx, txt in items if abs(gx - c["x"]) <= c["w"] / 2 + 2)
            for c in l["chars"]:
                # 字框 (1920x1080 坐标): x 是字中心, 宽取 layout 字宽, 高取 JP 字号
                if l["jp_y"] is not None:
                    c["box"] = [round(c["x"] - c["w"] / 2, 1), round(l["jp_y"] - fs_jp * 0.55, 1),
                                round(c["x"] + c["w"] / 2, 1), round(l["jp_y"] + fs_jp * 0.55, 1)]
            # 词 (timing.json 的 unit): 字与 mora 的时间重叠最大者
            mor = [m for m in timing if m.get("line") == l["line"]]
            for c in l["chars"]:
                best, ov = None, 0.0
                for m in mor:
                    o = min(c["e"], m["e"]) - max(c["s"], m["s"])
                    if o > ov:
                        best, ov = m, o
                c["unit"] = best["unit"] if best else None
                c["mora"] = [[m["text"], m["s"], m["e"]] for m in mor
                             if min(c["e"], m["e"]) - max(c["s"], m["s"]) > 0.005]
        return lines

    # ---------- 时间线片段: 每轨 x 每单元 一段
    def clips(self):
        P = self.P

        def build(p):
            ev = P.events("out") or []
            g = {}
            for e in ev:
                tr = track_of(e)
                if tr == "other":
                    continue
                k = (tr, unit_of(e))
                c = g.get(k)
                if c is None:
                    g[k] = c = dict(track=tr, unit=k[1], t0=e["t0"], t1=e["t1"], n=0, layers=set(), fns={})
                c["t0"] = min(c["t0"], e["t0"])
                c["t1"] = max(c["t1"], e["t1"])
                c["n"] += 1
                c["layers"].add(e["layer"])
                for fn in self.owners(e) or ["?"]:
                    c["fns"][fn] = c["fns"].get(fn, 0) + 1
            out = []
            for c in g.values():
                c["layers"] = sorted(c["layers"])
                c["fns"] = sorted(c["fns"].items(), key=lambda kv: -kv[1])
                c["t0"] = round(c["t0"], 3)
                c["t1"] = round(c["t1"], 3)
                out.append(c)
            out.sort(key=lambda c: (c["track"], c["t0"]))
            return out
        return P.cached("clips", P.p("out.ass"), build)

    def beats(self):
        m = self.music()
        strength = m.get("strength") or {}
        return dict(bpm=m.get("bpm"), grid=m.get("grid") or [], onset=m.get("onset") or [],
                    sub=m.get("sub") or [], strength={k: round(v, 3) for k, v in strength.items()})

    # ---------- explain
    def explain(self, sel, lyrics):
        """sel: [{line: <arc 行号>, from: i, to: j}] (字下标含两端). 返回分组, arc, 音乐事件, 参考对比."""
        P = self.P
        arc, sections = self.arc()
        by_line = {l["line"]: l for l in lyrics}
        ev = P.events("out") or []
        rev = P.events("ref") or []
        mus = self.music()
        out = []
        for s in sel:
            l = by_line.get(s.get("line"))
            if not l:
                continue
            ch = l["chars"]
            a, b = max(0, int(s.get("from", 0))), min(len(ch) - 1, int(s.get("to", len(ch) - 1)))
            if a > b:
                a, b = b, a
            whole = a == 0 and b == len(ch) - 1
            t0 = l["t"][0] if whole else ch[a]["s"]
            t1 = l["t"][1] if whole else ch[b]["e"]
            nm = l["name"]
            hit = [e for e in ev if unit_of(e) == nm and e["t1"] > t0 and e["t0"] < t1]
            groups = {}
            for e in hit:
                own = self.owners(e)
                fn = own[0] if len(own) == 1 else ("|".join(own) if own else "?")
                k = (fn, e["style"], e["layer"])
                gr = groups.get(k)
                if gr is None:
                    groups[k] = gr = dict(fn=fn, ambiguous=len(own) != 1, candidates=own, style=e["style"],
                                          layer=e["layer"], n=0, tags=e["text"][:160], lines=[],
                                          src=[self.fn_src(f) for f in (own or [])])
                gr["n"] += 1
                if len(gr["lines"]) < 400:
                    gr["lines"].append(e["ln"])
            counts = {}
            for e in hit:
                counts[track_of(e)] = counts.get(track_of(e), 0) + 1
            rhit = [e for e in rev if unit_of(e) == nm]
            rwin = [e for e in rhit if e["t1"] > t0 and e["t0"] < t1]

            def cat(es):
                c = {}
                for e in es:
                    k = "FX" if e["style"] == "FX" else e["style"]
                    c[k] = c.get(k, 0) + 1
                return c
            onset = [dict(t=t, s=(mus.get("strength") or {}).get(str(t))) for t in (mus.get("onset") or []) if t0 <= t < t1]
            sub = [t for t in (mus.get("sub") or []) if t0 <= t < t1]
            grid = [t for t in (mus.get("grid") or []) if t0 <= t < t1]
            ar = arc.get(l["line"], {})
            sec = next((x for x in sections if l["line"] in (x.get("lines") or [])), None)
            u = self.units().get(nm, {})
            out.append(dict(
                line=l["line"], name=nm, label=l.get("label"), text="".join(c["ch"] for c in ch[a:b + 1]), whole=whole,
                t0=round(t0, 3), t1=round(t1, 3), n=len(hit), counts=counts,
                groups=sorted(groups.values(), key=lambda g: (-g["n"])),
                arc=dict(role=ar.get("role"), technique=ar.get("technique"), idea=ar.get("idea"), why=ar.get("why"),
                         anchors=ar.get("anchors"), highlight=ar.get("highlight"), thread=ar.get("thread"),
                         section=sec.get("id") if sec else None, section_why=sec.get("why") if sec else None),
                params={k: v for k, v in (u.get("params") or {}).items() if k in ("fx", "ent", "ext", "hl", "density", "size", "alpha")},
                emit=[dict(fn=k, n=v.get("n"), layers=v.get("layers"), t=v.get("t"), src=self.fn_src(k))
                      for k, v in (u.get("emit") or {}).items()],
                music=dict(onset=onset, sub=sub, beats=len(grid), bpm=mus.get("bpm")),
                ref=dict(window=len(rwin), line=len(rhit), cat_window=cat(rwin), cat_line=cat(rhit),
                         out_window=cat(hit), out_line=cat([e for e in ev if unit_of(e) == nm]))))
        return out

    # ---------- 监视器命中
    def hit(self, t, x, y):
        P = self.P
        ev = P.events("out") or []
        st = styles(P.text(P.p("out.ass")))
        res = []
        for e in ev:
            if not (e["t0"] <= t < e["t1"]):
                continue
            s = st.get(e["style"], {})
            try:
                bb = geom.event_extent(e["text"], style_fs=s.get("fs", 40), style_bord=s.get("bord", 0),
                                       style_an=s.get("an", 5))
            except Exception:  # noqa: BLE001
                bb = None
            if not bb:
                continue
            pad = 6
            if bb[0] - pad <= x <= bb[2] + pad and bb[1] - pad <= y <= bb[3] + pad:
                res.append(dict(ln=e["ln"], style=e["style"], layer=e["layer"], name=e["name"], t0=e["t0"],
                                t1=e["t1"], box=[round(v, 1) for v in bb], track=track_of(e), fns=self.owners(e)))
        res.sort(key=lambda r: -r["layer"])
        return res
