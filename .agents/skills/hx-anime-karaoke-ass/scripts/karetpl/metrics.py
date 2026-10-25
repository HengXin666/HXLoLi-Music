# -*- coding: utf-8 -*-
"""度量：把"一个字多宽"与"整行放哪"抽出来，让字体可替换。

契约见 CONTRACT.md：
  line.width   用整数进位（全角 = fs + spacing）
  $scenter     用字体真实 advance
两者是**不同基准**，实测反推自某成品：lwidth=600（8 字 × 75）而字心递进 75.14。
合并会让盘位差 139px。
"""
from dataclasses import dataclass


class Metrics:
    """默认度量：按"每字 = fs + spacing"的整数进位算。

    换字体时继承并覆盖 advance()：
        class MyFont(Metrics):
            def advance(self, ch, fs, spacing):   # 从字体文件读真实 advance
                ...
    """

    def __init__(self, center_advance=None):
        # center_advance: $scenter 用的推进量；None 表示与 width 同基准
        self.center_advance = center_advance

    def is_fullwidth(self, ch: str) -> bool:
        """全角判定：CJK / 假名 / 全角标点。"""
        o = ord(ch)
        return (0x2E80 <= o <= 0x9FFF or 0xAC00 <= o <= 0xD7FF
                or 0xF900 <= o <= 0xFAFF or 0xFF00 <= o <= 0xFF60
                or 0x3000 <= o <= 0x303F)

    def advance(self, ch: str, fs: float, spacing: float) -> float:
        """单字推进量（**整数进位**基准，用于 line.width）。"""
        if ch == " ":
            return (fs + spacing) * 0.5
        return fs + spacing if self.is_fullwidth(ch) else (fs + spacing) * 0.5

    def width(self, text: str, fs: float, spacing: float) -> float:
        return sum(self.advance(c, fs, spacing) for c in text)

    def center_advance_of(self, fs: float, spacing: float) -> float:
        """$scenter 的基准推进量。默认与 width 一致，注入可给字体真值。"""
        return self.center_advance if self.center_advance is not None else (fs + spacing)

    # ---- 行几何
    def line_box(self, surface: str, style, res_x: int, res_y: int) -> dict:
        """算一行的 left / width / middle / bottom / top / height。

        ASS 的 align 决定"竖排锚点在哪"（karaskel 的公式）：

            align 1~3（底部）: bottom = res_y - mv;  middle = bottom - h/2
            align 4~6（中部）: middle = res_y/2;      bottom = middle + h/2
            align 7~9（顶部）: top    = mv;          middle = top + h/2

        实测教训：某成品的 `JP_FX_CS` 用 **align=8（顶部居中）**，
        它模板里的 `pos($scenter,$smiddle)` 原版产出 y=85（= mv50 + h70/2）。
        按"底部"算会得 995  差 910px，整个特效跑到画面另一头。
        """
        w = self.width(surface, style.size, style.spacing)
        left = (res_x - style.margin_l - style.margin_r - w) / 2 + style.margin_l
        h = style.size
        a = style.align
        if a in (7, 8, 9):          # 顶部
            top = style.margin_v
            middle = top + h / 2
            bottom = top + h
        elif a in (4, 5, 6):        # 中部
            middle = res_y / 2
            top, bottom = middle - h / 2, middle + h / 2
        else:                        # 1~3 底部
            bottom = res_y - style.margin_v
            middle = bottom - h / 2
            top = bottom - h
        return dict(left=left, width=w, right=left + w,
                    bottom=bottom, top=top, middle=middle, height=h)
