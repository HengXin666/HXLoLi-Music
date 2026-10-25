# -*- coding: utf-8 -*-
"""AssWriter  把 Event 列表落成 ASS。"""
import os

DEFAULT_INFO = ("[Script Info]\nScriptType: v4.00+\nWrapStyle: 2\n"
                "ScaledBorderAndShadow: yes\nPlayResX: {x}\nPlayResY: {y}\n")
STYLE_FMT = ("[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
             "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, "
             "Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, "
             "MarginV, Encoding\n")
EV_FMT = ("[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
          "Effect, Text\n")


def ts(t: float) -> str:
    """秒 -> ASS 时间戳。负值夹到 0。"""
    cs = int(round(max(0.0, t) * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def style_line(name, font, size, primary="&H00FFFFFF", outline="&H00000000",
               bord=0, spacing=0, align=2, bold=False, margin_v=0):
    return (f"Style: {name},{font},{size},{primary},&H00FFFFFF,{outline},&H00000000,"
            f"{-1 if bold else 0},0,0,0,100,100,{spacing},0,1,{bord},0,{align},0,0,"
            f"{margin_v},1")


def write(events, path, styles=None, res=(1920, 1080), title="", sort=True) -> int:
    """写文件；返回事件数。styles 可传 `{名字: Style}` 或已渲染的字符串列表。"""
    info = DEFAULT_INFO.format(x=res[0], y=res[1])
    if title:
        info = f"Title: {title}\n" + info
    lines = []
    if styles:
        if isinstance(styles, dict):
            for st in styles.values():
                lines.append(style_line(st.name, st.font, st.size, bord=st.outline,
                                        spacing=st.spacing, align=st.align,
                                        bold=st.bold, margin_v=st.margin_v))
        else:
            lines.extend(styles)
    if not lines:
        lines.append(style_line("Default", "Arial", 20))
    evs = sorted(events, key=lambda e: (e.start, e.layer)) if sort else events
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(info + STYLE_FMT + "\n".join(lines) + "\n\n" + EV_FMT)
        for e in evs:
            fh.write(f"Dialogue: {e.layer},{ts(e.start)},{ts(e.end)},{e.style},"
                     f"{e.actor},0,0,0,,{e.text}\n")
    return len(evs)
