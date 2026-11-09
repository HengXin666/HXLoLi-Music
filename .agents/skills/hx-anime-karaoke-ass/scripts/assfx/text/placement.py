# -*- coding: utf-8 -*-
"""歌词位置预设 (placement.json) -> 字带坐标. 纯计算: 不读写 ASS, 不 import 生成器.

预设 = 垂直 (top/middle/bottom) x 水平 (left/center/right) x 语言顺序 (jp_top/cn_top) x 行距 (tight/normal/loose).
锚定规则: 字块墨迹的外边缘离画面边 MARGIN_Y (竖) / MARGIN_X (横, 只对 left/right). 不提供 margin 可调 (无需求).
所有竖向量都由 calib.json (calibrate_ruby 输出) 推出, 不写死字号:
  注音顶   = ruby_offset + ruby_kana.top_p10        (相对 JY)
  日文底   = jp_kanji.bottom_p90
  中文上下 = cn_offset + cn.top_p10 / cn.bottom_p90
  基准行距 = 日文墨迹底到中文墨迹顶 (calib 自带, オンリー 为 20px); 行距档只在它上面加 Δ.
默认预设 (bottom/center/jp_top/normal) 必须复现旧工程写死的 JP_Y=915, cx=960, cn_offset 不变 (见 legacy 检查).

位置公式只有这一份: layout.py 的行起点调 row_x0, 预览台 (studio /api/placement) 调 preview, 前端只按返回的矩形与位移画.
"""
import json, os

PLAY_W, PLAY_H = 1920, 1080
MARGIN_X, MARGIN_Y = 144, 80          # 墨迹离画面边; band 再外扩 pad (96/54) 后离边 48/26
V = ("top", "middle", "bottom")
H = ("left", "center", "right")
ORDER = ("jp_top", "cn_top")
GAP = {"tight": -8, "normal": 0, "loose": 12}   # 相对 calib 基准行距的增量 px
DEFAULT = dict(v="bottom", h="center", order="jp_top", gap="normal")
FILE = "placement.json"


def _num(x):
    """整数值回整数, 避免 915.0 与 915 在格式化输出里不同."""
    return int(x) if float(x).is_integer() else x


def load(here):
    """读工程根目录的 placement.json; 文件或字段缺失 -> 默认. 未知值报错 (不静默回退)."""
    p = dict(DEFAULT)
    # ASSFX_PLACEMENT: 预览台重跑时指向临时预设文件; 生成成功后才落到工程的 placement.json (崩溃也不留半套状态)
    f = os.environ.get("ASSFX_PLACEMENT") or os.path.join(here, FILE)
    if os.path.exists(f):
        raw = json.load(open(f, encoding="utf-8"))
        for k in DEFAULT:
            if k in raw:
                p[k] = raw[k]
    for k, allowed in (("v", V), ("h", H), ("order", ORDER), ("gap", tuple(GAP))):
        if p[k] not in allowed:
            raise ValueError(f"{FILE}: {k}={p[k]!r} 不在 {allowed}")
    return p


def compute(p, calib, pad=(96, 54)):
    """返回 dict: jy, rb_offset, cn_offset (都相对/绝对 y), cx 或 x_edge+align, 墨迹上下沿, band 的 y 范围."""
    rb_off = calib["ruby_offset"]
    ruby_top = rb_off + calib["ruby_kana"]["top_p10"]
    jp_bot = calib["jp_kanji"]["bottom_p90"]
    cn_t, cn_b = calib["cn"]["top_p10"], calib["cn"]["bottom_p90"]
    base_gap = calib["cn_offset"] + cn_t - jp_bot
    gap = base_gap + GAP[p["gap"]]
    if p["order"] == "jp_top":                       # 注音 / 日文 / 中文
        cn_off = calib["cn_offset"] + GAP[p["gap"]]
        top, bot = ruby_top, cn_off + cn_b
    else:                                            # 中文 / 注音 / 日文: 注音必须贴日文, 中文在注音之上
        cn_off = ruby_top - gap - cn_b
        top, bot = cn_off + cn_t, jp_bot
    if p["v"] == "bottom":
        jy = PLAY_H - MARGIN_Y - bot
    elif p["v"] == "top":
        jy = MARGIN_Y - top
    else:
        jy = PLAY_H / 2 - (top + bot) / 2
    out = dict(preset=dict(p), jy=_num(jy), rb_offset=_num(rb_off), cn_offset=_num(cn_off),
               rb_y=_num(jy + rb_off), cn_y=_num(jy + cn_off), gap_px=_num(gap),
               ink_y=(_num(jy + top), _num(jy + bot)),
               band_y=(_num(jy + top - pad[1]), _num(jy + bot + pad[1])), align=p["h"])
    if p["h"] == "center":
        out["cx"] = PLAY_W // 2
    else:
        out["x_edge"] = MARGIN_X if p["h"] == "left" else PLAY_W - MARGIN_X
    return out


def table(calib):
    """全部 3x3x2x3 组合, 供文档/前端枚举; 越出画面的组合会在 band_y 上直接看出来."""
    rows = []
    for v in V:
        for h in H:
            for o in ORDER:
                for g in GAP:
                    rows.append(compute(dict(v=v, h=h, order=o, gap=g), calib))
    return rows


def row_x0(align, x_edge, cx, total, sp, lead):
    """一行的起点 x (layout.Layout._x0 直接调这里).
    total = 本行各字占位之和 (含每字尾部字距 sp); lead = 首字占位左侧空白 (日文 sp/2, 中文 0).
    center 保留旧式 (日文 cx - total/2, 中文 cx - (total - sp)/2), 逐字节不变;
    left/right: 整句块贴 x_edge, 日文行与中文行墨迹边对齐同一条线, 全曲共用, 句间不跳."""
    if align == "left":
        return x_edge - lead
    if align == "right":
        return x_edge - (total - sp) - lead
    return cx - (total - sp) / 2 if lead == 0 else cx - total / 2


def _x_args(r):
    return r["align"], r.get("x_edge"), r.get("cx", PLAY_W // 2)


def split_y(r, calib):
    """日文块 (含注音) 与中文行之间的分界 y: 两行墨迹间隙的中线."""
    if r["preset"]["order"] == "jp_top":
        return (r["jy"] + calib["jp_kanji"]["bottom_p90"] + r["cn_y"] + calib["cn"]["top_p10"]) / 2
    return (r["cn_y"] + calib["cn"]["bottom_p90"] + r["jy"] + calib["ruby_offset"] + calib["ruby_kana"]["top_p10"]) / 2


def preview(cur, new, calib, units, pad=(96, 54)):
    """近似预览: 当前成品 (按 cur 生成) 的每句拆成两块 -- 日文块 (注音+日文) / 中文行 -- 各自平移到 new 的位置.
    units: 清单里的句单元 (name, t, band, rows; rows 由生成器写: jp/cn = [total, sp, lead]).
    返回 [{name, t, jp: {src, dx, dy}, cn: {src, dx, dy} | None}], src 为 1920x1080 坐标 [x0, y0, x1, y1].
    块内的特效跟着块走; 跨两块或在 band 外的特效不跟 (界面上要标明)."""
    A, B = compute(cur, calib, pad), compute(new, calib, pad)
    sy = split_y(A, calib)
    jp_first = A["preset"]["order"] == "jp_top"
    out = []
    for u in units:
        band, rows = u.get("band"), u.get("rows") or {}
        if not band or not rows.get("jp"):
            continue
        x0, y0, x1, y1 = band[:4]
        has_cn = bool(rows.get("cn"))
        if not has_cn:
            jp_src, cn_src = [x0, y0, x1, y1], None
        elif jp_first:
            jp_src, cn_src = [x0, y0, x1, sy], [x0, sy, x1, y1]
        else:
            cn_src, jp_src = [x0, y0, x1, sy], [x0, sy, x1, y1]

        def dx(row):
            total, sp, lead = row
            return row_x0(*_x_args(B), total, sp, lead) - row_x0(*_x_args(A), total, sp, lead)
        it = dict(name=u.get("name"), t=u.get("t"),
                  jp=dict(src=[round(v, 1) for v in jp_src], dx=round(dx(rows["jp"]), 1), dy=_num(B["jy"] - A["jy"])))
        it["cn"] = dict(src=[round(v, 1) for v in cn_src], dx=round(dx(rows["cn"]), 1),
                        dy=_num(B["cn_y"] - A["cn_y"])) if has_cn else None
        out.append(it)
    return out
