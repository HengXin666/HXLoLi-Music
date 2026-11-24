# Agent Note: 验收台多工程 (一个服务挂全部歌) + 实时重建

Status: implemented

Decision-ID: karaoke-studio-multi

## Code

- `.agents/skills/hx-anime-karaoke-ass/scripts/studio/server/hub.py`
- `.agents/skills/hx-anime-karaoke-ass/scripts/studio/web/src/lib/base.ts`

## Problem

用户 2026-11-24: 几首歌并行做, 验收台一次只能看一首 (一首一个端口一个进程, 5398 / 5399 ...); 实时加载效果差.
实测找到的原因:
- 设计稿面板保存几乎必然 409 "设计稿在别处改过了": 服务端下发 `st_mtime_ns` 数字 (约 1.8e18, 超过 2^53), 浏览器 JSON 解析丢精度, 回传后永远对不上.
- kfx 模块在台子进程里 import 一次: 改了动作表要重启台子, 台子一停用户就看不了.
- 前端为了找 `\1img` 贴图把整份 ASS (10-20 MB) 再下载一遍再扫.

## Decision

- 一个服务挂 `dev/<番>/<歌>` 全部工程 (`--root`, 不给 `--project` 时默认), 首页列表 (成品, 大小, 改于, 在看人数, 最近重建, 待重建), 每首歌地址 `/s/<番>/<歌>/`. 服务端按前缀选工程 (线程局部), 前缀之后的接口与单工程完全相同; JSON 里的地址服务端加前缀, 前端 `lib/base.ts` 给写死的 `/api` `/media` 补前缀. 单工程 `--project` 照旧可用.
- 设计稿解析与重建放子进程 (`design_cli`), 每次用磁盘上最新的 kfx 代码, 不用重启. 解析结果按 (设计稿 mtime, 代码签名) 缓存.
- 有人在看的歌 (`/api/watch` 连着), 设计稿比成品新就后台自动重建 (单飞, 原子替换, 失败不动旧成品并在面板顶上报错). 只改了 kfx 代码默认不自动重建 (几首歌共用 kfx, 做 A 歌的改动不能悄悄改掉已认可的 B 歌成品), 首页标「待重建」+ 按钮; 工程 `studio.json` `"auto_rebuild": "all" | "design" | "off"` 可改.
- 设计稿 mtime 以字符串下发与比对.
- 新接口 `/api/imgrefs` 返回贴图清单, 前端没有贴图就不再整份重下 ASS.

## 追加: 2026-11-24 晚 首页重做 + 没有视频也渲染 + 发布库

- 首页 (`server/hub_index.html`) 重做: 工程卡片 (成品, 大小, 多久前, 在看, 重建状态与错误, 待重建) + 发布库 (static/music 按番分组, 标来源: 人做 / AI assfx / AI kfx / 草稿 / 带模板源码) + 搜索.
- 发布库的 ASS 可以直接打开 (`/s/static:<番>/<文件名>/`, `StaticProject`): 只读, 音频取同名文件, 批注写到 `dev/review/static/`, 不往发布目录写.
- 没有片源时监视器画中性暗底 + 角标, 字幕照常渲染.
- 修 worker 崩溃 (FS error): SubtitlesOctopus 预载字体命名 `font<i>-文件名`, 按名懒加载命名 `font<自增>-文件名`, 两套编号撞名就写同一个文件. 罪恶王冠 一打开就崩 (与有没有视频无关). 字体已整批预载, `availableFonts` 改传空.
- 后备字体给能显示中日文的 (NotoSansSC / 霞鹜文楷), 人做的老 ASS 用的商用字体本仓库没有, 原来会画成方块.
- 歌词面板在没有单元清单时依次退回: timing.json 逐字时间 -> ASS 里 Effect=karaoke 的源句 (去掉 `|<` 振假名写法) -> 按事件拼 (JP/CN 样式事件最多的一层, 按名字或开始时间分句, 同字近距离重复去掉).
- 不是本 skill 格式的 ASS 没有特效画像: `/api/profile` 回 404 而不是 500, 前端不再因此整个初始化失败.

## Alternatives considered

- 什么都不做 (继续一首一个端口): 最强理由是现有台子能用, e2e 有一套. 否决: 设计稿面板保存本来就坏 (409), 改动作表要重启, 并行几首歌要记几个端口; 这三件都是用户这次点名的问题.

- 每首歌继续一个端口, 写个启动脚本批量起: 最强理由是零改动. 否决: 改动作表仍要逐个重启, 端口要记, 用户要的是一个入口.
- 在台子进程里 `importlib.reload` kfx 模块: 否决. kfx 模块之间互相 import, reload 顺序错了会出现新旧代码混用, 出错难查; 子进程每次约多 0.3 s, 换来确定性.
- 代码一改所有在看的歌都自动重建: 否决 (见上, 会悄悄改掉别的歌已认可的成品).

## Consequences

- 以后只开一个台子 (默认 5390), 不再按歌分端口; skill 文档里的「改了动作表重启验收台」作废.
- 每次解析 / 重建多一个子进程启动 (约 0.3 s).
- 自动重建会改写工程里的 `out.kfx.ass` (只在设计稿比成品新且有人在看时); 已认可的成品靠 `saved-*` 快照与 static 副本兜底.

## Verification

- 假根 (两首歌的副本) 上 playwright: 首页两首, 两个标签页同时打开都就绪且无 4xx/页面错误; 面板 PUT 设计稿 200 (原来 409); 外部改设计稿后约 2.4 s 监视器重取新成品.
- `test_review.py` 7 项, `test_ref.py` 10 项通过; `tsc --noEmit` 通过. `e2e_ui.py` 在改动前后都在同一处崩 (route 回调 TargetClosed), 与本改动无关.
