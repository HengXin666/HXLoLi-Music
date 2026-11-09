# HX ASS Studio (scripts/studio)

阶段 D 骨架 (plan.md 3.1-3.4, 3.8). 只读成品, 不改 scripts/assfx 与生成器.

- server/app.py: 标准库服务. `python3 scripts/studio/server/app.py --project dev/无职转生/オンリー --port 5199`
  接口: /api/project /api/ass/{out,ref} /api/lyrics /api/events /api/profile /api/peaks /api/edl (GET/PUT)
  /api/review (GET/POST) /api/watch (WebSocket) /media/<repo 相对路径> (Range) /octopus/* (定制 libass, 与 render_octopus 同一份) /fonts/*
- web/: React 19 + TS 5.6 + Vite 6 + zustand 5. `npm --prefix scripts/studio/web install && npm --prefix scripts/studio/web run build`
  开发: 服务起在 5199 后 `npm --prefix scripts/studio/web run dev` (5198, 代理到 5199).
- server/check_viewports.py: 9 种视口 x DPR 验收 (零滚动条, canvas 像素 = CSS x DPR, libass 出帧).
