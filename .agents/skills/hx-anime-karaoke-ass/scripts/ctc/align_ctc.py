# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "numpy",
#   "torch",
#   "transformers",
# ]
# ///

"""
音拍级强制对齐（CTC Viterbi）：分离人声 + 平假名 wav2vec2 → 每个音拍起止
用法:
  hx-karaoke align_ctc.py --lyrics lyrics.txt --vocals stems/vocals16k.wav --offset 0.05 --out timing_auto.json
  hx-karaoke align_ctc.py ... --estimate-offset        # 只估计 lrc→视频 偏移
流程:
  1) 歌词 lrc 时间 + offset → 视频时间
  2) 人声能量检测“换气空隙”，在空隙处把相邻行切成独立块；连唱（无空隙）的行合并成一个块一起对齐
      避免人为窗口把句尾/句首截断（这是最常见的对齐错误来源）
  3) 每块做 CTC Viterbi，得到每个音拍的起点；终点 = 同句下一个音拍起点 / 句尾按人声能量回落
  4) 输出可疑点清单（过短/过长/与 lrc 偏差大），必须用 review_spectrogram.py 人工复核
依赖: transformers + torch，模型 vumichien/wav2vec2-large-xlsr-japanese-hiragana（输出平假名）
"""
import argparse, json, os, sys, wave
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from assfx.base.lyrics import load

# Agent Notes: 引入 MiliKara 作为注音/对齐来源
# 
# Agent Notes: 引入 MiliKara 作为注音/对齐来源
# .agents/notes/rejected/architecture/2026-10-02-milikara-not-adopted.md
MID = "vumichien/wav2vec2-large-xlsr-japanese-hiragana"


def read_wav(p):
    w = wave.open(p)
    assert w.getframerate() == 16000 and w.getnchannels() == 1, "需要 16k 单声道 wav"
    return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768


def energy_db(a, hop=160, smooth=5):
    n = len(a) // hop
    rms = np.sqrt(np.mean(a[:n * hop].reshape(n, hop) ** 2, axis=1))
    return np.convolve(20 * np.log10(rms + 1e-9), np.ones(smooth) / smooth, "same")


def gaps(db, thr, min_len=8):
    """能量低于 thr 且持续 >= min_len*10ms 的区间（秒）"""
    low = db < thr; out = []; s = None
    for i, v in enumerate(low):
        if v and s is None: s = i
        if not v and s is not None:
            if i - s >= min_len: out.append((s / 100, i / 100))
            s = None
    if s is not None: out.append((s / 100, len(low) / 100))
    return out


def viterbi(lp, toks, blank):
    """向量化 CTC 强制对齐；返回每帧所在状态"""
    T = lp.shape[0]; S = 2 * len(toks) + 1
    lab = np.array([blank if s % 2 == 0 else toks[s // 2] for s in range(S)])
    skip = np.zeros(S, bool)
    for s in range(2, S):
        skip[s] = lab[s] != blank and lab[s] != lab[s - 2]
    NEG = -1e18
    dp = np.full(S, NEG); dp[0] = lp[0, lab[0]]; dp[1] = lp[0, lab[1]]
    bp = np.zeros((T, S), np.int32)
    idx = np.arange(S)
    for t in range(1, T):
        c0 = dp
        c1 = np.concatenate([[NEG], dp[:-1]])
        c2 = np.where(skip, np.concatenate([[NEG, NEG], dp[:-2]]), NEG)
        st = np.stack([c0, c1, c2]); arg = st.argmax(0)
        dp = st[arg, idx] + lp[t, lab]
        bp[t] = idx - arg
    s = S - 1 if dp[S - 1] > dp[S - 2] else S - 2
    path = [s]
    for t in range(T - 1, 0, -1):
        s = bp[t, s]; path.append(s)
    return path[::-1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lyrics", required=True); ap.add_argument("--vocals", required=True)
    ap.add_argument("--offset", type=float, default=0.0); ap.add_argument("--out", default="timing_auto.json")
    ap.add_argument("--thr", type=float, default=None, help="空隙能量阈值 dB，默认=人声中位数-24")
    ap.add_argument("--min-gap", type=float, default=0.08)
    ap.add_argument("--estimate-offset", action="store_true")
    ap.add_argument("--device", default="", help="auto(默认,有卡就用GPU) / cuda / cpu；ASSFX_DEVICE 也可")
    ap.add_argument("--threads", type=int, default=32)
    a = ap.parse_args()

    lines = load(a.lyrics)
    A = read_wav(a.vocals); DB = energy_db(A)
    voiced = DB[DB > np.percentile(DB, 30)]
    thr = a.thr if a.thr is not None else float(np.median(voiced) - 24)
    G = gaps(DB, thr, int(a.min_gap * 100))
    print(f"[info] 空隙阈值 {thr:.1f} dB，找到 {len(G)} 个空隙")

    # 偏移估计：每行 lrc 时间附近找“空隙结束=起唱”点
    onsets = [g[1] for g in G]
    if a.estimate_offset:
        cands = []
        for ln in lines:
            t = ln["t_lrc"]
            if t is None: continue
            near = [o - t for o in onsets if abs(o - t - a.offset) < 1.5]
            if near: cands.append(min(near, key=lambda d: abs(d - a.offset)))
        print("[offset] 各行起唱-lrc 差值:", " ".join(f"{c:+.2f}" for c in cands))
        print(f"[offset] 中位数建议 offset = {np.median(cands):+.3f}")
        return

    import torch
    from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor
    torch.set_num_threads(a.threads)
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from setup.device import pick_device, log_device, warmup
    DEV = pick_device(a.device)
    log_device(DEV, "align_ctc wav2vec2")
    warmup(DEV)
    proc = Wav2Vec2Processor.from_pretrained(MID); model = Wav2Vec2ForCTC.from_pretrained(MID).eval().to(DEV)
    vocab = proc.tokenizer.get_vocab(); BLANK = proc.tokenizer.pad_token_id

    T = [ln["t_lrc"] + a.offset if ln["t_lrc"] is not None else None for ln in lines]
    # 缺时间的行：插值
    for i, t in enumerate(T):
        if t is None:
            T[i] = (T[i - 1] + (T[i + 1] if i + 1 < len(T) and T[i + 1] else T[i - 1] + 4)) / 2
    # 每行都切：优先用 [t-0.9, t+0.35] 内离 t 最近的换气空隙；没有空隙（连唱）就取该区间人声能量最低点
    MAIN = [i for i, ln in enumerate(lines) if not ln.get("call")]
    prev_main = {i: max([j for j in MAIN if j < i], default=None) for i in MAIN}

    def cut_at(i):
        tp = T[prev_main[i]] if prev_main[i] is not None else T[i] - 5
        cand = [g for g in G if g[1] > T[i] - 0.9 and g[0] < T[i] + 0.35 and g[0] > tp + 0.3]
        if cand:
            g = min(cand, key=lambda g: abs((g[0] + g[1]) / 2 - T[i]))
            return (g[0], g[1], "gap")
        lo, hi = int((T[i] - 0.9) * 100), int((T[i] + 0.25) * 100)
        j = lo + int(np.argmin(DB[lo:hi])); return (j / 100 - 0.03, j / 100 + 0.03, "min")
    cut = {i: (cut_at(i) if prev_main[i] is not None else None) for i in MAIN}
    blocks = []
    for i in MAIN:
        if lines[i].get("cont") and blocks:
            blocks[-1].append(i)          # 拆显示的后续段：与前段同块对齐
        else:
            blocks.append([i])
    result, report = [], []
    for bi, blk in enumerate(blocks):
        g0 = cut[blk[0]]
        w0 = max(0, (g0[1] - (0.25 if g0[2] == "gap" else 0.12)) if g0 else T[blk[0]] - 0.6)
        nxt = blocks[bi + 1][0] if bi + 1 < len(blocks) else None
        if nxt is not None:
            g1 = cut[nxt]; w1 = min(g1[0] + 0.25, g1[1]) if g1[2] == "gap" else g1[0] + 0.12
        else:
            w1 = min(len(A) / 16000, T[blk[-1]] + 12)
        mor = []
        for li in blk:
            for ui, u in enumerate(lines[li]["units"]):
                for mi, m in enumerate(u["morae"]):
                    mor.append((li, ui, mi, m))
        toks, owner = [], []
        for k, (_, _, _, m) in enumerate(mor):
            for ch in m:
                if ch not in vocab:
                    print(f"[warn] 字符 {ch} 不在模型词表，跳过"); continue
                toks.append(vocab[ch]); owner.append(k)
        seg = A[int(w0 * 16000):int(w1 * 16000)]
        with torch.no_grad():
            lg = model(proc(seg, sampling_rate=16000, return_tensors="pt").input_values.to(DEV)).logits[0]
        lp = torch.log_softmax(lg, -1).detach().cpu().numpy(); fd = (w1 - w0) / lp.shape[0]
        path = viterbi(lp, toks, BLANK)
        st = [None] * len(mor)
        for t, s in enumerate(path):
            if s % 2 == 1:
                k = owner[s // 2]
                if st[k] is None: st[k] = w0 + t * fd
        for k in range(len(mor)):
            if st[k] is None: st[k] = st[k - 1] + 0.05 if k else w0
        for k, (li, ui, mi, m) in enumerate(mor):
            result.append(dict(line=li, unit=ui, mora=mi, text=m, s=round(st[k], 3), e=None))
        print(f"[line {blk[0]:2d}] {w0:7.2f}-{w1:7.2f} cut={cut[blk[0]][2] if cut[blk[0]] else '-'}")
    # 合いの手：默认从 lrc 时间起每拍(0.333s 上限)一个音，之后用 fixes.json 精修
    for li, ln in enumerate(lines):
        if not ln.get("call"): continue
        ms = [(ui, mi, m) for ui, u in enumerate(ln["units"]) for mi, m in enumerate(u["morae"])]
        step = 0.333 if len(ms) <= 8 else 0.167
        for k, (ui, mi, m) in enumerate(ms):
            result.append(dict(line=li, unit=ui, mora=mi, text=m, s=round(T[li] + k * step, 3), e=None, call=True))

    finalize(result, DB, len(A) / 16000)
    json.dump(result, open(a.out, "w"), ensure_ascii=False, indent=0)
    # 可疑点
    for li in MAIN:
        ms = [m for m in result if m["line"] == li]
        if not lines[li].get("cont") and abs(ms[0]["s"] - T[li]) > 0.6:
            report.append(f"line {li}: 首拍 {ms[0]['s']:.2f} 与 lrc {T[li]:.2f} 相差 {ms[0]['s']-T[li]:+.2f}s")
        for j, m in enumerate(ms[:-1]):
            d = m["e"] - m["s"]
            if d < 0.07: report.append(f"line {li}: 「{m['text']}」@{m['s']:.2f} 过短 {d*1000:.0f}ms")
            if d > 2.5: report.append(f"line {li}: 「{m['text']}」@{m['s']:.2f} 过长 {d:.2f}s")
    print("\n[review] 需复核:" if report else "\n[review] 无自动可疑点（仍建议抽查频谱）")
    for r in report: print("  -", r)


def finalize(result, DB, dur, thr=-40):
    """重算终点。call（合いの手）与主唱分开处理：主唱序列单调，call 自成一轨（终点=同句下一音或 +0.3s）"""
    calls = sorted([m for m in result if m.get("call")], key=lambda m: m["s"])
    main_ = sorted([m for m in result if not m.get("call")], key=lambda m: m["s"])
    for i, m in enumerate(calls):
        nx = calls[i + 1] if i + 1 < len(calls) and calls[i + 1]["line"] == m["line"] else None
        m["e"] = round(nx["s"] if nx else m["s"] + 0.3, 3); m["s"] = round(m["s"], 3)
    result[:] = main_ + calls
    for i, m in enumerate(main_):
        nxt = main_[i + 1] if i + 1 < len(main_) else None
        if nxt and nxt["line"] == m["line"]:
            m["e"] = nxt["s"]
        else:
            lim = nxt["s"] if nxt else dur
            j = int((m["s"] + 0.2) * 100)
            while j < int(lim * 100) and j < len(DB) and DB[j] > thr: j += 1
            m["e"] = round(min(j / 100, lim), 3)
        m["s"] = round(m["s"], 3); m["e"] = round(m["e"], 3)


if __name__ == "__main__":
    main()
