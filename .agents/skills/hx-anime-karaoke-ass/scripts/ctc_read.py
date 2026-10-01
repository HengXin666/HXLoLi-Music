# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "numpy",
#   "torch",
#   "transformers",
# ]
# ///

# 缓存整首 CTC 后验（与 grid_align --emis 同格式）；打印指定区间“模型听到的”假名及时间（贪心 + 次优）
# 用法: uv run ctc_read.py stems/vocals16k.wav stems/ctc_lp.npz 80.0-82.5 85.5-87.0
import sys, os, json, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from align_ctc import read_wav, MID
def emissions(wav, cache):
    if os.path.exists(cache):
        z = np.load(cache, allow_pickle=True); return z["lp"], float(z["fd"]), list(z["vocab"])
    import torch
    from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor
    torch.set_num_threads(48)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from device import pick_device, log_device, warmup
    DEV = pick_device(os.environ.get("ASSFX_DEVICE", ""))
    log_device(DEV, "ctc_read wav2vec2")
    warmup(DEV)
    proc = Wav2Vec2Processor.from_pretrained(MID); model = Wav2Vec2ForCTC.from_pretrained(MID).eval().to(DEV)
    A = read_wav(wav); sr = 16000; CH, OV = 16.0, 1.0
    fd = 0.02; n = int(len(A) / sr / fd) + 1
    V = model.config.vocab_size; lp = np.full((n, V), -30.0, np.float32)
    t = 0.0
    while t < len(A) / sr:
        seg = A[int(t * sr):int((t + CH) * sr)]
        with torch.no_grad():
            lg = model(proc(seg, sampling_rate=sr, return_tensors="pt").input_values.to(DEV)).logits[0]
        l = torch.log_softmax(lg, -1).detach().cpu().numpy(); f = (len(seg) / sr) / l.shape[0]
        for i in range(l.shape[0]):
            tt = t + i * f
            if t > 0 and tt < t + OV / 2: continue
            k = int(round(tt / fd))
            if k < n: lp[k] = l[i]
        t += CH - OV
    inv = {v: k for k, v in proc.tokenizer.get_vocab().items()}
    vocab = [inv.get(i, "?") for i in range(V)]
    np.savez(cache, lp=lp, fd=fd, vocab=np.array(vocab, dtype=object))
    return lp, fd, vocab
if __name__ == "__main__":
    wav, cache = sys.argv[1], sys.argv[2]
    lp, fd, vocab = emissions(wav, cache)
    blank = vocab.index("[PAD]"); sep = vocab.index("|") if "|" in vocab else -1
    for rng in sys.argv[3:]:
        a, b = map(float, rng.split("-"))
        out = []; prev = -1
        for k in range(int(a / fd), int(b / fd)):
            j = int(lp[k].argmax())
            if j not in (blank, sep) and j != prev:
                row = lp[k].copy(); row[blank] = -99; row[sep] = -99; o = np.argsort(-row)[:2]
                out.append(f"{k*fd:.2f}{vocab[j]}" + (f"({vocab[o[1]]})" if o[0] == j else ""))
            prev = j
        print(f"[{a}-{b}] " + " ".join(out))
