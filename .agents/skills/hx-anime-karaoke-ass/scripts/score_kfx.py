#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""KFX 自检打分: 把散在各处的设计判据算成**一张表 + 一个总分**.

产物 `proj/review/score.md`, 交给 `steps/5-verify/16-blind-review` 的盲审子代理.

## 为什么需要它

判据此前散在六份 impl 文档里 (`three-layers` / `density` / `color` / `thread` / `beat` / `bg`),
**每一步都写了判据, 但没有一处把它们算成一张总分**. 后果实测 (漆黑子弹 v5):

    门禁 6/6 通过, 用户却连提三次「特效太多了」「图形很粗糙」「尺寸这么大」

判据不汇总 = 没有判据. 这个脚本把 A~F 六组判据**机械化**, 让"好不好"先有数字.

## 用法

    hx-karaoke score_kfx.py --project proj
    hx-karaoke score_kfx.py --project proj --out proj/review/score.md --min-score 8

退出码: 总分 < `--min-score` (默认 8.0) 时为 1.

## 六组与阈值来源

| 组 | 内容 | 阈值来源 |
|---|---|---|
| A | 设计表 15 格格式 | `42-text-main/impl/design-table.md` 的正则 |
| B | 素材来源 | `check_gates.py` 的既有判据 |
| C | 密度与层次 | `impl/density.md` 的实测值 |
| D | 色彩 | `47-color` 的色相跨度判据 |
| E | 层的时间基 | `44-beat` 的重合率 / `45-bg` 的同向率 |
| F | 生成器结构 | `gen/README.md` 的分层规范 |

**改阈值必须同时改这里的注释** —— 阈值没有出处就变成拍脑袋.
"""
import argparse, collections, hashlib, json, math, os, re, sys

BAND_RE = re.compile(r";\s*assfx-band:\s*(\S+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)")
IMG_RE = re.compile(r"\\1c&H([0-9A-Fa-f]{6})&")


def sec(x):
    h, m, s = x.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def parse_ass(path):
    evs, bands = [], {}
    for ln in open(path, encoding="utf-8-sig", errors="replace"):
        if ln.startswith(";"):
            m = BAND_RE.match(ln)
            if m:
                bands[m.group(1)] = tuple(float(g) for g in m.groups()[1:])
            continue
        if not ln.startswith("Dialogue:"):
            continue
        f = ln.split(",", 9)
        if len(f) < 10:
            continue
        try:
            lay = int(f[0].split(":")[1])
        except Exception:
            lay = 0
        evs.append(dict(layer=lay, s=sec(f[1]), e=sec(f[2]), style=f[3], name=f[4], text=f[9]))
    return evs, bands


def ass_hsv(c):
    """&HBBGGRR& -> (hue, sat, val). 注意 ASS 是 BGR 序, 颠倒会把红蓝对调."""
    import colorsys
    b, g, r = int(c[0:2], 16) / 255, int(c[2:4], 16) / 255, int(c[4:6], 16) / 255
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    return h * 360, s, v


def path_of(text):
    m = re.search(r"\\p[123]\}(.*)$", text)
    return m.group(1).strip() if m else None


def size_of(text):
    """返回 (原始路径尺寸, 实际缩放比). 缩放比取 \\t 内的终值, 没有则取初值, 都没有则 None."""
    path = path_of(text)
    if not path:
        return None, None
    nums = [float(x) for x in re.findall(r"-?\d+\.?\d*", path)]
    if len(nums) < 4:
        return None, None
    raw = max(max(nums[0::2]) - min(nums[0::2]), max(nums[1::2]) - min(nums[1::2]))
    tag = text.split("}")[0]
    ts = re.findall(r"\\t\([^)]*?\\fscx([\d.]+)", tag)
    fx = re.search(r"\\fscx([\d.]+)", tag)
    k = (float(ts[-1]) / 100) if ts else (float(fx.group(1)) / 100 if fx else None)
    return raw, k


def design_table(proj):
    p = os.path.join(proj, "review", "design-table.md")
    if not os.path.exists(p):
        return None, "缺文件"
    txt = open(p, encoding="utf-8").read()
    hdr = next((l for l in txt.splitlines() if l.startswith("|") and "主·出现" in l), None)
    if hdr is None:
        return None, "旧格式(无 主·出现 列)"
    cols = [c.strip() for c in hdr.strip().strip("|").split("|")]
    rows = []
    for l in txt.splitlines():
        if not l.startswith("|") or l.count("|") < len(cols) or "主·出现" in l:
            continue
        if re.match(r"^\|\s*[-: ]+\|", l):
            continue
        cells = [c.strip() for c in l.strip().strip("|").split("|")]
        if len(cells) >= len(cols):
            rows.append(cells[:len(cols)])
    return (cols, rows), None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=".")
    ap.add_argument("--ass", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("--min-score", type=float, default=8.0)
    a = ap.parse_args()
    proj = a.project
    items = []

    def add(i, block, name, value, thr, ok, why=""):
        items.append(dict(id=i, block=block, name=name, value=value, thr=thr, ok=bool(ok), why=why))

    # ---------------------------------------------------------------- A 设计表格式
    dt, err = design_table(proj)
    NEED = ["主·出现", "主·逐字", "主·词组", "主·意象", "主·消失",
            "副·出现", "副·逐字", "副·消失",
            "背景·场景", "背景·情绪", "背景·番剧", "承上", "启下"]
    if dt is None:
        for i, n in enumerate(["15 列齐全", "无空串", "主·逐字 取值", "副·出现 取值",
                               "副·逐字 填写率", "承上/启下 同名率", "背景·场景 填写率"]):
            add(f"A{i+1}", "A 设计表", n, err, "见 design-table.md", False, err)
    else:
        cols, rows = dt
        add("A1", "A 设计表", "15 列齐全", f"{len(cols)} 列", "含 13 个阶段列", all(c in cols for c in NEED))
        blanks = sum(1 for r in rows if any(c == "" for c in r))
        add("A2", "A 设计表", "无空串行", f"{blanks}/{len(rows)} 行有空串", "0 行", blanks == 0,
            "空串=忘了做, `—`=决定不做")
        for key, iid, need in (("主·逐字", "A3", 3), ("副·出现", "A4", 3)):
            ci = cols.index(key) if key in cols else -1
            vals = {r[ci] for r in rows if r[ci] not in ("—", "")} if ci >= 0 else set()
            add(iid, "A 设计表", f"{key} 取值种类", f"{len(vals)} 种", f">={need} 种", len(vals) >= need,
                "全曲同值 = 从没设计过")
        ci = cols.index("副·逐字") if "副·逐字" in cols else -1
        f = sum(1 for r in rows if ci >= 0 and r[ci] not in ("—", "")) / max(1, len(rows))
        add("A5", "A 设计表", "副·逐字 填写率", f"{f:.0%}", ">=50%", f >= 0.5)
        ci1 = cols.index("启下") if "启下" in cols else -1
        ci2 = cols.index("承上") if "承上" in cols else -1
        carry = 0
        if ci1 >= 0 and ci2 >= 0:
            for r1, r2 in zip(rows, rows[1:]):
                w1 = set(re.findall(r"[\u4e00-\u9fffA-Za-z_]+", r1[ci1]))
                w2 = set(re.findall(r"[\u4e00-\u9fffA-Za-z_]+", r2[ci2]))
                if w1 & w2:
                    carry += 1
        cr = carry / max(1, len(rows) - 1)
        add("A6", "A 设计表", "承上/启下 同名率", f"{cr:.0%}", ">=60%", cr >= 0.6,
            "句间承接必须传可指认的变量")
        ci = cols.index("背景·场景") if "背景·场景" in cols else -1
        sc = sum(1 for r in rows if ci >= 0 and r[ci] not in ("—", "")) / max(1, len(rows))
        add("A7", "A 设计表", "背景·场景 填写率", f"{sc:.0%}", ">=70%", sc >= 0.7)

    # ---------------------------------------------------------------- B 素材来源
    ep = os.path.join(proj, "anime.elements.md")
    if os.path.exists(ep):
        et = open(ep, encoding="utf-8").read()
        n_el = len(re.findall(r"\|\s*\*\*[^|]+\*\*\s*\|\s*(\d+)\s*\|", et))
        add("B1", "B 素材", "元素表带计数条目", f"{n_el} 条", ">=4 条", n_el >= 4)
    else:
        add("B1", "B 素材", "元素表带计数条目", "缺文件", ">=4 条", False)
    if dt:
        cols, rows = dt
        amb = sum(1 for r in rows if "氛围句" in " ".join(r))
        add("B2", "B 素材", "氛围句占比", f"{amb}/{len(rows)}", "<=35%", amb / max(1, len(rows)) <= 0.35)
    else:
        add("B2", "B 素材", "氛围句占比", "无法评", "<=35%", False)
    np_ = os.path.join(proj, "anime.notes.md")
    if os.path.exists(np_):
        nt = open(np_, encoding="utf-8").read()
        add("B3", "B 素材", "anime.notes.md", f"{len(nt.strip())} 字",
            ">=500 字且含内核/原作关系/出处",
            len(nt.strip()) >= 500 and bool(re.search(r"内核|主題|主题", nt))
            and bool(re.search(r"与原作|改编", nt)) and bool(re.search(r"来源|出处|http", nt)))
    else:
        add("B3", "B 素材", "anime.notes.md", "缺文件", ">=500 字", False)

    # ---------------------------------------------------------------- 载入 ass
    ass = a.ass or ""
    if not ass:
        for c in ("out_v5.ass", "out.ass"):
            p = os.path.join(proj, c)
            if os.path.exists(p):
                ass = p
                break
    evs, bands = ([], {})
    if ass and os.path.exists(ass):
        evs, bands = parse_ass(ass)

    def fx(prefix):
        return [e for e in evs if e["name"] == prefix] if prefix.startswith("fx:") and ":" in prefix \
            else [e for e in evs if e["name"].startswith(prefix)]

    # C 密度与层次
    per = collections.Counter(e["name"] for e in evs if e["name"].startswith("fx:p"))
    if per:
        v = sorted(per.values())
        med = v[len(v) // 2]
        # 下限 12 来自 impl/density.md 的实测(<12 判"敷衍"); 上限 60 = 参考量级 20 的 3 倍,
        # 由"用户两次指出过密"引入, **是暂定值**, 参考成品实测 19~21.
        add("C1", "C 密度", "每句 fx 事件数 中位", f"{med}", "[12, 60]", 12 <= med <= 60)
        mx = collections.defaultdict(set)
        for e in evs:
            if not e["name"].startswith("fx:p"):
                continue
            pp = path_of(e["text"])
            if pp:
                mx[e["name"]].add(hashlib.md5(pp.encode()).hexdigest()[:10])
        k = sorted(len(s) for s in mx.values())
        km = k[len(k) // 2] if k else 0
        # 判据出自 impl/three-layers.md: 一句里不同图形种类 >= 6
        add("C2", "C 密度", "每句图形种类 中位", f"{km}", ">=6", km >= 6)
    else:
        add("C1", "C 密度", "每句 fx 事件数 中位", "无 fx 事件", "[12, 60]", False)
        add("C2", "C 密度", "每句图形种类 中位", "无 fx 事件", ">=6", False)
    # 高潮/非高潮: 等级必须来自**设计表的真实 L 标注**, 不能按事件数分位.
    #
    # ⚠ 这里踩过一个循环论证(盲审 2026-10-03 指出): 早先用"事件数前 25%"定义高潮,
    # 再测"高潮/非高潮密度比" —— 分子分母都由同一组数决定, 必然自证(脚本给 1.81 PASS,
    # 而按设计表真实等级复算只有 1.17 FAIL). **判据不能用自己的被测量来分组.**
    levels = {}
    if dt:
        cols, rows = dt
        if "等级" in " ".join(cols) or True:
            lc = next((i for i, c in enumerate(cols) if "等级" in c), None)
            for r in rows:
                m = re.search(r"L([0-3])", " ".join(r))
                if m:
                    no = re.search(r"\d+", r[0])
                    if no:
                        levels[int(no.group(0))] = int(m.group(1))
    if per and levels:
        hi = [per[f"fx:p{i:02d}"] for i, L in levels.items() if L >= 2 and f"fx:p{i:02d}" in per]
        lo = [per[f"fx:p{i:02d}"] for i, L in levels.items() if L < 2 and f"fx:p{i:02d}" in per]
        if hi and lo:
            hm = sorted(hi)[len(hi) // 2]; lm = sorted(lo)[len(lo) // 2]
            ratio = hm / max(1e-6, lm)
            add("C3", "C 密度", "高潮/非高潮 密度比", f"{ratio:.2f}", ">=1.8", ratio >= 1.8,
                "等级取自设计表 L 列(不是按事件数分位 —— 那会循环论证)")
        else:
            add("C3", "C 密度", "高潮/非高潮 密度比", "设计表里没有 L 等级列", ">=1.8", False)
    else:
        add("C3", "C 密度", "高潮/非高潮 密度比", "无法评(缺 L 等级或 fx 事件)", ">=1.8", False,
            "等级必须来自设计表的 L 列")

    # D 色彩
    hs = collections.defaultdict(list)
    for e in evs:
        if not e["name"].startswith("ly:") or e["layer"] < 23:
            continue
        for m in IMG_RE.finditer(e["text"]):
            h, s, v = ass_hsv(m.group(1).upper())
            if s > 0.25 and v > 0.25:
                hs[e["name"]].append(h)
    spans = []
    for k, arr in hs.items():
        u = sorted(set(round(x) for x in arr))
        if len(u) < 2:
            spans.append(0)
            continue
        gaps = [b - x for x, b in zip(u, u[1:])] + [u[0] + 360 - u[-1]]
        spans.append(360 - max(gaps))
    if spans:
        okr = sum(1 for x in spans if 20 <= x <= 120) / len(spans)
        add("D1", "D 色彩", "每句色相跨度落 20~120°", f"{okr:.0%}", ">=90%", okr >= 0.9,
            "整句一色(跨度 0)也不合格 —— 见 47-color")
    else:
        add("D1", "D 色彩", "每句色相跨度落 20~120°", "无可评样本", ">=90%", False)

    # E 层的时间基
    mp = os.path.join(proj, "review", "music-events.json")
    tp = os.path.join(proj, "timing.json")
    if os.path.exists(mp) and os.path.exists(tp):
        import bisect
        mora = sorted(m["s"] for m in json.load(open(tp, encoding="utf-8")))
        beat = [e for e in evs if e["name"] == "fx:beat"]
        hit = 0
        for e in beat:
            i = bisect.bisect_left(mora, e["s"])
            if any(0 <= j < len(mora) and abs(mora[j] - e["s"]) < 0.04 for j in (i - 1, i)):
                hit += 1
        r = hit / max(1, len(beat))
        # ⚠ 判据不能是固定阈值(盲审 2026-10-03 指出): 在 482 个音拍上随机撒 1840 个点,
        # 落在 ±40ms 内的概率本来就 ~18.6%(实测 20 次随机: 16.2%~19.9%).
        # 所以"重合率 <=10%"任何产物都必 FAIL, 该判据没有区分度.
        # 改为**与随机基线比**: 只有显著低于基线, 才能说"卡点层真的没跟字".
        import random as _rnd
        _rnd.seed(0)
        base = []
        for _ in range(20):
            ev = [_rnd.uniform(mora[0], mora[-1]) for _ in range(len(beat) or 1)]
            h2 = 0
            for x in ev:
                i2 = bisect.bisect_left(mora, x)
                if any(0 <= j < len(mora) and abs(mora[j] - x) < 0.04 for j in (i2 - 1, i2)):
                    h2 += 1
            base.append(h2 / max(1, len(ev)))
        b = sorted(base)[len(base) // 2]
        add("E1", "E 时间基", "卡点层 vs 字音拍(对比随机基线)",
            f"实测 {r:.1%} / 随机基线 {b:.1%}", "< 基线 * 0.6", r < b * 0.6,
            "随机撒点本来就会撞上 ~19%; 只有明显低于它才算'真的没跟字'")
    else:
        add("E1", "E 时间基", "卡点层与字音拍重合率", "缺 music-events/timing", "<=10%", False)
    sp = os.path.join(proj, "review", "scene-timeline.json")
    if os.path.exists(sp):
        per_sec = {float(k): v for k, v in json.load(open(sp, encoding="utf-8"))["per_sec"].items()}
        bgc = collections.defaultdict(list)
        for e in evs:
            if e["name"] != "fx:bg":
                continue
            m = IMG_RE.search(e["text"])
            if not m:
                continue
            h, s, _ = ass_hsv(m.group(1).upper())
            if s > 0.2:
                bgc[int(e["s"])].append(h)
        hits = tot = 0
        for t, arr in bgc.items():
            if t not in per_sec or per_sec[t][1] < 0.15:
                continue
            ph = per_sec[t][0]
            bh = sum(arr) / len(arr)
            d = abs(bh - ph)
            tot += 1
            hits += min(d, 360 - d) < 60
        r = hits / max(1, tot)
        # 判据出自 45-bg 的过关条件: 同向率 >=60%
        add("E2", "E 时间基", "背景层色相同向率", f"{r:.0%} ({hits}/{tot})", ">=60%", r >= 0.6)
    else:
        add("E2", "E 时间基", "背景层色相同向率", "缺 scene-timeline", ">=60%", False)
    # E3 图片层: 只在启用时评
    imgs = [e for e in evs if e["name"] == "fx:img"]
    if imgs:
        bh = max((b[3] - b[1]) for b in bands.values()) if bands else 242
        bad = 0
        for e in imgs:
            raw, k = size_of(e["text"])
            if raw and k and raw * k > bh * 0.5:
                bad += 1
        add("E3", "E 时间基", "图片层单张高度占比", f"{bad}/{len(imgs)} 超 band 半高",
            "<=band 高 50%", bad == 0)
    else:
        add("E3", "E 时间基", "图片层", "未启用", "—", True, "不启用即通过")

    # F 生成器结构
    gen = os.path.join(proj, "gen")
    main_py = os.path.join(proj, "make_ass.py")
    if os.path.isdir(gen) and os.path.exists(main_py):
        n = len(open(main_py, encoding="utf-8").read().splitlines())
        add("F1", "F 结构", "生成器分层", f"gen/ + make_ass.py({n} 行)", "入口 <=120 行",
            n <= 120 and os.path.exists(os.path.join(gen, "common.py")))
    else:
        add("F1", "F 结构", "生成器分层", "未分层(单文件)", "gen/ 三个模块", False)

    # ---------------------------------------------------------------- 计分
    W = {"A": 2.0, "B": 1.0, "C": 1.5, "D": 1.5, "E": 1.0, "F": 1.0}
    tot_w = sum(W[i["block"][0]] for i in items)
    got = sum(W[i["block"][0]] for i in items if i["ok"])
    score = 10.0 * got / max(1e-6, tot_w)

    lines = ["# KFX 自检打分", "",
             f"- 工程: `{os.path.abspath(proj)}`",
             f"- 产物: `{os.path.basename(ass) if ass else '未找到 out.ass'}`",
             f"- **总分: {score:.1f} / 10**(门槛 {a.min_score})", "",
             "| # | 组 | 判据 | 实测 | 阈值 | 结果 |", "|---|---|---|---|---|---|"]
    for i in items:
        mark = "PASS" if i["ok"] else "**FAIL**"
        lines.append(f"| {i['id']} | {i['block']} | {i['name']} | {i['value']} | {i['thr']} | {mark} |")
    fails = [i for i in items if not i["ok"]]
    lines += ["", f"## 未过项 ({len(fails)})", ""]
    if fails:
        for i in fails:
            extra = f" —— {i['why']}" if i["why"] else ""
            lines.append(f"- **{i['id']} {i['name']}**: 实测 {i['value']}, 需 {i['thr']}{extra}")
    else:
        lines.append("- 无")
    txt = "\n".join(lines) + "\n"
    out = a.out or os.path.join(proj, "review", "score.md")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    open(out, "w", encoding="utf-8").write(txt)
    print(txt)
    print(f"-> {out}")
    return 0 if score >= a.min_score else 1


if __name__ == "__main__":
    raise SystemExit(main())
