# -*- coding: utf-8 -*-
"""FX 的专业手法三件套 (swoop / flutter / orbit). 从 fx.py 拆出, 让单文件不超 300 行 (铁律 4d).
全部经 self.shape() 发射, 所以 band 夹取与统一旋钮 (density/size/alpha) 照样生效."""
import math


class FXMotion:
    # ---------------------------------------------------------------- 专业手法三件套
    # 这三样是「专业 KFX 作品」（Aegisub 481 Examples）里每个形状的标配，
    # 而本库原先一个都没有  这就是"图形像贴纸、不像活的"的根因。

    def swoop(self, layer, t0, t1, path, draw, c1="#FFFFFF", a_peak=170, blur=1.6,
              be=2.0, bord=0, c3=None, spin=(0, 360), n_loop=0, loop_period=0.5,
              scale=(60, 100), fade_in=0.2, fade_out=0.4):
        """
        .agents/notes/implemented/feature/2026-11-09-karaoke-fx-gate-studio.md
沿【多段曲线】飞过 + 循环扇动（对应专业作品的 moves4 + loop）。

        path: [(x,y), ...] 至少 2 点；多段时逐段飞（ASS 的 \\move 只能走直线，多段靠切事件）。
        n_loop>0：叠加翻转，模拟扇翅/翻页的持续动感  专业羽毛特效靠它在 2.7s 内扇 20 次。
        be: \\be 边缘模糊，专业作品用它做柔光质感，本库原先完全没有。
        """
        R = self.rng
        pts = list(path)
        if len(pts) < 2:
            return
        # Agent Notes: 卡拉OK skill 通用化  去掉单次制作的事实与清单式铺陈
        # 
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
        专业羽毛/蝶翼类特效的核心  实测样品一条事件里链了 20 层 \\t。
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
