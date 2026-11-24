# Agent Note: 卡拉OK 特效只留一个生成器 kfx, 以 オンリー v2.1 为金样

Status: implemented

Decision-ID: karaoke-kfx-single-generator

## Code

- `.agents/skills/hx-anime-karaoke-ass/scripts/kfx/kfx_build.py`
- `.agents/skills/hx-anime-karaoke-ass/scripts/assdoc/design.py`
- `.agents/skills/hx-anime-karaoke-ass/scripts/studio/server/app.py`

## Problem

scripts/kfx 里同时躺着 hx-kara 2 到 13, pvfx, kfx3 和 kfx3 v4/v5 十几套生成器, 旁边还有一个独立的 hx-kfx skill, 触发词相同. SKILL.md 推荐的是 kara4, 用户认可的却是 kfx3 v2.1. 每个新会话挑一套或再写一套, 效果不稳定, 同样的坑反复踩.
用户认可的 out.v21.ass 已经不能由代码重现: v2.1 之后 verbs 和 scene 又被改过, design.v21.md 用当时的代码跑会报错.
踩过的坑 (越出歌词框 5%, 闪烁 / 旋转 / 穿字线, 字外物象看不懂) 只写在聊天里, 没有任何检查会失败.
验收台的设计稿面板用 assdoc/design.py 的另一套格式, 和 kfx 设计稿对不上, 保存后也不重建.

## Decision

- 生成器只剩 kfx (由 kfx3 v2.1 的代码改名拆分而来, 每个文件 300 行以内): 设计稿 design.md + 动作表 -> out.kfx.ass. 删除 karaN, pvfx, kfx3_*, mkplan 和旧对比产物. 独立的 hx-kfx skill 的 SKILL.md 改成停用说明 (不再被触发, 指向 kfx); 它的代码有 6 篇存量 note 引用, 暂留.
- 金样 examples/mushoku_ed1/kfx: design.md (v2.1 去掉 物象 字段) + lyrics.txt + timing.json, 用 skill fonts 重建必须逐字节等于 out.v21.ass (md5 3477cb23803a5d6acd197d0eeafda79a). kfx_test.py 核对; 金样只在用户认可后 --bless.
- 坑写成会失败的检查: kfx_design.validate 拒绝未知字段 (物象), 意境里的禁用词, 未知动作, 下限不足; kfx_check.py K1 非标准标签 / 一次 \t 转 >= 90 度 / 1 s 内 alpha 来回 >= 4 次, K2 实渲染: 所有像素在歌词并集框外扩 5% 内, K3 事件名只能是 ly:Lnn fx:Lnn fx.
- 验收台: assdoc/design.py 变成 kfx 设计稿的视图 (解析与校验只在 kfx_design.py), PUT /api/design 保存后单飞重建 out.kfx.ass (约 1.4 s), 失败不动旧成品; 监视器靠已有的 /api/watch 热更新.

## Alternatives considered

- 什么都不做, 只在 SKILL.md 写 "推荐 kfx3": 最省事, 不碰用户的 WIP. 否决: 旧生成器还在, 文档已经推荐过 kara4 照样被绕开; 不能重现 v2.1 的问题也不会消失.
- 复用现有的 kara4 (SKILL.md 当时的推荐): 有门禁和预览脚本. 否决: 用户认可的是 kfx3 v2.1, kara4 的效果用户没有认可.
- 复用 hx-kfx skill: 有成套 references. 否决: 它自己写明已被 hx-kara 取代, 读不了新方向文件.
- 旧生成器移到 archive 目录: 万一要翻回来方便. 否决: 用户要求直接删; 仓库规则禁止新建 archive; 历史由 Git 和仓库外的私有快照保留.
- 门禁按每帧歌词框算: 更严. 否决: 换行时旧句收走、框缩小, 合格的 v2.1 也会报错; 用户截取的是固定歌词区.

## Consequences

- 新歌只写 design.md, 不改代码; 效果不够时给 kfx 加动作并过金样.
- 依赖旧生成器方向文件的工程 (direction.kara*.json, direction.pv.json, design.v4/v5.md) 不能再出片; 产物文件仍在工程里.
- 验收台要用 --ass out.kfx.ass 启动才会保存即重建.
- hx-kfx skill 目录仍在, 只是停用; 彻底删除要同时处理引用它的存量 note.
- 旧逐句 fx 流程 (assfx 库 + make_ass.py) 仍在, 文档已标为只维护旧工程.
