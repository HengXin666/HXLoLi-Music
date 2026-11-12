# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "numpy",
#   "fonttools",
# ]
# ///
"""
卡拉OK 特效字幕生成器模板  **五层结构**.

复制到工程目录(与 lyrics.txt / timing.json / calib.json 同级)后修改:
  1) ASSFX 环境变量(hx-karaoke 会导出)与字体文件
  2) SEGMENTS: 段落表(时间 / 卡点等级 / 色族). 段边界用 chordwiki 的转调点, 不许凭感觉
  3) PHRASES: 每个显示句的 lines / 主题配色 / 动画选项 / 特效函数
  4) 写 fx_xxx(f, ph, k): 只通过 f.shape / f.text / f.burst / f.drift / f.pulse / f.glow / f.floor_spin 发射
  5) 接入预览台清单 (12-station 的参数层靠它): 主题用 register_theme 登记成有名字的色组,
     配方用 @recipe(why=..., knobs=[...]) 标注, 配方里的可调量用 f.opt("名", 默认) 读,
     卡点/背景/图片按段用 G.segment(...) 取参数. 不接入也能跑, 只是预览台只能做输出层补丁.

五层各有各的时钟(见 steps/4-kfx/index.md), **不要写成一个循环里画五遍**:

  主文本 / 副文本   人声音拍, 逐句        -> Generator.render()
  卡点              音乐事件网格           -> beat_layer(), 按段落遍历
  背景              镜头 / 情感            -> bg_layer(), 跨句连续
  图片              卡点时刻               -> image_layer(), 全曲 ≤8 处

字形与字体名必须与字体文件里的**真实族名**一致(不是文件名). 实测踩过:
文件 `LXGWWenKai-Medium.ttf` 的族名是 `霞鹜文楷 Medium`, 写成 `LXGW WenKai Medium` 会让
定制版 libass 找不到而回落, 症状是满屏豆腐块; 系统 ffmpeg 的字体回退会掩盖这个问题.
查真实族名: `hx-karaoke render_octopus.py <ass> --probe`.

完整示例: examples/mushoku_ed1/ (make_ass.py 设计表 PHRASES / 字层预设 P() / 高光集合 HIGH / 氛围床包装 _bedded, scene.py 公共场景,
fx_carry.py 承载与留白句, fx_high.py 高光句, fx_main.py 逐句主母题 pNN, fx_bed.py 氛围床 + 逐字命中, motif_img.py 图片母题, cards.py 卡片);
通用模块 templates/fx_bed.py (氛围床) 与 templates/motif_img.py (图片母题, 配 assets/motif.json) 可直接复制进工程;
"""
import json, math, os, random, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_SCRIPTS = os.environ.get("ASSFX", "")  # 必填: 指向本 skill 的 scripts/ 目录
if not SKILL_SCRIPTS:
    sys.exit("请先设置 ASSFX 指向本 skill 的 scripts/ 目录, 例如: export ASSFX=~/.agents/skills/hx-anime-karaoke-ass/scripts")
sys.path.insert(0, SKILL_SCRIPTS)
from assfx.base.core import Doc, col, al, ms
from assfx.base.lyrics import load
from assfx.text.layout import Layout, Metric
from assfx.layer.gen import Generator, find, seq, span, mid, flicker, sway, seed_parts   # 出入场规划/卡片/查字工具
from assfx.layer.manifest import recipe, knob, register_theme, register_family   # 预览台清单 (见 49-generate "接入清单")
from assfx.layer.fx import FX
from assfx.draw import shapes as S
from assfx.layer.music.beat import (MusicEvents, beat_scatter, beat_pulse, beat_drop, beat_sink, BEAT_COLORS)
from assfx.draw.image import put_image, pop_image, side_slots, check_images
from assfx.text.color import Palette, Scheme, make_hl_color, find_break, fold

FONTS = os.environ.get("ASSFX_FONTS", os.path.join(HERE, "fonts"))
lines = load(os.path.join(HERE, "lyrics.txt"))
TM = {(m["line"], m["unit"], m["mora"]): m for m in json.load(open(os.path.join(HERE, "timing.json")))}
calib = json.load(open(os.path.join(HERE, "calib.json")))     # calibrate_ruby.py 的输出(jp_y 要与它一致)

JP_Y = 915
L = Layout(jp_font=os.path.join(FONTS, "ShipporiMinchoB1-Bold.ttf"), cn_font=os.path.join(FONTS, "LXGWWenKai-Medium.ttf"),
           latin_font=os.path.join(FONTS, "CormorantGaramond-Italic[wght].ttf"),
           jp_fs=84, rb_fs=34, cn_fs=50, latin_fs=66, jp_y=JP_Y, calib=calib)

# 字体名用**真实族名**(见模块头). 改字体时先用 render_octopus.py --probe 查.
JP_FAMILY = "Shippori Mincho B1"
CN_FAMILY = "霞鹜文楷 Medium"
LAT_FAMILY = "Cormorant Garamond Light"

doc = Doc("<番剧> <OP/ED>「<曲名>」卡拉OK特效字幕", fx_font=CN_FAMILY)
doc.add_style("JP", JP_FAMILY, 84, bold=1)
doc.add_style("RB", JP_FAMILY, 34, bold=1)
doc.add_style("CN", CN_FAMILY, 50)
doc.add_style("LAT", LAT_FAMILY, 66, italic=1)
doc.add_style("TITLE", JP_FAMILY, 118, bold=1, spacing=8)
doc.add_style("CARD", CN_FAMILY, 32, spacing=6)


# ================================================================
# 段落表: (t0, t1, 卡点等级, 色族)
# 段边界用乐谱转调点(chordwiki); 等级 L0~L3 见 steps/4-kfx/42-text-main/impl/density.md
# ================================================================
SEGMENTS = [
    (30.8, 52.5,   0, "cyan"),
    (52.5, 84.2,   1, "cyan"),
    (84.2, 134.8,  2, "sunset"),
    (134.8, 158.4, 1, "violet"),
    (158.4, 245.0, 3, "jade"),
]


def seg_of(t):
    for t0, t1, lv, col in SEGMENTS:
        if t0 <= t < t1:
            return lv, col
    return 0, "cyan"


# 段落色系: 句内颜色在折线上按字游走(不是随机换色)
PAL = Palette([(t0, t1, Scheme("s%d" % i, ["#16243C", "#8A98A8"], level=lv,
                              roles={"octave": 26, "fifth": 208, "chorus": -34}))
               for i, (t0, t1, lv, _c) in enumerate(SEGMENTS)],
              default=Scheme("main", ["#DCE8F4"], level=0))


def TH(hi, glow, dark, base="#F6F1EC", cn="#F8F3EE"):
    return dict(hi=hi, glow=glow, dark=dark, base=base, cn=cn)


# 有名字的色组: 预览台里改色只能在这些组之间切, 交付说明能写出 "由 WARM 改为 BLOOD".
# skill 自带一批起点色组 (scripts/assfx/presets/themes.json); 这里登记本工程自己的, why 写对应画面.
TH_WARM = register_theme("WARM", TH("#FFF3E6", "#FFA07A", "#3A1A12"), why="温柔句, 暖光画面")
TH_BLOOD = register_theme("BLOOD", TH("#FFFFFF", "#FF2E4A", "#1E0004"), why="激烈句, 战斗画面")
for _n, _c in BEAT_COLORS.items():
    register_family(_n, _c, why="卡点色族")


# ------------------------------------------------------------------ 主文本层示例
@recipe(why="温柔句: 字后暖光 + 关键字心形脉冲 + 每字飘小爱心",
        knobs=[knob("hearts", 2, 0, 5, 1, "每个字飘出的小爱心数")])
def fx_love(f, ph, k):
    """温柔句: 字后暖光 + 关键字心形脉冲 + 每字飘小爱心"""
    xs = [c["x"] for c in ph.chars]
    f.glow(0, k.t_in, k.t_end, sum(xs) / len(xs), JP_Y + 8, (max(xs) - min(xs)) / 2 + 40, 55, "#FFC9A0", a_peak=205, blur=26)
    for c in find(ph, "愛"):
        f.pulse(0, c["s"], c["x"], JP_Y, S.heart(60), "#FF8CA0", dur=1.0, s0=40, s1=135, a0=80, blur=5)
    for c in ph.chars:
        f.burst(c["s"], c["x"], JP_Y - 24, f.opt("hearts", 2), ["#FFB6C4", "#FFFFFF"], draw_fn=lambda r: S.heart(r * 2), up=0.9, size=(3, 5))


@recipe(why="激烈句: 关键字裂纹 + 碎片", knobs=[knob("shards", 10, 4, 20, 1, "裂开时的碎片数")])
def fx_break(f, ph, k):
    """激烈句: 关键字裂纹 + 碎片"""
    R = f.rng
    for c in find(ph, "壊"):
        f.shape(6, c["s"], c["s"] + 0.9, c["x"], JP_Y, draw=S.crack(R, 130, 4.5), c1="#FFFFFF", c3="#FF2E4A", bord=1.5,
                a_peak=0, blur=0.6, fade_in=0.02, fade_out=0.5, extra=f"\\frz{R.uniform(-25, 25):.0f}")
        f.burst(c["s"], c["x"], JP_Y + 0, f.opt("shards", 10), ["#FFFFFF", "#FF4A5A"], draw_fn=lambda r: S.shard(R, r * 2.6), up=-0.5, spin=True)


# ------------------------------------------------------------------ 每个显示句
PHRASES = [
    # 注释写清: 对应画面时间点与内容
    # label 显示在预览台的单元列表里; 写画面时间点与内容
    dict(label="00 画面 xx-xx: <内容>", lines=[0], th=TH_WARM, o=dict(ent="rise", ext="rise", hl="bloom"), fx="love"),
    dict(label="01 画面 xx-xx: <内容>", lines=[1], th=TH_BLOOD, o=dict(ent="zoom", ext="scatter", hl="shake"), fx="break"),
]
FXMAP = {k[3:]: v for k, v in globals().items() if k.startswith("fx_")}

# ------------------------------------------------------------------ 字层预设 / 高光集合 / 氛围床 (可选)
# P(): 按句号写一行 PHRASES, 只写和默认不同的出入场/高亮. 例: P(5, "break", TH_BLOOD, ent="glitch", ext="scatter", hl="shake")
P = lambda i, fx, th, **o: dict(label="L%02d %s" % (i, fx), lines=[i], th=th, o=dict(dict(ent="rise", ext="rise", hl="wipe"), **o), fx=fx)  # noqa: E731
HIGH = set()    # 高光句的 fx 名 (不带 fx_ 前缀); 其余句按 carrier 强度铺床. 例: {"break"}
try:
    import fx_bed    # 复制 templates/fx_bed.py 到工程目录后启用 (它从 scene.py 取 S 等, 见其模块头); 没有就不铺床
except ImportError:
    fx_bed = None


def _bedded(name, fn):
    """主函数之后铺氛围床 + 逐字命中. 留白句 (quiet) 自己铺, 不包. 用同一个 f.rng 往后抽, 不改主函数的随机结果."""
    if fx_bed is None or name == "quiet":
        return fn

    def run(f, ph, k):
        fn(f, ph, k)
        fx_bed.apply(f, ph, k, name, "high" if name in HIGH else "carrier")
    run.__name__, run.__doc__, run.__wrapped__ = fn.__name__, fn.__doc__, fn   # 预览台清单按原函数名登记
    return run


FXMAP = {n: _bedded(n, fn) for n, fn in FXMAP.items()}

G = Generator(doc, L, lines, TM)          # lead=0.8: 最早提前 0.8s 入场

# 实测 33 句 band 的并集  卡点/背景/图片三层用这一个 band 登记
BAND_ALL = None   # 首次 render 后从 G.ks 反解; 不想反解就直接写 (x0,y0,x1,y1)


# ================================================================
# 卡点层 / 背景层 / 图片层: 独立时钟, 按段落遍历(不跟句)
# ================================================================
# Agent Notes: 卡拉OK skill 通用化  去掉单次制作的事实与清单式铺陈
# 
def beat_layer(f, t0, t1, p):
    """
    .agents/notes/implemented/process/2026-10-04-karaoke-skill-genericize.md
跟音乐事件网格走. 规格(起手 18~40%, 同刻多色, 存活密度)见 steps/4-kfx/44-beat.
    p 是 G.segment() 给的本段参数 (level/family 可在预览台按段改)."""
    lv, col = p["level"], p["family"]
    n = beat_pulse(f, ME, t0, t1, level=lv, colors=col, layer=0, every=4 if lv < 2 else 2)
    n += beat_scatter(f, ME, t0, t1, level=lv, colors=col,
                      per_beat=(5, 9) if lv >= 2 else (2, 4))
    n += beat_sink(f, ME, t0, t1)
    return n


def bg_layer(f, t0, t1, p):
    """由镜头/情感驱动, 跨句不停. band 铁律不变(见 steps/4-kfx/45-bg)."""
    lv, col = p["level"], p["family"]
    cols = BEAT_COLORS.get(col, ["#FFFFFF"])
    b, R, n = f.b, f.rng, 0
    t = t0
    while t < t1:
        f.shape(0, t, t + R.uniform(1.4, 2.4),
                R.uniform(b[0] + 20, b[2] - 20), b[3] - R.uniform(6, 40),
                R.uniform(b[0] + 20, b[2] - 20), b[1] + R.uniform(20, 80),
                draw=S.sparkle(R.uniform(3.0, 6.5)), c1=R.choice(cols),
                a_peak=R.randint(110, 175), blur=1.8, fade_in=0.4, fade_out=0.6)
        t += 0.6
        n += 1
    return n


def image_layer(f, t0, t1, p):
    """图片层: 全曲 ≤8 处, 左右元素在卡点出现. 图必须先抠干净(见 steps/4-kfx/46-image)."""
    hit = [("assets/cut/a.png", [170.3]), ("assets/cut/b.png", [193.0, 224.8])]
    n = 0
    for rel, ts in hit:
        if not os.path.exists(os.path.join(HERE, rel)):
            continue          # 图不存在就跳过, 不硬塞
        for t in ts:
            if t0 <= t < t1:
                n += side_slots(f, t, [rel], path_dir=HERE, y=(f.b[1] + f.b[3]) / 2, life=1.8, layer=3)
    return n


def title_card():
    """标题卡. items = (文本, 样式, 字号, Metric, x, y, 延迟, fade|wipe); band 自动 = 文字墨迹 + 5%.
    卡片是唯一**鼓励多字体**的地方(曲名/制作名单): 用不同字体与字号做出层次."""
    MJ = Metric(os.path.join(FONTS, "ShipporiMinchoB1-Bold.ttf"))
    MC = Metric(os.path.join(FONTS, "LXGWWenKai-Medium.ttf"))
    items = [("曲名", "JP", 84, MJ, 960, 880, 0.0, "wipe"),
             ("番剧名 OP", "CN", 50, MC, 960, 960, 0.6, "fade")]

    def fx(f, band):
        f.glow(0, 1.0, 6.0, 960, 900, 300, 70, "#FFE6C8", a_peak=210, blur=30)
    G.card("title", 1.0, 6.0, items, fx, seed=1)


def main(out):
    """Agent Notes
    .agents/notes/implemented/process/2026-10-02-karaoke-layout-consolidation.md
    """
    global BAND_ALL, ME
    try:
        # Agent Notes: skill 只保留一份可复现示例，模板只留一个
        # 
        ME = MusicEvents.load(os.path.join(HERE, "review", "music-events.json"))
    except Exception:
        ME = None
        print("[warn] 没有 review/music-events.json  卡点层会跳过. 先跑: hx-karaoke music_events.py ...")

    # 句内多色: 段落色系 + 声部色. voices.json 由 voices.py 生成; 没有就只按色域游走
    try:
        VJ = json.load(open(os.path.join(HERE, "review", "voices.json"), encoding="utf-8"))["tags"]
    except Exception:
        VJ = None

    phs = G.build(PHRASES)
    for P, ph in zip(PHRASES, phs):
        P["o"] = dict(P.get("o", {}), hl_color=make_hl_color(ph, PAL, voices=VJ))
    G.inputs(HERE, "lyrics.txt", "timing.json", "calib.json", "fixes.json")   # 变了预览台会标过期
    G.render(PHRASES, FXMAP)               # 打印每句 in/out/band/clamp; 同时登记清单

    if ME is not None:
        # band 并集: 从已渲染的句反解(每句的 ph.band 在 G.phs 里)
        xs0 = [ph.band[0] for ph in G.phs]; ys0 = [ph.band[1] for ph in G.phs]
        xs1 = [ph.band[2] for ph in G.phs]; ys1 = [ph.band[3] for ph in G.phs]
        BAND_ALL = (min(xs0), min(ys0), max(xs1), max(ys1))
        fb, fg, fi = (FX(doc, "beat", BAND_ALL, seed=31),
                      FX(doc, "bg", BAND_ALL, seed=32),
                      FX(doc, "img", BAND_ALL, seed=33))
        nb = ng = ni = 0
        for (t0, t1, lv, fam) in SEGMENTS:
            # 每段每层一个单元 (key = beat@<段起点ms>): 预览台可按段改等级/色族/旋钮/重抽, 别段不动
            for fx_, kind, base, fn in ((fb, "beat", 31, beat_layer), (fg, "bg", 32, bg_layer), (fi, "img", 33, image_layer)):
                p = G.segment(kind, t0, t1, BAND_ALL, level=lv, family=fam)
                if not p["enabled"]:
                    continue
                fx_.reseed(*seed_parts(base, kind, round(t0 * 1000), salt=p["salt"])).set_knobs(p["knobs"])
                n = fn(fx_, t0, t1, p)
                nb, ng, ni = nb + (kind == "beat") * n, ng + (kind == "bg") * n, ni + (kind == "img") * n
        for nm in ("beat", "bg", "img"):
            doc.band(nm, *BAND_ALL, SEGMENTS[0][0], SEGMENTS[-1][1])
        print("layers: beat %d / bg %d / img %d" % (nb, ng, ni))

    title_card()
    print("events:", doc.write(out))
    if "motif_img" in sys.modules:          # 用了图片母题 (templates/motif_img.py) 就汇总缺件回退, 别让缺图静默过关
        sys.modules["motif_img"].report(out)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "out.ass"))
