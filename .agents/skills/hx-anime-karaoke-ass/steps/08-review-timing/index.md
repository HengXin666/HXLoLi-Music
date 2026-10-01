# 08 人工校时与时间轴体检(最花时间也最值钱, 必做)

## 只做这一件事

看**频谱**逐句核对音拍起点, 把修正写进 `fixes.json`, 产出**终稿** `timing.json`.
这一步不许省: CTC 在连唱、长音、英文和声处会挤成一团, 机器判不出来.

## 8a 看频谱

```bash
uv run $S/review_spectrogram.py --vocals proj/stems/vocals16k.wav --timing proj/timing_snap.json \
   --grid proj/grid.json --out proj/review/r1.png --windows 45.0-51.5,57.0-63.4
```

读图: 横轴时间, 橙色谐波条=音符; 青线=当前音拍起点(标注 `line,unit,mora`), 绿虚线=节拍/十六分网格.

- 每个音拍线应落在一个音符起音处; 长音内部不应有多余的线; 一个音符里挤了多个线 → CTC 挤压, 需要摊开.
- **副歌一致性**: 同一句词在各段副歌中的相对节奏应一致(本例 chorus2 = chorus1 + 64.0s,
  chorus3 = +112.0s, 80/140 拍). 可疑时把三段并排渲染对比, 用可信的一段推算其他段.

修正写进 `fixes.json`: `{"line,unit,mora": 新起点}`; unit 下标包括空格单元, **以图上标签为准**.
用 `"_why"` 记一句「这轮看了哪几段、结论是什么」—— 门禁会读它, 0 条修正也要写.

```bash
uv run $S/apply_fixes.py --timing proj/timing_snap.json --fixes proj/fixes.json \
    --vocals proj/stems/vocals16k.wav --out proj/timing.json
```

脚本会重算终点并断言起点单调(合いの手行不参与单调检查). 再渲染频谱复核一遍.

## 8b 同步体检

```bash
uv run $S/check_sync.py --vocals proj/stems/vocals16k.wav --timing proj/timing.json --report proj/review/sync.txt
```

三类告警: A 起点时人声还没出来(字幕**早**了); B 最近起音在起点后 >0.18s; C 有人声起音但附近没有音拍起点.
`!!` 逐条看频谱确认: 长音换字、气声、齐唱错位常是误报; 真问题写进 fixes 再跑一遍.

**判定原则**: 人耳对「字幕早于声音」比「晚」敏感得多 —— 拿不准时宁可晚 20~40ms.

怀疑"整体慢了/快了"时跑 `check_lag.py`, 但**先读 `impl/lag-verdict.md`**:
逐句起音法给出的"字幕偏晚"在长句/长音句上是**系统性假阳性**, 不要照它平移.

## 8c 时间轴体检(会非零退出, 不许跳过)

```bash
uv run $S/check_timing_health.py --vocals proj/stems/vocals16k.wav --timing proj/timing.json \
    --report proj/review/health.txt
echo $?     # 非 0 = 有 CTC 塌缩或句内间奏，不许进下一步
```

它交叉三个互相独立的量: 音拍时长分布、人声谱通量起音、句内静音段.
**判定行必须满足 CTC塌缩 0 处 且 句内间奏 0 处**; `check_gates.py --stage render` 会读这一行.

为什么它现在会拦截: 历史版本只打印报告、退出码恒为 0. 实测 `proj-touhou` 里它正确报出 2 处塌缩,
但因为没人读报告, 错误一路进了成片, 那句歌词比声音晚了 20 秒.
`--max-collapse -1` 可显式放行(等于书面声明"我看过且认可").

## 产物与过关条件

- `proj/timing.json`(终稿, 音拍数 = `lyrics.txt` 的音拍数)、`proj/fixes.json`(含 `_why`).
- `proj/review/health.txt` 判定行: **CTC塌缩 = 0、句内间奏 = 0**. 非 0 不许往下走.
- `check_sync.py` 的 `!!` 逐条有结论(真问题进 fixes, 误报记原因).

## 这一步要用的脚本

- `<skill>/scripts/review_spectrogram.py` - 渲染频谱图 (谐波=音符) + 音拍起点竖线 + 节拍网格, 供逐句核对
- `<skill>/scripts/apply_fixes.py` - 把 `fixes.json` 应用成终稿 `timing.json`, 重算终点并断言起点单调
- `<skill>/scripts/check_sync.py` - 同步体检: A 字幕早了 / B 起音晚 / C 有音无拍, 写 `review/sync.txt`
- `<skill>/scripts/check_lag.py` - 量字幕比人声慢多少; 判据见 `impl/lag-verdict.md` (是系统性假阳性)
- `<skill>/scripts/check_timing_health.py` - 时间轴体检 (塌缩/句内间奏/起音匹配率), 写 `review/health.txt`; 退出码非 0 就是拦路

## 具体做法

- `impl/lag-verdict.md` —— **怀疑"字幕整体偏晚"时先读它**: 已核实的假阳性清单与复核算法的正确读法, 不要重新推导.
