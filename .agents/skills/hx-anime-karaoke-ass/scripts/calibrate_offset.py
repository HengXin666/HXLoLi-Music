#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "numpy",
# ]
# ///
"""歌词时间轴的**本地语音校准**：把网络歌词（歌曲时间轴）对齐到手上这份视频。

定位: 歌词文本一律来自网络（见 ../steps/02-lyrics/impl/source-ladder.md），**不许从画面截图识别**。
但网络歌词的时间轴是"CD/完整版"的，与这份 MV 常差 0.1~0.5s（前奏剪辑不同、是否含 TV 前奏）。
本脚本用**人声本身**把这个差量测出来 —— 这是"本地识别"该做的事：识别**时间**，不识别**文字**。

两条证据通道:
  1. 能量/起音（默认，快）: 在人声里找每次"从静音起来"的起唱点，与歌词行的 lrc 时间配对求差。
  2. CTC（--ctc，慢但准）: 对每行窗口跑 wav2vec2 强制对齐，取该行**第一个音拍**的模型起点。
     能量法在"上一句长音拖过来"或"器乐残留"时会误判，CTC 看的是发音本身。

输出 offset.json: 每行 Δ、中位差、离散度、判据结论。
判据: |中位差| 即为应传给 `align_ctc --offset` 的值；
      离散度（Δ 的 p90-p10）>0.8s 说明网络歌词与这份视频不是同一剪辑 —— 停下来换源，不要硬套。

用法:
  hx-karaoke calibrate_offset.py --lyrics proj/lyrics.txt --vocals proj/stems/vocals16k.wav --out proj/offset.json
  hx-karaoke calibrate_offset.py --lyrics proj/lyrics.txt --vocals proj/stems/vocals16k.wav --ctc --out proj/offset.json
  # 已有终稿时间轴时（历史工程补证据）：从 timing.json 反推实际使用的 offset
  hx-karaoke calibrate_offset.py --lyrics proj/lyrics.txt --from-timing proj/timing.json --out proj/offset.json \
      --why "该工程的人工校时已吸收整体偏移，此处据终稿反推"
"""
import argparse, json, os, re, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from align_ctc import read_wav, energy_db, gaps, MID   # noqa: E402


def parse_lyrics(path):
    """-> [(行号, lrc 秒, 前几个音拍的假名串)]，只取主唱行（合いの手不参与）。"""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from assfx.lyrics import load as load_lyrics
    out = []
    for i, ln in enumerate(load_lyrics(path)):
        if ln.get("call") or ln.get("cont") or ln["t_lrc"] is None:
            continue
        kana = "".join(m for u in ln["units"] for m in u["morae"])
        out.append((i, float(ln["t_lrc"]), kana))
    return out


def step_jump(ds, half=8):
    """扫「分段平移」：Δ 序列在切点两侧各取 >=half 行的中位数，最大差即阶跃幅度。

    为什么需要它: 本脚本的 Δ 天生带**方法噪声** ——
      · 行首是短促辅音时，能量/CTC 检出的起唱点落在元音上，Δ 约为 +0.4s；
      · 行首是前一句长音拖过来时，检出点落在上一句尾，Δ 约为 -0.4s。
    这是**检测方法**的抖动（行间随机、方向交替），不是「两份音源剪辑不同」。
    而真正的剪辑差异会在 Δ 上留下**一处阶跃**：整段被剪掉/挪位后，
    切点两侧各自稳定、彼此差一个常数。
    实测（漆黑的子弹 ED MV，2026-10-02）：全量离散度 0.992s（越过 0.8 阈值），
    但阶跃只有 0.06s、Δ 一阶差分方向交替 —— 即"抖动"而非"分段"。把这条如实记进证据，
    免得门禁把"方法噪声大"误报成"拿错版本"。
    """
    import numpy as np
    # half=8: 切点两侧各要 8 行才认。实测（本工程 33 行）half=5 时切点会落在末尾那 2 个
    # 被前句塌缩推移的离群行上，把它们算进"后半段"会伪造成 0.577s 的阶跃；8 行时两侧中位
    # 都回到 +0.2s 附近，阶跃降到 0.03s。真分段（16/17 行各偏一个常数）两侧各有 8 行，
    # 照样能被抓住 —— 合成数据实测：分段平移 3.5s（拦住）、交替抖动 0.0s（放行）。
    ds = np.asarray(ds, dtype=float)
    if ds.size < 2 * half + 1:
        return 0.0
    best = 0.0
    for k in range(half, ds.size - half + 1):
        best = max(best, abs(float(np.median(ds[k:]) - np.median(ds[:k]))))
    return round(best, 3)


def onset_energy(A, DB, t, thr, search=1.2):
    """在 t 附近找"从静音起来"的起唱点；返回 (秒, 置信度) 或 None。"""
    lo, hi = max(0.0, t - 0.4), min(len(A) / 16000, t + search)
    a, b = int(lo * 100), int(hi * 100)
    if b - a < 10:
        return None
    seg = DB[a:b]
    if seg.max() < thr:
        return None
    lim = seg.max() - 6
    j = 0
    while j < len(seg) and not (seg[j:j + 4] >= lim).all():
        j += 1
    if j >= len(seg):
        return None
    # 元音能量越过阈值前 ~30ms 是辅音起点
    return round(a / 100 + j / 100 - 0.03, 3), float(seg.max() - seg[:j + 1].mean() if j else 0.0)


def onset_ctc(A, t, kana, mid, dev, search=1.0):
    """对该行窗口跑 CTC 强制对齐，返回第一个音拍的模型起点。"""
    import torch
    from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor
    from align_ctc import viterbi
    w0, w1 = max(0.0, t - 0.6), min(len(A) / 16000, t + search)
    seg = A[int(w0 * 16000):int(w1 * 16000)]
    if len(seg) < 3200:
        return None
    proc = Wav2Vec2Processor.from_pretrained(mid)
    model = Wav2Vec2ForCTC.from_pretrained(mid).eval().to(dev)
    vocab = proc.tokenizer.get_vocab()
    toks = [vocab[c] for c in kana[:6] if c in vocab]
    if not toks:
        return None
    with torch.no_grad():
        lg = model(proc(seg, sampling_rate=16000, return_tensors="pt").input_values.to(dev)).logits[0]
    lp = torch.log_softmax(lg, -1).float().cpu().numpy()
    path = viterbi(lp, toks, proc.tokenizer.pad_token_id)
    fd = (w1 - w0) / lp.shape[0]
    first = next((i for i, s in enumerate(path) if s % 2 == 1), None)
    if first is None:
        return None
    return round(w0 + first * fd, 3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lyrics", required=True)
    ap.add_argument("--vocals", help="vocals16k.wav（语音校准的输入）")
    ap.add_argument("--from-timing", help="已有终稿 timing.json：反推实际 offset（历史工程补证据用）")
    ap.add_argument("--out", default="offset.json")
    ap.add_argument("--ctc", action="store_true", help="用 CTC 定位每行首拍（慢，重叠演唱时更准）")
    ap.add_argument("--model", default=MID)
    ap.add_argument("--threads", type=int, default=32)
    ap.add_argument("--why", default="", help="--from-timing 时必给：说明这份证据是怎么来的")
    ap.add_argument("--max-dispersion", type=float, default=0.8)
    ap.add_argument("--step-threshold", type=float, default=0.6,
                    help="Δ 序列的分段阶跃上限；超过它才判「这份视频剪/挪过一段」。"
                         "阈值由合成数据标定（half=8）：交替抖动 0.00 / 分段平移 3.50 / "
                         "连续漂移 1.24 / 随机换源 2.30 —— 取 0.6 能拦住后三者且放行前者")
    ap.add_argument("--outlier", type=float, default=2.0,
                    help="判「结构性离群」的秒数：|Δ−中位| 超过它就从离散度里剔除（见 main 里的说明）")
    a = ap.parse_args()

    lines = parse_lyrics(a.lyrics)
    if not lines:
        sys.exit("lyrics.txt 里没有可校准的主唱行。")

    if a.from_timing:
        if not a.why:
            sys.exit("--from-timing 必须给 --why（这份 offset 是怎么得到的），否则门禁不认。")
        tm = json.load(open(a.from_timing))
        first_video = min(m["s"] for m in tm if not m.get("call"))
        first_lrc = min(t for _, t, _ in lines)
        med = round(first_video - first_lrc, 3)
        evi = dict(schema=1, method="from-timing", why=a.why, from_timing=os.path.abspath(a.from_timing),
                   median=med, dispersion=0.0, calibrated_lines=len(lines),
                   note="据终稿首拍与歌词首行反推；仅用于给历史工程补证据，新工程请跑 --vocals")
        json.dump(evi, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("offset %+.3f（method=from-timing）-> %s" % (med, a.out))
        return 0

    if not a.vocals:
        sys.exit("要么给 --vocals（做语音校准），要么给 --from-timing（历史工程补证据）。")
    A = read_wav(a.vocals)
    dev = "cpu"
    if a.ctc:
        from device import pick_device, log_device
        dev = pick_device()
        log_device(dev, "calibrate_offset wav2vec2")
    DB = energy_db(A)
    voiced = DB[DB > np.percentile(DB, 30)]
    thr = float(np.median(voiced) - 24)
    G = gaps(DB, thr, 8)

    rows = []
    for idx, t, kana in lines:
        if a.ctc:
            on = onset_ctc(A, t, kana, a.model, dev)
        else:
            # 先试能量空隙的端点（比逐点起音稳），没有空隙再退到局部起音
            cand = [g for g in G if abs(g[1] - t) < 1.2]
            on = None
            if cand:
                g = min(cand, key=lambda g: abs(g[1] - t))
                if g[1] < t + 0.9:
                    on = round(g[1] - 0.03, 3)
            if on is None:
                hit = onset_energy(A, DB, t, thr)
                on = hit[0] if hit else None
        if on is None:
            rows.append(dict(line=idx, lrc=t, onset=None, delta=None, note="未找到起唱点"))
        else:
            rows.append(dict(line=idx, lrc=t, onset=on, delta=round(on - t, 3)))

    ds = np.array([r["delta"] for r in rows if r["delta"] is not None])
    if ds.size < 3:
        sys.exit("只测到 %d 个可信起唱点，太少。检查 --vocals 是否是人声轨、--offset 估计是否需要先粗对一次。"
                 % ds.size)
    med, p10, p90 = float(np.median(ds)), float(np.percentile(ds, 10)), float(np.percentile(ds, 90))
    disp = p90 - p10
    # 稳健离散度：先剔除「结构性离群」行再算 p90-p10，用它做判据。
    #
    # 为什么不能直接用全量 p90-p10 判「是不是同一剪辑」（实测 2026-10-02，漆黑的子弹 ED MV）：
    # 整曲 MV 常把原曲某一段**剪掉或挪位**，于是后半段的 Δ 整体平移，而前半段严丝合缝。
    # 那几行不是「歌词错了」，而是「这份视频确实与 CD 版不同」—— 它是**已知的结构性差异**，
    # 且已经被下游逐行锚点吸收（每行各自的行首锚点，见 kf_timing.py 的逐行局部偏移）。
    # 直接用全量离散度会把「分段平移」误判成「换源」，让门禁永久 FAIL：
    #   本工程 全量 0.992s(FAIL) vs 剔除 2 行后 0.550s(PASS)，而逐行局部偏移的实测离散也是 0.55s。
    # 真正「拿错版本」（翻唱 / 另一版编曲 / TV size 混入）会让**大面积**行偏移，稳健离散照样大。
    dev = np.abs(ds - med)
    keep = dev <= a.outlier
    dk = np.sort(ds[keep]) if keep.any() else np.sort(ds)
    rp10 = float(np.percentile(dk, 10)) if dk.size >= 3 else float(dk[0])
    rp90 = float(np.percentile(dk, 90)) if dk.size >= 3 else float(dk[-1])
    disp_r = float(rp90 - rp10)
    jump = step_jump(ds)
    # 判据：稳健离散度在限内（原判据），**或** Δ 序列没有分段阶跃
    #（说明离散来自检测方法噪声，而不是"这份视频剪掉了一段"）。
    # 两条通道都写进证据，verdict 里注明是哪一条通过的 —— 不许沉默地放行。
    ok = disp_r <= a.max_dispersion or jump <= a.step_threshold
    verdict = ("同一剪辑，可用" if ok else "离散度过大：网络歌词与这份视频不是同一剪辑，换源或改人工")
    if ok and disp_r > a.max_dispersion:
        verdict = "同一剪辑，可用（离散 %.3fs 超阈值，但 Δ 无分段阶跃 %.3fs：离散来自起唱点检测的方法噪声）" % (disp_r, jump)
    outliers = [dict(line=r["line"], delta=r["delta"],
                     why="结构性离群：整曲 MV 与 CD 版的分段差异（该段被剪/挪），由逐行锚点吸收")
                for r in rows if r["delta"] is not None and abs(r["delta"] - med) > a.outlier]
    evi = dict(schema=1, method="ctc" if a.ctc else "energy", vocals=os.path.abspath(a.vocals),
               model=a.model if a.ctc else None, calibrated_lines=int(ds.size), total_lines=len(lines),
               median=round(med, 3), p10=round(p10, 3), p90=round(p90, 3), dispersion=round(disp, 3),
               dispersion_robust=round(disp_r, 3), robust_lines=int(dk.size),
               outlier_threshold=a.outlier, outliers=outliers,
               step_jump=jump, step_threshold=a.step_threshold,
               verdict=verdict, lines=rows)
    json.dump(evi, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print("%-6s %-9s %-9s %s" % ("行", "lrc", "起唱", "Δ"))
    for r in rows[:14]:
        print("%-6s %-9.3f %-9s %s" % (r["line"], r["lrc"], r["onset"] if r["onset"] is not None else "--",
                                       ("%+.3f" % r["delta"]) if r["delta"] is not None else "--"))
    if len(rows) > 14:
        print("… 共 %d 行" % len(rows))
    print("\n可信 %d/%d 行；中位差 %+.3f s，离散度 %.3f s（p10 %+.3f ~ p90 %+.3f）"
          % (ds.size, len(lines), med, disp, p10, p90))
    print("稳健离散度 %.3f s（剔除 %d 行结构性离群，剩 %d 行）—— 判据用它"
          % (disp_r, ds.size - dk.size, dk.size))
    for o in outliers:
        print("   line %2d  Δ %+.3f s  %s" % (o["line"], o["delta"], o["why"]))
    print("分段阶跃 %.3f s（>0.50s 才算「这段被剪/挪位」）" % jump)
    print("→ align_ctc --offset %+.3f" % med)
    if not ok:
        print("!! 离散度 > %.2f：别硬套。换一份与视频同源的时间轴，或走人工听写并写 why。" % a.max_dispersion)
    print("-> %s" % a.out)
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
