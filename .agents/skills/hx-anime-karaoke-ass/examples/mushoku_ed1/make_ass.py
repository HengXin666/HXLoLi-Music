# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "numpy",
#   "fonttools",
# ]
# ///
"""
無職転生 ED1「オンリー」（大原ゆい子） 中日双语 + 振假名 卡拉OK 特效字幕

设计总纲
  * 歌曲：以第一人称向“唯一的你”告白愛/守りたい/壊したい 的矛盾与决意；MV 以回忆蒙太奇串起
    出生、旅途、战斗、魔法课、家族、离别。特效跟随每一句对应的画面（见 PHRASES 注释的时间点）。
  * 硬约束：所有特效（含歌词自身的出入场）只在“歌词块墨迹包围盒 + 5% 画面”(band) 内；
    FX 发射器生成期夹取，validate_ass.py 复核。
  * 注音：calibrate_ruby.py 实测墨迹，注音底与汉字顶间距 5px。
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
from assfx.draw import shapes as S

# Agent Notes: 卡拉OK 制作工作区统一为 dev/<番名>/<歌曲名>/，整棵屏蔽 git; skill 只保留一份可复现示例，模板只留一个
# 
# 
# Agent Notes: 卡拉OK 制作工作区统一为 dev/<番名>/<歌曲名>/，整棵屏蔽 git; skill 只保留一份可复现示例，模板只留一个
# .agents/notes/implemented/process/2026-10-02-karaoke-dev-workspace.md
# .agents/notes/implemented/process/2026-10-02-karaoke-layout-consolidation.md
FONTS = os.environ.get("ASSFX_FONTS", os.path.join(SKILL, "fonts"))
# Agent Notes: 卡拉OK skill 按步骤重构成 steps/NN-<key>/ 的契约 + impl 结构
# 
# Agent Notes: 卡拉OK skill 按步骤重构成 steps/NN-<key>/ 的契约 + impl 结构
# .agents/notes/implemented/process/2026-10-02-karaoke-steps-restructure.md
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

# 每个显示句：lines / 主题 / 动画选项 / 特效函数名（场景见注释，时间为 base 视频时间轴）
PHRASES = [
    # 19.5-28.5 婴儿的小脚、小手握住手指（诞生）
    dict(lines=[0], th=TH("#FFF3E6", "#FFA07A", "#3A1A12"), o=dict(ent="rise", ext="rise", hl="bloom", bright=True), fx="birth"),
    # 30 夕阳下交握的手
    dict(lines=[1], th=TH("#FFF0D6", "#FF9A3C", "#2E1606"), o=dict(ent="rise", ext="sink", hl="jump"), fx="grasp"),
    # 31.5 篝火 / 33 骑蜥蜴 / 36 雾
    dict(lines=[2], th=TH("#FFE6C2", "#FF6A1F", "#260C04"), o=dict(ent="slide", ext="rise", hl="wipe"), fx="campfire"),
    # 37.5 瑞杰路德·红叶悬崖 / 40.5 红树 / 42 艾莉丝
    dict(lines=[3], th=TH("#FFEDE6", "#E8402E", "#2A0806"), o=dict(ent="slide", ext="wind", hl="wipe"), fx="autumn"),
    # 45 拉钩约定 / 46.5 伙伴 / 48 与希露菲躺在草地
    dict(lines=[4], th=TH("#FFF6EE", "#FF5A6A", "#1E1410", base="#F4F6EE"), o=dict(ent="slide", ext="wind", hl="wipe", bright=True), fx="promise"),
    # 51 鲁迪笑 / 54 魔兽 / 55.5 艾莉丝战斗
    dict(lines=[5], th=TH("#FFFFFF", "#FF2E4A", "#1E0004"), o=dict(ent="zoom", ext="scatter", hl="shake"), fx="break_red"),
    # 58.5 岩石魔像 / 60 战斗 / 61.5 魔杖
    dict(lines=[6], th=TH("#FFFFFF", "#B24CFF", "#12081E"), o=dict(ent="glitch", ext="scatter", hl="wipe"), fx="glitch_violet"),
    # 64.5 蓝色魔力球 / 67.5 黑影
    dict(lines=[7], th=TH("#EAF6FF", "#3FA0FF", "#04122A"), o=dict(ent="rise", ext="rise", hl="bloom"), fx="magic_guard"),
    # 69 火球水球 / 70.5-72 天空魔法弧光
    dict(lines=[8], th=TH("#FFFFFF", "#FF8A3A", "#101020"), o=dict(ent="zoom", ext="rise", hl="bloom"), fx="fire_water"),
    # 75 希露菲在大树下 / 76.5 夕阳
    dict(lines=[9], th=TH("#FFF4E4", "#FF9E5E", "#2A1208"), o=dict(ent="fade", ext="rise", hl="bloom", din=0.8, dout=1.0), fx="sylphie_tree"),
    # 90 保罗持剑 / 91.5 塞妮丝治愈魔法
    dict(lines=[10], th=TH("#F2F6FF", "#8FB8FF", "#0A1020"), o=dict(ent="slide", ext="wind", hl="wipe"), fx="sword_heal"),
    # 93 婴儿 / 94.5 天空与飞鸟
    dict(lines=[11], th=TH("#FFFFFF", "#6EC6FF", "#0C2238"), o=dict(ent="rise", ext="wind", hl="wipe", bright=True), fx="birds"),
    # 94.5-97.5 天空飞鸟 → 99 家与全家
    dict(lines=[12], th=TH("#F4F8FF", "#7DB2FF", "#101A2C"), o=dict(ent="fade", ext="sink", hl="wipe", bright=True), fx="tears_theory"),
    # 103.5 塞妮丝 / 105 烛光下读书 / 106.5 剑术训练
    dict(lines=[13], th=TH("#FFF1D8", "#FFB04A", "#1E1206"), o=dict(ent="slide", ext="wind", hl="ink"), fx="candle_book"),
    # 109.5-112.5 洛琪希 / 114 希露菲·林间光
    dict(lines=[14], th=TH("#EEF4FF", "#4A7BFF", "#0A1230"), o=dict(ent="drop", ext="rise", hl="wipe"), fx="roxy_forest"),
    # 117 麦田夕阳 / 120 艾莉丝与鲁迪
    dict(lines=[15], th=TH("#FFFBEA", "#FFB42E", "#241404"), o=dict(ent="zoom", ext="scatter", hl="shake", bright=True), fx="break_wheat"),
    # 121.5 手 / 124.5 瑞杰路德 / 126 鲁迪
    dict(lines=[16], th=TH("#FFFFFF", "#1FD2C0", "#04161A"), o=dict(ent="glitch", ext="scatter", hl="wipe"), fx="glitch_teal"),
    # 127.5 红色眼环 / 129 蓝色地图 / 133.5 电光
    dict(lines=[17], th=TH("#E6EEFF", "#5A6CFF", "#060A1E"), o=dict(ent="fade", ext="sink", hl="ink"), fx="hide_map"),
    # 134 电光 / 135 夜城 / 136.5 魔法环 / 138 爆炎 / 139.5 青光（硬字幕已 delogo）
    dict(lines=[18, 19], th=TH("#E8FCFF", "#34D8FF", "#031018"), o=dict(ent="slide", ext="sink", hl="wipe"), fx="bolt_tears"),
    # 141 艾莉丝 / 142.5 雪中的鲁迪 / 145.5 日出草原
    dict(lines=[20], th=TH("#FFFFFF", "#9ED8FF", "#0E1C2E"), o=dict(ent="rise", ext="rise", hl="jump", bright=True), fx="snow_rise"),
    # 147 蓝光 / 148.5 花田 / 151.5 夹着花瓣的书
    dict(lines=[21, 22], th=TH("#FFF4FA", "#FF5AAE", "#2A0A1C"), o=dict(ent="rise", ext="wind", hl="bloom", bright=True), fx="flowers"),
    # 153-162 一家人的晚餐
    dict(lines=[23], th=TH("#FFF2E0", "#FF9B4A", "#241006"), o=dict(ent="flipx", ext="flipx", hl="wipe"), fx="dinner_flip"),
    # 163.5 洛琪希水魔法 / 168 洛琪希与鲁迪
    dict(lines=[24, 25], th=TH("#F0FCFF", "#2EB8FF", "#021426"), o=dict(ent="zoom", ext="scatter", hl="shake"), fx="break_water"),
    # 168-175 摸头
    dict(lines=[26], th=TH("#FFF2F4", "#FF7A9A", "#2A0A12"), o=dict(ent="fade", ext="rise", hl="bloom"), fx="embrace"),
    # 177 上课 / 178.5 鲁迪 / 180 起遮幅
    dict(lines=[27], th=TH("#F4FFF6", "#9EE6B8", "#0A1A12"), o=dict(ent="slide", ext="wind", hl="wipe"), fx="eraser"),
    # 180-189 遮幅：夕阳下的手 / 保罗与塞妮丝 / 篝火
    dict(lines=[28], th=TH("#FFF6E0", "#FFB43C", "#241404"), o=dict(ent="fade", ext="sink", hl="bloom"), fx="overflow"),
    # 189-195 雾 / 瑞杰路德 / 艾莉丝 / 拉钩 / 暗林 / 骑士
    dict(lines=[29], th=TH("#EEF0F6", "#9A8CFF", "#0C0A18"), o=dict(ent="slide", ext="scatter", hl="shake"), fx="chains"),
    # 195-201 暗青色森林 / 骑士
    dict(lines=[30], th=TH("#FFFFFF", "#2EF2E0", "#03141A"), o=dict(ent="glitch", ext="scatter", hl="wipe"), fx="glitch_cyan"),
    # 201 洛琪希持杖 / 204 火球 / 205.5 天空弧光 / 208.5 塞妮丝拥抱鲁迪
    dict(lines=[31], th=TH("#EEF6FF", "#4AA0FF", "#050E22"), o=dict(ent="rise", ext="rise", hl="bloom", stg_out=0.02), fx="finale"),
    # 210-213 洛琪希微笑 / 216 鲁迪在石墙后
    dict(lines=[32], th=TH("#FFF8E8", "#6F9CFF", "#0A1024"), o=dict(ent="fade", ext="rise", hl="bloom", din=0.8, dout=1.2), fx="only_you"),
]

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


# ======================================================================== 各句特效
def fx_birth(f, ph, k):
    a, b = span(ph.chars); cx = (a + b) / 2
    f.glow(0, k.t_in, k.t_end, cx, JY + 10, (b - a) / 2 + 30, 58, "#FFC9A0", a_peak=205, blur=26, fade_in=0.8, fade_out=0.8)
    ai = find(ph, "愛")[0]
    for dly, a0 in ((0, 70), (0.28, 110)):
        f.pulse(0, ai["s"] + dly, ai["x"], JY, S.heart(62), "#FF8CA0", dur=1.1, s0=40, s1=135, a0=a0, blur=5)
    f.shape(0, ai["s"], k.t_out, ai["x"], JY - 4, draw=S.heart(40), c1="#FF9CB0", a_peak=170, blur=8, fade_in=0.4, fade_out=0.5,
            extra=sway(8, 900, 5) + "\\fscx90\\fscy90")
    for c in ph.chars:
        f.burst(c["s"], c["x"], JY - 26, 2, ["#FFB6C4", "#FFD6C0", "#FFFFFF"], draw_fn=lambda r: S.heart(r * 1.9),
                speed=(25, 55), up=0.9, size=(3, 5), life=(0.8, 1.3))
    for c in seq(ph, "イロハ"):   # 爱的 ABC：小小的 い・ろ・は 从字上飘起
        g = {"イ": "い", "ロ": "ろ", "ハ": "は"}[c["ch"]]
        f.text(6, c["s"], c["s"] + 1.2, c["x"] + 18, RBY - 6, g, "RB", 34,
               f"\\bord0\\shad0\\1c{col('#FFB0A0')}\\blur1\\alpha&HFF&\\t(0,200,\\alpha&H40&)\\t(600,1200,\\alpha&HFF&)\\fscx70\\fscy70",
               x1=c["x"] + 40, y1=RBY - 30)
    f.drift(k.t_in, k.t_end, 18, ["#FFE3C8", "#FFD2B0", "#FFFFFF"], S.circle, vx=(-8, 8), vy=(-22, -8), size=(2, 4),
            a=(60, 150), spin=False, blur=(1, 2.5))


def fx_grasp(f, ph, k):
    te = find(ph, "手")[0]; nai = seq(ph, "ない")
    t_break = nai[0]["s"] if nai else ph.e - 0.5
    R = f.rng
    for i in range(10):     # 夕光汇聚到“手”
        x0 = R.uniform(f.b[0] + 30, f.b[2] - 30); y0 = R.choice([f.b[1] + 20, f.b[3] - 20])
        t0 = te["s"] - 0.25 + i * 0.03
        f.shape(7, t0, te["s"] + 0.45, x0, y0, te["x"], JY - 6, S.circle(R.uniform(2.5, 4.5)), "#FFD27A", a_peak=40,
                fade_in=0.15, fade_out=0.15, blur=1.5, c3=FIRE, bord=2, accel=0.6)
    f.shape(0, te["s"] + 0.3, t_break + 0.1, te["x"], JY - 4, draw=S.circle(22), c1="#FFC060", a_peak=90, blur=12,
            fade_in=0.3, fade_out=0.1, extra=flicker(6, 500, 150, 90))
    f.shape(6, te["s"] + 0.3, t_break + 0.1, te["x"], JY - 4, draw=S.sparkle(16), c1="#FFF6D8", a_peak=30, blur=0.8,
            fade_in=0.3, fade_out=0.1, extra="\\t(\\frz180)")
    # “得不到”：光球从指间滑落碎开
    cx = te["x"]
    f.shape(6, t_break, t_break + 0.9, cx, JY - 4, cx + 30, f.b[3] - 30, S.circle(9), "#FFC060", a_peak=40, blur=4, fade_in=0.05, fade_out=0.6, accel=1.8)
    f.burst(t_break + 0.35, cx + 25, f.b[3] - 40, 12, ["#FFD27A", "#FFB04A", "#FFF0C0"], speed=(40, 110), up=0.3, life=(0.5, 1.0))
    for c in seq(ph, "いれいれ"):
        f.pulse(5, c["s"], c["x"], JY, S.ring(34, 2.5), "#FFD090", dur=0.5, s0=60, s1=120, a0=90, blur=1)


def fx_campfire(f, ph, k):
    R = f.rng
    ki = seq(ph, "貴方")[0]["s"]
    x0, x1 = f.b[0] + 20, f.b[2] - 20
    for _ in range(46):     # 篝火余烬
        t = R.uniform(k.t_in, ki); L = R.uniform(1.0, 2.0); x = R.uniform(x0, x1)
        f.shape(0 if R.random() < 0.5 else 7, t, t + L, x, f.b[3] - 15, x + R.uniform(-30, 30), f.b[1] + 20, S.circle(R.uniform(1.8, 3.5)),
                R.choice(["#FFB347", "#FF7A2A", "#FFD27A"]), a_peak=R.randint(0, 60), fade_in=0.2, fade_out=0.6, blur=1.2,
                c3="#FF5A10", bord=1.5, extra=flicker(int(L / 0.2), 200, 120, 20))
    for c in seq(ph, "戦い"):
        for j in range(3):
            fx_ = c["x"] + (j - 1) * 20
            f.shape(0, c["s"] + j * 0.05, c["s"] + 1.3, fx_, JY + 30, fx_, JY - 8, S.flame(R.uniform(24, 34), R.uniform(-0.2, 0.2)),
                    R.choice([FIRE, "#FFB347"]), a_peak=90, blur=3, fade_in=0.15, fade_out=0.8, extra="\\fscy70\\t(0,600,\\fscy115)" + sway(3, 400, 6))
    for c in seq(ph, "疲れ果てた"):    # 疲惫：字下沉般的暗影
        f.shape(0, c["s"], c["s"] + 0.8, c["x"], JY + 6, c["x"], JY + 22, S.ellipse(30, 10), "#000000", a_peak=140, blur=8, fade_in=0.1, fade_out=0.6)
    for j in range(4):      # 36s 雾：“想要你”在雾中
        y = R.uniform(JY - 20, JY + 60); w = R.uniform(260, 420)
        f.shape(0, ki - 0.4 + j * 0.25, k.t_end, f.b[0] + w / 2, y, f.b[2] - w / 2, y + R.uniform(-10, 10), S.veil(w, 40, 3, 5),
                "#D8DCE8", a_peak=195, blur=14, fade_in=0.8, fade_out=0.7)
    for c in seq(ph, "欲しい"):
        f.pulse(5, c["s"], c["x"], JY, S.ring(40, 2), "#FFE0C0", dur=0.8, s0=50, s1=140, a0=110, blur=1.5)


def fx_autumn(f, ph, k):
    f.drift(k.t_in, k.t_end, 26, ["#E8402E", "#FF7A3A", "#C8201E", "#FFA040"], S.maple, vx=(25, 70), vy=(-5, 20),
            size=(8, 14), a=(20, 90), blur=(0.6, 1.4))
    lat = ph.chars[0]
    f.shape(6, lat["s"], lat["s"] + 1.4, lat["x"] + lat["w"] / 2 - 10, JY - 30, draw=S.sparkle(22), c1="#FFF0E0", a_peak=20, blur=0.8,
            fade_in=0.1, fade_out=0.9, extra="\\fscx30\\fscy30\\t(0,300,\\fscx110\\fscy110)\\t(\\frz90)")
    kw = seq(ph, "怖くない")
    if kw:
        cx = mid(kw)
        f.shape(0, kw[0]["s"], k.t_out + 0.3, cx, JY, draw=S.shield(58), c1="#8C1A10", a_peak=150, blur=4, fade_in=0.3, fade_out=0.5,
                extra="\\fscx60\\fscy60\\t(0,400,0.6,\\fscx100\\fscy100)")
        f.shape(0, kw[0]["s"], k.t_out + 0.3, cx, JY, draw=S.shield(58), c1="#FF6A4A", a_peak=255, a3=90, c3="#FF6A4A", bord=2.5, blur=2,
                fade_in=0.3, fade_out=0.5, extra="\\1a&HFF&\\fscx60\\fscy60\\t(0,400,0.6,\\fscx100\\fscy100)")
        f.pulse(5, kw[2]["s"], cx, JY, S.shield(58), "#FFB090", dur=0.7, s0=100, s1=150, a0=120, blur=3)


def fx_promise(f, ph, k):
    """Agent Notes
    .agents/notes/implemented/process/2026-10-04-karaoke-skill-genericize.md
    """
    R = f.rng
    lat = ph.chars[0]; se = seq(ph, "背中"); ma = seq(ph, "任せて")
    xa = lat["x"] + lat["w"] / 2 - 20; xb = ma[-1]["x"]
    y = JY + 40
    # Agent Notes: 卡拉OK skill 通用化  去掉单次制作的事实与清单式铺陈
    # 
    th = S.thread((0, 0), (xb - xa, 0), 16, 3)
    t0 = lat["s"]; t1 = ma[-1]["s"] + 0.2
    f.shape(5, t0, k.t_out + 0.3, (xa + xb) / 2, y, draw=th, c1="#FF3B4A", a_peak=30, blur=1.2, c3="#FF7080", bord=1.2, a3=120,
            fade_in=0.05, fade_out=0.5, extra=f"\\clip({xa-4:.0f},{y-40:.0f},{xa-4:.0f},{y+40:.0f})\\t(0,{ms(t1-t0)},\\clip({xa-4:.0f},{y-40:.0f},{xb+8:.0f},{y+40:.0f}))")
    f.pulse(6, ma[-1]["s"] + 0.15, xb, y + 4, S.heart(16), "#FF4A5A", dur=0.8, s0=80, s1=160, a0=20, blur=1)
    f.shape(6, ma[-1]["s"] + 0.15, k.t_out + 0.3, xb, y + 4, draw=S.heart(12), c1="#FF4A5A", a_peak=20, blur=0.8, fade_in=0.1, fade_out=0.4)
    if se:
        cx = mid(se)
        for sgn in (-1, 1):
            f.shape(0, se[0]["s"], k.t_out + 0.2, cx, JY, draw=S.sword(118), c1="#E8EEF6", a_peak=150, blur=1.2, c3="#FFFFFF", bord=0,
                    fade_in=0.25, fade_out=0.4, extra=f"\\frz{sgn*70}\\t(0,350,0.5,\\frz{sgn*38})")
        f.pulse(5, se[0]["s"] + 0.32, cx, JY - 30, S.sparkle(26), "#FFFFFF", dur=0.6, s0=40, s1=110, a0=10, blur=0.8)
    f.drift(k.t_in, k.t_end, 14, ["#B8E08A", "#8CCB6A", "#E6F5C0"], S.leaf, vx=(15, 45), vy=(-15, 10), size=(5, 8), a=(30, 110))


def fx_break(f, ph, k, pal, shard_cols, slash_col):
    R = f.rng
    for c in find(ph, "壊"):
        f.shape(6, c["s"], c["s"] + 0.9, c["x"], JY, draw=S.crack(R, 130, 4.5, 3), c1="#FFFFFF", a_peak=0, blur=0.6, c3=pal, bord=1.5,
                fade_in=0.02, fade_out=0.5, extra=f"\\frz{R.uniform(-25,25):.0f}\\clip({c['x']-70:.0f},{JY-70},{c['x']-70:.0f},{JY+70})\\t(0,120,\\clip({c['x']-70:.0f},{JY-70},{c['x']+70:.0f},{JY+70}))")
        f.burst(c["s"] + 0.05, c["x"], JY, 10, shard_cols, draw_fn=lambda r: S.shard(R, r * 2.6), speed=(50, 120), up=-0.5,
                size=(3, 6), life=(0.6, 1.1), spin=True, blur=(0.4, 1.0), a=(0, 40))
        f.pulse(5, c["s"], c["x"], JY, S.ring(44, 3), pal, dur=0.45, s0=50, s1=150, a0=40, blur=1.5)
    kk = seq(ph, "貴方のためなら")
    if kk:
        a, b = span(kk)
        t = kk[0]["s"]
        f.shape(7, t, t + 0.45, a, JY - 10, b, JY - 4, S.slash(b - a, 22), slash_col, a_peak=0, blur=1.5, fade_in=0.05, fade_out=0.3,
                extra="\\frz-6\\fscx40\\t(0,220,\\fscx100)", accel=0.5)
        f.burst(t + 0.25, b - 10, JY - 6, 10, ["#FFFFFF", slash_col, "#FFE0A0"], speed=(40, 100), life=(0.3, 0.7), size=(1.5, 3))


def fx_break_red(f, ph, k):
    fx_break(f, ph, k, "#FF2E4A", ["#FFFFFF", "#FFD0D6", "#FF4A5A"], "#FFE8E8")


def fx_glitch(f, ph, k, c_a, c_b, extra_cols):
    R = f.rng
    for c in ph.chars:
        if c["kind"] == "punct":
            continue
        for dx, cc in ((-7, c_a), (7, c_b)):
            f.text(5, c["s"], c["s"] + 0.16, c["x"] + dx, JY, c["ch"], c["style"], 84 if c["style"] == "JP" else 66,
                   f"\\bord0\\shad0\\blur0.6\\1c{col(cc)}\\alpha&H50&\\t(60,160,\\alpha&HFF&)")
    for _ in range(int((ph.e - ph.s) * 5)):
        t = R.uniform(k.t_in + 0.3, ph.e); w = R.uniform(60, 320); h = R.uniform(2, 5)
        f.shape(7, t, t + R.uniform(0.06, 0.16), R.uniform(f.b[0] + w / 2, f.b[2] - w / 2), R.uniform(f.b[1] + 10, f.b[3] - 10),
                draw=S.rect(w, h), c1=R.choice([c_a, c_b, "#FFFFFF"]), a_peak=R.randint(60, 140), blur=0.5, fade_in=0.01, fade_out=0.02)
    ms_ = seq(ph, "見境")
    if ms_:
        t = ms_[0]["s"]; cx = mid(ms_)
        f.burst(t, cx, JY + 10, 14, extra_cols, draw_fn=lambda r: S.shard(R, r * 2.2), speed=(40, 110), up=-0.3,
                size=(3, 6), life=(0.6, 1.2), spin=True, blur=(0.5, 1.2), a=(0, 50))
        f.pulse(5, t, cx, JY, S.ellipse_ring(90, 40, 3), c_b, dur=0.6, s0=40, s1=130, a0=60, blur=1)


def fx_glitch_violet(f, ph, k):
    fx_glitch(f, ph, k, "#FF2A6A", "#2AE8FF", ["#9A8C80", "#6E6258", "#C0B4A8"])   # 岩石魔像的碎石


def fx_magic_guard(f, ph, k, big=False):
    R = f.rng
    a, b = span(ph.chars); cx = (a + b) / 2
    r = min((b - a) / 2 + 70, 520) if big else min((b - a) / 2 + 40, 420)
    ma = find(ph, "守")
    t0 = ma[0]["s"] - 0.1
    yy = JY + 38
    dur_ms = ms(k.t_end - t0)
    mc = S.magic_circle(r)
    f.floor_spin(0, t0, k.t_end, cx, yy, mc, "#7CC8FF", deg_per_s=-22 if big else -16, a_peak=110, blur=1.0, fade_in=0.5, fade_out=0.6)
    f.shape(0, t0, k.t_end, cx, yy, draw=S.flat(S.circle(r * 0.9)), c1="#2A7CFF", a_peak=200, blur=24, fade_in=0.6, fade_out=0.6)
    f.floor_spin(0, t0 + 0.3, k.t_end, cx, yy, S.rune_ring(r * 0.62, rng=R), "#BDE6FF", deg_per_s=26, a_peak=120, blur=0.8,
                 fade_in=0.5, fade_out=0.6, grow=0)
    for c in ma:
        f.pulse(5, c["s"], cx, yy, S.flat(S.ring(r, r * 0.03)), "#9ED8FF", dur=0.8, s0=60, s1=110, a0=60, blur=1.5)
        f.burst(c["s"], c["x"], JY + 20, 6, ["#BDE6FF", "#7CC8FF", "#FFFFFF"], speed=(20, 60), up=1.2, size=(2, 3.5))
    sb = seq(ph, "全て")
    if sb:
        t = sb[0]["s"]; x = mid(sb)
        f.shape(6, t, k.t_out + 0.3, x, JY + 20, x, JY - 22, S.circle(12), "#9ED8FF", a_peak=30, blur=6, fade_in=0.3, fade_out=0.4,
                c3="#3FA0FF", bord=6, a3=120, t_move=(0, 900))
        f.shape(7, t, k.t_out + 0.3, x, JY + 20, x, JY - 22, S.sparkle(14), "#FFFFFF", a_peak=0, blur=0.6, fade_in=0.3, fade_out=0.4,
                t_move=(0, 900), extra="\\t(\\frz270)")


def fx_fire_water(f, ph, k):
    R = f.rng
    a, b = span(ph.chars); cx = (a + b) / 2
    rx = (b - a) / 2 + 50; ry = 42
    t0, t1 = k.t_in + 0.2, k.t_out + 0.3
    n = int((t1 - t0) / 0.1)
    for which, ph0, cc, glow in ((0, 0.0, "#FFB060", FIRE), (1, math.pi, "#A8E8FF", WATER)):
        for i in range(n):
            ta = t0 + i * 0.1; a0 = ph0 + i * 0.22; a1 = a0 + 0.22
            p0 = (cx + rx * math.cos(a0), JY + 4 + ry * math.sin(a0)); p1 = (cx + rx * math.cos(a1), JY + 4 + ry * math.sin(a1))
            front = math.sin(a0) > 0
            f.shape(7 if front else 0, ta, ta + 0.1, p0[0], p0[1], p1[0], p1[1], S.circle(9), cc, a_peak=0, blur=2, fade_in=0.0,
                    fade_out=0.0, c3=glow, bord=6, a3=100, alpha_t="")
            if i % 2 == 0:
                f.shape(0, ta, ta + 0.7, p0[0], p0[1], p0[0] + R.uniform(-8, 8), p0[1] + R.uniform(-12, 4), S.circle(R.uniform(2, 4)), glow,
                        a_peak=60, blur=1.5, fade_in=0.02, fade_out=0.6)
    # 70.5-72 天空弧光
    for i in range(5):
        t = 70.5 + i * 0.3
        f.shape(6, t, t + 0.9, cx + R.uniform(-150, 150), JY - 30, draw=S.arc(160, 200, 340, 4), c1=R.choice(["#FFD090", "#A8E8FF", "#FFFFFF"]),
                a_peak=40, blur=1.2, fade_in=0.1, fade_out=0.6, extra=f"\\fscy35\\clip({a-60:.0f},{JY-120},{a-60:.0f},{JY+60})\\t(0,500,\\clip({a-60:.0f},{JY-120},{b+60:.0f},{JY+60}))")


def fx_sylphie_tree(f, ph, k):
    a, b = span(ph.chars); cx = (a + b) / 2
    f.glow(0, k.t_in, k.t_end, cx, JY + 6, (b - a) / 2 + 40, 55, "#FFAA66", a_peak=200, blur=28, fade_in=1.0, fade_out=1.0)
    f.drift(k.t_in, k.t_end, 16, ["#9ED870", "#C8EE90", "#7CC060"], S.leaf, vx=(10, 30), vy=(8, 22), size=(6, 9), a=(30, 110),
            extra_fn=lambda R: sway(4, 700, 30))
    ke = find(ph, "け")[0]
    x, y = ke["x"] + 48, JY - 40
    f.shape(7, ke["s"], k.t_out + 0.8, x, y, draw=S.sparkle(30), c1="#FFFFFF", a_peak=0, blur=0.8, c3="#FFD090", bord=1.5, a3=60,
            fade_in=0.15, fade_out=0.8, extra="\\fscx10\\fscy10\\t(0,300,0.5,\\fscx120\\fscy120)\\t(300,600,\\fscx90\\fscy90)" +
            "".join(f"\\t({600+i*700},{950+i*700},\\fscx115\\fscy115)\\t({950+i*700},{1300+i*700},\\fscx90\\fscy90)" for i in range(4)))
    f.glow(6, ke["s"], k.t_out + 0.8, x, y, 26, 26, "#FFD090", a_peak=120, blur=10, fade_in=0.2, fade_out=0.8)
    for c in ph.chars:
        f.burst(c["s"], c["x"], JY - 20, 3, ["#FFE0B0", "#FFFFFF", "#C8EE90"], speed=(20, 50), up=0.9, size=(2, 3.5))


def fx_sword_heal(f, ph, k):
    R = f.rng
    for c in find(ph, "目"):
        f.shape(7, c["s"], c["s"] + 0.4, c["x"] - 40, JY - 30, c["x"] + 40, JY + 20, S.slash(150, 16), "#FFFFFF", a_peak=0, blur=1,
                c3="#9EC4FF", bord=1.5, fade_in=0.03, fade_out=0.3, extra="\\frz-35\\fscx40\\t(0,150,\\fscx100)", accel=0.5)
        f.burst(c["s"] + 0.1, c["x"], JY, 6, ["#FFFFFF", "#FFE8A0"], speed=(40, 90), life=(0.3, 0.6), size=(1.5, 3))
    for c in find(ph, "歯"):
        f.burst(c["s"], c["x"], JY, 12, ["#FFE8A0", "#FFFFFF", "#FFC040"], draw_fn=lambda r: S.sparkle(r * 2.5), speed=(40, 100),
                life=(0.4, 0.8), size=(2, 4), spin=True)
    to = seq(ph, "尖")
    if to:
        c = to[0]
        for j in range(5):
            f.shape(6, c["s"] + j * 0.04, c["s"] + 0.6, c["x"] + (j - 2) * 16, JY + 30, c["x"] + (j - 2) * 22, JY - 30,
                    S.poly([(0, -30), (6, 10), (-6, 10)]), "#DDE6FF", a_peak=40, blur=0.8, fade_in=0.05, fade_out=0.4)
    t0 = 91.5   # 塞妮丝的治愈魔法
    for _ in range(16):
        t = R.uniform(t0, k.t_out); x = R.uniform(f.b[0] + 30, f.b[2] - 30)
        f.shape(0 if R.random() < 0.5 else 6, t, t + 1.4, x, f.b[3] - 20, x + R.uniform(-10, 10), f.b[1] + 30, S.healing_cross(R.uniform(5, 9)),
                R.choice(["#9CFFB0", "#C8FFD0", "#6EE890"]), a_peak=R.randint(40, 110), blur=1.4, fade_in=0.3, fade_out=0.7,
                c3="#40D070", bord=2, a3=160)
    f.glow(0, t0, k.t_end, mid(ph.chars), JY + 10, (f.b[2] - f.b[0]) / 2 - 100, 50, "#60D080", a_peak=215, blur=24, fade_in=0.6)


def fx_birds(f, ph, k):
    R = f.rng
    for i in range(5):
        t = 94.3 + i * 0.22; L = R.uniform(1.6, 2.2)
        y0 = R.uniform(f.b[1] + 20, JY - 30); s = R.uniform(9, 15)
        f.shape(7 if i % 2 else 0, t, t + L, f.b[0] + 20, y0, f.b[2] - 20, y0 - R.uniform(0, 25), S.bird(s, 0.3), "#FFFFFF", a_peak=R.randint(20, 70),
                blur=0.8, fade_in=0.3, fade_out=0.4, c3="#2A4A70", bord=1, a3=150, extra=sway(int(L / 0.28), 280, 45, tag="fscy"))
    nai = seq(ph, "ない")
    if nai:
        x = nai[-1]["x"] + 50
        for j in range(3):    # 说不出口的“……”
            f.shape(6, nai[-1]["s"] + 0.2 + j * 0.15, ph.e + 0.4, x + j * 16, JY + 14, draw=S.circle(4), c1="#FFFFFF", a_peak=60, blur=0.8,
                    fade_in=0.1, fade_out=0.3, extra=flicker(4, 400, 200, 60))
    for c in ph.chars:
        f.burst(c["s"], c["x"], JY - 16, 2, ["#E0F4FF", "#FFFFFF"], speed=(20, 50), up=0.8, size=(2, 3.5))


def fx_tears_theory(f, ph, k):
    R = f.rng
    for c in find(ph, "悲"):
        for j in range(3):
            x = c["x"] + R.uniform(-18, 18)
            f.shape(6, c["s"] + j * 0.25, c["s"] + j * 0.25 + 1.0, x, JY + 20, x, f.b[3] - 22, S.teardrop(8), "#BFE4FF", a_peak=40, blur=0.8,
                    c3="#5AA0E8", bord=1, a3=120, fade_in=0.15, fade_out=0.3, accel=1.8)
    th_ = seq(ph, "セオリー")
    if th_:
        a, b = span(th_); t = th_[0]["s"]; y = JY + 36
        f.shape(5, t, k.t_out + 0.3, (a + b) / 2, y, draw=S.stroke([(0, 0), ((b - a) * 0.5, -3), (b - a, 0)], 3, taper=True), c1="#FFFFFF",
                a_peak=60, blur=0.6, fade_in=0.05, fade_out=0.4,
                extra=f"\\clip({a:.0f},{y-20:.0f},{a:.0f},{y+20:.0f})\\t(0,{ms(th_[-1]['e']-t)},\\clip({a:.0f},{y-20:.0f},{b:.0f},{y+20:.0f}))")
    it = seq(ph, "イタイ")
    if it:
        cx = mid(it); t = it[0]["s"]
        f.shape(0, t, k.t_out + 0.3, cx, JY, draw=S.heart(66), c1="#FF7A9A", a_peak=150, blur=5, fade_in=0.2, fade_out=0.4,
                extra="\\fscx70\\fscy70\\t(0,300,0.5,\\fscx100\\fscy100)" + sway(6, 160, 5))
        f.shape(6, it[1]["s"], k.t_out + 0.3, cx, JY - 4, draw=S.crack(R, 90, 3.5, 2), c1="#401020", a_peak=40, blur=0.6, fade_in=0.02,
                fade_out=0.4, extra="\\frz-70")
    # 99-102 家的暖光
    f.glow(0, 99.0, k.t_end, mid(ph.chars), JY + 10, (f.b[2] - f.b[0]) / 2 - 120, 48, "#FFC890", a_peak=215, blur=26, fade_in=0.8)


def fx_candle_book(f, ph, k):
    R = f.rng
    a, b = span(ph.chars); cx = (a + b) / 2
    bk_y = JY + 20
    t0 = k.t_in + 0.2
    f.shape(0, t0, k.t_end, cx, bk_y, draw=S.book(150), c1="#FFE2B0", a_peak=175, blur=1.2, fade_in=0.6, fade_out=0.6,
            c3="#FFB04A", bord=2, a3=180, extra="\\fscy70\\t(0,600,\\fscy100)")
    sh = seq(ph, "失っていいような")
    for i, c in enumerate(sh[::2]):     # 翻页：书页绕书脊翻到左侧
        t = c["s"]
        f.shape(0, t, t + 0.6, cx + 50, bk_y - 6, cx - 50, bk_y - 6, S.page(90), "#FFF2D8", a_peak=150, blur=1, fade_in=0.05, fade_out=0.2,
                extra="\\t(0,550,\\fry180)")
    for sx in (a - 50, b + 50):
        f.shape(6, t0, k.t_end, sx, JY - 4, draw=S.candle_flame(24), c1="#FFD27A", a_peak=10, blur=1.5, c3=FIRE, bord=3, a3=80,
                fade_in=0.5, fade_out=0.6, extra=sway(int((k.t_end - t0) / 0.3), 300, 8) + "\\fscy100")
        f.glow(0, t0, k.t_end, sx, JY - 4, 38, 42, "#FFB04A", a_peak=170, blur=16, fade_in=0.5, fade_out=0.6,
               extra=flicker(int((k.t_end - t0) / 0.25), 250, 190, 150))
    mi = seq(ph, "未来")
    if mi:
        for c in mi:
            f.burst(c["s"], c["x"], JY - 10, 6, ["#FFE8B0", "#FFFFFF", "#FFC860"], speed=(20, 60), up=1.2, size=(2, 4), life=(0.8, 1.4))
        f.pulse(6, mi[0]["s"], mid(mi), JY - 34, S.sparkle(30), "#FFFFFF", dur=1.0, s0=20, s1=100, a0=0, blur=0.8, extra="\\t(\\frz90)")


def fx_roxy_forest(f, ph, k):
    R = f.rng
    lat = ph.chars[0]
    hx, hy = lat["x"] - lat["w"] / 2 + 10, f.b[1] + 40
    t0, t1 = 109.5, 112.6
    f.shape(7, t0, t1, hx, hy - 30, hx, hy, S.witch_hat(34), "#3A4A9A", a_peak=30, blur=0.8, c3="#9EB8FF", bord=1.5, a3=60,
            fade_in=0.2, fade_out=0.4, t_move=(0, 450), extra="\\frz-40\\t(0,450,0.5,\\frz-12)" + sway(4, 700, 5))
    for c in ph.chars[1:]:
        if c["s"] < 113.4:
            f.burst(c["s"], c["x"], JY - 10, 5, ["#9ED8FF", "#46C8FF", "#FFFFFF"], draw_fn=lambda r: S.teardrop(r * 1.6), speed=(30, 70),
                    up=0.5, size=(3, 5), life=(0.5, 0.9), spin=True)
            f.pulse(0, c["s"], c["x"], JY + 34, S.ripple(40, 2), "#9ED8FF", dur=0.8, s0=40, s1=120, a0=100, blur=1)
    # 114 林间光：斜射光柱
    for i in range(7):
        t = 113.4 + i * 0.12; x = R.uniform(f.b[0] + 80, f.b[2] - 80)
        f.shape(0, t, k.t_end, x, (f.b[1] + f.b[3]) / 2, draw=S.rect(R.uniform(14, 34), f.b[3] - f.b[1] - 70), c1="#FFF6D0",
                a_peak=R.randint(190, 220), blur=10, fade_in=0.6, fade_out=0.6, extra="\\frz-18")
    f.drift(113.4, k.t_end, 12, ["#FFF6D0", "#E0FFD0"], S.circle, vx=(-6, 6), vy=(-10, 6), size=(1.5, 3), a=(40, 120), spin=False)


def fx_break_wheat(f, ph, k):
    fx_break(f, ph, k, "#FFB42E", ["#FFE6A0", "#FFD060", "#FFFFFF"], "#FFE0E0")
    R = f.rng
    for side in (0, 1):
        for j in range(4):
            x = (f.b[0] + 26 + j * 22) if side == 0 else (f.b[2] - 26 - j * 22)
            f.shape(0, 116.6 + j * 0.1, k.t_end, x, f.b[3] - 60, draw=S.wheat(R.uniform(42, 56)), c1="#F0C050", a_peak=90, blur=0.8,
                    fade_in=0.6, fade_out=0.6, extra="\\org(%.1f,%.1f)" % (x, f.b[3] - 10) + sway(int((k.t_end - 116.6) / 1.2), 1200, 6))
    f.drift(116.6, k.t_end, 20, ["#FFD878", "#FFE8B0", "#FFC040"], S.circle, vx=(10, 30), vy=(-18, -4), size=(1.8, 3.5), a=(40, 130), spin=False)


def fx_glitch_teal(f, ph, k):
    fx_glitch(f, ph, k, "#FF3A5A", "#1FF2E0", ["#FF3A3A", "#FFFFFF", "#1FD2C0"])
    R = f.rng
    for t in (124.5, seq(ph, "見境")[0]["s"] if seq(ph, "見境") else 125):   # 瑞杰路德额上的“红眼”
        x = R.uniform(f.b[0] + 80, f.b[2] - 80)
        f.pulse(6, t, x, f.b[1] + 36, S.eye_ring(26), "#FF2A2A", dur=0.9, s0=80, s1=120, a0=30, blur=1.2)


def fx_hide_map(f, ph, k):
    R = f.rng
    f.pulse(6, 127.6, f.b[0] + 70, JY - 20, S.eye_ring(30), "#FF2A2A", dur=1.2, s0=70, s1=110, a0=20, blur=1.2)
    for n in range(2):
        chs = seq(ph, "隠したい", n)
        if not chs:
            continue
        a, b = span(chs); t = chs[0]["s"]; d = max(0.5, chs[-1]["e"] - t)
        f.shape(7, t, t + d + 0.3, a - 20, JY - 4, b + 20, JY - 4, S.veil(120, 96, 4, 6), "#0A1030", a_peak=90, blur=6,
                fade_in=0.1, fade_out=0.3, t_move=(0, ms(d)))
    sb = seq(ph, "全てを")
    t0 = sb[0]["s"] - 0.3 if sb else 129.0
    a, b = f.b[0] + 30, f.b[2] - 30
    for i in range(9):     # 129 蓝色地图：经纬网格
        x = a + (b - a) * i / 8
        f.shape(0, t0 + i * 0.03, k.t_end, x, (f.b[1] + f.b[3]) / 2, draw=S.rect(1.6, f.b[3] - f.b[1] - 40), c1="#6E8CFF", a_peak=170,
                blur=0.6, fade_in=0.4, fade_out=0.5)
    for j in range(4):
        y = f.b[1] + 20 + (f.b[3] - f.b[1] - 40) * j / 3
        f.shape(0, t0 + j * 0.05, k.t_end, (a + b) / 2, y, draw=S.rect(b - a, 1.6), c1="#6E8CFF", a_peak=170, blur=0.6, fade_in=0.4, fade_out=0.5)
    f.shape(6, t0, k.t_end, b - 60, JY - 10, draw=S.compass(40), c1="#BCD0FF", a_peak=60, blur=0.8, fade_in=0.4, fade_out=0.5,
            extra="\\frz-30\\t(0,800,0.4,\\frz12)\\t(800,1600,\\frz0)")


def fx_bolt_tears(f, ph, k):
    R = f.rng
    for c in seq(ph, "背負う"):
        for j in range(2):
            x = R.uniform(f.b[0] + 40, f.b[2] - 40); t = c["s"] + j * 0.06
            f.shape(7, t, t + 0.18, x, (f.b[1] + f.b[3]) / 2, draw=S.bolt(R, f.b[3] - f.b[1] - 50, 5), c1="#E8FCFF", a_peak=0, blur=0.8,
                    c3="#34D8FF", bord=2.5, a3=60, fade_in=0.01, fade_out=0.1, extra=flicker(1, 120, 180, 0))
        f.glow(0, c["s"], c["s"] + 0.3, c["x"], JY, 70, 60, "#34D8FF", a_peak=150, blur=20, fade_in=0.02, fade_out=0.25)
    ki = seq(ph, "決めた")
    if ki:
        f.floor_spin(0, ki[0]["s"], ki[0]["s"] + 1.6, mid(ki), JY + 36, S.rune_ring(150, rng=R), "#7CE8FF", deg_per_s=60, a_peak=60,
                     blur=0.8, fade_in=0.2, fade_out=0.9, grow=0.6)
    # 138 爆炎
    cx = mid(ph.chars)
    f.burst(138.0, cx, JY + 20, 16, ["#FFB347", "#FF6A1F", "#FFE0A0"], speed=(60, 160), up=0.5, life=(0.5, 1.0), size=(2, 4.5), glow="#FF5A10")
    f.glow(0, 138.0, 138.6, cx, JY + 10, 200, 60, "#FF7A2A", a_peak=150, blur=26, fade_in=0.05, fade_out=0.5)
    for c in seq(ph, "涙"):
        for j in range(4):
            x = c["x"] + R.uniform(-20, 20)
            f.shape(6, c["s"] + j * 0.15, c["s"] + j * 0.15 + 0.9, x, JY + 18, x, f.b[3] - 22, S.teardrop(8), "#C8F6FF", a_peak=30,
                    blur=0.8, c3="#34D8FF", bord=1.2, a3=100, fade_in=0.1, fade_out=0.3, accel=1.8)
        f.pulse(0, c["s"] + 0.8, c["x"], f.b[3] - 26, S.ripple(40, 2), "#9EEFFF", dur=0.9, s0=30, s1=130, a0=80, blur=1)


def fx_snow_rise(f, ph, k):
    R = f.rng
    f.drift(k.t_in, 145.2, 34, ["#FFFFFF", "#E8F6FF"], S.snowflake, vx=(-10, 14), vy=(10, 28), size=(5, 9), a=(20, 110), blur=(0.5, 1.2))
    for c in seq(ph, "背伸び"):
        f.burst(c["s"], c["x"], JY + 20, 4, ["#FFFFFF", "#CDEBFF"], speed=(15, 40), up=1.6, size=(2, 3.5), life=(0.7, 1.1))
    se = seq(ph, "世界")
    if se:
        t = se[0]["s"]
        f.glow(0, t, k.t_end, mid(ph.chars), JY + 16, (f.b[2] - f.b[0]) / 2 - 90, 55, "#FFC878", a_peak=190, blur=28, fade_in=0.9)
        f.shape(0, t, k.t_end, mid(se), JY - 10, draw=S.sunburst(9, 110, 7, 150), c1="#FFE0A0", a_peak=185, blur=3, fade_in=0.6,
                fade_out=0.5, extra="\\fscx40\\fscy40\\t(0,900,0.5,\\fscx100\\fscy100)")


def fx_flowers(f, ph, k):
    R = f.rng
    cols = ["#FF5AAE", "#FF8AC8", "#FFE04A", "#FFFFFF", "#FFB0D8"]
    f.drift(k.t_in, k.t_end, 30, cols, lambda s: S.sakura(s) if R.random() < 0.5 else S.petal(s), vx=(15, 50), vy=(-12, 12),
            size=(6, 10), a=(10, 90), blur=(0.5, 1.2))
    for c in ph.chars:
        f.burst(c["s"], c["x"], JY - 10, 2, cols, draw_fn=S.petal, speed=(30, 70), up=0.6, size=(4, 6), spin=True)
    for key, cc in (("ため？", "#FF5AAE"), ("自分", "#FFE04A")):
        chs = seq(ph, key)
        if chs:
            t = chs[-1]["s"]; x = chs[-1]["x"] if key == "ため？" else mid(chs)
            f.shape(0, t, k.t_out + 0.3, x, JY, draw=S.flower(56), c1=cc, a_peak=130, blur=2, fade_in=0.2, fade_out=0.4,
                    extra="\\fscx10\\fscy10\\frz-60\\t(0,600,0.5,\\fscx100\\fscy100\\frz0)")


def fx_dinner_flip(f, ph, k):
    R = f.rng
    f.drift(k.t_in, k.t_end, 22, ["#FFD090", "#FFE8C0", "#FFB060"], S.circle, vx=(-6, 6), vy=(-14, -4), size=(2, 4.5), a=(60, 150),
            spin=False, blur=(1.5, 3), glow="#FF9B4A")
    f.glow(0, k.t_in, k.t_end, mid(ph.chars), JY + 12, (f.b[2] - f.b[0]) / 2 - 100, 50, "#FF9B4A", a_peak=215, blur=26, fade_in=1.0)
    ur = seq(ph, "裏側")
    if ur:
        x = ur[-1]["x"] + 80; t = ur[0]["s"]
        f.shape(6, t, k.t_out + 0.3, x, JY - 6, draw=S.heart(30), c1="#FF8A9A", a_peak=40, blur=1, fade_in=0.2, fade_out=0.4,
                c3="#FFD0D8", bord=1.5, a3=80, extra=f"\\t(0,{ms(k.t_out-t)},\\fry{360*int((k.t_out-t)/1.2)})")
    wa = seq(ph, "わからない")
    for c in wa:
        f.text(6, c["s"], c["s"] + 0.9, c["x"] + 12, RBY, "?", "LAT", 66, f"\\bord0\\shad0\\1c{col('#FFE0B0')}\\blur0.8\\fscx55\\fscy55"
               f"\\alpha&HFF&\\t(0,150,\\alpha&H50&)\\t(500,900,\\alpha&HFF&)", x1=c["x"] + 26, y1=RBY - 26)


def fx_break_water(f, ph, k):
    R = f.rng
    for c in find(ph, "壊"):
        f.burst(c["s"], c["x"], JY, 12, ["#C8F6FF", "#46C8FF", "#FFFFFF"], draw_fn=lambda r: S.teardrop(r * 1.5), speed=(50, 120),
                up=0.4, size=(3, 6), life=(0.5, 1.0), spin=True, glow="#1E90FF")
        for j in range(2):
            f.pulse(0, c["s"] + j * 0.18, c["x"], JY + 36, S.ripple(70, 2.5), "#9EEFFF", dur=1.0, s0=30, s1=140, a0=60, blur=1)
    f.drift(k.t_in, k.t_end, 26, ["#C8F6FF", "#9EE0FF"], lambda s: S.ring(s, 1.3), vx=(-6, 6), vy=(-30, -12), size=(4, 9), a=(40, 130),
            spin=False, blur=(0.5, 1))
    mo = seq(ph, "戻れない")
    if mo:
        f.pulse(0, mo[0]["s"], mid(mo), JY + 36, S.ripple(160, 3), "#9EEFFF", dur=1.6, s0=20, s1=110, a0=50, blur=1)


def fx_embrace(f, ph, k):
    R = f.rng
    a, b = span(ph.chars); cx = mid(ph.chars)
    da = seq(ph, "抱きしめ")
    t = da[0]["s"] if da else ph.s + 2
    rr = 90
    for sgn, a0, a1 in ((-1, 110, 250), (1, -70, 70)):
        x0 = cx + sgn * ((b - a) / 2 + 20); x1 = cx + sgn * ((b - a) / 2 - 30)
        f.shape(6, t - 0.2, k.t_out + 0.4, x0, JY - 2, x1, JY - 2, S.arc(rr, a0, a1, 5), "#FFC0D0", a_peak=40, blur=1.4, c3="#FF7A9A",
                bord=2, a3=100, fade_in=0.3, fade_out=0.4, t_move=(0, 700), extra="\\fscy80")
    f.glow(0, t, k.t_end, cx, JY + 6, (b - a) / 2 + 30, 55, "#FF9AB0", a_peak=205, blur=26, fade_in=0.8)
    for key in ("強", "抱"):
        for c in find(ph, key):
            f.burst(c["s"], c["x"], JY - 16, 5, ["#FF9AB0", "#FFD0DC", "#FFFFFF"], draw_fn=lambda r: S.heart(r * 2), speed=(25, 60),
                    up=1.0, size=(3, 5), life=(0.8, 1.4))


def fx_eraser(f, ph, k):
    R = f.rng
    ya = seq(ph, "優しさ")
    if ya:
        f.glow(0, ya[0]["s"], k.t_end, mid(ya), JY, 110, 48, "#C8FFD8", a_peak=200, blur=20, fade_in=0.5)
    ke = seq(ph, "消し去って")
    if ke:
        a, b = span(ke); t0 = ke[0]["s"]; t1 = ke[-1]["e"]
        f.shape(7, t0, t1 + 0.3, a - 10, JY - 8, b + 10, JY - 8, S.rect(34, 70), "#F4FFF6", a_peak=60, blur=2, c3="#9EE6B8", bord=2,
                a3=120, fade_in=0.1, fade_out=0.3, t_move=(0, ms(t1 - t0)), extra="\\frz-12")
        for i in range(int((t1 - t0) / 0.06)):
            tt = t0 + i * 0.06; x = a + (b - a) * (tt - t0) / (t1 - t0)
            f.shape(6, tt, tt + 0.8, x, JY + 20, x + R.uniform(-15, 15), JY + R.uniform(35, 60), S.circle(R.uniform(1.5, 3)), "#F4FFF6",
                    a_peak=R.randint(40, 120), blur=1, fade_in=0.05, fade_out=0.6)
        # 被擦过的字短暂变淡
        for c in ke:
            f.text(6, c["s"] + 0.05, c["s"] + 0.6, c["x"], JY, c["ch"], "JP", 84,
                   f"\\bord6\\shad0\\1c{col('#0A1A12')}\\3c{col('#0A1A12')}\\blur6\\alpha&HFF&\\t(0,120,\\alpha&H70&)\\t(250,550,\\alpha&HFF&)")


def fx_overflow(f, ph, k):
    R = f.rng
    for c in find(ph, "悲"):
        for j in range(3):
            x = c["x"] + R.uniform(-15, 15)
            f.shape(6, c["s"] + j * 0.2, c["s"] + j * 0.2 + 1.0, x, JY + 20, x, f.b[3] - 22, S.teardrop(7), "#FFF0C8", a_peak=40, blur=0.8,
                    c3="#FFB43C", bord=1, a3=120, fade_in=0.1, fade_out=0.3, accel=1.8)
    af = seq(ph, "溢れ出る")
    for c in af:
        f.burst(c["s"], c["x"], JY, 12, ["#FFE8A0", "#FFD060", "#FFFFFF"], speed=(30, 90), up=1.3, size=(2, 4), life=(0.8, 1.5), glow="#FFB43C")
        for j in range(2):
            x = c["x"] + R.uniform(-20, 20)
            f.shape(6, c["s"] + 0.1 + j * 0.2, c["s"] + 1.3, x, JY + 22, x, f.b[3] - 20, S.teardrop(6), "#FFE8A0", a_peak=40, blur=1,
                    fade_in=0.1, fade_out=0.4, accel=1.6, extra="\\frz180")
    om = seq(ph, "思い")
    if om:
        f.glow(0, om[0]["s"], k.t_end, mid(ph.chars), JY + 8, (f.b[2] - f.b[0]) / 2 - 90, 55, "#FFB43C", a_peak=190, blur=28, fade_in=0.8)
        f.pulse(6, om[0]["s"], om[-1]["x"] + 50, JY - 36, S.sparkle(30), "#FFFFFF", dur=1.4, s0=20, s1=100, a0=0, blur=0.8, extra="\\t(\\frz90)")


def fx_chains(f, ph, k):
    R = f.rng
    a, b = f.b[0] + 40, f.b[2] - 40
    n1 = seq(ph, "逃げない"); ji = seq(ph, "ジレンマ"); ka = seq(ph, "から")
    t_end_chain = ka[0]["s"] + 0.15 if ka else ph.e
    n_links = int((b - a) / (13 * 1.45))
    for j, (t, y, rz) in enumerate(((n1[0]["s"], JY - 6, -4), (seq(ph, "逃げたくない")[0]["s"] if seq(ph, "逃げたくない") else n1[0]["s"] + 1, JY + 14, 3))):
        ch = S.chain(n_links, 13)
        f.shape(0, t, t_end_chain, (a + b) / 2, y, draw=ch, c1="#B8B0D8", a_peak=120, blur=0.8, c3="#302848", bord=1, a3=120, fade_in=0.05,
                fade_out=0.05, extra=f"\\frz{rz}\\clip({a-30:.0f},{y-60:.0f},{a-30:.0f},{y+60:.0f})\\t(0,500,\\clip({a-30:.0f},{y-60:.0f},{b+30:.0f},{y+60:.0f}))" +
                (f"\\t({ms(ji[0]['s']-t)},{ms(ji[-1]['e']-t)},\\fscx94)" if ji else ""))
    if ka:   # 挣断锁链
        t = ka[0]["s"] + 0.1
        for i in range(24):
            x = R.uniform(a, b)
            f.shape(7, t, t + R.uniform(0.6, 1.0), x, JY + R.uniform(-10, 16), x + R.uniform(-40, 40), JY + R.uniform(10, 40),
                    S.chain_link(R.uniform(8, 12)) if i % 3 else S.shard(R, 8), "#B8B0D8", a_peak=R.randint(20, 80), blur=0.8,
                    fade_in=0.02, fade_out=0.6, extra=f"\\frz{R.randint(0,360)}\\t(\\frz{R.randint(-200,200)})")
        f.pulse(5, t, mid(ph.chars), JY, S.ellipse_ring(200, 60, 3), "#9A8CFF", dur=0.6, s0=50, s1=120, a0=40, blur=1.5)
    for j in range(3):
        y = R.uniform(JY - 10, JY + 60); w = R.uniform(260, 400)
        f.shape(0, k.t_in + j * 0.3, k.t_end, f.b[0] + w / 2, y, f.b[2] - w / 2, y, S.veil(w, 40, 3, 5), "#C0C4D8", a_peak=205, blur=14,
                fade_in=0.8, fade_out=0.7)


def fx_glitch_cyan(f, ph, k):
    fx_glitch(f, ph, k, "#FF3A8A", "#2EF2E0", ["#2EF2E0", "#E0FFFF", "#6A8C90"])


def fx_finale(f, ph, k):
    R = f.rng
    fx_magic_guard(f, ph, k, big=True)
    cx = mid(ph.chars)
    # 204 火球横穿
    t = 204.0
    f.shape(7, t, t + 0.9, f.b[0] + 40, JY - 30, f.b[2] - 40, JY - 30, S.circle(14), "#FFE0A0", a_peak=0, blur=3, c3=FIRE, bord=8, a3=60,
            fade_in=0.1, fade_out=0.2, alpha_t="")
    for i in range(18):
        tt = t + i * 0.045; x = f.b[0] + 40 + (f.b[2] - f.b[0] - 80) * (tt - t) / 0.9
        f.shape(6, tt, tt + 0.6, x, JY - 30, x - R.uniform(10, 40), JY - 30 + R.uniform(-15, 15), S.flame(R.uniform(8, 14)), R.choice([FIRE, "#FFB347"]),
                a_peak=60, blur=2, fade_in=0.02, fade_out=0.5, extra="\\frz-90")
    for i in range(6):   # 205.5-207 天空弧光
        tt = 205.5 + i * 0.25
        f.shape(6, tt, tt + 0.9, cx + R.uniform(-250, 250), JY - 30, draw=S.arc(180, 200, 340, 4), c1=R.choice(["#FFD090", "#A8E8FF", "#FFFFFF"]),
                a_peak=40, blur=1.2, fade_in=0.1, fade_out=0.6, extra="\\fscy30")
    # 208.5 塞妮丝拥抱鲁迪：暖光
    f.glow(0, 208.5, k.t_end, cx, JY + 10, (f.b[2] - f.b[0]) / 2 - 100, 55, "#FFB870", a_peak=190, blur=28, fade_in=0.8)
    for c in seq(ph, "教えてくれた"):
        f.burst(c["s"], c["x"], JY - 10, 5, ["#FFD090", "#A8E8FF", "#FFFFFF"], speed=(25, 70), up=1.0, size=(2, 4))


def fx_only_you(f, ph, k):
    R = f.rng
    a, b = span(ph.chars); cx = mid(ph.chars)
    f.glow(0, k.t_in, k.t_end, cx, JY + 8, (b - a) / 2 + 50, 55, "#6F9CFF", a_peak=205, blur=26, fade_in=1.0, fade_out=1.0)
    hx, hy = a - 40, f.b[1] + 44
    f.shape(7, 213.0, k.t_out + 0.6, hx, hy - 20, hx, hy, S.witch_hat(32), "#3A4A9A", a_peak=30, blur=0.8, c3="#9EB8FF", bord=1.5, a3=60,
            fade_in=0.3, fade_out=0.6, t_move=(0, 500), extra="\\frz-30\\t(0,500,0.5,\\frz-10)" + sway(4, 900, 4))
    ke = find(ph, "け")[0]
    x, y = ke["x"] + 50, JY - 38
    f.shape(7, ke["s"], k.t_out + 1.0, x, y, draw=S.star(5, 22, 9), c1="#FFF3C0", a_peak=0, blur=0.8, c3="#FFC040", bord=2, a3=60,
            fade_in=0.15, fade_out=1.0, extra="\\fscx10\\fscy10\\t(0,350,0.5,\\fscx120\\fscy120)\\t(350,700,\\fscx95\\fscy95)\\t(\\frz144)")
    f.glow(6, ke["s"], k.t_out + 1.0, x, y, 30, 30, "#FFD27A", a_peak=110, blur=12, fade_in=0.2, fade_out=1.0)
    f.drift(k.t_in, k.t_end, 12, ["#FFFFFF", "#E0E8FF"], S.feather, vx=(8, 24), vy=(6, 16), size=(10, 14), a=(30, 110),
            extra_fn=lambda R: sway(4, 900, 25))
    for c in ph.chars:
        f.burst(c["s"], c["x"], JY - 20, 4, ["#FFF3C0", "#FFFFFF", "#9EB8FF"], draw_fn=S.sparkle, speed=(20, 60), up=1.0, size=(4, 7), spin=True)


FXMAP = {k[3:]: v for k, v in globals().items() if k.startswith("fx_")}


# ======================================================================== 卡片（标题/序章/间奏/片尾）
def card(name, t0, t1, items, fx_fn=None, seed=0):
    """items: [(text, style, fs, metric, x, y, delay, kind)]；band = 文字墨迹 + 5%"""
    xs0, ys0, xs1, ys1 = [], [], [], []
    for text, st, fs, M, x, y, dl, _ in items:
        w = M.width(text, fs, 0) * 1.05; h = M.em(fs)
        xs0.append(x - w / 2); xs1.append(x + w / 2); ys0.append(y - h * 0.62); ys1.append(y + h * 0.62)
    band = doc.band(name, min(xs0) - 96, min(ys0) - 54, max(xs1) + 96, max(ys1) + 54, t0, t1)
    for text, st, fs, M, x, y, dl, kind in items:
        ta = t0 + dl
        sh = "\\bord7\\shad0\\1a&HFF&\\3c&H100804&\\3a&H60&\\blur9"
        lk = "\\bord1.6\\shad0\\3c&H201008&\\3a&H40&\\blur0.8"
        for layer, look in ((1, sh), (2, lk)):
            if kind == "wipe":
                w = M.width(text, fs, 0) * 1.1
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


def title():
    T0, T1 = 0.35, 6.2
    items = [("TVアニメ『無職転生 ～異世界行ったら本気だす～』エンディングテーマ", "CARD", 28, MJ, 960, 400, 0.2, "fade"),
             ("オンリー", "TITLE", 128, MJ, 960, 510, 0.5, "wipe"),
             ("Only", "TLAT", 58, ML, 960, 612, 1.1, "fade"),
             ("唯一", "CARDCN", 34, MC, 960, 668, 1.3, "fade"),
             ("作詞・作曲・歌　大原ゆい子", "CARD", 28, MJ, 960, 720, 1.6, "fade")]

    def fx(f, b):
        R = f.rng
        f.shape(0, T0 + 0.6, T1, 960, 510, draw=S.ring(170, 2), c1="#FFE6C0", a_peak=150, blur=1, fade_in=0.6, fade_out=0.6,
                extra="\\fscx40\\fscy40\\t(0,1400,0.5,\\fscx100\\fscy100)\\fscy100")
        f.pulse(0, T0 + 0.5, 960, 510, S.ring(170, 3), "#FFD090", dur=1.6, s0=20, s1=130, a0=60, blur=2)
        f.drift(T0 + 0.8, T1, 12, ["#FFFFFF", "#FFF0D8"], S.feather, vx=(10, 30), vy=(8, 20), size=(12, 18), a=(30, 110),
                extra_fn=lambda R: sway(4, 900, 25))
        for i in range(7):
            f.pulse(6, T0 + 1.0 + i * 0.5, R.uniform(b[0] + 60, b[2] - 60), R.uniform(b[1] + 40, b[3] - 40), S.sparkle(18), "#FFF4D8",
                    dur=0.9, s0=20, s1=100, a0=20, blur=0.8, extra="\\t(\\frz90)")
    card("title", T0, T1 + 0.2, items, fx, 1)


def prologue():
    T0, T1 = 10.8, 18.0
    items = [("二度目の人生　今度こそ本気で生きる", "PRO", 54, MJ, 960, 905, 0.0, "wipe"),
             ("第二次的人生　这一次一定要全力以赴地活下去", "PROCN", 40, MC, 960, 975, 0.6, "fade")]

    def fx(f, b):
        R = f.rng
        f.pulse(0, T0 + 0.2, 960, 930, S.ellipse_ring(420, 70, 2), "#FFE0B0", dur=1.8, s0=30, s1=105, a0=80, blur=1.5)
        for i in range(6):
            f.pulse(6, T0 + 1.0 + i * 0.8, R.uniform(b[0] + 60, b[2] - 60), R.uniform(b[1] + 30, b[3] - 30), S.sparkle(16), "#FFF4D8",
                    dur=1.0, s0=20, s1=100, a0=20, blur=0.8, extra="\\t(\\frz90)")
        for _ in range(26):     # 16.5-18 风暴中的船：斜雨
            t = R.uniform(16.4, 17.9); x = R.uniform(b[0] + 30, b[2] - 30)
            f.shape(7, t, t + 0.35, x, b[1] + 20, x - 40, b[3] - 20, S.rect(1.6, 36), "#D8E4F0", a_peak=R.randint(60, 140), blur=0.6,
                    fade_in=0.05, fade_out=0.1, extra="\\frz-20")
    card("pro", T0, T1, items, fx, 2)


def interlude():
    T0, T1 = 80.2, 88.2
    items = [("この世界で出会った　大切な人たちへ", "PRO", 54, MJ, 960, 905, 0.0, "wipe"),
             ("致在这个世界相遇的　每一个重要的人", "PROCN", 40, MC, 960, 975, 0.6, "fade")]

    def fx(f, b):
        f.drift(T0, T1, 26, ["#FFD060", "#FFB040", "#F0C050", "#FFE090"], S.leaf, vx=(10, 40), vy=(8, 24), size=(6, 10), a=(20, 100),
                extra_fn=lambda R: sway(4, 800, 30))
        for sx in (b[0] + 60, b[2] - 60):   # 84 烛光
            f.shape(6, 83.8, T1, sx, 905, draw=S.candle_flame(24), c1="#FFD27A", a_peak=10, blur=1.5, c3=FIRE, bord=3, a3=80,
                    fade_in=0.5, fade_out=0.6, extra=sway(12, 300, 8))
            f.glow(0, 83.8, T1, sx, 905, 36, 40, "#FFB04A", a_peak=170, blur=16, fade_in=0.5, fade_out=0.6)
    card("mid", T0, T1, items, fx, 3)


def outro():
    T0, T1 = 218.4, 227.4
    items = [("オンリー", "TITLE", 96, MJ, 960, 870, 0.0, "wipe"),
             ("Only　—　唯一", "CARDCN", 34, MC, 960, 958, 0.6, "fade"),
             ("作詞・作曲・歌　大原ゆい子", "CARD", 28, MJ, 960, 1010, 1.0, "fade")]

    def fx(f, b):
        R = f.rng
        f.drift(T0, T1, 16, ["#FFFFFF", "#FFF0D8"], S.feather, vx=(8, 24), vy=(6, 16), size=(12, 16), a=(30, 110),
                extra_fn=lambda R: sway(4, 900, 25))
        for i in range(8):
            f.pulse(6, T0 + 0.8 + i * 0.9, R.uniform(b[0] + 50, b[2] - 50), R.uniform(b[1] + 30, b[3] - 30), S.sparkle(16), "#FFF4D8",
                    dur=1.0, s0=20, s1=100, a0=20, blur=0.8, extra="\\t(\\frz90)")
    card("out", T0, T1, items, fx, 4)


# ======================================================================== 主流程
def main(out):
    phs = []
    for P in PHRASES:
        zh = P.get("zh") or " ".join(lines[li]["zh"] for li in P["lines"])
        phs.append(L.phrase(lines, P["lines"], TM, zh))
    # 显示窗口（避免前后两句在同一位置叠在一起）：
    #   退场：最后一拍唱出 ≥0.15s 后才走；若离下一句还早，就等长音结束
    #   退场时长：按“到下一句首拍”剩余时间自适应（0.25~dout），衔接紧时不做逐字错落
    #   入场：上一句退场完成 70% 之后；最迟在首拍前 0.12s
    plan = []
    for i, (P, ph) in enumerate(zip(PHRASES, phs)):
        o = dict(dict(din=0.5, dout=0.6, stg_out=0.02), **P.get("o", {}))
        last_s = ph.chars[-1]["s"]
        nxt = phs[i + 1].s if i + 1 < len(phs) else ph.e + 3
        t_out = max(last_s + 0.12, min(ph.e + 0.25, nxt - 0.75))
        room = nxt - 0.12 - t_out
        if room < o["dout"] + len(ph.chars) * o["stg_out"]:
            o["stg_out"] = 0.0
            o["dout"] = max(0.2, min(o["dout"], room * 0.8))
        plan.append((o, t_out))
    for i, (P, ph) in enumerate(zip(PHRASES, phs)):
        o, t_out = plan[i]
        if i:
            po, pto = plan[i - 1]
            prev_end = pto + po["dout"] + max(len(phs[i - 1].chars), len(phs[i - 1].cn)) * po["stg_out"]
            t_in = max(ph.s - 0.8, prev_end - 0.08)     # 同位置交替：上一句基本走完再进场
        else:
            t_in = ph.s - 0.8
        t_in = min(t_in, ph.s - 0.05)
        o["din"] = max(0.12, min(o["din"], ph.s - t_in))
        rng = random.Random(100 + i)
        name = f"p{i:02d}"
        k = Karaoke(doc, ph, name, P["th"], rng, **o)
        k.render(t_in, t_out)
        k.t_end = max(c["te"] for c in ph.chars) + 0.2
        doc.band(name, *ph.band, t_in, k.t_end)
        f = FX(doc, name, ph.band, seed=1000 + i)
        FXMAP[P["fx"]](f, ph, k)
        print(f"{name} {ph.s:7.2f}-{ph.e:7.2f} in {t_in:7.2f} out {t_out:7.2f} dout {o['dout']:.2f} band {tuple(round(v) for v in ph.band)} clamp {f.n_clamped}")
    title(); prologue(); interlude(); outro()
    n = doc.write(out)
    print("events:", n)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "out/only_ed1.ass"))
