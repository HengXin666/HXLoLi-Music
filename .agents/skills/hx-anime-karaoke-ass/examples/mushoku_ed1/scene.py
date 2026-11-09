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

JP_Y = 915
L = Layout(jp_font=os.path.join(FONTS, "ShipporiMinchoB1-Bold.ttf"), cn_font=os.path.join(FONTS, "LXGWWenKai-Medium.ttf"),
           latin_font=os.path.join(FONTS, "CormorantGaramond-Italic[wght].ttf"),
           jp_fs=84, rb_fs=34, cn_fs=50, latin_fs=66, jp_y=JP_Y, calib=calib, jp_sp=2, rb_sp=1, cn_sp=2, gap_em=0.55)
MJ = Metric(os.path.join(FONTS, "ShipporiMinchoB1-Bold.ttf"))
MC = Metric(os.path.join(FONTS, "LXGWWenKai-Medium.ttf"))
ML = Metric(os.path.join(FONTS, "CormorantGaramond-Italic[wght].ttf"))

doc = Doc("無職転生 ED1「オンリー」中日双语卡拉OK特效字幕", fx_font="LXGW WenKai Medium")
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


# 预览台参数层 (ASSFX_OVERRIDES) 由 Generator 读取; 没有覆盖时输出与改造前逐字节相同
G = Generator(doc, L, lines, TM, ly_seed=LY_SEED)
