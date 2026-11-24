# Agent Note: studio 暂停后视频不停

Status: implemented

Decision-ID: studio-pause-video-sync

## Code

- `.agents/skills/hx-anime-karaoke-ass/scripts/studio/web/src/lib/clock.ts`
- `.agents/skills/hx-anime-karaoke-ass/scripts/studio/web/src/components/Monitor.tsx`

## Problem

用户 2026-11-19 实测: 点暂停后监视器视频画面还在动. `Monitor.tsx` 的 `useVideoSync` 只靠 `clock.subscribe` 逐帧回调去 play/pause 视频, 而 `clock.ts` 的 rAF 环只在 `t()` 变化时回调. 播放中 800ms 回调 38 次, 暂停后 1.2s 只 1 次; 暂停那一刻 t 若没变 (静音工程 silentAt 路径, currentTime 精度截断), 回调为 0, video 永远停不下来.

## Decision

- `clock.ts` 加 `subscribeState(f)` 播放状态订阅 (订阅时立即回调一次) 与私有 `kick()`: 音频 play/playing/pause/ended/seeked 事件 (静音工程由 play()/pause() 自己派发) 与 `play()` 的 promise 落定, `pause()` 调用本身都同步走 `kick()`, 状态变化通知状态订阅者, 并不论 t 是否变化把当前 t 推给全部逐帧订阅者一次.
- `Monitor.tsx` 的 `useVideoSync` 把同步逻辑抽成 `sync(t)`, 同时挂逐帧订阅与状态订阅; 状态变为暂停时先无条件 `v.pause()` 再同步; 另监听 video 自身的 play/playing, 时钟未在播时立刻拉回暂停 (兜住晚到的 `v.play()` promise).
- 回归: `scripts/studio/server/e2e_pause.py` + `e2e_pause.js`, 真 chromium 点播放/暂停 N 轮, 要求暂停后 `video.paused === true` 且 1.5s 内 currentTime 不前进.

## Alternatives considered

- 什么都不做: 有音频的工程碰巧能停. 否决: 静音工程和精度截断时必现, 用户已复现.
- rAF 环每帧无条件回调: 最强理由是改动一行. 否决: 所有订阅者 (libass setCurrentTime, 时间线, 歌词) 暂停时也每帧空转, 浪费且掩盖 "状态变化" 这个真正的触发点.
- 只在 Monitor 里监听 `clock.audio` 的 pause 事件: 否决: 静音工程与 `pause()` 同步语义都绕不过 clock, 状态应由 clock 统一发.

## Consequences

- 订阅者在 play/pause/seek 时会多收到一次相同 t 的回调, 订阅者需幂等 (现有的 setCurrentTime / 视频同步都是).
- `web/dist` 重建: `assets/index-Db9ajxHr.js`, `assets/index-BjshpjrH.css`; 旧 `index-B4LIslik.js` / `index-GSzkAqGN.css` 已不被 index.html 引用.
- 验证 (2026-11-19, 沙箱 chromium, webm 片源): 有音频与静音两种工程各 5 轮暂停均 PASS; 旧构建在静音工程上视频根本不跟时钟起播.
