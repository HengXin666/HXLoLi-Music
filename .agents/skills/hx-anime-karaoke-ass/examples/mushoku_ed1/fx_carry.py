# -*- coding: utf-8 -*-
"""承载句与留白句的特效 (arc.json 里 role=carrier / rest). 每个函数对应 arc 的一个手法标签.
颜色只取 judge/style.json 的色板. 承载句的力度要低于高光句, 不发大范围粒子."""
from scene import *  # noqa: F401,F403
from fx_high import hand, snow_cap, line_shape, floor_circle  # noqa: E402
import fx_bed  # noqa: E402
import fx_main  # noqa: E402

SNOW, SNOWB, SPRING, PAPER = "#DBE5F0", "#8CA4C0", "#56A697", "#F7E5CC"
GOLD, RUST, BLUSH, DUSK = "#FCD487", "#A2522E", "#F9D0C4", "#CF7F4F"


# 2026-11-09 节奏复核: 第二段雪句 p10-p12 不再同一手感连用三句. 每句至少变两样 (方向/速度/尺寸/密度).
SNOW_VAR = {10: dict(n=9, vx=(-10, 10), vy=(18, 36), size=(5, 8)),       # 直落
            11: dict(n=8, vx=(14, 34), vy=(8, 18), size=(7, 11))}         # 往右斜飘, 慢, 大片


def fx_snow_write(f, ph, k, cap=True):
    """snow-write: 字写出后被一层薄雪盖住 (第 0, 1 句). 第二段 (cap=False) 不盖雪, 字角留小尖.
    2026-11-09 节奏复核: 雪帽从每字一个改为隔三个字一个 (V1 比 C1 挤, p01 存活到 51), 飘雪 14 -> 9."""
    R = f.rng
    if cap:
        for c in [c for c in ph.chars if c["kind"] != "punct"][::3]:
            f.shape(4, c["e"], k.t_out, c["x"], JY - 50, c["x"], JY - 40, snow_cap(c["w"] * 0.8), "#FFFFFF", a_peak=0,
                    blur=0.8, fade_in=0.4, fade_out=0.3, t_move=(0, 400))
    v = SNOW_VAR.get(k.P["lines"][0], SNOW_VAR[10])
    f.drift(k.t_in, k.t_end, 6 if cap else v["n"], ["#FFFFFF", SNOW], lambda s: S.snowflake(s), vx=(-10, 10) if cap else v["vx"],
            vy=(18, 36) if cap else v["vy"], size=(6, 11) if cap else v["size"], a=(0, 60) if cap else (30, 90), blur=(0.4, 0.9))
    if not cap:
        for c in ph.chars[::3]:
            f.pulse(4, c["s"], c["x"] + c["w"] / 2, JY - 30, S.sparkle(10), SNOWB, dur=0.5, s0=40, s1=100, a0=40, blur=0.6)


def fx_snow_plain(f, ph, k):
    fx_snow_write(f, ph, k, cap=False)


def fx_snow_gust(f, ph, k):
    """第 12 句 悲しむ顔は負けなセオリー 素直でイタイ: 不再是第三句落雪. 一阵横风把细雪往右扫 (快, 小, 近水平),
    字嘴硬地站直; イタイ 唱到时字后泛一下红 (arc: 稍微发红)."""
    R = f.rng
    f.drift(k.t_in, k.t_end, 16, ["#FFFFFF", SNOW], lambda s: S.snowflake(s), vx=(70, 120), vy=(2, 10), size=(4, 6),
            a=(40, 110), blur=(0.6, 1.2))
    for c in seq(ph, "イタイ") or []:
        f.glow(0, c["s"], c["s"] + 1.0, c["x"], JY, c["w"] * 0.6, 44, BLUSH, a_peak=150, blur=16, fade_in=0.15, fade_out=0.6)


def fx_chorus_float(f, ph, k, flash=None):
    """chorus-float: 和声英文段 (第 3, 4, 13, 14 句). 英文浮在一条细光带上, 表示另一个声音."""
    lat = [c for c in ph.chars if c["kind"] == "latin"]
    if lat:
        a, b = span(lat)
        f.shape(0, lat[0]["s"] - 0.2, lat[-1]["e"] + 0.4, (a + b) / 2, JY, draw=S.ellipse((b - a) / 2 + 30, 34), c1=k.th["glow"],
                a_peak=185, blur=16, fade_in=0.3, fade_out=0.4)
        f.shape(3, lat[0]["s"] - 0.2, lat[-1]["e"] + 0.4, (a + b) / 2, JY + 36, draw=S.rect(b - a + 30, 4), c1=k.th["glow"],
                a_peak=40, blur=1.5, fade_in=0.3, fade_out=0.4)
    if flash:
        t, x = flash, mid(ph.chars)
        f.glow(0, t, t + 0.6, x, JY, 260, 50, k.th["pale"], a_peak=190, blur=24, fade_in=0.05, fade_out=0.5)


def fx_chorus_beat(f, ph, k):
    fx_chorus_float(f, ph, k, flash=109.923)


# 2026-11-09 节奏复核: crack_hint 用在 5 句, p05/p15 帧几乎一样. 每句换尺寸/角度/走向/时长 (相邻两句至少变两样).
CRACK_VAR = {5: dict(sz=110, ang=(-30, 30), mv=(0, 0), dur=1.4),       # 原样: 正裂, 不动
             6: dict(sz=80, ang=(35, 70), mv=(-26, 0), dur=1.0),       # 小, 右斜, 往左滑, 快
             15: dict(sz=150, ang=(-80, -45), mv=(0, -20), dur=1.9),   # 大, 左斜, 往上顶, 慢
             16: dict(sz=95, ang=(-10, 15), mv=(22, 8), dur=0.9),      # 中, 近平, 往右下, 快
             30: dict(sz=125, ang=(65, 100), mv=(0, 16), dur=1.6)}     # 竖裂, 往下坠


def fx_crack_hint(f, ph, k):
    """crack-hint: 壊/純/盾 字边一道赭红细裂纹, 不碎 (第 5, 6, 15, 16, 30 句). 只是预告."""
    R = f.rng
    v = CRACK_VAR.get(k.P["lines"][0], CRACK_VAR[5])
    # 2026-11-12 r8: 第 30 句不画裂纹. 该句主母题是 fx_main.p30 (交叉剑 + 碎片/电弧/火苗), 裂纹穿过「盾」压字并伸进 CN 行,
    # 一句两套母题 (known-gaps #14). 第 5/6/15/16 句的裂纹预告照旧.
    for key in (() if k.P["lines"][0] == 30 else ("壊", "盾", "純", "順")):
        for c in find(ph, key):
            x1, y1 = c["x"] + v["mv"][0], JY + v["mv"][1]
            f.shape(5, c["s"], c["s"] + v["dur"], c["x"], JY, x1, y1, S.crack(R, v["sz"], 3.5, 3), k.th["dark"], c3=k.th["glow"],
                    bord=1.5, a3=60, a_peak=0, blur=0.6, fade_in=0.05, fade_out=0.6, t_move=(0, ms(v["dur"] * 0.7)),
                    extra=f"\\frz{R.uniform(*v['ang']):.0f}")
    if k.P["lines"][0] == 30:
        fx_main.p30(f, ph, k)   # 2026-11-11 主母题 (矛盾)


def fx_ring_guard(f, ph, k):
    """ring-guard: 与第 5 句同骨架, 裂纹换成一圈细光环 (第 7 句: 守りたい)."""
    for c in find(ph, "守"):
        f.shape(4, c["s"], c["s"] + 1.4, c["x"], JY, draw=S.ring(70, 4), c1=k.th["glow"], a_peak=20, blur=1.2, fade_in=0.1,
                fade_out=0.6, extra="\\fscx60\\fscy60\\t(0,300,\\fscx100\\fscy100)")
    # 2026-11-09: 67s 亮像素只有参考 41%. 参考第 7 句 L0 用逐帧步进大光环 (每 0.1s 一帧, 双环交替, ~108 条),
    # 我们只有字边小环 + 粒子. 补 L0 逐帧地面魔法阵, 不加底板.
    a, b = span(ph.chars)
    cx, t0 = (a + b) / 2, ph.chars[0]["s"] + 0.12
    t1 = k.t_end
    # 2026-11-09 二版: 对参考 67s 帧, 参考是地面魔法阵 (外阵 + 反向符文环, 宽 ~800, 压扁), 不是素环.
    # 复用 fx_high.floor_circle (原只给 h2/h3), fps=10 对齐参考 0.1s 步进.
    floor_circle(f, t0, t1, cx, JY + 10, 400, k.th["glow"], k.th["pale"], 24, fps=10, seed=7, a_peak=110, grow=0.6,
                 fade_in=0.5, fade_out=0.6)


def fx_veil_hide(f, ph, k):
    """veil-hide: 第 17, 18 句. 一层暗幕从两侧往里收, 把字半遮住."""
    a, b = span(ph.chars)
    t = ph.chars[0]["s"]
    for sgn in (-1, 1):
        x0 = (a if sgn < 0 else b) + sgn * 60
        f.shape(2, t, k.t_out, x0, JY, x0 - sgn * 60, JY, S.veil(70, 150, waves=4, amp=6), k.th["dark"], a_peak=50,
                blur=6, fade_in=0.4, fade_out=0.3, t_move=(0, 1500))


def fx_tear_drop(f, ph, k):
    """tear-drop: 第 19 句 涙だけ. 对位第 9 句的白闪, 但只有一滴光滑下."""
    for c in find(ph, "涙"):
        f.shape(5, c["s"] + 0.2, c["s"] + 1.8, c["x"] + 10, JY - 10, c["x"] + 10, CN_REL(80), S.teardrop(14), "#FFF4F0",
                a_peak=0, blur=0.8, c3=BLUSH, bord=2, a3=40, fade_in=0.2, fade_out=0.5, accel=1.6)
        f.glow(0, c["s"], c["s"] + 1.8, c["x"], JY, 60, 50, k.th["pale"], a_peak=170, blur=20)


def fx_quiet(f, ph, k):
    """quiet: 留白句 (桥段与伴奏抽空段). B 阶段改: 不再留空 (plan.md 决议 2).
    只铺 rest 强度的氛围床 + 逐字命中: 慢, 淡, 每字 2 颗, 不加光环. 与高光句的对比靠高光往上拔."""
    fx_bed.apply(f, ph, k, "quiet", "rest")


def fx_echo_reach(f, ph, k):
    """echo-reach: 末句 貴方だけ. 第 9 句的回声: 只有一只伸手剪影慢慢淡出, 不白闪."""
    a, b = span(ph.chars)
    # 2026-11-11 r4 (老板): 删去「だけ」右侧夕橙伸手剪影 (2026-11-09 起的第 9 句回声 hand(40,0.14) #CF7F4F).
    # 32 句设计表只有 heart + star4 + petal, 高潮段不留设计表外的图形.
    # 2026-11-09 节奏复核: 字都唱在句前半, 逐字命中后句子后半断崖 (17.8 -> 1.0/s). 加回声余光: 夕照色光尘从字带缓缓
    # 升起, 出生率沿整句线性递减 (约 6/s -> 1.5/s), 让衰减单调而平滑, 不是先闪后空.
    R = f.rng
    t0e, t1e = ph.chars[0]["s"], k.t_end - 0.3
    t = t0e
    while t < t1e:
        x = (t - t0e) / (t1e - t0e)
        L = R.uniform(0.8, 1.3)   # 2026-11-09: 1.2-2.0 -> 0.8-1.3, 存活随发射单调下降
        px = R.uniform(a, b); py = JY + R.uniform(-30, 30)
        f.shape(R.choice((0, 6)), t, min(t + L, k.t_end + 0.3), px, py, px + R.uniform(-15, 15), py - R.uniform(20, 45),
                S.sparkle(R.uniform(6, 10)), R.choice((k.th["pale"], PAPER, DUSK)), a_peak=R.randint(60, 140), blur=0.9,
                fade_in=0.3, fade_out=L * 0.6)
        t += 1.0 / (6.0 - 4.5 * x)
    # 2026-11-09: 原整句 (字宽+120)x80 夕照橙底板 blur26 改成逐字贴字光晕 (不铺满字带).
    for c in ph.chars:
        if c["kind"] != "punct":
            f.glow(0, c["s"], k.t_end, c["x"], JY, c["w"] * 0.55, 40, k.th["pale"], a_peak=205, blur=14, fade_in=0.6,
                   fade_out=1.5)
    fx_main.p32(f, ph, k)   # 2026-11-11 主母题 (貴方)

