# -*- coding: utf-8 -*-
"""
事件包围盒估算（保守）：生成器用它把特效夹进 band，校验器用它检查越界。

覆盖：\\an5/\\an7、\\pos/\\move、\\p 绘图、文字（按 em 宽估算）、\\fscx/\\fscy（含 \\t 内最大值）、
\\frz/\\frx/\\fry（按对角线半径放大）、\\org、\\fax、\\bord/\\blur/\\be、矩形 \\clip（取并集后相交）。
"""
import math, re

TAGBLK = re.compile(r"\{([^}]*)\}")
NUM = r"(-?\d+(?:\.\d+)?)"
R_POS = re.compile(r"\\pos\(\s*" + NUM + r"\s*,\s*" + NUM + r"\s*\)")
R_MOVE = re.compile(r"\\move\(\s*" + NUM + r"\s*,\s*" + NUM + r"\s*,\s*" + NUM + r"\s*,\s*" + NUM)
R_ORG = re.compile(r"\\org\(\s*" + NUM + r"\s*,\s*" + NUM + r"\s*\)")
R_CLIP = re.compile(r"\\i?clip\(\s*" + NUM + r"\s*,\s*" + NUM + r"\s*,\s*" + NUM + r"\s*,\s*" + NUM + r"\s*\)")
R_AN = re.compile(r"\\an(\d)")
R_P = re.compile(r"\\p(\d)")
R_FS = re.compile(r"\\fs" + NUM)


def _vals(tag, s):
    return [float(v) for v in re.findall(r"\\" + tag + NUM, s)]


def strip_t(tags):
    """去掉 \\t(...) 段（支持嵌套括号），得到静态初值部分"""
    out, i = [], 0
    while i < len(tags):
        if tags.startswith("\\t(", i):
            depth, j = 0, i + 2
            while j < len(tags):
                if tags[j] == "(":
                    depth += 1
                elif tags[j] == ")":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            i = j + 1
        else:
            out.append(tags[i]); i += 1
    return "".join(out)


def draw_bbox(d):
    nums = [float(v) for v in re.findall(NUM, d)]
    if len(nums) < 2:
        return None
    xs, ys = nums[0::2], nums[1::2]
    return min(xs), min(ys), max(xs), max(ys)


def event_extent(text, style_fs=40, style_bord=0, style_an=5, em=0.72, scale_x=100, scale_y=100, measure=None, style_font=None):
    """返回 (x0, y0, x1, y1)；无法定位（无 \\pos/\\move）返回 None"""
    tags = "".join(TAGBLK.findall(text))
    body = TAGBLK.sub("", text)
    pts = []
    m = R_MOVE.search(tags)
    if m:
        v = [float(x) for x in m.groups()]
        pts = [(v[0], v[1]), (v[2], v[3])]
    else:
        m = R_POS.search(tags)
        if m:
            pts = [(float(m.group(1)), float(m.group(2)))]
    if not pts:
        return None
    an = int(R_AN.search(tags).group(1)) if R_AN.search(tags) else style_an
    pm = R_P.search(tags)
    static = strip_t(tags)
    ix = _vals("fscx", static) + _vals("fsc", static); iy = _vals("fscy", static) + _vals("fsc", static)
    sx = max(_vals("fscx", tags) + _vals("fsc", tags) + [ix[-1] if ix else scale_x]) / 100
    sy = max(_vals("fscy", tags) + _vals("fsc", tags) + [iy[-1] if iy else scale_y]) / 100
    if pm and int(pm.group(1)) > 0:
        pdiv = 2 ** (int(pm.group(1)) - 1)
        bb = draw_bbox(body)
        if bb is None:
            return None
        w = (bb[2] - bb[0]) / pdiv * sx; h = (bb[3] - bb[1]) / pdiv * sy
        # libass: 绘图原点放在对齐框左上角，未归一化的绘图中心会偏移 (xmin, ymin)
        dshift = (bb[0] / pdiv * sx, bb[1] / pdiv * sy)
    else:
        dshift = (0, 0)
        fs = max(_vals("fs", tags) + [style_fs]) if R_FS.search(tags) else style_fs
        n = max(1, sum(1 if ord(c) > 0x2E80 else 0.55 for c in body.replace("\\N", "")))
        latin = any(ord(c) < 0x2E80 for c in body.replace("\\N", ""))
        w = n * fs * em * sx; h = fs * (1.0 if latin else em) * sy
        if measure:
            fm = re.findall(r"\\fn([^\\}]+)", tags)
            mw = measure(body.replace("\\N", ""), fs, fm[-1] if fm else style_font)
            if mw:
                w = mw * sx
    hw, hh = w / 2, h / 2
    fax = max([abs(v) for v in _vals("fax", tags)] + [0])
    hw += fax * hh * 2
    anim = "\\t(" in tags

    def samples(vals, *names):
        init = [v for n in names for v in _vals(n, static)]
        vs = sorted(set(([init[-1]] if init else [0.0]) + vals))
        if anim and len(vs) > 1:
            lo, hi = vs[0], vs[-1]
            vs = sorted(set(vs + [lo + (hi - lo) * k / 12 for k in range(13)]))
        return vs
    RZ = samples([v for v in _vals("frz", tags) + _vals("fr", tags)], "frz", "fr")
    RX = samples(_vals("frx", tags), "frx"); RY = samples(_vals("fry", tags), "fry")
    bord = max(_vals("bord", tags) + _vals("xbord", tags) + _vals("ybord", tags) + [style_bord])
    blur = max(_vals("blur", tags) + [0]) * 1.2 + max(_vals("be", tags) + [0])
    pad = bord + blur
    ox = {1: 0.5, 4: 0.5, 7: 0.5, 2: 0, 5: 0, 8: 0, 3: -0.5, 6: -0.5, 9: -0.5}[an]
    oy = {7: 0.5, 8: 0.5, 9: 0.5, 4: 0, 5: 0, 6: 0, 1: -0.5, 2: -0.5, 3: -0.5}[an]
    om = R_ORG.search(tags)
    D = 312.5    # libass 透视距离：20000 (26.6 定点) / 64 px
    combos = [(z, x_, y_) for z in RZ for x_ in RX for y_ in RY]
    if len(combos) > 400:
        combos = combos[::len(combos) // 400 + 1]
    boxes = []
    for x, y in pts:
        cx = x + ox * w + dshift[0]; cy = y + oy * h + dshift[1]
        Ox, Oy = (float(om.group(1)), float(om.group(2))) if om else (x, y)
        corners = [(cx + dx - Ox, cy + dy - Oy) for dx in (-hw, 0, hw) for dy in (-hh, 0, hh)]
        X0 = Y0 = 1e9; X1 = Y1 = -1e9
        for az, ax_, ay_ in combos:
            cz, sz = math.cos(math.radians(az)), math.sin(math.radians(az))
            cxr, sxr = math.cos(math.radians(ax_)), math.sin(math.radians(ax_))
            cyr, syr = math.cos(math.radians(ay_)), math.sin(math.radians(ay_))
            for px, py in corners:
                u = px * cz + py * sz; v = -px * sz + py * cz          # frz
                zz = -v * sxr; v = v * cxr                              # frx
                u, zz = u * cyr - zz * syr, u * syr + zz * cyr          # fry
                k = D / max(D + zz, 1e-3) if (ax_ or ay_) else 1.0
                X, Y = Ox + u * k, Oy + v * k
                X0, Y0, X1, Y1 = min(X0, X), min(Y0, Y), max(X1, X), max(Y1, Y)
        boxes.append((X0 - pad, Y0 - pad, X1 + pad, Y1 + pad))
    x0 = min(b[0] for b in boxes); y0 = min(b[1] for b in boxes)
    x1 = max(b[2] for b in boxes); y1 = max(b[3] for b in boxes)
    clips = [tuple(float(v) for v in c) for c in R_CLIP.findall(tags) if not tags.count("\\iclip")]
    if clips:
        cx0 = min(min(c[0], c[2]) for c in clips); cy0 = min(min(c[1], c[3]) for c in clips)
        cx1 = max(max(c[0], c[2]) for c in clips); cy1 = max(max(c[1], c[3]) for c in clips)
        x0, y0, x1, y1 = max(x0, cx0), max(y0, cy0), min(x1, cx1), min(y1, cy1)
    return x0, y0, x1, y1
