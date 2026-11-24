# Agent Note: studio 轨头眼睛的语义 (只给对监视器真有作用的轨)

Status: implemented

Decision-ID: karaoke-studio-track-visibility

## Code

- `.agents/skills/hx-anime-karaoke-ass/scripts/studio/web/src/lib/tracks.ts`
- `.agents/skills/hx-anime-karaoke-ass/scripts/studio/web/src/components/Timeline.tsx`

## Problem

用户 2026-11-11 反馈: "所谓的不可见竟然对MV等轨道不生效". 实查: 每条轨头都有眼睛, 但只有 `FILTER_IDS` (jp/rb/cn, fx0-8, card) 进 `filterAss`; mv/wave/beat/density 的眼睛只把时间线画暗, 监视器画面不变; review (标注) 的眼睛连时间线都不改. 用户看到的是"开关", 实际什么都没关.

## Decision

- 判断 (用户定): 轨头眼睛只给"对监视器画面真有作用"的轨. 纯时间线轨 (波形/节拍/密度/标注) 对画面没有任何影响, 给眼睛就是骗人, 直接不渲染眼睛按钮.
- `TrackDef` 新增 `eye?: boolean` (有眼睛但不进 ASS 过滤) 和 `hasEye()`; 眼睛按钮只在 `filter || eye` 时渲染.
- MV 改成真开关: 眼睛关掉, `Monitor` 的两个 `<video>` (成品框和参考框) 都设 `opacity: 0`, 只留字幕; 带 `data-mv-off` 与 `data-testid=video-out/video-ref` 供 e2e 断言.
- 同目录的 `components/Monitor.tsx` 一并改 (代表文件为 `Timeline.tsx`).
- 用 opacity 不用 visibility: `useVideoSync` 每帧按 EDL 改写 `video.style.visibility`, 用 visibility 会被覆盖.
- 波形/节拍/密度不再按 `vis.eye` 画暗: 没有按钮就改不回来, 旧 localStorage (`hxstudio.vis`) 里残留的 `eye:false` 不许把它们留在变暗状态.
- 纯时间线轨原本就没有锁按钮 (锁只给 filter 轨), 本次不新增.

## Alternatives considered

- 什么都不做 / 复用现有方案 (保留眼睛, 只让它把时间线变暗): 最强理由是改动最小、轨头整齐. 否决: 用户点眼睛预期的是画面变化, 只变时间线就是假开关.
- MV 眼睛用 `display:none` / 卸载 `<video>`: 否决. 卸载会丢解码状态, 重开要重新 seek; opacity 保持同步, 切换无延迟.

## Consequences

- 2026-11-11 实测 (1920x1080, 70.5s): MV 关掉后监视器 99.6% 像素变化 (平均亮度 1.6), 再打开与关前逐像素一致; jp/cn/fx0/fx7 眼睛照旧生效 (保留条数 10208 -> 6806 / 7922 / 8833 / 9443); wave/beat/density/review/ruler/overview 眼睛按钮 0 个. 对照图在工程 `review/vis/` (dev 下, 不入库).
- studio e2e_ui 68/68, e2e_placement 13/13, 九视口 9/9 零滚动条, 均不退.
- 以后新增轨: 对监视器没作用就不要给 `filter` 或 `eye`.
- 2026-11-18: 工程自定义样式 (如 比翼の羽根 的 `NAME`) 原来 `trackOf` 返回 null, 眼睛 / 独显永远藏不掉它 (e2e 字层 8644 != 8642); 改为按 Name 前缀 `ly:/fx:/card:` 归轨. 无音频工程的时钟改走墙钟 (`lib/clock.ts`), 见 `.agents/notes/implemented/feature/2026-11-17-karaoke-station-loop.md`.
