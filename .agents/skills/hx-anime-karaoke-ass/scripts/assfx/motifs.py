# -*- coding: utf-8 -*-
"""
意境层与逐词母题：把「一句 = 1 个意境背景 + 1 主母题 + ≤3 辅助母题」变成可复用的零件。

为什么单独一个模块（见 ../steps/4-kfx/42-text-main/impl/motif-catalog.md §2）：
  原先每句只有一个主母题，做出来的东西"每句都差不多、高潮不出来"——
  因为观众读不出层次。合格的做法是三种东西各司其职：

    意境背景（ambient）  铺满整句时长的氛围，**每句都必须有**。不带叙事，只给空气感。
    主母题（main）       该句情感核心，规模最大，挂在最重的词上。
    辅助母题（aux）      按词分组，2~3 个不同关键词各挂一个**不同**的小母题。

  本模块提供 `AMBIENT`（10 种意境）与 `MOTION`（12 种逐词动作）两张表，
  以及 `apply()` 一次把它们铺到一句上。加一种新意境 = 加一个函数 + 注册一行。

用法：
    from assfx.motifs import AMBIENT, MOTION, ambient, keyword_motifs
    ambient(f, ph, k, "dust_up", level=2)            # 意境背景
    keyword_motifs(f, ph, k, [("錆", "rust"), ("孤独", "fall_shard")])
"""


# ------------------------------------------------------------------ 意境背景
def _a_dust_up(f, ph, k, c, n, R):
    """微尘上浮：最通用，几乎任何情绪都成立"""
    from assfx import shapes as S
    f.drift(ph.s - 0.2, ph.e + 0.4, n, c, lambda r: S.sparkle(r * 1.1),
            vx=(-14, 14), vy=(-34, -10), life=(1.6, 3.2), size=(2.4, 5.2), layer=0,
            blur=(1.0, 2.2), a=(40, 110))


def _a_petals(f, ph, k, c, n, R):
    from assfx import shapes as S
    f.drift(ph.s - 0.2, ph.e + 0.6, n, c, lambda r: S.petal(r * 1.6),
            vx=(-34, -8), vy=(26, 60), life=(2.0, 3.6), size=(5, 10), layer=0,
            blur=(0.8, 1.8), a=(50, 130))


def _a_glow_curtain(f, ph, k, c, n, R):
    """光幕垂下：暖/亮场用，给画面加一层柔光"""
    b = ph.band
    cx = (b[0] + b[2]) / 2
    f.glow(0, ph.s - 0.3, ph.e + 0.5, cx, (b[1] + b[3]) / 2 - 20,
           (b[2] - b[0]) / 2 + 60, (b[3] - b[1]) / 2 + 30, c[0], a_peak=95, blur=34,
           fade_in=0.5, fade_out=0.7)


def _a_ripples(f, ph, k, c, n, R):
    from assfx import shapes as S
    for i in range(max(2, n // 3)):
        t = ph.s + i * (ph.e - ph.s) / max(1, n // 3)
        f.pulse(0, t, (ph.band[0] + ph.band[2]) / 2, ph.band[3] - 10,
                S.ring(28, 3.2), c[0], dur=1.4, s0=30, s1=210, a0=55, blur=3.0, c3=c[1], bord=1.6)


def _a_embers(f, ph, k, c, n, R):
    from assfx import shapes as S
    f.drift(ph.s, ph.e + 0.6, n, c, lambda r: S.circle(1.6 + r * 0.9),
            vx=(-18, 18), vy=(-52, -22), life=(1.2, 2.4), size=(2, 4.6), layer=0,
            blur=(1.4, 3.0), a=(50, 140))


def _a_mist(f, ph, k, c, n, R):
    from assfx import shapes as S
    b = ph.band
    for i in range(max(2, n // 5)):
        x = b[0] + (b[2] - b[0]) * (i + 0.5) / max(1, n // 5)
        f.shape(0, ph.s, ph.e + 0.4, x, (b[1] + b[3]) / 2, x + R.uniform(-40, 40), (b[1] + b[3]) / 2 - 10,
                draw=S.big_cloud(90 + R.uniform(0, 40)), c1=c[0], a_peak=40, blur=26,
                fade_in=0.6, fade_out=0.8)


def _a_light_rays(f, ph, k, c, n, R):
    from assfx import shapes as S
    b = ph.band
    cx = (b[0] + b[2]) / 2
    for i in range(3):
        f.shape(0, ph.s + i * 0.3, ph.e + 0.4, cx + (i - 1) * 150, b[1] - 20,
                cx + (i - 1) * 190, b[3] + 20, draw=S.streak(46, 3.0), c1=c[0],
                a_peak=45, blur=12, fade_in=0.5, fade_out=0.7, extra="\\frz%d" % ((i - 1) * 7))


def _a_snow(f, ph, k, c, n, R):
    from assfx import shapes as S
    f.drift(ph.s - 0.2, ph.e + 0.6, n, c, lambda r: S.snowflake(9 + r * 5),
            vx=(-20, 6), vy=(22, 48), life=(2.2, 4.0), size=(4, 9), layer=0,
            blur=(0.6, 1.6), a=(60, 150))


def _a_feathers(f, ph, k, c, n, R):
    from assfx import shapes as S
    f.drift(ph.s - 0.2, ph.e + 0.6, n, c, lambda r: S.feather(14 + r * 8),
            vx=(-30, -6), vy=(16, 40), life=(2.4, 4.2), size=(6, 13), layer=0,
            blur=(1.0, 2.2), a=(60, 150))


def _a_sparks(f, ph, k, c, n, R):
    from assfx import shapes as S
    for ch in ph.chars:
        f.burst(ch["s"], ch["x"], ph.band[3] - 30, 1, c, draw_fn=lambda r: S.sparkle(r * 1.3),
                speed=(40, 110), life=(0.5, 1.0), size=(2.4, 4.6), up=0.9, layer=0,
                blur=(1.2, 2.4), a=(40, 110))


AMBIENT = {
    "dust_up":      (("_a_dust_up",),      ("#FFF6E6", "#FFD9A8")),
    "petals":       (("_a_petals",),       ("#FFD9E4", "#FFB0C8")),
    "glow_curtain": (("_a_glow_curtain",), ("#FFE8CC", "#FFC898")),
    "ripples":      (("_a_ripples",),      ("#CFEAF6", "#8FD0F0")),
    "embers":       (("_a_embers",),       ("#FFC888", "#FF9050")),
    "mist":         (("_a_mist",),         ("#DDE6F0", "#B8C8DC")),
    "light_rays":   (("_a_light_rays",),   ("#FFF4DC", "#FFDCA0")),
    "snow":         (("_a_snow",),         ("#FFFFFF", "#CFE4F6")),
    "feathers":     (("_a_feathers",),     ("#FFF2F6", "#E8D0DC")),
    "sparks":       (("_a_sparks",),       ("#FFF0C0", "#FFD060")),
}


def ambient(f, ph, k, kind, level=1, colors=None, n=None):
    """铺一层意境背景。level 控制密度（0=最疏，3=最密）。"""
    fn_name, default_c = AMBIENT.get(kind, AMBIENT["dust_up"])
    fn = globals()[fn_name[0]]
    c = colors or default_c
    R = f.rng
    cnt = n if n is not None else {0: 7, 1: 11, 2: 16, 3: 21}.get(level, 11)
    fn(f, ph, k, c, cnt, R)


# ------------------------------------------------------------------ 逐词母题
def _m_rise_sparkle(f, ph, cs, c, lv):
    from assfx import shapes as S
    for ch in cs:
        # 每字 3+2*lv 颗；burst 是"一组"事件（内部展开成 n 颗），事件数不等于颗粒数
        f.burst(ch["s"], ch["x"], ch["y"] - 18, 3 + lv * 2, c, draw_fn=lambda r: S.sparkle(r * 1.5),
                speed=(14, 40), life=(0.8, 1.5), size=(3.0, 5.6), up=0.85, layer=5,
                blur=(1.2, 2.4), a=(40, 110))


def _m_fall_shard(f, ph, cs, c, lv):
    from assfx import shapes as S
    for ch in cs:
        f.drift(ch["s"], ch["s"] + 1.2, 3 + lv, c, lambda r: S.shard(f.rng, 11 + r * 8),
                vx=(-30, 30), vy=(36, 88), life=(0.7, 1.3), size=(5, 11), layer=5,
                blur=(0.8, 1.8), a=(60, 150))


def _m_ring_out(f, ph, cs, c, lv):
    from assfx import shapes as S
    for ch in cs:
        f.pulse(0, ch["s"], ch["x"], ch["y"] + 6, S.ring(30, 3.4), c[0],
                dur=1.0, s0=30, s1=200, a0=80, blur=3.2, c3=c[1], bord=1.8)


def _m_pulse_glow(f, ph, cs, c, lv):
    for ch in cs:
        f.glow(0, ch["s"], ch["s"] + 0.9, ch["x"], ch["y"], 62 + lv * 12, 52 + lv * 10,
               c[0], a_peak=120 + lv * 15, blur=22, fade_in=0.15, fade_out=0.45)


def _m_thread_link(f, ph, cs, c, lv):
    """红线相连：把【整句】相邻字串起来。

    注意：这个母题的语义是"句内串联"，所以不吃传入的 cs（那只是触发点），
    而是遍历整句。只连该词内部会很短、看不出来。
    """
    from assfx import shapes as S
    y = ph.chars[0]["y"] + 30
    for a, b in zip(ph.chars, ph.chars[1:]):
        f.shape(6, a["s"], b["e"] + 0.2, a["x"], y, b["x"], y,
                draw=S.thread((a["x"], y), (b["x"], y), 16, 2.0),
                c1=c[0], a_peak=130, blur=2.0, c3=c[1], bord=1.3, fade_in=0.18, fade_out=0.45)


def _m_petal_bloom(f, ph, cs, c, lv):
    from assfx import shapes as S
    for ch in cs:
        f.burst(ch["s"], ch["x"], ch["y"] + 8, 3 + lv, c, draw_fn=lambda r: S.petal(r * 1.7),
                speed=(20, 60), life=(1.0, 1.9), size=(5, 11), up=-0.4, layer=5,
                blur=(0.8, 1.8), a=(50, 130))


def _m_crack_burst(f, ph, cs, c, lv):
    from assfx import shapes as S
    for ch in cs:
        f.pulse(6, ch["s"], ch["x"], ch["y"], S.crack(f.rng, 46, 2.4), c[0],
                dur=0.6, s0=60, s1=140, a0=50, blur=1.6, c3=c[1], bord=1.4)
        f.burst(ch["s"], ch["x"], ch["y"], 3 + lv, c, draw_fn=lambda r: S.shard(f.rng, 9 + r * 6),
                speed=(60, 150), life=(0.5, 1.0), size=(3.4, 7), up=0.2, layer=6,
                blur=(0.8, 1.6), a=(70, 160))


def _m_star_twinkle(f, ph, cs, c, lv):
    from assfx import shapes as S
    for ch in cs:
        f.shape(5, ch["s"], ch["s"] + 0.42, ch["x"], ch["y"] - 6,
                draw=S.star(5, 16 + f.rng.uniform(-3, 4), 6), c1=c[0], a_peak=45,
                blur=1.6, c3=c[1], bord=1.2, fade_in=0.06, fade_out=0.30)


def _m_rust_texture(f, ph, cs, c, lv):
    from assfx import shapes as S
    for ch in cs:
        f.shape(0, ch["s"], ch["e"] + 0.5, ch["x"], ch["y"],
                draw=S.crack(f.rng, ch["w"] + 14, 2.0), c1=c[0], a_peak=90, blur=1.4,
                c3=c[1], bord=1.2, fade_in=0.25, fade_out=0.6)


def _m_mist_veil(f, ph, cs, c, lv):
    from assfx import shapes as S
    for ch in cs:
        f.shape(0, ch["s"], ch["s"] + 1.1, ch["x"], ch["y"],
                draw=S.big_cloud(46), c1=c[0], a_peak=55, blur=18, fade_in=0.3, fade_out=0.6)


def _m_feather_drift(f, ph, cs, c, lv):
    from assfx import shapes as S
    for ch in cs:
        f.drift(ch["s"], ch["s"] + 1.4, 2 + lv, c, lambda r: S.feather(13 + r * 7),
                vx=(-26, -4), vy=(-24, 8), life=(1.2, 2.2), size=(6, 12), layer=5,
                blur=(1.0, 2.0), a=(60, 150))


def _m_heart_pulse(f, ph, cs, c, lv):
    from assfx import shapes as S
    for ch in cs:
        f.pulse(5, ch["s"], ch["x"], ch["y"] - 54, S.heart(26 + lv * 5), c[0],
                dur=0.85, s0=50, s1=150, a0=40, blur=2.2, c3=c[1], bord=1.6)


MOTION = {
    "rise_sparkle":   _m_rise_sparkle,
    "fall_shard":     _m_fall_shard,
    "ring_out":       _m_ring_out,
    "pulse_glow":     _m_pulse_glow,
    "thread_link":    _m_thread_link,
    "petal_bloom":    _m_petal_bloom,
    "crack_burst":    _m_crack_burst,
    "star_twinkle":   _m_star_twinkle,
    "rust_texture":   _m_rust_texture,
    "mist_veil":      _m_mist_veil,
    "feather_drift":  _m_feather_drift,
    "heart_pulse":    _m_heart_pulse,
}


def keyword_motifs(f, ph, k, pairs, level=1, colors=None):
    """把不同的母题挂到不同的词上。

    pairs: [(词, 动作名)] —— 词可以是单字（"錆"）或多字（"孤独"），
           多字时挂到该词涉及的所有字上。
    同一句里请给**不同**的动作 —— 三个都用心形只是数量堆叠，读不出层次。
    """
    c = colors or (k.th["hi"], k.th["glow"])
    txt = "".join(ch["ch"] for ch in ph.chars)
    seen = set()
    for word, motion in pairs:
        fn = MOTION.get(motion)
        if fn is None:
            continue
        i = -1
        while True:
            i = txt.find(word, i + 1)
            if i < 0:
                break
            cs = []
            acc = 0
            for ch in ph.chars:
                if i <= acc < i + len(word):
                    cs.append(ch)
                acc += len(ch["ch"])
            if cs and (cs[0]["i"] not in seen):
                seen.add(cs[0]["i"])
                fn(f, ph, cs, c, level)
                break


def apply(f, ph, k, ambient_kind, pairs, level=1, ambient_colors=None, motif_colors=None):
    """一句 = 意境背景 + 逐词母题。生成器里对每句调用一次即可。"""
    ambient(f, ph, k, ambient_kind, level=level, colors=ambient_colors)
    keyword_motifs(f, ph, k, pairs, level=level, colors=motif_colors)
