# Agent Note: 用 check_gates.py 把卡拉OK 流程的必做步骤变成可失败的检查

Status: implemented

Decision-ID: karaoke-hard-gates-script


## Code

- `.agents/skills/hx-anime-karaoke-ass/scripts/gate/check_gates.py`

## Problem

改这次之前，这条流水线里已经有几处写了「必做」（人工校时、注音实测、素材达标），
但它们全是正文里的祈使句：跳过之后下游产物照样生成、`validate_ass.py` 照样通过，
没有任何机制会指出是哪一步塌的。素材级的错误（用了抄错的歌词、没读设定、没看频谱）
要到成片才显形，而那时已无人回头查。

这一次新增的三步（歌词来源证据、番剧设定考据、位置对齐校准）如果沿用同样的写法，
只是把「可被跳过」的步骤从 3 个增加到 6 个。

## Decision

新增 `scripts/gate/check_gates.py`，把必做步骤落成**文件存在性 + 内容强度**两类判据，退出码非 0 即不许渲染：

- `lyrics.source.json` 存在，来源级别只能是 `network` 或 `manual`（画面截图识别不合法），
  且 `manual` 必须带 `why`（否则区分不出「查过没有」与「懒得查」）。
- `anime.background.json` 存在，且 summary 非空、角色数 ≥ `--min-chars`（默认 6） 低于此说明抓错了条目。
- `lyrics.txt` 的振假名覆盖率 ≥ `--min-ruby`（默认 80%）。
- `timing.json` 存在，且**音拍数等于 `lyrics.txt` 的音拍数**（用 skill 自己的歌词解析器算，避免两套口径）。
- `offset.json` 存在，且 `verdict` 不得是「离散度过大」（语音校准测出的时间轴差量，见歌词来源那篇 note）。
- `fixes.json` 存在；0 条修正时必须写 `_why`（表示「这轮结论是没问题」而不是「没看」）。
- `calib.json` 存在（注音高度必须实测）。

分两级：`--stage design` 只查 8b 设计之前该有的三份，`--stage render` 追加语音校准、时间轴与排版。

## Alternatives considered

- **什么都不做（继续靠正文祈使句）**: 最强理由是「这些步骤的价值显而易见，agent 会照做」。
  否决：本次改动前的行为就是证据  三处「必做」没有一处留下过可查的痕迹。
- **把门禁写进 validate_ass.py**: 最强理由是「少一个脚本，出片路径上就一个检查点」。
  否决：validate_ass 的输入是 ASS，它跑的时候歌词来源、设定考据、人工校时都已经发生过了，
  此时报错只能让人回头重做；门禁必须在**每一步之前**能被调用，所以与它分开。
- **只查文件存在性，不查内容强度**: 否决。空文件、抄错的条目、0 条修正的 fixes 都能过存在性检查，
  而这三样恰恰是最省力的作弊方式；音拍数与注音率这两个判据是机器仅有的、能咬住内容的抓手。
- **把门禁做成 pre-commit**: 否决。本 skill 是可拷贝的独立目录，工程目录在用户侧，
  钩子挂在哪不确定；把它做成一条显式命令 + 写进出片顺序，是在这个上下文里能真正生效的形态。

## Consequences

- 三个 example 工程按新规补齐证据后，`--stage render` 全部 PASSED（各 7 项）。
  它们在补齐前分别是 2 项 FAIL（其后加入 `offset.json` 判据时又各自 FAIL 一次） 门禁确实能区分「做过」与「没做」。
- 已存在的旧工程是历史产物，缺证据文件时会被判 FAIL；补证据走 `find_lyrics.py --adopt` 与
  `fetch_anime_bg.py --register`，两者都强制写 why，不提供静默放行。
- 门禁不认识 `timing_grid.json` 这条可选路径的中间产物，只认最终 `timing.json`。