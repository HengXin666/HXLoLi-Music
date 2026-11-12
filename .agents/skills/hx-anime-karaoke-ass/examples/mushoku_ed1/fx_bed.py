# -*- coding: utf-8 -*-
"""氛围床 + 逐字命中 (plan.md 1.7 的第 1, 2 层). B 阶段 (2026-11-08) 新增.

每句都铺, 不论角色: rest 句也有, 只降速降透明 (推翻 v3 "留白 = 空").
  bed : 整句窗口 [t_in, t_end] 内不断的漂浮粒子. 一部分在字后 (layer 0), 一部分在字前 (layer 6).
  hits: 每个字起音时发 2-5 颗小粒子, 在字前 (layer 7); carrier/high 另加一个小光环 (layer 5).
粒子种类按句的主题取 (雪 / 新芽 / 光尘 / 余烬 / 花瓣羽毛 / 魔力 / 剑屑 / 水滴), 颜色只用 style.json 色板.
调用在各句主函数之后, 用同一个 f.rng 往后续抽, 所以不改变主函数已有的随机结果.
"""
import math
import os
from scene import *  # noqa: F401,F403

WHITE, SNOW, SNOWB = "#FFFFFF", "#DBE5F0", "#8CA4C0"
SPRING, GOLD, RUST, BLUSH, DUSK = "#56A697", "#FCD487", "#A2522E", "#F9D0C4", "#CF7F4F"
ERIS, ROXY, PAPER = "#C8202E", "#4A6FB5", "#F7E5CC"


def _star4(s):
    return S.star(4, s, s * 0.32)


def _star5(s):
    return S.star(5, s, s * 0.42)


def _mote(s):
    return S.circle(s * 0.45)


def _bubble(s):
    return S.ring(s * 0.6, max(1.0, s * 0.14))


def _flower(s):
    return S.flower(s * 0.8)


def _hexa(s):
    return S.star(6, s, s * 0.55)


def _rain(s):
    return S.raindrop(s * 2.2, 1.4)


def _streak(s):
    return S.streak(s * 3.2, s * 0.35)


# 主题: (粒子画法们, 颜色们, 命中画法, 命中颜色)
THEMES = {
    "snow":  ([S.snowflake, _mote, S.sparkle], [WHITE, SNOW, SNOWB], S.snowflake, [WHITE, SNOW]),
    "thaw":  ([S.leaf, S.snowflake, _flower, S.dandelion], [SPRING, "#8FD1B8", WHITE], _flower, [WHITE, "#8FD1B8"]),
    "gold":  ([_star5, S.sparkle, S.music_note], [GOLD, "#FFF0C8", WHITE], S.music_note, [GOLD, WHITE]),
    "rust":  ([_mote, _star4, S.flame], [RUST, GOLD, "#E0874A"], "crack", [GOLD, "#FFE0B0"]),
    "blush": ([S.petal, S.feather, S.sakura], [BLUSH, "#FFF4F0", PAPER], S.sakura, [BLUSH, WHITE]),
    "dusk":  ([S.feather, S.maple, S.dandelion, S.bird], [DUSK, PAPER, "#E9A66B"], S.feather, [PAPER, DUSK]),
    "mana":  ([_star4, S.sparkle, _hexa], [GOLD, "#FFFBEA", WHITE], S.sparkle, [GOLD, WHITE]),
    "sword": ([_streak, "shard", S.sparkle], [ERIS, "#E8E8F0", GOLD], S.sparkle, [WHITE, ERIS]),
    "water": ([S.teardrop, _bubble, _rain], ["#BFD3F2", ROXY, WHITE], _bubble, ["#BFD3F2", WHITE]),
}

FX_THEME = {
    "snow_write": "snow", "snow_plain": "snow", "thaw_bloom": "thaw", "chorus_float": "gold", "chorus_beat": "gold",
    "crack_hint": "rust", "ring_guard": "gold", "palm_cradle": "blush", "whiteout_reach": "blush", "veil_hide": "dusk",
    "tear_drop": "blush", "quiet": "dusk", "mana_crack": "mana", "sword_cut": "sword", "water_orb": "water",
    "echo_reach": "dusk",
}

# 角色强度: 每秒新生粒子, 字前比例, 粒子透明度区间(0=不透明), 每字命中颗数, 是否加光环, 尺寸
MODES = {
    # C 阶段 (2026-11-08, 用户复审 177s 帧: 安静句只剩 10 条 HAD-HBE 的几十 px 小点, 看不见):
    # rest 提密度/尺寸/不透明度, 并加雾层 (fog). 视觉分量要够, 不是靠条数堆.
    "rest":    dict(rate=5.0, front=0.35, a=(35, 110), hit=2, ring=False, size=(11, 19), life=(2.8, 4.4), fog=150),
    # 2026-11-09 节奏复核: 伴奏抽空段 Q (p25-28, 预算 0.1) 实测 18.6/s, 比 C2/V2 还高. hush 只留慢速低透明床, 每字 1 颗.
    "hush":    dict(rate=2.4, front=0.30, a=(70, 140), hit=1, ring=False, size=(11, 18), life=(3.2, 4.8), fog=150),
    # 2026-11-09 节奏复核: V1 开头两句雪句 (p00/p01) 存活到 40, 比 C1 挤. 床与逐字命中都减一档.
    "snow":    dict(rate=3.4, front=0.40, a=(40, 130), hit=2, ring=True, size=(9, 15), life=(2.0, 3.4), fog=170),
    "carrier": dict(rate=4.8, front=0.40, a=(40, 130), hit=3, ring=True, size=(9, 15), life=(2.0, 3.4), fog=170),
    "high":    dict(rate=9.0, front=0.45, a=(40, 140), hit=4, ring=True, size=(7, 13), life=(1.6, 3.0), fog=185),
}


# 2026-11-09 密度收缩: 门禁只设下限, 实测每句中位 77 (参考 40), 存活中位 21 (参考 7). 先收氛围床与逐字命中
# (数量最好砍, 不动结构), 逐帧件不动. BED_K 床出生率倍数, HIT_K 每字命中倍数, RING_EVERY 光环隔几字一个,
# BIG: 床数量减后单颗放大/提亮的倍数 (亮度掉超 10% 时用). 环境变量只供调参, 定值写在缺省里.
BED_K = float(os.environ.get("DENS_BED", "0.5"))
HIT_K = float(os.environ.get("DENS_HIT", "0.67"))
RING_EVERY = int(os.environ.get("DENS_RING", "2"))
BIG = float(os.environ.get("DENS_BIG", "1.0"))

FLUTTER = (S.petal, S.feather, S.leaf, S.maple, S.sakura, _flower, S.dandelion)
TWINKLE = (S.sparkle, _star4, _star5, _mote, _hexa, S.music_note)


def twinkle(n, per, a, t0=0):
    """闪烁: 在峰值透明度与更淡之间来回 (\\1a, 不覆盖淡入淡出用的 \\alpha)."""
    lo = min(255, a + 90)
    return "".join(f"\\t({t0+k*per},{t0+k*per+per//2},\\1a{al(lo)})\\t({t0+k*per+per//2},{t0+(k+1)*per},\\1a{al(a)})" for k in range(n))


def tinted(k, theme):
    """2026-11-09: 粒子颜色跟句子色相走 (make_ass.hue_theme 给的 glow/pale), 画法仍按 FX_THEME. 雪还是白的."""
    _, cols, _, hcols = THEMES[theme]
    th = getattr(k, "th", None) or {}
    if "pale" not in th:
        return cols, hcols
    if theme == "snow":
        return [WHITE, th["pale"], th["pale"]], [WHITE, th["pale"]]
    return [th["glow"], th["pale"], WHITE], [th["pale"], th["glow"], WHITE]


def bed(f, ph, k, theme, mode, decay=False):
    m = MODES[mode]
    draws, _, _, _ = THEMES[theme]
    cols, _ = tinted(k, theme)
    R = f.rng
    t0, t1 = k.t_in, k.t_end
    bk = 1.0 if mode == "hush" else BED_K   # 留白段 Q 已单独调到 发射 6.3 / 存活 11.2, 不再收
    n = max(3, int(round(m["rate"] * bk * (t1 - t0))))
    for j in range(n):
        dr = draws[j % len(draws)]
        if dr == "shard":
            dr = (lambda s, R=R: S.shard(R, s * 0.9))
        elif theme == "rust" and dr is S.flame:
            dr = (lambda s, lean=R.uniform(-0.4, 0.4): S.flame(s * 0.9, lean))
        layer = (8 if u < m["front"] * 0.6 else 6) if (u := R.random()) < m["front"] else 0   # 2026-11-11: front 六成 L8 四成 L6, 仍只抽一次随机数
        L = R.uniform(*m["life"])
        if decay:   # 2026-11-09: 末句床寿命 x0.5 (2.0-3.4 -> 1.0-1.7), 早生的不在中段堆积, 存活随发射单调下降
            L *= 0.5
        ts = R.uniform(t0 - 0.2, t1 - L * 0.5)
        if decay:   # 末句渐弱: 出生时刻密度线性递减
            ts = t0 + (t1 - L * 0.5 - t0) * (1 - math.sqrt(1 - R.random()))
        ts = max(ts, t0)
        te = min(ts + L, t1 + 0.3)
        if te - ts < 0.4:
            continue
        b = f.b
        x = R.uniform(b[0] + 12, b[2] - 12)
        y = R.uniform(b[1] + 12, b[3] - 12)
        up = -1 if theme in ("thaw", "mana", "rust", "water") else 1   # 新芽/魔力/余烬/气泡往上, 雪/花/羽往下
        dx = R.uniform(-22, 22) * (te - ts)
        dy = up * R.uniform(8, 26) * (te - ts)
        sz = R.uniform(*m["size"]) * {0: 1.0, 6: 0.8, 8: 0.62}[layer] * BIG   # 2026-11-11: 越靠前越小越淡; 新增层必须显式给档, 漏了直接 KeyError
        a = max(0, R.randint(*m["a"]) + {0: 0, 6: 25, 8: 45}[layer] - int(round((BIG - 1) * 120)))
        d_ms = int((te - ts) * 1000)
        if dr in FLUTTER:      # 花瓣/羽毛/叶子: 左右翻摆
            per = R.randint(500, 900)
            spin = f"\\frz{R.randint(-40, 40)}" + sway(max(1, d_ms // per), per, R.randint(18, 40)) + f"\\t(\\fry{R.choice((-70, 70))})"
        elif dr in TWINKLE:    # 星/光尘: 闪烁
            per = R.randint(260, 520)
            spin = f"\\frz{R.randint(0, 360)}\\t(\\frz{R.randint(-120, 120)})" + twinkle(max(0, (d_ms - 1100) // per), per, min(235, a), t0=300)  # 只在淡入后, 淡出前闪
        else:
            spin = f"\\frz{R.randint(0, 360)}\\t(\\frz{R.randint(-240, 240)})"
        f.shape(layer, ts, te, x, y, x + dx, y + dy, dr(sz), R.choice(cols), a_peak=min(235, a),
                fade_in=min(0.5, (te - ts) * 0.3), fade_out=min(0.8, (te - ts) * 0.4), blur=R.uniform(0.5, 1.6), extra=spin,
                effect=("over" if layer else ""))   # 2026-11-13 #13: 字前 (L6/L8) 的床粒子是有意盖字, 显式豁免; 字后 (L0) 照量


def fog(f, ph, k, theme, mode):
    """字后掠光 (layer 0). 2026-11-09 改 (老板复审 37.5s: 字带被一块青绿糊雾盖住).

    旧做法: 整句一块 (字宽+160)x124 椭圆 blur30 呼吸缩放 + 几团 110-170px 大雾团横移, 颜色取主题粒子色.
    实测 37.5s (L02 thaw): 1231x124 / 1251x160 两块 #56A697 底板, 不透明 27%/57%, 盖住 x356-1563 y813-1030
    共 217k 像素; 参考同帧第 0 层只有一道 311-414px 宽, blur14, 不透明 24% 的近白掠光 (48k 像素).
    新做法照参考: 撤掉底板和雾团, 每 ~3.2s 一道贴字的细长近白光带, 只在字的横向范围内从左扫到右.
    """
    t0, t1 = k.t_in, k.t_end
    a, b = span(ph.chars)
    d = t1 - t0
    w = max(220.0, min(420.0, (b - a) * 0.32))
    if b - a < w + 40:
        return
    n = max(1, int(d / 3.2))
    for j in range(n):
        ts = t0 + 0.2 + j * d / n
        te = min(t1, ts + 3.5)
        if te - ts < 1.0:
            continue
        f.shape(0, ts, te, a + w / 2, JY + 14, b - w / 2, JY + 10, S.ellipse(w / 2, 6), "#E8EEF6", a_peak=215,
                blur=14, fade_in=(te - ts) * 0.2, fade_out=(te - ts) * 0.25)


def hits(f, ph, k, theme, mode, decay=False):
    m = MODES[mode]
    _, _, hdraw, _ = THEMES[theme]
    _, hcols = tinted(k, theme)
    R = f.rng
    if hdraw == "crack":        # 裂纹句: 每个音拍崩出一道细小裂纹碎屑 (crack_hint 的逐字版)
        hdraw = (lambda s, R=R: S.crack(R, s * 4.5, 1.2, 2))
    cs = [c for c in ph.chars if c["kind"] != "punct"]
    for ci, c in enumerate(cs):
        x, y = c["x"], c["y"]
        hk = m["hit"] * (1.0 if mode == "hush" else HIT_K)
        nh = int(hk) + (1 if R.random() < hk - int(hk) else 0)
        nh = max(0, nh - ci) if decay else nh     # 末句渐弱: 后面的字命中越来越少
        for _ in range(nh):
            ang = R.uniform(0, 2 * math.pi)
            v = R.uniform(28, 70)
            L = R.uniform(0.45, 0.9)
            dx, dy = math.cos(ang) * v, math.sin(ang) * v * 0.6 - v * 0.35
            f.shape(7, c["s"], c["s"] + L, x + R.uniform(-c["w"] * 0.3, c["w"] * 0.3), y - 10, x + dx, y - 10 + dy,
                    hdraw(R.uniform(3, 6)), R.choice(hcols), a_peak=R.randint(10, 80), fade_in=0.05, fade_out=L * 0.7,
                    blur=R.uniform(0.4, 1.0), accel=0.8, extra=f"\\frz{R.randint(0, 360)}\\t(\\frz{R.randint(-200, 200)})",
                    effect="over")   # 2026-11-13 #13: 逐字命中粒子 (L7) 有意盖字, 显式豁免
        if m["ring"] and not (decay and ci > 0) and ci % (1 if mode == "hush" else RING_EVERY) == 0:
            if mode == "high" and theme in ("mana", "water"):   # 魔术句: 每字一个符文环 (无咏唱魔术的母题)
                f.pulse(5, c["s"], x, y, S.rune_ring(c["w"] * 0.6, rng=R), hcols[0], dur=0.7, s0=40, s1=120, a0=60, blur=0.8,
                        extra=f"\\t(\\frz{R.choice((-60, 60))})", effect="over")   # 音节光环 (L5) 有意盖字
            else:
                f.pulse(5, c["s"], x, y, S.ring(c["w"] * 0.55, 2.2), hcols[0], dur=0.5, s0=50, s1=125, a0=70, blur=1.0,
                        effect="over")   # 音节光环 (L5) 有意盖字


def apply(f, ph, k, fxname, mode):
    theme = FX_THEME.get(fxname, "dusk")
    if fxname == "quiet" and k.P["lines"][0] in (25, 26, 27, 28):
        mode = "hush"
    if fxname == "snow_write":
        mode = "snow"
    decay = fxname == "echo_reach"
    bed(f, ph, k, theme, mode, decay=decay)
    fog(f, ph, k, theme, mode)
    hits(f, ph, k, theme, mode, decay=decay)
