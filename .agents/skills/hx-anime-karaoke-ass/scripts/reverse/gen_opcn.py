# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""按反推的规格重生成 Charlotte 的 OPCN 效果。

规格来源：`reverse_opcn.py` 从成品量出，每项都有数百次独立印证。
本文件只把规格写成代码，不发明效果。

## 规格总表

一个字 = **8 条**事件，两族结构同构、轴向不同：

    字距 40（样式 fs=40、spacing=0），句宽 = 字数 × 40，整句居中于 PlayResX/2
    字高 200（clip 的纵向跨度），四片宽 90 | 10 | 10 | 90

    横切族  \\fad(140,0)   \\fscx240（在 \\t **外**）
        初始   y 带 = 固定 4 段 (-70,20)(20,30)(30,40)(40,130)
               x = 整块（跨 200），位置**错开**
        \\t(0,300)  x 收拢到 字心±100，y 保持；\\move 起点错开 -> 终点字心

    纵切族  \\fad(0,140)   \\fscy240（在 \\t **内**）
        初始   x 带 = 固定 4 段（90|10|10|90），y = 整块 -70..130
        \\t(0,300)  clip 与 \\move **同步整体平移**（高度恒 200，不拉伸）
               \\move 起点 = 字心 -> 终点 y = 平移后的中心

    色    句级，四色轮换 BA4561 / 672791 / 45C043 / A06E31
    时间  整句 7 个字**同时出现**（窗 = [句首, 句末]），句末再加一条 300ms 收尾

用法：
  hx-karaoke gen_opcn.py <源句.ass> <输出.ass>
"""
import re
import sys

#  规格常量 
CHAR_STEP = 40          # 字距 = 字号（fs=40、spacing=0）
SPAN_X = 200.0          # 横切族：x 整块的跨度
SPAN_Y = (-70, 130)     # 两族共用的 y 整块（高 200）
Y_BANDS = ((-70, 20), (20, 30), (30, 40), (40, 130))   # 横切族：y 撕成的 4 段
SLICES = (90, 10, 10, 90)                              # 纵切族：x 撕成的 4 段
DUR = 300               # \\t 时长（ms）
SCALE = 240             # 初始放大
COLORS = ("BA4561", "672791", "45C043", "A06E31")


# Agent Notes: hx-anime-karaoke-ass 的 scripts/ 按职责分组，并把 5 个超 300 行的模块拆开
# 
def read_source(path):
    """
    .agents/notes/implemented/process/2026-10-04-karaoke-skill-genericize.md
    .agents/notes/implemented/process/2026-10-05-karaoke-scripts-grouping.md
读源句（Comment: karaoke）、样式表、分辨率。"""
    lines, styles, res = [], {}, (1280, 720)
    for raw in open(path, encoding="utf-8-sig", errors="replace"):
        if raw.startswith("Style:"):
            # Agent Notes: 卡拉OK skill 通用化  去掉单次制作的事实与清单式铺陈
            # 
            f = [x.strip() for x in raw[6:].split(",")]
            # **原样保留整行**：只取字体/字号/对齐会丢掉描边色、描边宽、阴影等 
            # 实测漏掉 `\3c` 与 `bord` 会让渲染出的字没有辉光、笔画细一圈。
            styles[f[0]] = f
        elif raw.startswith("PlayRes"):
            # `PlayResX: 1280`  按**结尾字符**判，用 `in` 会同时命中 X 与 Y
            k, v = raw.split(":")
            res = (int(v), res[1]) if k.strip().endswith("X") else (res[0], int(v))
        elif raw.startswith("Comment:"):
            f = raw.split(",", 9)
            if len(f) >= 10 and f[8].strip().startswith("karaoke"):
                lines.append(dict(start=f[1], end=f[2], style=f[3], actor=f[4], text=f[9]))
    return lines, styles, res


def syllables(text):
    """拆 `\\kNN字` -> [(时长厘秒, 字)]；空白字（全角空格）保留但不产事件。"""
    out = []
    for m in re.finditer(r"\{[^}]*\\k(\d+)[^}]*\}([^{]*)", text):
        for ch in m.group(2):
            if ch.strip():
                out.append((int(m.group(1)), ch))
    return out


def emit_char(cx, cy, ch, base_ms, end_ms, color):
    """一个字的 8 条  **两族的时间窗不同**（实测「坍」）：

        横切族 4 条  \\fad(140,0)  → 时间窗 [句首, 句末]        整句都在
        纵切族 4 条  \\fad(0,140)  → 时间窗 [句末, 句末+300ms]  只做收尾

    把两族都铺满整句会多出一倍事件（实测 7872 vs 原版 2872）。
    """
    out = []
    half = SPAN_X / 2

    # ---- 横切族：y 带固定，x 初始错开 -> 收拢到字心。整句时间窗。
    for i, (y0, y1) in enumerate(Y_BANDS):
        off = (24, 15, 17, 25)[i]
        out.append((
            f"{{\\an5\\blur3\\fad(140,0)\\3c&H{color}&\\fscx{SCALE}"
            f"\\clip({cx - half + off:.0f},{y0},{cx + half + off:.0f},{y1})"
            f"\\t(0,{DUR},\\fscx100\\clip({cx - half:.0f},{y0},{cx + half:.0f},{y1})"
            f"\\move({cx + off:.0f},{cy:.0f},{cx:.0f},{cy:.0f},0,{DUR}))}}{ch}",
            base_ms, end_ms))

    # ---- 纵切族：x 带固定，y **整体平移**（高度恒 200）。只在收尾 300ms。
    x = cx - sum(SLICES) / 2
    for i, sw in enumerate(SLICES):
        dy = (22, -21, 21, -22)[i]
        out.append((
            f"{{\\an5\\blur3\\fad(0,140)\\3c&H{color}&"
            f"\\clip({x:.0f},{SPAN_Y[0]},{x + sw:.0f},{SPAN_Y[1]})"
            f"\\t(0,{DUR},\\fscy{SCALE}\\clip({x:.0f},{SPAN_Y[0] - dy:.0f},"
            f"{x + sw:.0f},{SPAN_Y[1] - dy:.0f})"
            f"\\move({cx:.0f},{cy:.0f},{cx:.0f},{cy - dy:.0f},0,{DUR}))}}{ch}",
            end_ms, end_ms + DUR))
        x += sw
    return out


def ts(ms):
    cs = max(0, int(ms)) // 10
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def to_ms(t):
    h, m, r = t.split(":")
    return (int(h) * 3600 + int(m) * 60) * 1000 + int(round(float(r) * 1000))


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else None
    dst = sys.argv[2] if len(sys.argv) > 2 else "opcn_out.ass"
    if not src:
        sys.exit("用法: hx-karaoke gen_opcn.py <源句.ass> <输出.ass>")
    lines, styles, res = read_source(src)
    print(f"源句 {len(lines)} 条  PlayRes {res[0]}x{res[1]}")

    events = []
    for i, ln in enumerate(lines):
        base, end_ms = to_ms(ln["start"]), to_ms(ln["end"])
        syls = syllables(ln["text"])
        if not syls:
            continue
        # 整句居中：字距 = 字号
        width = len(syls) * CHAR_STEP
        x0 = res[0] / 2 - width / 2 + CHAR_STEP / 2
        color = COLORS[i % len(COLORS)]
        # **整句同时出现**（横切族铺满整句，纵切族只做收尾  见 emit_char 的说明）
        for k, (_dur, ch) in enumerate(syls):
            cx = x0 + k * CHAR_STEP
            events += emit_char(cx, 30.0, ch, base, end_ms, color)

    fmt = ("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
           "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
           "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding")
    head = ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {res[0]}", f"PlayResY: {res[1]}",
            "WrapStyle: 2", "ScaledBorderAndShadow: yes", "", "[V4+ Styles]", fmt]
    for name, st in styles.items():
        # 样式行**原样透传**（读进来时保留了整行字段）
        head.append("Style: " + ",".join(st))
    head += ["", "[Events]",
             "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    with open(dst, "w", encoding="utf-8") as fh:
        fh.write("\n".join(head) + "\n")
        for text, a, b in events:
            fh.write(f"Dialogue: 0,{ts(a)},{ts(b)},OPCN,,0,0,0,,{text}\n")
    print(f"生成 {len(events)} 条 -> {dst}")


if __name__ == "__main__":
    main()
