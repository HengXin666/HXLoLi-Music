# -*- coding: utf-8 -*-
"""
卡点层 (beat layer): 跟着**音乐事件**走的特效层, 不跟字.

决策与实测依据: .agents/notes/implemented/feature/2026-10-03-karaoke-beat-layer.md

## 它解决什么

原先生成器里所有特效的触发源只有一个 —— 人声音拍(`c["s"]`). 于是特效只会"跟唱".
卡点层把触发源换成**伴奏事件网格**(十六分/八分音符), 特效才开始"跟曲".

## 实测的既定规格 (来自参考成品 天使の3P「大切がきこえる」01:00 高潮段, 逐条量过)

| 参数 | 实测值 |
|---|---|
| 网格 | 0.125s (十六分), 群发对齐误差中位 0.20 (随机 0.5) |
| 群发周期 | 2 格(八分) 15 次 / 1 格(十六分) 14 次, 约 4:1 |
| 单次群发 | 3~10 条 (峰值 23) |
| 起手缩放 | **18%~40%**, 300ms 涨到 63% |
| 单条寿命 | 0.5~0.9s (长族 2.8s) |
| 运动 | 从字心螺旋外扩, frz 1500ms 转 300~600deg |
| 颜色 | **同刻 5~7 色并置** |
| 密度比 | 高潮 148~215 条/5s vs 主歌 43~75 = 3~5 倍 |

**尺寸口径(关键, 我第一版就在这里错了)**: 参考成品的 `fscx18%~40%` 是相对**它自己画的大路径**,
实测换算到 1080p 的墨迹中位是 **12.4 x 11.6 px**(720p 实测 8.3x7.7, ×1.5)。
我方第一版把小图形的基准尺寸写成 4~9px 再乘 18%, 实际只有 0.7~5.7px —— **差一倍以上, 渲染出来看不见**。
所以这里的 `base_size` 默认按 **26~46px 的基准**给, 乘 18%~63% 后落在 5~29px, 与参考同量级。

## 三条硬纪律

1. **不许长成"字".** 卡点层是伴奏触发, 必然与人声错位; 一旦它看起来像文字,
   观众会拿它判断"唱到哪了", 结果是觉得字幕错了. 所以它只做光/粒子/形变/位移.
2. **起手必须小.** 实测 18%~40%, 不是 100%. 从满尺寸开始就没有"爆发".
3. **同刻多色.** 一次群发里 5~7 种颜色并置, 这是"颜色区分"在专业作品里的真实出处.
"""
import math

from . import shapes as S


# ------------------------------------------------------------------ 音乐事件表
class MusicEvents:
    """music_events.py 的产物 (review/music-events.json).

    grid      十六分/八分网格点(秒)
    onset     谱通量起音(鼓点), strength 里带归一化强度
    sub       低频峰(重量感)
    section   段落边界(与 chordwiki 的转调点互验)
    """

    def __init__(self, d):
        self.d = d or {}
        self.grid = list(self.d.get("grid") or [])
        self.onset = list(self.d.get("onset") or [])
        self.sub = list(self.d.get("sub") or [])
        self.section = list(self.d.get("section") or [])
        self.bpm = self.d.get("bpm")
        self.step = self.d.get("grid_step") or (60.0 / self.bpm / (self.d.get("grid_div") or 4)
                                                if self.bpm else None)
        self.strength = self.d.get("strength") or {}

    @classmethod
    def load(cls, path):
        import json
        return cls(json.load(open(path, encoding="utf-8")))

    def grid_between(self, t0, t1):
        return [t for t in self.grid if t0 <= t < t1]

    def grid_at(self, t, tol=0.02):
        """离 t 最近且落在一个网格中的点, 供'只在卡点上发射'用"""
        if not self.step:
            return None
        best = None
        for g in self.grid_between(t - self.step, t + self.step):
            d = abs(g - t)
            if d <= tol * 4 and (best is None or d < abs(best - t)):
                best = g
        return best

    def onsets_between(self, t0, t1, min_strength=0.0):
        return [t for t in self.onset if t0 <= t < t1 and self.strength.get(str(t), self.strength.get(t, 1.0)) >= min_strength]

    def level(self, t):
        """该时刻的卡点等级 0~3: 由该窗内起音密度决定 (对应 impl/density.md 的 L0~L3)"""
        w = 2.0
        n = len([x for x in self.onset if t - w <= x <= t + w])
        if n >= 26:
            return 3
        if n >= 18:
            return 2
        if n >= 10:
            return 1
        return 0

    def levels(self):
        """整曲每秒一个等级, 便于按段落拉开差距"""
        if not self.onset:
            return {}
        out = {}
        t = 0.0
        end = max(self.onset) if self.onset else 0
        while t < end:
            out[round(t, 2)] = self.level(t)
            t += 1.0
        return out


# ------------------------------------------------------------------ 卡点层
# 图形族: 必须是"现代、有区分度、不指涉具体人物"的形状.
# 用户 2026-10-03: 「具有区分的, 然后应该是比较现代的…你不要是番剧元素,
#   因为突然出现一个人的话在这里作为卡点不是很好」(点兔那种吉祥物图是另一层: 图片层)
BEAT_SHAPES = {
    "spark":      lambda r: S.sparkle(r),                       # 四芒星: 高频、锐
    "streak":     lambda r: S.streak(r * 2.6, r * 0.22),        # 短光条: 速度感
    "ring":       lambda r: S.ring(r, max(0.6, r * 0.16)),      # 脉冲环: 冲击
    "shard":      lambda r: S.shard(_RngShim(r), r),            # 碎片: 破碎
    "bolt":       lambda r: S.bolt(_RngShim(r), r * 2.2, r * 0.2),  # 电弧: 电音
    "tri":        lambda r: S.poly([(-r, r * 0.62), (r, r * 0.62), (0, -r * 0.86)]),  # 三角: 锐利现代
    "hex":        lambda r: _hex(r),                            # 六边形: 科技感
    "diamond":    lambda r: S.poly([(0, -r), (r * 0.72, 0), (0, r), (-r * 0.72, 0)]),
    "arc":        lambda r: S.arc(r, -70, 70, max(0.8, r * 0.28)),  # 弧: 扫过
    "beam":       lambda r: S.stroke([(0, 0), (0, -r * 3.2)], max(0.6, r * 0.18)),  # 光束
}


class _RngShim:
    """shard/bolt 需要 rng.uniform, 这里给一个由尺寸派生的确定性实现(卡点层要可复现)"""

    def __init__(self, seed):
        self._s = seed

    def uniform(self, a, b):
        x = math.sin(self._s * 12.9898) * 43758.5453
        return a + (b - a) * (x - math.floor(x))

    def random(self):
        return self.uniform(0, 1)

    def randint(self, a, b):
        return int(self.uniform(a, b + 0.999))


def _hex(r):
    pts = []
    for i in range(6):
        a = math.radians(60 * i - 90)
        pts.append((math.cos(a) * r, math.sin(a) * r))
    return S.poly(pts)


# 同刻并置的色族: 亮青蓝系为主 + 两支高饱和对比色(实测参考用色风格)
BEAT_COLORS = {
    "cyan":   ["#00FFFF", "#00B4FF", "#8EFFE6", "#41FF32", "#32FF6C", "#32FFB9"],
    "sunset": ["#FFD060", "#FF8A3C", "#FF5A8A", "#FFF0C0", "#FFB0D8", "#FFFFFF"],
    "jade":   ["#7CFFC4", "#3FE0A0", "#A8FFE0", "#E8FFF4", "#21C7A8", "#8EFFE6"],
    "violet": ["#C08CFF", "#8A5AFF", "#E0C8FF", "#FF8AE0", "#6A5AE0", "#F0E0FF"],
}


def beat_scatter(f, me, t0, t1, level=2, cx=None, cy=None, colors=None, seed=7,
                 per_beat=(3, 10), long_ratio=0.35, layer=2, xl=None, xr=None,
                 base_size=(26.0, 46.0), spread=(38, 150), fade=(18, 40), grow=63.0,
                 alpha=(190, 250)):
    """按音乐网格铺一整个区间的卡点群发.

    f         FX 实例(带 band 夹取)
    me        MusicEvents
    t0, t1    区间(通常等于一句或一段)
    level     0~3, 对应 impl/density.md; 决定每拍条数与是否加长族
    cx, cy    发射原点(默认 band 中心)
    colors    色族名或色表; 默认按 level 在 cyan/sunset 间切换
    per_beat  每次群发的条数范围(参考实测 3~10)
    base_size 图形基准尺寸(px). **乘起手缩放前**的值
    spread    从原点外扩的距离范围(px)
    fade      (lo, hi) 起手缩放百分比; 参考实测 18~40
    grow      300ms 内涨到的缩放百分比; 参考实测 63

    实现要点(与参考成品对齐):
      * 起手缩小到 18%~40%, 300ms 内涨到 63% -> "爆发"来自这个比例差
      * 从原点螺旋外扩, 同时 frz 旋转
      * 一次群发里取多个不同颜色(同刻并置)
      * level 越高: 群发越密、条数越多、寿命越长
    """
    R = f.rng
    b = f.b
    if cx is None:
        cx = (b[0] + b[2]) / 2
    if cy is None:
        cy = (b[1] + b[3]) / 2
    if xl is None:
        xl = b[0] + (b[2] - b[0]) * 0.06
    if xr is None:
        xr = b[0] + (b[2] - b[0]) * 0.94
    if colors is None:
        colors = "sunset" if level >= 2 else "cyan"
    cols = BEAT_COLORS.get(colors, colors)

    div = 2 if level >= 2 else 1          # L2/L3 用八分, L0/L1 用十六分间隔的 1/2
    names = list(BEAT_SHAPES)
    # 每格至少一发的密度; level 低时稀疏
    if len(me.grid_between(t0, t1)) == 0:
        return 0
    emit = 0
    for gi, g in enumerate(me.grid_between(t0, t1)):
        if gi % div:
            continue
        strong = me.strength.get(str(g), me.strength.get(g, 0.5)) or 0.5
        lo, hi = per_beat
        k = int(round(lo + (hi - lo) * (0.35 * strong + 0.2 * level)))
        if level >= 2 and gi % (div * 2) == 0:
            k += 3
        k = max(1, min(23, k))
        # 位置: 在 band 内取一段横向范围
        for _ in range(k):
            u = R.random()
            x0 = xl + (xr - xl) * u
            y0 = cy + R.uniform(-1, 1) * (b[3] - b[1]) * 0.30
            ang = R.uniform(0, 2 * math.pi)
            rad = R.uniform(*spread)
            x1 = x0 + math.cos(ang) * rad
            y1 = y0 + math.sin(ang) * rad * 0.75
            sz = R.uniform(*base_size) * (0.8 if level <= 1 else (1.0 if level == 2 else 1.25))
            # 寿命分布对齐参考实测: 中位 1.09s, 均值 1.41s, >2s 占 23%
            life = R.uniform(0.55, 1.35) if R.random() > long_ratio else R.uniform(2.0, 2.9)
            nm = names[int(R.random() * len(names)) % len(names)]
            dr = BEAT_SHAPES[nm](sz)
            col = cols[int(R.random() * len(cols)) % len(cols)]
            # 起手 18%~40% -> 300ms 到 63%; 这是"爆发"的来源
            s0 = R.uniform(*fade)
            spin = R.uniform(300, 600) * (1 if R.random() < 0.5 else -1)
            ex = (f"\\fscx{s0:.0f}\\fscy{s0:.0f}"
                  f"\\t(0,300,0.7,\\fscx{grow:.0f}\\fscy{grow:.0f})"
                  f"\\t(0,{int(life*1000)},\\frz{spin:.0f})")
            f.shape(layer, g, g + life, x0, y0, x1, y1, draw=dr, c1=col,
                    a_peak=R.randint(*alpha), blur=R.uniform(0.6, 1.5),
                    fade_in=0.05, fade_out=life * 0.55, extra=ex, accel=0.8)
            emit += 1
    return emit


def beat_pulse(f, me, t0, t1, level=2, cx=None, cy=None, colors="cyan", layer=0, every=4):
    """拍级脉动: 在强拍上给 band 一整片柔光呼吸(低存在感, 不与散射抢).

    `every`: 每几格一次; 4 = 每四分音符(拍)一次
    """
    b = f.b
    if cx is None:
        cx = (b[0] + b[2]) / 2
    if cy is None:
        cy = (b[1] + b[3]) / 2
    cols = BEAT_COLORS.get(colors, colors)
    rx = (b[2] - b[0]) * 0.5
    ry = (b[3] - b[1]) * 0.5
    n = 0
    for gi, g in enumerate(me.grid_between(t0, t1)):
        if gi % every:
            continue
        a = 90 + 45 * level
        f.glow(layer, g, g + (me.step or 0.125) * every * 0.9,
               cx, cy, rx, ry, cols[n % len(cols)],
               a_peak=min(150, a), blur=24, fade_in=0.03, fade_out=0.12)
        n += 1
    return n


def beat_drop(f, me, t, level=3, cx=None, cy=None, colors=None, layer=1, size=120, rings=3):
    """段落起爆点: riser/drop 处的单次大爆发(全曲只该有几次).

    与参考成品的区别: 它用大量小元素, 这里额外给一个"环 + 碎片"的结构,
    让段落边界在视觉上"翻页", 而不是"变密".
    """
    b = f.b
    if cx is None:
        cx = (b[0] + b[2]) / 2
    if cy is None:
        cy = (b[1] + b[3]) / 2
    cols = BEAT_COLORS.get(colors or ("sunset" if level >= 2 else "cyan"), None) or colors
    for i in range(rings):
        f.pulse(layer, t + i * 0.10, cx, cy, S.ring(size * (0.5 + 0.28 * i), 2.4),
                cols[i % len(cols)], dur=0.55 + 0.12 * i, s0=30, s1=190, a0=190, blur=1.6)
    for k in range(14):
        ang = k / 14 * 2 * math.pi
        f.shape(layer + 1, t, t + 1.1, cx, cy,
                cx + math.cos(ang) * size * 1.5, cy + math.sin(ang) * size * 0.6,
                draw=BEAT_SHAPES["streak"](6.5), c1=cols[k % len(cols)],
                a_peak=200, blur=1.4, fade_in=0.03, fade_out=0.7,
                extra="\\fscx40\\fscy40\\t(0,220,0.6,\\fscx100\\fscy100)", accel=0.8)
    return rings + 14


def beat_sink(f, me, t0, t1, cx=None, layer=0, colors=("#2A2036", "#1A1424")):
    """低频下沉: 低频峰处的暗色重量块(不亮, 只给"压下去"的感觉)"""
    b = f.b
    if cx is None:
        cx = (b[0] + b[2]) / 2
    n = 0
    for t in me.sub:
        if not (t0 <= t < t1):
            continue
        rx = (b[2] - b[0]) * 0.40
        ry = (b[3] - b[1]) * 0.34
        f.shape(layer, t, t + 0.42, cx, b[3] - ry * 0.6,
                draw=S.ellipse(rx, ry), c1=colors[n % len(colors)],
                a_peak=70, blur=26, fade_in=0.04, fade_out=0.24)
        n += 1
    return n
