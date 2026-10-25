# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""karetpl 自检：拿一份**带模板的成品**，看展开结果与原文件里的事件是否逐字节一致。

用法:
    hx-karaoke verify.py <成品.ass> [--line 6.37] [--window 0.02]

它做的事：
  1. 读成品的 Comment（程序）与 Dialogue（作者跑出来的结果）
  2. 用 karetpl 执行那段程序，取指定起始时刻的事件
  3. 与原文件**同一时刻**的事件做集合比对，报"逐字节相同 N/M"

这是本包唯一有意义的验收方式：**执行同一份程序，能否得到同一批事件**。
"看起来像"不算  颜色对不上、时间差 10ms 都会被这里抓出来。
"""
import argparse
import re
import sys

from karetpl import Expander, Metrics, Program


class FontMetrics(Metrics):
    """$scenter 用字体真实 advance（该成品实测 75.14 = fs70 + spacing5 + 0.14）。"""

    def __init__(self, adv=None):
        super().__init__(center_advance=adv)


def collect(path, start, window, styles):
    """原文件里起始时刻落在窗口内的事件文本。"""
    out = set()
    for raw in open(path, encoding="utf-8-sig", errors="replace"):
        if not raw.startswith("Dialogue:"):
            continue
        f = raw.split(",", 9)
        if len(f) < 10:
            continue
        h, m, r = f[1].split(":")
        t = int(h) * 3600 + int(m) * 60 + float(r)
        if abs(t - start) <= window and (not styles or f[3].startswith(tuple(styles))):
            out.add(f[9].strip())
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ass")
    ap.add_argument("--line", type=float, default=None, help="源行起始秒（默认第一句）")
    ap.add_argument("--window", type=float, default=0.02, help="比对窗口秒")
    ap.add_argument("--adv", type=float, default=None, help="$scenter 的推进量")
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()

    prog = Program.from_file(a.ass)
    if not prog.templates:
        sys.exit("这份 ASS 里没有 Comment 模板，无法验证（它可能是手写的）")
    line = None
    if a.line is not None:
        line = next((l for l in prog.karaoke if abs(l.start - a.line) < 0.05), None)
    line = line or prog.karaoke[0]

    exp = Expander(prog, metrics=FontMetrics(a.adv), seed=a.seed)
    got = {e.text.strip() for e in exp.expand_line(line)}
    # 原文件里该句展开结果的起始时刻（retime 会前后移动，用整段扫）
    want = collect(a.ass, line.start, max(a.window, 0.0), None)
    # retime 会把事件移到行首前，所以再扫一遍覆盖窗口
    for shift in (-0.30, 0.30, -0.03, 0.03):
        want |= collect(a.ass, line.start + shift, 0.01, None)

    hit = len(got & want)
    print(f"源行 {line.start:.2f}-{line.end:.2f}s  {line.style}")
    print(f"  原文件同段事件 {len(want)} 条 / 展开 {len(got)} 条")
    print(f"  逐字节相同 {hit}")
    if exp.warnings:
        print(f"  警告 {len(exp.warnings)} 条:")
        for w in exp.warnings[:3]:
            print("     ", w[:110])
    return 0 if hit else 1


if __name__ == "__main__":
    sys.exit(main())
