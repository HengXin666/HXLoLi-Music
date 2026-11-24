# Agent Note: 卡拉OK 作品设计圣经 + 整曲方向 + 换番名检查 + 落地追溯

Status: implemented

Decision-ID: karaoke-design-bible

## Code

- `.agents/skills/hx-anime-karaoke-ass/scripts/judge/c_bible.py`
- `.agents/skills/hx-anime-karaoke-ass/scripts/source/bible_skeleton.py`
- `.agents/skills/hx-anime-karaoke-ass/scripts/gate/check_gates.py`

## Problem

硬规则 4 / 4b 要求考据与 song-brief, 但产物是人读的 markdown. 元素表不区分官方设定, 原作原文与社区共识, 也不写 "这个符号换个番名还成不成立". 构想到代码之间没有中间表示, agent 写到中段就退化成按词义画图形. 用户 2026-11-17 要求升级为结构化的作品设计圣经, 发散整曲方向, 加换番名检查, 并在任务一的两首歌上落实.

## Decision

- 新增第 11 步 `11-design-bible`: `proj/bible/` 下 symbols / characters / scenes / lyric-map 四份 JSON. 来源分四型 (official / original / community / screen), 符号标专属度 0..3. 专属 (>=2) 要有官方或原作来源, 只有社区来源时至少 3 个; 只有画面证据的符号有效专属度按 1 算.
- 新增第 39 步 `39-directions`: 2-3 套整曲方向, 每套写母题, 运动语言, 色彩 (每色有出处), 字体气质, 高潮段处理. 换番名检查是机械的: 专属母题少于 2 个, 不到一半, 或高潮没用专属母题, 即判 "换掉番名仍成立". 自评与机械结果矛盾判 FAIL.
- 第 49 步之后登记 `bible/landing.json`: 符号 -> fx 函数 (源码里存在, 函数体含 marker) -> 句 (manifest 或设计表绑定, 认一层间接调用) -> 可选 out.ass 命中. 至少 3 个专属符号走通.
- 盲审 `blind_bible.py`: 去名盲审包 (real) 与通用化反例包 (decoy), 多个独立审稿人答题, 计认出率. 阈值 `THRESHOLD = None`, 未标定只报 WARN; `--calibrate` 只在正例最低认出率高于反例最高认出率时给阈值建议.
- `check_gates.py --stage design` 并入第 11 与 39 步判据; 旧工程没有 `bible/` 报 WARN, `--strict-design` 报 FAIL.
- 步骤契约, 格式文档, 空模板: `steps/3-anime-bg/11-design-bible/`, `steps/4-kfx/39-directions/`, `templates/bible/`; 硬规则加 4e.

## Alternatives considered

- 什么都不做 / 复用现有方案: 继续只靠 `anime.elements.md` 的自由文字和盲审. 否决: 意象出处追溯不到, 换个番名也能过, 正是本决策要解决的问题.
- 在 `anime.elements.md` 表格里加列: 否决. markdown 表格没法被代码引用, 落地追溯做不了.
- 专属度由模型打分: 否决. 用户点名这项不稳定. 改为人工标注 + 来源规则拦截 + 机械换番名检查, 模型只在盲审里用, 且多轮取一致.
- 盲审认出率直接定阈值 (例 0.67): 否决. 违反硬规则 10b; 实测两首成品分不开 (见下).

## Consequences

- 2026-11-18 两首成品 (無職転生 オンリー, ブラック・ブレット トコハナ) 的圣经与落地登记写在各自 `dev/<番名>/<曲名>/bible/`. `check_bible.py` 两首 0 FAIL; 落地专属符号 オンリー 3 个, トコハナ 5 个. `selftest_bible.py` 合格版 0 FAIL, 17 个反例逐一 FAIL.
- 盲审 (每包 3 个独立审稿人, 禁用工具): オンリー real 3/3, decoy 0/3; トコハナ real 0/3, decoy 0/3. 正例最低 0 不高于反例最高 0, 没有区分能力, THRESHOLD 保持 None. 第一版 decoy 把 "来源不足而降级" 的符号也当通用件, 实测 3/3 认出, 已改为只用 unique=0 的符号.
- トコハナ 机械判据全过但盲审认不出: 落地的专属符号 (红眼, 黑碑, 观测球, 莲) 写成图形描述后不足以指认作品. 这正是换番名检查管不到, 要靠盲审补的那一块.
- オンリー 的 `p32` (洛琪希尖帽) 不在 manifest 的直接绑定里, 经 `fx_echo_reach` 间接调用; 追溯链因此支持一层间接调用. 原本主母题之一的艾莉丝红发已在 2026-11-12 从 `fx_sword_cut` 删除, 不再登记.
- 本地没有跑 `hx-agent-notes` 的红线校验 (工具在用户机器上); `templates/`, `steps/` 下的文档与 JSON 属非 AST 资源, 会报 resource-review.
