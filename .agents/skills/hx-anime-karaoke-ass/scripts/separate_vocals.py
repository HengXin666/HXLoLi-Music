# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "numpy",
#   "torch",
#   "demucs",
# ]
# ///

"""人声分离（demucs htdemucs_ft，CPU 可跑）
用法: uv run separate_vocals.py <input_media> <out_dir> [--start S] [--dur D]
输出: out_dir/vocals.wav(44.1k 立体声) vocals16k.wav(16k 单声道, 供对齐/分析) inst.wav
依赖: torch, demucs(可 pip install --no-deps --target <dir> demucs julius openunmix dora-search lameenc ... 再加 PYTHONPATH)
"""
import argparse, subprocess, wave, numpy as np, torch, os, sys
from demucs.pretrained import get_model
from demucs.apply import apply_model

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from device import pick_device, log_device, warmup, peak_mem_mb

ap = argparse.ArgumentParser()
ap.add_argument("inp"); ap.add_argument("out")
ap.add_argument("--start", type=float, default=0); ap.add_argument("--dur", type=float, default=0)
ap.add_argument("--threads", type=int, default=32)
ap.add_argument("--device", default="", help="auto(默认,有卡就用GPU) / cuda / cpu；ASSFX_DEVICE 也可")
a = ap.parse_args()
torch.set_num_threads(a.threads)
DEV = pick_device(a.device)
log_device(DEV, "separate_vocals demucs")
warmup(DEV)
os.makedirs(a.out, exist_ok=True)
cmd = ["ffmpeg", "-v", "error", "-ss", str(a.start), "-i", a.inp]
if a.dur: cmd += ["-t", str(a.dur)]
cmd += ["-f", "f32le", "-ac", "2", "-ar", "44100", "-"]
raw = subprocess.run(cmd, capture_output=True, check=True).stdout
x = torch.from_numpy(np.frombuffer(raw, dtype=np.float32).reshape(-1, 2).T.copy())
m = get_model("htdemucs_ft"); m.eval().to(DEV)
ref = x.mean(0); mean, std = ref.mean(), ref.std()
# 12GB 显存跑 htdemucs_ft 全曲可能 OOM; split=True 让 demucs 自己分片并失败时降 segment
try:
    with torch.no_grad():
        out = apply_model(m, ((x - mean) / std)[None].to(DEV), device=DEV, shifts=1, split=True,
                          overlap=0.25, progress=False)[0] * std + mean
except torch.cuda.OutOfMemoryError:
    print("[device] CUDA OOM, 退回 CPU 重跑（慢但能出结果）", flush=True)
    torch.cuda.empty_cache()
    DEV = "cpu"; m.to(DEV)
    with torch.no_grad():
        out = apply_model(m, ((x - mean) / std)[None].to(DEV), device=DEV, shifts=1, split=True,
                          overlap=0.25, progress=False)[0] * std + mean
voc = out[m.sources.index("vocals")].detach().cpu().numpy()
print(f"[device] 峰值显存 {peak_mem_mb(DEV):.0f} MB（设备 {DEV}）", flush=True)

def save(p, arr, sr=44100):
    arr = (np.clip(arr, -1, 1) * 32767).astype(np.int16)
    arr = arr.T if arr.ndim == 2 else arr[:, None]
    w = wave.open(p, "wb"); w.setnchannels(arr.shape[1]); w.setsampwidth(2); w.setframerate(sr)
    w.writeframes(arr.tobytes()); w.close()

save(os.path.join(a.out, "vocals.wav"), voc)
save(os.path.join(a.out, "inst.wav"), x.numpy() - voc)
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", os.path.join(a.out, "vocals.wav"), "-ac", "1", "-ar", "16000",
                os.path.join(a.out, "vocals16k.wav")], check=True)
print("ok", a.out)
