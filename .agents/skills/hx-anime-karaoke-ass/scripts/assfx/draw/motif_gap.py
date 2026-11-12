# -*- coding: utf-8 -*-
"""
母题压字: 贴进 ASS 的图 (\\1img) 到同时显示的歌词字形的间隙.

硬约束 (2026-11-10 定): 间隙 >= MOTIF_GAP px. 本模块是唯一的尺子:
  * 生成器侧 (任何下发 \\1img 的调用方) 下发前用 text_ink_boxes / image_points / min_gap 决定尺寸;
  * 校验器 qa/validate_ass.py 的 [E] 母题压字 调 check_ass() 兜底.
两边同一套函数, 防止"生成器以为放得下、门禁判压字" (判据与实现脱钩).

维护提醒 (2026-11-10, 连续两次教训): 这道门禁的默认失败方向是**偏松**, 不是偏严.
  831f44c 之前只量缩放初值 (生长动画量成 37.4px, 满尺寸实为 10.8px); 之后又查出没有 \\pos/\\move 的字被静默跳过.
  两次都是"量少了, 所以间隙算大, 门禁绿灯", 而且都不报错不报 W.
  改这里任何口径, 第一件要验的是"会不会漏掉东西" (少量一帧、少算一个字、少算一段缩放), 再验会不会误报;
  量不到的东西一律报出来 (E 或 W), 不许 continue 了事. 自检要能在"故意量少"的变异下变红才算数.
  第三次 (同日): 字体缺字按 0.6em 前进且不出墨迹框, 实渲整行 650px 门禁只算 509px. 三次是同一条线: 漏算一部分 -> 间隙偏大 -> 绿灯.

通用原则 (2026-11-10 定): 本模块的失败方向必须偏严. 量不准时, 宁可把框算大、把间隙算小、报 W 或 E, 也不许算小.
  因为算小的后果是压字放行, 算大的后果只是多报警. 给不出上界的量 (未知后备字体的宽字、推不出的位置) 报 E, 不拿估值硬算.
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
#   时间: 整个显示期内的最小值 (sweep_gap): 图与字各按自己的 \\pos / \\move 轨迹走, 只比同一时刻在屏的字.
#         断点 = 图与字的事件起止 + 各自 \\move 的 t1/t2, 两断点之间一切都是线性 (或静止);
#         段内每 1/48s 采一次 (断点必采), 再从实测最小值里扣掉误差上限 相对速度 x 步长 / 2, 只会偏严.
#   image_scale     图的缩放: 取这条事件里**能达到的最大** \\fscx / \\fscy (见函数注释, 与 geom.event_extent 同口径).
#                   图从小长大时约束的是满尺寸, 不是初值 (2026-11-10 定: 初值口径会让门禁对生长动画完全失效).
# 已知边界: 动画旋转与 \\frx/\\fry 只按静态 \\frz 量并报 W; \\an 不是 5 报 W; \\move 的图带 \\org 旋转时
#           按"旋转中心跟着图走"近似并报 W. 缩放动画按最大缩放量, 与时间无关 (偏严).
MOTIF_GAP = 8.0
SAMPLE_DT = 1 / 48                                   # 段内采样步长 (秒); 误差上限随它线性变小
REFINE_FLOOR = 0.05                                  # 可能决定最小值的段, 加密到误差上限 <= 这个值 (px) 为止
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


# 缺字时 1em 能当上界的区段: CJK 字体按 em 方格设计 (汉字、假名、谚文、全角标点与全角形式的前进都是 1em,
# 墨迹在方格内); 拉丁 / 通用标点的字形宽度也不超过 1em. 2026-11-10 实测: JP 字体缺「测试词」时 libass 后备字
# 平均只占 0.738em (整行实渲 650px, 按 1em 算 716px). 区段外 (emoji、宽符号、组合字符等) 后备字宽可能 > 1em,
# 门禁给不出上界, 调用方报 E 要求补字体, 不拿 1em 硬算 (那样可能算小 = 偏松).
# 默认档是 E: 不在下表任何区段的字 (制表符号、几何图形、⸺ 双倍长破折号、私用区、emoji、组合字符 ...) 一律报 E.
# 表是白名单, 只许放进"后备字形宽度确定不超过 1em"的区段; 拿不准就别加 (加错 = 偏松).
#   0020-024F 基本拉丁 / 拉丁补充 / 扩展 A-B (比例字, 字宽 < 1em)
#   2000-206F 通用标点 (… — ‰ 等, em dash 本身就是 1em; 不含 2E3A/2E3B 双倍、三倍破折号)
#   2E80-9FFF CJK 部首 / 全角标点 3000-303F / 假名 / 注音 / CJK 统一汉字 (CJK 字体按 em 方格设计)
#   AC00-D7AF 谚文音节; F900-FAFF CJK 兼容汉字; FE30-FE4F CJK 兼容形式 (竖排标点)
#   FF00-FFEF 全角 / 半角形式
_EM_BOUNDED = ((0x0020, 0x024F), (0x2000, 0x206F), (0x2E80, 0x9FFF), (0xAC00, 0xD7AF), (0xF900, 0xFAFF), (0xFE30, 0xFE4F), (0xFF00, 0xFFEF))


# 零宽字符 (ZWSP / ZWNJ / ZWJ / 方向标记 / 词连接符 / BOM): 实际渲染宽度 0. 2026-11-11 用户定: 仍按 1em 算 (偏严,
# 可能误报, 但不会漏), 只在报错里写明"含零宽字符, 已按 1em 保守估算", 让人知道框为什么大. 不剔出白名单.
# FEFF 不在白名单区段, 缺字时落默认档 E (同样写明是零宽).
_ZERO_WIDTH = frozenset("\u200b\u200c\u200d\u200e\u200f\u2060\u2061\u2062\u2063\u2064\ufeff")


def _zw_note(tags):
    zw = sorted({ord(t[-1]) for t in tags if t and t[-1] in _ZERO_WIDTH})
    return (f"  [这行含零宽字符 {'/'.join('U+%04X' % o for o in zw)}, 实际宽 0, 已按 1em 保守估算, 框偏大可能误报]" if zw else "")


def _em_bounded(c):
    o = ord(c)
    return any(a <= o <= b for a, b in _EM_BOUNDED)


def _static_tags(text):
    from assfx.base.geom import strip_t
    return strip_t("".join(re.findall(r"\{([^}]*)\}", text)))


def text_ink_boxes(evs, t0, t1, fontsdir=None, unplaced=None):
    """evs: [(start, end, style_dict, text)], style_dict 有 Fontname/Fontsize/ScaleX/ScaleY/Outline/Spacing.
    返回与 [t0,t1) 有交叠、填充可见的字事件的静止墨迹框 [(x0,y0,x1,y1,label,est)].
    est: None = 按字体 glyf 量; 字体名 = 该字体在 fontsdir 里找不到, 按 0.72em 估宽 (不准, 调用方须告警).
    unplaced: 传入 list 时, 有可见字但没有 \\pos / \\move 的事件记成 (start, end, 正文) 追加进去.
      这类字由样式对齐 + 边距排版, 这里不模拟, 量不到它的位置; 不记下来就等于少算一个字 (间隙偏大 = 漏判).
      调用方 (check_ass) 据此报 E. 不传时行为同旧版 (只返回能量的框), 供生成器侧调用."""
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
            if unplaced is not None:
                unplaced.append((s, e, body.strip(), text))
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
            # 字体里没有的字 (cmap 缺字): libass 换后备字体画, 门禁不知道后备字体是哪个. 2026-11-10 前这里按 0.6em 前进、
            # 不出墨迹框 = 少算一个字 (偏松, 静默). 现在按 1em 前进 + 整格 em 方框 (CJK 后备字形接近满格, 偏严),
            # 并在框的第 6 项记 "<字体>:缺字", 调用方报 W. 缺字一律走这条路, 空白字符也不例外 (出一个空 em 框, 偏严),
            # 没有"分类不中就跳过"的出口: 分类只决定报 W 还是报 E, 不决定量不量.
            tw = sum((a[0] if a else (asc + desc)) for c, a in zip(body, adv)) * k * sx
            left = x - tw / 2 if an in (2, 5, 8) else (x if an in (1, 4, 7) else x - tw)
            top = y - fs * sy / 2 if an in (4, 5, 6) else (y if an in (7, 8, 9) else y - fs * sy)
            base = top + asc * k * sy
            cur = left
            for c, a in zip(body, adv):
                if a is None:
                    em_w = (asc + desc) * k * sx
                    tag = ":缺字" if _em_bounded(c) else ":缺字无上界"
                    out.append((cur - bord, top - bord, cur + em_w + bord, top + fs * sy + bord, body, f"{fn}{tag}{c}"))
                    cur += em_w
                    continue
                if a and a[1]:
                    xm, ym, xM, yM = a[1]
                    out.append((cur + xm * k * sx - bord, base - yM * k * sy - bord,
                                cur + xM * k * sx + bord, base - ym * k * sy + bord, body, None))
                cur += a[0] * k * sx
        else:                                            # 无字体: em 估宽, 可能偏大也可能偏小, 记下字体名
            n = max(1, sum(1 if ord(c) > 0x2E80 else 0.55 for c in body))
            w, h = n * fs * 0.72 * sx, fs * 0.72 * sy
            out.append((x - w / 2 - bord, y - h / 2 - bord, x + w / 2 + bord, y + h / 2 + bord, body, fn or "?"))
    return out


_NUM = r"(-?(?:\d+(?:\.\d*)?|\.\d+))"
# 顺序要紧: fscx / fscy 必须排在 fsc 前, 否则 "\fscx100" 会被当成 "\fsc" 加残渣 "x100".
_R_SCALE = re.compile(r"\\(fscx|fscy|fsc)\s*" + _NUM + r"?")
_R_RESET = re.compile(r"\\r([^\\})]*)")         # \r 或 \r<样式名>; 不吃 \rnd 之类 (ASS 没有) 也不吃 \t( 里的
_R_ROT_ANY = re.compile(r"\\(frx|fry|frz|fr)(?![a-z])\s*" + _NUM)


def image_scale(text, style=None, styles=None):
    """贴图事件能达到的最大缩放 (sx, sy), 单位 1.0 = 100%. 返回 (sx, sy, warns).

    量什么: libass 画这张图时 \\fscx / \\fscy 在事件显示期内可能取到的最大值. 门禁要的是"最坏的那一帧",
    所以取最大而不是初值: 一张 \\fscx30 → \\t(\\fscx100) 的图, 满尺寸那几帧才是压字的那几帧.
    怎么算: 把下面每种写法给出的候选值收进一个集合, 各取 |值| 的最大 (负值 = 镜像, 尺寸按绝对值).
      1  \\fscx<N>            只动 x
      2  \\fscy<N>            只动 y
      3  \\fsc<N>             x、y 一起. libass 实际把 \\fsc 当"复位到样式值"而忽略参数, VSFilter 系当两轴都设 N;
                             两种读法都收 (N 和样式值都进候选), 宁严勿漏
      4  \\fscx \\fscy \\fsc 不带数   复位到样式值
      5  \\r / \\r<样式名>      复位到 (该) 样式值; 样式名查不到报 W, 并按 100 收
      6  样式 ScaleX / ScaleY 没有任何静态缩放标签时的起点
      7  以上任一写在 \\t(...) 里: 任意个数、首尾相连、嵌套括号、带 accel 或起止时间都一样,
         因为是对整条事件文本做正则, 不去配对括号 (\\t 内插值是两端之间单调, 极值必在端点, 端点都在文本里)
      8  多个覆写块 {..}{..}: 拼起来看, 所有静态值都收 (libass 只让最后一个生效, 这里偏严, 不会漏)
      9  首个静态值之前的样式值不算进候选 (它从未显示过), 不然 "\\fscx50" 的图在 100% 样式下会被误判成 100%
    边界: 不认识的写法不会被当成缩放; 本函数只放大判断 (取并集的最大), 不会让一张图量得比 libass 画的小.
    \\fs (字号) 对 \\1img 无效, 不在此列."""
    from assfx.base.geom import strip_t
    style = style or {}; styles = styles or {}; warns = []
    tags = "".join(re.findall(r"\{([^}]*)\}", text))
    st_x = float(style.get("ScaleX", 100)); st_y = float(style.get("ScaleY", 100))
    cx, cy = [], []                                   # 候选 (百分数)

    def resets(name):
        if not name.strip():
            return st_x, st_y
        o = styles.get(name.strip())
        if o is None:
            warns.append(f"\\r{name.strip()} 样式查不到, 缩放按 100 收")
            return 100.0, 100.0
        return float(o.get("ScaleX", 100)), float(o.get("ScaleY", 100))

    for m in _R_SCALE.finditer(tags):                 # 写法 1-4, 7: 静态与 \t 内一视同仁
        tag, v = m.group(1), m.group(2)
        if v is None:
            if tag in ("fscx", "fsc"): cx.append(st_x)
            if tag in ("fscy", "fsc"): cy.append(st_y)
            continue
        v = float(v)
        if tag in ("fscx", "fsc"): cx.append(v)
        if tag in ("fscy", "fsc"): cy.append(v)
        if tag == "fsc": cx.append(st_x); cy.append(st_y)
    for m in _R_RESET.finditer(tags):                 # 写法 5
        rx, ry = resets(m.group(1)); cx.append(rx); cy.append(ry)
    static = strip_t(tags)                            # 写法 6, 8, 9: 没有静态 x (或 y) 标签时, 起点是样式值
    if not re.search(r"\\fsc(x|(?![xy]))", static) and not _R_RESET.search(static): cx.append(st_x)
    if not re.search(r"\\fsc(y|(?![xy]))", static) and not _R_RESET.search(static): cy.append(st_y)
    return max(abs(v) for v in cx) / 100, max(abs(v) for v in cy) / 100, warns


def image_rotation(text):
    """贴图事件的静态 \\frz (含别名 \\fr) 与旋转中心. 返回 (frz, org_xy | None, warns).
    \\org 只在有旋转时才改变图的位置 (它是旋转中心, 不是位移), 所以 frz == 0 时忽略 \\org.
    动画旋转 (\\t 里的 \\frz/\\fr/\\frx/\\fry) 与静态 \\frx/\\fry (透视) 本尺子不建模: 按静态 \\frz 量并报 W, 不静默."""
    from assfx.base.geom import strip_t
    tags = "".join(re.findall(r"\{([^}]*)\}", text)); static = strip_t(tags); warns = []
    zs = [float(v) for t, v in _R_ROT_ANY.findall(static) if t in ("frz", "fr")]
    frz = zs[-1] if zs else 0.0
    if any(float(v) for t, v in _R_ROT_ANY.findall(static) if t in ("frx", "fry")):
        warns.append("有 \\frx/\\fry 透视旋转, 只按平面 \\frz 量")
    s_all = sorted({(t if t != "fr" else "frz", float(v)) for t, v in _R_ROT_ANY.findall(tags)})
    s_st = sorted({(t if t != "fr" else "frz", float(v)) for t, v in _R_ROT_ANY.findall(static)})
    if s_all != s_st:
        warns.append("\\t 里有旋转动画, 只按静态旋转量")
    org = re.findall(r"\\org\(\s*" + _NUM + r"\s*,\s*" + _NUM, tags)
    return frz, ((float(org[-1][0]), float(org[-1][1])) if org and frz else None), warns


def image_points(alpha, cx, cy, sx=1.0, sy=1.0, frz=0.0, org=None):
    """\\an5 图: alpha>8 像素中心落到画面的坐标 (px, py).
    org: 旋转中心 (\\org); None = 绕图中心 (\\pos). 有 \\org 时图整体绕它转, 位置会跟着变."""
    import math
    import numpy as np
    h, w = alpha.shape
    ys, xs = np.nonzero(alpha > _ALPHA_MIN)
    u = (xs + 0.5 - w / 2) * sx; v = (ys + 0.5 - h / 2) * sy
    if frz:
        t = math.radians(frz)
        ox, oy = org if org else (cx, cy)
        u, v = u + cx - ox, v + cy - oy
        u, v = u * math.cos(t) + v * math.sin(t), -u * math.sin(t) + v * math.cos(t)
        return ox + u, oy + v
    return cx + u, cy + v


def min_gap(px, py, boxes):
    """点集到框集的最小欧氏距离 (像素); 返回 (gap, 最近的框). 点落进框内 = 0."""
    import numpy as np
    # 2026-11-13 #13: 由逐框 python 循环改成一次性 (点 x 框) 矩阵, 结果逐位相同 (同值取第一个框, 与原循环的 "<" 一致);
    # 矢量件点多、事件多, 原写法在 dev 上 8 分钟跑不完. 大矩阵分块, 避免内存爆.
    if not len(px) or not boxes:
        return (float("inf"), None)
    B = np.array([b[:4] for b in boxes], float)
    best_g, best_i = float("inf"), None
    step = max(1, 2000000 // max(1, len(boxes)))
    for i in range(0, len(px), step):
        x = px[i:i + step, None]; y = py[i:i + step, None]
        dx = np.maximum(np.maximum(B[None, :, 0] - x, x - B[None, :, 2]), 0)
        dy = np.maximum(np.maximum(B[None, :, 1] - y, y - B[None, :, 3]), 0)
        g = np.sqrt(dx * dx + dy * dy).min(0)
        j = int(g.argmin())
        if g[j] < best_g or (g[j] == best_g and best_i is not None and j < best_i):
            best_g, best_i = float(g[j]), j
    return (best_g, boxes[best_i]) if best_i is not None and best_g < float("inf") else (float("inf"), None)


def estimated_fonts(boxes):
    """text_ink_boxes 结果里按 em 估宽的字体名 (去重排序); 空 = 全部按字形量."""
    return sorted({b[5] for b in boxes if len(b) > 5 and b[5]})


def track(text, dur_ms):
    """事件的定位轨迹: (x0, y0, x1, y1, t1, t2), t1/t2 为相对事件起点的毫秒. 找不到 \\pos / \\move 返回 None.
    量什么: libass 每一时刻把这条事件画在哪. \\pos(x,y) = 不动 (x0=x1, t1=t2=0).
    \\move(x0,y0,x1,y1[,t1,t2]): t1 之前停在起点, t2 之后停在终点, 中间线性 (ASS 的 \\move 没有 accel).
    边界: 右括号可缺 (libass 容忍 "\\move(1,2,3,4}", 2026-11-10 命运石之门 ファティマ 有 20 条); 不带 t1/t2 或两者都 <= 0 = 整个事件时长 (libass 同口径); t1 > t2 时交换 (libass 同口径);
    多个 \\pos/\\move 时取第一个 (libass 只认第一个)."""
    tags = "".join(re.findall(r"\{([^}]*)\}", text))
    m = re.search(r"\\move\(\s*" + r"\s*,\s*".join([_NUM] * 4) + r"(?:\s*,\s*" + _NUM + r"\s*,\s*" + _NUM + r")?\s*\)?", tags)
    p = re.search(r"\\pos\(\s*" + _NUM + r"\s*,\s*" + _NUM, tags)
    if m and (not p or m.start() < p.start()):
        x0, y0, x1, y1 = (float(v) for v in m.groups()[:4])
        t1, t2 = (float(m.group(5)), float(m.group(6))) if m.group(5) is not None else (0.0, 0.0)
        if t1 <= 0 and t2 <= 0:
            t1, t2 = 0.0, float(dur_ms)
        if t1 > t2:
            t1, t2 = t2, t1
        return (x0, y0, x1, y1, t1, t2)
    if p:
        x, y = float(p.group(1)), float(p.group(2))
        return (x, y, x, y, 0.0, 0.0)
    return None


def _at(trk, ms):
    """轨迹在相对毫秒 ms 时的位置."""
    x0, y0, x1, y1, t1, t2 = trk
    if ms <= t1 or t2 <= t1:
        u = 0.0 if ms <= t1 and t2 > t1 else 1.0
    elif ms >= t2:
        u = 1.0
    else:
        u = (ms - t1) / (t2 - t1)
    return x0 + (x1 - x0) * u, y0 + (y1 - y0) * u


def _vel(trk, ms):
    """轨迹在 ms 时刻的速度 (px/s); 断点上调用方传段中点, 所以不会落在 t1/t2 上."""
    x0, y0, x1, y1, t1, t2 = trk
    if t2 > t1 and t1 < ms < t2:
        k = 1000.0 / (t2 - t1)
        return (x1 - x0) * k, (y1 - y0) * k
    return 0.0, 0.0


def text_ink_tracks(evs, t0, t1, fontsdir=None, unplaced=None):
    """同 text_ink_boxes, 但按事件分组并带上轨迹: [(start, end, boxes, trk)].
    量什么: 每条字事件在屏期间的墨迹框随时间的位置.
    怎么算: boxes 是静止位置 (\\move 终点) 的墨迹框; 某时刻的实际位置 = boxes + (_at(trk) - 终点).
    边界: 没有 \\pos / \\move 的字量不到框 (text_ink_boxes 记进 unplaced, 由调用方报 E);
          有框但 track 解析不出 (理论上不会, 两边认同一组标签) 时按静止处理, 不丢弃; 没有墨迹的事件跳过."""
    out = []
    for ev in evs:
        s, e, st, text = ev
        if e <= t0 or s >= t1:
            continue
        bx = text_ink_boxes([ev], s, e, fontsdir, unplaced)
        if not bx:
            continue
        # 没有 \pos / \move 的字 (按样式对齐排版) 是静止的: 墨迹框已经是它的画面位置, 偏移恒为 0.
        # 不能因为没有轨迹就丢掉这条字, 否则这条字永远不参与比较 = 静默假通过.
        trk = track(text, (e - s) * 1000) or (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        out.append((s, e, bx, trk))
    return out


def sweep_gap(px, py, img_s, img_e, img_trk, tracks, dt=SAMPLE_DT, stop_at=None):
    """图在整个显示期 [img_s, img_e) 内到同时在屏的字的最小间隙的**下界**.
    px/py: 图停在轨迹终点 (img_trk 的 x1,y1) 时的像素坐标; tracks: text_ink_tracks 的结果.
    返回 dict: lower (下界, 门禁比的就是它) 以及决定下界的那一段的 raw (段内采样实测最小)、t (raw 出现的时刻, 秒)、
               bound (该段误差上限 L*h/2)、box (最近的字框); samples (总采样数); dt_min (实际用到的最小步长, 秒).
               同时没有字: lower = raw = inf.

    怎么算:
      1 断点 = 图与每条字事件的起止 + 各自 \\move 的 t1/t2 (截到图的显示期内). 两个断点之间, 在屏的字集合不变,
        每个对象要么静止要么匀速直线, 所以图与每个字的相对运动是匀速直线.
      2 段 [a, b) 等分成 n = ceil((b - a) / dt) 步 (步长 h <= dt), 采 a, a+h, ..., b-ε 共 n+1 个点 (断点必采).
        整段都没有相对运动 (L = 0) 时只采段首, 结果是精确值.
        加密: 某段的 实测 - 上限 比目前的下界还小 (它可能决定最小值) 时, 该段步长减半重采, 直到上限 <= REFINE_FLOOR
        (0.05px). 所以报出的下界离真值不超过 0.05px; 不加密的话, 0.8px 的上限会把实测 8.5px 的图判红.
      3 误差上限: 一个点到一个框的距离, 在相对速度 v 下是 |v|-Lipschitz 的; 取最小值不增大 Lipschitz 常数,
        所以间隙函数在段内是 L-Lipschitz, L = max |v_图 - v_字| (段内在屏的字). 两相邻采样点之间漏掉的下降
        不超过 L * h / 2. 下界 = min(各段的 采样最小 - L_段 * h_段 / 2), 只会比真值小 (偏严).
    边界: 只建模平移; 缩放用调用方给的最大缩放 (偏严); 旋转按静态值 (调用方报 W).
    stop_at: 下界已经 <= 它就提前返回 (下界只会更小, 不改变"是否 < 门槛"). 默认 None = 扫完, 贴图口径不变."""
    import math
    import numpy as np
    INF = float("inf")
    res = {"lower": INF, "raw": INF, "t": None, "bound": 0.0, "box": None, "samples": 0, "dt_min": dt}
    if not tracks or not len(px):
        return res
    ex, ey = img_trk[2], img_trk[3]
    bps = {img_s, img_e, img_s + img_trk[4] / 1000, img_s + img_trk[5] / 1000}
    for s, e, _, trk in tracks:
        bps |= {s, e, s + trk[4] / 1000, s + trk[5] / 1000}
    bps = sorted(b for b in bps if img_s <= b <= img_e)
    for a, b in zip(bps, bps[1:]):
        if b - a <= 1e-9:
            continue
        mid = (a + b) / 2
        vis = [tr for tr in tracks if tr[0] <= mid < tr[1]]
        if not vis:
            continue
        vix, viy = _vel(img_trk, (mid - img_s) * 1000)
        L = max(math.hypot(vix - _vel(tr[3], (mid - tr[0]) * 1000)[0], viy - _vel(tr[3], (mid - tr[0]) * 1000)[1])
                for tr in vis)
        step = dt
        while True:
            n = 1 if L == 0 else max(1, math.ceil((b - a) / step - 1e-9))
            h = (b - a) / n
            ts = [a] if L == 0 else [a + k * h for k in range(n)] + [b - 1e-6]
            seg_raw, seg_t, seg_box = INF, None, None
            for t in ts:
                ix, iy = _at(img_trk, (t - img_s) * 1000)
                dx_i, dy_i = ix - ex, iy - ey
                boxes = []
                for s, e, bx, trk in vis:
                    tx, ty = _at(trk, (t - s) * 1000)
                    ox, oy = tx - trk[2] - dx_i, ty - trk[3] - dy_i   # 字相对图的偏移: 等价于图不动、字反向移
                    boxes += [(q[0] + ox, q[1] + oy, q[2] + ox, q[3] + oy) + tuple(q[4:]) for q in bx]
                g, bb = min_gap(px, py, boxes)
                res["samples"] += 1
                if g < seg_raw:                      # 报告用的字框换回画面坐标 (加回图的位移)
                    seg_raw, seg_t = g, t
                    seg_box = (bb[0] + dx_i, bb[1] + dy_i, bb[2] + dx_i, bb[3] + dy_i) + tuple(bb[4:]) if bb else None
            bound = L * h / 2
            # 可能决定最小值的段才加密: 这段的 实测-上限 比目前的下界还小时, 步长减半重采, 直到上限 <= REFINE_FLOOR.
            # 这样报出来的下界离真值不超过 REFINE_FLOOR, 不会因为 0.8px 的上限把实测 8.5px 的图判红.
            # 加密只让上限变小, 下界仍然成立, 所以不改变"只会偏严".
            if L == 0 or bound <= REFINE_FLOOR or seg_raw - bound >= res["lower"]:
                break
            step /= 2
        res["dt_min"] = min(res["dt_min"], h if L else res["dt_min"])
        if seg_raw - bound < res["lower"] or res["t"] is None and seg_raw < INF:
            # 报告的 raw / t / bound / box 都取决定下界的那一段, 不跨段拼凑
            res.update(lower=max(0.0, seg_raw - bound), raw=seg_raw, t=seg_t, bound=bound, box=seg_box)
        if stop_at is not None and res["lower"] <= stop_at:
            break
    return res


def _play_res(ass_path):
    """[Script Info] 的 PlayResX/PlayResY; 缺任一个返回 None (libass 的缺省推导规则不在这里模拟, 调用方报 E)."""
    info = {}
    try:
        for raw in open(ass_path, encoding="utf-8-sig"):
            if raw.startswith("[") and info.get("_in"):
                break
            if raw.strip() == "[Script Info]":
                info["_in"] = 1
            elif info.get("_in") and ":" in raw and not raw.startswith(";"):
                k, v = raw.split(":", 1); info[k.strip()] = v.strip()
        return float(info["PlayResX"]), float(info["PlayResY"])
    except (OSError, KeyError, ValueError):
        return None


def infer_position(ev, style, play_res, events, fontsdir=None):
    """没有 \\pos / \\move 的字, 按 libass 的排版规则推出它的定位点. 返回 (x, y, an) 或 推不出的原因 (str).
    量什么: libass 对无显式定位的事件, 位置只由 对齐 (\\an 或样式 Alignment) + 边距 (事件 MarginL/R/V 非 0 时覆盖样式)
            + PlayResX/Y 决定; ASS 没有"沿用上一条事件的 \\pos"这种语义, 每条事件独立.
    怎么算: 横向 an 1/4/7 x = MarginL, 2/5/8 x = (MarginL + PlayResX - MarginR) / 2, 3/6/9 x = PlayResX - MarginR;
            纵向 an 1-3 y = PlayResY - MarginV (框底), 4-6 y = PlayResY / 2 (中线, 不看 MarginV), 7-9 y = MarginV (框顶).
    推不出 (调用方报 E) 的情形, 都是 libass 的位置取决于这里没建模的东西:
      * 没有 PlayResX/Y (libass 有缺省推导, 不模拟);
      * 多行 (\\N / \\n) 或单行宽度超过 PlayResX - MarginL - MarginR (会自动换行, 行数由 WrapStyle 定);
      * 同 Layer 有时间交叠的另一条无定位事件 (libass 碰撞检测会把它上下挤开, 位置取决于事件顺序);
      * 旧式对齐标签 \\a<n>."""
    text = ev["Text"]
    tags = _static_tags(text)
    if play_res is None:
        return "文件没有 PlayResX/PlayResY"
    if re.search(r"\\a\d", tags):
        return "用了旧式对齐 \\a<n>"
    if re.search(r"\\[Nn]", text):
        return "多行 (\\N), 行位置取决于换行排版"
    W, H = play_res
    def mg(k):
        v = int(float(ev.get(k) or 0))
        return v if v else int(float(style.get(k, 0) or 0))
    ml, mr, mv = mg("MarginL"), mg("MarginR"), mg("MarginV")
    an = int((re.findall(r"\\an(\d)", tags) or [style.get("Alignment", 2)])[-1])
    for o in events:
        if o is ev or o.get("Layer") != ev.get("Layer") or o["e"] <= ev["s"] or o["s"] >= ev["e"]:
            continue
        ot = o["Text"]
        if re.search(r"\\(pos|move)\(", ot) or re.search(r"\\p[1-9]", ot) or not re.sub(r"\{[^}]*\}", "", ot).strip():
            continue
        return f"同 Layer {ev.get('Layer')} 有时间交叠的无定位事件 L{o['_ln']} (libass 碰撞检测会挤开, 位置取决于事件顺序)"
    col = an % 3
    x = ml if col == 1 else (W - mr if col == 0 else (ml + W - mr) / 2)
    y = H - mv if an <= 3 else (H / 2 if an <= 6 else mv)
    bx = text_ink_boxes([(ev["s"], ev["e"], style, "{\\an%d\\pos(%g,%g)}" % (an, x, y) + text)], ev["s"], ev["e"], fontsdir)
    if bx and max(b[2] for b in bx) - min(b[0] for b in bx) > W - ml - mr + 1:
        return "单行宽度超过 PlayResX - 边距, libass 会自动换行"
    return x, y, an


def check_ass(events, styles, ass_path, fontsdir=None):
    """母题压字校验入口: 图边缘到同时显示的字在整个显示期内任一时刻 < MOTIF_GAP 报错 (sweep_gap); 估宽、推算定位、1em 缺字报警告; 推不出定位、缺字无上界报错.
    .agents/notes/implemented/feature/2026-11-10-karaoke-motif-text-gap.md
    events/styles 为 validate_ass.load_ass 的结果.
    返回 (errors, warns, measured): measured = [(gap, 行号, band, 图, sx, sy, sweep)] 供报告,
    gap 是整个显示期内的间隙下界 (sweep_gap 的 lower), sx/sy 是量时用的最大缩放, sweep 是 sweep_gap 的完整结果.
    量 Name=fx:<band> 且用 \\pos 或 \\move 定位的 \\1img 事件 (两者都没有的进 warns); 缺图交给 check_images."""
    errs, warns, measured = [], [], []
    if not any("img(" in ev["Text"] or _R_DRAW.search(ev["Text"]) for ev in events):
        return errs, warns, measured                     # 没有贴图也没有矢量件: 不引 numpy/pillow
    import numpy as np
    from PIL import Image
    adir = os.path.dirname(os.path.abspath(ass_path))
    by_band = collections.defaultdict(list)
    by_band_ev = collections.defaultdict(list)          # 矢量件按层分前后景时要用到字事件本身 (Layer / 行号)
    play_res = None
    why_unplaced, inferred = {}, collections.defaultdict(list)   # 原文 -> 推不出的原因; band -> [(行号, x, y)]
    for ev in events:
        if ev.get("Name", "").startswith("ly:"):
            st, tx = styles.get(ev["Style"], {}), ev["Text"]
            if not re.search(r"\\(pos|move)\(", _static_tags(tx)) and re.sub(r"\{[^}]*\}", "", tx).strip() \
                    and not re.search(r"\\p[1-9]", tx):
                # 无显式定位: 按 libass 排版规则推算 (infer_position), 推得出就补一个 \\pos 再量 (报 W), 推不出留给下面报 E
                play_res = play_res or _play_res(ass_path)
                r = infer_position(ev, st, play_res, events, fontsdir)
                if isinstance(r, tuple):
                    tx = "{\\an%d\\pos(%g,%g)}" % (r[2], r[0], r[1]) + tx
                    inferred[ev["Name"][3:]].append((ev["_ln"], r[0], r[1], ev["s"], ev["e"],
                                                     re.sub(r"\{[^}]*\}", "", ev["Text"]).replace("\\N", "")))
                else:
                    why_unplaced[tx] = f"L{ev['_ln']}: {r}"
            by_band[ev["Name"][3:]].append((ev["s"], ev["e"], st, tx))
            by_band_ev[ev["Name"][3:]].append((ev, (ev["s"], ev["e"], st, tx)))
    for ev in events:
        t = ev["Text"]; m = re.search(r"\\1img\(([^)]+)\)", t); nm = re.match(r"fx:(\S+)", ev.get("Name", ""))
        if not m or not nm:
            continue
        rel, bn = m.group(1).strip(), nm.group(1)
        if not os.path.exists(os.path.join(adir, rel)):
            continue
        trk = track(t, (ev["e"] - ev["s"]) * 1000)
        if not trk:
            warns.append(f"L{ev['_ln']} {os.path.basename(rel)} 没有 \\pos / \\move, 母题压字未量")
            continue
        # 缩放取事件内能达到的最大值 (image_scale), 不是剥掉 \\t 后的初值: 2026-11-10 p31 水球
        # \\fscx30 → \\t(\\fscx100) 时初值口径量 37.4px、满尺寸实为 10.8px, 门禁对生长动画等于失效.
        stl = styles.get(ev["Style"], {})
        sx, sy, sw = image_scale(t, stl, styles)
        frz, org, rw = image_rotation(t)
        an = (re.findall(r"\\an(\d)", t) or [str(stl.get("Alignment", 5))])[-1]
        al = np.asarray(Image.open(os.path.join(adir, rel)).convert("RGBA"))[:, :, 3]
        if org and trk[:2] != trk[2:4]:
            # \\org 是画面绝对坐标, 图在 \\move 时旋转中心不跟着走: 点集按终点时刻 (图在终点、绕 org 转) 算出后
            # 整体平移, 途中的旋转半径变化没建模. 不静默, 报 W.
            rw = rw + ["\\move 的图带 \\org 旋转, 按终点时刻的旋转中心量 (近似)"]
        px, py = image_points(al, trk[2], trk[3], sx, sy, frz, org)
        unplaced = []
        tracks = text_ink_tracks(by_band.get(bn, []), ev["s"], ev["e"], fontsdir, unplaced)
        boxes = [q for tr in tracks for q in tr[2]]
        if unplaced:
            # 为什么是 E 不是 W: 量不到的字等于没算进去, 间隙只会算大 (漏判压字), 与估宽保持 [E] 同理;
            # 报 W 的话下面的间隙数字照样会绿, 看报告的人会以为量过了.
            u0 = unplaced[0]
            errs.append(f"母题压字 缺显式定位 L{ev['_ln']} band {bn} {os.path.basename(rel)}: 同 band 有 {len(unplaced)} 条字没有 \\pos / \\move"
                        f" 且按 libass 规则推不出位置 (首条「{u0[2][:12]}」{u0[0]:.2f}-{u0[1]:.2f}s, {why_unplaced.get(u0[3], '原因未记录')}),"
                        " 量不到位置, 下面的间隙不含它们、不可信  (给这些字加 \\pos, 或把图移出该 band; 不要改尺子)")
        inf = [r for r in inferred.get(bn, []) if r[3] < ev["e"] and r[4] > ev["s"]]
        # 两种情形的报错分开写, 被拦的人才知道该改什么: 推不出 = "缺显式定位" (上面的 E); 推得出 = 正常量, 压字时 E 里注明"位置是推算的"
        if inf:                                          # 推算不是量, 不静默: 报 W 并给出推算点
            warns.append(f"L{ev['_ln']} {os.path.basename(rel)} 母题压字: 同 band {len(inf)} 条字没有 \\pos / \\move,"
                         f" 按 libass 对齐 + 边距推算定位点量 (首条 L{inf[0][0]} 推为 ({inf[0][1]:g},{inf[0][2]:g}))")
        if boxes:                                        # 同时没有字 = 不可能压字, 量不准也无所谓, 不刷屏
            for w_ in sw + rw + ([f"\\an{an} 不是 5, 按 \\an5 (中心) 量"] if an != "5" else []):
                warns.append(f"L{ev['_ln']} {os.path.basename(rel)} 母题压字: {w_}")
        # 整个显示期的最小值 (sweep_gap): 2026-11-10 第 8 句矢量手从下方升起, 终点 23.4px、起点 0.0px,
        # 只量终点 (或只量 \\pos) 的口径会把升起途中压中文行判成通过, 和"只量初始缩放"是同一类错.
        sw_ = sweep_gap(px, py, ev["s"], ev["e"], trk, tracks)
        g, b = sw_["lower"], sw_["box"]
        measured.append((g, ev["_ln"], bn, rel, sx, sy, sw_))
        est = estimated_fonts(boxes)
        nob = [x for x in est if ":缺字无上界" in x]
        gaps_ = [x for x in est if ":缺字" in x and x not in nob]; est = [x for x in est if ":缺字" not in x]
        if nob:
            # 为什么是 E: 区段外的缺字 (emoji、宽符号) 后备字宽可能超过 1em, 按 1em 量可能算小 = 偏松; 给不出上界就不放行
            errs.append(f"母题压字 缺字无上界 L{ev['_ln']} band {bn} {os.path.basename(rel)}: {'/'.join(nob)} 不在字体里,"
                        " 且不在 1em 能当上界的区段 (CJK / 假名 / 谚文 / 全角 / 拉丁), 后备字宽未知, 间隙不可信  (补一个含这些字的字体到 fontsdir; 不要改尺子)" + _zw_note(nob))
        if gaps_:
            warns.append(f"L{ev['_ln']} {os.path.basename(rel)} 母题压字: {'/'.join(gaps_)} (字体里没有这些字, libass 会换后备字体),"
                         f" 这些字按 1em 方格量 (这些区段 1em 是上界), 实测间隙 {g:.1f}px 偏严; 换覆盖这些字的字体可消除" + _zw_note(gaps_))
        if est:
            warns.append(f"L{ev['_ln']} {os.path.basename(rel)} 母题压字: 字体 {'/'.join(est)} 不在 fontsdir, 字框按 0.72em 估宽,"
                         f" 实测间隙 {g:.1f}px 可能不准 (估大会白缩图, 估小会漏压字); 带上 --fontsdir 重跑")
        inf_hit = [r for r in inf if b and r[5] == b[4]]   # 最近的字是不是推算出来的那条 (按正文对)
        if g < MOTIF_GAP:
            errs.append(f"母题压字 L{ev['_ln']} band {bn} {os.path.basename(rel)}: 到「{b[4]}」间隙 {g:.1f}px < {MOTIF_GAP:g}px"
                        f" (按最大缩放 {sx*100:.0f}%x{sy*100:.0f}% 量; 最近时刻 {sw_['t']:.2f}s,"
                        f" 采样实测 {sw_['raw']:.1f}px 减误差上限 {sw_['bound']:.2f}px)"
                        f"  字框=({b[0]:.0f},{b[1]:.0f},{b[2]:.0f},{b[3]:.0f})"
                        + (f"  [这条字没有显式定位, 位置按 libass 对齐+边距推算 (L{', L'.join(str(r[0]) for r in inf_hit)});"
                           " 推算口径由 libass 实渲自检保证误差 <= 2px, 若怀疑推算错, 先给字写 \\pos 再量]" if inf_hit else "")
                        + (f"  [最近的框是缺字 {b[5][-1]!r} 的 1em 保守框]" + _zw_note([b[5]])
                           if b[5] and ":缺字" in b[5] else "")
                        + "  (图被 band 夹取推过来, 或尺寸超出 band 余量: 缩图或换位, 不要改尺子)")
    check_vectors(events, styles, ass_path, fontsdir, by_band_ev, errs, warns, measured)
    return errs, warns, measured


# ---------------------------------------------------------------- 矢量母题 (\p 绘图), known-gaps #13
# 2026-11-12 定: 矢量件按路径采样取外框, 不按控制点, 不先光栅化. 和贴图走同一套 sweep_gap / text_ink_tracks,
# 字侧没有第二套取框逻辑. 失败方向偏严: \bord / \blur 直接从间隙里扣 (vector_pad), 不展开成像素.
VEC_STEP = 0.5            # 边界取点间距 (px): 点到框距离的采样误差 <= VEC_STEP / 2
VEC_FLAT = 0.1            # 贝塞尔细分的弦误差上限 (px)
VEC_FILL_GRID = 4.0       # 可见填充的内部网格 (px): 字框整块落在形状里面时间隙记 0, 只看边界会漏.
#   为什么 4px 够: 字框与填充部分相交时, 要么有边界点落进字框 (边界点距 0.5px), 要么字框整块在填充里;
#   整块在里面的字框只要两边都 >= 网格距, 就必含一个网格点. check_vectors 用 min(4, 最小字框边) 当网格距, 不靠假设.
_R_DRAW = re.compile(r"\\p([1-9])[^}]*\}([^{]*)")


def _cubic(p0, p1, p2, p3):
    """三次贝塞尔按弦误差 <= VEC_FLAT 细分 (控制多边形到弦的最大距离做上界, 递归二分)."""
    import math
    out = []
    def rec(a, b, c, d, depth):
        ux, uy = d[0] - a[0], d[1] - a[1]; L = math.hypot(ux, uy) or 1e-9
        dev = max(abs((q[0] - a[0]) * uy - (q[1] - a[1]) * ux) / L for q in (b, c))
        if dev <= VEC_FLAT or depth > 16:
            out.append(d); return
        ab = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2); bc = ((b[0] + c[0]) / 2, (b[1] + c[1]) / 2)
        cd = ((c[0] + d[0]) / 2, (c[1] + d[1]) / 2); abc = ((ab[0] + bc[0]) / 2, (ab[1] + bc[1]) / 2)
        bcd = ((bc[0] + cd[0]) / 2, (bc[1] + cd[1]) / 2); m = ((abc[0] + bcd[0]) / 2, (abc[1] + bcd[1]) / 2)
        rec(a, ab, abc, m, depth + 1); rec(m, bcd, cd, d, depth + 1)
    rec(p0, p1, p2, p3, 0)
    return out


def vector_contours(drawing, scale=1.0):
    """\\p 绘图串 -> 闭合轮廓列表 [[(x, y), ...], ...] (绘图坐标, 已乘 scale; 贝塞尔已细分).
    支持 m / n / l / b. s / p / c (B 样条) 按控制多边形处理: 曲线在控制点凸包内, 取控制多边形只会把形状算大或贴近, 偏严;
    出现时返回的 warns 里记一条. 不认识的命令 -> warns 并跳过该记号."""
    toks = re.findall(r"[a-z]|-?(?:\d+(?:\.\d*)?|\.\d+)", drawing)
    cons, cur, warns, cmd, buf = [], [], [], None, []
    def flush_close():
        if len(cur) >= 2:
            cons.append(list(cur))
    i = 0
    pos = (0.0, 0.0)
    while i < len(toks):
        t = toks[i]
        if t.isalpha():
            cmd = t; i += 1
            if cmd in ("s", "p", "c") and "B 样条按控制多边形量" not in warns:
                warns.append("B 样条按控制多边形量")
            if cmd == "c":
                cmd = None
            continue
        n = {"m": 2, "n": 2, "l": 2, "b": 6, "s": 2, "p": 2}.get(cmd)
        if n is None:
            if "绘图里有不认识的记号" not in warns:
                warns.append("绘图里有不认识的记号")
            i += 1; continue
        chunk = toks[i:i + n]
        if len(chunk) < n or any(x.isalpha() for x in chunk):
            if "绘图里有不完整的坐标" not in warns:
                warns.append("绘图里有不完整的坐标")
            i += 1; continue
        v = [float(x) * scale for x in chunk]
        i += n
        if cmd in ("m", "n"):
            if cmd == "m":
                flush_close(); cur = []
            pos = (v[0], v[1]); cur.append(pos)
        elif cmd in ("l", "s", "p"):
            pos = (v[0], v[1]); cur.append(pos)
        elif cmd == "b":
            pts = _cubic(pos, (v[0], v[1]), (v[2], v[3]), (v[4], v[5])); cur.extend(pts); pos = pts[-1]
    flush_close()
    return cons, warns


def _vis(tags, which, style_alpha=0):
    """该分量 (1 填充 / 3 边框 / 4 阴影) 在事件内是否可能可见: 出现过任一 < FF 的 alpha 值就算可见 (静态与 \\t 内一视同仁)."""
    vals = [int(v, 16) for v in re.findall(r"\\(?:%sa|alpha)&H([0-9A-Fa-f]{2})&" % which, tags)]
    if not re.search(r"\\(?:%sa|alpha)&H" % which, strip_t_(tags)):
        vals.append(style_alpha)
    return any(v < 0xFF for v in vals)


def strip_t_(tags):
    from assfx.base.geom import strip_t
    return strip_t(tags)


def _style_alpha(style, key):
    v = str(style.get(key, "&H00FFFFFF"))
    m = re.match(r"&H([0-9A-Fa-f]{2})[0-9A-Fa-f]{6}", v)
    return int(m.group(1), 16) if m else 0


def vector_points(text, cx, cy, style=None, styles=None, grid=None):
    """矢量母题事件停在 (cx, cy) (\\pos 或 \\move 终点) 时的量测点集. 返回 (px, py, pad, warns, info).
    量什么: libass 画出来的那块可见墨迹 (填充 / 边框 / 阴影). pad = 门禁要从间隙里再扣掉的外扩 (边框 + 2·blur + be),
            调用方 gap = max(0, sweep_gap 下界 - pad).
    怎么算: 轮廓按 VEC_STEP 取边界点; 填充可见时再加 VEC_FILL_GRID 内部网格 (非零环绕), 字框落进形状里间隙才会是 0.
            对齐与 geom.event_extent 同口径: 绘图原点放在对齐框左上角, 框宽高 = 绘图包围盒 x 缩放.
            缩放 = image_scale (事件内能达到的最大值); 旋转 = image_rotation (静态 \\frz, 动画报 W).
            阴影可见且偏移非 0 时, 整份点集平移后并入.
    边界: \\clip 不裁 (只会算大); \\frx/\\fry 只报 W; 全程不可见 (填充、边框、阴影都不可见) 返回空点集."""
    import math
    import numpy as np
    style = style or {}; warns = []
    tags = "".join(re.findall(r"\{([^}]*)\}", text))
    ds = _R_DRAW.findall(text)
    if not ds:
        return np.zeros(0), np.zeros(0), 0.0, ["没有绘图串"], {}
    pdiv = 2 ** (int(ds[-1][0]) - 1)
    cons = []
    for _, d in ds:
        c, w_ = vector_contours(d, 1.0 / pdiv); cons += c; warns += w_
    cons = [c for c in cons if len(c) >= 2]
    if not cons:
        return np.zeros(0), np.zeros(0), 0.0, warns + ["绘图串没有可量的轮廓"], {}
    sx, sy, sw = image_scale(text, style, styles); warns += sw
    frz, org, rw = image_rotation(text); warns += rw
    allp = np.array([p for c in cons for p in c])
    x0, y0 = allp.min(0); x1, y1 = allp.max(0)
    w, h = (x1 - x0) * sx, (y1 - y0) * sy
    an = int((re.findall(r"\\an(\d)", tags) or [style.get("Alignment", 7)])[-1])
    ox = {1: 0.5, 4: 0.5, 7: 0.5, 2: 0, 5: 0, 8: 0, 3: -0.5, 6: -0.5, 9: -0.5}[an]
    oy = {7: 0.5, 8: 0.5, 9: 0.5, 4: 0, 5: 0, 6: 0, 1: -0.5, 2: -0.5, 3: -0.5}[an]
    orx, ory = cx + (ox - 0.5) * w, cy + (oy - 0.5) * h       # 绘图原点 (对齐框左上角)
    fill = _vis(tags, "1", _style_alpha(style, "PrimaryColour"))
    def nums(tag):
        return [float(v) for v in re.findall(r"\\" + tag + r"(?![a-z])\s*" + _NUM, tags)]
    bord = max(nums("bord") + nums("xbord") + nums("ybord") + [float(style.get("Outline", 0) or 0)]) \
        if not re.search(r"\\bord", strip_t_(tags)) else max(nums("bord") + nums("xbord") + nums("ybord"))
    border = bord > 0 and _vis(tags, "3", _style_alpha(style, "OutlineColour"))
    shx = max(nums("shad") + nums("xshad") + [0.0] if re.search(r"\\x?shad", tags) else [float(style.get("Shadow", 0) or 0)])
    shy = max(nums("shad") + nums("yshad") + [0.0] if re.search(r"\\y?shad", tags) else [float(style.get("Shadow", 0) or 0)])
    shadow = (shx or shy) and _vis(tags, "4", _style_alpha(style, "BackColour"))
    if not (fill or border or shadow):
        return np.zeros(0), np.zeros(0), 0.0, warns, {"invisible": True}
    blur = max(nums("blur") + [0.0]); be = max(nums("be") + [0.0])
    pad = (bord if border else 0.0) + 2 * blur + be
    # 边界取点
    bx, by = [], []
    for c in cons:
        c2 = c + [c[0]]
        for (a0, a1), (b0, b1) in zip(c2, c2[1:]):
            L = math.hypot((b0 - a0) * sx, (b1 - a1) * sy)
            k = max(1, math.ceil(L / VEC_STEP))
            u = np.arange(k) / k
            bx.append(a0 + (b0 - a0) * u); by.append(a1 + (b1 - a1) * u)
    px = np.concatenate(bx); py = np.concatenate(by)
    if fill:                                          # 内部网格: 非零环绕
        gs = grid or VEC_FILL_GRID
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1e-9, gs / max(sx, 1e-9)), np.arange(y0, y1 + 1e-9, gs / max(sy, 1e-9)))
        gx = gx.ravel(); gy = gy.ravel(); wn = np.zeros(len(gx), int)
        for c in cons:
            c2 = np.array(c + [c[0]])
            for (a0, a1), (b0, b1) in zip(c2[:-1], c2[1:]):
                cr = (b0 - a0) * (gy - a1) - (gx - a0) * (b1 - a1)
                up = (a1 <= gy) & (b1 > gy) & (cr > 0); dn = (a1 > gy) & (b1 <= gy) & (cr < 0)
                wn += up.astype(int) - dn.astype(int)
        ins = wn != 0
        px = np.concatenate([px, gx[ins]]); py = np.concatenate([py, gy[ins]])
    # 绘图坐标 -> 画面: 缩放 (相对绘图原点), 平移到对齐框, 旋转 (\\org 或 \\pos)
    X = orx + px * sx; Y = ory + py * sy
    if frz:
        t = math.radians(frz)
        Ox, Oy = org if org else (cx, cy)
        u, v = X - Ox, Y - Oy
        X, Y = Ox + u * math.cos(t) + v * math.sin(t), Oy - u * math.sin(t) + v * math.cos(t)
    if shadow and not (fill or border):
        X, Y = X + shx, Y + shy
    elif shadow:
        X, Y = np.concatenate([X, X + shx]), np.concatenate([Y, Y + shy])
    return X, Y, pad, warns, {"fill": bool(fill), "border": bool(border), "shadow": bool(shadow),
                              "bord": bord, "blur": blur, "sx": sx, "sy": sy, "frz": frz, "an": an}



# ---------------------------------------------------------------- 矢量件门禁 (known-gaps #13, 2026-11-12 用户定)
# 前景 / 背景按"谁画在上面"分, 不按层号: libass 先比 Layer, 同层按文件里的先后 (后写的在上).
#   前景 (矢量件画在字上面): 间隙 < MOTIF_GAP 报 E, 与贴图同一把尺子 (sweep_gap).
#   背景 (字画在矢量件上面): 遮挡不是问题, 字底的对比度才是. 判据 = 覆盖比例 (形状盖住字墨迹框的面积比) + 峰值不透明度.
#     2026-11-12 定: 阈值先不定, 先量分布报数 (VEC_STATS["behind"]), 本轮背景线只报 W 汇总, 不出 E.
# 显式豁免: 事件的 Effect 字段写 "over" (libass 不认这个值, 渲染不受影响) = 有意盖字的效果 (粒子、音节高亮光斑).
#   over 不量间隙, 但兜底照样报 E: 形状尺寸 > OVER_MAX_EXT 且峰值不透明度 > OVER_MAX_OPACITY, 或在屏 > OVER_MAX_DUR 秒.
# 白名单: .ass 同目录 motif_gap.allow.json, 只收用户过目的条目, 每条带到期轮次; 命中报 W 并每次打印一行, 过期转 E.
VEC_OVER = "over"
OVER_MAX_EXT = 24.0
OVER_MAX_OPACITY = 0.5
OVER_MAX_DUR = 1.0
ALLOW_FILE = "motif_gap.allow.json"
VEC_STATS = {}            # 最近一次 check_vectors 的统计 (报数脚本读): front / behind / over / allow


def _peak_opacity(tags, style, info):
    """可见分量 (填充 / 边框 / 阴影) 在事件内能达到的最大不透明度 (0-1). \\fad 不算 (只会偏严)."""
    vals = []
    for which, key, on in (("1", "PrimaryColour", info.get("fill")), ("3", "OutlineColour", info.get("border")),
                           ("4", "BackColour", info.get("shadow"))):
        if not on:
            continue
        v = [int(x, 16) for x in re.findall(r"\\(?:%sa|alpha)&H([0-9A-Fa-f]{2})&" % which, tags)]
        if not re.search(r"\\(?:%sa|alpha)&H" % which, strip_t_(tags)):
            v.append(_style_alpha(style, key))
        vals += [x for x in v if x < 0xFF] or []
    return (255 - min(vals)) / 255 if vals else 0.0


def _coverage(px, py, pad, fill, boxes, grid=VEC_FILL_GRID):
    """形状盖住字墨迹框的面积比 (每个框 1px 网格采样; 到点集距离 <= 半径算盖住). 返回 (最大比例, 那个框)."""
    import numpy as np
    r = max(pad, grid * 0.71 if fill else 0.0, VEC_STEP)   # 填充内部网格点之间的空当也算盖住 (偏大)
    best = (0.0, None)
    for b in boxes:
        x0, y0, x1, y1 = b[:4]
        sel = (px >= x0 - r) & (px <= x1 + r) & (py >= y0 - r) & (py <= y1 + r)
        if not sel.any():
            continue
        qx, qy = px[sel], py[sel]
        gx, gy = np.meshgrid(np.arange(x0 + 0.5, x1, 1.0), np.arange(y0 + 0.5, y1, 1.0))
        gx = gx.ravel(); gy = gy.ravel()
        if not len(gx):
            continue
        cov = np.zeros(len(gx), bool)
        for i in range(0, len(qx), 512):
            d2 = (gx[:, None] - qx[None, i:i + 512]) ** 2 + (gy[:, None] - qy[None, i:i + 512]) ** 2
            cov |= (d2 <= r * r).any(1)
        f = float(cov.mean())
        if f > best[0]:
            best = (f, b)
    return best


def _boxes_at(tracks, t, img_trk, img_s):
    """t 时刻在屏字框的画面坐标, 以及图相对终点的位移."""
    ix, iy = _at(img_trk, (t - img_s) * 1000)
    out = []
    for s, e, bx, trk in tracks:
        if not (s <= t < e):
            continue
        tx, ty = _at(trk, (t - s) * 1000)
        ox, oy = tx - trk[2], ty - trk[3]
        out += [(q[0] + ox, q[1] + oy, q[2] + ox, q[3] + oy) + tuple(q[4:]) for q in bx]
    return out, ix - img_trk[2], iy - img_trk[3]


def _load_allow(ass_path):
    import json
    p = os.path.join(os.path.dirname(os.path.abspath(ass_path)), ALLOW_FILE)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _allow_hit(allow, ev, bn):
    for it in (allow or {}).get("entries", []):
        if it.get("band") == bn and int(it.get("layer", -1)) == int(ev.get("Layer", -2)) \
                and abs(float(it.get("start", -99)) - ev["s"]) <= 0.02:
            return it
    return None


def check_vectors(events, styles, ass_path, fontsdir, by_band_ev, errs, warns, measured):
    """矢量件 (Name=fx:<band> 且带 \\p 绘图) 的母题压字. 字侧与贴图完全同一套 (text_ink_tracks / sweep_gap);
    只有点集来源换成 vector_points. 结果写进 errs / warns / measured, 统计写进 VEC_STATS."""
    import numpy as np
    allow = _load_allow(ass_path)
    st_ = {"front": [], "behind": [], "over": [], "over_e": [], "allow": [], "invisible": 0, "measured": 0,
           "unplaced": collections.Counter(), "est": set()}
    sides = [min(q[2] - q[0], q[3] - q[1]) for lst in by_band_ev.values() for _, tup in lst
             for q in text_ink_boxes([tup], tup[0], tup[1], fontsdir)]
    grid = max(0.5, min([VEC_FILL_GRID] + [x for x in sides if x > 0]))
    st_["grid"] = grid

    def tracks_of(bn, evs_, t0, t1):
        unpl = []
        tr = text_ink_tracks([x[1] for x in evs_], t0, t1, fontsdir, unpl)
        return tr, unpl

    for ev in events:
        t = ev["Text"]; nm = re.match(r"fx:(\S+)", ev.get("Name", ""))
        if not nm or not _R_DRAW.search(t):
            continue
        bn = nm.group(1)
        txt = [x for x in by_band_ev.get(bn, []) if x[0]["e"] > ev["s"] and x[0]["s"] < ev["e"]]
        if not txt:
            continue
        trk = track(t, (ev["e"] - ev["s"]) * 1000)
        if not trk:
            warns.append(f"L{ev['_ln']} 矢量件没有 \\pos / \\move, 母题压字未量")
            continue
        stl = styles.get(ev["Style"], {})
        px, py, pad, vw, info = vector_points(t, trk[2], trk[3], stl, styles, grid)
        if not len(px):
            st_["invisible"] += 1
            continue
        tags = "".join(re.findall(r"\{([^}]*)\}", t))
        op = _peak_opacity(tags, stl, info)
        ext = float(max(px.max() - px.min(), py.max() - py.min()))
        dur = ev["e"] - ev["s"]
        if (ev.get("Effect") or "").strip() == VEC_OVER:
            why = []
            if ext > OVER_MAX_EXT and op > OVER_MAX_OPACITY:
                why.append(f"尺寸 {ext:.0f}px > {OVER_MAX_EXT:g} 且不透明度 {op:.0%} > {OVER_MAX_OPACITY:.0%}")
            if dur > OVER_MAX_DUR:
                why.append(f"在屏 {dur:.2f}s > {OVER_MAX_DUR:g}s")
            if why:
                st_["over_e"].append((ev["_ln"], bn, ev["Layer"], round(ext, 1), round(op, 2), round(dur, 2)))
                errs.append(f"母题压字 over 越界 L{ev['_ln']} band {bn}: 标了 over (有意盖字) 但{'; '.join(why)},"
                            " 不是粒子 / 高亮光斑该有的样子  (去掉 over 让它按母题量, 或把它做小做短; 不要改兜底)")
            else:
                st_["over"].append(bn)
            continue
        # 预筛: 点集沿轨迹的包围盒 + pad 离所有字框 (含字的轨迹) 都 >= MOTIF_GAP + 1 的, 不可能压字
        mx0, my0 = px.min() + min(0, trk[0] - trk[2]), py.min() + min(0, trk[1] - trk[3])
        mx1, my1 = px.max() + max(0, trk[0] - trk[2]), py.max() + max(0, trk[1] - trk[3])
        L, ln = int(ev.get("Layer", 0)), ev["_ln"]
        front = [x for x in txt if L > int(x[0].get("Layer", 0)) or (L == int(x[0].get("Layer", 0)) and ln > x[0]["_ln"])]
        behind = [x for x in txt if x not in front]
        for side, grp in (("front", front), ("behind", behind)):
            if not grp:
                continue
            tr, unpl = tracks_of(bn, grp, ev["s"], ev["e"])
            if unpl:
                st_["unplaced"][bn] += 1
            if not tr:
                continue
            near = False
            for s_, e_, bx, ttrk in tr:
                dx = (ttrk[0] - ttrk[2]); dy = (ttrk[1] - ttrk[3])
                for q in bx:
                    qx0, qy0 = q[0] + min(0, dx), q[1] + min(0, dy); qx1, qy1 = q[2] + max(0, dx), q[3] + max(0, dy)
                    gx = max(qx0 - mx1, mx0 - qx1, 0); gy = max(qy0 - my1, my0 - qy1, 0)
                    if (gx * gx + gy * gy) ** 0.5 - pad < MOTIF_GAP + 1:
                        near = True; break
                if near:
                    break
            if not near:
                continue
            for q in (b for x in tr for b in x[2]):
                if len(q) > 5 and q[5]:
                    st_["est"].add(q[5])
            # 点集裁剪 (只为速度): 离所有字框 (按字与图的相对位移扫过的范围外扩) 都 > MOTIF_GAP + pad + 1 的点,
            # 不可能让间隙 < MOTIF_GAP, 去掉不改变任何 E / 背景线判定 (只改变 >= 门槛时报出的数, 那些数不用).
            idx, idy = (min(0, trk[0] - trk[2]), max(0, trk[0] - trk[2])), (min(0, trk[1] - trk[3]), max(0, trk[1] - trk[3]))
            keep = np.zeros(len(px), bool); R_ = MOTIF_GAP + pad + 1
            for s_, e_, bx, ttrk in tr:
                tdx = (min(0, ttrk[0] - ttrk[2]), max(0, ttrk[0] - ttrk[2])); tdy = (min(0, ttrk[1] - ttrk[3]), max(0, ttrk[1] - ttrk[3]))
                for q in bx:
                    keep |= (px >= q[0] + tdx[0] - idx[1] - R_) & (px <= q[2] + tdx[1] - idx[0] + R_) \
                        & (py >= q[1] + tdy[0] - idy[1] - R_) & (py <= q[3] + tdy[1] - idy[0] + R_)
            if not keep.any():
                continue
            # 同理裁掉离点集太远的字框 (同一个字在 2/3/4 层的重复框也去重): 同样只改变 >= 门槛时的数
            kx, ky = px[keep], py[keep]; X0, X1, Y0, Y1 = kx.min(), kx.max(), ky.min(), ky.max()
            tr2 = []
            for s_, e_, bx, ttrk in tr:
                tdx = (min(0, ttrk[0] - ttrk[2]), max(0, ttrk[0] - ttrk[2])); tdy = (min(0, ttrk[1] - ttrk[3]), max(0, ttrk[1] - ttrk[3]))
                seen, kept = set(), []
                for q in bx:
                    k_ = tuple(round(v, 2) for v in q[:4])
                    if k_ in seen:
                        continue
                    seen.add(k_)
                    if q[0] + tdx[0] - idx[1] - R_ <= X1 and q[2] + tdx[1] - idx[0] + R_ >= X0 \
                            and q[1] + tdy[0] - idy[1] - R_ <= Y1 and q[3] + tdy[1] - idy[0] + R_ >= Y0:
                        kept.append(q)
                if kept:
                    tr2.append((s_, e_, kept, ttrk))
            if not tr2:
                continue
            tr = tr2
            sw_ = sweep_gap(kx, ky, ev["s"], ev["e"], trk, tr, stop_at=0.0)
            st_["measured"] += 1
            g = max(0.0, sw_["lower"] - pad)
            if g >= MOTIF_GAP:
                continue
            b = sw_["box"]
            rec = {"ln": ln, "band": bn, "layer": L, "gap": round(g, 2), "geom": round(sw_["lower"], 2), "pad": round(pad, 2),
                   "t": round(sw_["t"], 3) if sw_["t"] is not None else None, "char": b[4] if b else None,
                   "ext": round(ext, 1), "op": round(op, 2), "dur": round(dur, 2), "warns": vw}
            if side == "behind":
                bxs, ddx, ddy = _boxes_at(tr, sw_["t"], trk, ev["s"])
                cov, cb = _coverage(px + ddx, py + ddy, pad, info.get("fill"), bxs, grid)
                rec.update(cov=round(cov, 3), cov_char=cb[4] if cb else None)
                st_["behind"].append(rec)
                continue
            hit = _allow_hit(allow, ev, bn)
            if hit is not None:
                exp, cur = int(hit.get("expires_round", 0)), int((allow or {}).get("round", 0))
                rec.update(allow=hit.get("gap"), expires_round=exp)
                st_["allow"].append(rec)
                if cur > exp:
                    errs.append(f"母题压字 白名单过期 L{ln} band {bn}: {hit.get('gap')} 到期轮次 {exp}, 当前轮次 {cur}, 间隙 {g:.1f}px 仍 < {MOTIF_GAP:g}px  (修掉它; 不要续期)")
                continue
            st_["front"].append(rec)
            errs.append(f"母题压字 矢量 L{ln} band {bn} layer {L}: 到「{rec['char']}」间隙 {g:.1f}px < {MOTIF_GAP:g}px"
                        f" (矢量件画在字上面; 几何间隙 {sw_['lower']:.1f}px 扣外扩 {pad:.1f}px (边框+2·blur); 最近时刻 {rec['t']}s;"
                        f" 形状 {ext:.0f}px 不透明度 {op:.0%})  (挪开或缩小; 有意盖字的粒子 / 高亮写 Effect=over; 不要改尺子)")
            measured.append((g, ln, bn, "<vector>", info.get("sx", 1), info.get("sy", 1), sw_))
    for bn, n in st_["unplaced"].items():
        errs.append(f"母题压字 缺显式定位 band {bn}: {n} 条矢量件同时在屏的字没有 \\pos / \\move 且推不出位置, 量不到, 间隙不可信  (给字加 \\pos)")
    if st_["est"]:
        warns.append(f"矢量件母题压字: 字体 {'/'.join(sorted(st_['est']))[:200]} 按估宽量 (见贴图那条同类 W)")
    if st_["over"]:
        c = collections.Counter(st_["over"])
        warns.append(f"矢量件母题压字: Effect=over 豁免 {sum(c.values())} 条 ({', '.join(f'{k} {v}' for k, v in sorted(c.items()))})")
    if st_["behind"]:
        warns.append(f"矢量件母题压字 背景线 (字画在矢量件上面) 间隙 < {MOTIF_GAP:g}px 共 {len(st_['behind'])} 条: 本轮只报数, 阈值待定"
                     f" (覆盖比例最大 {max(r['cov'] for r in st_['behind']):.0%})")
    if allow is not None:
        rs = sorted({int(it.get('expires_round', 0)) for it in allow.get('entries', [])})
        warns.append(f"母题压字 白名单命中 {len(st_['allow'])} 条, 到期轮次 {'/'.join(map(str, rs)) or '-'} (当前轮次 {allow.get('round')})")
    VEC_STATS.clear(); VEC_STATS.update(st_)


def allow_banner(ass_path, fontsdir=None):
    """生成后打印白名单那一行 (2026-11-13 用户定: 每次生成都要打, 让它没法忘). 只量白名单点名的那几条矢量件, 很快.
    返回 (命中条数, 过期 E 列表); 没有白名单文件返回 None."""
    allow = _load_allow(ass_path)
    if allow is None:
        return None
    import sys as _sys
    qa = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "qa")
    if qa not in _sys.path:
        _sys.path.insert(0, qa)
    from validate_ass import load_ass
    _, styles, events, _ = load_ass(ass_path)
    pick = [ev for ev in events if (m := re.match(r"fx:(\S+)", ev.get("Name", ""))) and _allow_hit(allow, ev, m.group(1))]
    bands = {re.match(r"fx:(\S+)", ev["Name"]).group(1) for ev in pick}
    sub = pick + [ev for ev in events if ev.get("Name", "")[3:] in bands and ev.get("Name", "").startswith("ly:")]
    errs, warns, _ = check_ass(sub, styles, ass_path, fontsdir)
    hits = len(VEC_STATS.get("allow", []))
    rs = sorted({int(it.get("expires_round", 0)) for it in allow.get("entries", [])})
    cur = allow.get("round")
    exp = [e for e in errs if "白名单过期" in e]
    print(f"[motif_gap] 白名单命中 {hits} 条, 到期轮次 {'/'.join(map(str, rs)) or '-'} (当前轮次 {cur}; 条目 {len(allow.get('entries', []))},"
          f" 点名事件找到 {len(pick)} 条)" + (f"  已过期 {len(exp)} 条 = E" if exp else ""))
    for e in exp:
        print("[motif_gap] E " + e)
    return hits, exp
