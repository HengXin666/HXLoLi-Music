# HX ASS Studio (scripts/studio)

阶段 D 骨架 (plan.md 3.1-3.4, 3.8). 只读成品, 不改 scripts/assfx 与生成器.

- server/app.py: 标准库服务.
  多工程 (默认): `python3 scripts/studio/server/app.py --port 5390` -> 首页列出 dev/<番>/<歌> 全部工程, 每首 `/s/<番>/<歌>/` (前缀之后的接口与单工程相同, JSON 里的地址服务端已加前缀, 前端 `lib/base.ts` 补写死的地址). 规则见 `server/hub.py`.
  单工程: `python3 scripts/studio/server/app.py --project dev/<番>/<歌> --port 5199`
  设计稿解析与重建在子进程 (最新 kfx 代码, 不用重启); 有人看时设计稿一改自动重建; 设计稿 mtime 以字符串下发 (ns 超 2^53, 数字会丢精度导致保存 409).
  `/api/imgrefs` 给 \\1img 清单, 前端不再为找贴图整份重下 ASS.
  接口: /api/project /api/ass/{out,ref} /api/lyrics /api/events /api/profile /api/peaks /api/edl (GET/PUT)
  /api/review (GET/POST) /api/watch (WebSocket) /media/<repo 相对路径> (Range) /octopus/* (定制 libass, 与 render_octopus 同一份) /fonts/*
- web/: React 19 + TS 5.6 + Vite 6 + zustand 5. `npm --prefix scripts/studio/web install && npm --prefix scripts/studio/web run build`
  开发: 服务起在 5199 后 `npm --prefix scripts/studio/web run dev` (5198, 代理到 5199).
- server/check_viewports.py: 9 种视口 x DPR 验收 (零滚动条, canvas 像素 = CSS x DPR, libass 出帧).
- server/loop.py: 看, 挑, 改, 证 (对比对象 参考/上一版/候选, 候选生成与挑选冻结调 accept.py, 标注状态). 接口 /api/loop /api/loop/{cmp,cands,pick} /api/ass/{cand,prev}
- server/e2e_loop.py: 候选闭环在台上的全程验收 (工程副本上跑). 契约见 steps/5-verify/12-station/index.md "候选闭环"
