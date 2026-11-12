# -*- coding: utf-8 -*-
"""無職転生 ED1 示例的公共场景: 字体/布局/样式/主题/取字工具, 以及 Generator 实例.
make_ass.py, fx_*.py, cards.py 都从这里 import *.
"""
import json, math, os, random, sys

HERE = os.path.dirname(os.path.abspath(__file__))
# 本 skill 的根目录: examples/<曲目>/ -> 上两级。ASSFX 可覆盖成拷到别处后的 scripts 路径。
SKILL = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.environ.get("ASSFX", os.path.join(SKILL, "scripts")))
from assfx.base.core import Doc, col, al, ms, lerp_hex, grad
from assfx.base.lyrics import load
from assfx.text.layout import Layout, Metric
from assfx.text.anim import Karaoke, life, exit_vec
from assfx.layer.fx import FX
from assfx.layer.gen import Generator
from assfx.base.seeding import _derive as derive
from assfx.draw import shapes as S

LY_SEED = 1    # 字层退场向量种子: 与特效层解耦、位置无关 (按 key 派生), 不参与全局换种子重抽


FONTS = os.environ.get("ASSFX_FONTS", os.path.join(SKILL, "fonts"))
lines = load(os.path.join(HERE, "lyrics.txt"))
timing = json.load(open(os.path.join(HERE, "timing.json")))
TM = {(m["line"], m["unit"], m["mora"]): m for m in timing}
calib = json.load(open(os.path.join(HERE, "calib.json")))

# 歌词位置预设: placement.json (缺省 = 底部居中, 日上中下, 标准行距 -> JY 915, 与旧写死值逐字节一致)
from assfx.text import placement as PLC
PLACE = PLC.compute(PLC.load(HERE), calib)
ORDER = PLACE["preset"]["order"]
JP_Y = PLACE["jy"]
L = Layout(jp_font=os.path.join(FONTS, "ShipporiMinchoB1-Bold.ttf"), cn_font=os.path.join(FONTS, "LXGWWenKai-Medium.ttf"),
           latin_font=os.path.join(FONTS, "CormorantGaramond-Italic[wght].ttf"),
           jp_fs=84, rb_fs=34, cn_fs=50, latin_fs=66, jp_y=JP_Y, calib=dict(calib, cn_offset=PLACE["cn_offset"]), jp_sp=2, rb_sp=1, cn_sp=2, gap_em=0.55,
           **({} if PLACE["align"] == "center" else dict(align=PLACE["align"], x_edge=PLACE["x_edge"])))
MJ = Metric(os.path.join(FONTS, "ShipporiMinchoB1-Bold.ttf"))
MC = Metric(os.path.join(FONTS, "LXGWWenKai-Medium.ttf"))
ML = Metric(os.path.join(FONTS, "CormorantGaramond-Italic[wght].ttf"))

doc = Doc("無職転生 ED1「オンリー」中日双语卡拉OK特效字幕", fx_font="LXGW WenKai Medium")
doc.TEXT_LIFT = 0   # 三明治层序 (plan.md 1.3): 字在 0-4, 前景粒子 5-8 压在字上, 底光 0 在字下
doc.add_style("JP", "Shippori Mincho B1", 84, bold=1)
doc.add_style("RB", "Shippori Mincho B1", 34, bold=1)
doc.add_style("CN", "LXGW WenKai Medium", 50)
doc.add_style("LAT", "Cormorant Garamond Light", 66, italic=1)
doc.add_style("TITLE", "Shippori Mincho B1", 128, bold=1)
doc.add_style("TLAT", "Cormorant Garamond Light", 58, italic=1, spacing=10)
doc.add_style("CARD", "Shippori Mincho B1", 28, bold=0, spacing=3)
doc.add_style("CARDCN", "LXGW WenKai Medium", 34, spacing=6)
doc.add_style("PRO", "Shippori Mincho B1", 54, bold=1, spacing=4)
doc.add_style("PROCN", "LXGW WenKai Medium", 40, spacing=3)

# ======================================================================== 主题
def TH(hi, glow, dark, base="#F6F1EC", cn="#F8F3EE"):
    return dict(hi=hi, glow=glow, dark=dark, base=base, cn=cn)

FIRE, WATER = "#FF8A3A", "#46C8FF"

# ======================================================================== 工具
def find(ph, s):
    return [c for c in ph.chars if c["ch"] == s]

def seq(ph, s, nth=0):
    txt = "".join(c["ch"] for c in ph.chars); out = []; start = -1
    for _ in range(nth + 1):
        start = txt.find(s, start + 1)
    if start < 0:
        return []
    # 字符索引 → 对应 chars（latin 单元是多字符）
    acc = 0; res = []
    for c in ph.chars:
        if acc >= start and acc < start + len(s):
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

JY = JP_Y
RBY = L.rb_y
CNY = L.cn_y


def CN_REL(n):
    """原写作 JY+n、落在中文行区域的特效坐标. jp_top 原样返回 JY+n (逐字节不变);
    cn_top 时中文行在上, 改按中文行基准: CNY + (n - 默认 cn_offset)."""
    if ORDER == "jp_top":
        return JY + n
    return CNY + (n - calib["cn_offset"])


# 预览台参数层 (ASSFX_OVERRIDES) 由 Generator 读取; 没有覆盖时输出与改造前逐字节相同
G = Generator(doc, L, lines, TM, ly_seed=LY_SEED)


# C 阶段 (2026-11-08): 逐字 burst (Karaoke 第 4 层, \fscx145 放大闪光) 在宽字/拉丁单元贴近 band 左右边时会飞出 band
# (validate_ass 不带 --fontsdir 时按 em 估宽: p03/p04/p13/p14 [ly] 越界). 不关 burst, 也不改库:
# 生成器侧用 validate 同一个 event_extent 量包围盒 (估宽口径, 比实字体更宽, 两种口径都过), 逐字把放大倍数夹到 band 内.
import re as _re
import assfx.layer.gen as _gen
from assfx.base.geom import event_extent as _extent

_SCL = "\\fscx145\\fscy145"


def _style_of(doc, st):
    for line in doc.styles:
        f = str(line).split(":", 1)[-1].split(",")
        if f[0].strip() == st:
            return float(f[2]), float(f[16]), float(f[11]), float(f[12]), float(f[13])
    return 40.0, 0.0, 100.0, 100.0, 0.0


class BandKaraoke(Karaoke):
    def highlight(self, c):
        ev0, band = self.doc.ev, self.ph.band

        def fits(text, st):
            fs, bord, sx, sy, sp = _style_of(self.doc, st)
            e = _extent(text, fs, bord, 5, scale_x=sx, scale_y=sy)
            return e is None or (e[0] >= band[0] + 2 and e[2] <= band[2] - 2)

        def ev(layer, t0, t1, text, st="FX", name=""):
            if layer == 4 and _SCL in text and not fits(text, st):
                for s in range(140, 99, -5):
                    t2 = text.replace(_SCL, f"\\fscx{s}\\fscy{s}")
                    if fits(t2, st) or s == 100:
                        text = t2
                        break
            return ev0(layer, t0, t1, text, st, name)
        self.doc.ev = ev
        try:
            return super().highlight(c)
        finally:
            self.doc.ev = ev0


_gen.Karaoke = BandKaraoke
