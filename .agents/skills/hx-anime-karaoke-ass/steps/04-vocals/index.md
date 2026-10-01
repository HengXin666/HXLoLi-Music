# 04 人声分离

## 只做这一件事

从 `base.mp4` 里分出**人声轨**与**伴奏轨**。后面所有"看时间"的判定（校准、对齐、体检、频谱）都吃这份人声。

## 命令

```bash
uv run $S/separate_vocals.py proj/base.mp4 proj/stems --threads 32
```

## 产物

- `proj/stems/vocals16k.wav` —— 16k 单声道，**对齐/分析用这一份**
- `proj/stems/inst.wav` —— 伴奏，节拍网格用
- `proj/stems/vocals.wav` —— 44.1k 立体声

报告里会打印**实际使用的设备与峰值显存**。整曲在 12GB 显存上可能 OOM，
脚本捕获后自动退回 CPU 重跑并打印实际设备 —— 这不是失败，但要写进交付说明。
实测 20s 片段 CUDA 峰值显存 1139MB。

## 过关条件

三个 wav 都在，且报告里能读到实际设备。若实际走了 CPU，记下来（第 00 步的 `device_check` 在换机器时才有意义）。

## 顺序说明

这一步必须在 `03-offset` 与 `05-align` **之前**（那两步都要 `vocals16k.wav`）。
`02-lyrics` 的 2c 读音核对也用它，所以标准顺序是 01 → 02a → 02b → 04 → 02c → 03 → 05。
若先做了 02c 发现缺 vocals，回头补 04 再重跑 02c 即可。
