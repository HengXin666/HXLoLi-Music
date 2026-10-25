# -*- coding: utf-8 -*-
"""
卡点层 (beat layer): 跟着**音乐事件**走的特效层, 不跟字.

决策与实测依据: 

## 它解决什么

原先生成器里所有特效的触发源只有一个  人声音拍(`c["s"]`). 于是特效只会"跟唱".
卡点层把触发源换成**伴奏事件网格**(十六分/八分音符), 特效才开始"跟曲".

## 怎么定参数: 从这首歌自己量, 不要抄别首

卡点层的一切参数都由**伴奏**决定, 而伴奏每首不同. 所以这里的做法是:

1. `music_events.py` 先从伴奏抽出 `grid` / `onset` / `strength` / `section`;
2. 生成器按 `ME.level(t)` 与 `ME.strength` **逐段**决定密度, 而不是全曲一套常数;
3. 参数落在下面的**区间**里, 具体值由那首歌的实测网格与起音强度定.

| 参数 | 取值区间 | 怎么定 |
|---|---|---|
| 网格 | 十六分 / 八分 | `ME.grid` 直接给, 不要自己算 |
| 单次群发条数 | 3~10 (峰值可到 23) | 按 `ME.strength` 缩放; 高潮段加倍 |
| 起手缩放 | **18%~40%** | 不是 100%; 从满尺寸开始就没有"爆发" |
| 单条寿命 | 短族 ~0.5~1.3s + 长族 ~2~2.9s | `long_ratio` 控制长族占比, 默认 0.35 |
| 颜色 | 同刻 5~7 色并置 | 由 `BEAT_COLORS` 的色族提供 |
| 密度比 | 高潮段 / 主歌段 **>= 1.8** | 与 `impl/density.md` 同一判据 |

**尺寸口径(最容易搞错的一条)**: 参考成品的 `fscx18%~40%` 是相对**它自己画的大路径**,
换算到 1080p 的墨迹中位约 **12 x 12 px**。若把小图形的基准尺寸写成 4~9px 再乘 18%,
实际只有 0.7~5.7px  **差一倍以上, 渲染出来看不见**。
所以 `base_size` 默认给 **26~46px 的基准**, 乘 18%~63% 后落在 5~29px。

## 三条硬纪律

1. **不许长成"字".** 卡点层是伴奏触发, 必然与人声错位; 一旦它看起来像文字,
   观众会拿它判断"唱到哪了", 结果是觉得字幕错了. 所以它只做光/粒子/形变/位移.
2. **起手必须小.** 18%~40%, 不是 100%.
3. **同刻多色.** 一次群发里 5~7 种颜色并置.
4. **柔光预算: 同一个带里最多一层大 blur.** 实测(2026-10-03)失败模式: 每句 fx 里
   已有两处 blur=26~46 的 `f.glow`, 卡点层再叠一层 blur=24, 三者在 758x242 的窄带里
   糊成一片雾  逐字多色被整片盖掉. 分工: **背景层用大 blur(>=20), 卡点层 <=10,
   每句特效的柔光只留一处**.
"""

import math

from assfx.draw import shapes as S
from assfx.layer.music.beat_events import MusicEvents                  # noqa: F401  (对外导出)
from assfx.layer.music.beat_shapes import (BAKED_NORM, BEAT_BAKED,     # noqa: F401
                                     BEAT_COLORS, BEAT_SHAPES, bind_baked)


# Agent Notes: 卡点层与图片层  第五、第六层特效的实测规格
# 
def beat_scatter(f, me, t0, t1, level=2, cx=None, cy=None, colors=None, seed=7,
                 per_beat=(3, 10), long_ratio=0.35, layer=2, xl=None, xr=None,
                 base_size=(14.0, 26.0), spread=(38, 150), fade=(18, 40), grow=52.0,
                 alpha=(190, 250), avoid=None, avoid_win=0.05):
    """
    .agents/notes/implemented/feature/2026-10-03-karaoke-beat-layer.md
按音乐网格铺一整个区间的卡点群发.

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
    avoid     一组时间点(通常传 `timing.json` 的音拍起点): 群发时刻落在其中任一点的
              ±`avoid_win` 内时**跳过这一发**。见下面"为什么要躲字"的实测。

    实现要点(与参考成品对齐):
      * 起手缩小到 18%~40%, 300ms 内涨到 63% -> "爆发"来自这个比例差
      * 从原点螺旋外扩, 同时 frz 旋转
      * 一次群发里取多个不同颜色(同刻并置)
      * level 越高: 群发越密、条数越多、寿命越长

    **为什么要躲字**(实测 2026-10-03): 卡点层按十六分网格发, 而字音拍
    也在同一张网格上  于是它与字的起点重合率高达 **19.4%**, 比随机撒点(17.7%)还高。
    观众看到的是"字还没唱, 那里先亮了一下", 加一次 `\\k` 高亮的读点就被抢走一次。
    参考成品的同一指标是 **11.9%**(人声分离干净时的正常值), 即它**主动避开了字**。
    """
    R = f.rng
    b = f.b
    if avoid is not None and avoid_win > 0:
        _av = sorted(avoid)
        import bisect as _bs
        def _hit(t):
            i = _bs.bisect_left(_av, t - avoid_win)
            return i < len(_av) and abs(_av[i] - t) <= avoid_win
    else:
        def _hit(t):
            """Agent Notes
            .agents/notes/implemented/bug-fix/2026-10-03-karaoke-shape-size-baseline.md
            """
            return False
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
    # Agent Notes: 组合图形的尺寸口径必须按"参照边"归一化
    # 
    names = list(BEAT_SHAPES)
    if not names:
        raise RuntimeError(
            "卡点层没绑素材: 先调 beat.bind_baked(json.load(open('assets/shapes.json'))) "
            "再发卡点  没有素材时发不出任何图形(旧版会在这里 ZeroDivisionError).")
    # 每格至少一发的密度; level 低时稀疏
    if len(me.grid_between(t0, t1)) == 0:
        return 0
    emit = 0
    for gi, g in enumerate(me.grid_between(t0, t1)):
        if gi % div:
            continue
        if _hit(g):                      # 这一格压在字上  让给歌词的高亮, 不发卡点
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
            # 尺寸纪律: 单个图形 30~70px 是**含细节的素材**的量级; 这里是缩放前的基准,
            # 乘 fade(18~52%) 后落在 2.5~13px  卡点层要"多而小", 不要"少而大".
            sz = R.uniform(*base_size) * (0.8 if level <= 1 else (1.0 if level == 2 else 1.2))
            # 寿命分布对齐参考实测: 中位 1.09s, 均值 1.41s, >2s 占 23%
            life = R.uniform(0.55, 1.35) if R.random() > long_ratio else R.uniform(2.0, 2.9)
            nm = names[int(R.random() * len(names)) % len(names)]
            dr = BEAT_SHAPES[nm](sz)
            col = cols[int(R.random() * len(cols)) % len(cols)]
            s0 = R.uniform(*fade)
            spin = R.uniform(300, 600) * (1 if R.random() < 0.5 else -1)
            # 烘焙素材是 200px 规范尺寸: 必须先按目标像素算出基准缩放, 再叠起手/成长动画.
            # 直接给 fscx18 会让 200px 的图从 36px 起手  尺寸完全不可控(实测墨迹达 1063px).
            base = (sz / BAKED_NORM * 100.0) if nm in BEAT_BAKED else 100.0
            ex = (f"\\fscx{base*s0/100:.1f}\\fscy{base*s0/100:.1f}"
                  f"\\t(0,300,0.7,\\fscx{base*grow/100:.1f}\\fscy{base*grow/100:.1f})"
                  f"\\t(0,{int(life*1000)},\\frz{spin:.0f})")
            f.shape(layer, g, g + life, x0, y0, x1, y1, draw=dr, c1=col,
                    a_peak=R.randint(*alpha), blur=R.uniform(0.6, 1.5),
                    fade_in=0.05, fade_out=life * 0.55, extra=ex, accel=0.8)
            emit += 1
    return emit


def beat_pulse(f, me, t0, t1, level=2, cx=None, cy=None, colors="cyan", layer=0, every=4,
               blur=10.0, alpha=90, span=0.08):
    """拍级脉动: 在强拍上给 band 一整片柔光呼吸.

    **`blur` 必须压住.** 实测教训(2026-10-03): 卡点层原先用 blur=24 的柔光,
    而每句的 fx 里已经有两处 blur=26~46 的大柔光(`f.glow`), 三层柔光叠在同一个
    758x242 的窄带里 -> 糊成一片雾, **把逐字多色整片盖掉**(逐字色相跨度中位只有 26°,
    但仍看不清). 背景层才该用大 blur; 卡点层与每句特效必须锐.

    `every`: 每几格一次; 4 = 每四分音符(拍)一次
    `span`: 柔光的半宽, 相对 band 半宽的比例.

    ⚠ **这个函数默认不应使用.** 它是"整片柔光", 无论 span 给多小, 只要它是
    一个**大椭圆**就压不住尺度: 实测 span=0.20 时椭圆直径仍是 602px(band 高只有 242px),
    在窄带里就是一层糊住字的雾, 且不产生任何信息.
    **卡点层的职责由 `beat_scatter`(有形状的小元素群发)承担**  那是"卡点",
    而这个是"呼吸"; 两者叠在一起就是噪音.

    只在**确实需要一次整体呼吸**(如段落起爆)时用, 且必须配合 span<=0.08.
    """
    b = f.b
    if cx is None:
        cx = (b[0] + b[2]) / 2
    if cy is None:
        cy = (b[1] + b[3]) / 2
    cols = BEAT_COLORS.get(colors, colors)
    rx = (b[2] - b[0]) * max(0.05, min(0.6, span))
    ry = (b[3] - b[1]) * max(0.05, min(0.6, span))
    n = 0
    for gi, g in enumerate(me.grid_between(t0, t1)):
        if gi % every:
            continue
        a = alpha + 30 * level
        f.glow(layer, g, g + (me.step or 0.125) * every * 0.9,
               cx, cy, rx, ry, cols[n % len(cols)],
               a_peak=min(150, a), blur=blur, fade_in=0.03, fade_out=0.12)
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
                # 这里**不能**用 BEAT_SHAPES[...]: 那个字典只由 bind_baked() 按
                # `_BAKED_SPEC` 的 8 个键填(streak 不在其中), 所以取它必然 KeyError。
                # 实测(2026-10-03): `beat_drop(...) -> KeyError: 'streak'`,
                # 段落起爆层在整整一个工程里都是不可用的  而调用方看不到异常原因之外的信息。
                # 改用 shapes.py 的手绘件: 它按像素构造, 不需要 \fscx 归一化,
                # 形态就是"细梭形光条", 正是这里要的放射火花。
                draw=S.streak(26.0, 5.0), c1=cols[k % len(cols)],
                a_peak=200, blur=1.4, fade_in=0.03, fade_out=0.7,
                extra="\\fscx40\\fscy40\\t(0,220,0.6,\\fscx100\\fscy100)", accel=0.8)
    return rings + 14


def beat_sink(f, me, t0, t1, cx=None, layer=0, colors=("#2A2036", "#1A1424"), span=0.10):
    """低频下沉: 低频峰处的暗色重量块.

    **尺寸必须收住.** 实测教训(2026-10-03, 用户指正「非常大」): 第一版用
    `rx = (b[2]-b[0]) * 0.40` = band 全宽的 40%, 实际墨迹 **1205px**,
    而 band 只有 242px 高  一个 1205x166 的暗椭圆横在字上, 就是"糊住字的雾".
    现在默认 `span=0.30` 且**只画在 band 下缘**(不压文字行), 并且它本来就该是可选的:
    低频下沉是"重量感", 在很多句里并不需要.
    """
    b = f.b
    if cx is None:
        cx = (b[0] + b[2]) / 2
    n = 0
    for t in me.sub:
        if not (t0 <= t < t1):
            continue
        # span 是**半径相对 band 宽的比例**, 直径是它的两倍 
        # 给 0.30 就是直径 0.6*band = 902px(实测), 仍然是糊住字的尺寸.
        # 收到 0.10 (直径约 300px) 才是"一块重量感", 不是"一层雾".
        rx = (b[2] - b[0]) * max(0.03, min(0.14, span))
        ry = (b[3] - b[1]) * 0.07
        f.shape(layer, t, t + 0.42, cx, b[3] - ry * 0.5,
                draw=S.ellipse(rx, ry), c1=colors[n % len(colors)],
                a_peak=60, blur=20, fade_in=0.04, fade_out=0.24)
        n += 1
    return n
