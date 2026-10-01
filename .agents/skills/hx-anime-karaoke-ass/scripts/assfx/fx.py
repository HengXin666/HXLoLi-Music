# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "fonttools",
# ]
# ///

"""
受 band 约束的特效发射器。所有绘图/光效都经过 FX.shape()，它会：
  1) 用 geom.event_extent 计算事件包围盒（含缩放/旋转/边框/模糊）
  2) 若越出 band，先把 \\move 两端点向内平移；仍放不下就整体缩小
  3) 事件 Name 写成 fx:<band>，供 validate_ass.py 复核
这样“特效只出现在字幕附近 5% 区域”是生成期保证 + 校验期复核的双保险。
"""
import math, random, re
from .core import col, al, ms
from .geom import event_extent
from . import shapes as S


class FX:
    def __init__(self, doc, name, band, seed=0):
        self.doc = doc; self.name = name; self.b = band; self.rng = random.Random(seed)
        self.n_clamped = 0

    # ---------------------------------------------------------------- 核心：带夹取的绘图事件
    def shape(self, layer, t0, t1, x0, y0, x1=None, y1=None, draw="", c1="#FFFFFF", a_peak=0, fade_in=0.2, fade_out=0.4,
              blur=1.0, extra="", c3=None, bord=0, t_move=None, accel=1.0, a3=None, fsc=100, alpha_t=None,
              solid=None):
        # solid=<px>：把**线稿**填充成实心块 —— 用同色描边把笔画加粗到 solid 像素。
        # 为什么需要它：网络图标（MDI）是**线稿**，\p1 填充后只有一条细线（实测墨迹宽中位 5px），
        # 整帧看上去"什么都没画"。手绘实心块又不可辨认。
        # 这是既不手绘、又能得到实心形状的唯一办法：保留真实素材的轮廓，只把笔画加粗。
        if solid:
            c3 = c1
            bord = max(bord, float(solid))
        x1 = x0 if x1 is None else x1; y1 = y0 if y1 is None else y1
        d = t1 - t0
        if d < 0.02:
            return
        draw = S.norm(draw)
        for it in range(6):
            bx0, by0, bx1, by1 = self.b[:4]
            # 分别计算端点处的半尺寸（不含位移）
            e0 = event_extent(self._text(d, 0, 0, 0, 0, draw, c1, a_peak, fade_in, fade_out, blur, extra, c3, bord, None, accel, a3, fsc, alpha_t))
            hw = (e0[2] - e0[0]) / 2; hh = (e0[3] - e0[1]) / 2
            ocx = (e0[0] + e0[2]) / 2; ocy = (e0[1] + e0[3]) / 2      # 包围盒中心相对 pos 的偏移（旋转原点不在中心时）
            if (hw * 2 > bx1 - bx0 - 2 or hh * 2 > by1 - by0 - 2) and it < 5:
                k = min((bx1 - bx0 - 4) / (hw * 2), (by1 - by0 - 4) / (hh * 2), 0.97)
                fsc = fsc * k; self.n_clamped += 1
                continue
            cl = lambda v, lo, hi: min(max(v, lo), hi) if lo <= hi else (lo + hi) / 2
            nx0 = cl(x0, bx0 + hw - ocx + 1, bx1 - hw - ocx - 1); ny0 = cl(y0, by0 + hh - ocy + 1, by1 - hh - ocy - 1)
            nx1 = cl(x1, bx0 + hw - ocx + 1, bx1 - hw - ocx - 1); ny1 = cl(y1, by0 + hh - ocy + 1, by1 - hh - ocy - 1)
            if (nx0, ny0, nx1, ny1) != (x0, y0, x1, y1):
                self.n_clamped += 1
                # \org 跟着平移，否则旋转半径会被放大
                dx_, dy_ = nx0 - x0, ny0 - y0
                extra = re.sub(r"\\org\(\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*\)",
                               lambda m: f"\\org({float(m.group(1))+dx_:.1f},{float(m.group(2))+dy_:.1f})", extra)
            x0, y0, x1, y1 = nx0, ny0, nx1, ny1
            if "\\org" in extra:
                e1 = event_extent(self._text(d, x0, y0, x1, y1, draw, c1, a_peak, fade_in, fade_out, blur, extra, c3, bord, t_move, accel, a3, fsc, alpha_t))
                if e1[0] < bx0 - 1 or e1[1] < by0 - 1 or e1[2] > bx1 + 1 or e1[3] > by1 + 1:
                    fsc *= 0.85; self.n_clamped += 1
                    if it < 5:
                        continue
            break
        text = self._text(d, x0, y0, x1, y1, draw, c1, a_peak, fade_in, fade_out, blur, extra, c3, bord, t_move, accel, a3, fsc, alpha_t)
        self.doc.ev(layer, t0, t1, text, "FX", "fx:" + self.name)

    def text(self, layer, t0, t1, x0, y0, txt, st, fs, tags, x1=None, y1=None, t_move=None):
        """文字型特效（鬼影/RGB 分离/飘字）；tags 不含定位，自动夹进 band"""
        x1 = x0 if x1 is None else x1; y1 = y0 if y1 is None else y1
        e = event_extent(f"{{\\an5\\pos(0,0){tags}}}{txt}", fs)
        hw = (e[2] - e[0]) / 2; hh = (e[3] - e[1]) / 2; cxo = (e[0] + e[2]) / 2; cyo = (e[1] + e[3]) / 2
        bx0, by0, bx1, by1 = self.b[:4]
        cl = lambda v, lo, hi: min(max(v, lo), hi) if lo <= hi else (lo + hi) / 2
        x0 = cl(x0, bx0 + hw - cxo + 1, bx1 - hw - cxo - 1); x1 = cl(x1, bx0 + hw - cxo + 1, bx1 - hw - cxo - 1)
        y0 = cl(y0, by0 + hh - cyo + 1, by1 - hh - cyo - 1); y1 = cl(y1, by0 + hh - cyo + 1, by1 - hh - cyo - 1)
        pos = f"\\pos({x0:.1f},{y0:.1f})" if (x0, y0) == (x1, y1) else \
            f"\\move({x0:.1f},{y0:.1f},{x1:.1f},{y1:.1f}" + (f",{t_move[0]},{t_move[1]})" if t_move else ")")
        self.doc.ev(layer, t0, t1, f"{{\\an5{pos}{tags}}}{txt}", st, "fx:" + self.name)

    @staticmethod
    def _text(d, x0, y0, x1, y1, draw, c1, a_peak, fade_in, fade_out, blur, extra, c3, bord, t_move, accel, a3, fsc, alpha_t):
        if (x0, y0) == (x1, y1):
            pos = f"\\pos({x0:.1f},{y0:.1f})"
        else:
            pos = f"\\move({x0:.1f},{y0:.1f},{x1:.1f},{y1:.1f}" + (f",{t_move[0]},{t_move[1]})" if t_move else ")")
        fi, fo = ms(min(fade_in, d / 2)), ms(min(fade_out, d / 2))
        ex = extra
        if abs(fsc - 100) > 0.01:
            # 统一缩放：把 extra 里所有 \fscx/\fscy 数值乘以 fsc/100，并给初值
            k = fsc / 100
            ex = re.sub(r"\\fsc([xy])(-?\d+(?:\.\d+)?)", lambda m: f"\\fsc{m.group(1)}{float(m.group(2))*k:.1f}", ex)
            if "\\fscx" not in extra.split("\\t(")[0]:
                ex = f"\\fscx{fsc:.1f}\\fscy{fsc:.1f}" + ex
        at = alpha_t if alpha_t is not None else (f"\\alpha&HFF&\\t(0,{fi},\\alpha{al(a_peak)})\\t({ms(d)-fo},{ms(d)},{accel},\\alpha&HFF&)")
        return (f"{{\\an5{pos}\\bord{bord}\\shad0\\blur{blur:.2f}\\1c{col(c1)}"
                + (f"\\3c{col(c3)}" if c3 else "") + (f"\\3a{al(a3)}" if a3 is not None else "")
                + f"{at}{ex}\\p1}}{draw}{{\\p0}}")

    # ---------------------------------------------------------------- 常用发射器
    def burst(self, t, x, y, n, colors, draw_fn=None, speed=(30, 90), life=(0.6, 1.2), size=(2.5, 5.5), up=0.4,
              layer=8, blur=(0.8, 2.0), a=(0, 60), spin=False, glow=None):
        """从 (x,y) 向四周迸出（位移受 band 夹取）"""
        R = self.rng
        n = int(n)
        for _ in range(n):
            ang = R.uniform(0, 2 * math.pi); v = R.uniform(*speed); L = R.uniform(*life)
            dx, dy = math.cos(ang) * v, math.sin(ang) * v * 0.6 - v * up
            sz = R.uniform(*size)
            ex = f"\\frz{R.randint(0,360)}\\t(\\frz{R.randint(-360,360)})" if spin else ""
            self.shape(layer, t, t + L, x, y, x + dx, y + dy, draw_fn(sz) if draw_fn else S.circle(sz), R.choice(colors),
                       a_peak=R.randint(*a), fade_in=0.06, fade_out=L * 0.7, blur=R.uniform(*blur), extra=ex, accel=0.8,
                       c3=glow, bord=1.5 if glow else 0)

    def drift(self, t0, t1, n, colors, draw_fn, vx=(-20, 20), vy=(-40, -10), life=(1.5, 3.0), size=(4, 9), layer=0,
              blur=(0.8, 2.0), a=(40, 120), spin=True, y_range=None, x_range=None, extra_fn=None, glow=None):
        """在 band 内持续飘动的元素（花瓣/雪/余烬/尘）"""
        n = int(n)
        R = self.rng; bx0, by0, bx1, by1 = self.b[:4]
        yr = y_range or (by0 + 10, by1 - 10); xr = x_range or (bx0 + 10, bx1 - 10)
        for _ in range(n):
            L = R.uniform(*life); ts = R.uniform(t0 - L * 0.3, t1 - L * 0.4)
            ts = max(ts, t0); te = min(ts + L, t1 + 0.3)
            if te - ts < 0.4:
                continue
            x = R.uniform(*xr); y = R.uniform(*yr)
            dx = R.uniform(*vx) * (te - ts); dy = R.uniform(*vy) * (te - ts)
            ex = (f"\\frz{R.randint(0,360)}\\t(\\frz{R.randint(-300,300)})" if spin else "") + (extra_fn(R) if extra_fn else "")
            self.shape(layer, ts, te, x, y, x + dx, y + dy, draw_fn(R.uniform(*size)), R.choice(colors),
                       a_peak=R.randint(*a), fade_in=min(0.5, L * 0.3), fade_out=min(0.8, L * 0.4), blur=R.uniform(*blur),
                       extra=ex, c3=glow, bord=1.5 if glow else 0)

    def pulse(self, layer, t, x, y, draw, c1, dur=0.6, s0=60, s1=140, a0=40, blur=2.0, extra="", c3=None, bord=0):
        """原地放大并淡出（冲击环/光晕）"""
        self.shape(layer, t, t + dur, x, y, draw=draw, c1=c1, blur=blur, c3=c3, bord=bord,
                   alpha_t=f"\\alpha{al(a0)}\\t(0,{ms(dur)},0.8,\\alpha&HFF&)",
                   extra=f"\\fscx{s0}\\fscy{s0}\\t(0,{ms(dur)},0.6,\\fscx{s1}\\fscy{s1}){extra}")

    def floor_spin(self, layer, t0, t1, x, y, draw, c1, deg_per_s=20, squash=0.26, fps=10, a_peak=100, fade_in=0.5, fade_out=0.5,
                   blur=1.0, grow=0.5, c3=None, bord=0, a3=None, angle0=0):
        """地面上旋转的魔法阵：逐帧预先旋转+压扁（不用 \\frx，避免透视畸变）；grow 秒内从 30% 放大到 100%"""
        n = max(1, int((t1 - t0) * fps))
        seg = (t1 - t0) / n

        def alpha(t):
            k = min(1.0, (t - t0) / fade_in if fade_in > 0 else 1, (t1 - t) / fade_out if fade_out > 0 else 1)
            return 255 - (255 - a_peak) * max(0.0, k)

        def sc(t):
            if grow <= 0 or t - t0 >= grow:
                return 100
            u = (t - t0) / grow
            return 30 + 70 * (1 - (1 - u) ** 2)
        for i in range(n):
            ta = t0 + i * seg; tb = ta + seg
            dr = S.flat(draw, angle0 + deg_per_s * (ta - t0), squash)
            s0, s1 = sc(ta), sc(tb)
            self.shape(layer, ta, tb, x, y, draw=dr, c1=c1, blur=blur, c3=c3, bord=bord, a3=a3,
                       alpha_t=f"\\alpha{al(alpha(ta))}\\t(0,{ms(seg)},\\alpha{al(alpha(tb))})",
                       extra=f"\\fscx{s0:.0f}\\fscy{s0:.0f}\\t(0,{ms(seg)},\\fscx{s1:.0f}\\fscy{s1:.0f})" if s0 != 100 or s1 != 100 else "")

    def glow(self, layer, t0, t1, x, y, rx, ry, c1, a_peak=150, blur=18, fade_in=0.3, fade_out=0.5, extra=""):
        self.shape(layer, t0, t1, x, y, draw=S.ellipse(rx, ry), c1=c1, a_peak=a_peak, blur=blur, fade_in=fade_in,
                   fade_out=fade_out, extra=extra)

    # ---------------------------------------------------------------- 专业手法三件套
    # 这三样是「专业 KFX 作品」（Aegisub 481 Examples）里每个形状的标配，
    # 而本库原先一个都没有 —— 这就是"图形像贴纸、不像活的"的根因。

    def swoop(self, layer, t0, t1, path, draw, c1="#FFFFFF", a_peak=170, blur=1.6,
              be=2.0, bord=0, c3=None, spin=(0, 360), n_loop=0, loop_period=0.5,
              scale=(60, 100), fade_in=0.2, fade_out=0.4):
        """沿【多段曲线】飞过 + 循环扇动（对应专业作品的 moves4 + loop）。

        path: [(x,y), ...] 至少 2 点；多段时逐段飞（ASS 的 \\move 只能走直线，多段靠切事件）。
        n_loop>0：叠加翻转，模拟扇翅/翻页的持续动感 —— 专业羽毛特效靠它在 2.7s 内扇 20 次。
        be: \\be 边缘模糊，专业作品用它做柔光质感，本库原先完全没有。
        """
        R = self.rng
        pts = list(path)
        if len(pts) < 2:
            return
        times = [t0 + (t1 - t0) * i / (len(pts) - 1) for i in range(len(pts))]
        for i in range(len(pts) - 1):
            (x0, y0), (x1, y1) = pts[i], pts[i + 1]
            ta, tb = times[i], times[i + 1]
            if tb - ta < 0.03:
                continue
            ex = ("\\be%.1f" % be) if be else ""
            if n_loop > 0:
                half = max(0.10, loop_period / 2)
                k = max(1, int((tb - ta) / half))
                for j in range(k):
                    a_ = int(j * half * 1000); b_ = int((j + 1) * half * 1000)
                    tag = "frx" if j % 2 == 0 else "fry"
                    ex += "\\t(%d,%d,\\%s%d)" % (a_, b_, tag, spin[1] if j % 2 == 0 else spin[0])
            if i == 0 and fade_in > 0:
                ex += "\\t(0,%d,\\\\be0)" % int(fade_in * 1000)
            self.shape(layer, ta, tb, x0, y0, x1, y1, draw=draw, c1=c1, a_peak=a_peak,
                       blur=blur, extra=ex, c3=c3, bord=bord,
                       fade_in=fade_in if i == 0 else 0.05,
                       fade_out=fade_out if i == len(pts) - 2 else 0.05,
                       fsc=R.uniform(*scale))

    def flutter(self, layer, t0, t1, x, y, draw, c1="#FFFFFF", a_peak=180, blur=1.4,
                period=0.26, amp=78, be=2.4, bord=0, c3=None, drift=(0, 0)):
        """原地持续扇动/翻飞（\\frx 与 \\fry 交替，周期 period 秒）。

        这是"贯穿整句"的来源：形状本身不位移，靠持续翻转产生生命感。
        专业羽毛/蝶翼类特效的核心 —— 实测样品一条事件里链了 20 层 \\t。
        """
        d = t1 - t0
        if d < 0.05:
            return
        k = max(2, int(d / max(0.05, period / 2)))
        half = d / k
        ex = ("\\be%.1f" % be) if be else ""
        for j in range(k):
            a_ = int(j * half * 1000); b_ = int((j + 1) * half * 1000)
            tag = "fry" if j % 2 == 0 else "frx"
            val = amp if j % 2 == 0 else -amp
            ex += "\\t(%d,%d,\\%s%d)" % (a_, b_, tag, val)
        if d > 0.6:
            ex += "\\t(0,%d,\\\\be0)" % int(min(0.3, d * 0.3) * 1000)
        dx, dy = drift
        self.shape(layer, t0, t1, x, y, x + dx, y + dy, draw=draw, c1=c1, a_peak=a_peak,
                   blur=blur, extra=ex, c3=c3, bord=bord, fade_in=0.15, fade_out=0.3)

    def orbit(self, layer, t0, t1, cx, cy, r0, r1, draw, c1="#FFFFFF", a_peak=170,
              turns=1.0, n=14, blur=1.4, be=2.0, bord=0, c3=None, arc0=0.0, arc1=360.0):
        """绕中心旋转的轨迹（用 n 段近似圆/弧），用于魔法阵环、光环、粒子绕行。

        比 floor_spin 更通用：可绕任意中心、任意椭圆半径、只走一段弧。
        """
        if n < 2:
            return
        for i in range(n):
            u0, u1 = i / n, (i + 1) / n
            a0 = math.radians(arc0 + (arc1 - arc0) * u0 + 360.0 * turns * u0)
            a1 = math.radians(arc0 + (arc1 - arc0) * u1 + 360.0 * turns * u1)
            rr = r0 + (r1 - r0) * u0
            ta = t0 + (t1 - t0) * u0
            tb = t0 + (t1 - t0) * u1
            if tb - ta < 0.02:
                continue
            self.shape(layer, ta, tb, cx + math.cos(a0) * rr, cy + math.sin(a0) * rr,
                       cx + math.cos(a1) * rr, cy + math.sin(a1) * rr,
                       draw=draw, c1=c1, a_peak=a_peak, blur=blur,
                       extra=(("\\be%.1f" % be) if be else ""), c3=c3, bord=bord,
                       fade_in=0.05, fade_out=0.05)
