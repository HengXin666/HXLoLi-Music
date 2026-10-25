# -*- coding: utf-8 -*-
"""
配色叙事: 段落色系 + 句内多色.

决策与实测依据: 

## 为什么需要它 (2026-10-02)

`anim.py::Karaoke.colors()` 现在是:

    def colors(self, c):                     # c = 一个字
        if self.o["hl_color"]:
            r = self.o["hl_color"](c)
            if r: return r
        return self["hi"], self["glow"]      # ← 一句里所有字都是同一个颜色

所以**同一句里颜色永远一致**, 齐唱/和声/主唱全都一个色, 前后半句也不分.

## 专业成品是怎么做的 (实测)

| 成品 | 做法 | 实测证据 |
|---|---|---|
| 成品 A (OP) | **描边四色轮换, 每段一色** | `\\3c` 只有 4 种, 全曲不变, 填充恒为纯白 |
| 成品 B | 全曲一套色域 | 6 种有色标签, 色相集中度 R=0.99 |
| 成品 C | **全曲在同一色域里逐字游走** | 28257 条字形事件里 97% 带 `\\t(...\\1c...)` **终色**, 61 种终色, 按字分配 |
| 成品 D | 4 个角色色 + 主题色, 逐字取 | 11 种颜色, 4 个样式前缀各挂一套 |

两条被实测钉死的规律:

1. **配色有"段落"这一层**: 成品 A 换的是"哪一段", 不是"哪一句". 逐句换色会让全曲失去统一性.
2. **句内多种颜色有两类来源**: (a) **谁在唱**(声部/角色), (b) **时间上的游走**(一个色域里缓慢移动).
   两者可以叠加.

本模块就提供这两件事, 并给出与 `Karaoke` 对接的回调工厂.

## 实测教训: 色相跨度要落在 20~120 度 (2026-10-03)

第一版接上逐字游走后, 量出来是**分布极不均匀**:

| 量 | v4(未接) | v5(第一版) |
|---|---|---|
| 每句色相跨度 中位 | 0° | 26° |
| 跨度 >180° 的句数 | 0/28 | **5/32**(最大 253°) |
| 跨度 <=3° 的句数 | 28/28 | 25/32 |

- 中位 26° 说明方向对(是色域内游走, 不是彩虹);
- 但 **5/32 句跨了半个色环**(过了), 而 **25/32 句只有 2~3°**(等于只有明度差, 色相没动)。
- 那些"13~21 个唯一色相"是**连续取值的锯齿**, 不是设计出来的色档。

**判据: 每句色相跨度落在 20°~120°, 且 >=90% 的句落在区间内.**
量法: 取该句所有 `ly:` 高亮层(Layer>=23) 的 `\1c`, 转 HSV 保留 sat>0.25 的,
看色相的**环形跨度**(补上首尾环绕间隔, 否则会算出 359° 的假值).

## 与 KPI 的关系

`doc/KFX-RULES.md` 规定填充恒白、色彩表达交给描边. 本模块只产出**描边色对** `(hi, glow)`,
填充与可读性由既有规则负责  配色变多不许把对比度吃回去 (`py/music/kfx_gate.py` 会量).
"""
import math

from assfx.base.core import col  # noqa: F401  (导出给调用方用)


# ------------------------------------------------------------------ 色相工具
# Agent Notes: 句内配色  声部归属检测 + 段落色系
# 
def hex_to_rgb(h):
    """Agent Notes
    .agents/notes/implemented/feature/2026-10-03-karaoke-voice-color.md
    """
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(c):
    return "#" + "".join("%02X" % max(0, min(255, int(round(v)))) for v in c)


def hue_rotate(h, deg):
    """色相旋转(保持 HSV 的 S/V): 用于从主色派生第二个声部的颜色.

    为什么不用"另挑一个好看的颜色": 派生出来的色与主色**同明度同饱和**,
    在动效场景下不会一个跳一个闷, 观感是"同一套配色里的另一个位置".
    """
    import colorsys
    r, g, b = [v / 255.0 for v in hex_to_rgb(h)]
    hh, ss, vv = colorsys.rgb_to_hsv(r, g, b)
    hh = (hh + deg / 360.0) % 1.0
    r, g, b = colorsys.hsv_to_rgb(hh, ss, vv)
    return rgb_to_hex((r * 255, g * 255, b * 255))


def mix(a, b, k):
    """线性混色 k∈[0,1]"""
    ca, cb = hex_to_rgb(a), hex_to_rgb(b)
    return rgb_to_hex(tuple(x + (y - x) * k for x, y in zip(ca, cb)))


def lighten(h, k):
    return mix(h, "#FFFFFF", k)


def darken(h, k):
    return mix(h, "#000000", k)


# ------------------------------------------------------------------ 段落色系
class Scheme:
    """一个段落(主歌/副歌/间奏)的配色.

    stops: 色域里的锚点, 按时间顺序. 逐字取色就在这条折线上游走 
           这是"全天候一个色域"与"每句换色"之间那条被专业成品实测过的中间路线.
    hi/glow: 高亮描边与辉光. 不给就从 stops 的首尾派生.
    level: 0~3 的情绪等级(与 impl/density.md 的 L0~L3 同源), 决定游走的**速度**与**振幅**.
    """

    def __init__(self, name, stops, hi=None, glow=None, level=1, roles=None):
        self.name, self.stops, self.level = name, list(stops), level
        self.hi = hi or stops[-1]
        self.glow = glow or lighten(stops[-1], 0.35)
        self.roles = roles or {}          # 声部 -> 色相偏移角度; 例 {"uni": 26, "duo": 208}

    def at(self, k):
        """k∈[0,1] 在这段色域里取色(按 stops 折线)"""
        k = max(0.0, min(1.0, k))
        if len(self.stops) == 1:
            return self.stops[0]
        pos = k * (len(self.stops) - 1)
        i = min(int(pos), len(self.stops) - 2)
        return mix(self.stops[i], self.stops[i + 1], pos - i)

    def role_color(self, role, base):
        """把一个基础色按声部派生出该声部的色(roles 里没写就原样返回)"""
        deg = self.roles.get(role)
        return hue_rotate(base, deg) if deg else base


class Palette:
    """全曲配色: 段落列表 + 查询.

    segments: [(t0, t1, Scheme), ...]  顺序给, 允许有空隙(空隙里的句子走 default).

    ⚠ 段边界**不许凭"听着像副歌"**: 与 `impl/density.md` 同源, 用 chordwiki 的转调点.
    """

    def __init__(self, segments, default=None):
        self.segs = sorted(segments, key=lambda x: x[0])
        self.default = default or Scheme("default", ["#DCE8F4", "#FFFFFF"], level=1)

    def at(self, t):
        """返回该时刻的 (Scheme, 段内进度 k)"""
        for t0, t1, sc in self.segs:
            if t0 <= t < t1:
                return sc, (t - t0) / max(1e-6, t1 - t0)
        return self.default, 0.0

    def char_color(self, t, k):
        """逐字取色: t = 该字的起始秒, k = 该字在句内的进度(0..1)"""
        sc, _ = self.at(t)
        return sc, sc.at(k)

    def voice_colors(self, t, voice, base):
        sc, _ = self.at(t)
        return sc.role_color(voice, base)


# ------------------------------------------------------------------ 与 Karaoke 对接
def make_hl_color(ph, palette, voices=None, t_in=None, t_end=None, use_voice=True, use_ramp=True):
    """造一个 `hl_color(ch) -> (hi, glow)` 回调, 直接塞进 `Karaoke` 的选项.

    ph        该句的 Phrase (layout.py)
    palette   Palette
    voices    voices.py 的输出 dict: {"line.unit.mora": "solo|uni|duo|none"}
    use_voice 声部是否参与配色
    use_ramp  句内游走是否参与(关掉就回到"一句一色")
    """
    xs = [c["x"] for c in ph.chars] or [0.0]
    x0, x1 = min(xs), max(xs)

    def hl(ch):
        t = ch["s"]
        sc, _ = palette.at(t)
        # `use_ramp=False`(句内一色) 时取**色域中段**, 不是 `sc.hi`。
        # 为什么: `sc.hi` 是 stops 的**最浅**那个(明度最高、色相最偏), 用它当整句唯一颜色
        # 会让全曲的"主题色"都退化成一片浅色  实测段间色相差被压到 16°(设计上是 22~122°),
        # 也就是**色彩叙事被取色口径吃掉了**。取中段才是这个色域的代表色。
        base = sc.at((ch["x"] - x0) / max(1e-6, x1 - x0)) if use_ramp else sc.at(0.5)
        role = "solo"
        if use_voice and voices is not None:
            # voices.json 的 key 是 "<line>.<unit>.<mora>"; 一个字符可能跨多个音拍,
            # 所以按该字的音拍列表逐个查, 取第一个命中的. **不能写死 mora=0** 
            # 实测写死 mora=0 时命中率极低, 声部色等于没生效(全部退回 solo).
            line = ch.get("line"); unit = ch.get("unit")
            morae = ch.get("morae") or []
            cand = ["%d.%d.%d" % (line, unit, m.get("mora", i)) for i, m in enumerate(morae)]
            for k in cand:
                if k in voices:
                    role = voices[k]
                    break
            else:
                role = voices.get("%d.%d.0" % (line, unit), "solo")
        c = sc.role_color(role, base)
        return c, lighten(c, 0.35)

    return hl


# ------------------------------------------------------------------ 句内时间折返
def fold(ph, t_break, k_before=0.0, k_after=1.0):
    """句内情绪折返点: t_break 之前用 k_before 那一档的色, 之后用 k_after.

    为什么需要: 用户的第二条意见是"前面和后面可能要颜色区分". 专业作品里这不是随机换色,
    而是挂在**句子的语义反转点**上  与 `impl/per-line.md` §3「把语法结构变成时间结构」同源:
    否定/转折词就是折返点, 颜色在那一刻换档, 观众读到"这里变意思了".
    """
    out = {}
    for c in ph.chars:
        out[c["i"]] = k_after if c["s"] >= t_break else k_before
    return out


def find_break(ph, words):
    """在句里找一个折返时刻: 给定词表, 返回第一个命中的词的首字起始秒."""
    from assfx.layer.gen import seq
    for w in words:
        chs = seq(ph, w)
        if chs:
            return chs[0]["s"], w
    return None, None
