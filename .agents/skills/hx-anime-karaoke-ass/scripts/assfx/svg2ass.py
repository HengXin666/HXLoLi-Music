# -*- coding: utf-8 -*-
r"""
SVG -> ASS 绘图代码 (p1) 转换器。

## 为什么需要它
用 shapes.py 里的 circle/rect/arc 拼一个"自行车", 出来只是几个圆圈加几条线。
用户原话: "你画的图都太不精细了，你必须要在网上去找图片，然后把它变为SVG或者直接内封渲染"。
真正精细的做法是取现成的矢量图形(图标库/插画 SVG), 把它的 path 转成 ASS 绘图指令。

## 为什么用 svgelements 而不是手写解析器
先手写了一个支持 M/L/H/V/C/S/Q/T/A/Z 的解析器, 实测渲染时 bicycle / window / moon-stars
出现**实心团块**(环的孔被填死)、tree / music-note 形状错乱 —— 相对指令与圆弧的
方向处理有隐 bug。改为依赖 `svgelements`(纯 python, 1 个包) 后一次通过。
**不要重新手写 SVG 解析器。**

## 做法: 把曲线采样成折线
svgelements 的 Path 可以直接按长度采样。ASS 的 \p1 只认 m/l/b, 用折线近似曲线最简单且
不可能出方向错 —— 每条子路径的点序原样保留, ASS 的 nonzero 填充自动把孔挖出来。

## 用法
    from assfx.svg2ass import from_url, from_file
    d = from_url("https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/icons/bicycle.svg", size=64)
    f.shape(5, t0, t1, x, y, draw=d, c1="#FFFFFF", ...)

## 缓存：**绝不写进 skill 目录**
缓存目录按 `ASSFX_SVG_CACHE` > `$XDG_CACHE_HOME/hx-anime-karaoke-ass/svg` 的顺序取。

**不许把缓存放回 skill 里**：缓存是**运行期产物**，落到 skill 目录就等于把"某个工程的素材"
永久混进 skill 本体 —— 换首歌时旧图形还在，删都分不清哪些是该留的。
skill 是只读的代码与契约, 不带任何一次运行的痕迹。
"""
import hashlib
import os
import re
import urllib.request


def _ensure_cache():
    c = os.environ.get("ASSFX_SVG_CACHE")
    if not c:
        base = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
        c = os.path.join(base, "hx-anime-karaoke-ass", "svg")
    os.makedirs(c, exist_ok=True)
    return c


def _paths(svg_text):
    """取出全部 path/marker 的 d 字符串。"""
    return re.findall(r'<path[^>]*\bd\s*=\s*"([^"]+)"', svg_text)


def _one_path_to_polys(d, flatten=0.6):
    """一条 path -> [[(x,y), ...], ...]（每条子路径一个点列）。"""
    from svgelements import Path, Move, Close, Line, Arc, CubicBezier, QuadraticBezier
    p = Path(d)
    polys = []
    cur = []
    for seg in p:
        if isinstance(seg, Move):
            if cur:
                polys.append(cur)
            cur = [(float(seg.end.x), float(seg.end.y))]
        elif isinstance(seg, Close):
            if seg.start is not None:
                cur.append((float(seg.end.x), float(seg.end.y)))
            if cur:
                polys.append(cur)
            cur = []
        else:
            # npoint 返回的是 numpy 数组（不是 Point），必须按下标取；点 用 .point() 才给 Point
            n = max(3, int(seg.length() / max(0.2, flatten)) + 2)
            ts = _linspace(0.0, 1.0, n)
            pts = []
            try:
                arr = seg.npoint(ts)
                for row in arr:
                    pts.append((float(row[0]), float(row[1])))
            except Exception:
                try:
                    pts = [(float(seg.point(t).x), float(seg.point(t).y)) for t in ts]
                except Exception:
                    pts = []
            for q in pts:
                cur.append(q)
    if cur:
        polys.append(cur)
    return [q for q in polys if len(q) >= 2]


def _linspace(a, b, n):
    if n <= 1:
        return [a]
    return [a + (b - a) * i / (n - 1) for i in range(n)]


def to_ass_draw_multi(polys, size=60, flip_y=True, precision=2, min_step=0.35):
    r"""多条折线 -> 单条 ASS \p1 绘图代码（以视觉中心为原点）。

    min_step: 相邻点距离小于它时合并 —— 控制输出长度。ASS 事件太长会影响加载。
    """
    flat = [pt for pl in polys for pt in pl]
    if not flat:
        return ""
    xs = [p[0] for p in flat]; ys = [p[1] for p in flat]
    cx, cy = (min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0
    h = max(1e-6, max(ys) - min(ys))
    k = size / h
    def fx(v): return (v - cx) * k
    def fy(v): return -((v - cy) * k) if flip_y else (v - cy) * k
    parts = []
    for pl in polys:
        seq = [pl[0]]
        for pt in pl[1:]:
            if abs(fx(pt[0]) - fx(seq[-1][0])) + abs(fy(pt[1]) - fy(seq[-1][1])) < min_step:
                continue
            seq.append(pt)
        if len(seq) < 2:
            continue
        parts.append("m %.{}f %.{}f".format(precision, precision) % (fx(seq[0][0]), fy(seq[0][1])))
        for pt in seq[1:]:
            parts.append("l %.{}f %.{}f".format(precision, precision) % (fx(pt[0]), fy(pt[1])))
    return " ".join(parts)


def from_text(svg_text, size=60, flip_y=True, flatten=0.6):
    polys = []
    for d in _paths(svg_text):
        try:
            polys.extend(_one_path_to_polys(d, flatten))
        except Exception:
            continue
    return to_ass_draw_multi(polys, size=size, flip_y=flip_y)


def from_file(path, size=60, flip_y=True, flatten=0.6):
    with open(path, encoding="utf-8") as f:
        return from_text(f.read(), size=size, flip_y=flip_y, flatten=flatten)


def fetch(url, timeout=25):
    """下载并缓存 SVG 文本。缓存键 = url 的 sha1；缓存目录见 `_ensure_cache()`（不在 skill 内）。"""
    c = _ensure_cache()
    key = hashlib.sha1(url.encode()).hexdigest()[:16] + ".svg"
    p = os.path.join(c, key)
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return f.read()
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        txt = r.read().decode("utf-8", "replace")
    with open(p, "w", encoding="utf-8") as f:
        f.write(txt)
    return txt


def from_url(url, size=60, flip_y=True, flatten=0.6, timeout=25):
    return from_text(fetch(url, timeout=timeout), size=size, flip_y=flip_y, flatten=flatten)
