#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""作品设计圣经判据. 产物在 proj/bible/, 格式见 steps/3-anime-bg/11-design-bible/impl/formats.md.

  hx-karaoke judge/check_bible.py --project proj                    # 全部
  hx-karaoke judge/check_bible.py --project proj --stage bible      # 第 11 步: 符号 / 角色 / 名场面 / 逐句对位
  hx-karaoke judge/check_bible.py --project proj --stage directions # 第 39 步: 整曲方向 + 换番名检查
  hx-karaoke judge/check_bible.py --project proj --stage landing    # 第 49 步之后: 落地追溯 + 盲审
  hx-karaoke judge/check_bible.py --project proj --trace            # 打印 符号 -> 来源 -> fx -> 句 的追溯链

退出码: 0 = 没有 FAIL; 1 = 有 FAIL; 2 = 工程缺 lyrics.txt / timing.json.
"""
import argparse, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from judge import blind_bible, c_bible, c_directions   # noqa: E402
from judge.bible_io import Bible                        # noqa: E402
from judge.common import Res, Song                      # noqa: E402

STAGES = ("bible", "directions", "landing")


def run(proj, stage="all"):
    """返回 (Res, 追溯链). stage 之外的结果丢弃, 但上游仍读 (下游要用选定方向)."""
    song, bible = Song(proj), Bible(proj)
    res, quiet = Res(), Res()
    pick = lambda s: res if stage in ("all", s) else quiet    # noqa: E731
    c_bible.check(bible, song, pick("bible"))
    chosen = c_directions.check_directions(bible, song, pick("directions"))
    chain = []
    if stage in ("all", "landing"):
        chain = c_directions.check_landing(bible, song, res, chosen)
        blind_bible.gate(proj, res)
    return res, chain


def trace(bible, chain):
    for sid, fx, ls, srcs, hits in chain:
        s = bible.symbols[sid]
        print("%-22s u=%d  %s  句%s  来源: %s%s" % (sid, bible.unique(sid), fx, ls, " / ".join(srcs),
                                                    "" if hits is None else "  out.ass 命中 %d" % hits))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True)
    ap.add_argument("--stage", choices=("all",) + STAGES, default="all")
    ap.add_argument("--trace", action="store_true")
    ap.add_argument("--quiet", action="store_true", help="只打印 WARN 与 FAIL")
    a = ap.parse_args()
    for f in ("lyrics.txt", "timing.json"):
        if not os.path.exists(os.path.join(a.project, f)):
            print("FAIL 工程缺 %s" % f)
            return 2
    res, chain = run(a.project, "landing" if a.trace else a.stage)
    if a.trace:
        trace(Bible(a.project), chain)
        return 0
    res.show(a.quiet)
    n = {k: sum(1 for r in res.rows if r[0] == k) for k in ("PASS", "WARN", "FAIL")}
    print("\n%d 项通过, %d 项警告, %d 项失败 (stage=%s)" % (n["PASS"], n["WARN"], n["FAIL"], a.stage))
    return 1 if n["FAIL"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
