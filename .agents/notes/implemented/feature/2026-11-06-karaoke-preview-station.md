# Agent Note: 卡拉OK 预览台  锁定产物与区间补丁

Status: implemented

Decision-ID: karaoke-preview-station


## Code

- `.agents/skills/hx-anime-karaoke-ass/scripts/assdoc/assdoc.py`

## Problem

用户 2026-11-06: 「参考 video-shotcraft 搞一个预览台, 来固定产物. 并且可以简单精确区间的进行微调, 而非全局抽奖」

调整 `out.ass` 只有一条路: 改 `make_ass.py` 再整首重跑. 随机数按位置取种子:
`Generator.render()` 第 i 句用 `random.Random(seed + i)` 与 `FX(seed=1000 + i)`, 卡点层整首共用一个 `FX(seed=31)`.
所以改一句的参数或在 PHRASES 里插一句, 会换掉后面所有句与整段卡点层的随机序列.
上一版满意的句子留不住, 每次重跑都是全局抽奖. 也没有"只把这 3 条 fx 往后挪 40ms"的手段.

## Decision

在 skill 里加 `scripts/station/`, 参照 video-shotcraft 的 Motion Workbench (成片交付后在浏览器里按轨编辑, 改动可撤).
成品拆三层, 构建顺序固定: `out.ass = 补丁(锁(out.raw.ass))`.

- **raw**: 生成器输出, 预览台只读.
- **锁**: 选区内事件的原文快照 (`review/station/locks/*.ass`). 构建时先删 raw 里同选区的事件, 再写回快照. 重跑生成器不影响已锁句.
- **补丁**: `station.json` 里的有序算子 (shift / trim / retime / tags / sub / layer / drop), 每条只作用于自己的选区, 可逐条撤.
- **选区**: Name 通配加可选 `[t0, t1)`, 只按事件起点判, 一条事件只属于一个区间.
- **页面**: 用 skill 自带的定制版 libass 叠在 `base.mp4` 上实时播放. 时间线按句分泳道, 点句即循环, Shift 拖框区间, `[` `]` 10ms 平移并合并成一条补丁.

未改动的事件按原串写回, 排序只按 (厘秒起点, 原文件次序). 实测示例工程 9131 条事件接管后逐字节不变.
直接覆盖 `out.ass` 会被下一次构建拒绝 (按 sha 判), 防止补丁层被静默丢掉.

## Alternatives considered

**什么都不做 / 复用现有.** 最强理由是无需新增实现和维护成本: 继续改 `make_ass.py` 后整首重跑. 现有状态仍存在 Problem 中的缺口: 满意的句留不住, 也不能只改一个区间. 因此采用本记录的选择

- **改 Generator 的种子为按句名取 (`seed=hash(name)`)**: 最强理由是从根上消除位置耦合.
  否决为主方案: 它会改变所有现存工程的输出, 且只解决"插一句", 不解决"改同一句的参数也会换掉它的随机结果".
  锁是对产物的承诺, 不依赖生成器写法.
- **直接移植 shotcraft 的 Remotion 工作台**: 否决. 那套以 React 组件为单元, 这里的单元是 ASS 事件, 渲染器也必须是定制版 libass (系统 libass 会静默退化 `\1img` 等标签).
- **补丁直接改 raw**: 否决. 重跑生成器会冲掉补丁, 又回到抽奖.

## Consequences

- 工程多两个产物: `out.raw.ass` 与 `review/station/`. 都在工程目录, skill 内无运行痕迹.
- 补丁按选择器匹配, 重跑后句子编号或时间变了会命中 0 条. `ls` 与页面状态栏会标出, 由人处理.
- 预览台不做 band 校验. `tags` 加位置或放大可能出 band, 仍由 `13-validate` 拦.
- 自检: `scripts/station/selftest.py` 造一个会抽奖的生成器, 验证接管不改字节, 锁不随重跑变, 补丁只动选区, 撤销可回到原样.
- 端到端: `scripts/station/e2e.py` (+ `e2e_api.py`, `e2e_ui.js`) 用 mushoku_ed1 真生成器, 真 CLI, 真 HTTP 服务, playwright + 定制版 libass 逐项实测. 2026-11-06 实跑 75/75 PASS.
- 2026-11-06 补: 外部改动在写锁/补丁之前检查 (409, 不落盘), 补丁参数落盘前校验, 页面加替换与起点微调, 未命中补丁标红, 伸缩框随重建刷新.
- 2026-11-09: 用户确认删除旧前端, `scripts/station/` 整个目录已删 (未曾入库). 事件读写 (未改动事件按原串写回, 逐字节不变) 搬到 `.agents/skills/hx-anime-karaoke-ass/scripts/assdoc/assdoc.py`, 供 `scripts/accept/` 与 `scripts/selfreview/` 共用; 浏览器页面由 `scripts/studio/` 取代, 标注改走 studio 的 `POST /api/review`. 上文 station 的 selftest / e2e 随目录一并删除, 75/75 为当时的历史结果.

## 后续变更 (2026-11-24)

本决策覆盖的目录在 2026-11-17 到 11-24 之间有改动, 本决策本身不变:

- scripts/assdoc/ 新增 design.py: 验收台设计稿面板的视图, 解析与校验只用 kfx_design.py (architecture/2026-11-22-karaoke-kfx-single-generator.md).
