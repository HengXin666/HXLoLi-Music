# -*- coding: utf-8 -*-
"""
母题压字: 贴进 ASS 的图 (\\1img) 到同时显示的歌词字形的间隙.

硬约束 (2026-11-10 定): 间隙 >= MOTIF_GAP px. 本模块是唯一的尺子:
  * 生成器侧 (任何下发 \\1img 的调用方) 下发前用 text_ink_boxes / image_points / min_gap 决定尺寸;
  * 校验器 qa/validate_ass.py 的 [E] 母题压字 调 check_ass() 兜底.
两边同一套函数, 防止"生成器以为放得下、门禁判压字" (判据与实现脱钩).
"""
import collections, os, re

# ---------------------------------------------------------------- 口径
# 硬约束 (2026-11-10 定): 贴进来的图 (\\1img) 的可见像素, 到同时显示的同 band 歌词字形, 间隙 >= MOTIF_GAP px.
# 这里是唯一的尺子. 生成器侧 (任何下发 \\1img 的调用方, 如工程层的 slot 贴图器) 下发前用它决定尺寸,
# 校验器 qa/validate_ass.py 的 [E] 母题压字 用它兜底  两边同一套函数, 防止"生成器以为放得下、门禁判压字".
#
# 口径 (三个函数各管一段):
#   image_points    图: alpha > 8 的像素 (含外发光), 以 \\an5 \\pos 为中心, 乘静态 \\fscx/\\fscy, 转静态 \\frz.
#   text_ink_boxes  字: 同 band 的 ly: 事件里, 填充可见的那几层 (静态 \\1a&HFF& 的纯光晕层不算), 取**静止位置**
#                   (\\pos, 或 \\move 终点) 上每个字的墨迹框 = 字体 glyf 包围盒 + 静态 \\bord.
#                   不含: \\t 里的瞬时放大 (入场/高亮 pop)、\\blur 光晕. 约束的是"静止时不压字".
#                   字体找不到时退回 em 估宽 (0.72em 方块). 这个估值可能偏大 (白缩图) 也可能偏小 (漏压字),
#                   所以不静默: 框的第 6 项记下估宽的字体名, 校验器报 W, 生成器打印 WARN.
#   min_gap         点到框的最小欧氏距离; 点落进框 = 0.
#   时间: 只比显示时间有交叠的字.
# 已知边界: 用 \\move 定位的图、带动画缩放/旋转的图, 只按静态值量 (校验器对 \\move 图报 W 而不是放过).
MOTIF_GAP = 8.0
_ALPHA_MIN = 8
_INK = {}


def _ink_font(fontsdir, family):
    """family -> (scale_fn, glyph_bbox_fn) ; 找不到返回 None. 结果缓存."""
    key = (fontsdir, (family or "").strip().lower())
    if key in _INK:
        return _INK[key]
    found = None
    if fontsdir and os.path.isdir(fontsdir):
        import glob
        from fontTools.ttLib import TTFont
        from fontTools.pens.boundsPen import BoundsPen
        for p in sorted(glob.glob(os.path.join(fontsdir, "*.[ot]t[fc]"))):
            try:
                f = TTFont(p, fontNumber=0)
                names = {r.toUnicode().strip().lower() for r in f["name"].names if r.nameID in (1, 4, 16)}
            except Exception:
                continue
            if key[1] not in names:
                continue
            os2 = f["OS/2"]; asc, desc = os2.usWinAscent, os2.usWinDescent
            cmap = f.getBestCmap(); gs = f.getGlyphSet(); hmtx = f["hmtx"]
            cache = {}

            def bbox(ch, cmap=cmap, gs=gs, hmtx=hmtx, cache=cache):
                if ch not in cache:
                    g = cmap.get(ord(ch))
                    if g is None:
                        cache[ch] = None
                    else:
                        pen = BoundsPen(gs); gs[g].draw(pen)
                        cache[ch] = (hmtx[g][0], pen.bounds)    # (advance, (xMin,yMin,xMax,yMax) | None)
                return cache[ch]
            found = (asc, desc, bbox)
            break
    _INK[key] = found
    return found


def _static_tags(text):
    from assfx.base.geom import strip_t
    return strip_t("".join(re.findall(r"\{([^}]*)\}", text)))


def text_ink_boxes(evs, t0, t1, fontsdir=None):
    """evs: [(start, end, style_dict, text)], style_dict 有 Fontname/Fontsize/ScaleX/ScaleY/Outline/Spacing.
    返回与 [t0,t1) 有交叠、填充可见的字事件的静止墨迹框 [(x0,y0,x1,y1,label,est)].
    est: None = 按字体 glyf 量; 字体名 = 该字体在 fontsdir 里找不到, 按 0.72em 估宽 (不准, 调用方须告警)."""
    out = []
    for s, e, st, text in evs:
        if e <= t0 or s >= t1:
            continue
        body = re.sub(r"\{[^}]*\}", "", text).replace("\\N", "")
        if not body.strip() or re.search(r"\\p[1-9]", text):
            continue
        tags = _static_tags(text)
        if re.search(r"\\1a&HFF&", tags) or (re.search(r"\\alpha&HFF&", tags) and "\\t(" not in text):
            continue                                     # 只有光晕 / 全透明的那层
        mv = re.search(r"\\move\(\s*[-\d.]+\s*,\s*[-\d.]+\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)", tags)
        ps = re.search(r"\\pos\(\s*([-\d.]+)\s*,\s*([-\d.]+)", tags)
        if not (mv or ps):
            continue
        x, y = float((mv or ps).group(1)), float((mv or ps).group(2))
        fs = float((re.findall(r"\\fs([\d.]+)", tags) or [st.get("Fontsize", 40)])[-1])
        sx, sy = float(st.get("ScaleX", 100)) / 100, float(st.get("ScaleY", 100)) / 100
        bord = float((re.findall(r"\\bord([\d.]+)", tags) or [st.get("Outline", 0)])[-1])
        fn = (re.findall(r"\\fn([^\\}]+)", tags) or [st.get("Fontname")])[-1]
        an = int((re.findall(r"\\an(\d)", tags) or [5])[-1])
        F = _ink_font(fontsdir, fn)
        if F:
            asc, desc, bbox = F
            k = fs / (asc + desc)
            adv = [bbox(c) for c in body]
            tw = sum((a[0] if a else (asc + desc) * 0.6) for a in adv) * k * sx
            left = x - tw / 2 if an in (2, 5, 8) else (x if an in (1, 4, 7) else x - tw)
            top = y - fs * sy / 2 if an in (4, 5, 6) else (y if an in (7, 8, 9) else y - fs * sy)
            base = top + asc * k * sy
            cur = left
            for a in adv:
                if a and a[1]:
                    xm, ym, xM, yM = a[1]
                    out.append((cur + xm * k * sx - bord, base - yM * k * sy - bord,
                                cur + xM * k * sx + bord, base - ym * k * sy + bord, body, None))
                cur += (a[0] if a else (asc + desc) * 0.6) * k * sx
        else:                                            # 无字体: em 估宽, 可能偏大也可能偏小, 记下字体名
            n = max(1, sum(1 if ord(c) > 0x2E80 else 0.55 for c in body))
            w, h = n * fs * 0.72 * sx, fs * 0.72 * sy
            out.append((x - w / 2 - bord, y - h / 2 - bord, x + w / 2 + bord, y + h / 2 + bord, body, fn or "?"))
    return out


def image_points(alpha, cx, cy, sx=1.0, sy=1.0, frz=0.0):
    """\\an5 图: alpha>8 像素中心落到画面的坐标 (px, py)."""
    import math
    import numpy as np
    h, w = alpha.shape
    ys, xs = np.nonzero(alpha > _ALPHA_MIN)
    u = (xs + 0.5 - w / 2) * sx; v = (ys + 0.5 - h / 2) * sy
    if frz:
        t = math.radians(frz)
        u, v = u * math.cos(t) + v * math.sin(t), -u * math.sin(t) + v * math.cos(t)
    return cx + u, cy + v


def min_gap(px, py, boxes):
    """点集到框集的最小欧氏距离 (像素); 返回 (gap, 最近的框). 点落进框内 = 0."""
    import numpy as np
    best = (float("inf"), None)
    for b in boxes:
        dx = np.maximum(np.maximum(b[0] - px, px - b[2]), 0); dy = np.maximum(np.maximum(b[1] - py, py - b[3]), 0)
        g = float(np.sqrt(dx * dx + dy * dy).min()) if len(px) else float("inf")
        if g < best[0]:
            best = (g, b)
    return best


def estimated_fonts(boxes):
    """text_ink_boxes 结果里按 em 估宽的字体名 (去重排序); 空 = 全部按字形量."""
    return sorted({b[5] for b in boxes if len(b) > 5 and b[5]})


def check_ass(events, styles, ass_path, fontsdir=None):
    """母题压字校验入口: 图边缘到同时显示的字 < MOTIF_GAP 报错, 估宽与 \\move 图报警告.
    .agents/notes/implemented/feature/2026-11-10-karaoke-motif-text-gap.md
    events/styles 为 validate_ass.load_ass 的结果.
    返回 (errors, warns, measured): measured = [(gap, 行号, band, 图)] 供报告.
    只量 Name=fx:<band> 且用 \\pos 定位的 \\1img 事件; \\move 定位的进 warns (不静默放过); 缺图交给 check_images."""
    errs, warns, measured = [], [], []
    if not any("img(" in ev["Text"] for ev in events):
        return errs, warns, measured                     # 没有贴图: 不引 numpy/pillow
    import numpy as np
    from PIL import Image
    from assfx.base.geom import strip_t
    adir = os.path.dirname(os.path.abspath(ass_path))
    by_band = collections.defaultdict(list)
    for ev in events:
        if ev.get("Name", "").startswith("ly:"):
            by_band[ev["Name"][3:]].append((ev["s"], ev["e"], styles.get(ev["Style"], {}), ev["Text"]))
    for ev in events:
        t = ev["Text"]; m = re.search(r"\\1img\(([^)]+)\)", t); nm = re.match(r"fx:(\S+)", ev.get("Name", ""))
        if not m or not nm:
            continue
        rel, bn = m.group(1).strip(), nm.group(1)
        if not os.path.exists(os.path.join(adir, rel)):
            continue
        pos = re.search(r"\\pos\(\s*([-\d.]+)\s*,\s*([-\d.]+)", t)
        if not pos:
            warns.append(f"L{ev['_ln']} {os.path.basename(rel)} 用 \\move 定位, 母题压字未量 (只量 \\pos)")
            continue
        st = strip_t("".join(re.findall(r"\{([^}]*)\}", t)))
        sx = float((re.findall(r"\\fscx([\d.]+)", st) or [100])[-1]) / 100
        sy = float((re.findall(r"\\fscy([\d.]+)", st) or [100])[-1]) / 100
        frz = float((re.findall(r"\\frz(-?[\d.]+)", st) or [0])[-1])
        al = np.asarray(Image.open(os.path.join(adir, rel)).convert("RGBA"))[:, :, 3]
        px, py = image_points(al, float(pos.group(1)), float(pos.group(2)), sx, sy, frz)
        boxes = text_ink_boxes(by_band.get(bn, []), ev["s"], ev["e"], fontsdir)
        g, b = min_gap(px, py, boxes)
        measured.append((g, ev["_ln"], bn, rel))
        est = estimated_fonts(boxes)
        if est:
            warns.append(f"L{ev['_ln']} {os.path.basename(rel)} 母题压字: 字体 {'/'.join(est)} 不在 fontsdir, 字框按 0.72em 估宽,"
                         f" 实测间隙 {g:.1f}px 可能不准 (估大会白缩图, 估小会漏压字); 带上 --fontsdir 重跑")
        if g < MOTIF_GAP:
            errs.append(f"母题压字 L{ev['_ln']} band {bn} {os.path.basename(rel)}: 到「{b[4]}」间隙 {g:.1f}px < {MOTIF_GAP:g}px"
                        f"  字框=({b[0]:.0f},{b[1]:.0f},{b[2]:.0f},{b[3]:.0f})"
                        "  (图被 band 夹取推过来, 或尺寸超出 band 余量: 缩图或换位, 不要改尺子)")
    return errs, warns, measured
