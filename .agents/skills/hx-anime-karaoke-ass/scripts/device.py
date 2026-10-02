# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "torch",
# ]
# ///
"""统一的 torch 设备选择：**默认自动用 GPU**，探测不到才回 CPU。

为什么默认改成自动: 本机实测 RTX 4080 Laptop 上 wav2vec2 前向比 CPU 快一个数量级，
而 skill 原先把默认写死 CPU 的理由是"换机器结果可复现"。这个理由只在**判决性差异**
存在时才成立 —— 本 skill 的对齐是逐块 CTC Viterbi，模型权重始终是 fp32、Viterbi 本身
跑在 CPU 的 numpy 上，设备差异只来自 CUDA kernel 的浮点归约顺序，量级远小于后面
"人工校时"要处理的 ±0.1s。所以默认取速度，把"可复现"做成一个**可验证**的开关而不是默认值：

  ASSFX_DEVICE=cpu        # 要逐帧复现旧结果时显式关掉 GPU
  --device cuda|cpu|auto  # 单次覆盖（四个入口脚本都接受）

要确认某台机器上 GPU/CPU 到底差多少，跑:
  hx-karaoke device_check.py --vocals <proj>/stems/vocals16k.wav --sample 60
它把同一段音频在两种设备上各跑一遍 CTC，给出前后验帧级最大位移与起音时间差。
判据: 若最大位移 >1 帧(20ms)，就当它会影响对齐，用 CPU 出终稿。

CPU 侧仍用 torch.set_num_threads(32~48) 压满核心，所以"回 CPU"不等于放弃并行。

工程约束见 .agents/notes/implemented/process/2026-10-01-karaoke-gpu-default-auto.md
（该篇记着"为什么不默认 CPU"被推翻的实测依据，改默认值前先读它）。

用法:
    from device import pick_device, log_device
    dev = pick_device()
    model = Model.from_pretrained(MID).eval().to(dev)
"""
import os
import sys

VALID = ("auto", "cuda", "cpu")


def _cuda_usable() -> bool:
    """CUDA 可用性探测；任何异常（无卡/驱动不匹配/裁剪版 torch）都算不可用。"""
    try:
        import torch
        return bool(torch.cuda.is_available())
    except Exception:
        return False


def pick_device(prefer: str = "") -> str:
    """返回 "cuda" 或 "cpu"。

    默认 **auto**: CUDA 可用就用 CUDA（GPU 优先），否则 CPU。
    覆盖优先级: 参数 prefer > 环境变量 ASSFX_DEVICE > auto。
    显式写 cpu 就不再探测 —— 需要复现旧结果时用它。
    """
    want = (prefer or os.environ.get("ASSFX_DEVICE", "") or "auto").strip().lower()
    if want not in VALID:
        print(f"[device] 未知设备 {want!r}（可用: {', '.join(VALID)}），按 auto 处理", file=sys.stderr)
        want = "auto"
    if want == "cpu":
        return "cpu"
    if want == "cuda":
        if not _cuda_usable():
            print("[device] 要求 cuda 但 torch.cuda.is_available() 为假，退回 cpu", file=sys.stderr)
            return "cpu"
        return "cuda"
    return "cuda" if _cuda_usable() else "cpu"


def why(dev: str) -> str:
    """给出一行"为什么是这个设备"，写进报告用。"""
    want = (os.environ.get("ASSFX_DEVICE", "") or "auto").strip().lower()
    if dev == "cuda":
        return "cuda（默认自动探测：可用且有卡）" if want in ("", "auto") else f"cuda（ASSFX_DEVICE={want}）"
    if want == "cpu":
        return "cpu（ASSFX_DEVICE=cpu 显式关闭 GPU）"
    if want == "cuda":
        return "cpu（要求 cuda 但不可用，已退回）"
    return "cpu（自动探测：本机 CUDA 不可用）"


def log_device(dev: str, what: str = "") -> str:
    """打印一行设备信息，便于报告里写实测来源。"""
    extra = ""
    if dev == "cuda":
        try:
            import torch
            extra = f" ({torch.cuda.get_device_name(0)})"
        except Exception:
            pass
    msg = f"[device] {what or 'torch'} -> {dev}{extra}  [{why(dev)}]"
    print(msg, flush=True)
    return msg


def warmup(dev: str) -> None:
    """CUDA 首次调用要初始化上下文，先跑一个小算子避免把耗时算进第一步。"""
    if dev != "cuda":
        return
    import torch
    torch.zeros(1, device=dev).sum().item()


def peak_mem_mb(dev: str) -> float:
    """返回峰值显存占用 MB，用于报告。CPU 返回 0。"""
    if dev != "cuda":
        return 0.0
    import torch
    return torch.cuda.max_memory_allocated() / 1048576


def oom_fallback(model, dev: str, tag: str = ""):
    """CUDA OOM 的统一兜底：清缓存、把模型挪回 CPU、返回 "cpu"。

    12GB 显存跑 htdemucs_ft 整曲仍可能 OOM（实测 20s 片段峰值 1.1GB，整曲远高于此），
    这里只负责"摔下来还能跑完"，不负责重试别的设备。
    """
    import torch
    torch.cuda.empty_cache()
    print(f"[device] {tag or 'torch'} CUDA OOM，退回 CPU 重跑（慢但能出结果）", file=sys.stderr)
    try:
        model.to("cpu")
    except Exception:
        pass
    return "cpu"


if __name__ == "__main__":
    dev = pick_device()
    log_device(dev, "probe")
    print(f"ASSFX_DEVICE={os.environ.get('ASSFX_DEVICE', '(unset)')}")
