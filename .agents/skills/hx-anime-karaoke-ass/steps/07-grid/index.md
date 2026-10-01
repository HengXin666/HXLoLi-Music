# 07 节拍网格与吸附

## 只做这一件事

从**伴奏**测出节拍网格, 把音拍起点朝最近的网格槽位吸附一次. 给第 08 步的频谱图一条参照线,
也给第 07b 的约束重对齐提供槽位.

## 命令

```bash
uv run $S/beat_grid.py --inst proj/stems/inst.wav --out proj/grid.json
uv run $S/snap_timing.py --timing proj/timing_kf.json --grid proj/grid.json --out proj/timing_snap.json --lag 0.035
```

**输入用 `timing_kf.json`**(若第 06 步拿到了). 没有逐字源时用 `timing_auto.json`.

## 要点

- J-pop 人声基本在 1/16 网格上; CTC 起点通常比网格晚 ~35ms(辅音后才判元音), `--lag` 补偿.
- 吸附只在 60ms 以内生效且**不与邻拍冲突**.
- **BPM 减半**: beat_grid 常把 170~190BPM 测成一半(ピンキージョーンズ 180→90),
  此时 16 分音符 = 每个 period 细分 8(`--div 8`).

## 07b 快歌/齐唱: 网格约束重对齐(可选)

CTC 在齐唱、rap、快歌里会把没听清的几拍挤成 20ms 或整段漂移, 逐拍手修成本太高.
`grid_align.py` 把每个音拍起点限制在网格槽位上做 DP.

```bash
uv run $S/grid_align.py --lyrics proj/lyrics.txt --vocals proj/stems/vocals16k.wav \
   --timing proj/timing_auto.json --grid proj/grid.json --div 8 --emis proj/stems/ctc_lp.npz \
   --anchors proj/fixes.json --parity 15:48,16:49,17:50 --out proj/timing_grid.json
```

- 证据 = CTC 贪心解码「听到的音拍」(小假名并入前字); 相似度: 完全相同 0 > 同首假名/仅浊点不同 −0.4 >
  ん/ー −0.5 > 同元音 −0.8 > 同辅音 −1.2 > 其他 −2.2; 距离按高斯(σ 50ms)衰减, ±80ms 内什么都没听到 −4.
- `--lag` 缺省自动估计; 8 分槽位 +0.3 奖励; 偏离原对齐 >0.25s 起罚(先验).
- `--anchors` 把 `fixes.json` 的人工起点当硬约束; `--parity a:b` 让两段同词句**联合对齐**
  (相对节奏强制一致, 偏移在 ±3 槽内搜索)——**副歌、重复段必用**.
- 查「模型到底听到了什么」: `uv run $S/ctc_read.py vocals16k.wav ctc_lp.npz 80.0-82.5`.
- 对比重复段: `uv run $S/parity_cmp.py proj/timing.json 15:48,16:49`(差 >0.12s 标 `<<`).

## 这一步要用的脚本

- `<skill>/scripts/beat_grid.py` - 从伴奏测节拍网格, 写 `grid.json`
- `<skill>/scripts/snap_timing.py` - 把音拍起点吸附到最近的网格槽位 (`--lag` 补偿 CTC 延迟), 写 `timing_snap.json`
- `<skill>/scripts/grid_align.py` - 07b: 把音拍起点限制在网格槽位上做 DP 重对齐 (`--parity` 副歌联合)
- `<skill>/scripts/ctc_read.py` - 查模型到底听到了什么 - 判断是 CTC 听错还是歌词/读音写错
- `<skill>/scripts/parity_cmp.py` - 对比重复段的相对节奏 (差 >0.12s 标 `<<`)

## 产物与过关条件

`proj/grid.json` + `proj/timing_snap.json`(或走 07b 时的 `timing_grid.json`).
吸附量过大的句子(>60ms 未吸附、或与邻拍冲突)在报告里逐条看, 不静默放过.
