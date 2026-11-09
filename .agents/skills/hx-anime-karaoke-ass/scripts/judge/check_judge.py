#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""判断档与剧本产物的判据. 产物在 proj/judge/, 格式见 shared/judge-formats.md.

  hx-karaoke judge/check_judge.py --project proj                # 全部
  hx-karaoke judge/check_judge.py --project proj --stage arc    # 只查一份 (上游产物只读不判)
  hx-karaoke judge/check_judge.py --project proj --skeleton     # 打印每句 line + text, 填表时复制

stage 顺序: shots -> visual -> bar -> style -> arc -> concepts.
退出码: 0 = 没有 FAIL; 1 = 有 FAIL; 2 = 工程缺基础文件 (lyrics.txt / timing.json).
只查能机械证伪的项. 写得好不好由自审盲审判.
"""
import argparse, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from judge import c_arc, c_bar, c_concepts, c_shots, c_style, c_visual   # noqa: E402
from judge.common import Res, Song, skeleton                                # noqa: E402

STAGES = ("shots", "visual", "bar", "style", "arc", "concepts")


# Agent Notes: v3 判断链: 六组判据
# .agents/notes/implemented/feature/2026-11-09-karaoke-fx-gate-studio.md
def run(proj, stage="all"):
    """返回 Res. stage 之外的产物也读 (给下游当上下文), 但判据结果丢弃."""
    song = Song(proj)
    res, quiet = Res(), Res()
    pick = lambda s: res if stage in ("all", s) else quiet    # noqa: E731
    shots = c_shots.check(song, pick("shots"))
    visual = c_visual.check(song, pick("visual"))
    bar = c_bar.check(song, pick("bar"), shots)
    if stage in ("all", "style"):
        c_style.check(song, res, shots)
    arc = c_arc.check(song, pick("arc"), bar, visual, shots) if stage in ("all", "arc", "concepts") else None
    if stage in ("all", "concepts"):
        c_concepts.check(song, res, bar, arc)
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True)
    ap.add_argument("--stage", choices=("all",) + STAGES, default="all")
    ap.add_argument("--skeleton", action="store_true")
    ap.add_argument("--quiet", action="store_true", help="只打印 WARN 与 FAIL")
    a = ap.parse_args()
    for f in ("lyrics.txt", "timing.json"):
        if not os.path.exists(os.path.join(a.project, f)):
            print("FAIL 工程缺 %s, 判断档要在机械档之后做" % f)
            sys.exit(2)
    if a.skeleton:
        skeleton(a.project)
        return
    res = run(a.project, a.stage)
    res.show(a.quiet)
    n = {k: sum(1 for r in res.rows if r[0] == k) for k in ("PASS", "WARN", "FAIL")}
    print("\n%d 项通过, %d 项警告, %d 项失败 (stage=%s)" % (n["PASS"], n["WARN"], n["FAIL"], a.stage))
    sys.exit(1 if n["FAIL"] else 0)


if __name__ == "__main__":
    main()
