# Agent Note: 卡拉OK 字幕链默认改用 GPU，可复现性降级为可验证开关

Status: implemented

- 影响: `.agents/skills/hx-anime-karaoke-ass/scripts/device.py`（`pick_device` 默认值），
  以及 `align_ctc.py` / `grid_align.py` / `ctc_read.py` / `separate_vocals.py` 的设备入口；
  新增 `scripts/device_check.py`；`SKILL.md` 与 `steps/00-setup/index.md` 的 GPU 说明段。

## Problem

`device.py` 把默认设备写死成 `cpu`，理由写在注释里：GPU 与 CPU 的浮点结果不完全相同，
同一份工程换设备跑出来的 timing 可能有毫秒级差异，保持默认 CPU 就等于结果可复现。

这个理由在本次改动前从未被测量过。实测（RTX 4080 Laptop，12s 人声片段，同一份权重）：
logits 最大绝对差 0.048，**逐帧 argmax 一致率 100.0000%**，贪心解码出的 34 个发音尖峰**完全同序同字**，
帧位移最大 0.000s。也就是说「设备会改变对齐结果」这个前提在本工程的判据上不成立 ——
对齐用的是后验的 argmax 边界，不是浮点值本身。

代价却是实测的：整曲 3~5 分钟要切成几十个块逐块前向，CPU 上这一步是整条流水线里最长的等待，
而它正好在人工校时**之前**，每改一次歌词/读音就要重跑一次。

## Decision

默认值从 `cpu` 改为 `auto`：探测到 CUDA 就用 GPU，否则回 CPU；`ASSFX_DEVICE=cpu` 与 `--device cpu`
仍可关掉。可复现性不再是默认行为，而是一个**可验证的开关**：新增 `scripts/device_check.py`，
它把同一段音频在两种设备上各跑一遍，输出逐帧一致率、尖峰帧位移与解算耗时，判据写在输出里 ——
位移 ≤1 帧(20ms) 就用 GPU 出终稿，超过就用 `ASSFX_DEVICE=cpu` 复跑一次。

四个入口脚本原来各自 `pick_device()`，现在都能被 `--device` 单独覆盖，`grid_align.emissions()`
多了 `prefer` 参数以便 `--device` 透传。

## Alternatives considered

- **什么都不做（保持默认 CPU）**: 最强理由是「不测就不知道换设备哪天会咬人，CPU 慢但稳」。
  否决：这个稳是**未验证的**稳，而慢是每天都在付的成本；真正需要稳的人可以用环境变量显式关掉，
  而现在关掉的那一方是少数。
- **默认改 GPU 但不提供对照工具**: 最强理由是「实测已经证明没差，不必为此再写脚本」。
  否决：实测结论绑定在本机这张卡、这个 torch 版本、这个模型上；换机器后没有人会再去测一遍，
  于是「默认 GPU」变成一条无法复验的口头承诺。对照脚本把结论变成每条机器上都能重跑的实验。
- **默认 GPU 并把 CPU 路径删掉**: 否决。规范允许的无 GPU 环境（CI、别人的笔记本）会直接跑不动，
  而 OOM 退回本来就是 CPU 路径的一部分。

## Consequences

- 有 CUDA 的机器上对齐/分离默认走 GPU；`separate_vocals.py` 仍捕获 OOM 退回 CPU，并打印实际设备与峰值显存。
- 短片段上 CUDA 因上下文初始化可能反而更慢（实测 12s 片段 cuda 8.1s vs cpu 3.1s）——
  这条已写进 `steps/00-setup/index.md`，避免有人用片段耗时否定整曲收益。
- 想复现历史工程：`ASSFX_DEVICE=cpu` 跑一次即可；`device_check.py` 能给出那次复现是否必要的证据。