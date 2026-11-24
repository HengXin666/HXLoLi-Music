"""2026-11-11 主母题 (老板定): 29 逃 / 30 矛盾 / 32 貴方 各自挂在 weight 字上, 每句 1 主 + 辅.
主母题一律三层同形 (外光晕 + 芯 + 内衬), 不做单层细线 (31 句验证过). 所有事件名带 m 后缀 (fx:p29m 等), 方便单独实渲量间隙/亮度.
fade_in / fade_out 不写 0: libass 把 \\t(0,0) 当整段时长 (31 句 v3 踩过).
位置都按 scratch/geo5.py 量出的字框避让 (>=8px), 矢量件门禁不量, 由 scratch/v5.py 实渲量."""
from scene import *  # noqa: F401,F403
import motif_img  # noqa: E402
import math
from assfx.layer.provenance import main_motif

H29 = {"dark": "#2B3A4A", "base": "#7D8C9C", "glow": "#C9D6E3", "pale": "#EEF3F8"}
H30 = {"dark": "#1A0E10", "base": "#C8102E", "glow": "#FF6B7D", "pale": "#FFD3D9"}
H32 = {"dark": "#FF8FA3", "base": "#FFC2CD", "glow": "#FFF1E6", "pale": "#FFFFFF"}


def _a(v):
    return "&H%02X&" % max(0, min(255, int(v)))


def _out_alpha(d, a, fi, fo):           # 只显示描边 (填充全透明), 描边按 fi/fo 淡入淡出
    fi, fo = ms(min(fi, d / 2)), ms(min(fo, d / 2))
    return f"\\1a&HFF&\\3a&HFF&\\t(0,{fi},\\3a{_a(a)})\\t({ms(d) - fo},{ms(d)},\\3a&HFF&)"


def outline3(f, layer, t0, t1, x, y, draw, h, core, size, cw=2.6, gw=5, gb=9, ga=165, ca=30, ia=195, fi=0.5, fo=0.8,
             extra=""):
    """描边三层: 外光晕 (glow 色, 宽 cw+gw, blur gb) / 芯 (core 色, cw) / 内衬 (dark 色, 缩 2px 同形, 1.2px)."""
    d = t1 - t0
    k = (size - 2) / size * 100
    f.shape(layer, t0, t1, x, y, draw=draw, c1=h["glow"], c3=h["glow"], bord=cw + gw, blur=gb, extra=extra,
            alpha_t=_out_alpha(d, ga, fi, fo))
    f.shape(layer + 1, t0, t1, x, y, draw=draw, c1=core, c3=core, bord=cw, blur=0.7, extra=extra,
            alpha_t=_out_alpha(d, ca, fi, fo))
    f.shape(layer + 1, t0, t1, x, y, draw=draw, c1=h["dark"], c3=h["dark"], bord=1.2, blur=0.5,
            extra=f"\\fscx{k:.1f}\\fscy{k:.1f}" + extra, alpha_t=_out_alpha(d, ia, fi, fo))


def _heart_poly(s, n=24):
    """S.heart 同形, 采样成折线 (每段贝塞尔 n 点). 夹取按路径点算包围盒, 贝塞尔控制点伸到 ±0.9s, 实际心宽只有 ±0.52s."""
    segs = (((0, .35), (-.9, -.2), (-.45, -.95), (0, -.4)), ((0, -.4), (.45, -.95), (.9, -.2), (0, .35)))
    pts = [(0, .35)]
    for p0, p1, p2, p3 in segs:
        for i in range(1, n + 1):
            t = i / n; u = 1 - t
            pts.append(tuple(u ** 3 * a + 3 * u * u * t * b + 3 * u * t * t * c + t ** 3 * d for a, b, c, d in zip(p0, p1, p2, p3)))
    return "m " + " l ".join(f"{x * s:.2f} {y * s:.2f}" for x, y in pts[:-1]) + " "


def _mark(f):
    """给本模块所有事件加 \\q2 标记 (对绘图无效果), v5.py 据此单独实渲量间隙/亮度. 事件名不能改: validate 按名字找 band."""
    orig = f.shape

    def sh(*a, **kw):
        kw["extra"] = "\\q2" + kw.get("extra", "")
        return orig(*a, **kw)
    f.shape = sh


def _unmark(f):
    del f.shape


H29C = {"glow": "#9B8FC8", "core": "#C9C2E6", "dark": "#4A4268"}   # 2026-11-12 29 句铁链 (老板定淡紫)


# 2026-11-12 r6 (按参考 190.6 实测定): 参考的链 = 正面环与侧面环交替互套的真链. 正面环外 ~30x14, 线 ~2px; 侧面环 (转 90° 侧对观众) ~28x7,
# 仍是空心 (中间一道细缝); 正面环中心距 ~40, 即节距 ~20, 侧面环两端各伸进左右正面环的孔里. 链本身亮 ~100 (字 240 的约 42%), 几乎无光晕.
# 两条链走向 (按参考逐列量的链心): 上链左高 y866 往右压到 x~1220 处 y914 再回升到 y897; 下链左低 y960 往上收到 x~1100 处 y928 再落回 y949.
# 即两条链在字身后、句子中后部收拢到几乎相贴 (勒住这一行), 两头张开, 左右都伸出字带. 走向用 Catmull-Rom 过实测点.
# 咬合靠"压一下": 每节带一圈暗描边, 按从左到右顺序画, 后画的那节用暗边在前一节上切出缺口 -> 侧面环在左边压住正面环、在右边被下一节正面环压住, 一上一下.
P29_FACE = dict(w=30, h=14, tl=2.4, tt=1.8)    # 正面环: 左右略粗上下略细
P29_SIDE = dict(w=28, h=7, tl=2.0, tt=1.5)     # 侧面环: 扁, 仍空心
P29_PITCH = 20
P29_COL, P29_EDGE = "#6E6888", "#07060C"       # 灰紫芯 (参考同色系) / 暗描边 (切出压叠缺口)
P29_A = 0                                       # a_peak; 亮度靠颜色定, 不靠 alpha (alpha 会让暗边一起变浅, 缺口就没了)


def _ring(w, h, tl, tt, n=40):
    """横向椭圆环 (填充环带): 外椭圆 w x h 顺时针, 内椭圆 (w/2-tl) x (h/2-tt) 逆时针挖空."""
    import math
    def ell(rx, ry, rev):
        qs = range(n, 0, -1) if rev else range(n)
        return "m " + " l ".join(f"{rx * math.cos(2 * math.pi * q / n):.2f} {ry * math.sin(2 * math.pi * q / n):.2f}" for q in qs)
    return ell(w / 2, h / 2, False) + " " + ell(w / 2 - tl, h / 2 - tt, True) + " "


P29_U = ((345, 866), (580, 882), (860, 901), (1000, 909), (1220, 914), (1400, 908), (1565, 897))
P29_D = ((345, 960), (580, 948), (860, 933), (1000, 928), (1220, 928), (1400, 940), (1565, 949))


def _cr_path(pts, k=24):
    """Catmull-Rom 过控制点, 每段 k 个采样, 返回折线点."""
    P = [pts[0]] + list(pts) + [pts[-1]]; out = []
    for j in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[j - 1], P[j], P[j + 1], P[j + 2]
        for q in range(k):
            t = q / k; t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * (2 * p1[c] + (-p0[c] + p2[c]) * t + (2 * p0[c] - 5 * p1[c] + 4 * p2[c] - p3[c]) * t2
                                    + (-p0[c] + 3 * p1[c] - 3 * p2[c] + p3[c]) * t3) for c in (0, 1)))
    out.append(pts[-1]); return out


def p29_chain(f, t0, t1, pts, lag=0.0, step=0.014):
    """一条链: 沿 pts 的 Catmull-Rom 曲线按弧长每 P29_PITCH 放一节, 正面环/侧面环交替, 首尾为正面环, 每节按当地切线转 (\\frz).
    事件按弧长从左到右排 (同层后画的盖前画的), 每节 bord1.2 暗边 -> 相邻两节交叠处出现一上一下的压叠缺口.
    从左往右逐节锁上 (130%->100%), 单层, layer 0 字后. 事件带 \\fe1 标记 (对绘图无效果), 量链峰时单独实渲."""
    import math
    pl = _cr_path(pts); acc = [0.0]
    for a, b in zip(pl, pl[1:]):
        acc.append(acc[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    L = acc[-1]; n = int(L // P29_PITCH) + 1; n -= 1 - n % 2
    off = (L - (n - 1) * P29_PITCH) / 2
    df = _ring(**P29_FACE); ds = _ring(**P29_SIDE); j = 0
    for i in range(n):
        s_ = off + i * P29_PITCH
        while j < len(acc) - 2 and acc[j + 1] < s_:
            j += 1
        (ax, ay), (bx, by) = pl[j], pl[j + 1]; u = (s_ - acc[j]) / max(acc[j + 1] - acc[j], 1e-9)
        cx, cy = ax + (bx - ax) * u, ay + (by - ay) * u
        rz = -math.degrees(math.atan2(by - ay, bx - ax))               # 屏幕 y 向下: 往右下 = 顺时针 = frz 负
        ts = t0 + lag + i * step
        if ts >= t1 - 0.3:
            break
        ex = f"\\fe1\\frz{rz:.2f}\\fscx130\\fscy130\\t(0,120,0.7,\\fscx100\\fscy100)"
        f.shape(0, ts, t1, cx, cy, draw=df if i % 2 == 0 else ds, c1=P29_COL, c3=P29_EDGE, bord=1.2, blur=0.5,
                a_peak=P29_A, fade_in=0.12, fade_out=0.8, extra=ex)
    return P29_PITCH, n


@main_motif("chain")
def p29(f, ph, k):
    print(f"[main] p29 t0 {ph.chars[0]['s']:.3f} t_end {k.t_end:.3f} t_out {k.t_out:.3f} band {tuple(round(v) for v in f.b[:4])}")
    _mark(f); R = f.rng
    nige = find(ph, "逃")
    t_end = k.t_end + 0.6
    # 2026-11-12 (老板): 主母题由速度线改为上下两条 X 形铁链 = 束缚 (ジレンマから逃げない). 参考 190.6 字带上下各一条链铺到 x1480.
    # 2026-11-12 r4: 上一版下链放 CN 行下方 (y1031) 是参考里不存在的东西, 已撤; 两条链改放 layer 0 字后.
    # 2026-11-12 r7: 走向按参考 190.6 实测 (见 P29_U/P29_D 上方注释). 两条链都在字身后, 句子中后部收拢, 下链在 JP 行脚与 CN 行之间.
    t0 = ph.chars[0]["s"]
    tc = ph.chars[-1]["s"]      # r9: 参考 194.4 链已退净 -> 链在末字「ら」起唱时结束, 0.8s 淡出落在「か」「ら」上 (r8 的 +0.3 在 194.4 仍满亮)
    pt, n = p29_chain(f, t0, tc, P29_U)
    p29_chain(f, t0, tc, P29_D, lag=0.04)
    print(f"[main] p29 chain t_end {tc:.3f} (last char {ph.chars[-1]['s']:.3f})")
    print(f"[main] p29 chain U {P29_U} D {P29_D} n {n} pitch {pt} face {P29_FACE} side {P29_SIDE} col {P29_COL} edge {P29_EDGE}")
    c = nige[0]                                   # 辅 (原速度线位置): 一道裂纹, 首个「逃げない」正下方空带 (CN 行从 x690 起)
    cr = S.crack(R, 200, 5, 3)
    for lay, a, bd, bl in ((4, 110, 2.5, 3), (5, 20, 0, 0.5)):
        f.shape(lay, c["s"], tc, 545, 976, draw=cr, c1=H29["glow"], c3=H29["glow"], bord=bd, a_peak=a, blur=bl,
                fade_in=0.15, fade_out=0.8, extra="\\fscy35\\frz2")
    print(f"[main] p29 逃1 {c['s']:.3f} 逃2 {nige[1]['s']:.3f}")
    c2 = nige[1]                                 # 辅1: 第二个「逃」上方几粒光尘往后 (左) 飘走又淡掉 = 想逃的念头
    for q in range(6):
        t = c2["s"] + q * 0.12; x = c2["x"] + R.uniform(-18, 18); y = 846 + R.uniform(-6, 6)
        f.shape(5, t, t + 1.5, x, y, x - R.uniform(40, 70), y - R.uniform(0, 8), S.circle(R.uniform(2.4, 3.4)),
                H29["glow"], c3=H29["glow"], bord=1, a_peak=R.randint(30, 70), blur=1.2, fade_in=0.15, fade_out=1.0,
                t_move=(0, 1500), accel=0.7)
    # ジレンマ 上方的裂纹 (y846) 已删: 那里现在是上链 (y830-852).
    kr = seq(ph, "から")                          # 辅3: 少量光尘从「から」上方升起
    if kr:
        a_, b_ = span(kr)
        for j in range(7):
            t = kr[0]["s"] + j * 0.28; x = R.uniform(a_ + 6, b_ - 6)
            f.shape(5, t, t + 1.6, x, 874, x + R.uniform(-8, 8), 826, S.circle(R.uniform(2.2, 3.4)), H29["glow"],
                    a_peak=R.randint(40, 90), blur=1.4, fade_in=0.3, fade_out=0.8)
    _unmark(f)


@main_motif("sword_cross")
def p30(f, ph, k):
    print(f"[main] p30 t0 {ph.chars[0]['s']:.3f} t_end {k.t_end:.3f} t_out {k.t_out:.3f} band {tuple(round(v) for v in f.b[:4])}")
    _mark(f); R = f.rng
    mj = seq(ph, "矛盾")
    t_end = k.t_end + 0.6
    if mj:                                        # 主: 两把剑交叉 (sword_red 同图镜像一次) = 对立. 振假名上方只有 ~45px, 剑盾两件放不下 (v5 首帧)
        a_, b_ = span(mj); cx = (a_ + b_) / 2; t0 = mj[0]["s"]
        motif_img.place(f, "p30_sword_a", 6, t0, t_end, cx, 830, fade_in=0.35, fade_out=0.8, hue=H30, extra="\\q2")
        motif_img.place(f, "p30_sword_b", 6, t0 + 0.12, t_end, cx, 830, fade_in=0.35, fade_out=0.8, hue=H30, extra="\\q2")
        print(f"[main] p30 矛盾 {t0:.3f} cx {cx:.1f}")
    fj = seq(ph, "不順")                          # 辅1: 碎片, 从「不順」上方崩开
    if fj:
        a_, b_ = span(fj)
        for j in range(6):
            t = fj[0]["s"] + j * 0.07; x = R.uniform(a_, b_)
            f.shape(5, t, t + 1.1, x, 846, x + R.uniform(-30, 30), 826, S.shard(R, R.uniform(4, 6)), H30["base"],
                    c3=H30["glow"], bord=1, a_peak=30, blur=0.6, fade_in=0.05, fade_out=0.6, t_move=(0, 1000),
                    extra=f"\\frz{R.randint(0, 360)}\\t(\\frz{R.randint(-200, 200)})")
    mk = seq(ph, "見境")                          # 辅2: 一道电弧横过「見境」振假名上方
    if mk:
        a_, b_ = span(mk); t = mk[0]["s"]
        bo = S.bolt(R, 90, 3)
        for lay, col_, a, bl in ((4, H30["glow"], 140, 3), (5, "#FFFFFF", 30, 0.5)):
            f.shape(lay, t, t + 0.9, (a_ + b_) / 2, 838, draw=bo, c1=col_, c3=col_, bord=1.5 if lay == 4 else 0,
                    a_peak=a, blur=bl, fade_in=0.04, fade_out=0.5, extra="\\frz90" + flicker(4, 0.12, 0, 120))
    na = seq(ph, "ない")                          # 辅3: 小火苗, 在「ない」上方
    if na:
        a_, b_ = span(na); t = na[0]["s"]
        for lay, col_, a, bl, s in ((4, H30["base"], 110, 3, 16), (5, "#FFB36B", 40, 1, 10)):
            f.shape(lay, t, t_end, (a_ + b_) / 2, 862, draw=S.flame(s, 0.1), c1=col_, a_peak=a, blur=bl,
                    fade_in=0.3, fade_out=0.8, extra="\\t(0,400,\\fscy112)\\t(400,800,\\fscy96)\\t(800,1200,\\fscy108)")
    _unmark(f)


def _hat_polys(s):
    """洛琪希的尖帽 (平涂剪影): 帽身尖顶向右弯折 + 扁帽檐. 折线, 原点在帽身底中心, 宽约 s."""
    cone = [(-.30, .20), (-.20, .02), (-.10, -.16), (-.01, -.31), (.08, -.40), (.18, -.44), (.27, -.42), (.33, -.36),
            (.25, -.36), (.17, -.32), (.12, -.22), (.12, -.04), (.16, .10), (.26, .20)]
    brim = [(.5 * math.cos(2 * math.pi * i / 36), .20 + .10 * math.sin(2 * math.pi * i / 36)) for i in range(36)]
    f_ = lambda pts: "m " + " l ".join(f"{x * s:.2f} {y * s:.2f}" for x, y in pts) + " "
    return f_(cone), f_(brim)


def _star_poly(s, rot=-8):
    """五角星 (尖角略圆的效果靠描边 + blur), 外径 0.5s, 内径 0.23s."""
    pts = []
    for i in range(10):
        r = .5 if i % 2 == 0 else .23
        a = math.radians(rot - 90 + i * 36)
        pts.append((r * math.cos(a) * s, r * math.sin(a) * s))
    return "m " + " l ".join(f"{x:.2f} {y:.2f}" for x, y in pts) + " "


@main_motif("hat_star")
def p32(f, ph, k):
    print(f"[main] p32 t0 {ph.chars[0]['s']:.3f} t_end {k.t_end:.3f} t_out {k.t_out:.3f} band {tuple(round(v) for v in f.b[:4])}")
    _mark(f)
    an = seq(ph, "貴方")
    t_end = k.t_end + 0.6
    # 2026-11-12 r11: 主母题由心形改为 洛琪希尖帽 (「貴方」左上) + 金色五角星 (「だけ」右上). 参考 215.5/217.6 即此构图.
    # 理由: 全曲以洛琪希为线 (第 8 句蓝发辫, 授课阵), 末句「貴方だけ」的"你"是具体的人, 帽子比通用的心更收得住.
    # 原心形 (outline3 + _heart_poly 折线) 与「だ」四角星、「け」粉色花瓣 (即 だけ 右侧的红点) 一并撤下.
    if an:
        a_, b_ = span(an); t0 = an[0]["s"]
        t1 = min(t_end, k.t_out + 0.8)                 # 片尾标题 ~219s 进场, 不能活到那时
        hs = 68
        cone, brim = _hat_polys(hs)
        # 绘图按包围盒居中摆放: 帽身盒心 (0.015, -0.12)s, 帽檐盒心 (0, 0.20)s -> 帽檐中心要比帽身中心低 0.32s, 左 0.015s
        hx, hy = 798, 850
        bx, by = hx - 0.015 * hs, hy + 0.32 * hs
        for lay, dr, c1_, x_, y_ in ((3, brim, "#4657A8", bx, by), (4, cone, "#3C4C98", hx, hy)):
            f.shape(lay, t0, t1, x_, y_, draw=dr, c1=c1_, c3="#9FB8E6", bord=1.0, a3=120, a_peak=0, blur=0.6,
                    fade_in=0.9, fade_out=1.2)
        f.shape(2, t0, t1, bx, by, draw=brim, c1="#7E96E0", c3="#7E96E0", bord=5, blur=8, a_peak=200,
                fade_in=0.9, fade_out=1.2)                # 帽檐下一层淡蓝晕, 让深蓝帽在黑底上立住
        ts = t0 + 0.4
        ss = 46
        tail = seq(ph, "だけ")
        ra = span(tail)[1] if tail else b_
        sx, sy = ra + 34, 872
        st = _star_poly(ss)
        pul = ""
        for j in range(int((t1 - ts) / 1.6)):
            u = ms(j * 1.6)
            pul += f"\\t({u},{u + 800},0.7,\\fscx106\\fscy106)\\t({u + 800},{u + 1600},1.4,\\fscx100\\fscy100)"
        f.shape(3, ts, t1, sx, sy, draw=st, c1="#FFC94A", c3="#FFC94A", bord=5, blur=9, a_peak=110, fade_in=0.5,
                fade_out=1.2, extra=pul)
        f.shape(4, ts, t1, sx, sy, draw=st, c1="#FFE28A", c3="#FFF6D8", bord=1.2, blur=0.7, a_peak=0, fade_in=0.5,
                fade_out=1.2, extra=pul)
        print(f"[main] p32 hat ({hx},{hy}) star ({sx:.0f},{sy}) t0 {t0:.3f} star {ts:.3f} t1 {t1:.3f}")
    _unmark(f)
