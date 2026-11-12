# -*- coding: utf-8 -*-
"""高光句特效 (bar.json h1-h5). 本曲新写, 不从其他工程拷贝.
每个函数的时间点取自 bar.json 的 music_event, 构图取自 shots.json 或 anime.elements.md 的母题.
r2 (2026-11-08): 盲审 r1 判 6 句都 "没到参照水平" 且认不出本作. 改法: 图形铺满字带 (band 是硬上限,
不能出带, 见 validate_ass), 不透明度提到能一眼看见, 母题换成作品卡上有名字的东西 (洛琪希的蓝发麻花辫, 艾莉丝的剑与红发, 无咏唱魔术)."""
from scene import *  # noqa: F401,F403
import motif_img  # noqa: E402
import fx_main  # noqa: E402
import math  # noqa: E402

SNOW, SPRING, GOLD, BLUSH, WHITE = "#FFFFFF", "#56A697", "#FCD487", "#F9D0C4", "#FFFFFF"
ERIS, ROXY, RUST = "#C8202E", "#4A6FB5", "#A2522E"


def hand(s, spread=0.0):
    """手的剪影: 掌 + 四指 + 拇指, 指尖朝上. s = 掌宽. spread 张开角 (弧度)."""
    d = S.ellipse(s * 0.5, s * 0.55, 0, s * 0.35)
    for i, dx in enumerate((-0.33, -0.11, 0.11, 0.33)):
        ln = s * (0.62, 0.72, 0.7, 0.58)[i]
        a = (i - 1.5) * spread
        cx, cy = dx * s + math.sin(a) * ln * 0.5, -s * 0.1 - math.cos(a) * ln * 0.5
        pts = [(math.cos(t * math.pi / 8) * s * 0.1, math.sin(t * math.pi / 8) * ln * 0.5) for t in range(16)]
        d += S.poly(S.move(S.rot(pts, a), cx, cy))
    d += S.poly(S.move(S.rot([(math.cos(t * math.pi / 8) * s * 0.11, math.sin(t * math.pi / 8) * s * 0.3)
                               for t in range(16)], -0.9), -s * 0.52, s * 0.25))
    return d


def braid(n, r):
    """麻花辫: n 节交错的椭圆, 竖直向下, 末端收细."""
    d = ""
    for i in range(n):
        k = 1 - i / (n * 1.6)
        d += S.ellipse(r * k, r * 0.75 * k, (r * 0.35) * (1 if i % 2 else -1), i * r * 1.15)
    return d


def ribbon(L, w, amp, ph=0.0):
    """飘动的长条 (红发): 一条正弦曲线加粗, 两端收尖."""
    pts = [(x, math.sin(x / L * math.pi * 2 + ph) * amp) for x in [L * i / 24 for i in range(25)]]
    return S.stroke(pts, w, taper=True)


def snow_cap(w):
    """字顶的积雪: 下平上圆的雪堆."""
    pts = [(-w / 2 + w * i / 16, -math.sin(math.pi * i / 16) * w * 0.32) for i in range(17)]
    return S.poly(pts + [(w / 2, 3), (-w / 2, 3)])


MOTIF_MAX = 80   # 母题尺寸上限 = band 高 242 的 1/3. 母题一律放在字两侧, 不许压字 (C 阶段, 用户复审 71s 帧)


def line_shape(f, layer, t0, t1, x0, y0, x1=None, y1=None, draw="", color="#FFFFFF", a_line=30, a_fill=225, bord=2.0,
               blur=0.8, fade_in=0.4, fade_out=0.6, **kw):
    """线稿式母题: 描边 (主题色, 实) + 近乎全透明的同色填充. 不出实心肤色块.
    alpha 分开写 \\1a / \\3a, 不用 \\alpha (那会把填充也拉实)."""
    d = t1 - t0
    fi, fo = ms(min(fade_in, d / 2)), ms(min(fade_out, d / 2))
    at = (f"\\1a&HFF&\\3a&HFF&\\t(0,{fi},\\1a{al(a_fill)}\\3a{al(a_line)})"
          f"\\t({ms(d) - fo},{ms(d)},\\1a&HFF&\\3a&HFF&)")
    f.shape(layer, t0, t1, x0, y0, x1, y1, draw, color, c3=color, bord=bord, blur=blur, alpha_t=at, **kw)


def floor_circle(f, t0, t1, x, y, r, c_out, c_in, dps, fps=16, a_peak=90, seed=7, grow=0.5, fade_in=0.5, fade_out=0.5,
                 angle0=0):
    """地面魔法阵 = 外阵 (magic_circle) + 反向内符文环 (rune_ring), 都走 floor_spin 逐帧预旋转+压扁, 不用 \\t 转.
    C 阶段 (2026-11-08): 只在 h2 (第 8, 9 句 洛琪希授课阵) 与 h3 (第 24 句 转移事件阵) 用, 不全曲撒."""
    f.floor_spin(0, t0, t1, x, y, S.magic_circle(r), c_out, deg_per_s=dps, fps=fps, a_peak=a_peak, blur=1.0,
                 grow=grow, fade_in=fade_in, fade_out=fade_out, angle0=angle0)
    f.floor_spin(0, t0, t1, x, y, S.rune_ring(r * 0.62, rng=random.Random(seed)), c_in, deg_per_s=-dps * 1.6, fps=fps,
                 a_peak=a_peak + 20, blur=0.8, grow=grow, fade_in=fade_in, fade_out=fade_out, angle0=-angle0 * 1.6)


def _ell(rx, ry, n=48, rev=False):
    pts = [(rx * math.cos(2 * math.pi * i / n), ry * math.sin(2 * math.pi * i / n)) for i in range(n)]
    pts = pts[::-1] if rev else pts
    return "m " + " l ".join(f"{x:.1f} {y:.1f}" for x, y in pts) + " "


def floor_fill(f, t0, t1, x, y, r, c_fill, c_rim, fa=200, ra=190, squash=0.26, grow=0.8, fade_in=0.6, fade_out=0.8,
               dy=0.0, ryk=0.92):
    """地面阵内部: 冷色底 (横 0.92r, 纵 ryk 倍, 下移 dy: 阵后半更亮, blur 10) + 阵线内侧暖雾环 (0.80r..0.95r, 内圈反向成洞, blur 8). 与 floor_circle 同心同压扁."""
    gr = f"\\fscx30\\fscy30\\t(0,{int(grow * 1000)},0.5,\\fscx100\\fscy100)"
    f.shape(0, t0, t1, x, y + dy, draw=_ell(r * 0.92, r * squash * ryk), c1=c_fill, a_peak=fa, blur=10, fade_in=fade_in,
            fade_out=fade_out, extra=gr)
    ring = _ell(r * 0.95, r * squash * 0.95) + _ell(r * 0.80, r * squash * 0.80, rev=True)
    f.shape(0, t0, t1, x, y, draw=ring, c1=c_rim, a_peak=ra, blur=8, fade_in=fade_in, fade_out=fade_out, extra=gr)


def fx_thaw_bloom(f, ph, k, t0=32.729):
    """h1 / 第 2 句: 字顶的积雪在 貴方が欲しい 起音处化开滑落, 雪花变成新叶. 2026-11-09 起颜色跟 judge/hue.json 第 2 句 (暖橙金), 不再是春山青."""
    R = f.rng
    a, b = span(ph.chars)
    for c in ph.chars:
        if c["kind"] == "punct":
            continue
        f.shape(4, k.t_in, t0 + 0.9, c["x"], JY - 50, c["x"], JY - 34, snow_cap(c["w"] * 0.8), SNOW, a_peak=0, blur=0.8,
                fade_in=0.3, fade_out=0.6, t_move=(ms(t0 - k.t_in), ms(t0 - k.t_in) + 900))
        if c["s"] >= t0 - 0.05:
            f.shape(5, c["s"], c["s"] + 1.0, c["x"], JY - 30, c["x"], CN_REL(70), S.teardrop(6), k.th["pale"], a_peak=20,
                    blur=0.6, fade_in=0.05, fade_out=0.4, accel=1.7)
    f.drift(k.t_in, t0, 14, [SNOW], lambda s: S.snowflake(s), vx=(-10, 10), vy=(20, 40), size=(6, 11), a=(0, 60),
            blur=(0.4, 0.9))
    f.drift(t0, k.t_end, 16, [k.th["glow"], k.th["pale"]], lambda s: S.leaf(s), vx=(-30, 30), vy=(-40, -15), size=(9, 15),
            a=(0, 50), blur=(0.4, 0.8))
    # 2026-11-09: 原来是整句 (字宽+180)x160 的春山青椭圆 blur24 (不透明 57%) 从中间拉开, 37.5s 实测把整条字带盖成一块绿布.
    # 改成贴字的近白光晕: 每个化开的字一团, 只盖字本身 (参考同帧是白/金色的贴字光晕).
    for c in ph.chars:
        if c["kind"] != "punct" and c["s"] >= t0 - 0.05:
            f.glow(0, c["s"], k.t_end, c["x"], JY, c["w"] * 0.55, 44, k.th["pale"], a_peak=190, blur=14, fade_in=0.25,
                   fade_out=0.8)


def fx_palm_cradle(f, ph, k):
    """h2 前半 / 第 8 句 教えてくれた: 大手 (洛琪希) 与小手 (鲁迪) 从字带两端升起, 唱完时在句下合拢 (ED s14 托手).
    左上垂下洛琪希的蓝发麻花辫, 随句摆动."""
    a, b = span(ph.chars)
    cx = (a + b) / 2
    t, te = ph.chars[0]["s"], ph.chars[-1]["e"]
    # 大手 (洛琪希, 蓝) 与小手 (鲁迪, 粉) 在字两侧外缘从下升起, 唱完向内倾; 只描线, 不压字
    for sgn, s, col_ in ((-1, 36, "#9FB8E6"), (1, 44, BLUSH)):
        x0 = (a - 50) if sgn < 0 else (b + 50)
        line_shape(f, 2, t - 0.4, k.t_out, x0, CN_REL(50), x0, JY - 14, hand(s, 0.1), col_, a_line=20, a_fill=220, bord=2.2,
                   blur=0.8, fade_in=0.5, fade_out=0.6, t_move=(0, ms(te - t + 0.4)),
                   extra=f"\\frz{-sgn * 40}\\t(0,{ms(te - t)},\\frz{-sgn * 15})")
    line_shape(f, 4, t - 0.4, k.t_out, a - 70, JY - 40, a - 70, JY - 26, braid(6, 8), ROXY, a_line=10, a_fill=200,
               bord=1.8, fade_in=0.6, fade_out=0.6, t_move=(0, 2400))
    # 2026-11-09: 原整句 (字宽+120)x140 粉霞底板 blur26 改成逐字贴字光晕, 同 thaw_bloom.
    for c in ph.chars:
        if c["kind"] != "punct":
            f.glow(0, c["s"], k.t_end, c["x"], JY, c["w"] * 0.55, 44, k.th["pale"], a_peak=190, blur=14, fade_in=0.3)
    # 洛琪希的授课阵: 两手合拢处的地面上慢慢转开, 接到第 9 句白光 (fx_whiteout_reach 续转)
    floor_circle(f, 68.0, k.t_end, cx, CN_REL(62), 170, "#8FB0F0", "#CFE0FF", -20, seed=8, grow=1.2, a_peak=30,
                 fade_in=0.8, fade_out=0.05)
    for c in find(ph, "教"):
        f.burst(c["s"], c["x"], JY + 30, 10, [BLUSH, WHITE, GOLD], speed=(20, 50), up=1.6, size=(3, 5), life=(1.0, 1.8))


def fx_whiteout_reach(f, ph, k, t0=75.395):
    """h2 后半 / 第 9 句 貴方だけ: 低音落下 (sub 75.395) 时整条字带被白光吞没, 一只手的剪影伸向光 (同 ED s15)."""
    bx0, by0, bx1, by1 = f.b[:4]
    cx, cy = (bx0 + bx1) / 2, (by0 + by1) / 2
    f.shape(0, t0, t0 + 2.6, cx, cy, draw=S.ellipse((bx1 - bx0) / 2 - 20, (by1 - by0) / 2 - 20), c1=WHITE, a_peak=30,
            blur=28, fade_in=0.08, fade_out=2.0)
    a, b = span(ph.chars)
    line_shape(f, 1, t0 + 0.1, k.t_end, b + 54, CN_REL(50), b + 54, JY - 10, hand(44, 0.16), GOLD, a_line=20, a_fill=215,
               bord=2.2, blur=1.0, fade_in=0.3, fade_out=1.0, t_move=(0, 1600), extra="\\frz-15")
    f.pulse(0, t0, (a + b) / 2, JY, S.ring(110, 4), GOLD, dur=1.2, s0=30, s1=100, a0=40, blur=3)
    # 授课阵续转: 白光落下前慢转, 低音落下后加速并被白光烧成金色, 唱完散去
    cx = (a + b) / 2
    floor_circle(f, k.t_in, t0, cx, CN_REL(62), 170, "#8FB0F0", "#CFE0FF", -20, seed=8, grow=0, a_peak=30, fade_in=0.05,
                 fade_out=0.05)
    floor_circle(f, t0, max(k.t_end, 80.0), cx, CN_REL(62), 170, GOLD, WHITE, -90, seed=8, grow=0, a_peak=60,
                 fade_in=0.05, fade_out=1.2, angle0=-20 * (t0 - k.t_in))


def fx_mana_crack(f, ph, k, t0=164.908):
    """h3 / 第 24 句 壊したい: 每个 壊 被魔力光从内部撑裂, 起音 164.908 白光圆从句心炸开铺满字带 (菲托亚领转移事件)."""
    R = f.rng
    for c in find(ph, "壊"):
        for j in range(2):
            f.shape(6, c["s"], k.t_out, c["x"], JY, draw=S.crack(R, 120, 4, 3), c1=WHITE, a_peak=0, blur=1, c3=k.th["glow"],
                    bord=2, a3=30, fade_in=0.08, fade_out=0.4, extra=f"\\frz{R.uniform(-60, 60):.0f}")
        f.glow(1, c["s"], k.t_out, c["x"], JY, 80, 70, k.th["glow"], a_peak=190, blur=20, fade_in=0.3)
    a, b = span(ph.chars)
    cx = (a + b) / 2
    bx0, by0, bx1, by1 = f.b[:4]
    # 转移事件的阵: 句起就在字下转, 起音 164.908 前后同一个阵 (逐帧, 速度快, 金白)
    # 2026-11-09 节奏复核: 原写死到 170.0, 阵转进留白句 p25 (句首 57/s, 带光环). 收到本句结束.
    # 2026-11-09 密度收缩: p24 句中亮度 48802 (参考 30329), 收一档. 阵是逐帧件, 帧数不动, 只调淡 (a_peak 70 -> 115);
    # 爆光 a 40 -> 90, 放射光束 18 -> 12. 第二档: 阵 a 115 -> 160, 壊 裂纹描边 3 -> 2 / 光晕 a 150 -> 190.
    floor_circle(f, 162.0, k.t_end + 0.3, cx, CN_REL(58), 120, k.th["glow"], WHITE, 70, seed=24, a_peak=160, grow=0.8,
                 fade_in=0.6, fade_out=0.8)
    f.shape(0, t0, t0 + 0.9, cx, (by0 + by1) / 2, draw=S.ellipse(((bx1 - bx0) / 2 - 6) * 0.4, ((by1 - by0) / 2 - 6) * 0.4), c1=WHITE,
            a_peak=90, blur=14, fade_in=0.02, fade_out=0.5, extra="\\fscx5\\fscy5\\t(0,350,0.6,\\fscx100\\fscy100)")
    for i in range(12):
        ang = i * 360 / 12 + R.uniform(-6, 6)
        f.shape(5, t0, t0 + 1.1, cx, JY, draw=S.streak(R.uniform(200, 320) * 0.4, 7), c1=WHITE, a_peak=10, blur=1.5,
                c3=k.th["glow"], bord=2, a3=60, fade_in=0.03, fade_out=0.6, extra=f"\\frz{ang:.0f}\\fscx30\\t(0,250,\\fscx100)")


def fx_sword_cut(f, ph, k, t0=189.521):
    """h4 / 第 29 句 逃げない. 2026-11-12 老板定: 删旧剑斩 (剑讲"斩断", 29 句讲"不逃", 叙事冲突), 只留主母题铁链 + 裂纹.
    旧实现 (矢量剑 + 红斜斩痕 + 红发飘带 + 红金碎火) 备份在 scratch/bak_sword/fx_high.py.base."""
    fx_main.p29(f, ph, k)   # 2026-11-11 主母题 (逃)


def mamo_shield(f, t0, t1, cx, cy, rx=61, ry=83, nb=0.2, half=128, grow=0.9, steps=15, s0=1.12):
    """2026-11-11 v4 (老板定): 256° 开口护罩弧包住首个「守」(连振假名), 缺口朝「り」; 蛋形 (下端收窄 nb), 不做正圆.
    弧从左侧 180° 往两端长出来, 同时从 s0 倍往里收到 1 (从外面收拢护住, 离字最近在停住时).
    三层同形 (和字的三层同语汇, 单层加粗只会变粗月牙): 外光晕 #7FC8FF (加宽 5px, blur 9) / 芯 #CFE0FF 2.6px /
    内衬金 #FFD66B (向内 1px). fade_in 不能写 0: libass 把 \t(0,0) 当整段时长, 弧会慢慢亮整句 (v3 踩过). 只在两端各 15% 收锥, 中段饱满. 端点光晕 = 光从开口透出; 金符文点沿弧 -15°/s 流动.
    整弧不转: 一转缺口就离开「り」, 弧会压字. 几何与间隙由 scratch/geo_ring.py + v4.py 实渲量出, 改尺寸要重量."""
    import math

    def path(s, hs, dn=0.0, n=64):
        out = []
        for i in range(n + 1):
            t = math.radians(180 - hs + 2 * hs * i / n); sn = math.sin(t)
            out.append((cx + (rx * s - dn) * math.cos(t) * (1 - nb * max(0, sn)), cy + (ry * s - dn) * sn))
        return out

    def band(pts, w, tip=0.15):              # 粗线: 只在两端 tip 比例内收锥
        n = len(pts) - 1; L, Rr = [], []
        for i, (x, y) in enumerate(pts):
            a, b = pts[max(0, i - 1)], pts[min(n, i + 1)]
            dx, dy = b[0] - a[0], b[1] - a[1]; dl = math.hypot(dx, dy) or 1
            u = min(i, n - i) / (n * tip); hw = w / 2 * (0.25 + 0.75 * min(1, u))
            L.append((x - dy / dl * hw, y + dx / dl * hw)); Rr.append((x + dy / dl * hw, y - dx / dl * hw))
        q = L + Rr[::-1]
        return "m %.1f %.1f l " % q[0] + " ".join("%.1f %.1f" % p for p in q[1:]) + " "
    t0 = round(t0, 2); dt = round(grow / steps, 2); tg = t0 + steps * dt
    for i in range(steps + 1):
        e = 1 - (1 - min(1, (i + 1) / steps)) ** 3
        s, hs, last = s0 - (s0 - 1) * e, 20 + (half - 20) * e, i == steps
        ta, tb, fo = (tg, t1, 0.8) if last else (t0 + i * dt, t0 + (i + 1) * dt, 0)
        for lay, w, dn, c, a, bl in ((2, 2.6 + 5, 0, "#7FC8FF", 165, 9), (3, 2.6, 0, "#CFE0FF", 30, 0.7),
                                     (4, 2.6, 1, "#FFD66B", 195, 0.5)):
            f.shape(lay, ta, tb, 0, 0, draw=band(path(s, hs, dn), w), c1=c, a_peak=a, blur=bl, an5=False,
                    fade_in=0.01, fade_out=fo)
    for x, y in (path(1, half)[0], path(1, half)[-1]):
        f.shape(4, tg, t1, x, y, draw=S.circle(9), c1="#7FC8FF", a_peak=170, blur=5, fade_in=0.4, fade_out=0.8)
        f.shape(4, tg, t1, x, y, draw=S.circle(3.5), c1=WHITE, a_peak=30, blur=2, fade_in=0.4, fade_out=0.8)
    fps, gap = 8, 2 * half / 11
    for j in range(int((t1 - tg) * fps)):
        ta = tg + j / fps; d = ""
        for q in range(11):
            a = 180 - half + (q * gap - 15 * (ta - tg)) % (2 * half)
            if min(a - (180 - half), 180 + half - a) < 10:
                continue
            t = math.radians(a); sn = math.sin(t)
            x, y = cx + rx * math.cos(t) * (1 - nb * max(0, sn)), cy + ry * sn
            d += f"m {x - 2.2:.1f} {y:.1f} l {x:.1f} {y - 2.2:.1f} {x + 2.2:.1f} {y:.1f} {x:.1f} {y + 2.2:.1f} "
        if d:
            f.shape(5, ta, min(t1, ta + 1 / fps), 0, 0, draw=d, c1="#FFD66B", a_peak=60, blur=0.6, an5=False,
                    fade_in=0.01, fade_out=0.8 if ta + 1 / fps >= t1 else 0)


def fx_water_orb(f, ph, k, t0=201.47):
    """h5 / 第 31 句 守りたい…教えてくれた: 摊开的手掌上不念咒地凝出一颗洛琪希蓝的水球 (无咏唱魔术), 到 教え 长到最大.
    2026-11-09 节奏复核 (用户定): 原 "没有阵" 让收尾高光比铺垫句 p07 还暗, 10 秒几乎静止. 参考在 守りたい 召回第 7 句
    的地面魔法阵, 这里同样召回: 同一套 floor_circle, fps=10, 从句首转到句尾 (不只在句首); 水滴改为全句持续汇入."""
    R = f.rng
    a, b = span(ph.chars)
    # 2026-11-11 v3 (老板定): 主母题改成「字被护住」= mamo_shield 开口弧包住首个「守」; 手降为辅助 (洛琪希出现过的记号),
    # fit 76, 放在弧左下外侧, 从左下升起 1.3s, 撑过句末 k.t_end 再淡出 0.8s; 水球 28px 跟着手.
    c_mamo = find(ph, "守")[0]
    t_h0, t_h1, t_up = c_mamo["s"], k.t_end + 0.8, 1.3
    mamo_shield(f, t_h0, t_h1, c_mamo["x"] + 0.3, JY + 1)
    hx, hy = c_mamo["x"] + -80, 1012          # 手终点
    ox, oy = hx + -12, hy + -8              # 水球 (掌心偏左) = 水滴汇入点 / 爆点
    if not motif_img.place(f, "p31_palm", 1, t_h0, t_h1, hx + -30, hy + 30, fade_in=t_up, fade_out=0.8,
                           x1=hx, y1=hy, t_move=(0, int(t_up * 1000)), hue=k.th):
        line_shape(f, 1, t_h0, t_h1, hx, hy, draw=hand(40, 0.05), color="#9FB8E6", a_line=20, a_fill=220,
                   bord=2.0, blur=0.8, fade_in=t_up, fade_out=0.8)
    # 2026-11-12 (老板定, 212s 量): 阵内比参考暗 (上缘 21.8 vs 38.4, 下缘 48.7 vs 72.6), 阵外两边一样 (5.4 vs 6.0).
    # 补阵内: 低亮度冷色底填充 + 阵线内侧一圈暖褐雾 (#B08A6A 系). 都按阵的压扁比 (0.26) 画, 不出阵外; 与阵同步 grow 0.8s.
    floor_fill(f, t0 - 0.2, k.t_end, (a + b) / 2, JY + 10, 440, "#3A5078", "#B08A6A", fa=182, ra=205, dy=14.0, ryk=0.84)
    floor_circle(f, t0 - 0.2, k.t_end, (a + b) / 2, JY + 10, 440, k.th["glow"], k.th["pale"], 40, fps=10, seed=31,
                 a_peak=105, grow=0.8, fade_in=0.6, fade_out=0.8)
    nd = int((k.t_out - 1.2 - t0) / 0.2)
    for i in range(nd):
        x0 = ox + R.uniform(-200, 60); y0 = oy + R.uniform(-60, 80)
        tt = t0 + i * 0.2
        f.shape(5, tt, tt + 1.2, x0, y0, ox, oy, S.teardrop(6), "#BFD3F2", a_peak=10, blur=0.6, fade_in=0.1,
                fade_out=0.2, t_move=(0, 1000), accel=0.6)
    te = seq(ph, "教え")
    t_big = te[0]["s"] if te else t0 + 4
    # 2026-11-11 v2: 水球只当掌心一侧的水魔法点题 (直径 ~28px), 手托到位后才凝出, 与手同时淡出.
    t_o0 = t_h0 + t_up
    if not motif_img.place(f, "p31_orb", 4, t_o0, t_h1, ox, oy, fade_in=0.5, fade_out=0.8, hue=k.th,
                           init="\\fscx30\\fscy30", anim=[(0, t_big - t_o0, "\\fscx100\\fscy100")]):
        f.shape(4, t_o0, t_h1, ox, oy, draw=S.circle(14), c1="#9FB8E6", a_peak=120, blur=1.0, c3=ROXY, bord=1.5,
                fade_in=0.5, fade_out=0.8, extra=f"\\fscx30\\fscy30\\t(0,{ms(t_big - t_o0)},\\fscx100\\fscy100)")
        f.shape(5, t_o0, t_h1, ox - 5, oy - 6, draw=S.ellipse(3.5, 2.5), c1=WHITE, a_peak=20, blur=1, fade_in=0.5,
                fade_out=0.8, extra=f"\\fscx30\\fscy30\\t(0,{ms(t_big - t_o0)},\\fscx100\\fscy100)")
    f.burst(k.t_out, ox, oy, 16, ["#BFD3F2", ROXY, WHITE], draw_fn=lambda r: S.teardrop(r * 1.4), speed=(40, 100),
            up=0.6, size=(3, 5), life=(0.5, 1.0))
