# -*- coding: utf-8 -*-
"""`align` 阶段: LDDC 逐字形状 + 本地 CTC 行首 -> 音拍级时间轴, 并写融合报告.

融合方式只有一行: `pred = lddc_rel + (ctc_line_start - lddc_line_start)` 
句内相对形状来自网络逐字, 整体平移来自本地音频. 细节与实测依据见模块头的表
(在 kf/__init__ 的说明与 ).
"""
import json
import os
import sys


def load_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)

from kf.pool import build_global_pool, shape_from_pool
from kf.shape import key, line_ends, line_starts, local_shape, shape_for_line, shape_quality
from kf.shape import norm


def cmd_align(a):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from assfx.base.lyrics import load as load_lyrics

    lyr_path = a.lyrics if os.path.isabs(a.lyrics) else os.path.join(a.project, a.lyrics)
    lines = load_lyrics(lyr_path)
    print("[align] %s：%d 行 / %d 音拍" % (lyr_path, len(lines),
                                          sum(len(u["morae"]) for ln in lines for u in ln["units"])))

    auto_path = a.auto if os.path.isabs(a.auto) else os.path.join(a.project, a.auto)
    if not os.path.exists(auto_path):
        sys.exit("[align] 缺 %s。先跑 align_ctc.py（它负责本地音频的行首），"
                 "本脚本只提供句内形状，不单独决定整体位置。" % auto_path)
    timing = load_json(auto_path)
    st = line_starts(timing)
    print("[align] 锚点 %s：%d 行" % (auto_path, len(st)))

    kf_path = a.kf if os.path.isabs(a.kf) else os.path.join(a.project, a.kf)
    if not os.path.exists(kf_path):
        print("[align] 缺 %s  没有网络逐字时**本脚本不做任何事**（不会伪造）。"
              "退回纯 CTC 流程，或先跑 fetch。" % kf_path)
        print("[align] 若确认要用纯 CTC 结果，直接把它当 timing.json 走人工校时即可；本步跳过。")
        return 0
    kf = load_json(kf_path)
    kidx = {}
    for i, l in enumerate(kf["lines"]):
        kidx.setdefault(key(l["text"]), []).append(i)
    print("[align] 逐字 %s：%d 行（源 %s / song %s）" % (kf_path, len(kf["lines"]), kf.get("source"), kf.get("song_id")))

    # ---- 0) 全局字符池（行级匹配失败时的兜底；见 build_global_pool 的说明）----
    pool_chars, pool_times = build_global_pool(kf)
    print("[align] 全局字符池 %d 字" % len(pool_chars))

    # ---- 1) 每行的句内形状 + 两个锚点 ----
    rows = []
    miss = []
    n_pool = 0
    # 已被某一行用掉的逐字行下标。
    #
    # 为什么需要它：副歌里**同一句会重复出现 2~3 次**，而 `kidx` 是「文本 -> 所有下标」。
    # 原实现永远取 `kidx[k][0]`，于是第二次出现的那句会吸到**第一次的**行首。
    # 实测（2026-10-02）：同一句词在 kf 里出现在 28(201.84s) 与 32(225.06s) 两处，
    # 原实现让 line 25 与 line 29 都锚到 201.84 → line 29 整行落到 202s（真值 225s），
    # 「Like a lotus」同理（line 27 与 line 31 都锚到 210.35）
    # 后来加的"离群行兜底"只换偏移量、换不掉行首，于是这两行被夹成零长（间距 -14.6s）。
    # 改成「取尚未使用、且行首最靠近本行本地锚点的那一次」。
    used_kf = set()
    for li, ln in enumerate(lines):
        if ln.get("call"):
            continue
        if li not in st:
            miss.append((li, "无本地锚点"))
            continue
        k = key("".join(u["surf"] for u in ln["units"]))
        shape, lddc_start, how = None, None, ""
        if k in kidx:
            cands = []
            for j in kidx[k]:
                if j in used_kf:
                    continue
                t0 = min((w["s"] for w in kf["lines"][j]["words"] if w["s"] is not None), default=None)
                if t0 is not None:
                    cands.append((j, t0))
            if cands:
                cands.sort(key=lambda jt: abs(jt[1] - st[li]))     # 就近：本地锚点指着哪一次就用哪一次
                j, lddc_start = cands[0]
                used_kf.add(j)
                words = kf["lines"][j]["words"]
                shape = shape_for_line(ln, words)
                how = "行匹配"
                # 形状太塌（拉丁单元对不上罗马字）就回退到本地 CTC 形状，
                # **行首仍用 LDDC 的**（行首是本地 CTC 最不可靠、LDDC 最可靠的那一端）。
                if shape is not None and shape_quality(shape) < a.shape_min_quality:
                    loc = local_shape(timing, li)
                    nm = sum(len(u["morae"]) for u in ln["units"] if u["kind"] != "space")
                    if loc is not None and len(loc) == nm and shape_quality(loc) >= a.shape_min_quality:
                        shape = loc
                        how = "行匹配+本地形状"
        if shape is None:
            # 兜底：整曲字符池里定位本行（分句与歌词站不一致时走这里）
            shape = shape_from_pool(ln, pool_chars, pool_times)
            if shape is None:
                miss.append((li, "无对应逐字行（逐行与全局都匹配不上）"))
                continue
            n_pool += 1
            how = "全局池"
            # 全局池给的是**相对**首音拍的时间，LDDC 行首得由本地 CTC 反推
            lddc_start = 0.0
        if lddc_start is None:
            miss.append((li, "逐字行没有绝对时间"))
            continue
        n_mora = sum(len(u["morae"]) for u in ln["units"] if u["kind"] != "space")
        if len(shape) != n_mora:
            miss.append((li, "音拍数不符 %d!=%d" % (len(shape), n_mora)))
            continue
        rows.append(dict(li=li, text=k, shape=shape, lddc_start=lddc_start, how=how,
                         lddc_len=shape[-1] - shape[0] if len(shape) > 1 else 0.0,
                         ctc_start=st[li], ctc_end=line_ends(timing).get(li, st[li])))

    if len(rows) < a.min_lines:
        sys.exit("[align] 可用于估偏移的行只有 %d < %d，不可靠。检查 kf.json 是否抓错版本。"
                 % (len(rows), a.min_lines))

    # ---- 2) 塌缩判定：本地行跨度 / 逐字行跨度 ----
    for r in rows:
        ld = max(0.30, r["lddc_len"] + 0.35)
        r["ratio"] = (r["ctc_end"] - r["ctc_start"]) / ld
        r["collapse"] = r["ratio"] > a.collapse_ratio

    import statistics
    # 偏移 = 本地行首 − 逐字行首，即「这份视频与那份音源差多少」。
    #
    # 关键：这里**用全部行**取中位，不剔除塌缩行。实测（真值 +1.901s 的工程）：
    #   全部 36 行中位 +1.9190（误差 18ms）  ← 用它
    #   剔除塌缩后 24 行 +1.9475（误差 46ms）
    # 原因是塌缩发生在**行尾**（长音/间奏被塞给最后几个音拍），行首那一拍仍是准的；
    # 剔除它们等于白丢 12 个有效样本。中位数本身就能吸收个别被前一行推迟的行首。
    # 只有「行匹配」的行才有真实的 LDDC 行首，能用来估偏移；
    # 「全局池」行的 lddc_start 是占位值，混进来会把偏移整体带偏。
    offrows = [r for r in rows if r["how"] == "行匹配"]
    if len(offrows) < a.min_lines:
        print("[align] 警告：可用真实行首的行只有 %d 行，偏移估计不稳。" % len(offrows))
        offrows = rows
    diffs = [r["ctc_start"] - r["lddc_start"] for r in offrows]
    OFF = statistics.median(diffs)
    sd = statistics.pstdev(diffs) if len(diffs) > 1 else 0.0
    if n_pool:
        print("[align] 其中 %d 行是「逐行匹配不上、用全局字符池兜底」的（不参与估偏移）" % n_pool)
    n_col = sum(1 for r in rows if r["collapse"])
    print("\n[align] 疑似塌缩行 %d / %d（行跨度比 > %.2f；只作提示，不参与剔除）"
          % (n_col, len(rows), a.collapse_ratio))
    print("[align] 全局偏移 = %+.4f s（%d 行取中位，离散 %.3f s）" % (OFF, len(diffs), sd))

    # ---- 2b) 逐行锚点：**全部**用同一个全局偏移 ----
    #
    # 实测(outlier 扫描, 真值 +1.901s 的工程): 全用各行自己的 CTC 行首 MAE 0.2918s,
    # 全用单一全局偏移 MAE 0.0307s  给离群行开小灶反而差 4.5 倍, 因为 CTC 行首的抖动
    # 是全曲性的(每行都不够好), 挑偏离大的行当锚点等于去选最不准的测量值.
    # 完整扫描表与理由: 

    # ---- 2b) 逐行锚点：中位滤波的局部偏移 ----
    # 只用单一全局偏移有个盲点: 前一行 CTC 塌缩会把下一行整体推后(实测行 7 晚 4.24s,
    # 行 8/14 同样偏 3.16/3.35s). 修法 = 对「逐行偏移」序列做中位滤波, 用邻行共识当局部基准;
    # 中位而不是均值: 个别被推后的行不会把邻行一起拖走. 窗长用奇数, 窗 3 不够、窗 5 起有效.
    seq = [r for r in rows if r["how"] == "行匹配"]
    for r in rows:
        r["dev"] = abs(r["ctc_start"] - r["lddc_start"] - OFF)
    # 自适应: 只有抖动确实大时才滤波。判据 = 偏离全局值 > 2s 的行占比:
    # 工程 A(纯抖动, 最大 0.758s) 占 0% -> 不滤波(滤波会自伤 3.5 倍);
    # 工程 B(前句塌缩推移, 最大 4.62s) 占 10% -> 滤波(把 4.6s 纠正掉).
    # 试过 90 分位当判据不行: 工程 A 的 90 分位 0.570s 会被 19% 的少数行抬起来而误触发.
    devs_all = [r["dev"] for r in seq]
    frac_far = (sum(1 for d in devs_all if d > a.medfilt_trigger) / len(devs_all)) if devs_all else 0.0
    spread = max(devs_all) if devs_all else 0.0
    use_filt = a.medfilt > 1 and seq and frac_far >= a.medfilt_frac
    if use_filt:
        res = [r["ctc_start"] - r["lddc_start"] for r in seq]
        h = a.medfilt // 2
        for i, r in enumerate(seq):
            lo, hi = max(0, i - h), min(len(res), i + h + 1)
            r["local_off"] = statistics.median(res[lo:hi])
    print("[align] 逐行偏移：最大偏离 %.3f s，>%.1fs 的行占 %.0f%% → %s"
          % (spread, a.medfilt_trigger, frac_far * 100,
             ("启用中位滤波窗%d（吸收结构性漂移）" % a.medfilt) if use_filt else "不滤波（抖动在正常范围）"))
    for r in rows:
        if r["how"] != "行匹配":
            r["local_off"] = OFF
            r["base"] = r["ctc_start"]
            r["use_local"] = False
            continue
        if r["dev"] > a.outlier:
            # 远超邻行共识：本地行首明显被前一行拖了，优先信逐字源的行首 + 全局偏移
            r["local_off"] = OFF
            r["use_local"] = True
        else:
            r["local_off"] = r.get("local_off", OFF)
            r["use_local"] = False
        r["base"] = r["lddc_start"] + r["local_off"]
    n_local = sum(1 for r in rows if r["use_local"])
    print("[align] 锚定：逐字源行首 + 局部偏移 %d 行；其中 %d 行偏离邻行共识 >%.2fs，已用全局偏移兜底"
          % (sum(1 for r in rows if r["how"] == "行匹配"), n_local, a.outlier))
    for r in rows:
        if r["use_local"]:
            print("   line %2d 本地行首比邻行共识晚 %.2fs（疑前句塌缩推移），已纠正" % (r["li"], r["dev"]))
    # 0.25s 是「本机实测正常工程」的上限（sd=0.315 但融合结果 MAE 0.032s，
    # 因为 CTC 行首本身就有 ~0.3s 抖动，中位数能吸收）。超过 0.8s 才是「不是同一剪辑」的信号。
    if sd > 0.8:
        print("[align] ⚠ 离散 %.2fs 过大：歌词与这份音源可能不是同一剪辑。核对 --source/--song-id。" % sd)
    elif sd > 0.25:
        print("[align] 离散 %.2fs（CTC 行首的固有抖动，中位数可吸收；>0.8s 才需怀疑源不对）" % sd)

    # ---- 3) 组装：pred = 行锚点 + 句内相对形状 ----
    base = {}
    for r in rows:
        base[r["li"]] = r["base"]

    # 行窗口：本行锚点 ~ 下一行锚点（用于夹取，防塌缩行的形状把尾巴甩出去）
    order = sorted(base)
    win = {}
    for i, li in enumerate(order):
        hi = base[order[i + 1]] if i + 1 < len(order) else None
        win[li] = hi

    out, n_clamped, sugg = [], 0, []
    for r in rows:
        li = r["li"]
        s_list = [round(base[li] + d, 3) for d in r["shape"]]
        # 单调 + 窗口夹取
        hi = win.get(li)
        for k in range(len(s_list)):
            if k and s_list[k] < s_list[k - 1]:
                s_list[k] = s_list[k - 1]
            if a.clamp:
                lo_b = base[li] - a.slack
                hi_b = (hi - 0.03) if hi else (r["ctc_end"] + a.slack)
                # 行窗口上界取「下一行锚点」；但锚点是 逐字行首+偏移，当下一行是**副歌里重复出现的
                # 同一句**时，行匹配会吸到更早的那一次（实测 line 30 淀みない…被 line 31 的
                # Like a lotus 锚点吸到 210.53），hi 落到本行之前 → 整行被夹成零长（17 个音拍
                # 全在 227.50-227.80，起音匹配率 0/17）。留一个本地 CTC 跨度的下界把它救回来。
                hi_b = max(hi_b, r["ctc_end"] + a.slack)
                if s_list[k] > hi_b:
                    s_list[k] = round(hi_b, 3); n_clamped += 1
                if s_list[k] < lo_b:
                    s_list[k] = round(lo_b, 3); n_clamped += 1
        if r["collapse"]:
            sugg.append(dict(line=li, ratio=round(r["ratio"], 2), text=r["text"][:24],
                             why="本地跨度是逐字跨度的 %.1f 倍，CTC 在此塌缩" % r["ratio"]))
        for k, (ui, mi, m) in enumerate([(ui, mi, m) for ui, u in enumerate(lines[li]["units"])
                                         if u["kind"] != "space" for mi, m in enumerate(u["morae"])]):
            out.append(dict(line=li, unit=ui, mora=mi, text=m, s=s_list[k], e=None))
    out.sort(key=lambda x: (x["line"], x["unit"], x["mora"]))

    # 终点 = 同句下一个音拍起点；句尾用形状的内源末拍 + 余量
    by = {}
    for m in out:
        by.setdefault(m["line"], []).append(m)
    for li, v in by.items():
        v.sort(key=lambda x: x["s"])
        for i, m in enumerate(v):
            m["e"] = round(v[i + 1]["s"] if i + 1 < len(v) else m["s"] + 0.30, 3)
    out = [m for li in sorted(by) for m in by[li]]

    outp = a.out if os.path.isabs(a.out) else os.path.join(a.project, a.out)
    with open(outp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=0)

    print("\n[align] -> %s（%d 音拍）" % (outp, len(out)))
    print("[align] 夹取 %d 个音拍到行窗口内（--no-clamp 可关）" % n_clamped)
    if miss:
        print("[align] 未用上逐字的行 %d 个：" % len(miss))
        for li, why in miss[:12]:
            print("   line %2d  %s  %s" % (li, why, norm("".join(u["surf"] for u in lines[li]["units"]))[:30]))

    if a.report:
        rp = a.report if os.path.isabs(a.report) else os.path.join(a.project, a.report)
        os.makedirs(os.path.dirname(rp) or ".", exist_ok=True)   # 新工程没有 review/ 目录时自动建
        L = ["# kf 融合报告", "",
             "源: %s (song %s)  |  逐字 %d 行  |  锚点 %s" % (kf.get("source"), kf.get("song_id"),
                                                             len(kf["lines"]), a.auto), "",
             "全局偏移 **%+.4f s**（%d 行中位，离散 %.3f s）" % (OFF, len(diffs), sd), "",
             "## 疑似 CTC 塌缩的行（%d，只作提示）" % len(sugg), "",
             "| 行 | 倍数 | 文本 |", "|---|---|---|"]
        for s in sugg:
            L.append("| %d | %.1f× | %s |" % (s["line"], s["ratio"], s["text"]))
        L += ["", "## 未用上逐字的行（%d）" % len(miss), ""]
        for li, why in miss:
            L.append("- line %d：%s" % (li, why))
        L += ["", "## 逐行偏移（非塌缩行应聚在全局值附近）", "",
              "| 行 | 本地行首 | 减全局偏移 | 倍数 |", "|---|---|---|---|"]
        for r in sorted(rows, key=lambda x: x["li"]):
            L.append("| %d | %.3f | %+.3f | %.2f× |" % (r["li"], r["ctc_start"], r["ctc_start"] - OFF, r["ratio"]))
        with open(rp, "w", encoding="utf-8") as f:
            f.write("\n".join(L) + "\n")
        print("[align] 报告 -> %s" % rp)
    if sugg:
        print("\n[align] 注意：以下行本地 CTC 塌缩，已按句内形状纠正（人工仍应抽看频谱）")
        for s in sugg[:10]:
            print("   line %2d  %.1f×  %s" % (s["line"], s["ratio"], s["text"]))
    return 0
