# -*- coding: utf-8 -*-
"""
背景层: 由**镜头 / 情感 / 番剧符号**三者驱动的一层.

决策与实测依据: .agents/notes/implemented/feature/2026-10-03-karaoke-bg-from-scene.md

## 与卡点层的分工 (别合成一层)

| | 背景层 | 卡点层 (beat.py) |
|---|---|---|
| 曲线 | **平坦**(宽、低) | **脉冲**(窄峰、高) |
| 时钟 | 镜头切换 | 音乐事件网格 |
| 意图 | 空气 / 质感 | 情绪强度 |

合成一层会让"空气"和"脉搏"互相吃掉 —— 这是两组必须分开的数学理由.

## band 铁律

背景层**只能**在 band 内. 实测专业参考(东方「轨迹さえ」42872 事件)也全部落在
y 856~972 的 116px 横带里. "背景贯通全曲"的正确形式是:
  1) 图形与配色全曲统一;  2) 覆盖率铺到句间空隙;  3) 单条事件仍短(0.5~1s), 不靠长事件跨句.
实测参考覆盖率: Ptcl 逐秒 61%, Flow 78%; 跨句事件只有 1.2%.
"""
import json

from . import shapes as S


class SceneTimeline:
    """`scripts/scene_timeline.py` 的产物 (review/scene-timeline.json).

    at(t)     -> (hue 0~360, sat, val)  该秒画面主色(HSV)
    shot(t)   -> 该秒所属的镜头段 dict(t0,t1,hue,sat,val,rgb,is_dark)
    cuts(a,b) -> (a,b) 区间内的镜头切换时刻
    is_bright(t) -> 亮场判定(背景层必须压暗, 否则字看不清)
    """

    def __init__(self, d):
        self.d = d or {}
        self.shots = self.d.get("shots") or []
        self.per = {float(k): v for k, v in (self.d.get("per_sec") or {}).items()}
        self._keys = sorted(self.per)

    @classmethod
    def load(cls, path):
        return cls(json.load(open(path, encoding="utf-8")))

    def at(self, t):
        if not self._keys:
            return 210.0, 0.4, 0.35
        # 最近邻(逐秒采样, 不需要插值)
        import bisect
        i = bisect.bisect_left(self._keys, t)
        best = min((j for j in (i - 1, i, i + 1) if 0 <= j < len(self._keys)),
                   key=lambda j: abs(self._keys[j] - t))
        return tuple(self.per[self._keys[best]])

    def shot(self, t):
        for s in self.shots:
            if s["t0"] <= t < s["t1"]:
                return s
        return self.shots[-1] if self.shots else None

    def cuts(self, a, b):
        return [s["t0"] for s in self.shots if a < s["t0"] < b]

    def is_bright(self, t):
        s = self.shot(t)
        return bool(s and s.get("val", 0) > 0.62)


def hue_to_hex(h, s=0.55, v=0.95):
    """HSV -> #RRGGBB, 用于把画面色温变成背景色"""
    import colorsys
    r, g, b = colorsys.hsv_to_rgb((h % 360) / 360.0, max(0.0, min(1.0, s)),
                                  max(0.0, min(1.0, v)))
    return "#%02X%02X%02X" % (round(r * 255), round(g * 255), round(b * 255))


def bg_drift(f, st, t0, t1, family=None, n_per_sec=1.7, layer=0, size=(3.0, 6.5),
             a=(110, 175), blur=1.8, follow_hue=True):
    """背景层主体: 铺满 [t0,t1] 的低存在感颗粒.

    `follow_hue`: 是否让色温跟着该秒画面走(默认跟). 关掉就只用 `family` 给的固定色族.
    `n_per_sec`: 每秒颗粒数. 实测覆盖率要 >=55%, 这个值决定它 —— 1.7/秒 x 平均寿命 1.9s ≈ 3.2 颗常驻.
    """
    R = f.rng
    b = f.b
    fam_cols = None
    if family:
        from .beat import BEAT_COLORS
        fam_cols = BEAT_COLORS.get(family, family if isinstance(family, (list, tuple)) else None)
    n = 0
    t = t0
    step = 1.0 / max(0.1, n_per_sec)
    while t < t1:
        if follow_hue and st is not None:
            h, sat, val = st.at(t)
            col = hue_to_hex(h, min(0.62, max(0.28, sat)), 0.82 if val > 0.5 else 0.95)
        else:
            col = R.choice(fam_cols) if fam_cols else "#FFFFFF"
        life = R.uniform(1.4, 2.4)
        f.shape(layer, t, min(t + life, t1 + 0.3),
                R.uniform(b[0] + 16, b[2] - 16), b[3] - R.uniform(4, 36),
                R.uniform(b[0] + 16, b[2] - 16), b[1] + R.uniform(16, 72),
                draw=S.sparkle(R.uniform(*size)), c1=col,
                a_peak=R.randint(*a), blur=blur, fade_in=0.4, fade_out=0.6)
        t += step
        n += 1
    return n


def bg_frames(f, st, t0, t1, every=1.0, layer=0, alpha=60, blur=26, follow_hue=True):
    """镜头切换处的整片柔光.

    ⚠ **默认不该用.** 实测教训(2026-10-03, 用户指正「非常大」): 整片柔光的墨迹
    达 **1446px**(band 只有 242px 高), 在窄带里就是一层糊住字的雾, 且它不产生任何信息.
    背景层的职责是"空气", 由 `bg_drift` 的小颗粒承担就够; 换镜头可以靠色温变化读出,
    不需要再叠一层大椭圆. 保留此函数只为"确实需要一次整体呼吸"的场合(比如段落起爆).
    """
    if st is None:
        return 0
    b = f.b
    n = 0
    for t in st.cuts(t0, t1):
        h, sat, val = st.at(t)
        col = hue_to_hex(h, 0.5, 0.9)
        f.glow(layer, t, t + 0.55, (b[0] + b[2]) / 2, (b[1] + b[3]) / 2,
               (b[2] - b[0]) * 0.48, (b[3] - b[1]) * 0.5, col,
               a_peak=alpha, blur=blur, fade_in=0.06, fade_out=0.4)
        n += 1
    return n
