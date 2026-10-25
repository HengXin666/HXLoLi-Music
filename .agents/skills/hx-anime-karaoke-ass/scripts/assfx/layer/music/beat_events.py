# -*- coding: utf-8 -*-
"""音乐事件表: music_events.py 的产物 (review/music-events.json).

卡点层的参数全部由**伴奏**决定, 而伴奏每首不同, 所以生成器按 ME.level(t) 与 ME.strength
逐段决定密度, 而不是全曲一套常数.
"""
class MusicEvents:
    """music_events.py 的产物 (review/music-events.json).

    grid      十六分/八分网格点(秒)
    grid_fit  起音对网格的归一化误差中位; <0.30 = 贴合, 0.5 = 随机
    onset     谱通量起音(鼓点), strength 里带归一化强度
    sub       低频峰(重量感)
    section   段落边界(与 chordwiki 的转调点互验)
    """

    def __init__(self, d):
        self.d = d or {}
        self.grid = list(self.d.get("grid") or [])
        self.onset = list(self.d.get("onset") or [])
        self.sub = list(self.d.get("sub") or [])
        self.section = list(self.d.get("section") or [])
        self.bpm = self.d.get("bpm")
        self.step = self.d.get("grid_step") or (60.0 / self.bpm / (self.d.get("grid_div") or 4)
                                                if self.bpm else None)
        self.strength = self.d.get("strength") or {}
        self.grid_fit = self.d.get("grid_fit")

    @classmethod
    def load(cls, path):
        import json
        return cls(json.load(open(path, encoding="utf-8")))

    def grid_between(self, t0, t1):
        return [t for t in self.grid if t0 <= t < t1]

    def grid_at(self, t, tol=0.02):
        """离 t 最近且落在一个网格中的点, 供'只在卡点上发射'用"""
        if not self.step:
            return None
        best = None
        for g in self.grid_between(t - self.step, t + self.step):
            d = abs(g - t)
            if d <= tol * 4 and (best is None or d < abs(best - t)):
                best = g
        return best

    def onsets_between(self, t0, t1, min_strength=0.0):
        return [t for t in self.onset if t0 <= t < t1 and self.strength.get(str(t), self.strength.get(t, 1.0)) >= min_strength]

    def level(self, t):
        """该时刻的卡点等级 0~3: 由该窗内起音密度决定 (对应 impl/density.md 的 L0~L3)"""
        w = 2.0
        n = len([x for x in self.onset if t - w <= x <= t + w])
        if n >= 26:
            return 3
        if n >= 18:
            return 2
        if n >= 10:
            return 1
        return 0

    def levels(self):
        """整曲每秒一个等级, 便于按段落拉开差距"""
        if not self.onset:
            return {}
        out = {}
        t = 0.0
        end = max(self.onset) if self.onset else 0
        while t < end:
            out[round(t, 2)] = self.level(t)
            t += 1.0
        return out
