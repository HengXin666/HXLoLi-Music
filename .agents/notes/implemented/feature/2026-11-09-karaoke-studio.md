# Agent Note: 卡拉OK studio 前端 (按轨看层 / 标注 / 对比参考)

Status: implemented

Decision-ID: karaoke-studio

## Code

- `.agents/skills/hx-anime-karaoke-ass/scripts/studio/server/app.py`
- `.agents/skills/hx-anime-karaoke-ass/scripts/studio/web/vite.config.ts`
- `.agents/skills/hx-anime-karaoke-ass/scripts/studio/web/src/main.tsx`
- `.agents/skills/hx-anime-karaoke-ass/scripts/studio/web/src/components/App.tsx`
- `.agents/skills/hx-anime-karaoke-ass/scripts/studio/web/src/lib/store.ts`
- `.agents/skills/hx-anime-karaoke-ass/scripts/studio/web/src/hooks/useSize.ts`

## Problem

用户 2026-11-06 至 2026-11-09 的验收反馈: 旧预览台 (`scripts/station/`) 只能锁区间, 不能按轨看层、标注、对比参考; 滚轮缩放、标注轨、轨名等交互问题在旧结构里改不动.

## Decision

- 新建 `scripts/studio/`, 取代 `scripts/station/` (已删, 未曾入库).
- server 为标准库 HTTP, 只读产物, 只写工程内 `review.jsonl` / `mv.edl.json`; 标注走 `POST /api/review`.
- web 为 React + 定制版 libass (系统 libass 会静默退化 `\1img` 等标签), 按轨分层显示, 可叠参考对比.
- 事件读写复用 `scripts/assdoc/` (见 `.agents/notes/implemented/feature/2026-11-06-karaoke-preview-station.md`).

## Alternatives considered

- 什么都不做 / 继续用 station: 最强理由是已有 75/75 的 e2e. 否决: station 不能按轨看层和对比参考, 用户验收的交互问题在旧结构里改不动.
- 直接移植 shotcraft 的 Remotion 工作台: 否决. 那套以 React 组件为单元, 这里的单元是 ASS 事件, 渲染器也必须是定制版 libass.

## Consequences

- 2026-11-09 实测: studio e2e 68/68, 九视口 (1280x720 / 1920x1080 / 2560x1440 x DPR 1 / 1.5 / 2) 9/9 零滚动条.
- `scripts/studio/web/node_modules/` 与 `dist/` 由 `scripts/studio/web/.gitignore` 忽略, 运行时由 python 服务直接发 `dist/`, 需先 `npm run build`.
- 本记录从特效门禁记录 (Decision-ID karaoke-fx-gate-studio) 拆出, 使 studio 可独立提交, 不牵动特效门禁与生成器目录.
