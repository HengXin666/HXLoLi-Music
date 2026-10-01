# -*- coding: utf-8 -*-
"""
ASS 基础：时间/颜色/透明度格式化、事件容器、区域(band)登记、文件写出。

约定（validate_ass.py 依赖这些约定做自动校验）：
  * 每条事件的 Name 字段标注归属：
      ly:<band>   歌词本体（日文/注音/中文字符）
      fx:<band>   特效（绘图/光晕/粒子），必须完整落在 <band> 矩形内
      card:<band> 标题/片尾等卡片文字
  * band 在 [Script Info] 中以注释行登记：
      ; assfx-band: <name> <x0> <y0> <x1> <y1> <t0> <t1>
  * 所有定位用 \\an5（绘图/文字中心 = \\pos 点），校验器按此计算包围盒
"""


def ts(t):
    t = max(0.0, t)
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000); m, cs = divmod(cs, 6000); s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def col(hexrgb):
    """#RRGGBB -> &HBBGGRR&"""
    h = hexrgb.lstrip("#")
    return f"&H{h[4:6]}{h[2:4]}{h[0:2]}&".upper()


def al(a):
    return f"&H{int(max(0, min(255, round(a)))):02X}&"


def ms(x):
    return int(round(x * 1000))


def lerp_hex(a, b, k):
    a = a.lstrip("#"); b = b.lstrip("#")
    ca = [int(a[i:i + 2], 16) for i in (0, 2, 4)]; cb = [int(b[i:i + 2], 16) for i in (0, 2, 4)]
    return "#" + "".join(f"{int(round(x + (y - x) * k)):02X}" for x, y in zip(ca, cb))


def grad(stops, k):
    """多色渐变取色 k∈[0,1]"""
    k = max(0.0, min(1.0, k)); pos = k * (len(stops) - 1); i = int(pos); j = min(i + 1, len(stops) - 1)
    return lerp_hex(stops[i], stops[j], pos - i)


STYLE_FMT = ("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
             "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding")


def style(name, font, fs, bold=0, italic=0, primary="&H00FFFFFF", outline="&H00000000", bord=0, spacing=0, an=5):
    return (f"Style: {name},{font},{fs},{primary},&H00FFFFFF,{outline},&H00000000,{-1 if bold else 0},{-1 if italic else 0},"
            f"0,0,100,100,{spacing},0,1,{bord},0,{an},0,0,0,1")


class Doc:
    def __init__(self, title, w=1920, h=1080, fx_font="Arial"):
        """fx_font: 绘图专用样式 FX 的字体名——设为 fonts 目录里已有的字体，避免 libass 做无谓的字体回退"""
        self.title = title; self.w = w; self.h = h
        self.styles = [style("FX", fx_font, 20, an=7)]
        self.events = []      # (layer, start, end, style, name, text)
        self.bands = {}       # name -> (x0, y0, x1, y1, t0, t1)

    def add_style(self, *a, **k):
        self.styles.append(style(*a, **k))

    def band(self, name, x0, y0, x1, y1, t0, t1):
        x0, y0 = max(0, x0), max(0, y0); x1, y1 = min(self.w, x1), min(self.h, y1)
        self.bands[name] = (round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1), round(t0, 2), round(t1, 2))
        return self.bands[name]

    # 文字层相对特效层的固定抬升量。
    #
    # 为什么必须有它（实测 2026-10-02）：动画层（anim.py）用 layer 1~4 画日文/注音/中文，
    # 而特效层（fx.py）也被允许用 0~8 —— 两者落在同一区间，特效直接压在字上。
    # 黑底分层渲染的量化结果：t=45s 时 FX 墨迹 105169 像素、JP 只有 16393，
    # FX 是歌词的 6.4 倍且盖在文字带（y 444-474）里 —— 观感就是"全是重叠，看不了"。
    # 参考项目（HX-Ass-Skill 的成品 KFX）的做法是：**特效一律在字下，字永远在最上**。
    TEXT_LIFT = 20 if False else 20     # 见下方 ev() 的说明

    def ev(self, layer, start, end, text, st="FX", name=""):
        if end - start < 0.011:
            return
        # 文字事件（ly: 开头）统一抬到特效之上；特效保持调用方给的层号。
        # 这样"字永远压得住特效"是**结构保证**，不依赖每个特效函数自觉。
        if name.startswith("ly:"):
            layer += 20
        self.events.append((layer, start, end, st, name, text))

    def write(self, path, extra_info=""):
        self.events.sort(key=lambda e: (e[1], e[0]))
        with open(path, "w", encoding="utf-8-sig") as f:
            f.write("[Script Info]\n")
            f.write(f"Title: {self.title}\nScriptType: v4.00+\nWrapStyle: 2\nScaledBorderAndShadow: yes\n"
                    f"YCbCr Matrix: TV.709\nPlayResX: {self.w}\nPlayResY: {self.h}\n")
            if extra_info:
                f.write(extra_info.rstrip("\n") + "\n")
            for n, b in self.bands.items():
                f.write(f"; assfx-band: {n} {b[0]} {b[1]} {b[2]} {b[3]} {b[4]} {b[5]}\n")
            f.write("\n[V4+ Styles]\n" + STYLE_FMT + "\n" + "\n".join(self.styles) + "\n\n")
            f.write("[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
            for layer, s, e, st, name, text in self.events:
                f.write(f"Dialogue: {layer},{ts(s)},{ts(e)},{st},{name},0,0,0,,{text}\n")
        return len(self.events)
