# Agent Note: 验收台 "看, 挑, 改, 证" 闭环 (候选挑选冻结, 对比对象退化, 工程元数据, 标注处理状态)

Status: implemented

Decision-ID: karaoke-station-loop

## Code

- `.agents/skills/hx-anime-karaoke-ass/scripts/accept/cands.py`
- `.agents/skills/hx-anime-karaoke-ass/scripts/assfx/layer/manifest.py`
- `.agents/skills/hx-anime-karaoke-ass/scripts/studio/server/loop.py`
- `.agents/skills/hx-anime-karaoke-ass/scripts/studio/web/src/components/LoopPanel.tsx`
- `.agents/skills/hx-anime-karaoke-ass/scripts/studio/web/src/lib/actions.ts`

## Problem

验收台只能 "看与标": 换一个构想要 agent 离台手改, 用户没法并排挑; 没有参考 ASS 的新歌对比按钮直接停用; 台子里有 オンリー 专属默认值 (片源 `source/ed1_creditless.mp4`, 视频偏移, 字身层写死 2 即 TEXT_LIFT=0, e2e 写死 L03 / こわ / fx_bed / 42s); `review.jsonl` 的标注落到 issues 后用户看不到处理到哪一步. 2026-11-17 在 ヨスガノソラ 两首新工程上跑旧 e2e_ui 只过 67/84, 其中振假名 / 字框 / 中文全读不到 (缺省 TEXT_LIFT=20 的工程字身在 22 层).

## Decision

- 候选: `accept.py cands` 只重跑本单元 (`gen.py` 的 `ASSFX_ONLY`) 出 2-3 个, 换配方优先、同配方 salt 交错, 跳过构想记录里出现过的; `pick` 把选中参数写进 `review/accept/picks.json` (accept 重跑经 `ASSFX_OVERRIDES` 喂回), 整首重跑过 G2 三条 + 隔离核对 (本单元 == 候选快照) 才冻结; 未选进 `ideas.jsonl`. 细节 `steps/5-verify/12-station/impl/cands.md`
- 标注处理状态: `review.jsonl` 每条带 `status` 与 `changes`, 由 `accept/reviewlog.py` 按 issues 回写 (只改目标行, 坏行字节不变); 台子写入时给 `open` / `noted`
- 对比对象退化: 用户选 > 参考 ASS > 上一版 (`review/accept/prev.ass`, accept build 前留) > 无; 门禁阈值只认参考 ASS. 对比按钮、角标、检查器都写对比对象的名字
- 工程元数据: 片源与偏移读 `studio.json` / `mv.edl.json` / `base.mp4`; 清单 `meta.text_lift` (gen.py 写) 定字身层, 老清单按 ly: 最小层号推; 振假名 / 中文只认静止 `\pos` 事件; 自定义样式按 Name 前缀归轨
- 没有音频的工程: 时钟用墙钟走 (`lib/clock.ts`), 播放选区 / 循环照常
- e2e_ui 测试句与期望值从工程数据取; check_viewports 取样时刻取一句歌词中间; 新增 `e2e_loop.py` 在工程副本上跑闭环全程
- 台子不在服务进程里改工程: `/api/loop/*` 后台单飞调 `accept.py`, 与位置预设共用生成器锁

## Alternatives considered

- 什么都不做 / 复用现有 (agent 离台改, 用户看完再说): 最强理由是不动前端, 回归面最小. 否决: 用户要在台上并排挑, 且无参考的新歌根本没法对比, オンリー 默认值让新工程的振假名和字框直接丢失.
- 候选整首重跑: 实现最简单, 与正式输出天然一致. 否决: 慢的工程每个候选要整首时间; 改为只重跑单元, 再用 pick 时的整首重跑 + 隔离核对证明一致.
- 选中候选直接把候选 ASS 贴进 raw: 快. 否决: 下次重跑生成器就丢; 写 picks.json 让生成器自己出, 才可复现且 G2 有效.
- 对比上一版用 git: 否决, 工程目录不进库 (hard-rules 第 11 条); accept build 自己留 prev.ass.

## Consequences

- 2026-11-18 沙箱 (aarch64 chromium): selftest_accept 51/51, selftest_selfreview 25/25; e2e_loop 比翼の羽根 (有参考) 6/6, ピンキージョーンズ (无参考无音频, 对比上一版) 6/6. e2e_ui / check_viewports 结果见交付说明
- `review.jsonl` 多了 `status` / `issue` / `changes` 字段; 老记录读出时补默认并标 `status_src: default`
- 清单多了 `meta`; revision 不含它, 老清单不受影响
