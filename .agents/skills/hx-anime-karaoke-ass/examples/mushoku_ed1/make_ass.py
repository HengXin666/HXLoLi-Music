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
import os, sys

sys.dont_write_bytecode = True   # 同目录模块不留 __pycache__ (示例目录会被整份拷走)
from scene import HERE, doc, G, TH  # noqa: E402  (scene 负责 sys.path / 字体 / 样式 / Generator)
from cards import title, prologue, interlude, outro  # noqa: E402
import fx_common, fx_verse1, fx_verse2, fx_last  # noqa: E402

# 拆分 (hard-rules 4d): 公共场景 scene.py; 共用特效 fx_common.py; 各句特效按歌曲段落 fx_verse1.py (一番) /
# fx_verse2.py (二番) / fx_last.py (末段); 卡片 cards.py. 本文件只留逐句设计表与主流程.

SEED = 100     # 特效层种子基准: 换种子 / 改一句只重抽对应 fx, 插入或重排不再波及别的句

# 每个显示句：lines / 主题 / 动画选项 / 特效函数名（场景见注释，时间为 base 视频时间轴）
# Agent Notes: 卡拉OK skill 按步骤重构成 steps/NN-<key>/ 的契约 + impl 结构
# .agents/notes/implemented/process/2026-10-02-karaoke-steps-restructure.md
PHRASES = [
    dict(label="19.5-28.5 婴儿的小脚、小手握住手指（诞生）", lines=[0], th=TH("#FFF3E6", "#FFA07A", "#3A1A12"), o=dict(ent="rise", ext="rise", hl="bloom", bright=True), fx="birth"),
    dict(label="30 夕阳下交握的手", lines=[1], th=TH("#FFF0D6", "#FF9A3C", "#2E1606"), o=dict(ent="rise", ext="sink", hl="jump"), fx="grasp"),
    dict(label="31.5 篝火 / 33 骑蜥蜴 / 36 雾", lines=[2], th=TH("#FFE6C2", "#FF6A1F", "#260C04"), o=dict(ent="slide", ext="rise", hl="wipe"), fx="campfire"),
    dict(label="37.5 瑞杰路德·红叶悬崖 / 40.5 红树 / 42 艾莉丝", lines=[3], th=TH("#FFEDE6", "#E8402E", "#2A0806"), o=dict(ent="slide", ext="wind", hl="wipe"), fx="autumn"),
    dict(label="45 拉钩约定 / 46.5 伙伴 / 48 与希露菲躺在草地", lines=[4], th=TH("#FFF6EE", "#FF5A6A", "#1E1410", base="#F4F6EE"), o=dict(ent="slide", ext="wind", hl="wipe", bright=True), fx="promise"),
    dict(label="51 鲁迪笑 / 54 魔兽 / 55.5 艾莉丝战斗", lines=[5], th=TH("#FFFFFF", "#FF2E4A", "#1E0004"), o=dict(ent="zoom", ext="scatter", hl="shake"), fx="break_red"),
    dict(label="58.5 岩石魔像 / 60 战斗 / 61.5 魔杖", lines=[6], th=TH("#FFFFFF", "#B24CFF", "#12081E"), o=dict(ent="glitch", ext="scatter", hl="wipe"), fx="glitch_violet"),
    dict(label="64.5 蓝色魔力球 / 67.5 黑影", lines=[7], th=TH("#EAF6FF", "#3FA0FF", "#04122A"), o=dict(ent="rise", ext="rise", hl="bloom"), fx="magic_guard"),
    dict(label="69 火球水球 / 70.5-72 天空魔法弧光", lines=[8], th=TH("#FFFFFF", "#FF8A3A", "#101020"), o=dict(ent="zoom", ext="rise", hl="bloom"), fx="fire_water"),
    dict(label="75 希露菲在大树下 / 76.5 夕阳", lines=[9], th=TH("#FFF4E4", "#FF9E5E", "#2A1208"), o=dict(ent="fade", ext="rise", hl="bloom", din=0.8, dout=1.0), fx="sylphie_tree"),
    dict(label="90 保罗持剑 / 91.5 塞妮丝治愈魔法", lines=[10], th=TH("#F2F6FF", "#8FB8FF", "#0A1020"), o=dict(ent="slide", ext="wind", hl="wipe"), fx="sword_heal"),
    dict(label="93 婴儿 / 94.5 天空与飞鸟", lines=[11], th=TH("#FFFFFF", "#6EC6FF", "#0C2238"), o=dict(ent="rise", ext="wind", hl="wipe", bright=True), fx="birds"),
    dict(label="94.5-97.5 天空飞鸟 → 99 家与全家", lines=[12], th=TH("#F4F8FF", "#7DB2FF", "#101A2C"), o=dict(ent="fade", ext="sink", hl="wipe", bright=True), fx="tears_theory"),
    dict(label="103.5 塞妮丝 / 105 烛光下读书 / 106.5 剑术训练", lines=[13], th=TH("#FFF1D8", "#FFB04A", "#1E1206"), o=dict(ent="slide", ext="wind", hl="ink"), fx="candle_book"),
    dict(label="109.5-112.5 洛琪希 / 114 希露菲·林间光", lines=[14], th=TH("#EEF4FF", "#4A7BFF", "#0A1230"), o=dict(ent="drop", ext="rise", hl="wipe"), fx="roxy_forest"),
    dict(label="117 麦田夕阳 / 120 艾莉丝与鲁迪", lines=[15], th=TH("#FFFBEA", "#FFB42E", "#241404"), o=dict(ent="zoom", ext="scatter", hl="shake", bright=True), fx="break_wheat"),
    dict(label="121.5 手 / 124.5 瑞杰路德 / 126 鲁迪", lines=[16], th=TH("#FFFFFF", "#1FD2C0", "#04161A"), o=dict(ent="glitch", ext="scatter", hl="wipe"), fx="glitch_teal"),
    dict(label="127.5 红色眼环 / 129 蓝色地图 / 133.5 电光", lines=[17], th=TH("#E6EEFF", "#5A6CFF", "#060A1E"), o=dict(ent="fade", ext="sink", hl="ink"), fx="hide_map"),
    dict(label="134 电光 / 135 夜城 / 136.5 魔法环 / 138 爆炎 / 139.5 青光（硬字幕已 delogo）", lines=[18, 19], th=TH("#E8FCFF", "#34D8FF", "#031018"), o=dict(ent="slide", ext="sink", hl="wipe"), fx="bolt_tears"),
    dict(label="141 艾莉丝 / 142.5 雪中的鲁迪 / 145.5 日出草原", lines=[20], th=TH("#FFFFFF", "#9ED8FF", "#0E1C2E"), o=dict(ent="rise", ext="rise", hl="jump", bright=True), fx="snow_rise"),
    dict(label="147 蓝光 / 148.5 花田 / 151.5 夹着花瓣的书", lines=[21, 22], th=TH("#FFF4FA", "#FF5AAE", "#2A0A1C"), o=dict(ent="rise", ext="wind", hl="bloom", bright=True), fx="flowers"),
    dict(label="153-162 一家人的晚餐", lines=[23], th=TH("#FFF2E0", "#FF9B4A", "#241006"), o=dict(ent="flipx", ext="flipx", hl="wipe"), fx="dinner_flip"),
    dict(label="163.5 洛琪希水魔法 / 168 洛琪希与鲁迪", lines=[24, 25], th=TH("#F0FCFF", "#2EB8FF", "#021426"), o=dict(ent="zoom", ext="scatter", hl="shake"), fx="break_water"),
    dict(label="168-175 摸头", lines=[26], th=TH("#FFF2F4", "#FF7A9A", "#2A0A12"), o=dict(ent="fade", ext="rise", hl="bloom"), fx="embrace"),
    dict(label="177 上课 / 178.5 鲁迪 / 180 起遮幅", lines=[27], th=TH("#F4FFF6", "#9EE6B8", "#0A1A12"), o=dict(ent="slide", ext="wind", hl="wipe"), fx="eraser"),
    dict(label="180-189 遮幅：夕阳下的手 / 保罗与塞妮丝 / 篝火", lines=[28], th=TH("#FFF6E0", "#FFB43C", "#241404"), o=dict(ent="fade", ext="sink", hl="bloom"), fx="overflow"),
    dict(label="189-195 雾 / 瑞杰路德 / 艾莉丝 / 拉钩 / 暗林 / 骑士", lines=[29], th=TH("#EEF0F6", "#9A8CFF", "#0C0A18"), o=dict(ent="slide", ext="scatter", hl="shake"), fx="chains"),
    dict(label="195-201 暗青色森林 / 骑士", lines=[30], th=TH("#FFFFFF", "#2EF2E0", "#03141A"), o=dict(ent="glitch", ext="scatter", hl="wipe"), fx="glitch_cyan"),
    dict(label="201 洛琪希持杖 / 204 火球 / 205.5 天空弧光 / 208.5 塞妮丝拥抱鲁迪", lines=[31], th=TH("#EEF6FF", "#4AA0FF", "#050E22"), o=dict(ent="rise", ext="rise", hl="bloom", stg_out=0.02), fx="finale"),
    dict(label="210-213 洛琪希微笑 / 216 鲁迪在石墙后", lines=[32], th=TH("#FFF8E8", "#6F9CFF", "#0A1024"), o=dict(ent="fade", ext="rise", hl="bloom", din=0.8, dout=1.2), fx="only_you"),
]


# Agent Notes: 卡拉OK skill 通用化  去掉单次制作的事实与清单式铺陈
# .agents/notes/implemented/process/2026-10-04-karaoke-skill-genericize.md
FXMAP = {k[3:]: v for m in (fx_common, fx_verse1, fx_verse2, fx_last) for k, v in vars(m).items() if k.startswith("fx_")}


# ======================================================================== 主流程
# Agent Notes: 卡拉OK 制作工作区统一为 dev/<番名>/<歌曲名>/，整棵屏蔽 git
# .agents/notes/implemented/process/2026-10-02-karaoke-dev-workspace.md
# Agent Notes: skill 只保留一份可复现示例，模板只留一个
# .agents/notes/implemented/process/2026-10-02-karaoke-layout-consolidation.md
def main(out):
    # 出入场规划 / 逐句渲染 / band 登记 / 清单 (out.manifest.json) 全部由 Generator 负责.
    # 显示窗口规则见 assfx/layer/gen.py 模块头; 字层种子 LY_SEED 与特效种子 SEED 解耦.
    G.inputs(HERE, "lyrics.txt", "timing.json", "calib.json", "fixes.json")
    G.render(PHRASES, FXMAP, seed=SEED)
    title(); prologue(); interlude(); outro()
    n = doc.write(out)
    print("events:", n)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "out/only_ed1.ass"))
