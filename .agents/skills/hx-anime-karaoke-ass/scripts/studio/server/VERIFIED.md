# e2e 断言有效性证据 (变异验证)

日期: 2026-11-10。工程: `dev/无职转生/オンリー`。方法: 每项把产品代码弄坏一处 → 重建 dist → 跑全套 → 记录哪条红 → 恢复 (与备份字节一致) → 重建 (产物名回到正常版 `index-CY0lxZ1B.js`) → 再跑全套回绿。

基线: e2e_placement 13/13, e2e_ui 68/68, check_viewports 9/9。基线 out.ass sha256 前缀 `9e69349871913ab93d5f20b0`, placement.json 不存在, 每轮后核对均未变。

## e2e_ui.js (8 处高危断言)

| 用例 | 变异点 | 红的断言原文 / 实际值 | 结果 | 恢复 |
|---|---|---|---|---|
| M14 | `web/src/lib/actions.ts` L299 `if (k === 'g') …` 注释掉 | `快捷键 G: 条数 10->10` (新增条数断言; 旧版只看 kind 会误过) | 65/68 (M14, M15, K5 红) | 68/68 |
| M15 | 同上 L300 `if (k === 'r') …` 注释掉 (与 M14 同一次变异) | `快捷键 R: 条数 10->10`; K5 连带红 `good,bad,note` (缺 redo) | 同上 | 68/68 |
| M10 | `web/src/components/Inspector.tsx` L96 `inspector-close` 的 onClick 改为 `{ void set; /* MUTATION */ }` (点关闭不卸载检查器) | `page.waitForFunction: Timeout 3000ms exceeded` (等旧检查器卸载; 旧版 count===1 会误过) | 67/68 (仅 M10) | 68/68 |
| U3 | `server/app.py` do_POST /api/review 的 `send_json(rec, 201)` 改为 `self.err(500, …)` | `POST bad -> 500` | 65/68 (U3, U4, U6 红) | 68/68 |
| U6 | 同上 (与 U3 同一次变异) | `POST -> 500`; U4 连带红 `page.waitForFunction: Timeout 4000ms exceeded` (U4 依赖 U3 写入的标注, 是 U3 的下游) | 同上 | 68/68 |
| F2 | `web/src/components/LyricsPanel.tsx` L43 `if (browse) return;` 注释掉 | `浏览模式下仍在跟随: translate3d(0px, -150.4px, 0px) -> translate3d(0px, -607.9px, 0px) @4ms` (holdFor 第 4ms 即抓到) | 67/68 (仅 F2) | 68/68 |
| M6 | `web/src/components/ContextMenu.tsx` L78 onClick 内 `if (it.disabled) return;` 注释掉 | `点置灰项关了菜单 (count=0 @1ms)`。含义: 这处防护保证置灰项点击无反应, 去掉后点置灰项会执行并关掉菜单 | 67/68 (仅 M6) | 68/68 |
| T4 | `web/src/components/Timeline.tsx` L536 onCtx 内 `if (lockedRow(r)) { toast(…); return; }` 注释掉 | `锁定轨仍可选 (menu @1ms)` (锁定轨右键弹出菜单) | 67/68 (仅 T4) | 68/68 |

注: M10 首版变异 (onClick 清空) 触发 TS6133 编译失败, dist 未变, 那次 68/68 作废, 不计入。

## e2e_placement.js (位置预设)

- 变异 a: `server/app.py` 三条 `os.replace` 注释掉 → **5/13**。P5 红 `st.ok===true …` (cur 仍 bottom-center, src default, rev 0); P6 红 `现在生效被改了`; P8/P9/P10/P12/P13 卡在 `assRev > rev0` 的 waitForFunction (30s 超时); P11 10s 超时。没有走到 IoU / closer 断言, closer>150 只作二级兜底 (见 e2e_placement.js L132-134 注释)。恢复后 13/13。
- 变异 b: `Monitor.tsx` 中 `(x0 + k.dx)` 改为 `(x0 + 0)` → **9/13**。P2 `预览没右移: 原 387,825,1614,1033 预览 387,825,1614,1033`; P8 `IoU 0.205 < 0.70`; P9 `IoU 0.416 < 0.70`; P10 `IoU 0.435 < 0.70`。P7 不检查位置 (已知盲区)。恢复后 13/13。
- 变异 c: `PlacementPanel.tsx` L57 place-order 的 onClick 置空 → 首次 **12/13** (仅 P10 红, P11-P13 当时都用默认 jp_top, 无覆盖)。
- P13 补强: `gapCase` 增加 order 参数, P13 改用 `cn_top` (中上日下, 非默认); 因此 P11 回 jp_top 也成了真切换。补强后变异 c 重验 → **11/13**, P10 与 P13 红 `page.waitForFunction: Timeout 10000ms exceeded`。P11 在该变异下仍 OK, 所以 P11 的真切换只在正常代码下成立, 对 onClick 置空的捕获来自 P10 与 P13。恢复后 13/13。
