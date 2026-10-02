# 05 音拍级强制对齐(本地音频)

## 只做这一件事

把人声里的发音逐音拍对到 `lyrics.txt` 上, 产出**第一版**时间轴 `timing_auto.json`.

**初版不等于终稿**: 这一步产出的是"机器的读数", 第 06 步要用网络逐字源重塑句内形状,
第 08 步要人工看频谱核对. 不要拿 `timing_auto.json` 直接进设计.

## 命令

```bash
hx-karaoke align_ctc.py --lyrics proj/lyrics.txt --vocals proj/stems/vocals16k.wav --estimate-offset     # 先估偏移
hx-karaoke align_ctc.py --lyrics proj/lyrics.txt --vocals proj/stems/vocals16k.wav \
    --offset <03 步的中位差> --out proj/timing_auto.json
```

## 要点

- **每句单独成块, 窗口在换气空隙切**(没有空隙就切在能量最低点); 否则连唱句尾被截、下一句首被吃.
- **合いの手行(整句括号)不参与切窗** —— 呼喊常与主唱重叠, 用它的 lrc 时间切窗会把前一句腰斩.
- `--offset` 用 `03-offset` 的 median. 那一步离散度过大时先解决来源问题, **不要靠调 offset 硬凑**.
- 脚本会同时留一份 `ctc_lp.npz`(逐帧 logits), 后面 `ctc_read.py` 与 `grid_align.py --emis` 都要它.

## 这一步要用的脚本

- `<skill>/scripts/align_ctc.py` - 音拍级强制对齐, 写 `timing_auto.json` 与 `ctc_lp.npz` (后者给 ctc_read / grid_align 用)

## 产物与过关条件

`proj/timing_auto.json` + 可疑点清单(脚本打印). 音拍数应等于 `lyrics.txt` 的音拍数;
对不上说明歌词用了两份不同版本, 回第 02 步.

## 已知局限(这就是第 06 步存在的理由)

CTC 在**长音与间奏**处会**塌缩**: 把整段拖长/间奏算给最后几个音拍, 其后的字被整体顺延几秒.
实测东方工程 36 行里 8 行如此, 最坏一行「教えてくれた」被判成 22.73s 跨度而真值 1.50s(**15.2 倍**).
这一步不做修正, 修正放在 `06-kf-timing` 与 `08-review-timing`.
