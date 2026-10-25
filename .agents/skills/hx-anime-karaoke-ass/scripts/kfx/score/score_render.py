# -*- coding: utf-8 -*-
"""C~F 四组判据: 密度与层次 / 色彩 / 层的时间基 / 生成器结构.

输入是**已解析的 ass 事件**(evs/bands)与设计表(dt), 所以这一层不碰文件系统格式,
只做判据计算  阈值出处写在各自的注释里, 改阈值必须同时改注释.
"""
import bisect
import collections
import hashlib
import json
import os
import random as _rnd
import re

from kfx.score.score_ass import IMG_RE, ass_hsv, path_of, seg_hue_shift, size_of


def check_render(proj, evs, bands, dt, add):
    """写入 C~F 四组判据."""
    # C 密度与层次
    # 只认 "fx:" 前缀, 不认 "fx:p"  band 名由工程自定(core.py 的约定是 fx:<band>),
    # 写成 fx:p 会把 clock/verse 这类合法命名判成"无特效", 且不给任何提示.
    # 实测(盲审 2026-10-06): 内容一字不动、仅把 clock 改名 p00, C1/C2 就从 FAIL 变 PASS.
    per = collections.Counter(e["name"] for e in evs if e["name"].startswith("fx:"))
    if per:
        v = sorted(per.values())
        med = v[len(v) // 2]
        # 下限来自 impl/density.md: 低于它观众会读成"敷衍"。
        # 上限是**防糊**的: 事件多到一定程度, 观众读到的不是层次而是噪音。
        # 区间给得宽, 因为它随歌曲类型变(快歌天然密)  真正判"有没有分层"的是 C3。
        add("C1", "C 密度", "每句 fx 事件数 中位", f"{med}", "[12, 60]", 12 <= med <= 60)
        mx = collections.defaultdict(set)
        for e in evs:
            if not e["name"].startswith("fx:"):
                continue
            pp = path_of(e["text"])
            if pp:
                mx[e["name"]].add(hashlib.md5(pp.encode()).hexdigest()[:10])
        k = sorted(len(s) for s in mx.values())
        km = k[len(k) // 2] if k else 0
        # 判据: 一句里的**形态多样性**。用相对口径, 不用绝对条数 
        # 绝对条数会把"全曲只用 4 种核心图形"的专业做法误判(见 impl/thread.md).
        # 要求: 中位 >= 4 且 最贫的一句 >= 2.
        kmin = k[0] if k else 0
        add("C2", "C 密度", "每句图形种类 中位/最小", f"{km}/{kmin}", "中位>=4 且 最小>=2",
            km >= 4 and kmin >= 2)
    else:
        add("C1", "C 密度", "每句 fx 事件数 中位", "无 fx 事件", "[12, 60]", False)
        add("C2", "C 密度", "每句图形种类 中位/最小", "无 fx 事件", "中位>=4 且 最小>=2", False)
    # 高潮/非高潮: 等级必须来自**设计表的真实 L 标注**, 不能按事件数分位.
    #
    # ⚠ 这里踩过一个循环论证(盲审 2026-10-03 指出): 早先用"事件数前 25%"定义高潮,
    # 再测"高潮/非高潮密度比"  分子分母都由同一组数决定, 必然自证(脚本给 1.81 PASS,
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
        def _bucket(i):
            for k in (f"fx:p{i:02d}", f"fx:p{i}", f"fx:{i}"):
                if k in per:
                    return per[k]
            return 0
        hi = [_bucket(i) for i, L in levels.items() if L >= 2]
        lo = [_bucket(i) for i, L in levels.items() if L < 2]
        if hi and lo:
            hm = sorted(hi)[len(hi) // 2]; lm = sorted(lo)[len(lo) // 2]
            ratio = hm / max(1e-6, lm)
            add("C3", "C 密度", "高潮/非高潮 密度比", f"{ratio:.2f}", ">=1.8", ratio >= 1.8,
                "等级取自设计表 L 列(不是按事件数分位  那会循环论证)")
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
    # D 色彩: 认两条合法路线(见 47-color): ① 每段一色、句内不变; ② 同族内逐字游走.
    # 只认 ② 会把更克制的 ① 判 FAIL, 与它自己引用的文档矛盾; 实测按原判据开到满游走
    # 会得到每句 15 个色相/22 个颜色, 用户原话「配色太丑了」.
    # 判据: 多数句跨度 20~120° = 路线 ②; 否则「句内跨度中位 <=25° 且 段间色相差 >=24°」= 路线 ①.
    if spans:
        okr = sum(1 for x in spans if 20 <= x <= 120) / len(spans)
        med_span = sorted(spans)[len(spans) // 2]
        seg_shift = seg_hue_shift(evs)
        route2 = okr >= 0.9
        # 阈值出处: `47-color` 的**红线**原文  "单色族 = 无色彩叙事;
        # 彩虹 = 可读性灾难. 专业成品的区间是 **1~4 个色相族**"。
        # 所以段间叙事的判据是"**至少 2 个色相族**"(= 相邻色块中位差显著到换族,
        # 族宽按 60° 算, 即 >=30° 意味着跨越了半个族界), 而不是"每段都要变".
        # 实测(2026-10-03): 3 个族(青/绿/红)在视觉上读起来是有叙事的,
        # 而按 >=30° 会判 FAIL  那是把"克制"误判成"没叙事", 与文档红线相反。
        route1 = med_span <= 25 and seg_shift >= 24
        passed = route2 or route1
        add("D1", "D 色彩", "色彩叙事(句内游走 或 段间换档)",
            f"游走合规 {okr:.0%} / 句内跨度中位 {med_span:.0f}° / 段间色相差 {seg_shift:.0f}°",
            "游走 >=90% 或 (跨度<=25° 且 段间 >=24°)",
            passed, "两条路线都认: ① 每段一色 ② 同族内游走  见 47-color; 段间量取相邻句色相差的上四分位")
    else:
        add("D1", "D 色彩", "色彩叙事(句内游走 或 段间换档)", "无可评样本", "同上", False)

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
