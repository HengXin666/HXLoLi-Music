# 03 位置对齐校准(语音, 不靠画面)

## 只做这一件事

测出**网络歌词时间轴与这份视频之间差多少**, 产出一个数: 中位差. 它后面要喂给第 05 步的 `--offset`.

## 为什么必须做

网络歌词的时间轴是 CD/完整版的, 与手上这份 MV 常差 0.1~0.5s(前奏剪辑不同、是否含 TV 前奏).
不做这一步, 整首歌的字幕会统一偏早或偏晚.

**用语音测, 不用画面测** —— 识别**时间**, 不识别**文字**.

## 命令

```bash
uv run $S/calibrate_offset.py --lyrics proj/lyrics.txt --vocals proj/stems/vocals16k.wav --out proj/offset.json
uv run $S/calibrate_offset.py --lyrics proj/lyrics.txt --vocals proj/stems/vocals16k.wav --ctc --out proj/offset.json
```

两条证据通道:

- **能量/起音**(默认, 快): 在人声里找每次「从静音起来」的起唱点, 与歌词行的 lrc 时间配对求差.
- **CTC**(`--ctc`, 慢但准): 对每行窗口跑 wav2vec2 强制对齐, 取该行**第一个音拍**的模型起点.
  能量法在「上一句长音拖过来」或「器乐残留」时会误判, CTC 看的是发音本身(默认走 GPU).

## 判据

产物里给三个数: **中位差**(= 第 05 步 `--offset` 的值)、**离散度**(Δ 的 p90−p10)、**verdict**.

- 离散度 >0.8s → 先读 `impl/verdict.md`. **不许手改 verdict 字段**, 要先看 `step_jump`:
  实测有一次能量法与 CTC 法的中位差一致到 1ms, 但离散度双双 FAIL, 逐行看是正负交替的**方法噪声**,
  不是剪辑差异. 真剪辑差异长的是"一处阶跃"的样子.
- 真判定为「不是同一剪辑」时 → 换一份同源时间轴, 或退回人工听写并写 why, **不许硬套**.
- 历史工程可以用 `--from-timing proj/timing.json --why "..."` 据终稿反推, 但必须写 why ——
  它给的是「当时用了多少」, 不是「这次该用多少」.

## 产物与过关条件

`proj/offset.json`: 来源级别合法、中位差与离散度都在产物里、verdict 写明通过的是哪条通道.
`check_gates.py --stage render` 会查这个文件.

## 这一步要用的脚本

- `<skill>/scripts/calibrate_offset.py` - 从人声测网络时间轴与这份视频的差量 (能量起音法 / `--ctc`), 写 `offset.json`

## 具体做法

- `impl/verdict.md` —— **离散度判 FAIL 时先读它**: 怎么分「检出噪声」与「真剪辑差异」, 两条通道的阈值怎么标定出来的.
