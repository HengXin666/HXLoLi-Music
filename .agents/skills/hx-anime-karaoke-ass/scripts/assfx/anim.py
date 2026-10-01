# -*- coding: utf-8 -*-
"""
歌词动画：逐字生命周期（入场 → 停留 → 退场）+ 卡拉OK 高亮。

层次约定（同一字符叠多层）：
  L0 长音光晕   L1 暗色描边阴影（保证任何画面都看得清）   L2 基础字（未唱，半透明）
  L3 高亮字（唱到时覆盖）   L4 辉光爆发（唱到瞬间一闪）   L5+ 特效
关键细节：
  * 入场淡入必须淡到“该层自己的”\\1a/\\3a，而不是 \\alpha&H00&（否则阴影层会突然变实）
  * 所有位移幅度都很小（≤80px 横 / ≤30px 纵），保证歌词自身也不越出 band
"""
import math, re
from .core import col, al, ms

ENT = {
    # kind: (起点偏移 dx, dy, 起始附加标签, 过渡到的标签)
    "slide": (-36, 0, "\\blur5\\fscx112", "\\fscx100"),
    "rise": (0, 22, "\\blur4\\fscy120", "\\fscy100"),
    "drop": (0, -24, "\\blur3\\fscy115", "\\fscy100"),
    "zoom": (0, 0, "\\blur8\\fscx150\\fscy150", "\\fscx100\\fscy100"),
    "flip": (0, 0, "\\blur3\\fry85", "\\fry0"),
    "flipx": (0, 0, "\\blur3\\frx85", "\\frx0"),
    "spin": (0, 0, "\\blur4\\frz-35\\fscx60\\fscy60", "\\frz0\\fscx100\\fscy100"),
    "fade": (0, 0, "\\blur6", ""),
    "glitch": (0, 0, "\\blur2\\fax0.6\\fscx130", "\\fax0\\fscx100"),
}


def exit_vec(kind, rng):
    if kind == "wind":
        return dict(dx=rng.uniform(25, 55), dy=-rng.uniform(8, 24), tag=f"\\frz{rng.uniform(-30,30):.0f}\\fscx70\\fscy70\\blur6")
    if kind == "rise":
        return dict(dx=rng.uniform(-8, 8), dy=-rng.uniform(18, 30), tag="\\fscy135\\fscx85\\blur7")
    if kind == "sink":
        return dict(dx=0, dy=rng.uniform(14, 24), tag="\\fscy80\\blur6")
    if kind == "scatter":
        return dict(dx=rng.uniform(-45, 45), dy=rng.uniform(6, 28), tag=f"\\frz{rng.uniform(-90,90):.0f}\\fscx60\\fscy60\\blur3")
    if kind == "zoom":
        return dict(dx=0, dy=0, tag="\\fscx140\\fscy140\\blur9")
    if kind == "flip":
        return dict(dx=0, dy=0, tag="\\fry-85\\blur3")
    if kind == "flipx":
        return dict(dx=0, dy=0, tag="\\frx-85\\blur3")
    return dict(dx=0, dy=0, tag="\\blur8")      # fade


def target_alpha(look):
    a1 = re.search(r"\\1a(&H[0-9A-Fa-f]{2}&)", look); a3 = re.search(r"\\3a(&H[0-9A-Fa-f]{2}&)", look)
    return f"\\1a{a1.group(1) if a1 else '&H00&'}\\3a{a3.group(1) if a3 else '&H00&'}"


def look_blur(look):
    m = re.findall(r"\\blur([\d.]+)", look)
    return m[-1] if m else "0"


def life(doc, name, layer, st, ch, x, y, t_in, t_hold, t_out, t_end, look, ent="slide", xv=None, hold_extra="",
         entrance=True, ent_scale=1.0):
    """单字三段式。t_in→t_hold 入场，t_hold→t_out 停留，t_out→t_end 退场"""
    xv = xv or dict(dx=0, dy=0, tag="\\blur8")
    if entrance and t_hold > t_in:
        dx, dy, a0, a1 = ENT[ent]
        d = ms(t_hold - t_in)
        doc.ev(layer, t_in, t_hold,
               f"{{\\an5\\move({x+dx*ent_scale:.1f},{y+dy*ent_scale:.1f},{x:.1f},{y:.1f},0,{d}){look}\\alpha&HFF&{a0}"
               f"\\t(0,{d},0.6,{a1}\\blur{look_blur(look)})\\t(0,{int(d*0.8)},{target_alpha(look)})}}{ch}", st, name)
        hs = t_hold
    else:
        hs = t_in
    doc.ev(layer, hs, t_out, f"{{\\an5\\pos({x:.1f},{y:.1f}){look}{hold_extra}}}{ch}", st, name)
    d = ms(t_end - t_out)
    doc.ev(layer, t_out, t_end,
           f"{{\\an5\\move({x:.1f},{y:.1f},{x+xv['dx']:.1f},{y+xv['dy']:.1f},0,{d}){look}"
           f"\\t(0,{d},1.5,{xv['tag']}\\alpha&HFF&)}}{ch}", st, name)


class Karaoke:
    """
    th: 主题配色 dict(hi, glow, dark, base, cn)；opts:
      ent/ext: 入场/退场类型；hl: 高亮类型 wipe|bloom|jump|flipx|ink
      bright: 明亮画面加重阴影；din/dout: 入退场时长；stg_in/stg_out: 逐字错落
      hl_color(ch)->(hi, glow) 可逐字改色
    """

    def __init__(self, doc, ph, band_name, th, rng, **opts):
        self.doc, self.ph, self.name, self.th, self.rng = doc, ph, "ly:" + band_name, th, rng
        o = dict(ent="slide", ext="wind", hl="wipe", bright=False, din=0.5, dout=0.6, stg_in=0.03, stg_out=0.02,
                 hl_color=None, hl_kind=None, pop=116, burst=True, halo=True, cn_ent=None, cn_delay=0.2, rb_ent=None)
        o.update(opts); self.o = o

    def looks(self):
        th, br = self.th, self.o["bright"]
        return dict(
            shadow=f"\\bord{9 if br else 7}\\shad0\\1a&HFF&\\3c{col(th['dark'])}\\3a{'&H40&' if br else '&H60&'}\\blur{10 if br else 8}",
            base=f"\\bord2\\shad0\\1c{col(th['base'])}\\1a&H50&\\3c{col(th['dark'])}\\3a{'&H18&' if br else '&H30&'}\\blur0.8",
            rshadow=f"\\bord5\\shad0\\1a&HFF&\\3c{col(th['dark'])}\\3a{'&H48&' if br else '&H68&'}\\blur5",
            rbase=f"\\bord1.2\\shad0\\1c{col(th['base'])}\\1a&H58&\\3c{col(th['dark'])}\\3a&H40&\\blur0.6",
            rhl=f"\\bord1.5\\shad0\\1c{col(th['hi'])}\\3c{col(th['glow'])}\\3a&H40&\\blur1",
            cshadow=f"\\bord6\\shad0\\1a&HFF&\\3c{col(th['dark'])}\\3a{'&H48&' if br else '&H68&'}\\blur7",
            cbase=f"\\bord1.6\\shad0\\1c{col(th['cn'])}\\1a&H08&\\3c{col(th['dark'])}\\3a&H40&\\blur0.7",
        )

    def render(self, t_in, t_out):
        o, th, doc, rng, ph = self.o, self.th, self.doc, self.rng, self.ph
        L = self.looks(); name = self.name
        self.t_in, self.t_out = t_in, t_out
        for c in ph.chars:
            c["xv"] = exit_vec(o["ext"], rng)
            c["ti"] = t_in + c["i"] * o["stg_in"]; c["to"] = t_out + c["i"] * o["stg_out"]
            c["te"] = c["to"] + o["dout"]
            st = c["style"]
            for layer, lk in ((1, L["shadow"]), (2, L["base"])):
                life(doc, name, layer, st, c["ch"], c["x"], c["y"], c["ti"], c["ti"] + o["din"], c["to"], c["te"], lk, o["ent"], c["xv"])
            self.highlight(c)
        for r in ph.rb:
            h = r["host"]
            ti = h["ti"] + 0.06
            ent = o["rb_ent"] or ("fade" if o["ent"] in ("flip", "flipx", "spin") else o["ent"])
            for layer, lk in ((1, L["rshadow"]), (2, L["rbase"])):
                life(doc, name, layer, "RB", r["ch"], r["x"], r["y"], ti, ti + o["din"], h["to"], h["te"], lk, ent, h["xv"], ent_scale=0.5)
            hi, gl = self.colors(h)
            rhl = f"\\bord1.5\\shad0\\1c{col(hi)}\\3c{col(gl)}\\3a&H40&\\blur1"
            life(doc, name, 3, "RB", r["ch"], r["x"], r["y"], r["s"], r["s"], h["to"], h["te"], rhl, xv=h["xv"], entrance=False,
                 hold_extra="\\fscx130\\fscy130\\t(0,220,0.6,\\fscx100\\fscy100)")
            doc.ev(4, r["s"], r["s"] + 0.35, f"{{\\an5\\pos({r['x']:.1f},{r['y']:.1f})\\bord0\\shad0\\1c{col(gl)}\\blur5\\alpha&H50&"
                                             f"\\t(0,350,\\fscx160\\fscy160\\alpha&HFF&)}}{r['ch']}", "RB", name)
        for j, c in enumerate(ph.cn):
            ti = t_in + o["cn_delay"] + j * 0.025; to = t_out + j * o["stg_out"]
            xv = exit_vec(o["ext"], rng)
            ent = o["cn_ent"] or ("fade" if o["ent"] in ("zoom", "glitch") else o["ent"])
            for layer, lk in ((1, L["cshadow"]), (2, L["cbase"])):
                life(doc, name, layer, "CN", c["ch"], c["x"], c["y"], ti, ti + o["din"], to, to + o["dout"], lk, ent, xv, ent_scale=0.6)

    def colors(self, c):
        if self.o["hl_color"]:
            r = self.o["hl_color"](c)
            if r:
                return r
        return self.th["hi"], self.th["glow"]

    def highlight(self, c):
        o, doc, name = self.o, self.doc, self.name
        hs, he = c["s"], c["e"]; dur = max(0.05, he - hs)
        hi, gl = self.colors(c)
        look = f"\\bord2.2\\shad0\\1c{col(hi)}\\3c{col(gl)}\\3a&H48&\\blur1.5"
        x, y, w = c["x"], c["y"], c["w"]
        pop = o["pop"]
        kind = o["hl_kind"](c) if o.get("hl_kind") else o["hl"]
        if c["kind"] == "latin":
            # 英文/非假名单元：按每个音拍的时间分段擦亮（第 i 拍结束时擦到 (i+1)/n 宽度）
            x1, x2 = x - w / 2 - 6, x + w / 2 + 6
            n = len(c["morae"]); segs = ""
            for i, m in enumerate(c["morae"]):
                a_ = ms(m["s"] - hs); b_ = ms(max(m["s"] + 0.05, min(m["e"], m["s"] + 0.5)) - hs)
                segs += f"\\t({a_},{b_},\\clip({x1:.0f},{y-60:.0f},{x1 + (x2-x1)*(i+1)/n:.0f},{y+60:.0f}))"
            anim = f"\\clip({x1:.0f},{y-60:.0f},{x1:.0f},{y+60:.0f}){segs}"
        elif kind == "wipe":
            x1, x2 = x - w / 2 - 6, x + w / 2 + 6
            wipe = max(0.1, min(dur * 0.6, 0.5)) if c["kind"] != "latin" else max(0.2, dur * 0.9)
            anim = (f"\\clip({x1:.0f},{y-60:.0f},{x1:.0f},{y+60:.0f})\\t(0,{ms(wipe)},\\clip({x1:.0f},{y-60:.0f},{x2:.0f},{y+60:.0f}))"
                    f"\\fscx{pop}\\fscy{pop}\\t(0,{ms(min(0.35, dur+0.1))},0.6,\\fscx100\\fscy100)")
        elif kind == "bloom":
            anim = f"\\blur8\\fscx{pop+10}\\fscy{pop+10}\\t(0,{ms(min(0.45, dur+0.15))},0.6,\\blur1.5\\fscx100\\fscy100)"
        elif kind == "flipx":
            anim = f"\\frx70\\t(0,{ms(min(0.35, dur+0.1))},0.6,\\frx0)"
        elif kind == "shake":
            anim = f"\\frz-9\\t(0,90,\\frz7)\\t(90,180,\\frz-4)\\t(180,270,\\frz0)\\fscx{pop}\\fscy{pop}\\t(0,300,\\fscx100\\fscy100)"
        elif kind == "ink":
            anim = f"\\blur10\\1a&H80&\\t(0,{ms(min(0.6, dur+0.2))},\\blur1.5\\1a&H00&)"
        else:
            anim = ""
        if kind == "jump" and c["kind"] != "latin":
            t2 = min(c["to"], hs + 0.24)
            doc.ev(3, hs, t2, f"{{\\an5\\move({x:.1f},{y:.1f},{x:.1f},{y-12:.1f},0,120){look}\\fscx{pop}\\fscy{pop}\\t(0,240,\\fscx100\\fscy100)}}{c['ch']}", c["style"], name)
            doc.ev(3, t2, c["to"], f"{{\\an5\\move({x:.1f},{y-12:.1f},{x:.1f},{y:.1f},0,140){look}}}{c['ch']}", c["style"], name)
            doc.ev(3, c["to"], c["te"], f"{{\\an5\\move({x:.1f},{y:.1f},{x+c['xv']['dx']:.1f},{y+c['xv']['dy']:.1f},0,{ms(c['te']-c['to'])}){look}"
                                         f"\\t(0,{ms(c['te']-c['to'])},1.5,{c['xv']['tag']}\\alpha&HFF&)}}{c['ch']}", c["style"], name)
        else:
            life(doc, name, 3, c["style"], c["ch"], x, y, hs, hs, c["to"], c["te"], look, xv=c["xv"], entrance=False, hold_extra=anim)
        if o["burst"]:
            doc.ev(4, hs, hs + 0.45, f"{{\\an5\\pos({x:.1f},{y:.1f})\\bord0\\shad0\\1c{col(gl)}\\blur9\\alpha&H40&"
                                     f"\\t(0,450,0.7,\\fscx145\\fscy145\\alpha&HFF&)}}{c['ch']}", c["style"], name)
        if o["halo"] and dur > 0.8:
            doc.ev(0, hs, min(c["to"], he + 0.4),
                   f"{{\\an5\\pos({x:.1f},{y:.1f})\\bord8\\shad0\\1a&HFF&\\3c{col(gl)}\\blur14\\alpha&HFF&"
                   f"\\t(0,{ms(dur)},\\3a&H60&)\\t({ms(dur)},{ms(dur+0.4)},\\3a&HFF&)}}{c['ch']}", c["style"], name)
