# 06 逐字权威时间(网络逐字歌词优先)

## 只做这一件事

用网络逐字歌词(LDDC)**重塑句内相对形状**, 再用本地 CTC 定**整体平移**, 产出 `timing_kf.json`.

分工只有一句话: **网络定句内形状 + 本地定整体平移. ** 这是逐字准确率的第一手段, 能做到就该做.

## 为什么必须走它

CTC 强制对齐在**长音与间奏**处会塌缩: 把整段拖长/间奏算给最后几个音拍, 其后的字被整体顺延几秒.
网络逐字歌词(LDDC)的**句内相对关系**是权威的(实测与作者手工调准的音拍句内间隔差中位 5ms).
最坏实例、完整实测数据与四条不许丢的纪律见 `impl/collapse.md`.

## 命令

```bash
export HX_LDDC_PATH=~/Loli/code/HX-Music/pyTool      # 亦可每次传 --lddc
hx-karaoke kf_timing.py fetch --title "<曲名>" --artist "<艺人>" --source QM --project proj
#   打印候选表让你核对；给 --song-id 定版本（别让 Inst./TV size/翻唱混进来）
hx-karaoke kf_timing.py align --project proj --auto proj/timing_auto.json --out proj/timing_kf.json
hx-karaoke kf_timing.py verify --project proj --a proj/timing_kf.json --b proj/timing.json
```

产物: `kf.json`(原始逐字)、`timing_kf.json`(融合结果)、`review/kf-report.md`(塌缩行清单 + 逐行偏移表).

## 三条不许丢的纪律

**全部行取中位求偏移、绝不逐行定锚、对齐坐标系用显示文本 `surf`** —— 每条的实测数字与理由见 `impl/collapse.md`.
换实现时这三条最容易丢, 丢了精度会退回纯 CTC 的水平.

## `--source` 怎么选(覆盖关系, 不是投票关系)

按可用性试 `QM / KG / NE / LRCLIB`. 实测 **QM 与 KG 对同一首歌返回逐字时间完全相同**(句内间隔差恒为 0),
说明它们共享同一数据源; NE 是独立采集, 与 QM 有 0.2~12s 的差异. 所以多源不是投票, 而是"哪个源有这首歌" ——
用 `NE` 前先确认它的版本对得上.

**缺 `kf.json` 时 `align` 明说"不做任何事"**, 不会伪造时间轴. 没有逐字源的曲目退回纯 CTC 流程即可.

## 产物与过关条件

`timing_kf.json` 存在; `review/kf-report.md` 的**离散度**里没有 >20s 级分量(那是配对错误, 见 `impl/pairing.md`).

## 这一步要用的脚本

- `<skill>/scripts/kf_timing.py` - 三个子命令 `fetch` / `align` / `verify`: 抓网络逐字歌词, 融合本地平移, 对比两份时间轴

## 具体做法

- `impl/collapse.md` —— 长音塌缩的判据(长音拍**内部**静音占比)与两种修法. **怀疑"字幕慢了几秒"时读它. **
- `impl/pairing.md` —— `align` 的三处失手模式(重复句吸错、拉丁单元塌成 0、行窗口倒挂)与一眼看出配错的方法.
