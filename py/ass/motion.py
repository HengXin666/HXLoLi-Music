#!/usr/bin/env python3
"""动效词汇库  从实测反推的可组合动效原语。

**为什么要有这个文件**：一个"动效"不是一个标签，而是「多层 × 时间链 × 空间变换」的组合。
本文件把这种组合拆成可复用的原语，让动效成为**可生成**的，而不是逐字手写。

## 数据来源

从对照实测得出（见 doc/KFX-MOTION-VOCAB.md 的记录）：
- 单字文本事件平均带 1.60 个 \\t；日文层 2.16 个  **多层链是常态，不是炫技**
- 21.5% 的事件带 \\p1 绘图  绘图层不是装饰，是结构的一部分
- 55% 的事件带 \\clip；中文层每个字 2.00 个  **一个汉字拆多条 clip 是标准做法**
- \\t 区间：p10=200 / p50=300 / p90=700 ms  中位 300ms 是设计值

## 三层模型

一个字要"动"，最多用三层同时作用：

    L1 字形层  字本身的 scale / blur / alpha / color    负责"出现与点亮"
    L2 条带层  clip 切分 + 纵横拉伸                     负责"解构与流动"
    L3 图形层  \\p1 自绘图形                             负责"语义符号"

三层独立计时，互不同步  这才是观感上有"层次"的原因。同一时刻三层都在变，
但变化的相位不同。
"""
import math

BS = chr(92)


# Agent Notes: KFX 质量红线（静态拦截）
# 
def ts(ms):
    """Agent Notes
    .agents/notes/implemented/process/2026-09-28-kfx-quality-redline.md
    """
    return int(round(ms))


# ---------------------------------------------------------------------------
# L1 字形层：出现 / 点亮 / 退场
# ---------------------------------------------------------------------------

def glyph_emerge(at_ms, dur=200, blur_from=8, blur_to=0, scale_from=0, scale_to=100):
    """从零放大 + 模糊聚焦。dur 200ms 起，这是实测的常见入场。"""
    return (f"{BS}alpha&H00&{BS}fscx{scale_from}{BS}fscy{scale_from}"
            f"{BS}t({at_ms},{at_ms + dur},{BS}fscx{scale_to}{BS}fscy{scale_to}"
            f"{BS}blur{blur_to})")


def glyph_pulse(at_ms, dur=400, peak=150):
    """唱到时的强调脉冲：放大到 peak% 再回弹。实测 Charlotte 用 150%。"""
    half = dur // 2
    return (f"{BS}t({at_ms},{at_ms + half},{BS}fscx{peak}{BS}fscy{peak})"
            f"{BS}t({at_ms + half},{at_ms + dur},{BS}fscx100{BS}fscy100)")


def glyph_ignite(at_ms, dur, fill="&H00FFFFFF&", edge="&H0026774D&",
                 ghost="&H00888888&", peak=126):
    """点亮：暗态 → 亮态，带过冲回弹。dur 由语义模型给出。"""
    a = at_ms + int(dur * 0.45)
    b = at_ms + dur
    return (f"{BS}alpha&H00&{BS}1c{ghost}{BS}3c&H00100804&{BS}bord2{BS}blur2.2"
            f"{BS}t({at_ms},{a},{BS}1c{fill}{BS}3c{edge}"
            f"{BS}bord4{BS}blur0.4{BS}fscx{peak}{BS}fscy{peak})"
            f"{BS}t({a},{b},{BS}fscx100{BS}fscy100)")


def glyph_echo(at_ms, dur, scale=128, fade_at=None):
    """幻影副本：放大后淡出。Charlotte 日文层用这个做"残响"。"""
    fade = fade_at if fade_at is not None else at_ms + int(dur * 0.6)
    return (f"{BS}t({at_ms},{fade},{BS}fscx{scale}{BS}fscy{scale}{BS}blur3)"
            f"{BS}t({fade},{at_ms + dur},{BS}alpha&HFF&)")


def glyph_rise(at_ms, dur, dy=-40):
    """上浮退场。"""
    return f"{BS}move(0,0,0,{dy},0,{dur}){BS}t({at_ms},{at_ms + dur},{BS}alpha&HFF&)"


# ---------------------------------------------------------------------------
# L2 条带层：解构与流动（Charlotte 中文层的核心手法）
# ---------------------------------------------------------------------------

# 实测的 4 条横带切分 (以字高 ±100 为范围)
BANDS_4 = [(-70, 20), (20, 30), (30, 40), (40, 130)]


def band_liquid(x0, y_center, width, at_ms, dur=300,
                bands=None, stretch=2.4, drift=0):
    """液态撕裂：一个字拆成 N 条横带，各自纵向拉伸不同幅度。

    返回 N 条文本片段（每条一个独立的 override 块）。
    这是把"一个字"变成"多条带子"的核心  单条 clip 做不出撕裂感。

    x0/y_center: 字的左上角 x 与中线 y
    width:       字宽
    stretch:     纵向拉伸倍数（实测 Charlotte 用 2.4）
    drift:       横向漂移像素
    """
    bands = bands or BANDS_4
    out = []
    for i, (ya, yb) in enumerate(bands):
        # 每条带拉伸的幅度不同  这才是"撕裂"而不是"整体缩放"
        k = stretch * (1.0 - i * 0.13)
        y1 = y_center + ya
        y2 = y_center + yb
        # 拉伸后条带向两侧扩
        mid = (y1 + y2) / 2
        half = (y2 - y1) / 2 * k
        ny1, ny2 = mid - half, mid + half
        # clip 必须带反斜杠, 否则会被当作正文文字渲染出来
        c0 = f"{BS}clip({x0},{y1},{x0 + width},{y2})"
        c1 = f"{BS}clip({x0},{int(ny1)},{x0 + width},{int(ny2)})"
        mv = f"{BS}move({x0 + width // 2},{y_center},{x0 + width // 2 + drift},{y_center},0,{dur})" if drift else ""
        out.append(f"{{{BS}an5{BS}blur3{BS}fad(140,0){c0}"
                   f"{BS}t(0,{dur},{c1}){mv}}}")
    return out


def band_sweep(x0, y_center, width, at_ms, dur=300, stretch=2.4):
    """横扫式：单条 clip 从左扫到右，做"揭开"。适合不需要撕裂的庄重句子。"""
    y1, y2 = y_center - 70, y_center + 130
    return (f"{{{BS}an5{BS}blur3{BS}fad(140,0)"
            f"{BS}clip({x0},{y1},{x0},{y2})"
            f"{BS}t(0,{dur},{BS}clip({x0},{y1},{x0 + width},{y2}))}}")


def band_curtain(x0, y_center, width, at_ms, dur=400, steps=5):
    """百叶帘：等分横条依次拉开。"""
    out = []
    step = max(2, (y_center + 130 - (y_center - 70)) // steps)
    for i in range(steps):
        y1 = y_center - 70 + i * step
        y2 = y1 + max(2, step - 2)
        d = i * (dur // (steps * 2))
        out.append(f"{{{BS}an5{BS}blur2{BS}clip({x0},{y1},{x0},{y2})"
                   f"{BS}t({d},{d + dur // 2},{BS}clip({x0},{y1},{x0 + width},{y2}))}}")
    return out


# ---------------------------------------------------------------------------
# L3 图形层：语义符号
# ---------------------------------------------------------------------------

def shape_burst(path, at_ms, dur, x, y, scale_from=0, scale_to=170,
                alpha_in=0x20, color="&H00FFFFFF&", peak_ms=None):
    """图形爆开：从零放大到 scale_to 后缩灭。Charlotte 用 fscx170 → fscx0。"""
    peak = peak_ms if peak_ms is not None else dur // 2
    return (f"{{{BS}an5{BS}p1{BS}alpha&H{alpha_in:02X}&{BS}3c{color}"
            f"{BS}fscx{scale_from}{BS}fscy{scale_from}"
            f"{BS}t(0,{peak},{BS}fscx{scale_to}{BS}fscy{scale_to})"
            f"{BS}t({peak},{dur},{BS}fscx0{BS}fscy0){BS}blur6"
            f"{BS}pos({x},{y})}}{path}")

def shape_float(path, at_ms, dur, x, y, dx=0, dy=-80, rot=0):
    """图形漂浮。"""
    r = f"{BS}frz{rot}" if rot else ""
    return (f"{{{BS}an5{BS}p1{BS}alpha&H30&{BS}blur2{r}"
            f"{BS}move({x},{y},{x + dx},{y + dy},0,{dur})}}{path}")


# ---------------------------------------------------------------------------
# 组合：把三层拼成一条完整的"字事件组"
# ---------------------------------------------------------------------------

def compose_glyph(ch, x, y, t_start, t_light, dur, params,
                  with_bands=False, width=70):
    """生成一个字所需的全部事件行。

    返回 [(layer, tags, text), ...]  调用方负责拼成 ASS Dialogue 行。

    layer 约定（越大越靠前）：
      1 = L2 条带层
      2 = L1 字形层
      3 = L3 图形层
    """
    out = []
    fill = params.get("fill", "&H00FFFFFF&")
    edge = params.get("edge", "&H0026774D&")
    ghost = params.get("ghost", "&H00888888&")
    peak = params.get("peak", 126)
    # L1: 入场 + 点亮
    tags = glyph_emerge(0, 200, 8, 0, 0, 100) + BS + "pos(" + str(x) + "," + str(y) + ")"
    out.append((2, tags, ch))
    out.append((2, glyph_ignite(t_light, dur, fill, edge, ghost, peak)
                + BS + "pos(" + str(x) + "," + str(y) + ")", ch))
    # L2: 条带（可选）
    if with_bands:
        for i, b in enumerate(band_liquid(x - width // 2, y, width, t_start)):
            out.append((1, b, ch))
    return out


MOTION_NAMES = ["emerge", "ignite", "pulse", "echo", "rise",
                "liquid", "sweep", "curtain", "burst", "float"]
