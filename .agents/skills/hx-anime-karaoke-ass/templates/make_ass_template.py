# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "numpy",
#   "fonttools",
# ]
# ///
"""
卡拉OK 特效字幕生成器模板。复制到工程目录（与 lyrics.txt / timing.json / calib.json 同级）后修改：
  1) SKILL_SCRIPTS 路径、字体文件、JP_Y
  2) PHRASES：每个显示句的 lines / 主题配色 / 动画选项 / 特效函数
  3) 写 fx_xxx(f, ph, k) 特效函数：只通过 f.shape / f.text / f.burst / f.drift / f.pulse / f.glow / f.floor_spin 发射
完整示例：examples/mushoku_ed1/make_ass.py（手写规划 + 卡片）；另见 static/music/ 下的历史工程。
"""
import json, math, os, random, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_SCRIPTS = os.environ.get("ASSFX", "")  # 必填: 指向本 skill 的 scripts/ 目录
if not SKILL_SCRIPTS:
    sys.exit("请先设置 ASSFX 指向本 skill 的 scripts/ 目录, 例如: export ASSFX=~/.agents/skills/hx-anime-karaoke-ass/scripts")
sys.path.insert(0, SKILL_SCRIPTS)
from assfx.core import Doc, col, al, ms
from assfx.lyrics import load
from assfx.layout import Layout, Metric
from assfx.gen import Generator, find, seq, span, mid, flicker, sway   # 出入场规划/卡片/查字工具
from assfx import shapes as S

FONTS = os.path.join(HERE, "fonts")
lines = load(os.path.join(HERE, "lyrics.txt"))
TM = {(m["line"], m["unit"], m["mora"]): m for m in json.load(open(os.path.join(HERE, "timing.json")))}
calib = json.load(open(os.path.join(HERE, "calib.json")))     # calibrate_ruby.py 的输出（jp-y 要与下面一致）

JP_Y = 915
L = Layout(jp_font=os.path.join(FONTS, "ShipporiMinchoB1-Bold.ttf"), cn_font=os.path.join(FONTS, "LXGWWenKai-Medium.ttf"),
           latin_font=os.path.join(FONTS, "CormorantGaramond-Italic[wght].ttf"),
           jp_fs=84, rb_fs=34, cn_fs=50, latin_fs=66, jp_y=JP_Y, calib=calib)

doc = Doc("<番剧> <OP/ED>「<曲名>」卡拉OK特效字幕", fx_font="LXGW WenKai Medium")
doc.add_style("JP", "Shippori Mincho B1", 84, bold=1)
doc.add_style("RB", "Shippori Mincho B1", 34, bold=1)
doc.add_style("CN", "LXGW WenKai Medium", 50)
doc.add_style("LAT", "Cormorant Garamond Light", 66, italic=1)


def TH(hi, glow, dark, base="#F6F1EC", cn="#F8F3EE"):
    return dict(hi=hi, glow=glow, dark=dark, base=base, cn=cn)


# ------------------------------------------------------------------ 特效函数示例
def fx_love(f, ph, k):
    """温柔句：字后暖光 + 关键字心形脉冲 + 每字飘出小爱心"""
    xs = [c["x"] for c in ph.chars]
    f.glow(0, k.t_in, k.t_end, sum(xs) / len(xs), JP_Y + 8, (max(xs) - min(xs)) / 2 + 40, 55, "#FFC9A0", a_peak=205, blur=26)
    for c in find(ph, "愛"):
        f.pulse(0, c["s"], c["x"], JP_Y, S.heart(60), "#FF8CA0", dur=1.0, s0=40, s1=135, a0=80, blur=5)
    for c in ph.chars:
        f.burst(c["s"], c["x"], JP_Y - 24, 2, ["#FFB6C4", "#FFFFFF"], draw_fn=lambda r: S.heart(r * 2), up=0.9, size=(3, 5))


def fx_break(f, ph, k):
    """激烈句：关键字裂纹 + 碎片"""
    R = f.rng
    for c in find(ph, "壊"):
        f.shape(6, c["s"], c["s"] + 0.9, c["x"], JP_Y, draw=S.crack(R, 130, 4.5), c1="#FFFFFF", c3="#FF2E4A", bord=1.5,
                a_peak=0, blur=0.6, fade_in=0.02, fade_out=0.5, extra=f"\\frz{R.uniform(-25, 25):.0f}")
        f.burst(c["s"], c["x"], JP_Y, 10, ["#FFFFFF", "#FF4A5A"], draw_fn=lambda r: S.shard(R, r * 2.6), up=-0.5, spin=True)


# ------------------------------------------------------------------ 每个显示句
PHRASES = [
    # 注释写清：对应画面时间点与内容
    dict(lines=[0], th=TH("#FFF3E6", "#FFA07A", "#3A1A12"), o=dict(ent="rise", ext="rise", hl="bloom"), fx="love"),
    dict(lines=[1], th=TH("#FFFFFF", "#FF2E4A", "#1E0004"), o=dict(ent="zoom", ext="scatter", hl="shake"), fx="break"),
]
FXMAP = {k[3:]: v for k, v in globals().items() if k.startswith("fx_")}


G = Generator(doc, L, lines, TM)          # lead=0.8：最早提前 0.8s 入场


def title_card():
    """标题卡示例：items = (文本, 样式, 字号, Metric, x, y, 延迟, fade|wipe)。band 自动 = 文字墨迹 + 5%。
    注意 Metric 必须用该样式的字体；样式 spacing 会被计入宽度（gen.card 读取 Style 的 Spacing 字段）。"""
    MJ = Metric(os.path.join(FONTS, "ShipporiMinchoB1-Bold.ttf"))
    MC = Metric(os.path.join(FONTS, "LXGWWenKai-Medium.ttf"))
    items = [("曲名", "JP", 84, MJ, 960, 880, 0.0, "wipe"),
             ("番剧名 OP", "CN", 50, MC, 960, 960, 0.6, "fade")]

    def fx(f, band):
        f.glow(0, 1.0, 6.0, 960, 900, 300, 70, "#FFE6C8", a_peak=210, blur=30)
    G.card("title", 1.0, 6.0, items, fx, seed=1)


def main(out):
    G.render(PHRASES, FXMAP)               # 打印每句 in/out/band/clamp
    title_card()
    print("events:", doc.write(out))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "out.ass"))
