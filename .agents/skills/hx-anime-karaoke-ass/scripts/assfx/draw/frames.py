# -*- coding: utf-8 -*-
"""预缩放帧序列: 贴图 (\\1img) 的生长 / 缩放动画不再用 \\fscx \\fscy 插值, 改成逐段换一张预先缩好的图.

为什么 (known-gaps #10): libass 对 \\1img 纹理缩放是最近邻采样, 水球从 30% 长到 100% 的中途圆边出台阶.
做法: 用 Pillow 的 LANCZOS 把原图缩到每一档尺寸, 落进**工程目录** (硬规则 11: 不许落进 skill);
动画按档切段, 每段一条事件, 矩形 = 该档图的真实尺寸 (纹理按矩形平铺, 见 draw/image.py 规格 1), 不带 \\fsc.
相邻两档之间用很短的交叠 (默认 1 帧) 防闪. 档位按面积等比 (视觉上匀速).

用法:
    from assfx.draw.frames import prescale, grow
    seq = prescale(PROJ, "assets/orb.png", s0=0.3, s1=1.0, steps=8)
    grow(f, 4, t0, t0 + 0.8, t1, x, y, seq)          # t0..t0+0.8 生长, 停在最大档到 t1
"""
import os

from assfx.base.core import al

_SKILL = os.path.abspath(os.path.join(os.path.dirname(__file__), *[".."] * 5))


def _inside_skill(p):
    p = os.path.abspath(p)
    return p == _SKILL or p.startswith(_SKILL + os.sep)


def prescale(proj, rel, s0=0.3, s1=1.0, steps=8, out_dir="out/frames"):
    """返回 [(scale, 相对 ass 的文件名, w, h)], 升序. 已存在且尺寸对的帧不重写 (确定性: 同输入同字节)."""
    from PIL import Image
    src = os.path.join(proj, rel)
    dst = os.path.join(proj, out_dir)
    if _inside_skill(dst):
        parts = os.path.relpath(dst, _SKILL).split(os.sep)
        if not (len(parts) >= 3 and parts[0] == "examples" and parts[2] == "out"):     # examples/*/out/ 被 gitignore
            raise ValueError("预缩放帧不许写进 skill 目录 (硬规则 11), 示例工程只许写 examples/<曲目>/out/: %s" % dst)
    os.makedirs(dst, exist_ok=True)
    im = Image.open(src).convert("RGBA")
    W, H = im.size
    base = os.path.splitext(os.path.basename(rel))[0]
    out = []
    n = max(2, int(steps))
    for i in range(n):
        u = i / (n - 1)
        s = (s0 * s0 + (s1 * s1 - s0 * s0) * u) ** 0.5          # 面积等比
        w, h = max(1, round(W * s)), max(1, round(H * s))
        name = "%s@%03d.png" % (base, round(s * 100))
        p = os.path.join(dst, name)
        if not (os.path.exists(p) and Image.open(p).size == (w, h)):
            im.resize((w, h), Image.LANCZOS).save(p, optimize=False)
        out.append((round(s, 4), os.path.relpath(p, proj).replace(os.sep, "/"), w, h))
    return out


def grow(f, layer, t0, t_full, t1, x, y, seq, a_peak=0, fade_out=0.5, extra="", overlap=1 / 48):
    """逐档切段: [t0, t_full] 均分给各档, 最大档一直留到 t1 (末段带淡出). 中心对齐 (\\an5).
    每段的矩形 = 该档图的尺寸, 绝不带 \\fsc 缩放标签; 返回发出的事件数."""
    if not seq or t1 <= t0:
        return 0
    n = len(seq)
    seg = max(1e-3, (t_full - t0) / n)
    sent = 0
    for i, (_, rel, w, h) in enumerate(seq):
        ta = t0 + i * seg
        tb = (t0 + (i + 1) * seg + overlap) if i < n - 1 else t1
        rect = "m 0 0 l %d 0 l %d %d l 0 %d" % (w, w, h, h)
        tail = ""
        if i == n - 1 and fade_out > 0:
            d = int((tb - ta) * 1000)
            tail = "\\t(%d,%d,\\alpha&HFF&)" % (max(0, d - int(fade_out * 1000)), d)
        f.shape(layer, ta, tb, x, y, draw=rect, c1="#FFFFFF", a_peak=a_peak, fade_in=0.01, fade_out=0.01, blur=0,
                normalize=True, extra="\\1img(%s)%s%s" % (rel, extra, tail))
        sent += 1
    return sent


def alpha_in(f, layer, t0, t1, x, y, rel, w, h, fade_in=0.5, fade_out=0.5, a_peak=0, extra=""):
    """另一条已定方向: 不缩放, 用 alpha 淡入代替生长 (一张图, 一条事件)."""
    rect = "m 0 0 l %d 0 l %d %d l 0 %d" % (w, w, h, h)
    f.shape(layer, t0, t1, x, y, draw=rect, c1="#FFFFFF", a_peak=a_peak, fade_in=max(0.01, fade_in),
            fade_out=max(0.01, fade_out), blur=0, extra="\\1img(%s)%s" % (rel, extra))
    return al(a_peak)
