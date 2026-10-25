#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""门禁：把这套流程里**不许跳、不许悄悄降级**的步骤变成可失败的检查。

为什么要有它: 本 skill 的流程表里，"人工校时""来源证据""设定考据"这类步骤最容易
被"时间紧、先出个版本"绕过  绕过之后所有下游产物都还在、也都还"看起来正常"，
只有最终的片子不对味，而那时候已经没人回头查是哪一步塌的。所以判据必须前置成文件：

  必须存在的文件            为什么
  lyrics.source.json        歌词是从哪来的（网络 or 人工听写）。缺它 = 无法判断歌词可信度
  anime.background.json     番剧设定是否被查过。缺它 = 特效设计没有语境，容易退化成通用图形
  timing.json               人工校时的最终产物（不是 timing_auto.json）
  fixes.json                人工校时的记录（哪怕是空 {}，也要显式存在表示"看过频谱了"）
  calib.json                排版实测（注音位置不能凭感觉）
  offset.json               网络歌词时间轴 → 这份视频的**语音校准**结果（不许靠画面截图）
  review/health.txt         时间轴体检的判定行（CTC塌缩 0 处 / 句内间奏 0 处）。
                            它原先只打印不拦截，实测有工程带着 2 处塌缩交付、字幕慢了 20 秒  所以现在查判定行

以及两条**可证伪**的强度判据（不是"文件在就行"）:
  * timing.json 的音拍数 == lyrics.txt 的音拍数（对不上说明用了别的歌词）
  * timing.json 相对 timing_auto.json 必须**发生过修正**（全等 = 没做人工校时；
    或者按 --no-auto 声明本次跳过自动对齐、直接手工标）
  * lyrics.txt 是否被补过注音（含 [漢|よみ] 的行占比）

用法:
  hx-karaoke check_gates.py --project proj [--min-ruby 0.8] [--stage all|design|render]
退出码非 0 = 有未通过的强制项。--stage design 只查设计前的门禁（source/background/lyrics），
--stage render 追加时间轴与排版门禁。
"""
import argparse, json, os, re, sys

OK, BAD, WARN = "PASS", "FAIL", "WARN"
RUBY = re.compile(r"\[[^\]|]+\|")


# Agent Notes: 特效母题必须指向带来源计数的番剧元素表; 语音校准的判据要区分「检出噪声」与「真剪辑差异」
# 
# 
def load(p):
    """Agent Notes
    .agents/notes/implemented/process/2026-10-02-karaoke-elements-table-gate.md
    .agents/notes/implemented/process/2026-10-02-karaoke-offset-verdict.md
    """
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return None


# Agent Notes: 特效设计维度从 3 格扩到 15 格, 并让门禁真的查它
# 
def parse_lines(path):
    """
    .agents/notes/implemented/process/2026-10-03-karaoke-design-15-cells.md
-> (行数, 带注音的行数, 音拍数)。音拍数用 skill 自己的解析器保证一致。"""
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from assfx.base.lyrics import load as load_lyrics
    rows = [x for x in open(path, encoding="utf-8") if x.strip() and not x.lstrip().startswith("#")]
    ruby = sum(1 for x in rows if RUBY.search(x))
    try:
        lines = load_lyrics(path)
    except Exception as exc:
        return len(rows), ruby, None, "解析失败: %s" % exc
    mora = sum(len(u["morae"]) for ln in lines for u in ln["units"])
    return len(rows), ruby, mora, None

import argparse
import sys

from gate.gates_meta import (BAD, OK, WARN, check_background, check_brief, check_design,   # noqa: F401
                             check_elements, check_notes, check_prose, check_source)
from gate.gates_render import (check_calib, check_coverage, check_health, check_lyrics,   # noqa: F401
                              check_offset, check_timing)


def main():
    """Agent Notes
    .agents/notes/implemented/process/2026-10-01-karaoke-hard-gates-script.md
    .agents/notes/implemented/process/2026-10-01-karaoke-lyrics-source-ladder.md
    .agents/notes/implemented/process/2026-10-02-karaoke-lyrics-timing-authority.md
    .agents/notes/implemented/process/2026-10-02-karaoke-steps-restructure.md
    """
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=".")
    ap.add_argument("--stage", choices=["all", "design", "render"], default="all")
    ap.add_argument("--min-ruby", type=float, default=0.8, help="带振假名的行占比下限")
    ap.add_argument("--min-chars", type=int, default=6)
    ap.add_argument("--max-ambient", type=float, default=0.35,
                    help="设计表里「氛围句」占比的上限；指不到番剧元素时不许用氛围句兜底")
    ap.add_argument("--strict-design", action="store_true",
                    help="把 15 格设计表的缺项从 WARN 升为 FAIL（新工程用；旧格式的表还没迁移时保持 WARN）")
    a = ap.parse_args()
    # Agent Notes: 逐字时间以网络逐字歌词为权威，CTC 只用于定整体平移
    # 
    proj = a.project
    res = []
    check_source(proj, res)
    check_background(proj, res, a.min_chars)
    check_notes(proj, res)
    # Agent Notes: 用 check_gates.py 把卡拉OK 流程的必做步骤变成可失败的检查; 歌词来源定级  一律从网络取，时间轴校准走语音; 卡拉OK skill 按步骤重构成 steps/NN-<key>/ 的契约 + impl 结构
    # 
    # 
    # 
    mora = check_lyrics(proj, res, a.min_ruby)
    if a.stage in ("all", "design", "render"):
        check_brief(proj, res)
        check_prose(proj, res)
        check_elements(proj, res, a.max_ambient)
        check_design(proj, res, a.strict_design)
    if a.stage in ("all", "render"):
        check_offset(proj, res)
        check_timing(proj, res, mora)
        check_coverage(proj, res)
        check_health(proj, res)
        check_calib(proj, res)

    bad = [r for r in res if r[0] == BAD]
    for st, name, why in res:
        print("%-4s %-24s %s" % (st, name, why))
    print("\n%s: %d 项通过, %d 项警告, %d 项失败 (stage=%s, proj=%s)"
          % ("FAILED" if bad else "PASSED", len([r for r in res if r[0] == OK]),
             len([r for r in res if r[0] == WARN]), len(bad), a.stage, proj))
    if bad:
        print("\n硬性要求没满足。这些步骤不许跳：见 SKILL.md 的「强制门禁」一节。")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
