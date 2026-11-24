# Agent Note: kfx 罪恶王冠 动作 (晶 虚空 王冠 差)

Status: implemented

Decision-ID: kfx-guilty-crown-verbs

## Code

- `.agents/skills/hx-anime-karaoke-ass/scripts/kfx/kfx_verbs_gc.py`

## Problem

用户 2026-11-24: 把 罪恶王冠 OP2 当新歌用 skill 从头做一遍 (旧版是 AI 第一代 assfx, 光晕 + 浮尘, 看不出是哪部番). reference-library 的结论: 人做的歌一首一个贯穿全曲的主题物件框在句子上, 分段换色, 词级意象只给少数词, 要有一道主菜.

## Decision

- 4 个新动作, 全部出自这部番 (出处写在 docstring): 晶 = 句子两端的病毒结晶 (主题物件, 每句一次, 小节头亮, 出场碎), 虚空 = 从 "胸" 里拔出 ヴォイド 的剑 (主菜, 歌词 胸の中にある x4), 王冠 = 罪の王冠 画在注音上方戴下去 (只 2 处), 差 = いのり 的红 (荒木访谈 青的世界里唯一的差し色).
- 全部 late 回调按字真实位置画, 上沿不超过注音上方 + 40 px (kfx_check K2 的允许框比 P['box'] 更紧), 剑与光带只在分开的缝里, 不压字.
- 虚空 用 piece 竖切: `piece` 的半平面保留 n.p <= off, 左半是 (1,0,0); 写反了两半会交叉成一条细缝 (2026-11-24 第一次渲染就是这样).
- 没有改任何旧动作, オンリー 金样逐字节不变 (kfx_test ALL PASS).

## Alternatives considered

- 什么都不做 / 复用现有方案: 只用已有动作 (斩 齐舞 虹 等) 做这首歌. 否: 那些是别的歌的主菜, 用户 2026-11-24 要求元素出自这首歌, 不借别歌动作.

- 剑横着拔出: 会穿过两边的字, 否.
- 王冠每句都戴: 变成装饰, 否; 只给 支配され 和 その罪を.

## Consequences

- 罪恶王冠 工程 (dev/罪恶王冠/The Everlasting Guilty Crown) 用 kfx 重做, 旧 assfx 成品与生成器在 `backup-2026-11-24-assfx/`.
- 别的歌可以用这 4 个动作, 但它们来自这部番; 不是这部番的歌不该用 (skill 第 1 条: 换到别的歌也成立的意象不算意象).
- 首页会把用 kfx 的其它歌标「待重建」(代码签名变了); 它们不用这些动作, 重建结果不变.
