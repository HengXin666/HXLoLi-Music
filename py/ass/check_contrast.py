#!/usr/bin/env python3
"""配色可读性检查器。

用法:
  python3 check_contrast.py --fill FFFFFF --outline 91276F --bg 0B1016
  python3 check_contrast.py --image shots/frame.png

判据来自 WCAG 2.1 (W3C 原文):
  大字号 >= 3:1   普通字号 >= 4.5:1
本项目的额外门槛 (见 RULES.md):
  填充/描边 >= 4.5:1    暗态填充/背景 >= 3:1
"""
import argparse, sys
import numpy as np


def lum(c):
    c = np.array(c, dtype=float) / 255.0
    c = np.where(c <= 0.03928, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return float(0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2])


def R(a, b):
    l1, l2 = lum(a), lum(b)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def hex2rgb(h, ass=False):
    """Parse a colour.

    ass=False (default) reads a plain #RRGGBB web hex, which is what a designer
    types.  ass=True reads ASS override order &HBBGGRR&, where the FIRST byte
    pair is blue.  Mixing the two silently swaps red and blue: 0B1016 as web
    hex is RGB(11,16,22), as ASS it is RGB(22,16,11).  Every contrast number
    derived from a mis-parsed background is then wrong, which is exactly how an
    earlier run of this checker "passed" a palette nobody could read.
    """
    # NB: never strip with lstrip("0x") -- it is a character set, not a prefix,
    # so "0B1016" loses its leading "0B" and every later parse is garbage.
    h = h.strip()
    if h.startswith("#"):
        h = h[1:]
    elif h[:2].lower() == "0x":
        h = h[2:]
    if len(h) == 8:
        h = h[-6:]
        ass = True
    if ass:
        # &HBBGGRR& -> R=h[4:6] G=h[2:4] B=h[0:2]
        return (int(h[4:6], 16), int(h[2:4], 16), int(h[0:2], 16))
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def check_pair(name, a, b, need):
    v = R(a, b)
    ok = "PASS" if v >= need else "FAIL"
    print("  [%s] %-22s %6.2f:1   (needs >= %.1f)" % (ok, name, v, need))
    return v >= need


def check_image(path):
    """Agent Notes
    .agents/notes/implemented/process/2026-09-27-kfx-readability-gate.md
    """
    from PIL import Image
    # Agent Notes: KFX 可读性规则与对比度门禁
    # 
    a = np.asarray(Image.open(path).convert("RGB")).astype(int)
    q = (a // 16 * 16).reshape(-1, 3)
    from collections import Counter
    cnt = Counter(map(tuple, q))
    print("  %s 里出现最多的颜色:" % path)
    for c, n in cnt.most_common(10):
        if n >= 150:
            print("     RGB%-16s %7d px   亮度 %.3f" % (str(c), n, lum(c)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fill")
    ap.add_argument("--outline")
    ap.add_argument("--bg", default="0B1016")
    ap.add_argument("--ghost", help="暗态填充色 (整行先出现时用)")
    ap.add_argument("--image")
    a = ap.parse_args()
    ok = True
    if a.fill:
        fill, bg = hex2rgb(a.fill), hex2rgb(a.bg, ass=True)
        out = hex2rgb(a.outline) if a.outline else None
        print("配色检查 (fill=%s outline=%s bg=%s)" % (a.fill, a.outline, a.bg))
        ok &= check_pair("填充 / 背景", fill, bg, 4.5)
        if out:
            ok &= check_pair("填充 / 描边", fill, out, 4.5)
        if a.ghost:
            ok &= check_pair("暗态填充 / 背景", hex2rgb(a.ghost), bg, 3.0)
    if a.image:
        check_image(a.image)
    print()
    print("结果:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
