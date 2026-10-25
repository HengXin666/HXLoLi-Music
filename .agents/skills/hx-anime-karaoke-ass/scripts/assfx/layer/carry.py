# -*- coding: utf-8 -*-
"""
句间承接 (carry): 让相邻句共用一个视觉变量, 使整首读作连续体.

决策与实测依据: 

## 症状 (实测某工程 33 句, 2026-10-03)

| 量 | 实测 |
|---|---|
| fx 首事件 == 该句 band 起点(±0.05s) | **31/33** |
| fx 末事件 == 该句 band 终点 | **33/33** |
| 每句图形种类(按绘图路径 md5) | 中位 4, 最小 1 |
| fx 终点晚于下一句 band 起点 | 31.3% |

六条边里四条在动, 但整段读起来是 33 个独立片段  **每句的视觉变量生命周期被钉死在本句**.
那 31.3% 跨句事件只是 `Generator` 的退场淡出尾巴(α 在降, 颜色/位置/图形全不变),
**不携带任何变量**.

## 什么是可核对的"承接"

"有承接感"不可证伪, 等于没写. 能证伪的形式只有一种:

> **某个视觉变量在 A 句结束前就设定了, 且它决定 B 句的同一变量.**

`Carry` 就是那个对象: 生成器逐句把它传下去, 每句读它、再写它.

## 五种量 (都能在下一句被读到)

| 字段 | 含义 | 承接类型 |
|---|---|---|
| `color` | 末色 (hex) | 色温承接 |
| `x, y` | 末位置 (band 坐标) | 位置承接 |
| `dx, dy` | 剩余动量 (px/s) | 位置承接 |
| `shape` | 末图形名 | 意象承接 |
| `energy` | 0~1 强度 | 语法承接(收/放) |

**意象承接 ≠ 意象重复**: 同一元素**加高一级**是承接, 原样再用一遍是偷懒.
所以 `Carry.boost()` 存在的意义是"让同一个意象在下一句长一级", 而不是"再画一遍".
"""
import math
import re


class Carry:
    """逐句传递的视觉状态.

    用法(生成器里):

        carry = Carry()
        for P, ph in zip(PHRASES, phs):
            fx_fn(f, ph, k, carry)      # 读 carry 里的末位置/末色
            carry.update_from(f)        # 写回: 这一句最后落在哪
    """

    # Agent Notes: 句间承接  跨句状态对象与可核对的承接量
    # 
    def __init__(self, color="#FFFFFF", x=None, y=None, dx=0.0, dy=0.0,
                 shape=None, energy=0.5):
        """Agent Notes
        .agents/notes/implemented/feature/2026-10-03-karaoke-carry.md
        """
        self.color = color
        self.x, self.y = x, y
        self.dx, self.dy = float(dx), float(dy)
        self.shape = shape
        self.energy = float(energy)
        self.history = []          # [(句名, 快照)] 供写设计表时回查

    # ------------------------------------------------------------ 读
    def entry(self, f, pull=0.35):
        """下一句的**入场承接**: 用上一句留下的动量与位置决定从哪进来.

        `pull`: 动量回收比例. 1.0 = 完全沿用上一句的方向; 0 = 完全不动.
        返回 (x, y). 位置已经夹进 band.
        """
        b = f.b
        cx = (b[0] + b[2]) / 2 if self.x is None else self.x
        cy = (b[1] + b[3]) / 2 if self.y is None else self.y
        x = cx + self.dx * pull
        y = cy + self.dy * pull
        cl = lambda v, lo, hi: min(max(v, lo), hi)
        return cl(x, b[0] + 12, b[2] - 12), cl(y, b[1] + 12, b[3] - 12)

    def tint(self, base, k=0.30):
        """把上一句的末色混进本句的基色  色温承接.

        `k=0` 就是完全不管上一句(等于没有承接).
        """
        if not self.color or k <= 0:
            return base
        a = self.color.lstrip("#"); c = base.lstrip("#")
        ca = [int(a[i:i + 2], 16) for i in (0, 2, 4)]
        cc = [int(c[i:i + 2], 16) for i in (0, 2, 4)]
        mix = [round(x + (y - x) * k) for x, y in zip(ca, cc)]
        return "#" + "".join("%02X" % max(0, min(255, v)) for v in mix)

    def boost(self, level=1):
        """意象承接: 该元素在上一句的基础上升几级(尺寸/数量).

        返回建议的规模倍率. 未接过任何意象时返回 1.0(不要凭空放大).
        """
        if self.shape is None:
            return 1.0
        return 1.0 + 0.28 * level

    # ------------------------------------------------------------ 写
    def update(self, color=None, x=None, y=None, dx=None, dy=None,
               shape=None, energy=None):
        if color is not None:
            self.color = color
        if x is not None:
            self.x = x
        if y is not None:
            self.y = y
        if dx is not None:
            self.dx = dx
        if dy is not None:
            self.dy = dy
        if shape is not None:
            self.shape = shape
        if energy is not None:
            self.energy = float(energy)

    def snapshot(self, name=""):
        s = dict(name=name, color=self.color, x=self.x, y=self.y,
                 dx=self.dx, dy=self.dy, shape=self.shape, energy=self.energy)
        self.history.append(s)
        return s

    def from_events(self, f, name="", decay=0.7):
        """从**刚刚发射过的事件**反解末状态  不用手写 update.

        这是让承接"自动成立"的关键: 扫描 f.doc.events 里本句新增的那些,
        取最晚起步、位移最大的那条, 把它的终点与方向作为 carry.
        `decay`: 动量回收衰减(位移方向是这一句的, 下一句不必完全沿用).
        """
        tail = f.doc.events[f._mark:] if hasattr(f, "_mark") else []
        if not tail:
            return self.snapshot(name)
        best = None
        for ev in tail:
            lay, s, e, st, nm, txt = ev
            if not nm.startswith("fx:"):
                continue
            if best is None or e > best[2]:
                best = ev
        if best is None:
            return self.snapshot(name)
        lay, s, e, st, nm, txt = best
        m = re.search(r"\\move\(([-\d.]+),([-\d.]+),([-\d.]+),([-\d.]+)", txt)
        c = re.search(r"\\1c&H([0-9A-Fa-f]{6})&", txt)
        p = re.search(r"\\pos\(([-\d.]+),([-\d.]+)\)", txt)
        if m:
            x0, y0, x1, y1 = [float(g) for g in m.groups()]
            dt = max(0.05, e - s)
            self.update(x=x1, y=y1, dx=(x1 - x0) / dt * decay, dy=(y1 - y0) / dt * decay)
        elif p:
            self.update(x=float(p.group(1)), y=float(p.group(2)), dx=0.0, dy=0.0)
        if c:
            h = c.group(1)
            self.update(color="#%02X%02X%02X" % (int(h[4:6], 16), int(h[2:4], 16), int(h[0:2], 16)))
        return self.snapshot(name)
