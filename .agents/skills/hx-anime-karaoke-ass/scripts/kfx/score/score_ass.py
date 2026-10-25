# -*- coding: utf-8 -*-
"""ASS 侧读取: 解析 Dialogue 与 `; assfx-band:` 表, 以及几何/色彩的小工具.

为什么单独一个模块: 判据全部建立在这些读数之上(事件名、层号、`\p` 路径尺寸、`\t` 缩放终值、
色相), 而它们彼此不依赖  与"哪条判据多少分"分开, 改读数口径不必翻判据表.
"""
import os
import re

# Agent Notes: hx-anime-karaoke-ass 的 scripts/ 按职责分组，并把 5 个超 300 行的模块拆开
# 
# Agent Notes: hx-anime-karaoke-ass 的 scripts/ 按职责分组，并把 5 个超 300 行的模块拆开
# .agents/notes/implemented/process/2026-10-05-karaoke-scripts-grouping.md
BAND_RE = re.compile(r";\s*assfx-band:\s*(\S+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)")
IMG_RE = re.compile(r"\\1c&H([0-9A-Fa-f]{6})&")

def sec(x):
    h, m, s = x.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def parse_ass(path):
    evs, bands = [], {}
    for ln in open(path, encoding="utf-8-sig", errors="replace"):
        if ln.startswith(";"):
            m = BAND_RE.match(ln)
            if m:
                bands[m.group(1)] = tuple(float(g) for g in m.groups()[1:])
            continue
        if not ln.startswith("Dialogue:"):
            continue
        f = ln.split(",", 9)
        if len(f) < 10:
            continue
        try:
            lay = int(f[0].split(":")[1])
        except Exception:
            lay = 0
        evs.append(dict(layer=lay, s=sec(f[1]), e=sec(f[2]), style=f[3], name=f[4], text=f[9]))
    return evs, bands


def ass_hsv(c):
    """&HBBGGRR& -> (hue, sat, val). 注意 ASS 是 BGR 序, 颠倒会把红蓝对调."""
    import colorsys
    b, g, r = int(c[0:2], 16) / 255, int(c[2:4], 16) / 255, int(c[4:6], 16) / 255
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    return h * 360, s, v


def path_of(text):
    m = re.search(r"\\p[123]\}(.*)$", text)
    return m.group(1).strip() if m else None


def size_of(text):
    """
    .agents/notes/implemented/process/2026-10-04-karaoke-skill-genericize.md
返回 (原始路径尺寸, 实际缩放比). 缩放比取 \\t 内的终值, 没有则取初值, 都没有则 None."""
    path = path_of(text)
    if not path:
        return None, None
    # Agent Notes: 卡拉OK skill 通用化  去掉单次制作的事实与清单式铺陈
    # 
    nums = [float(x) for x in re.findall(r"-?\d+\.?\d*", path)]
    if len(nums) < 4:
        return None, None
    raw = max(max(nums[0::2]) - min(nums[0::2]), max(nums[1::2]) - min(nums[1::2]))
    tag = text.split("}")[0]
    ts = re.findall(r"\\t\([^)]*?\\fscx([\d.]+)", tag)
    fx = re.search(r"\\fscx([\d.]+)", tag)
    k = (float(ts[-1]) / 100) if ts else (float(fx.group(1)) / 100 if fx else None)
    return raw, k


def design_table(proj):
    p = os.path.join(proj, "review", "design-table.md")
    if not os.path.exists(p):
        return None, "缺文件"
    txt = open(p, encoding="utf-8").read()
    hdr = next((l for l in txt.splitlines() if l.startswith("|") and "主·出现" in l), None)
    if hdr is None:
        return None, "旧格式(无 主·出现 列)"
    cols = [c.strip() for c in hdr.strip().strip("|").split("|")]
    rows = []
    for l in txt.splitlines():
        if not l.startswith("|") or l.count("|") < len(cols) or "主·出现" in l:
            continue
        if re.match(r"^\|\s*[-: ]+\|", l):
            continue
        cells = [c.strip() for c in l.strip().strip("|").split("|")]
        if len(cells) >= len(cols):
            rows.append(cells[:len(cols)])
    return (cols, rows), None



def seg_hue_shift(evs, gap=6.0):
    """**段落之间**的色相叙事量: 按时间把事件切成连续色块, 取相邻色块的中位色相差。

    踩过的两个坑(2026-10-03):
    (1) 固定 20s 桶  桶边界横跨段落, 桶中位把"相邻两段各一色"混成中间色(真实 43~72° 只报 19°);
    (2) 按句子比较  段内各句同色(这正是想要的), 于是"句子间差"里有大量 0,
        上四分位被摊薄(真实段间 24~148° 只报 15°)。
    正确口径是**按色块的边界切**: 相邻事件同色就并成一块, 色相跳变 > gap 才切块。
    这样"段内恒定"不产生差, "段间跳变"如实计入。
    """
    import collections as _c
    rows = []
    for e in evs:
        if not e["name"].startswith("ly:") or e["layer"] < 23:
            continue
        hs = []
        for m in IMG_RE.finditer(e["text"]):
            h, s, v = ass_hsv(m.group(1).upper())
            if s > 0.25 and v > 0.25:
                hs.append(h)
        if hs:
            rows.append((e["s"], sorted(hs)[len(hs) // 2]))
    rows.sort()
    if len(rows) < 4:
        return 0.0
    blocks = [[rows[0][1]]]
    for _, h in rows[1:]:
        if min(abs(h - blocks[-1][-1]), 360 - abs(h - blocks[-1][-1])) > gap:
            blocks.append([h])
        else:
            blocks[-1].append(h)
    med = [sorted(b)[len(b) // 2] for b in blocks]
    if len(med) < 2:
        return 0.0
    ds = [min(abs(b - a), 360 - abs(b - a)) for a, b in zip(med, med[1:])]
    return sorted(ds)[len(ds) // 2]
