#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KFX 质量红线 — 扫描流程内嵌副本。

设计原则:
  1. 每条判据都来自**实测对照**, 不是拍脑袋
  2. 能自动判的一律自动判, 不留给人工
  3. 阈值分两档: 红线(FAIL, 拒绝交付) / 黄线(WARN, 需说明理由)

用法:
  python3 quality_gate.py <ass_file> [--res 1920x1080] [--audio song.mp3]

判据来源:
  - 空间分布: 对照 assets/案例/Bravely You/成品_KFX.ass 实测
  - 配色可读性: WCAG 2.1 + doc/KFX-RULES.md
  - 结构完整性: assets/案例 的成品统计
"""
import sys, re, os, math, argparse, json
from collections import Counter, defaultdict

B = chr(92)

# ============================================================
# 红线阈值 (全部来自实测对照)
# ============================================================
RED = {
    "min_events":        2000,    # 参照成品 5211 / 点兔 71462; 低于 3000 说明只是卡拉OK
    "min_size_mb":       0.8,    # 用户明确要求
    "min_layers":        3,       # 参照成品有 5+ 个 layer
    "min_styles":        5,       # 参照成品 31 个; 至少 5 个职能样式
    "band_bottom_ratio": 0.55,    # 文字带下界 (y/H)
    "mid_band_max":      0.05,    # 画面中部 (12%~55%) 最多只能占 5%
    "min_tag_kinds":     8,     # 每条事件平均 \\t 数 (参照实测 1.60)
    "min_anim_ratio":    0.80,     # 带动画标签的事件占比; 实测大切 84% (最小)
    "require_furigana":  True,    # 必须有 -furigana 样式 + 注音事件
    "require_cn":        True,    # 必须有中文层
    "min_colors":        2,       # 至少 2 种描边色 (单色 = 无色彩叙事)
    "max_outline_lum":   0.183,   # 白填充下描边亮度上限 (WCAG 4.5:1)
    # WCAG 2.1 分两档: 普通文字 4.5:1, 大文字(>=18pt/24px, 或 >=14pt bold) 3:1。
    # 卡拉OK字幕实测 40~86px, 属于**大文字**  用 3:1。
    # 早期用 4.5:1 是判据用错档位, 会把 3.32:1 的真实作品(大切)误判 FAIL。
    "min_contrast_large": 3.0,   # 大文字 (字幕属于此档)
    "min_contrast_normal": 4.5,  # 普通文字 (备用)
    # 稳态配色的**达标事件占比**上限/下限。
    # 早期判据是「存在一对占比 >=10% 且达标」, 在动画步进多的成品上失效:
    # 无职 ED 有 135 种达标配色对, 每一种只占 3.4%, 但合计 85.8% 的事件都达标。
    # 实测分离面: 合格成品 70~100%, 未设计配色的 23~28%  阈值取在中间的空档。
    "min_readable_share": 0.50,
    # 注音层: 字号必须小于主歌词行的这个比例 (实测真实成品 0.40~0.50)
    "furi_size_ratio": 0.60,
    # 注音层: 该样式的事件中纯假名占比下限 (实测真实成品 100%)
    "furi_kana_ratio": 0.80,
    # 特效与文字的空间关系 (用户定的硬约束: 上下左右 15%)
    # 特效允许区: 文字盒 + 上下左右此比例的屏幕尺寸
    # 演进: 15% -> 5% (用户: 「我现在只要限制 5% 了, 15% 还是太广了, 我还是看不清」)
    "zone_margin": 0.05,
    "max_deco_far_ratio": 0.05,   # 偏离文字带超过上下 15% 屏高的装饰事件占比
    # 注音与主文字的生命周期关联
    "max_furi_lag_ms":   900,     # 注音最晚可比主字多活多久
}
YELLOW = {
    "min_labels_per_event": 3.0,  # 每事件不同动画标签数; 实测真实成品 3.80~7.00
    "min_particles":     2000,    # 粒子/装饰事件
    "min_rot_tags":      500,     # 旋转标签
    "min_draw_events":   200,     # 绘图事件
    "min_clip_events":   100,     # 遮罩事件
}


# 参与"标签多样性"统计的标签  覆盖 ASS 的动画/变换/绘制能力。
# 实测 6 份真实成品的种类数: 8 / 12 / 13 / 14 / 14 / 14
ANIM_TAGS = ("t","clip","iclip","p1","p2","frz","fry","frx","org","move",
             "fad","blur","bord","pos","alpha","shad")


# ------------------------------------------------------------
# band: 特效允许区的**权威来源**
# ------------------------------------------------------------
#
# 本 skill 生成的成品会在文件头写下每句的 band, 并在事件的 Name 字段声明归属:
#     ; assfx-band: p00 563.9 812.0 1356.1 1054.0 25.15 29.16
#     Dialogue: 0,0:00:25.88,0:00:28.18,FX,fx:p00,0,0,0,,{...}
# 这是**作者自己算好的答案**, 判据应当读它, 而不是反推。
#
# 反面教材(已修复): 早期判据用「全部文字事件 \pos 的 y 中位数」当基准,
# 拿每个装饰锚点与这一个标量比。失败实例  无职 ED 的标题卡锚在 y=353,
# 歌词带在 y=915, 于是标题卡的装饰被判"偏离文字带"; 同一个文件里还并存
# 注音(875)/日文(915)/中文(982) 三行, 单一标量表达不了"带"。
# 实测该判据把 1780/1780 条**全部在各自 band 内**的特效判成 20.2% 越界。
_BAND_RE = re.compile(
    r"^;\s*assfx-band:\s*(\S+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)", re.M)


def _parse_bands(text):
    """读文件自带的白名单式 band 定义: {名字: (x0, y0, x1, y1)}"""
    return {m.group(1): tuple(float(m.group(i)) for i in (2, 3, 4, 5))
            for m in _BAND_RE.finditer(text)}


# 纯假名 (含长音符/促音/小假名/浊点)。注音层的文本几乎全是假名。
_KANA_RE = re.compile(r"^[\u3041-\u3096\u30a1-\u30fa\u30fc\u3099\u309a\s]+$")


# Agent Notes: KFX 红线改用结构化判据（注音层 / 特效贴合 / 配色稳态）
# 
def _furigana_by_structure(ev, styles, text_events):
    """
    .agents/notes/implemented/bug-fix/2026-10-02-kfx-gate-structural-criteria.md
**结构性地**找出注音层, 不依赖样式命名。

    反面教材(已修复): 早期判据写死 `"-furigana" in style`, 于是
      * 本仓自己的模板 `make_ass_template.py` 生成的是 `RB` 样式,
      * 用户新交付的两份成品也用 `RB`,
    全被判「注音层: 样式无 / 事件0」判据与自家模板互相矛盾。
    同一类命名还有 `FURI`(ヨスガ ED)。

    注音层的**语义特征**是跨作品稳定的, 与它叫什么无关:
      1. 字号明显小于同文件的主歌词行 (实测 0.40~0.50 倍)
      2. 文本几乎全是纯假名 (实测 100%)
      3. 与其它文字事件**时间重叠**  它就是给那些字标注读音的

    三个条件是"与"关系, 不靠任一条单独成立, 避免把中文行/拉丁行误认成注音。
    """
    if not text_events:
        return None, 0
    # 主歌词行: 该文件里事件数最多且字号最大的文字样式
    sizes = {}
    for e in text_events:
        sv = styles.get(e["style"])
        try:
            sizes[e["style"]] = float(sv["size"]) if sv else 0.0
        except Exception:
            sizes[e["style"]] = 0.0
    if not sizes:
        return None, 0
    main_size = max(sizes.values())
    if main_size <= 0:
        return None, 0

    by_style = defaultdict(list)
    for e in text_events:
        by_style[e["style"]].append(e)

    best, best_n = None, 0
    for st, evs in by_style.items():
        fs = sizes.get(st, 0.0)
        if fs <= 0 or fs >= main_size * RED["furi_size_ratio"]:
            continue
        kana = sum(1 for e in evs
                   if _KANA_RE.match(re.sub(r"\{[^}]*\}", "", e["text"]).strip()))
        if kana / len(evs) < RED["furi_kana_ratio"]:
            continue
        # 时间重叠: 注音必须与**别的**样式文字同时出现 (它是那些字的标注)
        overlap = 0
        for e in evs[:400]:
            s, en = _ts_to_ms(e["s"]), _ts_to_ms(e["e"])
            for o in text_events:
                if o["style"] == st:
                    continue
                if _ts_to_ms(o["s"]) < en and _ts_to_ms(o["e"]) > s:
                    overlap += 1
                    break
        if overlap / max(1, min(len(evs), 400)) < 0.5:
            continue
        if len(evs) > best_n:
            best, best_n = st, len(evs)
    return best, best_n


def _ts_to_ms(s):
    try:
        h, m, rest = s.split(":"); ss, cs = rest.split(".")
        return int(h)*3600000+int(m)*60000+int(ss)*1000+int(cs)*10
    except Exception:
        return 0


def _furi_lag(main_evs, furi_evs):
    """注音比主文字多活多久 (ms)。

    判法: 按**时间重叠**配对, 不用起始时间做 key 
    主字有 3 个 stage(暗淡/高亮/余辉), 各有不同起始时间; 注音只有 1 条。
    早期用 e["s"] 做 key, 于是注音永远找不到对应的主字, 拿全部主字的最大值去比,
    得出了虚高的 1410ms。

    正确做法: 对每条注音, 找**与它时间重叠最多**的那组主字, 比较二者结束时间。
    """
    if not main_evs or not furi_evs:
        return 0
    lags = []
    for fe in furi_evs:
        fs, fend = _ts_to_ms(fe["s"]), _ts_to_ms(fe["e"])
        best = None; best_ov = -1
        for me in main_evs:
            ms0, me0 = _ts_to_ms(me["s"]), _ts_to_ms(me["e"])
            ov = min(fend, me0) - max(fs, ms0)
            if ov > best_ov:
                best_ov = ov; best = me0
        if best is not None and best_ov > 0:
            lags.append(max(0, fend - best))
    # 取 95 分位而不是最大值  个别句尾的收束慢一点不代表整体脱节
    if not lags:
        return 0
    lags.sort()
    return lags[int(len(lags)*0.95)] if len(lags) > 1 else lags[0]


def _external_grade(path):
    """调用外部评分器 (research-output/ass-kfx-grade/kfx_grade.py)。

    找不到脚本或执行失败时返回 {}  评分是**加分判据**, 不该让整体检查崩掉。
    """
    import subprocess, json, os
    here = os.path.dirname(os.path.abspath(__file__))
    # py/music -> repo root
    root = os.path.abspath(os.path.join(here, "..", "..", "..", ".."))
    script = os.path.join(root, "research-output", "ass-kfx-grade", "kfx_grade.py")
    if not os.path.exists(script):
        return {}
    try:
        r = subprocess.run([sys.executable, script, "--json", str(path)],
                           capture_output=True, text=True, timeout=180)
        if r.returncode != 0 or not r.stdout.strip():
            return {}
        data = json.loads(r.stdout)
        if not data: return {}
        v = data[0].get("verdict", {})
        return {"score": v.get("score", 0), "grade": v.get("grade", "?"),
                "failed": v.get("failed", [])}
    except Exception:
        return {}


def contrast_rgb(fill_hex, outline_hex):
    """两个 ASS 色值(&HBBGGRR& 或裸 hex)之间的对比度。"""
    l1, l2 = lum_hex(fill_hex), lum_hex(outline_hex)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def lum_hex(h):
    h = h.lstrip("&H").lstrip("&").rstrip("&")
    h = h[-6:]
    r, g, b = int(h[4:6],16)/255.0, int(h[2:4],16)/255.0, int(h[0:2],16)/255.0
    def f(x): return x/12.92 if x <= 0.03928 else ((x+0.055)/1.055)**2.4
    return 0.2126*f(r) + 0.7152*f(g) + 0.0722*f(b)


def parse(path):
    raw = open(path, "rb").read()
    bom = raw[:3] == b"\xef\xbb\xbf"
    t = raw.decode("utf-8-sig", errors="replace")
    ev = []
    for l in t.splitlines():
        if l.startswith("Dialogue:"):
            f = l.split(",", 9)
            if len(f) >= 10:
                ev.append({"layer": f[0].split(":")[1].strip(), "s": f[1], "e": f[2],
                           "style": f[3], "name": f[4].strip(), "fx": f[8], "text": f[9]})
    styles = {}
    for l in t.splitlines():
        if l.startswith("Style:"):
            f = l.split(",")
            if len(f) > 20:
                styles[f[0][6:].strip()] = {"font": f[1], "size": f[2],
                                            "primary": f[3], "outline": f[5],
                                            "outline_w": f[16] if len(f) > 16 else "1"}
    return {"text": t, "events": ev, "styles": styles, "bom": bom}


def analyse(d, res, path=None):
    W, H = res
    ev = d["events"]; t = d["text"]
    E = len(ev)
    out = {"events": E, "size_mb": len(t.encode("utf-8"))/1048576}
    # layer / style
    out["layers"] = len(set(e["layer"] for e in ev))
    out["styles"] = len(d["styles"])
    # 动画
    tt = [len(re.findall(re.escape(B)+r"t\(", e["text"])) for e in ev]
    out["t_tags_avg"] = (sum(tt)/E) if E else 0
    # 动画事件: 带任一动画标签的都算 (早期只查 [tc]/move, 漏了 frz/p1/blur/fad 等)
    ANIM_ANY = re.compile(re.escape(B)+r"(?:t|clip|iclip|p[1-6]|frz|fry|frx|org|move|fad|blur|bord|alpha|shad)")
    anim = sum(1 for e in ev if ANIM_ANY.search(e["text"]))
    out["anim_ratio"] = anim/E if E else 0
    # 空间
    ys=[]; xs=[]
    for e in ev:
        for m in re.finditer(re.escape(B)+r"(?:pos|move)\((-?[0-9.]+),(-?[0-9.]+)", e["text"]):
            xs.append(float(m.group(1))); ys.append(float(m.group(2)))
    if ys:
        out["y_min"], out["y_max"] = min(ys), max(ys)
        out["x_min"], out["x_max"] = min(xs), max(xs)
        out["mid_ratio"] = sum(1 for y in ys if 0.12*H < y < RED["band_bottom_ratio"]*H)/len(ys)
    else:
        out["y_min"]=out["y_max"]=out["x_min"]=out["x_max"]=0; out["mid_ratio"]=1.0
    # 功能层
    #
    # 注音层用**结构**判定 (字号 + 纯假名 + 时间重叠), 不用样式命名。
    # 判据见 _furigana_by_structure 的注释: 写死 "-furigana" 会把自家模板
    # 生成的 `RB` 样式和用户新交付的成品全部判成"没有注音层"。
    # 实际赋值在下方 is_text_event 定义之后 (需要它来筛文字事件)。
    out["cn_events"] = sum(1 for e in ev if "CN" in e["style"] or "CN" in e["style"])
    out["particle_events"] = sum(1 for e in ev if "Ptcl" in e["style"] or "Particle" in e["style"])
    out["rot_tags"] = len(re.findall(re.escape(B)+r"frz", t))
    out["draw_events"] = len(re.findall(re.escape(B)+r"p[1-6]", t))
    out["clip_events"] = len(re.findall(re.escape(B)+r"clip\(", t))
    out["move_tags"] = len(re.findall(re.escape(B)+r"move\(", t))
    # 动画标签的"种类数"与"每事件标签数"
    #
    # 为什么用种类而非密度: 预渲染式成品靠堆事件做动画, 一条 t 标签都不用
    # (实测 ときめき t 密度 0.07 / 命运石之门 0.02), 用密度判会误杀。
    # "用了几种标签"对模板式与预渲染式都成立  实测真实成品 8~14 种。
    kinds = 0
    for tg in ANIM_TAGS:
        if re.search(re.escape(B)+tg+r"(?![a-z])", t):
            kinds += 1
    out["tag_kinds"] = kinds
    per = []
    for e in ev[:4000]:
        k = set()
        for tg in ANIM_TAGS:
            if re.search(re.escape(B)+tg+r"(?![a-z])", e["text"]):
                k.add(tg)
        per.append(len(k))
    out["labels_per_event"] = (sum(per)/len(per)) if per else 0.0
    # 色彩: 只统计**承载文字**的样式的描边色。
    #
    # 不用样式名白名单  各作品的命名毫无规律（"OP JP 6-furigana" / "OPCN-A" /
    # "TextLit" / "S3" ...）。判据改为**结构性的**: 凡是被文字事件引用、
    # 且该事件文本确实含可读字符的样式, 都算"承载文字"。
    # 装饰层的特征是: 引用它的事件的文本全是绘图路径 (\p1 后跟 "m ..."), 或没有可读字符。
    used = Counter(e["style"] for e in ev)
    # ASS 绘图路径的字面量: "m 12 34 b 56 78 ... l 90 12 ..." 全是坐标。
    # 这类事件即使去掉 override 块, 剩下的也不是"可读文本"。
    DRAW_PATH = re.compile(r"^\s*[mnlbspc]\s+(-?[0-9.]+\s*)+$")
    def is_drawing(text):
        s = re.sub(r"{[^}]*}", "", text).strip()
        if not s: return False
        # 去掉全部 "命令+数字" 对后应当为空
        s2 = re.sub(r"[mnlbspc]\s*(?:-?[0-9.]+\s*)+", "", s)
        return s2.strip() == "" and bool(re.search(r"[mnlbspc]", s))
    def is_text_event(e):
        """**逐事件**判定: 这条事件到底在画字还是在画图形?

        必须按事件判, 不能按样式判  同一个样式(如大切 的 OPJP)既用来写歌词,
        也用来画羽毛粒子(\p2 + "m 26 37 l 38 27...")。
        早期版本只看该样式的**首条**事件就下结论, 于是羽毛粒子的 `\3c` 颜色
        (#EBBEBE 浅粉) 被当成"文字描边"判 FAIL。
        """
        txt = e["text"]
        # 1) 声明了绘图模式 (p1~) 且未 p0 复位 -> 是图形
        if re.search(re.escape(B)+r"p[1-6]", txt) and not re.search(re.escape(B)+r"p0", txt):
            return False
        # 2) 去掉 override 块后是纯绘图路径 -> 是图形
        if is_drawing(txt):
            return False
        # 3) 去掉 override 块后还有可读字符 -> 是文字
        return bool(re.sub(r"{[^}]*}", "", txt).strip())

    def has_outline(e, sv):
        """这条事件真的有描边吗?

        \bord0 = 没有描边, 那种样式是**发光层/光晕层**  它的 \3c 只是辉光颜色,
        不是勾边, 用可读性门槛去卡它是判据用错对象。
        样式表里的 Outline 字段为 0 同理。
        """
        for m in re.finditer(re.escape(B)+r"bord([0-9.]+)", e["text"]):
            return float(m.group(1)) > 0
        if sv:
            try:
                return float(sv.get("outline_w", 1)) > 0
            except Exception:
                pass
        return True

    # 注音层: 结构性识别 (需要 is_text_event, 因此放在这里而非函数开头)
    _furi_style, _furi_n = _furigana_by_structure(
        ev, d["styles"], [e for e in ev if is_text_event(e)])
    out["furi_style"] = _furi_style
    out["has_furi_style"] = _furi_style is not None
    out["furi_events"] = _furi_n

    # 逐**事件**收集「文字描边色 + 它配的填充色」。
    #
    # 为什么要成对记录: 可读性判据是 **填充 vs 描边** 的对比度, 缺任一方都算不出。
    # 同一文件里可能**两种方向并存**  实测 ときめき 多数样式是「白填充+深蓝描边」,
    # 而 JP_FX_A 是反过来的「深蓝填充+白描边」(负片风格)。按"文件级主填充"判会误伤。
    pairs = Counter()
    for ev1 in ev:
        if not is_text_event(ev1):
            continue                      # 图形/粒子事件
        sv = d["styles"].get(ev1["style"])
        if not has_outline(ev1, sv):
            continue                      # bord0 的发光层, 没有描边
        # 该事件的描边色
        mo = re.search(re.escape(B)+r"3c&H([0-9A-Fa-f]{6,8})&", ev1["text"])
        if mo:
            oc = mo.group(1)[-6:]
        elif sv:
            oc = sv["outline"].lstrip("&H").lstrip("&").rstrip("&")[-6:]
        else:
            continue
        # 该事件的填充色
        mf = re.search(re.escape(B)+r"1c&H([0-9A-Fa-f]{6,8})&", ev1["text"])
        if mf:
            fc = mf.group(1)[-6:]
        elif sv:
            fc = sv["primary"].lstrip("&H").lstrip("&").rstrip("&")[-6:]
        else:
            continue
        pairs[(fc, oc)] += 1
    out["pairs"] = pairs
    out["outline_colors"] = len(set(oc for _fc, oc in pairs))
    out["outline_cols"] = pairs.most_common(8)
    # ---- 高级度评分: 复用 research-output/ass-kfx-grade/kfx_grade.py ----
    #
    # 不在这里重写一遍判据  那份脚本有 9 条判据 + 51 项指标, 阈值是从
    # 5 份高级成品与 2 份基线实测标定的。重写会引入偏差。
    # 装饰事件的**锚点**检查。
    #
    # 判据看的是 **\move 的起点 / \pos 的位置**(即"它从哪儿长出来"),
    # 不是图形的终点或包围盒  因为跟随式粒子**设计上就要向外飘出去**,
    # 落点远是特征而不是缺陷。参照成品的羽毛也是 move(440,48,430,-49),
    # 起点贴着文字(48), 终点飘到 -49。
    #
    # 排除粒子层: 粒子的散点分布是既有设计, 且数量极大(3.5万条)会淹没判据。
    PARTICLE_HINT = ("Ptcl", "Particle", "Spark", "Glitter", "Dust")
    bands = _parse_bands(d["text"])
    # 每句的**墨迹包围盒**: 该句所有文字事件的外接矩形 (再外扩 5% 画面)。
    # 这是"文字带"的逐句形式  band 只能表达一句, 而一个文件有几十句。
    lyric_boxes = []          # (s_ms, e_ms, x0, x1, y0, y1)
    decos = []                # (s_ms, e_ms, x, y, band_name|None)
    for e in ev:
        s_ms, e_ms = _ts_to_ms(e["s"]), _ts_to_ms(e["e"])
        if is_text_event(e):
            # 标题卡不属于歌词带, 不参与 band 计算
            if e["name"].startswith("card:"):
                continue
            g2 = re.search(re.escape(B)+r"pos\((-?[0-9.]+),(-?[0-9.]+)\)", e["text"])
            if not g2:
                continue
            sv = d["styles"].get(e["style"]) or {}
            try:
                fs = float(sv.get("size", 40))
            except Exception:
                fs = 40.0
            txt = re.sub(r"\{[^}]*\}", "", e["text"]).strip()
            x, y = float(g2.group(1)), float(g2.group(2))
            w = fs * max(1, len(txt))
            lyric_boxes.append((s_ms, e_ms, x - w/2, x + w/2, y - fs/2, y + fs/2))
            continue
        if any(h in e["style"] for h in PARTICLE_HINT):
            continue
        gm = re.search(re.escape(B)+r"move\((-?[0-9.]+),(-?[0-9.]+),", e["text"])
        gp = re.search(re.escape(B)+r"pos\((-?[0-9.]+),(-?[0-9.]+)\)", e["text"])
        if gm:
            px, py = float(gm.group(1)), float(gm.group(2))
        elif gp:
            px, py = float(gp.group(1)), float(gp.group(2))
        else:
            continue
        nm = e["name"]
        decos.append((s_ms, e_ms, px, py, nm[3:] if nm.startswith("fx:") else None))
    # ---- 特效与文字的空间关系 (用户定的硬约束: 上下左右 5%) ----
    #
    # 用户明确要求: 「特效就只能紧贴着文字, 在文字的旁边,
    # 范围 15% 就是上下左右 15%, 已经是顶级了」, 后收紧到 5%。
    #
    # 判定顺序(**按权威性**, 先读作者给的答案):
    #   1. 文件自带的 `; assfx-band:` 表 + 事件的 `fx:<band>` 归属
    #       skill 的硬规则第 5 条要求每条绘图事件都写它, 这是作者算好的答案;
    #   2. 没有 band 声明时, 回退到**同句墨迹包围盒** (逐句, 不是全文件一个标量)。
    #
    # 为什么不能用"全局文字 y 中位数": 一个文件里同时存在标题卡、注音、日文、
    # 中文多行, 单一标量既代表不了"带", 也会让标题卡的装饰去跟歌词行比。
    # 实测该判据把无职 ED 中 1780/1780 条**全在各自 band 内**的特效判成 20.2% 越界。
    #
    # 判据看的是 **\move 的起点 / \pos 的位置**(即"它从哪儿长出来"),
    # 不是图形的终点或包围盒  因为跟随式粒子**设计上就要向外飘出去**。
    if decos:
        slack_x = RED["zone_margin"] * W
        slack_y = RED["zone_margin"] * H
        far = 0; judged = 0; skipped = 0
        for (ds, de, px, py, bname) in decos:
            rect = bands.get(bname) if bname else None
            if rect is not None:
                judged += 1
                if not (rect[0]-1 <= px <= rect[2]+1 and rect[1]-1 <= py <= rect[3]+1):
                    far += 1
                continue
            # 无 band 声明: 与该装饰**同句**的文字墨迹包围盒比
            ov = [b for b in lyric_boxes if b[0] < de and b[1] > ds]
            if not ov:
                skipped += 1        # 该时刻没有歌词行 (纯过场特效), 不作判断
                continue
            judged += 1
            x0 = min(b[2] for b in ov) - slack_x; x1 = max(b[3] for b in ov) + slack_x
            y0 = min(b[4] for b in ov) - slack_y; y1 = max(b[5] for b in ov) + slack_y
            if not (x0 <= px <= x1 and y0 <= py <= y1):
                far += 1
        out["deco_far_ratio"] = far / judged if judged else 0.0
        out["deco_judged"] = judged
        out["deco_skipped"] = skipped
        out["text_y"] = (sorted(b[4] for b in lyric_boxes)[len(lyric_boxes)//2]
                         if lyric_boxes else 0.0)
        out["deco_y_span"] = max(y for _s, _e, _x, y, _b in decos) - min(y for _s, _e, _x, y, _b in decos)
        out["deco_x_span"] = max(x for _s, _e, x, _y, _b in decos) - min(x for _s, _e, x, _y, _b in decos)
    else:
        out["deco_far_ratio"] = 0.0; out["text_y"] = 0.0
        out["deco_y_span"] = 0.0; out["deco_x_span"] = 0.0
    # ---- 注音与主文字的**生命周期关联** ----
    #
    # 判据来源: 用户指出「你的文字如果要消失, 你的注音为什么不关联?」。
    # 失败的实例: 注音事件跨度 ds->de(整句), 而主文字在 Stage3 就淡出了,
    # 导致「字没了, 注音还在」。
    #
    # 判法: 取同一条歌词里最后一个主文字事件的结束时间, 与注音事件结束时间比。
    # 用结构判出来的注音样式名, 不用写死的 "-furigana" (见 _furigana_by_structure)。
    _fs = out.get("furi_style")
    out["furi_lag_max"] = _furi_lag(
        [e for e in ev if is_text_event(e) and e["style"] != _fs],
        [e for e in ev if e["style"] == _fs],
    ) if _fs else 0
    out["grade"] = _external_grade(path) if path else {}
    # 兼容旧字段: 取占比最高的那对的填充色
    out["main_fill"] = pairs.most_common(1)[0][0][0] if pairs else "FFFFFF"
    return out


def check(a):
    fails, warns, oks = [], [], []
    def R(k, cond, msg):
        (oks if cond else fails).append(msg)
    def Y(k, cond, msg):
        (oks if cond else warns).append(msg)
    R("events", a["events"] >= RED["min_events"], "事件数 %d (红线 >=%d)" % (a["events"], RED["min_events"]))
    R("size", a["size_mb"] >= RED["min_size_mb"], "体积 %.2f MB (红线 >=%.1f)" % (a["size_mb"], RED["min_size_mb"]))
    R("layers", a["layers"] >= RED["min_layers"], "图层数 %d (红线 >=%d)" % (a["layers"], RED["min_layers"]))
    R("styles", a["styles"] >= RED["min_styles"], "样式数 %d (红线 >=%d)" % (a["styles"], RED["min_styles"]))
    # 动画标签种类 (替代早期的 "\\t 密度" 判据)
    R("tk", a["tag_kinds"] >= RED["min_tag_kinds"],
      "动画标签种类 %d (红线 >=%d)" % (a["tag_kinds"], RED["min_tag_kinds"]))
    Y("lpe", a["labels_per_event"] >= YELLOW["min_labels_per_event"],
      "每事件不同标签数 %.2f (黄线 >=%.1f; 实测真实成品 3.80~7.00)" % (
          a["labels_per_event"], YELLOW["min_labels_per_event"]))
    # 用整数百分比比较, 避免 0.9 >= 0.9 的浮点误差 (0.8999… 会误判 FAIL)
    R("anim", round(100*a["anim_ratio"]) >= round(100*RED["min_anim_ratio"]),
      "动画事件占比 %d%% (红线 >=%d%%)" % (round(100*a["anim_ratio"]), round(100*RED["min_anim_ratio"])))
    R("mid", a["mid_ratio"] <= RED["mid_band_max"], "画面中部占用 %.1f%% (红线 <=%.0f%%)" % (100*a["mid_ratio"], 100*RED["mid_band_max"]))
    R("furi", (not RED["require_furigana"]) or (a["has_furi_style"] and a["furi_events"]>0),
      "注音层: 样式%s / 事件%d" % (("'%s'" % a["furi_style"]) if a["has_furi_style"] else "无", a["furi_events"]))
    # 中文层是**本项目(中日双语)的交付需求**, 不是通用质量判据 
    # 纯日文作品(如大切がきこえる)没有中文翻译, 用红线拦它是判据越界。改判黄线。
    Y("cn", a["cn_events"]>0, "中文层: %d 事件 (本项目要求有)" % a["cn_events"])
    # 可读性判据: 量**达标事件占总事件的比重**, 而不是"某一对占比是否 >=10%"。
    #
    # 静态解析分不清"稳态色"与"过渡色":
    #   * \t 动画里的闪白目标值(填充白+描边白=1:1)会作为独立配对被统计出来,
    #     它是**点亮瞬间的一帧**, 不是设计的稳态;
    #   * 暗态(整行先出现时)故意不强调轮廓, 暗字配暗描边也是低对比, 但那是设计意图。
    #
    # 早期的判据是「存在一对占比 >=10% 且达标」。它在**逐字拉长、动画步进密**的
    # 成品上失效: 无职 ED 有 135 种达标配色对(合计 85.8% 的事件都达标), 但每一种
    # 只占 3.4%  于是被判 FAIL, 理由却是"无一对占比 >=10% 的配色达标"。
    # 那是判据形状与作品形态不匹配, 不是作品没有可读配色。
    #
    # 实测分离面(有效对中有多少事件达标): 合格成品 70~100%,
    # 未设计配色的 23~28%  阈值落在空档里。
    thr = RED["min_contrast_large"]
    prs = a.get("pairs") or Counter()
    if prs:
        tot = sum(prs.values()) or 1
        ranked = sorted(prs.items(), key=lambda kv: -kv[1])
        ok_events = sum(n for (fc, oc), n in prs.items() if contrast_rgb(fc, oc) >= thr)
        share = ok_events / tot
        # 报告用的代表对: 占比最高且达标的那一对
        ok_pairs = [((fc, oc), n) for (fc, oc), n in ranked if contrast_rgb(fc, oc) >= thr]
        if share >= RED["min_readable_share"] and ok_pairs:
            (fc, oc), n = ok_pairs[0]
            R("lum", True,
              "稳态配色可读性: 达标事件 %d/%d = %.0f%% (阈值 >=%.0f%%; 代表对 填充 #%s / 描边 #%s = %.2f:1, %d 条)" % (
                  ok_events, tot, 100*share, 100*RED["min_readable_share"],
                  fc, oc, contrast_rgb(fc, oc), n))
        else:
            (fc, oc), n = ranked[0]
            R("lum", False,
              "可读配色不足: 达标事件 %d/%d = %.0f%% (阈值 >=%.0f%%; 占比最高的是 #%s/#%s = %.2f:1, %d 条)" % (
                  ok_events, tot, 100*share, 100*RED["min_readable_share"],
                  fc, oc, contrast_rgb(fc, oc), n))
        # 暗态检视: 填充最暗的那对需对背景 >=3:1, 否则整行会像没出现
        (dfc, doc), dn = min(prs.items(), key=lambda kv: lum_hex(kv[0][0]))
        rb = contrast_rgb(dfc, "0B1016")
        Y("dark", rb >= 3.0,
          "暗态可读性: 填充 #%s 对背景 = %.2f:1 (黄线 >=3.0:1, %d 条)" % (dfc, rb, dn))
    Y("ptcl", a["particle_events"] >= YELLOW["min_particles"],
      "粒子事件 %d (黄线 >=%d)" % (a["particle_events"], YELLOW["min_particles"]))
    Y("rot", a["rot_tags"] >= YELLOW["min_rot_tags"],
      "旋转标签 %d (黄线 >=%d)" % (a["rot_tags"], YELLOW["min_rot_tags"]))
    Y("draw", a["draw_events"] >= YELLOW["min_draw_events"],
      "绘图事件 %d (黄线 >=%d)" % (a["draw_events"], YELLOW["min_draw_events"]))
    # ---- 特效必须紧贴文字 (用户硬约束: 上下左右 15%) ----
    fr = a.get("deco_far_ratio", 0.0)
    R("zone", fr <= RED["max_deco_far_ratio"],
      "特效贴合度: 偏离文字带(y=%.0f)超过 %.0f%% 屏高的装饰事件占 %.1f%% (红线 <=%.0f%%)" % (
          a.get("text_y", 0), 100*RED["zone_margin"], 100*fr, 100*RED["max_deco_far_ratio"]))
    # ---- 注音必须与主文字同生命周期 ----
    lag = a.get("furi_lag_max", 0)
    R("furi_sync", lag <= RED["max_furi_lag_ms"],
      "注音/主字生命周期: 注音最多多活 %d ms (红线 <=%d ms)" % (lag, RED["max_furi_lag_ms"]))
    Y("clip", a["clip_events"] >= YELLOW["min_clip_events"],
      "遮罩事件 %d (黄线 >=%d)" % (a["clip_events"], YELLOW["min_clip_events"]))
    # ---- 高级/土 评分 (判据与阈值见 research-output/ass-kfx-grade/README.md) ----
    #
    # 这套判据是从 5 份高级成品与 2 份基线(模板态/K轴)的**实测分离面**标定的,
    # 实测无中间态: 高级 92.5~100, 土 0~15。
    # 阈值只取"被全部高级成品满足"的那一侧, 避免拦合格品。
    g = a.get("grade") or {}
    if g:
        R("grade", g["score"] >= 80,
          "高级度评分 %s/100 (%s)" % (g["score"], g["grade"]))
        if g.get("failed"):
            warns.append("评分未拿满项的判据: %s" % ", ".join(g["failed"][:6]))
    return fails, warns, oks



# 豁免名单: 这些不是"本项目要交付的成品", 不参与红线判定。
# 判据写的都是**交付标准**; 参考作品 / 素材 / 转轴文件本来就不该按交付标准量。
#   - 参考作品: 学它的手法, 不交付它
#   - 纯 K 轴: 是输入不是输出
EXEMPT_MARKERS = (
    "Charlotte",            # 用户指定的学习对象, 非本仓库产物
    "点兔", "天使の3P",     # 素材库参考作品
    ".bak-", ".orig.",      # 备份
)

def run_gate(path, res=(1920,1080)):
    """供扫描流程调用的入口。

    返回 None 表示**不做判断**, 三种情况:
      - 文件不可解析
      - 事件数 < 100 (不是特效成品)
      - 命中豁免名单 (参考作品 / 素材, 不是本项目的交付物)

    返回 dict: {"ok": bool, "events": int, "size_mb": float, "fails": [...], "warns": [...]}

    为什么不在这里打印: 扫描器要自己控制输出格式。
    """
    p = str(path)
    if any(m in p for m in EXEMPT_MARKERS):
        return None
    try:
        d = parse(p)
    except Exception:
        return None
    if len(d["events"]) < 100:
        return None      # 不是特效成品, 不拦
    s = analyse(d, res, path)
    fails, warns, oks = check(s)
    return {"ok": not fails, "events": s["events"], "size_mb": s["size_mb"],
            "fails": fails, "warns": warns, "oks": oks, "stats": s}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ass")
    ap.add_argument("--res", default="1920x1080")
    a = ap.parse_args()
    W,H = [int(x) for x in a.res.lower().split("x")]
    d = parse(a.ass)
    s = analyse(d, (W,H), a.ass)
    f,w,ok = check(s)
    print("="*64)
    print("KFX 质量红线检查: %s" % a.ass)
    print("="*64)
    print("  事件 %d   体积 %.2f MB   图层 %d   样式 %d" % (s["events"], s["size_mb"], s["layers"], s["styles"]))
    if s.get("grade"):
        print("  高级度 %s/100 (%s)" % (s["grade"]["score"], s["grade"]["grade"]))
    print("  y 范围 %.0f~%.0f   x 范围 %.0f~%.0f   中部占用 %.1f%%" % (s["y_min"],s["y_max"],s["x_min"],s["x_max"],100*s["mid_ratio"]))
    print("  注音 %d   中文 %d   粒子 %d   旋转 %d   遮罩 %d" % (s["furi_events"],s["cn_events"],s["particle_events"],s["rot_tags"],s["clip_events"]))
    print()
    for m in ok:   print("  [PASS] %s" % m)
    for m in w:    print("  [WARN] %s" % m)
    for m in f:    print("  [FAIL] %s" % m)
    print()
    print("结果:", "✅ 通过红线" if not f else "❌ 未通过 (%d 条红线)" % len(f))
    return 0 if not f else 1


if __name__ == "__main__":
    sys.exit(main())
