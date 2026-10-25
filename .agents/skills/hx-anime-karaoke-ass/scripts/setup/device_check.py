#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "numpy",
#   "torch",
#   "transformers",
# ]
# ///
"""实测同一段音频在 GPU 与 CPU 上的对齐差异，回答"默认开 GPU 会不会改变结果"。

背景: device.py 的默认值从 CPU 改成"自动优先 GPU"，理由在实际数据上  但"应该没差"
不是数据。这个脚本给出这个工程真正要看的判据:

  1) logits 的最大绝对差（浮点噪声量级）
  2) 贪心解码后，**每个发音的首次出现帧**在两种设备上的位移
      这才是判决性的量：对齐用的是 CTC 后验的 argmax 边界，
        1 帧 = 20ms。位移 ≤1 帧(<20ms) 视为不影响；>1 帧就老老实实用 CPU 出终稿。

用法:
  hx-karaoke device_check.py --vocals proj/stems/vocals16k.wav --seconds 60
  hx-karaoke device_check.py --vocals ... --lyrics proj/lyrics.txt   # 顺带报每句首字的位移
"""
import argparse, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from ctc.align_ctc import read_wav, MID              # noqa: E402
from setup.device import pick_device, log_device       # noqa: E402


def logits_on(dev, A, mid, threads):
    import torch
    from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor
    torch.set_num_threads(threads)
    proc = Wav2Vec2Processor.from_pretrained(mid)
    model = Wav2Vec2ForCTC.from_pretrained(mid).eval().to(dev)
    with torch.no_grad():
        out = model(proc(A, sampling_rate=16000, return_tensors="pt").input_values.to(dev)).logits[0]
    lp = torch.log_softmax(out, -1).float().cpu().numpy()
    vocab = {v: k for k, v in proc.tokenizer.get_vocab().items()}
    return lp, vocab


def spikes(lp, vocab, blank_id, sep_id):
    """贪心解码 → [(帧号, 字)]，只在标签变化时记一次（与 ctc_read 同口径）。"""
    out, prev = [], -1
    for k in range(lp.shape[0]):
        j = int(lp[k].argmax())
        if j in (blank_id, sep_id):
            prev = j
            continue
        if j != prev:
            out.append((k, vocab.get(j, "?")))
        prev = j
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vocals", required=True)
    ap.add_argument("--seconds", type=float, default=60.0, help="取前 N 秒做对照（0 = 整首）")
    ap.add_argument("--model", default=MID)
    ap.add_argument("--threads", type=int, default=48)
    ap.add_argument("--out", default="")
    a = ap.parse_args()

    if pick_device("") != "cuda":
        sys.exit("本机 CUDA 不可用，无需对照：直接 ASSFX_DEVICE=cpu 跑即可。")
    A = read_wav(a.vocals)
    if a.seconds:
        A = A[:int(a.seconds * 16000)]
    print("[info] 对照片段 %.1fs" % (len(A) / 16000))

    import time
    t0 = time.time(); lp_g, vocab = logits_on("cuda", A, a.model, a.threads); t_gpu = time.time() - t0
    t0 = time.time(); lp_c, _ = logits_on("cpu", A, a.model, a.threads);  t_cpu = time.time() - t0
    print("[time] cuda %.1fs   cpu %.1fs   加速 %.1fx" % (t_gpu, t_cpu, t_cpu / max(t_gpu, 1e-6)))

    n = min(lp_g.shape[0], lp_c.shape[0])
    d = np.abs(lp_g[:n] - lp_c[:n])
    print("[logits] 帧数 %d  最大差 %.4f  平均差 %.5f" % (n, d.max(), d.mean()))
    agree = (lp_g[:n].argmax(-1) == lp_c[:n].argmax(-1)).mean()
    print("[argmax] 逐帧一致率 %.4f%%" % (agree * 100))

    inv = {v: k for k, v in vocab.items()}
    blank, sep = inv.get("[PAD]", 0), inv.get("|", -1)
    sg, sc = spikes(lp_g[:n], vocab, blank, sep), spikes(lp_c[:n], vocab, blank, sep)
    # 对齐两串尖峰（同一模型同一音频，理论上同序；不同序说明设备真的影响了判决）
    m = min(len(sg), len(sc))
    same = sum(1 for i in range(m) if sg[i][1] == sc[i][1])
    print("[spikes] cuda %d 个 / cpu %d 个，前 %d 个里 %d 个同字" % (len(sg), len(sc), m, same))
    if m:
        shifts = np.array([abs(sc[i][0] - sg[i][0]) for i in range(m)]) * 0.02
        print("[spikes] 同序尖峰帧位移: 最大 %.3fs  中位 %.3fs  >1 帧(20ms) 的比例 %.1f%%"
              % (shifts.max(), float(np.median(shifts)), (shifts > 0.02).mean() * 100))
        verdict = "≤1 帧，GPU 可作终稿设备" if shifts.max() <= 0.02 else ">1 帧：终稿请用 ASSFX_DEVICE=cpu 复跑一次"
    else:
        verdict = "没有可比尖峰（片段太静/太短）"
    print("[verdict] " + verdict)
    if a.out:
        json_text = dict(seconds=len(A) / 16000, frames=int(n), logits_max=float(d.max()),
                         argmax_agree=float(agree), spikes_cuda=len(sg), spikes_cpu=len(sc),
                         max_shift_s=float(shifts.max()) if m else None, verdict=verdict,
                         time_gpu=t_gpu, time_cpu=t_cpu)
        import json
        json.dump(json_text, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("-> " + a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
