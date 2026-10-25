#!/usr/bin/env python3
"""量测一份成品里的运动是"真移动"还是"逐帧打印"。

背景: 粒子流派的核心机制是"同点 move 残影法"  \\move(X,Y,X,Y,t1,t2), 起点等于终点,
位置根本不动, 靠大量静止点错开时间连成轨迹。ASS 没有沿路径运动的原生语法。

用法: python3 move_probe.py <字幕.ass>
输出: 同点 move 占比。比例高 = 运动是打印出来的, 不是动出来的。
"""
import re
import sys

BS = chr(92)
MOVE = re.compile(BS + BS + r"move\(([-\d.]+),([-\d.]+),([-\d.]+),([-\d.]+)(?:,([-\d.]+),([-\d.]+))?\)")


# Agent Notes: HXLoLi-Music 接入 Agent Notes v2
# 
def main() -> int:
    """Agent Notes
    .agents/notes/implemented/process/2026-10-08-repository-agent-notes-v2-adoption.md
    """
    path = sys.argv[1]
    same = total = with_alpha = 0
    dur = []
    for line in open(path, encoding="utf-8-sig", errors="replace"):
        if not line.startswith("Dialogue:"):
            continue
        for m in MOVE.finditer(line):
            total += 1
            x0, y0, x1, y1 = (float(m.group(i)) for i in range(1, 5))
            if abs(x0 - x1) < 0.01 and abs(y0 - y1) < 0.01:
                same += 1
            if BS + "alpha" in line:
                with_alpha += 1
            if m.group(5) and m.group(6):
                dur.append(float(m.group(6)) - float(m.group(5)))
    if not total:
        print("没有 \\move")
        return 0
    print("move 总数 %d" % total)
    print("同点 move %d (%.1f%%)" % (same, same / total * 100))
    print("带 alpha 的事件 %d (%.1f%%)" % (with_alpha, with_alpha / total * 100))
    if dur:
        dur.sort()
        print("残影时长 中位 %.2f  范围 %.2f - %.2f" % (dur[len(dur)//2], dur[0], dur[-1]))
    print()
    print("判定: " + ("逐帧打印式 (同点残影法)" if same / total > 0.5 else "真位移"))
    return 0


if __name__ == "__main__":
    sys.exit(main())