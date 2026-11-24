# -*- coding: utf-8 -*-
"""字形来源: 取字体里一个字的真实轮廓, 转成 ASS \\p1 路径 (精确, 不采样成折线).

为什么要它: 手拼的几何语汇只有几十种, 每首歌都从同一批圆/星/心里取, 容易同质化.
字形是现成的高质量矢量: 汉字部首, 假名, 符号字体里的纹样都能当母题 (例: 「雪」的雨头, 「♪」).
TrueType 的二次贝塞尔按 2/3 规则精确升成三次 (ASS 的 b 是三次), 不丢精度.

用法:
    from assfx.draw.glyph import glyph_path
    d = glyph_path(FONT, "雪", size=80)          # 以字身高 80px 归一化, 原点在包围盒左上
"""
import os

_CACHE = {}


def _fmt(v):
    s = "%.2f" % v
    s = s.rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


class _AssPen:
    """fontTools 的 pen 协议 -> ASS 命令串. y 轴翻转 (字体 y 向上, ASS y 向下)."""

    def __init__(self, k, ox, oy):
        self.k, self.ox, self.oy = k, ox, oy
        self.out, self.cur, self.start = [], None, None

    def _p(self, pt):
        return (pt[0] - self.ox) * self.k, (self.oy - pt[1]) * self.k

    def moveTo(self, pt):
        x, y = self._p(pt)
        self.out.append("m %s %s" % (_fmt(x), _fmt(y)))
        self.cur = self.start = pt

    def lineTo(self, pt):
        x, y = self._p(pt)
        self.out.append("l %s %s" % (_fmt(x), _fmt(y)))
        self.cur = pt

    def curveTo(self, *pts):
        # 三次: 多于 3 个点时 fontTools 用隐含点分段; 这里只收标准 3 点 (CFF 字体)
        for i in range(0, len(pts) - 2, 3):
            a, b, c = (self._p(p) for p in pts[i:i + 3])
            self.out.append("b " + " ".join(_fmt(v) for v in (*a, *b, *c)))
            self.cur = pts[i + 2]

    def qCurveTo(self, *pts):
        # 二次 B 样条: 相邻控制点之间有隐含的落点 (中点). 每段二次 -> 三次: c1 = p0 + 2/3 (q - p0), c2 = p1 + 2/3 (q - p1)
        if pts[-1] is None:          # 全是离线点的闭合轮廓 (少见)
            pts = pts[:-1] + (self.start,)
        ctrl, end = list(pts[:-1]), pts[-1]
        p0 = self.cur
        for i, q in enumerate(ctrl):
            p1 = end if i == len(ctrl) - 1 else ((q[0] + ctrl[i + 1][0]) / 2, (q[1] + ctrl[i + 1][1]) / 2)
            c1 = (p0[0] + 2 / 3 * (q[0] - p0[0]), p0[1] + 2 / 3 * (q[1] - p0[1]))
            c2 = (p1[0] + 2 / 3 * (q[0] - p1[0]), p1[1] + 2 / 3 * (q[1] - p1[1]))
            a, b, c = self._p(c1), self._p(c2), self._p(p1)
            self.out.append("b " + " ".join(_fmt(v) for v in (*a, *b, *c)))
            p0 = p1
        self.cur = end

    def closePath(self):
        self.cur = self.start

    endPath = closePath

    def addComponent(self, name, tf):     # 复合字形由 glyphSet 的 pen 展开, 这里不会被调到
        raise NotImplementedError(name)


def _font(path):
    if path not in _CACHE:
        from fontTools.ttLib import TTFont
        if not os.path.exists(path):
            raise FileNotFoundError("glyph 来源的字体不存在: %s (字体由 setup/fetch_fonts.py 取, 不进 git)" % path)
        _CACHE[path] = TTFont(path, lazy=True)
    return _CACHE[path]


def glyph_path(font_path, ch, size=80, by="height"):
    """返回 (ASS 路径, 宽, 高). by=height: 包围盒高缩放到 size; by=em: 字身 (units_per_em) 缩放到 size."""
    from fontTools.pens.boundsPen import BoundsPen
    from fontTools.pens.recordingPen import DecomposingRecordingPen
    f = _font(font_path)
    cmap = f.getBestCmap() or {}
    gname = cmap.get(ord(ch))
    if gname is None:
        raise KeyError("字体 %s 里没有「%s」" % (os.path.basename(font_path), ch))
    gs = f.getGlyphSet()
    bp = BoundsPen(gs)
    gs[gname].draw(bp)
    if bp.bounds is None:
        raise ValueError("「%s」是空字形 (空格类), 不能当母题" % ch)
    x0, y0, x1, y1 = bp.bounds
    k = size / (y1 - y0 if by == "height" else f["head"].unitsPerEm)
    rec = DecomposingRecordingPen(gs)
    gs[gname].draw(rec)
    pen = _AssPen(k, x0, y1)
    rec.replay(pen)
    return " ".join(pen.out), (x1 - x0) * k, (y1 - y0) * k
