# Agent Note: hx-kfx v2, 方向文件驱动的字幕组级卡拉OK 特效歌词

Status: implemented

Decision-ID: hx-kfx-v2-direction-engine

## Code

- `.agents/skills/hx-kfx/scripts/kfx_build.py`

## Problem

用户 2026-11-20: 验收台与 skill 产出的 ASS 歌词 "全部垃圾, 没法看", 要求以 無職転生 ED1 为蓝本全部推翻重做 hx-kfx. 目标: 中日双语, 日文汉字逐拍注音, 卡拉OK 逐拍点亮, 特效贴合 MV 场景, 情感, 番剧背景, 作者意图与歌曲意境, 达到字幕组 PV 级.
hx-kfx v1 (归一化安全区 + 16 种母题按语义表随机挑 + 每字等长事件) 只约束 "不越界", 产物没有注音, 没有翻译, 母题与画面和词义无关.

## Decision

- 推翻 v1. 新模块 `scripts/kfx_*.py` (hxoa 不能建目录, 故平铺在 scripts/ 下): lyrics (注音标记 + 音拍时间), layout (真实字形宽度, libass 字号按 winAscent+winDescent 换算, 实测 < 1%), fx_text (每单元 光晕 / 未唱 / clip 擦亮 / 起音光 四层, 振假名逐音拍点亮, 中文跟进度点亮且与日文关键词同色), fx_scene (贴着音拍生的粒子 + 名场面), build (一次一行排程), check (G1-G6 门禁), preview (MV 上真 libass 抽帧联系表).
- 一首歌的全部设计写在工程的 `direction.kfx.json`: 段落 (句范围, MV 画面, why, 调色板, 进退场, 粒子), 名场面, 关键词. 生成器不自己发明任何设计; 缺 why, 未唱色太暗, 一句两段等直接退出码 2.
- 蓝本 `dev/无职转生/オンリー/direction.kfx.json` (副本在 `assets/mushoku-only.direction.kfx.json`, 单测 `scripts/test_kfx.py` 用它): 22 段跟 MV 回忆蒙太奇走 (雪 -> 风 -> 夕阳 -> 副歌红 -> 洛琪希魔法阵 -> 花园 -> 舞会 -> 天空 -> 火 -> 冰 -> 金光 -> 白场), 三次 "壊したい" 同骨架换材质, "貴方" 用一根红线贯穿.

## Alternatives considered

- 什么都不做 / 复用现有 v1: 它的门禁与归一化是完整的, 最强理由是 "已验证不越界". 但它的产物恰恰是用户说没法看的东西, 缺的是设计与双语注音, 不是边界. 否决.
- 复用 hx-anime-karaoke-ass 的 pvfx (`scripts/kfx/pv_*.py`): 最强理由是同样走方向文件, 已有 トコハナ 成品. 但它属于另一个 skill 的 49 步流程, 依赖其 calib / grid / band 产物, 用户指定要重做的是 hx-kfx; 把 hx-kfx 做成可单独运行的最小闭环 (3 个输入文件 -> 1 个 ASS -> 门禁 -> 抽帧) 更容易维护. 否决复用, 保留并行.
- 模型逐句写 fx 代码: 已在旧工程证明第 5 句之后退化成按词贴图. 否决.

## Consequences

- オンリー: `python kfx_build.py dev/无职转生/オンリー` -> `out.kfx.ass` (约 3900 事件, 1MB), `kfx_check.py --render` G1-G6 全部 PASS; 在 base.mp4 上抽帧目检过 (片头字卡, 三次副歌, 魔法阵, 红线, 白场).
- 只用标准 libass 标签 (无 `\1img` 等扩展), ffmpeg 系统 libass 与 SubtitlesOctopus 结果应一致; 定制 Octopus 未在本机核对.
- 验收台接入: `kfx_manifest.py` 写台子格式的清单 (含 cn), 生成的中文样式名用台子约定的 CN; 台子 `app.py` 加 `--ass` (默认 out.ass, 老工程不变), `analysis.py` 跟着读同一份成品; kfx 模式拒绝台上重跑旧生成器. 已在沙箱用 headless Chromium 打开台子核对: 33 句中日双语列表, JP / RB / CN 轨都有内容. 沙箱没有定制 Octopus, 监视器出字未核对.
- v1 的 `scripts/gates/`, `scripts/tools/` 与旧 references 已不再被 SKILL.md 引用. 本次通过 hxoa 无法删除文件, 待用户 `git rm`; 对应旧 note `2026-09-28-kfx-normalized-safe-area.md`, `2026-09-29-kfx-mv-driven-safe-area.md` 随之删除.
- 本机未跑 `scripts/redlines/agent_notes.py --diff`.
