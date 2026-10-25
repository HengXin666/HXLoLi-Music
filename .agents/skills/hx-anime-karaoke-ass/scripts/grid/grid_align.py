# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "numpy",
#   "scipy",
#   "torch",
#   "transformers",
# ]
# ///

"""
网格约束重对齐（快歌/齐唱专用）：每个音拍的起点只能落在节拍细分网格上，
用 CTC 发音尖峰做证据、原对齐做先验，动态规划求整句最优排布。

为什么需要：CTC 自由对齐在齐唱/快歌里常把没“听清”的几个音挤在 1~2 帧（过短 20ms），
或整段漂移。流行歌几乎所有音拍都落在 8/16 分网格上，把搜索空间限制在网格槽位后：
  * 不会再有 <1 槽的挤压（最短 = 1 个 16 分音符）
  * 没尖峰的音（っ、ー、弱辅音）由前后有证据的音夹住，按节奏先验落位
用法:
  hx-karaoke grid_align.py --lyrics lyrics.txt --vocals stems/vocals16k.wav --timing timing_auto.json \
      --grid grid.json --div 8 --lag 0.03 --out timing_grid.json [--emis stems/ctc_lp.npz] [--anchors fixes.json]
  --div：每个 grid period 的细分数（beat_grid 把 180BPM 测成 90BPM 时，16 分音符 = div 8）
  --anchors：fixes.json 中的人工起点当作硬约束（该音拍只能在其最近的槽位）
输出与 align_ctc 相同格式；随后照常 apply_fixes → check_sync → review_spectrogram 复核。
"""
import argparse, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from ctc.align_ctc import read_wav, energy_db, finalize
from ctc.emis import SMALL, VOWEL, emissions, similarity
from grid.beat_grid import grid_lines
from assfx.base.lyrics import load

def main():
    """Agent Notes
    .agents/notes/implemented/process/2026-10-01-karaoke-gpu-default-auto.md
    """
    ap = argparse.ArgumentParser()
    ap.add_argument("--lyrics", required=True); ap.add_argument("--vocals", required=True)
    ap.add_argument("--timing", required=True, help="先验（align_ctc 输出）")
    ap.add_argument("--grid", required=True); ap.add_argument("--div", type=int, default=4)
    ap.add_argument("--lag", type=float, default=None, help="音拍起点相对网格的偏移；默认按 CTC 尖峰自动估计")
    ap.add_argument("--out", required=True)
    ap.add_argument("--emis"); ap.add_argument("--anchors")
    ap.add_argument("--prior-tol", type=float, default=0.25, help="偏离先验超过此值开始罚分")
    ap.add_argument("--prior-w", type=float, default=4.0, help="每偏离 1s 的罚分")
    ap.add_argument("--max-gap", type=float, default=2.5, help="相邻音拍最大间隔（秒）")
    ap.add_argument("--even-bonus", type=float, default=0.3, help="落在 8 分音符位置的加分（div/2 网格）")
    ap.add_argument("--parity", help="歌词相同的重复段联合对齐，如 15:47,16:48（块首行号）")
    ap.add_argument("--lines", help="只重排这些行，如 9-11,30-32（其余保持原样）")
    ap.add_argument("--device", default="", help="auto(默认,有卡就用GPU) / cuda / cpu；ASSFX_DEVICE 也可")
    a = ap.parse_args()

    lines = load(a.lyrics)
    prior = json.load(open(a.timing))
    P = {(m["line"], m["unit"], m["mora"]): m for m in prior}
    # Agent Notes: 卡拉OK 字幕链默认改用 GPU，可复现性降级为可验证开关
    # 
    lp, fd, vocab = emissions(a.vocals, a.emis, prefer=a.device)
    VI = {v: i for i, v in enumerate(vocab)}
    G = json.load(open(a.grid))
    blank = VI.get("[PAD]", VI.get("<pad>", 0)); sep = VI.get("|", -1)
    if a.lag is None:
        # 自动估计：高置信尖峰（首帧、logp>-0.3）相对最近网格线的偏移（圆周中位数）
        am = lp.argmax(1); mx = lp.max(1); ph = []
        for f in range(1, len(am)):
            if am[f] not in (blank, sep) and am[f] != am[f - 1] and mx[f] > -0.3:
                t = f * fd; gl = grid_lines(G, t - 0.3, t + 0.3, a.div)
                if gl:
                    ph.append(min((t - g[0] for g in gl), key=abs))
        a.lag = round(float(np.median(ph)), 3) if ph else 0.03
        print(f"[lag] 自动估计 {a.lag:+.3f}s（{len(ph)} 个尖峰）")
    anchors = {}
    if a.anchors and os.path.exists(a.anchors):
        anchors = {tuple(map(int, k.split(","))): float(v) for k, v in json.load(open(a.anchors)).items() if not k.startswith("_")}
    sel = None
    if a.lines:
        sel = set()
        for r in a.lines.split(","):
            x, _, y = r.partition("-"); sel |= set(range(int(x), int(y or x) + 1))

    # 主唱块（与 align_ctc 相同：cont 并入前块；call 跳过）
    blocks = []
    for i, ln in enumerate(lines):
        if ln.get("call"):
            continue
        if ln.get("cont") and blocks:
            blocks[-1].append(i)
        else:
            blocks.append([i])

    # 听到的音拍：贪心解码的 token 起始帧；小写假名并入前一个字（ぎ+ゅ → ぎゅ）
    am = lp.argmax(1); mx = lp.max(1); HEARD = []
    for f in range(len(am)):
        tok = vocab[am[f]]
        if am[f] in (blank, sep) or (f and am[f] == am[f - 1]):
            continue
        if tok in SMALL and HEARD and f * fd - HEARD[-1][0] < 0.1:
            HEARD[-1] = (HEARD[-1][0], HEARD[-1][1] + tok, HEARD[-1][2]); continue
        HEARD.append((f * fd, tok, float(mx[f])))

    def tok_score(ch, f0, f1):
        """ch 在帧区间 [f0,f1) 内的最大对数后验（尖峰证据）"""
        if ch not in VI:
            return None
        f0 = max(0, f0); f1 = min(len(lp), max(f0 + 1, f1))
        return float(lp[f0:f1, VI[ch]].max())

    out = {k: dict(v) for k, v in P.items()}
    HT = np.array([h[0] for h in HEARD]) if HEARD else np.zeros(0)
    SLOT = None

    def prep(bi):
        blk = blocks[bi]
        keys = [(li, ui, mi) for li in blk for ui, u in enumerate(lines[li]["units"]) for mi, _ in enumerate(u["morae"])]
        keys = [k for k in keys if k in P]
        if not keys:
            return None
        texts = [P[k]["text"] for k in keys]
        pri = np.array([P[k]["s"] for k in keys])
        # 窗口：前一块已定的最后起点 ~ 下一块先验起点
        prev_end = max([out[k]["s"] for k in out if k[0] < blk[0] and not out[k].get("call")], default=0) + 0.06
        nxt_blk = blocks[bi + 1] if bi + 1 < len(blocks) else None
        nxt_s = min([P[k]["s"] for k in P if nxt_blk and k[0] == nxt_blk[0]], default=pri[-1] + 3)
        w0 = max(prev_end, pri[0] - 0.6); w1 = nxt_s - 0.06
        slots = np.array([g[0] + a.lag for g in grid_lines(G, w0 - 0.3, w1 + 0.3, a.div) if w0 <= g[0] + a.lag < w1])
        return dict(blk=blk, keys=keys, texts=texts, pri=pri, w0=w0, w1=w1, slots=slots)

    def evid(B, slots):
        """证据矩阵 E[k,j]：槽位 ±0.08s 内“听到的音拍”与歌词音拍的相似度（一致 0 / 同字差浊点 -0.4 /
        同元音 -0.8 / 同辅音 -1.2 / 其他 -2.2）减距离罚分；附近什么都没听到 = -4；
        ー/っ/非假名 无独立证据 → 贴近先验。另加 8 分音符位置加分、偏离先验罚分、锚点硬约束"""
        texts, pri, keys = B["texts"], B["pri"], B["keys"]
        K, J = len(texts), len(slots)
        slot_dt = float(np.median(np.diff(slots))) if J > 1 else 0.083
        E = np.zeros((K, J))
        for k, tx in enumerate(texts):
            if tx[0] in "ーっ" or tx[0] not in VOWEL and tx[0] != "ん":
                E[k] = -1.5 - 2.0 * np.abs(slots - pri[k]); continue
            for j, t in enumerate(slots):
                lo, hi = np.searchsorted(HT, t - 0.08), np.searchsorted(HT, t + 0.08)
                best = -4.0
                for th, hx, conf in HEARD[lo:hi]:
                    best = max(best, similarity(tx, hx) + min(0.0, conf) * 0.2 - ((th - t) / 0.05) ** 2)
                E[k, j] = best
        if a.even_bonus:
            ph = np.array([min((t - a.lag - g[0] for g in grid_lines(G, t - 0.4, t + 0.4, a.div // 2)), key=abs) for t in slots])
            E += np.where(np.abs(ph) < slot_dt / 3, a.even_bonus, 0.0)[None, :]
        for k in range(K):
            E[k] -= a.prior_w * np.clip(np.abs(slots - pri[k]) - a.prior_tol, 0, None)
            if keys[k] in anchors:
                ja = int(np.argmin(np.abs(slots - anchors[keys[k]])))
                E[k] = -1e6; E[k, ja] = 0.0
        return E

    def dp(E, slot_dt):
        K, J = E.shape
        maxg = max(2, int(round(a.max_gap / slot_dt)))
        D = np.full((K, J), -1e9); Bk = np.zeros((K, J), int)
        D[0] = E[0]
        for k in range(1, K):
            for j in range(k, J):
                lo = max(0, j - maxg)
                cand = D[k - 1, lo:j]
                if cand.size == 0:
                    continue
                gap = j - np.arange(lo, j)
                # 节奏先验：1~4 槽免罚；更长的间隔轻罚（长音/休止都可能）
                v = cand - np.where(gap <= 4, 0.0, 0.08 * (gap - 4) ** 0.7)
                b = int(np.argmax(v)); D[k, j] = E[k, j] + v[b]; Bk[k, j] = lo + b
        j = int(np.argmax(D[K - 1])); score = float(D[K - 1, j]); path = [j]
        for k in range(K - 1, 0, -1):
            j = Bk[k, j]; path.append(j)
        return path[::-1], score

    def commit(B, slots, path, E, tag=""):
        nonlocal_moved = 0
        for k, j in zip(B["keys"], path):
            t = round(float(slots[j]), 3)
            if abs(out[k]["s"] - t) > 0.04:
                nonlocal_moved += 1
            out[k]["s"] = t
        blk = B["blk"]
        print(f"[block {blk[0]:2d}{'+' if len(blk) > 1 else ' '}] {B['w0']:7.2f}-{B['w1']:7.2f} 槽 {len(slots):3d} 音 {len(B['keys']):3d} "
              f"平均证据 {np.mean([E[k, j] for k, j in enumerate(path)]):.2f} {tag}")
        return nonlocal_moved

    # 副歌联合：--parity 15:47,16:48 → 两块歌词相同，节奏相同；证据相加后一起求解（偏移在先验差 ±3 槽内搜索）
    pairs = {}
    if a.parity:
        for pr in a.parity.split(","):
            x, y = map(int, pr.split(":"))
            pairs[x] = y
    first_of = {blk[0]: bi for bi, blk in enumerate(blocks)}
    done = set(); n_moved = 0
    for bi, blk in enumerate(blocks):
        if sel is not None and not (set(blk) & sel) or blk[0] in done:
            continue
        B = prep(bi)
        if B is None:
            continue
        slots = B["slots"]; K, J = len(B["keys"]), len(slots)
        if J < K:
            print(f"[skip] block {blk}: 槽位 {J} < 音拍 {K}"); continue
        slot_dt = float(np.median(np.diff(slots))) if J > 1 else 0.083
        E = evid(B, slots)
        y = pairs.get(blk[0])
        if y is not None and y in first_of:
            B2 = prep(first_of[y])
            if B2 and B2["texts"] == B["texts"]:
                base = round((B2["pri"][0] - B["pri"][0]) / slot_dt)
                best = None
                for m in range(-3, 4):
                    # 第二遍的槽位 = 第一遍槽位 + 整数个槽（同一网格）
                    g2 = np.array([g[0] + a.lag for g in grid_lines(G, slots[0] + (base + m) * slot_dt - 0.3,
                                                                    slots[-1] + (base + m) * slot_dt + 0.3, a.div)])
                    s2 = np.array([g2[np.argmin(np.abs(g2 - (t + (base + m) * slot_dt)))] for t in slots])
                    E2 = evid(B2, s2)
                    path, sc = dp(E + E2, slot_dt)
                    if best is None or sc > best[1]:
                        best = (path, sc, s2, E2, m)
                path, sc, s2, E2, m = best
                n_moved += commit(B, slots, path, E, f"⇄ 与 {y} 联合")
                n_moved += commit(B2, s2, path, E2, f"⇄ 与 {blk[0]} 联合（偏移 {s2[0]-slots[0]:+.2f}s）")
                done.add(y)
                continue
            print(f"[parity] {blk[0]}:{y} 歌词音拍不一致，单独对齐")
        path, sc = dp(E, slot_dt)
        n_moved += commit(B, slots, path, E)
    res = list(out.values())
    A = read_wav(a.vocals); DB = energy_db(A)
    finalize(res, DB, len(A) / 16000)
    json.dump(res, open(a.out, "w"), ensure_ascii=False, indent=0)
    print(f"重排 {n_moved} 个音拍 → {a.out}")


if __name__ == "__main__":
    main()
