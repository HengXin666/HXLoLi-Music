# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "fonttools",
# ]
# ///

"""
生成器通用骨架：逐句出入场窗口规划 + 渲染 + band 登记 + 卡片（标题/间奏/片尾）+ 常用小工具。

用法（见 templates/make_ass_template.py）：
    from assfx.layer.gen import Generator, find, seq, span, mid, flicker, sway
    G = Generator(doc, L, lines, TM)
    G.render(PHRASES, FXMAP)           # PHRASES: [dict(lines=[..], th=..., o=..., fx="name", zh=可选)]
    G.card("title", t0, t1, items, fx_fn)

出入场规则（避免同位置两句叠字，也避免字幕在无声处挂太久）：
  * 退场 t_out：最后一拍唱出 ≥0.12s 后；若离下一句还早，等长音结束 +0.25s，但不晚于下一句首拍前 0.75s
  * 退场时长：按到下一句首拍的剩余时间自适应（≥0.2s）；衔接紧时取消逐字错落
  * 入场 t_in：上一句退场完成 ~90% 之后，最早首拍前 lead(默认 0.8s)，最迟首拍前 0.05s
"""
import random
from assfx.base.core import ms, al
from assfx.layer.fx import FX
from assfx.text.anim import Karaoke


# ------------------------------------------------------------------ 查字/几何
def find(ph, s):
    return [c for c in ph.chars if c["ch"] == s]


def seq(ph, s, nth=0):
    """按显示文本查找连续字符（latin 单元算多字符）；nth=第几次出现"""
    txt = "".join(c["ch"] for c in ph.chars); start = -1
    for _ in range(nth + 1):
        start = txt.find(s, start + 1)
        if start < 0:
            return []
    acc = 0; res = []
    for c in ph.chars:
        if start <= acc < start + len(s):
            res.append(c)
        acc += len(c["ch"])
    return res


def span(chs):
    return chs[0]["x"] - chs[0]["w"] / 2, chs[-1]["x"] + chs[-1]["w"] / 2


def mid(chs):
    a, b = span(chs); return (a + b) / 2


def flicker(n, period, a_lo, a_hi, t0=0):
    return "".join(f"\\t({t0+int(k*period)},{t0+int((k+0.5)*period)},\\alpha{al(a_lo)})\\t({t0+int((k+0.5)*period)},{t0+int((k+1)*period)},\\alpha{al(a_hi)})" for k in range(n))


def sway(n, period, a, t0=0, tag="frz"):
    return "".join(f"\\t({t0+int(k*period)},{t0+int((k+0.5)*period)},\\{tag}{a})\\t({t0+int((k+0.5)*period)},{t0+int((k+1)*period)},\\{tag}{-a})" for k in range(n))


# ------------------------------------------------------------------ 生成器
class Generator:
    def __init__(self, doc, layout, lines, TM, lead=0.8, verbose=True):
        self.doc, self.L, self.lines, self.TM = doc, layout, lines, TM
        self.lead = lead; self.verbose = verbose
        self.phs, self.ks = [], []

    def build(self, PHRASES):
        self.phs = []
        for P in PHRASES:
            zh = P.get("zh") or " ".join(self.lines[li]["zh"] for li in P["lines"] if self.lines[li]["zh"])
            self.phs.append(self.L.phrase(self.lines, P["lines"], self.TM, zh))
        return self.phs

    def plan(self, PHRASES):
        phs = self.phs; out = []
        for i, (P, ph) in enumerate(zip(PHRASES, phs)):
            o = dict(dict(din=0.5, dout=0.6, stg_out=0.02), **P.get("o", {}))
            last_s = ph.chars[-1]["s"]
            nxt = phs[i + 1].s if i + 1 < len(phs) else ph.e + 3
            t_out = max(last_s + 0.12, min(ph.e + P.get("hold", 0.25), nxt - 0.75))
            if "t_out" in P:
                t_out = P["t_out"]
            room = nxt - 0.12 - t_out
            if room < o["dout"] + len(ph.chars) * o["stg_out"]:
                o["stg_out"] = 0.0
                o["dout"] = max(0.2, min(o["dout"], room * 0.8))
            out.append((o, t_out))
        return out

    def render(self, PHRASES, FXMAP, seed=100):
        if not self.phs:
            self.build(PHRASES)
        plan = self.plan(PHRASES); phs = self.phs
        for i, (P, ph) in enumerate(zip(PHRASES, phs)):
            o, t_out = plan[i]
            lead = P.get("lead", self.lead)
            if i:
                po, pto = plan[i - 1]
                prev_end = pto + po["dout"] + max(len(phs[i - 1].chars), len(phs[i - 1].cn)) * po["stg_out"]
                t_in = max(ph.s - lead, prev_end - 0.08)
            else:
                t_in = ph.s - lead
            t_in = min(t_in, ph.s - 0.05)
            o["din"] = max(0.12, min(o["din"], ph.s - t_in))
            name = P.get("name", f"p{i:02d}")
            k = Karaoke(self.doc, ph, name, P["th"], random.Random(seed + i), **o)
            k.render(t_in, t_out)
            k.t_end = max(c["te"] for c in ph.chars) + 0.2
            k.P = P; k.i = i
            self.doc.band(name, *ph.band, t_in, k.t_end)
            f = FX(self.doc, name, ph.band, seed=1000 + i)
            fn = FXMAP.get(P.get("fx")) if P.get("fx") else None
            if fn:
                fn(f, ph, k)
            self.ks.append(k)
            if self.verbose:
                print(f"{name} {ph.s:7.2f}-{ph.e:7.2f} in {t_in:7.2f} out {t_out:7.2f} dout {o['dout']:.2f} "
                      f"band {tuple(round(v) for v in ph.band)} fx {P.get('fx')} clamp {f.n_clamped}")
        return self.ks

    # -------------------------------------------------------------- 卡片
    def card(self, name, t0, t1, items, fx_fn=None, seed=0, shadow="&H100804&", outline="&H201008&"):
        """items: [(text, style, fs, metric, x, y, delay, kind)]  kind: fade|wipe；band = 文字墨迹 + 5%"""
        doc = self.doc

        def sp_of(st):      # 样式里的字间距（Spacing 字段）宽度估算必须带上，否则 wipe 的 clip 会切掉两端
            """Agent Notes
            .agents/notes/implemented/bug-fix/2026-10-03-karaoke-shape-size-baseline.md
            """
            for ln in doc.styles:
                f = ln.split(",")
                if f[0] == f"Style: {st}":
                    return float(f[13])
            return 0.0
        W = {}
        xs0, ys0, xs1, ys1 = [], [], [], []
        for text, st, fs, M, x, y, dl, _ in items:
            W[text] = M.width(text, fs, sp_of(st)) * 1.06 + 12
            # band 必须包住实际渲染出来的墨迹, 不是行框, 且口径要与 validate_ass 一致:
            # 取「行框估算(带样式字间距)」与「geom.event_extent 实测」的**并集**  只按
            # 行框会漏掉描边/模糊(实测 card:title 报越界 4 条), 只按实测又会因调用方给的
            # Metric 与样式名声明的字体不同(实测某工程传 MC 文楷而样式名写 TITLE 明朝)
            # 把 band 算窄、误判原本通过的工程.
            from assfx.base.geom import event_extent
            # Agent Notes: 组合图形的尺寸口径必须按"参照边"归一化
            # 
            e = event_extent(f"{{\\an5\\pos({x},{y})\\fs{fs}\\bord7\\shad0\\blur9}}{text}", fs)
            h = M.em(fs)
            xs0.append(min(e[0], x - W[text] / 2)); ys0.append(min(e[1], y - h * 0.62))
            xs1.append(max(e[2], x + W[text] / 2)); ys1.append(max(e[3], y + h * 0.62))
        band = doc.band(name, min(xs0) - 96, min(ys0) - 54, max(xs1) + 96, max(ys1) + 54, t0, t1)
        for text, st, fs, M, x, y, dl, kind in items:
            ta = t0 + dl
            sh = f"\\fs{fs}\\bord7\\shad0\\1a&HFF&\\3c{shadow}\\3a&H60&\\blur9"
            lk = f"\\fs{fs}\\bord1.6\\shad0\\3c{outline}\\3a&H40&\\blur0.8"
            for layer, look in ((1, sh), (2, lk)):
                if kind == "wipe":
                    w = W[text] + 20
                    doc.ev(layer, ta, t1, f"{{\\an5\\pos({x},{y}){look}\\clip({x-w/2:.0f},{y-80},{x-w/2:.0f},{y+80})\\t(0,900,0.6,\\clip({x-w/2:.0f},{y-80},{x+w/2:.0f},{y+80}))"
                                          f"\\t({ms(t1-ta)-700},{ms(t1-ta)},\\alpha&HFF&\\blur8)}}{text}", st, "card:" + name)
                else:
                    doc.ev(layer, ta, t1, f"{{\\an5\\move({x},{y+14},{x},{y},0,900){look}\\alpha&HFF&\\blur6\\t(0,900,0.6,\\blur{0.8 if layer==2 else 9})"
                                          f"\\t(0,700,\\1a&H{'FF' if layer==1 else '00'}&\\3a&H{'60' if layer==1 else '40'}&)\\t({ms(t1-ta)-700},{ms(t1-ta)},\\alpha&HFF&\\blur8)}}{text}",
                           st, "card:" + name)
        f = FX(doc, name, band, seed)
        if fx_fn:
            fx_fn(f, band)
        return band
