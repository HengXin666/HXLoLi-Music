# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.11"
# dependencies = ["svgelements"]
# ///
r"""精密图标素材库：把网络矢量图标落成**可辨认的实心路径**，而不是手绘拼贴。

为什么单独一个模块（对应 ../steps/4-kfx/42-text-main/impl/precise-shapes.md）：
  * 手绘的 circle+rect 拼不出可辨认的物体。实测同一物体两者差一个量级：
    手绘自行车 = 两个圆圈 + 几条线；网络 SVG 转出 = 3148 字符的真实车架/辐条路径。
  * shapes.py 提供的是**可参数化的几何语汇**（心/花/星/裂纹，尺寸与比例都能调）；
    本模块提供的是**现成的具象物件**（眼睛/剑/盾/花/雪…），拿来即用、不可参数化。

**这里只有通用物件，没有"某部作品的专属道具"。**
作品专属的符号（某番的怪物眼睛、某番的方尖碑）要按工程的元素表现取：
用 `svg2ass.from_url` 取一个贴合的通用图标，或在工程里画好路径存进
`proj/assets/`，不要加进本模块  加进来就等于把某一次制作的素材焊进 skill。

来源：MDI（Material Design Icons，Apache-2.0）与 Bootstrap Icons（MIT）的 CDN，
经 assfx.base.svg2ass 采样成 ASS 的 \p1 折线。缓存**不在 skill 目录**（`ASSFX_SVG_CACHE` 或
`~/.cache/hx-anime-karaoke-ass/svg`），可离线复现；见 svg2ass._ensure_cache 的理由说明。

用法：
    from assfx.asset import props as P
    f.shape(6, t0, t1, x, y, draw=P.eye(56), c1="#FF5A6E", bord=2)
    P.prefetch(["eye", "sword"])        # 首次联网预热；断网时已有缓存仍可用
"""
import os
import sys

_HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# 名字 -> CDN 上的图标名。全部实测 200 OK（见 .agents/notes/implemented/process/
# 2026-10-02-karaoke-kf-line-pairing.md 同一轮的探测记录）。
ICONS = {
    #  人物 / 能力
    "eye":          "https://cdn.jsdelivr.net/npm/@mdi/svg@7.4.47/svg/eye.svg",
    "eye_open":     "https://cdn.jsdelivr.net/npm/@mdi/svg@7.4.47/svg/eye-outline.svg",
    "crosshair":    "https://cdn.jsdelivr.net/npm/@mdi/svg@7.4.47/svg/crosshairs-gps.svg",
    "orbit":        "https://cdn.jsdelivr.net/npm/@mdi/svg@7.4.47/svg/orbit.svg",
    "atom":         "https://cdn.jsdelivr.net/npm/@mdi/svg@7.4.47/svg/atom.svg",
    "virus":        "https://cdn.jsdelivr.net/npm/@mdi/svg@7.4.47/svg/virus.svg",
    "dna":          "https://cdn.jsdelivr.net/npm/@mdi/svg@7.4.47/svg/dna.svg",
    #  猫 / 爪 / 帽
    "cat":          "https://cdn.jsdelivr.net/npm/@mdi/svg@7.4.47/svg/cat.svg",
    "paw":          "https://cdn.jsdelivr.net/npm/@mdi/svg@7.4.47/svg/paw.svg",
    "wizard_hat":   "https://cdn.jsdelivr.net/npm/@mdi/svg@7.4.47/svg/wizard-hat.svg",
    "rabbit":       "https://cdn.jsdelivr.net/npm/@mdi/svg@7.4.47/svg/rabbit.svg",
    #  武器 / 装备
    "sword":        "https://cdn.jsdelivr.net/npm/@mdi/svg@7.4.47/svg/sword.svg",
    "shield":       "https://cdn.jsdelivr.net/npm/@mdi/svg@7.4.47/svg/shield.svg",
    "bullet":       "https://cdn.jsdelivr.net/npm/@mdi/svg@7.4.47/svg/bullet.svg",
    "lightning":    "https://cdn.jsdelivr.net/npm/@mdi/svg@7.4.47/svg/lightning-bolt.svg",
    "hexagon":      "https://cdn.jsdelivr.net/npm/@mdi/svg@7.4.47/svg/hexagon-outline.svg",
    "diamond":      "https://cdn.jsdelivr.net/npm/@mdi/svg@7.4.47/svg/diamond-stone.svg",
    #  器物 / 自然：碑 / 火 / 水 / 月 / 冠
    "pillar":       "https://cdn.jsdelivr.net/npm/@mdi/svg@7.4.47/svg/pillar.svg",
    "fire":         "https://cdn.jsdelivr.net/npm/@mdi/svg@7.4.47/svg/fire.svg",
    "water":        "https://cdn.jsdelivr.net/npm/@mdi/svg@7.4.47/svg/water.svg",
    "sunset":       "https://cdn.jsdelivr.net/npm/@mdi/svg@7.4.47/svg/weather-sunset.svg",
    "moon":         "https://cdn.jsdelivr.net/npm/@mdi/svg@7.4.47/svg/moon-waning-crescent.svg",
    "crown":        "https://cdn.jsdelivr.net/npm/@mdi/svg@7.4.47/svg/crown.svg",
    "cross":        "https://cdn.jsdelivr.net/npm/@mdi/svg@7.4.47/svg/cross.svg",
    #  花 / 生命
    "flower":       "https://cdn.jsdelivr.net/npm/@mdi/svg@7.4.47/svg/flower.svg",
    "tulip":        "https://cdn.jsdelivr.net/npm/@mdi/svg@7.4.47/svg/flower-tulip.svg",
    "sprout":       "https://cdn.jsdelivr.net/npm/@mdi/svg@7.4.47/svg/sprout.svg",
    "seed":         "https://cdn.jsdelivr.net/npm/@mdi/svg@7.4.47/svg/seed-outline.svg",
    "butterfly":    "https://cdn.jsdelivr.net/npm/@mdi/svg@7.4.47/svg/butterfly.svg",
    "feather":      "https://cdn.jsdelivr.net/npm/@mdi/svg@7.4.47/svg/feather.svg",
    "bird":         "https://cdn.jsdelivr.net/npm/@mdi/svg@7.4.47/svg/bird.svg",
    "snowflake":    "https://cdn.jsdelivr.net/npm/@mdi/svg@7.4.47/svg/snowflake.svg",
    "head_snow":    "https://cdn.jsdelivr.net/npm/@mdi/svg@7.4.47/svg/head-snowflake.svg",
    #  光 / 破
    "heart_broken": "https://cdn.jsdelivr.net/npm/@mdi/svg@7.4.47/svg/heart-broken.svg",
    "star4":        "https://cdn.jsdelivr.net/npm/@mdi/svg@7.4.47/svg/star-four-points.svg",
    "shooting":     "https://cdn.jsdelivr.net/npm/@mdi/svg@7.4.47/svg/star-shooting.svg",
    "creation":     "https://cdn.jsdelivr.net/npm/@mdi/svg@7.4.47/svg/creation.svg",
    "blur_radial":  "https://cdn.jsdelivr.net/npm/@mdi/svg@7.4.47/svg/blur-radial.svg",
    "ring2":        "https://cdn.jsdelivr.net/npm/@mdi/svg@7.4.47/svg/circle-double.svg",
    "ring1":        "https://cdn.jsdelivr.net/npm/@mdi/svg@7.4.47/svg/circle-outline.svg",
    "cloud":        "https://cdn.jsdelivr.net/npm/@mdi/svg@7.4.47/svg/cloud.svg",
}

# 尺寸（ASS 单位）。**实测标定**：本 skill 的 band 只有 758×242，
# 单个图形 30~70px 是参考工程的量级；但"贵重感"要求 L3 句的主母题更大更精密，
# 这类图形的路径本身已很密，放大到 90~130px 反而更像"实物"而不是"贴纸"。
_CACHE = {}


# Agent Notes: 卡拉OK skill 通用化  去掉单次制作的事实与清单式铺陈; hx-anime-karaoke-ass 的 scripts/ 按职责分组，并把 5 个超 300 行的模块拆开
# 
# 
def _draw(name, size):
    """
    .agents/notes/implemented/process/2026-10-04-karaoke-skill-genericize.md
    .agents/notes/implemented/process/2026-10-05-karaoke-scripts-grouping.md
取（并按 size 缩放）某个图标的 ASS 绘图代码。同 (name,size) 只算一次。"""
    key = (name, int(size))
    if key in _CACHE:
        return _CACHE[key]
    from assfx.base.svg2ass import from_url
    url = ICONS[name]
    d = from_url(url, size=size)
    _CACHE[key] = d
    return d


def get(name):
    """返回一个可调用对象：P.get("eye")(56)  便于在 fx 函数里按尺寸现取。"""
    def f(size):
        return _draw(name, size)
    return f


# Agent Notes: 特效母题必须指向带来源计数的番剧元素表; 卡拉OK skill 按步骤重构成 steps/NN-<key>/ 的契约 + impl 结构
# 
# 
def prefetch(names=None):
    """
    .agents/notes/implemented/process/2026-10-02-karaoke-elements-table-gate.md
    .agents/notes/implemented/process/2026-10-02-karaoke-steps-restructure.md
预热缓存（首次联网用；之后离线可跑）。"""
    out = []
    for n in (names or ICONS):
        try:
            out.append((n, len(_draw(n, 48))))
        except Exception as e:                                   # 断网时明确报出来，不静默
            out.append((n, "FAIL %s" % str(e)[:50]))
    return out


#  常用组合：把"道具 + 它的动作"包成一个函数，避免每句重写一遍 ----
def eye(s):
    """眼睛：可开合的虹膜（放大小尺寸时读作"注视/觉醒"）"""
    return _draw("eye", s)


def monolith(s):
    """方尖碑 / 巨柱：竖长矩形体，适合"地标 / 权威 / 压迫感"母题"""
    return _draw("pillar", s)


def field_ring(s):
    """轨道环：中心点 + 环绕轨迹，适合"装置 / 浮游物 / 观测"母题"""
    return _draw("orbit", s)


def katana(s):
    """刀：单刃长刀剪影"""
    return _draw("sword", s)


def bara(s):
    """弹丸：适合"材质 / 弹药 / 金属"母题"""
    return _draw("bullet", s)


def cat_ear(s):
    """猫耳：兽耳剪影"""
    return _draw("cat", s)


def witch_hat(s):
    """魔女帽：尖顶帽 + 宽檐"""
    return _draw("wizard_hat", s)


def shield(s):
    """盾：适合"守护 / 防御"母题"""
    return _draw("shield", s)


def lotus(s):
    """莲 / 花：正面绽放的花形"""
    return _draw("flower", s)


def sprout(s):
    """芽：刚破土的新芽"""
    return _draw("sprout", s)


def feather(s):
    return _draw("feather", s)


def broken_heart(s):
    return _draw("heart_broken", s)


def snow(s):
    return _draw("snowflake", s)


def spark4(s):
    return _draw("star4", s)


def ring_double(s):
    return _draw("ring2", s)


def glow_radial(s):
    return _draw("blur_radial", s)


def fire(s):
    return _draw("fire", s)


def virus(s):
    """病毒：适合"侵蚀 / 感染 / 扩散"母题"""
    return _draw("virus", s)
