#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""跨作品特效指纹: 防止不同的歌长成一个样 (组合式生成的副作用就是同质化, 这里给它一把尺子).

指纹只看特效 "长什么样", 不看歌词: 6 组分布, 每组归一化后算余弦, 相似度 = 6 组余弦的均值 (0~1).
  tags    每种覆盖标签出现在多少比例的事件里 (\\frz \\fax \\move \\t \\clip \\1img \\p ...)
  geom    绘图件的几何: 点数档 x 长宽比档 x 曲线占比档 (同一批原语反复用, 这组会很像)
  layer   层号分布 (0-9)
  life    事件时长分布 (对数档, 50ms~16s)
  motion  \\move 的位移长度档 + 8 个方向
  hue     \\1c \\3c 的色相 12 档 + 低饱和 1 档
用法:
  hx-karaoke kfx/fingerprint.py a.ass b.ass                 # 两份: 打相似度和每组余弦
  hx-karaoke kfx/fingerprint.py --matrix *.ass              # 多份: 两两矩阵
  hx-karaoke kfx/fingerprint.py a.ass b.ass --max 0.86      # 门禁用法: 超过阈值退出码 1 (阈值见 shared/calibration.md)
"""
import argparse, colorsys, itertools, math, os, re, sys

TAGS = ["frz", "frx", "fry", "fax", "fay", "fscx", "fscy", "move", "pos", "org", "t", "clip", "iclip", "blur", "be", "bord",
        "shad", "fad", "fade", "alpha", "1a", "3a", "1c", "3c", "k", "kf", "ko", "p", "1img", "distort", "fsvp", "fe", "q"]
_TAG = re.compile(r"\\(" + "|".join(sorted(TAGS, key=len, reverse=True)) + r")(?![a-z])")
_OVR = re.compile(r"\{([^}]*)\}")
_DRAW = re.compile(r"\\p[1-9][^}]*\}([^{]+)")
_MOVE = re.compile(r"\\move\(\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)")
_COL = re.compile(r"\\[13]?c&H([0-9A-Fa-f]{6})&")
BLOCKS = ("tags", "geom", "layer", "life", "motion", "hue")


def _t(s):
    h, m, r = s.split(":")
    return int(h) * 3600 + int(m) * 60 + float(r)


def events(path):
    fmt = None
    for raw in open(path, encoding="utf-8-sig", errors="replace"):
        if raw.startswith("Format:") and "Text" in raw and "Start" in raw:
            fmt = [x.strip() for x in raw[7:].split(",")]
        elif raw.startswith("Dialogue:") and fmt:
            v = raw[9:].rstrip("\n").split(",", len(fmt) - 1)
            d = dict(zip(fmt, v))
            try:
                yield int(d["Layer"]), _t(d["Start"].strip()), _t(d["End"].strip()), d["Text"]
            except (KeyError, ValueError):
                continue


def _geom_bin(dr):
    toks = dr.split()
    n = sum(1 for x in toks if re.match(r"^-?[\d.]+$", x)) // 2
    nb = sum(1 for x in toks if x == "b")
    nums = [float(x) for x in toks if re.match(r"^-?[\d.]+$", x)]
    xs, ys = nums[0::2], nums[1::2]
    if not xs or not ys:
        return None
    w, h = max(xs) - min(xs), max(ys) - min(ys)
    ar = math.log2((w + 1) / (h + 1))
    return (min(7, int(math.log2(n + 1))), min(4, max(0, int(ar + 2.5))), min(3, int(4 * nb / max(1, nb + toks.count("l")))))


# Agent Notes: 组合式生成: 设计中间表示 + 形状来源 + 母题来源门禁 + 跨作品指纹
# 
def fingerprint(path):
    """Agent Notes
    .agents/notes/implemented/architecture/2026-11-17-karaoke-compositional-generator.md
    返回 {组名: {键: 计数}}. 只统计带覆盖标签的事件 (纯文本行不算特效)."""
    fp = {b: {} for b in BLOCKS}

    def add(b, k, v=1.0):
        fp[b][k] = fp[b].get(k, 0.0) + v
    for layer, s, e, text in events(path):
        ovr = "".join(_OVR.findall(text))
        if not ovr:
            continue
        for tg in set(_TAG.findall(ovr)):
            add("tags", tg)
        for dr in _DRAW.findall(text):
            g = _geom_bin(dr)
            if g:
                add("geom", g)
        add("layer", min(layer, 9))
        add("life", min(9, max(0, int(math.log2(max(e - s, 0.05) / 0.05)))))
        m = _MOVE.search(ovr)
        if m:
            x0, y0, x1, y1 = (float(v) for v in m.groups())
            d = math.hypot(x1 - x0, y1 - y0)
            add("motion", ("len", min(6, int(math.log2(d + 1)))))
            if d > 1:
                add("motion", ("dir", int(((math.degrees(math.atan2(y1 - y0, x1 - x0)) + 360 + 22.5) % 360) // 45)))
        for c in _COL.findall(ovr):
            b_, g_, r_ = int(c[0:2], 16) / 255, int(c[2:4], 16) / 255, int(c[4:6], 16) / 255
            h, sat, val = colorsys.rgb_to_hsv(r_, g_, b_)
            add("hue", "grey" if sat < 0.15 or val < 0.1 else int(h * 12) % 12)
    return fp


FAIL_AT = 0.95    # 2026-11-17 标定 (shared/calibration.md): 外部批量模板 0.999, 本地产线两对 0.96 以上判 FAIL
WARN_AT = 0.85


def _cos(a, b):
    ks = set(a) | set(b)
    na = math.sqrt(sum(v * v for v in a.values())); nb = math.sqrt(sum(v * v for v in b.values()))
    if not na or not nb:
        return 0.0
    return sum(a.get(k, 0) * b.get(k, 0) for k in ks) / (na * nb)


def similarity(fa, fb):
    per = {b: _cos(fa[b], fb[b]) for b in BLOCKS}
    return sum(per.values()) / len(per), per


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ass", nargs="+")
    ap.add_argument("--matrix", action="store_true")
    ap.add_argument("--max", type=float, default=FAIL_AT, help="相似度上限 (标定见 shared/calibration.md); 任一对 >= 即退出码 1")
    a = ap.parse_args()
    fps = {p: fingerprint(p) for p in a.ass}
    worst = 0.0
    if len(a.ass) == 2 and not a.matrix:
        s, per = similarity(fps[a.ass[0]], fps[a.ass[1]])
        worst = s
        print("相似度 %.3f  (%s)" % (s, "  ".join("%s %.3f" % kv for kv in per.items())))
    else:
        for p, q in itertools.combinations(a.ass, 2):
            s, _ = similarity(fps[p], fps[q])
            worst = max(worst, s)
            print("%.3f  %s  |  %s" % (s, os.path.basename(p), os.path.basename(q)))
    if worst >= a.max:
        print("FAIL 特效指纹相似度 %.3f >= 上限 %.3f: 两首歌长成一个样 (换母题词汇表或组合法, 别调阈值)" % (worst, a.max))
        return 1
    if worst >= WARN_AT:
        print("WARN 特效指纹相似度 %.3f >= %.2f: 手法相近, 看看母题词汇表是否换过" % (worst, WARN_AT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
