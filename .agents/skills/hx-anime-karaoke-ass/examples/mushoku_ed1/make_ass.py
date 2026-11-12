# -*- coding: utf-8 -*-
"""無職転生 ED1「オンリー」(大原ゆい子) 中日双语 + 振假名 卡拉OK 特效字幕. v3 流程版 (2026-11-08).

设计来源 (下游只引用上游, 不凭空发挥):
  judge/shots.json (ED1 官方无字幕版, 只覆盖 0.7-91.2s) -> judge/bar.json (5 个高光) -> judge/style.json (色板, 禁用项)
  -> judge/arc.json (每句角色, 手法, 锚点). 本文件的 PHRASES 与 arc.json 一一对应: fx 名 = arc 的手法标签.
  高光句的函数在 fx_high.py (新写). 承载与留白在 fx_carry.py.
"""
import os, sys

sys.dont_write_bytecode = True
from scene import HERE, doc, G, TH  # noqa: E402
from cards import title, prologue, interlude, outro  # noqa: E402
import fx_carry, fx_high, fx_bed  # noqa: E402

SEED = 100


def _hsv(h, s, v):
    import colorsys
    return "#%02X%02X%02X" % tuple(round(x * 255) for x in colorsys.hsv_to_rgb((h % 360) / 360, s, v))


def _lum(hx):
    f = lambda u: u / 12.92 if u <= 0.03928 else ((u + 0.055) / 1.055) ** 2.4  # noqa: E731
    r, g, b = (int(hx[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def hue_theme(h, s, lum=0.42):
    """每句一个色相 (judge/hue.json). 2026-11-09 用户复审: 旧色板只把 春山青 等提亮, 37.5s 字带均色仍是 G>R>B 的青绿灰,
    参考同帧是 R>G>B 的暖橙金. 改为按句的词意/镜头定色相, glow 在给定饱和度下只调明度到相对亮度约 0.42;
    L1/L2 暗晕 dark 取同色相 s0.85 v0.17 (参考 2E1606 一类), hi 取同色相近白."""
    if _lum(_hsv(h, s, 1.0)) < lum:          # 蓝/紫在该饱和度下到不了目标亮度: 降饱和直到够亮
        while s > 0.3 and _lum(_hsv(h, s, 1.0)) < lum:
            s -= 0.02
    lo, hi = 0.3, 1.0
    for _ in range(30):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if _lum(_hsv(h, s, mid)) < lum else (lo, mid)
    return dict(TH(_hsv(h, 0.05, 1.0), _hsv(h, s, hi), _hsv(h, 0.85, 0.17)), pale=_hsv(h, 0.22, 1.0))


import json  # noqa: E402
HUES = json.load(open(os.path.join(HERE, "judge", "hue.json"), encoding="utf-8"))["lines"]
STYLE = json.load(open(os.path.join(HERE, "judge", "style.json"), encoding="utf-8"))
# 2026-11-09 用户裁定 style.json 红蓝冲突: 两条共存, 分层用. 字身 (L2 base \\1c) 走 role_color (这个字属于谁),
# 光晕/描边 (glow/dark/pale, 高亮层 \\3c) 走 hue.json 逐句对比 (这句要和背景拉开). 之前冲突是两者混在同一个色变量里.
ROLE = {ln: r["hex"] for r in STYLE.get("role_color", []) for ln in r["lines"]}


def C(i):
    th = hue_theme(HUES[i]["hue"], HUES[i]["sat"])
    if i in ROLE:
        th["base"] = ROLE[i]
    return th


Q = dict(ent="fade", ext="wind", hl="wipe")          # 留白句: 字走得慢, 退场随风斜飘 (\\frz), B 阶段改
P = lambda i, fx, **o: dict(label="L%02d %s" % (i, fx), lines=[i], th=C(i), o=dict(dict(ent="rise", ext="rise", hl="wipe"), **o), fx=fx)  # noqa: E731

# C 阶段: 和声句 burst=False 撤回 (逐字闪光是跟手的来源, 关掉=少了逐字响应).
# 字层预设 (B 阶段, plan.md 2 漏点 8): 雪/留白句退场 wind (\\frz 斜飘), 裂纹句 glitch 入场 (\\fax 斜切) + scatter 退场
# + shake 高亮 (\\frz 抖), 和声句 flipx 进出 (\\frx 3D 翻), 守护句 spin 入场. 参考 JP 层 \\frz 858, \\fax+\\frx 240.
# Agent Notes: 卡拉OK skill 按步骤重构成 steps/NN-<key>/ 的契约 + impl 结构
# .agents/notes/implemented/process/2026-10-02-karaoke-steps-restructure.md
PHRASES = [
    P(0, "snow_write", ent="fade", ext="wind"), P(1, "snow_write", ent="fade", ext="wind"),
    P(2, "thaw_bloom", hl="bloom", ext="wind"),                                        # h1
    P(3, "chorus_float", ent="flipx", ext="flipx"), P(4, "chorus_float", ent="flipx", ext="flipx"),
    P(5, "crack_hint", ent="glitch", ext="scatter", hl="shake"), P(6, "crack_hint", ent="glitch", ext="scatter", hl="shake"),
    P(7, "ring_guard", ent="spin", hl="bloom", ext="wind"),
    P(8, "palm_cradle", ent="rise", hl="bloom"),                          # h2
    P(9, "whiteout_reach", ent="fade", hl="bloom", din=0.8, dout=1.0),    # h2
    P(10, "snow_plain", ent="fade", ext="wind"), P(11, "snow_plain", ent="fade", ext="wind"), P(12, "snow_gust", ent="fade", ext="wind"),
    P(13, "chorus_beat", ent="flipx", ext="flipx"), P(14, "chorus_float", ent="flipx", ext="flipx"),
    P(15, "crack_hint", ent="glitch", ext="scatter", hl="shake"), P(16, "crack_hint", ent="glitch", ext="scatter", hl="shake"),
    P(17, "veil_hide", ent="fade", ext="sink"), P(18, "veil_hide", ent="fade", ext="sink"),
    P(19, "tear_drop", ent="fade", ext="sink"),
    P(20, "quiet", **Q), P(21, "quiet", **Q), P(22, "quiet", **Q), P(23, "quiet", **Q),
    P(24, "mana_crack", ent="zoom", hl="shake", ext="scatter"),                           # h3
    P(25, "quiet", **Q), P(26, "quiet", **Q), P(27, "quiet", **Q), P(28, "quiet", **Q),
    P(29, "sword_cut", ent="slide", hl="shake", ext="scatter"),                          # h4
    P(30, "crack_hint", ent="glitch", ext="scatter", hl="shake"),
    P(31, "water_orb", ent="rise", hl="bloom"),                           # h5
    P(32, "echo_reach", ent="fade", hl="bloom", din=0.8, dout=1.2),
]

# Agent Notes: 卡拉OK skill 通用化  去掉单次制作的事实与清单式铺陈
# .agents/notes/implemented/process/2026-10-04-karaoke-skill-genericize.md
FXMAP = {k[3:]: v for m in (fx_carry, fx_high) for k, v in vars(m).items() if k.startswith("fx_")}

# B 阶段 (plan.md 1.7 第 1, 2 层): 承载句与高光句在主函数之后铺氛围床 + 逐字命中.
# 留白句 (quiet) 在 fx_carry.fx_quiet 里自己铺 rest 强度. 高光句强度最高, 保留 "高光往上拔" 的对比.
HIGH = {"thaw_bloom", "palm_cradle", "whiteout_reach", "mana_crack", "sword_cut", "water_orb"}


def _bedded(name, fn):
    if name == "quiet":
        return fn

    def run(f, ph, k):
        fn(f, ph, k)
        fx_bed.apply(f, ph, k, name, "high" if name in HIGH else "carrier")
    run.__name__ = fn.__name__
    run.__doc__ = fn.__doc__
    run.__wrapped__ = fn
    return run


FXMAP = {n: _bedded(n, fn) for n, fn in FXMAP.items()}

def phrases():
    return PHRASES


# Agent Notes: 卡拉OK 制作工作区统一为 dev/<番名>/<歌曲名>/，整棵屏蔽 git
# .agents/notes/implemented/process/2026-10-02-karaoke-dev-workspace.md
# Agent Notes: skill 只保留一份可复现示例，模板只留一个
# .agents/notes/implemented/process/2026-10-02-karaoke-layout-consolidation.md
def main(out):
    G.inputs(HERE, "lyrics.txt", "timing.json", "calib.json", "fixes.json")
    G.render(phrases(), FXMAP, seed=SEED)
    title(); prologue(); interlude(); outro()
    n = doc.write(out)
    print("events:", n)
    import motif_img
    motif_img.report(out)          # 缺件回退汇总 + 旁证文件 (完整版不留旁证)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "out.ass"))
