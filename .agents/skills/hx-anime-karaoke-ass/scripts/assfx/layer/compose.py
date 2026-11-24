# -*- coding: utf-8 -*-
"""组合器: 设计中间表示 -> Generator 要的 PHRASES 与 FXMAP. 每句 = 主母题 x 语法 + 辅助母题 x 语法 + 与上一句的关系,
写不出来的句子走逃生口 (escape: 工程自己的专属函数). 组合式不等于模板化: 词汇表 (motifs) 每首歌自己定,
同一种语法换个母题, 同一个母题换个语法, 都是另一种语言; 真正的高光仍可以手写.

用法 (工程的 make_ass.py):
    from assfx.layer.compose import Composer
    C = Composer(ir_path, here=HERE, theme=lambda p: C_of(p["i"]), beats=GRID_BEATS, shots=SHOT_CUTS, post=fx_bed_hook)
    PHRASES, FXMAP = C.build()
    G.render(PHRASES, FXMAP, seed=SEED)
    ...; doc.write(out); C.finish(out)        # 写 <out>.motifs.json, 给 gate/check_motif_mono.py
"""
import importlib
import os
import sys

from assfx.layer import ir as IR
from assfx.layer import provenance as PV
from assfx.layer.grammar import GRAMMAR
from assfx.draw.resolve import shape_fn

TEXT_DEF = dict(ent="rise", ext="rise", hl="wipe")
REL_SCALE = dict(carry=1.0, contrast=1.0, echo=1.0, cut=1.0, rest=0.5, none=1.0)
ROLE_N = dict(carrier=4, high=8, rest=2)


class Composer:
    def __init__(self, ir_path, here, theme, beats=None, shots=None, post=None, fonts=None):
        """theme(p) -> 本句色组 (dict, 含 hi/glow/dark/base/pale); post(f, ph, k, p): 每句组合之后的工程钩子 (氛围床等)."""
        self.path, self.here = ir_path, here
        self.ir = IR.load(ir_path)
        self.theme, self.post = theme, post
        self.beats, self.shots = sorted(beats or []), sorted(shots or [])
        self.fonts = fonts
        self.motifs = self.ir["motifs"]
        self._shape = {}
        if here not in sys.path:
            sys.path.insert(0, here)

    def shape(self, mid):
        if mid not in self._shape:
            self._shape[mid] = shape_fn(self.motifs[mid]["shape"], proj=self.here, fonts=self.fonts)
        return self._shape[mid]

    def _escape(self, spec):
        mod, _, fn = spec.partition(":")
        return getattr(importlib.import_module(mod), fn)

    def _times(self, p, ph, k):
        clock = p.get("clock", "voice")
        if clock == "beat":
            ts = [t for t in self.beats if k.t_in <= t <= k.t_end]
        elif clock == "shot":
            ts = [t for t in self.shots if k.t_in <= t <= k.t_end]
        else:
            ts = [c["s"] for c in ph.chars if c.get("kind") != "punct"]
        return ts or [ph.s]

    def _col(self, th, name):
        if name and name.startswith("#"):
            return name
        return th.get(name or "glow") or th["glow"]

    def _emit(self, f, ph, k, p, mid, role, prev):
        m = self.motifs[mid]
        n = int(round(p.get("params", {}).get("n", ROLE_N[p["role"]]) * REL_SCALE[p.get("relation", "none")]))
        size = float(m.get("size", 24)) * float(p.get("params", {}).get("size", 1.0))
        th = k.P["th"]
        col = self._col(th, m.get("color"))
        if p.get("relation") == "contrast" and prev is not None:
            col = self._col(th, "pale" if m.get("color") != "pale" else "glow")
        GRAMMAR[m["grammar"]](f, ph, k, self.shape(mid), col, size, max(1, n), self._times(p, ph, k))
        PV.note(mid, role, "grammar.%s" % m["grammar"])

    def _relation(self, f, ph, k, p, prev):
        rel = p.get("relation", "none")
        if prev is None or rel in ("none", "cut", "rest"):
            return
        pm = prev.get("main")
        if rel == "echo" and pm:                            # 上一句的主母题缩小在句首回响一下 (辅助身份, 不算第二个主母题)
            GRAMMAR["stamp"](f, ph, k, self.shape(pm), self._col(k.P["th"], "pale"), float(self.motifs[pm].get("size", 24)) * 0.6,
                             1, self._times(p, ph, k))
            PV.note("echo:" + pm, "aux", "relation.echo")
        elif rel == "carry":                                # 上一句的余光从左缘带进来
            x0, y0, x1, y1 = ph.ink
            f.glow(0, k.t_in, ph.s + 0.6, x0, (y0 + y1) / 2, 60, 40, self._col(prev["_th"], "glow"), a_peak=170, blur=18,
                   fade_in=0.2, fade_out=0.5)

    def _fn(self, p, prev):
        esc = self._escape(p["escape"]) if p.get("escape") else None

        def run(f, ph, k):
            PV.begin(k.key)
            try:
                p["_th"] = k.P["th"]
                if esc is None:                       # 逃生口句自己管句间关系 (例: layer/carry.py), 组合器不再叠一层
                    self._relation(f, ph, k, p, prev)
                if esc is not None:
                    if p.get("main"):                 # 逃生口自己画的那部分算作 IR 声明的主母题; 它再调别的主母题函数会另记一条
                        PV.note(p["main"], "main", "escape:" + p["escape"])
                    esc(f, ph, k)
                elif p.get("main"):
                    self._emit(f, ph, k, p, p["main"], "main", prev)
                for a in p.get("aux") or []:
                    self._emit(f, ph, k, p, a, "aux", prev)
                if self.post:
                    self.post(f, ph, k, p)
            finally:
                PV.end()
        run.__name__ = "compose_%02d" % p["i"]
        run.__wrapped__ = esc or GRAMMAR[self.motifs[p["main"]]["grammar"]] if (esc or p.get("main")) else None
        return run

    # Agent Notes: 组合式生成: 设计中间表示 + 形状来源 + 母题来源门禁 + 跨作品指纹
    # 
    def build(self):
        """Agent Notes
        .agents/notes/implemented/architecture/2026-11-17-karaoke-compositional-generator.md
        返回 (PHRASES, FXMAP). fx 名 = u<句号>, 一句一个组合函数; label 原样进清单 (验收台检查器显示)."""
        PHRASES, FXMAP, prev = [], {}, None
        for p in sorted(self.ir["phrases"], key=lambda q: q["i"]):
            name = "u%02d" % p["i"]
            o = dict(TEXT_DEF, **(p.get("text") or {}))
            PHRASES.append(dict(label=p.get("label") or name, lines=p.get("lines") or [p["i"]], th=self.theme(p), o=o, fx=name))
            FXMAP[name] = self._fn(p, prev)
            prev = p
        return PHRASES, FXMAP

    def finish(self, out):
        """生成之后调用: 写母题来源旁证 <out>.motifs.json. 单元 key 与 Generator 用的同一套 (phrase_keys)."""
        from assfx.layer.gen import phrase_keys
        PH = [dict(lines=p.get("lines") or [p["i"]]) for p in sorted(self.ir["phrases"], key=lambda q: q["i"])]
        keys = phrase_keys(PH)
        units = [(key, p["i"], p.get("main")) for key, p in zip(keys, sorted(self.ir["phrases"], key=lambda q: q["i"]))]
        return PV.write(out, units, self.path)
