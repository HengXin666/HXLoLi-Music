#!/usr/bin/env python3
"""可读性门禁: 算填充/描边/背景/幽灵态四者之间的 WCAG 2.1 对比度并判门。

用法:
    python3 contrast_check.py --fill FFFFFF --outline 695A37 --bg 0B1016 [--ghost 7B7B7B]
    python3 contrast_check.py --ass 字幕.ass --bg 0B1016      # 直接从样式表读

接受两种色写法:
    #RRGGBB (网页) / RRGGBB / &HBBGGRR& 或 &HAABBGGRR& (ASS)
注意 ASS 是 BBGGRR 逆序, 写错会让红蓝对调而**所有对比度数字静默失真**。
本脚本对同一输入同时算两种色序并给出警告, 避免这个坑。

退出码 0 = 全部门通过; 1 = 有门未过; 2 = 参数错。
"""
from __future__ import annotations
import argparse
import re
import sys

# 门限来自 KFX-RULES.md (WCAG 2.1 + 本项目实测教训)
GATES = [
    ("填充/描边", 4.5, "轮廓必须与填充拉开; 浅色描边一律不合格"),
    ("填充/背景", 12.0, "底板要压得够暗, 白字才立得住"),
    ("幽灵态/背景", 3.0, "整行未点亮时也必须看得见"),
]


def rel_lum(rgb) -> float:
    c = [v / 255.0 for v in rgb]
    c = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def contrast(a, b) -> float:
    la, lb = rel_lum(a), rel_lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def parse_color(s: str):
    """返回 (RGB, 是否被当作 ASS 色序)。"""
    t = s.strip()
    if t.startswith("&H"):
        h = t[2:].rstrip("&")
        if len(h) == 6:                     # BBGGRR
            bb, gg, rr = h[0:2], h[2:4], h[4:6]
            return (int(rr, 16), int(gg, 16), int(bb, 16)), True
        if len(h) == 8:                     # AABBGGRR
            aa, bb, gg, rr = h[0:2], h[2:4], h[4:6], h[6:8]
            return (int(rr, 16), int(gg, 16), int(bb, 16)), True
        raise ValueError(f"无法解析 ASS 色: {s}")
    h = t.lstrip("#")
    if len(h) != 6:
        raise ValueError(f"无法解析色值 (需要 6 位或 &H 形式): {s}")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)), False


def hex_of(rgb) -> str:
    return "#%02X%02X%02X" % tuple(rgb)


DRAW_RE = re.compile(r"\\p[1-9]")


def read_styles(path: str):
    """读取 ASS 的样式, 并标出每个样式是否为「文本样式」。

    为什么要区分: 绘图样式的填充色就是它画出来的颜色, 描边色对它没有意义。
    对绘图样式套用「填充/描边必须拉开」会稳定误报  实测踩过: 装饰层被判 FAIL,
    而它本来就不该受那条门限约束。判据是「该样式有没有被不含绘图标签的事件用过」。
    """
    styles, used_as_text = {}, set()
    for line in open(path, encoding="utf-8-sig", errors="replace"):
        if line.startswith("Style:"):
            f = line[6:].strip().split(",")
            if len(f) < 8:
                continue
            name = f[0].strip()
            try:
                fill, _ = parse_color(f[3].strip())
                outl, _ = parse_color(f[5].strip())
                back, _ = parse_color(f[6].strip())
            except ValueError:
                continue
            styles[name] = (fill, outl, back)
        elif line.startswith("Dialogue:"):
            f = line[9:].split(",", 9)
            if len(f) < 10:
                continue
            if not DRAW_RE.search(f[9]):
                used_as_text.add(f[3].strip())
    return [(n, *v, n in used_as_text) for n, v in styles.items()]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fill"); ap.add_argument("--outline")
    ap.add_argument("--bg"); ap.add_argument("--ghost")
    ap.add_argument("--ass", help="从 ASS 样式表读取, 与 --fill 等互斥")
    ap.add_argument("--style", help="只检查该样式名 (默认全部)")
    a = ap.parse_args()

    jobs = []
    if a.ass:
        for name, fill, outl, back, is_text in read_styles(a.ass):
            if a.style and name != a.style:
                continue
            jobs.append((name, fill, outl, back, None, is_text))
    else:
        if not (a.fill and a.outline and a.bg):
            print("需要 --fill/--outline/--bg, 或用 --ass", file=sys.stderr)
            return 2
        fill, _ = parse_color(a.fill); outl, _ = parse_color(a.outline); bg, _ = parse_color(a.bg)
        ghost = parse_color(a.ghost)[0] if a.ghost else None
        jobs.append(("(命令行)", fill, outl, bg, ghost, True))

    if not jobs:
        print("没有可检查的样式", file=sys.stderr)
        return 2

    failed = False
    for name, fill, outl, bg, ghost, is_text in jobs:
        print(f"\n=== 样式 {name} " + ("(文本)" if is_text else "(仅绘图, 只查亮度)") + " ===")
        print(f"  填充 {hex_of(fill)}   描边 {hex_of(outl)}   背景 {hex_of(bg)}"
              + (f"   幽灵 {hex_of(ghost)}" if ghost else ""))
        # 绘图样式只判「它画出来的颜色」够不够显眼, 不判填充/描边的分离度。
        pairs = []
        if is_text:
            pairs.append(("填充/描边", contrast(fill, outl), 4.5, GATES[0][2]))
            pairs.append(("填充/背景", contrast(fill, bg), 12.0, GATES[1][2]))
            if ghost:
                pairs.append(("幽灵态/背景", contrast(ghost, bg), 3.0, GATES[2][2]))
        else:
            pairs.append(("绘图色/背景", contrast(fill, bg), 3.0, "装饰图元至少要能看出来"))
        for label, val, need, why in pairs:
            ok = val >= need
            failed |= not ok
            print(f"  {label:<12} {val:6.2f}:1  门限 {need:>5.1f}  {'PASS' if ok else 'FAIL'}   {why if not ok else ''}")
        # 描边亮度硬上限: 要让白填充有清晰轮廓, 描边亮度须 <= 0.1833。
        # 只对文本样式适用  绘图样式没有"轮廓"这个概念。
        if is_text:
            ol = rel_lum(outl)
            print(f"  描边亮度      {ol:.4f}  上限 0.1833  "
                  f"{'OK' if ol <= 0.1833 else '超限: 描边比中灰亮, 轮廓会糊'}")
            if ol > 0.1833:
                failed = True

    print()
    print("总判定: " + ("FAIL" if failed else "PASS"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
