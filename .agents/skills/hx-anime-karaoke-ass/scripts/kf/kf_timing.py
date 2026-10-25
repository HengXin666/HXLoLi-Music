#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "numpy",
# ]
# ///
"""逐字权威时间轴(kf): 用 LDDC 抓网络逐字歌词, 与本地音频的行首锚点融合, 产出音拍级 timing.

## 为什么要有这条通道(实测 2026-10-02)

`align_ctc.py`(wav2vec2 平假名 + CTC Viterbi)在**长音与间奏处会塌缩**: 它把整整一段
拖长/间奏全算给最后一个音拍, 其后的音拍起点被整体顺延. 同工程 36 行里 8 行如此,
最坏一行「教えてくれた」被判成 22.73s 跨度  真值 1.50s, 15.2 倍.

## 结论: 分工

| 量 | 来源 | 理由 |
|---|---|---|
| 句内相对形状 | LDDC 逐字(网络) | 权威. CTC 在这里会塌缩, 且塌缩不可从 CTC 自身察觉 |
| 整体平移 | CTC 行首(本地音频) | 唯一由**这份视频**决定的东西; LDDC 的时间轴是别份音源的 |

实测效果(字级, 对作者手工锚点): MAE 0.0322s vs 纯 CTC 0.2595s, 8.1 倍.

## 用法

    # 1) 抓逐字(--lddc 指向 HX-Music 的 pyTool 目录, 即 LDDC 包所在)
    hx-karaoke kf_timing.py fetch --title "<曲名>" --artist "<艺人>" --project proj --source QM

    # 2) 融合(缺 kf.json 时自动退回 CTC, 不报错)
    hx-karaoke kf_timing.py align --project proj --auto timing_auto.json --out timing_kf.json

    # 3) 复核
    hx-karaoke kf_timing.py verify --project proj --a timing_kf.json --b timing.json --top 20

子命令的实现分别在 kf/fetch.py / kf/align.py / kf/verify.py.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from kf.align import cmd_align
from kf.fetch import LDDC_SOURCES, cmd_fetch
from kf.verify import cmd_verify


# Agent Notes: 逐字源与歌词行的配对要「就近取用」，句内形状不可信时回退本地
# 
def main():
    """Agent Notes
    .agents/notes/implemented/process/2026-10-02-karaoke-kf-line-pairing.md
    .agents/notes/implemented/process/2026-10-02-karaoke-lyrics-timing-authority.md
    """
    ap = argparse.ArgumentParser(description="LDDC 逐字 + 本地行首锚点 -> 音拍级时间轴")
    sub = ap.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fetch", help="抓网络逐字歌词 -> kf.json")
    f.add_argument("--lddc", default=os.environ.get("HX_LDDC_PATH", "~/Loli/code/HX-Music/pyTool"))
    f.add_argument("--title", default=""); f.add_argument("--artist", default="")
    f.add_argument("--song-id", default="", help="从打印的候选列表里挑；不给取第一条")
    f.add_argument("--source", default="QM", choices=LDDC_SOURCES)
    f.add_argument("--lang", default="orig")
    f.add_argument("--project", default="."); f.add_argument("--out", default="kf.json")
    f.set_defaults(fn=cmd_fetch)

    # Agent Notes: 逐字时间以网络逐字歌词为权威，CTC 只用于定整体平移
    # 
    al = sub.add_parser("align", help="融合 -> timing_kf.json")
    al.add_argument("--project", default=".")
    al.add_argument("--lyrics", default="lyrics.txt")
    al.add_argument("--auto", default="timing_auto.json", help="提供本地行首锚点的 timing")
    al.add_argument("--kf", default="kf.json")
    al.add_argument("--out", default="timing_kf.json")
    al.add_argument("--report", default="review/kf-report.md")
    al.add_argument("--collapse-ratio", type=float, default=1.45, help="本地跨度/逐字跨度 超过即判塌缩")
    al.add_argument("--min-lines", type=int, default=5, help="估偏移所需的最少非塌缩行")
    al.add_argument("--medfilt-trigger", type=float, default=2.0,
                    help="单行偏移超过此秒数即算「结构性漂移」的候选（默认 2.0）")
    al.add_argument("--medfilt-frac", type=float, default=0.05,
                    help="「结构性漂移」的行占比超过此值才启用中位滤波（默认 0.05）。"
                         "实测：抖动小的工程该占比 0%%（滤波有害 0.031->0.107），有前句塌缩推移的 10%%（滤波有益，纠 4.6s）")
    al.add_argument("--medfilt", type=int, default=5,
                    help="逐行偏移的中位滤波窗长（奇数）。用邻行共识吸收「前句塌缩把后句推后」；"
                         "实测窗 3 在 3s 级漂移上不够、窗 5 起有效。给 1 关闭")
    al.add_argument("--outlier", type=float, default=0.9,
                    help="某行本地行首相对全局偏移偏离超过此秒数才单独用它的本地锚点。"
                         "实测调小反而更差（0.5 -> MAE 0.138s vs 0.9 -> 0.031s），别降低")
    al.add_argument("--shape-min-quality", type=float, default=0.5,
                    help="LDDC 句内形状的可信下限（差分 >40ms 的占比）；低于它回退到本地 CTC 形状")
    al.add_argument("--slack", type=float, default=0.45, help="行窗口前后容许的溢出秒数")
    al.add_argument("--no-clamp", dest="clamp", action="store_false", help="不做行窗口夹取")
    al.set_defaults(fn=cmd_align, clamp=True)

    v = sub.add_parser("verify", help="两份时间轴对比")
    v.add_argument("--project", default="."); v.add_argument("--a", required=True); v.add_argument("--b", required=True)
    v.add_argument("--thr", type=float, default=0.15); v.add_argument("--top", type=int, default=20)
    v.set_defaults(fn=cmd_verify)

    a = ap.parse_args()
    sys.exit(a.fn(a) or 0)


if __name__ == "__main__":
    main()
