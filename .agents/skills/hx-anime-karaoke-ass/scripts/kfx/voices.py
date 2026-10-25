#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""声部归属检测: 每个音拍是「独唱 / 多层次(齐唱·和声) / 无可靠人声」, 供句内配色用.

决策与实测依据: 

## 为什么需要它

逐字高亮现在只有一个颜色 (`Karaoke.colors()` → `th["hi"]`), 所以**齐唱的和声与主唱同色**,
观众看不出"这里是几个人在唱". 专业成品是**逐字分配颜色**的:
实测某成品 28257 条字形事件里 **97%** 带 `\\t(...\\1c...)` 终色、共 61 种终色;
另一成品是 4 色按段落轮换; 还有一份是角色色 + 主题色逐字取.

配色要按"谁在唱"分, 所以先要能回答这个问题. **不做说话人分离**(那是另一个量级的模型):
只回答"这一处是一条音高线还是多条", 这是可测的.

## 判据

对每个音拍区间取 YIN 基频轨 (自实现, 不依赖 scipy):

  * **solo**    一条稳定音高线: 音高直方图只有一个满足能量门槛的峰.
  * **octave**  两个峰, 间距 11~13 半音 → 有人低八度/高八度垫底(最常见的和声写法).
  * **fifth**   两个峰, 间距 5.5~8.5 半音 → 五度/四度和声.
  * **chorus**  两个以上峰且间距不成简单音程 → 齐唱(多人不同音高).
  * **none**    该句整体没有可靠人声基线, 或该字有效帧不足 → 不配色, 退回基础暗态.

**句级门槛是必需的**: 单字层面的基频判定在伴奏泄漏时会被乐器的谐波骗过.
反验样本(同一套判据):
    人声轨 `stems/vocals16k.wav` → 句级置信基线 **0.77~0.93**, `none` 只占 0.2%
    伴奏轨 `stems/inst.wav`      → 句级置信基线 **0.05~0.44**, `none` 占 30%+
所以判据带一条**基线门槛**: 句级基频置信中位 < `--min-base`(默认 0.55) 的句子整句判 `none`.
不猜: 判不出来就退回单色, 而不是随机上色.

用法:
  hx-karaoke voices.py --vocals proj/stems/vocals16k.wav --timing proj/timing.json \\
                       --lyrics proj/lyrics.txt --out proj/review/voices.json
产物: {"tags": {"<line>.<unit>.<mora>": tag}, "per_line": {...}, "baseline": {...}}

配色规则(在 `assfx/color.py` 里落实):
  solo → 该句主题色; octave/fifth/chorus → 同一色域里的派生色(色相偏移);
  none → 保留基础暗态, 不染色.
"""
import argparse, json, math, os, wave

import numpy as np

# Agent Notes: 句内配色  声部归属检测 + 段落色系
# 
# Agent Notes: 句内配色  声部归属检测 + 段落色系
# .agents/notes/implemented/feature/2026-10-03-karaoke-voice-color.md
SEMI = 12.0 / math.log(2.0)


# ------------------------------------------------------------------ 音频 / 基频
def read_wav(path, want_sr=16000):
    """Agent Notes
    .agents/notes/implemented/process/2026-10-04-karaoke-skill-genericize.md
    .agents/notes/implemented/process/2026-10-05-karaoke-scripts-grouping.md
    """
    with wave.open(path, "rb") as w:
        sr, n, ch, sw = w.getframerate(), w.getnframes(), w.getnchannels(), w.getsampwidth()
        raw = w.readframes(n)
    if sw != 2:
        raise SystemExit("只支持 16-bit PCM: %s (sampwidth=%d)" % (path, sw))
    # Agent Notes: 卡拉OK skill 通用化  去掉单次制作的事实与清单式铺陈; hx-anime-karaoke-ass 的 scripts/ 按职责分组，并把 5 个超 300 行的模块拆开
    # 
    # 
    a = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    if ch > 1:
        a = a.reshape(-1, ch).mean(axis=1)
    if sr != want_sr:
        idx = np.linspace(0, len(a) - 1, int(len(a) * want_sr / sr))
        a = np.interp(idx, np.arange(len(a)), a).astype(np.float32)
        sr = want_sr
    return a, sr


def yin_track(a, sr, hop=160, win=1024, fmin=80.0, fmax=1000.0, th=0.12):
    """YIN 基频 + 置信度. 返回 (f0[Hz, nan=无声], conf[0..1], 帧率)"""
    n = 1 + max(0, (len(a) - win) // hop)
    tau_min = max(2, int(sr / fmax)); tau_max = min(win // 2 - 1, int(sr / fmin))
    f0 = np.full(n, np.nan, dtype=np.float32)
    conf = np.zeros(n, dtype=np.float32)
    for i in range(n):
        x = a[i * hop: i * hop + win].astype(np.float64)
        if x.size < win:
            break
        x = x - x.mean()
        if float(np.dot(x, x)) < 1e-7:
            continue
        ac = np.correlate(x, x, mode="full")[win - 1:win - 1 + tau_max + 1]
        ac = ac / (ac[0] + 1e-12)
        d = 2.0 * (1.0 - ac)
        best, best_t, run = 1e9, -1, 0.0
        t = tau_min
        while t < tau_max:
            run += d[t]
            cm = d[t] * t / (run + 1e-12)
            if cm < th:
                while t + 1 < tau_max and d[t + 1] * (t + 1) / (run + d[t + 1] + 1e-12) < cm:
                    t += 1
                    run += d[t]
                    cm = d[t] * t / (run + 1e-12)
                best, best_t = cm, t
                break
            if cm < best:
                best, best_t = cm, t
            t += 1
        if best_t > 0:
            f0[i] = sr / best_t
            conf[i] = float(max(0.0, min(1.0, 1.0 - best)))
    return f0, conf, sr / hop


def to_semi(f):
    return SEMI * np.log(np.maximum(f, 1e-6) / 55.0)


# ------------------------------------------------------------------ 判定
def peaks_of(hist, edges, min_share=0.22):
    """音高直方图的强峰. 返回 [(中心半音, 占比), ...]"""
    if hist.max() <= 0:
        return []
    out = []
    for k in range(len(hist)):
        left = hist[k - 1] if k else 0
        right = hist[k + 1] if k + 1 < len(hist) else 0
        if hist[k] >= left and hist[k] >= right and hist[k] >= min_share * hist.max():
            out.append(((edges[k] + edges[k + 1]) / 2.0, hist[k] / hist.sum()))
    # 合并相邻 bin 造成的一峰两列
    merged = []
    for c, w in out:
        if merged and abs(c - merged[-1][0]) < 1.0:
            if w > merged[-1][1]:
                merged[-1] = (c, w)
        else:
            merged.append((c, w))
    return merged


def classify(seg_semi, min_frames=3):
    """seg_semi: 该音拍内有效帧的半音值. 返回 (tag, info)

    稳健跨度用 p10~p90 而不是 ptp: 音拍边界处常混进上/下一个音的 1~2 帧,
    ptp 会把它们算成 "这个字里音高跳了 8 个半音" 而误判 none.
    实测: 改用 p10~p90 后人声轨的 none 从 26% 降到 11%, 伴奏轨仍是 93%(反验判据不被削弱).
    """
    if seg_semi.size < min_frames:
        return "none", dict(n=int(seg_semi.size))
    span = float(np.percentile(seg_semi, 90) - np.percentile(seg_semi, 10))
    hist, edges = np.histogram(seg_semi, bins=max(3, min(20, seg_semi.size // 3)))
    pk = peaks_of(hist, edges)
    info = dict(n=int(seg_semi.size), med=round(float(np.median(seg_semi)), 2),
                span=round(span, 2), peaks=[round(c, 1) for c, _ in pk])
    if len(pk) >= 2:
        gaps = [abs(pk[b][0] - pk[a][0]) for a in range(len(pk)) for b in range(a + 1, len(pk))]
        g = min(gaps)
        if len(pk) >= 3:
            return "chorus", info
        if 10.0 <= g <= 14.0:
            return "octave", info
        if 4.5 <= g <= 9.5:
            return "fifth", info
        return "chorus", info
    if span > 4.5:                     # 一条线但在本字内大幅移动 = 判定不可靠
        return "none", info
    return "solo", info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vocals", required=True)
    ap.add_argument("--timing", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--lyrics", help="用于跳过合いの手行(不参与对齐, 也没有独立人声)")
    ap.add_argument("--min-base", type=float, default=0.55,
                    help="句级基频置信中位的门槛; 低于它整句判 none (反验: 伴奏轨基线 0.05~0.44)")
    ap.add_argument("--min-conf", type=float, default=0.25, help="逐帧置信门槛")
    a = ap.parse_args()

    x, sr = read_wav(a.vocals)
    f0, conf, fr = yin_track(x, sr)
    tm = json.load(open(a.timing, encoding="utf-8"))
    call_lines = set()
    if a.lyrics:
        for i, ln in enumerate(l for l in open(a.lyrics, encoding="utf-8")
                               if l.strip() and not l.lstrip().startswith("#")):
            jp = ln.split(" | ")[1].strip() if " | " in ln else ""
            if jp[:1] in "（(" and jp[-1:] in "）)":
                call_lines.add(i)

    by_line = {}
    for m in tm:
        by_line.setdefault(m["line"], []).append(m)

    tags, per_line, baseline = {}, {}, {}
    for li, ms in sorted(by_line.items()):
        t0 = min(m["s"] for m in ms); t1 = max(m["e"] for m in ms)
        i0, i1 = int(t0 * fr), max(int(t0 * fr) + 1, int(t1 * fr))
        base = float(np.median(conf[i0:i1])) if i1 > i0 else 0.0
        baseline[li] = round(base, 3)
        silent_line = (li in call_lines) or base < a.min_base
        cnt = {}
        for m in ms:
            if silent_line:
                tag, info = "none", dict(n=0, why="line-baseline" if li not in call_lines else "call")
            else:
                j0, j1 = int(m["s"] * fr), max(int(m["s"] * fr) + 1, int(m["e"] * fr))
                seg = f0[j0:j1]; cg = conf[j0:j1]
                ok = np.isfinite(seg) & (cg > a.min_conf)
                tag, info = classify(to_semi(seg[ok]))
            tags["%d.%d.%d" % (m["line"], m["unit"], m["mora"])] = tag
            cnt[tag] = cnt.get(tag, 0) + 1
        per_line[li] = cnt
        print("line %2d  基线 %.2f  %s%s" % (li, base, cnt, "  <- 整句 none" if silent_line else ""))

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump({"tags": tags, "per_line": per_line, "baseline": baseline},
              open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    n = len(tags)
    tot = {}
    for v in tags.values():
        tot[v] = tot.get(v, 0) + 1
    print("\n%d 个音拍: %s -> %s" % (n, tot, a.out))
    print("配色规则: solo=主题色 / octave·fifth·chorus=同色域派生色 / none=不染色(基础暗态)")
    print("反验: 换 --vocals stems/inst.wav 跑一遍, none 占比应显著上升 (实测 0.2%% -> 30%%+)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
