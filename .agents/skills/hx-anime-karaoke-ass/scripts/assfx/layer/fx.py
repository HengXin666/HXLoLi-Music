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
from assfx.base.core import col, al, ms
from assfx.base.seeding import _derive as derive
from assfx.base.geom import event_extent
from assfx.draw import shapes as S
from assfx.layer.fx_motion import FXMotion


class FX(FXMotion):
    def __init__(self, doc, name, band, seed=0, knobs=None):
        self.doc = doc; self.name = name; self.b = band; self.rng = random.Random(seed)
        self.n_clamped = 0
        self.used = set()      # 本单元真正用到的统一旋钮 (清单写成 knobs_used, 面板只显示这些)
        self.set_knobs(knobs)

    def set_knobs(self, knobs=None):
        """统一旋钮 (预览台参数层): density 乘粒子数, size 乘图形尺寸, alpha 加到透明度上.
        默认值 (1, 1, 0) 时输出逐字节与没有旋钮时相同. 其余键是配方专属旋钮, 用 opt() 读."""
        self._ukey = getattr(knobs, "unit_key", None)    # G.segment / G.card_unit 给的旋钮带单元 key
        k = dict(knobs or {})
        self.density = float(k.pop("density", 1.0)); self.size = float(k.pop("size", 1.0))
        self.alpha = int(k.pop("alpha", 0)); self.opts = k
        return self

    def opt(self, key, default):
        """配方专属旋钮的当前值; 没覆盖时用配方里写的默认值."""
        return self.opts.get(key, default)

    def _use(self, *names):
        """记下旋钮被用到. 不改输出: 默认值时字节不变, 只影响清单的 knobs_used."""
        self.used.update(names)
        if self._ukey:
            from assfx.layer.manifest import REG
            REG.mark(self._ukey, names)

    def _n(self, n):
        self._use("density")         # 只有 burst / drift 走这里: 不发射粒子的配方, 密度旋钮无效
        return int(n) if self.density == 1.0 else max(0, int(round(n * self.density)))

    def reseed(self, *parts):
        self.rng = random.Random(derive(*parts))
        return self

    # ---------------------------------------------------------------- 核心：带夹取的绘图事件
    # Agent Notes: hx-anime-karaoke-ass 的 scripts/ 按职责分组，并把 5 个超 300 行的模块拆开
    # 
    def shape(self, layer, t0, t1, x0, y0, x1=None, y1=None, draw="", c1="#FFFFFF", a_peak=0, fade_in=0.2, fade_out=0.4,
              blur=1.0, extra="", c3=None, bord=0, t_move=None, accel=1.0, a3=None, fsc=100, alpha_t=None,
              solid=None, normalize=True, origin=None, an5=True):
        # solid=<px>：把**线稿**填充成实心块  用同色描边把笔画加粗到 solid 像素。
        # 为什么需要它：网络图标（MDI）是**线稿**，\p1 填充后只有一条细线（实测墨迹宽中位 5px），
        # 整帧看上去"什么都没画"。手绘实心块又不可辨认。
        # 这是既不手绘、又能得到实心形状的唯一办法：保留真实素材的轮廓，只把笔画加粗。
        """Agent Notes
        .agents/notes/implemented/process/2026-10-05-karaoke-scripts-grouping.md
        .agents/notes/implemented/process/2026-10-04-karaoke-skill-genericize.md
        """
        self._use("size", "alpha")   # 只有画图形 (shape) 时尺寸与透明度旋钮才生效
        if self.size != 1.0:
            fsc = fsc * self.size
        if self.alpha:
            a_peak = max(0, min(255, a_peak + self.alpha))
            if alpha_t:
                alpha_t = re.sub(r"\\alpha&H([0-9A-Fa-f]{2})&", lambda m: m.group(0) if m.group(1).upper() == "FF"
                                 else "\\alpha" + al(int(m.group(1), 16) + self.alpha), alpha_t)
        if solid:
            c3 = c1
            bord = max(bord, float(solid))
        x1 = x0 if x1 is None else x1; y1 = y0 if y1 is None else y1
        d = t1 - t0
        if d < 0.02:
            return
        # 定位规则：libass 对 \an5 绘图按 [0,w]x[0,h] 定位，所以传入的路径必须先平移到
        # 左上角  这就是 S.norm()。**不能省**：不归一化会整体偏 (xmin,ymin)
        # （实测 pos(623,1000) 的圆盘落到左上角 513,890）。
        #
        # 但有一类画法：**一组图形共用同一个 pos，彼此相对位置由各自路径坐标表达**
        # （实测某成品：兔耳 body 是 y=[-92,60]，圆盘 [-55,55]，那 37px 的纵向差就是构图）。
        # 各自独立归一化会抹掉这层关系  整体上移 46px 并侵入注音带。
        #
        # 解法：origin=(x, y) 指定一个**公共原点**，所有图形相对它整体归一化。
        # 同组图形传同一个 origin，相对关系就保住了，同时定位仍然正确。
        # an5=False 走 \an7(左上对齐)：pos 即绘图左上角，路径坐标**原样使用**，
        # 因此不需要归一化。对照用的成品就是这么写的（实测 \an7\pos(620,1000) + 路径 y=[-55,55]，
        # 实际落在 y=945~1055）。这条路上"图形间的相对位置"天然由路径坐标表达，不会被改。
        if not an5:
            pass
        elif origin is not None:
            draw = S.translate(S.norm(draw), origin[0], origin[1])
        elif normalize:
            draw = S.norm(draw)
        for it in range(6):
            bx0, by0, bx1, by1 = self.b[:4]
            # 分别计算端点处的半尺寸（不含位移）
            e0 = event_extent(self._text(d, 0, 0, 0, 0, draw, c1, a_peak, fade_in, fade_out, blur, extra, c3, bord, None, accel, a3, fsc, alpha_t, an=(5 if an5 else 7)))
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
                e1 = event_extent(self._text(d, x0, y0, x1, y1, draw, c1, a_peak, fade_in, fade_out, blur, extra, c3, bord, t_move, accel, a3, fsc, alpha_t, an=(5 if an5 else 7)))
                if e1[0] < bx0 - 1 or e1[1] < by0 - 1 or e1[2] > bx1 + 1 or e1[3] > by1 + 1:
                    fsc *= 0.85; self.n_clamped += 1
                    if it < 5:
                        continue
            break
        text = self._text(d, x0, y0, x1, y1, draw, c1, a_peak, fade_in, fade_out, blur, extra, c3, bord, t_move, accel, a3, fsc, alpha_t, an=(5 if an5 else 7))
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
    def _text(d, x0, y0, x1, y1, draw, c1, a_peak, fade_in, fade_out, blur, extra, c3, bord, t_move, accel, a3, fsc, alpha_t, an=5):
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
        return (f"{{\\an{an}{pos}\\bord{bord}\\shad0\\blur{blur:.2f}\\1c{col(c1)}"
                + (f"\\3c{col(c3)}" if c3 else "") + (f"\\3a{al(a3)}" if a3 is not None else "")
                + f"{at}{ex}\\p1}}{draw}{{\\p0}}")

    # ---------------------------------------------------------------- 常用发射器
    def burst(self, t, x, y, n, colors, draw_fn=None, speed=(30, 90), life=(0.6, 1.2), size=(2.5, 5.5), up=0.4,
              layer=8, blur=(0.8, 2.0), a=(0, 60), spin=False, glow=None):
        """从 (x,y) 向四周迸出（位移受 band 夹取）"""
        R = self.rng
        n = self._n(n)
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
        n = self._n(n)
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
