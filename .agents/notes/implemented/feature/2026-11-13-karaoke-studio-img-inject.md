# Agent Note: studio 自己把 \1img 贴图注入 libass worker, 缺图显示成 partial

Status: implemented

Decision-ID: karaoke-studio-img-inject

## Code

- `.agents/skills/hx-anime-karaoke-ass/scripts/studio/web/src/lib/octopus.ts`

## Problem

2026-11-13 用户反馈: オンリー 212s 左下有一个白框. 命令行 `render/render_octopus.py` 出的帧正常, studio 监视器里不正常. 两边用的是同一份 `out.ass`.

根因: `render_octopus.py` 在渲染前把 ASS 里 `\1img(...)` 引用的图片拷进 libass 的工作目录; studio 的 `createOctopus()` 只给 worker 传了 canvas / subUrl / workerUrl / 字体, 没有把图片写进 worker 的虚拟 FS. libass (vsfiltermod) 打开不了图片时只打一条 `Failed to load image ... (can't fopen)`, 然后照常用 `\1c` 去填 `\p1` 矩形. 白框就是 p31 手那张图 (96x77) 的矩形被 `\1c&HFFFFFF&` 填满了. 磁盘和 ASS 都没有问题, 缺的是浏览器端这一步; 界面上也看不出任何异常 (`octo` 显示"就绪").

## Decision

- 服务端 `app.py` 加 `GET /api/img/{out|ref}/<相对路径>`: 按对应 ASS 所在目录解析路径 (与 `render_octopus.py` 的口径一致), `realpath` 不许出该目录, 文件不存在返回 404.
- 前端 `octopus.ts`: `imgRefs()` 从 subUrl 内容里正则取出 `\[1-4]img(...)` 的引用 (跳过 `data:`、`!`、`$`); 在 worker `onReady` 里逐张 fetch, 用 `writeFile` 写进虚拟 FS, 写完再 `setTrack` 重载 (只写不重载, libass 不会重新去找图), 全部处理完才回调外层的 onReady.
- 逐张独立 (每张单独 try): 取到的照写, HTTP 失败或网络失败的进 `missing`. 3 张坏 1 张时, 另外 2 张照常显示, 不会整批退化成色块.
- 缺图不能静默显示"就绪" (用户定): `store.octo` 新增 `'partial'` 状态, 并加 `octoMissing`; `Monitor.tsx` 有缺图就把状态设成 partial, `octoErr` 写"贴图缺 N 张: 路径 (HTTP 404)". `TopBar.tsx` 的 libass 标签 (`data-testid=octo-chip`) 显示红字"缺图 N 张", 鼠标悬停 (title) 列出缺的路径.
- partial 不等于 ready: 等 `ready` 的 e2e 遇到缺图会超时, 这是有意的, 带缺图的状态不应该混过测试.
- 服务端 `server/app.py` 的 `/api/img/` 接口同一次提交 (它的主笔记是 `2026-11-09-karaoke-studio.md`, 未改). 同目录的 `lib/store.ts`、`components/Monitor.tsx`、`components/TopBar.tsx` 一并改 (代表文件为 `octopus.ts`).

## Alternatives considered

- 什么都不做 / 复用现有方案 (让用户以命令行渲染为准, studio 只当预览): 最强理由是零改动, 磁盘产物本来就对. 否决: studio 是老板看帧的地方, 预览错了就是在错的画面上做审美判断, 而且错得没有任何提示.
- 服务端加 `/api/images` 接口扫描 out.ass 返回列表: 可行, 但前端本来就拿得到 ASS 内容, 再开一个接口就多一份要和 ASS 保持一致的状态. 选了前端正则.
- `Promise.all` 一次性注入: 否决. 一张失败整批都不写, 坏 1 张会让 3 张全变色块.
- 缺图时直接把 `octo` 设成 `error`: 否决. 画面其实已经渲染出来了, 只是缺几张图; 设 error 会让人以为整个 libass 挂了, partial 更准确.

## Consequences

- 2026-11-13 实测 (オンリー 212.0s, 关掉 MV 只看字幕): 修复前左下区域白像素 1320, 修复后 1. 变异: 拦截所有 `/api/img/` 请求, 白框重现 (1320); 恢复后 1.
- 第 2 层变异 (只让 `hand_palm_01` 返回 404): 两张剑图照常注入 (200), 199.2s 剑区红像素 95, 与正常组相同; 顶栏显示"libass 缺图 1 张", 颜色 rgb(239,107,107); `octo=partial`. 正常组显示"libass 就绪", 颜色 rgb(89,195,138). 截图在工程 `review/vis/l2_*` (dev 下, 不入库).
- 还没做: `validate_ass` / render 遇到找不到的 `\1img` 图报 E 的门禁 (另做).
