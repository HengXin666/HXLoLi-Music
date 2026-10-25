#!/usr/bin/env python3
r"""归一化 KFX 生成器: 从「句 + 逐字时间」出发, 产出全程落在固定安全区内的 ASS。

这条链路是本 skill 的核心可交付件, 它把三件事一次做完:
  1. 归一化   所有 \pos 与绘图路径都约束在 SAFE 矩形内 (裁剪退化成常量);
  2. 整行先出现再逐字点亮  每字一条事件、时长相同、位置全片不变;
  3. 画面驱动  描边色取自 MV 主色的暗色簇 (见 scene_analysis.py), 母题按语义挑.

用法:
    python3 build_normalized.py --sentences sentences.json --safe X0,Y0,X1,Y1 \
        --out out.ass [--font "Noto Sans CJK JP"] [--outline 375A69] [--bg 0D1924]

sentences.json 形如:
    [ {"t0":3.07, "t1":8.89, "jp":"人の儚さを断つため"}, ... ]
"""
from __future__ import annotations
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from motifs import LIBRARY, pick, path_of   # noqa: E402


def ts(t: float) -> str:
    return "%d:%02d:%05.2f" % (int(t // 3600), int((t % 3600) // 60), t % 60)


def ass_color(rgb_hex: str, alpha: str = "00") -> str:
    h = rgb_hex.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return "&H%s%s%s%s&" % (alpha, b, g, r)          # ASS 是 BBGGRR


def char_w(ch: str, fs: float) -> float:
    """字宽估算: 全角按字号, 半角按一半。估算必然有偏差, 靠第二遍收框兜住。"""
    return fs if ord(ch) > 0x2E80 else fs * 0.5


# 字号同时受安全区宽高约束、且不留兜底下限, 以及 8px 内缩余量: 这三条都是实测踩出来的,
# 改回去会出现 1 到 16 像素的越界
# (see ).
def main() -> int:
    """Agent Notes
    .agents/notes/implemented/architecture/2026-09-28-kfx-normalized-safe-area.md
    """
    ap = argparse.ArgumentParser()
    ap.add_argument("--sentences", required=True)
    ap.add_argument("--safe", required=True, help="X0,Y0,X1,Y1")
    ap.add_argument("--out", required=True)
    ap.add_argument("--font", default="Noto Sans CJK JP")
    ap.add_argument("--outline", default="375A69", help="文字描边色 RRGGBB, 取自 MV 主色暗色簇")
    ap.add_argument("--deco", default="", help="母题色 RRGGBB; 留空则取 --outline 的提亮版")
    ap.add_argument("--deco-lift", type=float, default=2.6,
                    help="母题色 = 描边色乘该系数 (描边要暗才压得住白字, 图元要亮才看得见, "
                         "两者不是同一个颜色)")
    ap.add_argument("--bright", default="FFFFFF", help="点亮时的填充色")
    ap.add_argument("--ghost", default="7B7B7B", help="幽灵态填充灰阶")
    ap.add_argument("--bg", default="0D1924",
                    help="局部暗底色 RRGGBB; 用独立绘图事件画出 (BorderStyle=1 时 BackColour 不渲染)")
    ap.add_argument("--no-backdrop", action="store_true",
                    help="不画暗底。默认画, 因为实测明亮 MV 上九成区域靠白字达不到 12:1")
    ap.add_argument("--backdrop-pad", type=float, default=14.0, help="暗底相对安全区的内缩")
    ap.add_argument("--main-fs", type=float, default=68.0)
    ap.add_argument("--margin", type=float, default=8.0,
                    help="安全区四边各向内预留的像素 (给描边/阴影/字形 overshoot 用)")
    a = ap.parse_args()

    sx0, sy0, sx1, sy1 = (int(v) for v in a.safe.split(","))
    SW, SH = sx1 - sx0, sy1 - sy0
    sentences = json.load(open(a.sentences, encoding="utf-8"))
    sentences = [s for s in sentences if s["t1"] - s["t0"] >= 0.5]

    FILL_ON = ass_color(a.bright)
    FILL_OFF = ass_color(a.ghost)
    OUTLINE = ass_color(a.outline)
    BACK = ass_color(a.bg)
    if a.deco:
        deco_hex = a.deco.lstrip("#")
    else:
        oh = a.outline.lstrip("#")
        deco_hex = "".join("%02X" % min(255, int(int(oh[i:i+2], 16) * a.deco_lift)) for i in (0, 2, 4))
    DECO = ass_color(deco_hex)
    CLIP = "\\clip(%d,%d,%d,%d)" % (sx0, sy0, sx1, sy1)

    head = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: JP,%s,68,%s,%s,%s,%s,0,0,0,0,100,100,0,0,1,3,0,5,0,0,0,1
Style: DECO,%s,68,%s,%s,%s,%s,0,0,0,0,100,100,0,0,1,0,0,5,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""" % (a.font, FILL_ON, FILL_ON, OUTLINE, BACK,
       a.font, DECO, DECO, DECO, BACK)

    ev, used = [], set()

    # 局部暗底: 必须用 \p1 画一个矩形。写进 Style 的 BackColour 在 BorderStyle=1 下**不渲染**
    #  实测踩过: 纯白底渲染的暗像素占比是 0.0000%, 即暗底根本没出现, 而对比度门禁
    # 却对着这个不存在的底板算出了 17.92:1。
    if not a.no_backdrop:
        pad = a.backdrop_pad
        bx0, by0 = sx0 + pad, sy0 + pad
        bx1, by1 = sx1 - pad, sy1 - pad
        rect = "m 0 0 l %.0f 0 l %.0f %.0f l 0 %.0f" % (bx1 - bx0, bx1 - bx0, by1 - by0, by1 - by0)
        t_last = max((s["t1"] for s in sentences), default=0.0)
        ev.append("Dialogue: 0,%s,%s,DECO,,0,0,0,,{\\an7\\pos(%.0f,%.0f)\\p1\\bord0\\1c%s\\alpha&H30&}%s"
                  % (ts(0), ts(t_last), bx0, by0, BACK, rect))

    for si, s in enumerate(sentences):
        jp = s["jp"]
        n = len(jp)
        if n == 0:
            continue
        # 字号受两维同时约束: 宽度 (估算字宽 x0.92 余量) 与高度 (文字带约 1.24 倍字号加母题带约 0.5 倍).
        # 只按宽度自适应会在矮安全区溢出底边; 不能给字号设会突破安全区的下限, 放不下就缩字号并告警.
        usable_h = max(SH - 2.0 * a.margin, 4.0)
        usable_w = max(SW - 2.0 * a.margin, 4.0)
        fs = min(a.main_fs, usable_w / n * 0.92, usable_h / 1.77)
        if fs < 14.0:
            print("! 警告: 安全区太矮 (高 %d), 字号被压到 %.1fpx, 建议放高或减少母题带"
                  % (SH, fs), file=sys.stderr)
        widths = [char_w(c, fs) for c in jp]
        total = sum(widths)
        x0 = sx0 + a.margin + (usable_w - total) / 2.0        # 水平居中于内缩后的可用区
        # 纵向排版: 自上而下 [margin][余量][文字带][母题带][余量][margin]。
        text_h = fs * 1.27
        deco_h = fs * 0.50
        slack = usable_h - text_h - deco_h
        if slack < 0:                                        # 极窄安全区: 母题让位
            deco_h = max(0.0, usable_h - text_h)
            slack = 0.0
        top = sy0 + a.margin + slack / 2.0
        y_main = top + text_h / 2.0
        y_deco = top + text_h + deco_h / 2.0
        span = (s["t1"] - s["t0"]) * 0.88                    # 留出尾部「全亮」时间
        for i, ch in enumerate(jp):
            cx = x0 + sum(widths[:i]) + widths[i] / 2.0
            tl = span * (i + 0.5) / n * 1000.0
            ev.append("Dialogue: 0,%s,%s,JP,,0,0,0,,{\\an5\\pos(%.1f,%.1f)\\bord3\\1c%s\\3c%s"
                      "\\t(%.0f,%.0f,\\1c%s\\bord4)\\t(%.0f,%.0f,\\bord3)}%s"
                      % (ts(s["t0"]), ts(s["t1"]), cx, y_main, FILL_OFF, OUTLINE,
                         tl, tl + 140, FILL_ON, tl + 140, tl + 300, ch))
        name = pick(jp, si)
        used.add(name)
        # 母题用 \an4 (左中) 锚在左下角, 路径向上生长, 宽度不超整行, 高度不超 deco_h。
        p = path_of(name, total, deco_h * 0.86)
        ev.append("Dialogue: 0,%s,%s,DECO,,0,0,0,,{\\an4\\pos(%.1f,%.1f)\\p1\\bord0\\1c%s%s"
                  "\\t(0,%d,\\1a&HFF&)}%s"
                  % (ts(s["t0"]), ts(s["t1"]), x0, y_deco, DECO,
                     CLIP, int((s["t1"] - s["t0"]) * 1000), p))

    outdir = os.path.dirname(os.path.abspath(a.out))
    os.makedirs(outdir, exist_ok=True)
    open(a.out, "w", encoding="utf-8").write(head + "\n".join(ev) + "\n")
    print("句子 %d  事件 %d  用到的母题 %d 种: %s"
          % (len(sentences), len(ev), len(used), ",".join(sorted(used))))
    print("安全区 x[%d,%d] y[%d,%d]" % (sx0, sx1, sy0, sy1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
